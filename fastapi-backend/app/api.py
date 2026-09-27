from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, Form, UploadFile
from pydantic import BaseModel

from app.dependencies import (
    get_chatbot_service, get_location_service, get_roadmap_service, get_supabase_service, get_voice_service
)
from app.models import (
    ChatRequest, ChatResponse, TaskState, LocationResolveRequest, ResolvedLocation, 
    NearbyOfficesResponse, GovernmentOffice, RoadmapGenerateRequest, Roadmap, 
    ProgressUpdateRequest, RoadmapProgress
)
from app.services.chatbot_service import ChatbotService
from app.services.location_service import LocationService
from app.services.roadmap_service import RoadmapService, RoadmapValidationError
from app.services.supabase_service import SupabaseService
from app.services.voice_service import VoiceService, VoiceServiceError
from app.services.nlp_service import NLPServiceError

logger = logging.getLogger(__name__)
api_router = APIRouter(prefix="/api")

# --- Location Routes ---

@api_router.post("/location/resolve", response_model=ResolvedLocation)
async def resolve_location(
    body: LocationResolveRequest,
    location_service: LocationService = Depends(get_location_service),
) -> ResolvedLocation:
    has_coords = body.latitude is not None and body.longitude is not None
    if has_coords:
        result = await location_service.resolve_coordinates(body.latitude, body.longitude) # type: ignore
        if not result.geocoded:
            raise HTTPException(status_code=502, detail={"error": {"code": "GEOCODING_FAILED", "message": "Failed"}})
        return result
    return location_service.resolve_manual(city=body.city, district=body.district, state=body.state, country=body.country, pincode=body.pincode)

@api_router.get("/offices/nearby", response_model=NearbyOfficesResponse)
async def get_nearby_offices(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    department: Optional[str] = Query(None),
    radius_km: float = Query(10.0, gt=0, le=100),
    db: SupabaseService = Depends(get_supabase_service),
    location_service: LocationService = Depends(get_location_service),
) -> NearbyOfficesResponse:
    from app.services.location_service import haversine_km
    try:
        rows = await db.get_nearby_offices(latitude=latitude, longitude=longitude, department=department, radius_km=radius_km)
    except Exception:
        raise HTTPException(status_code=503, detail={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Error"}})
    
    offices = []
    for row in rows:
        dist = haversine_km(latitude, longitude, row["latitude"], row["longitude"])
        if dist <= radius_km:
            offices.append(GovernmentOffice(id=row["id"], name=row["name"], department=row["department"], address=row.get("address", ""), latitude=row["latitude"], longitude=row["longitude"], distance_km=round(dist, 2), phone=row.get("phone"), email=row.get("email"), website=row.get("website"), source_url=row.get("source_url")))
    offices.sort(key=lambda o: o.distance_km or 0)
    return NearbyOfficesResponse(offices=offices)

# --- Chat Routes ---

@api_router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    chatbot: ChatbotService = Depends(get_chatbot_service),
    db: SupabaseService = Depends(get_supabase_service),
) -> ChatResponse:
    logger.info("Chat request received (session_id=%s)", body.session_id)
    try:
        state = await db.get_task_state(body.session_id) or chatbot.create_initial_state(body.session_id)
    except Exception:
        logger.warning(
            "Could not load chat session; starting fresh (session_id=%s)",
            body.session_id,
            exc_info=True,
        )
        state = chatbot.create_initial_state(body.session_id)
    
    try:
        reply, updated_state = await chatbot.process_message(state, body.message)
    except Exception:
        logger.exception("Chat message processing failed (session_id=%s)", body.session_id)
        raise HTTPException(status_code=500, detail={"error": {"code": "CHATBOT_ERROR", "message": "Error"}})
        
    try:
        await db.save_task_state(updated_state)
    except Exception:
        logger.warning(
            "Could not save chat session (session_id=%s)",
            body.session_id,
            exc_info=True,
        )

    logger.info("Chat request completed (session_id=%s)", body.session_id)
        
    return ChatResponse(session_id=body.session_id, reply=reply, task_state=updated_state, sources=[])

# --- Roadmap Routes ---

@api_router.post("/roadmap/generate", response_model=Roadmap)
async def generate_roadmap(
    body: RoadmapGenerateRequest,
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> Roadmap:
    try:
        return await roadmap_service.generate(body.session_id)
    except RoadmapValidationError as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "INCOMPLETE_TASK_STATE", "message": str(exc)}})
    except NLPServiceError as exc:
        status_map = {504: 504, 503: 503}
        raise HTTPException(status_code=status_map.get(exc.status_code or 0, 502), detail={"error": {"code": "NLP_SERVICE_ERROR", "message": "Error"}})
    except Exception:
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "Error"}})

@api_router.get("/roadmap/{roadmap_id}", response_model=Roadmap)
async def get_roadmap(roadmap_id: str, db: SupabaseService = Depends(get_supabase_service)) -> Roadmap:
    try:
        data = await db.get_roadmap(roadmap_id)
    except Exception:
        raise HTTPException(status_code=503, detail={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Error"}})
    if not data:
        raise HTTPException(status_code=404, detail={"error": {"code": "ROADMAP_NOT_FOUND", "message": "Not found"}})
    return Roadmap(**data)

# --- Progress Routes ---

@api_router.post("/progress", response_model=RoadmapProgress)
async def update_progress(body: ProgressUpdateRequest, db: SupabaseService = Depends(get_supabase_service)) -> RoadmapProgress:
    try:
        await db.upsert_step_progress(session_id=body.session_id, roadmap_id=body.roadmap_id, step_id=body.step_id, completed=body.completed)
        steps = await db.get_roadmap_progress(body.roadmap_id)
    except Exception:
        raise HTTPException(status_code=503, detail={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Error"}})
    
    completed_count = sum(1 for s in steps if s.completed)
    total = len(steps)
    percentage = (completed_count / total * 100) if total > 0 else 0.0
    return RoadmapProgress(roadmap_id=body.roadmap_id, session_id=body.session_id, steps=steps, total_steps=total, completed_steps=completed_count, percentage=round(percentage, 1))

@api_router.get("/progress/{roadmap_id}", response_model=RoadmapProgress)
async def get_progress(roadmap_id: str, db: SupabaseService = Depends(get_supabase_service)) -> RoadmapProgress:
    try:
        steps = await db.get_roadmap_progress(roadmap_id)
    except Exception:
        raise HTTPException(status_code=503, detail={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Error"}})
    
    completed_count = sum(1 for s in steps if s.completed)
    total = len(steps)
    percentage = (completed_count / total * 100) if total > 0 else 0.0
    return RoadmapProgress(roadmap_id=roadmap_id, session_id="", steps=steps, total_steps=total, completed_steps=completed_count, percentage=round(percentage, 1))

# --- Voice Routes ---

class TranscribeResponse(BaseModel):
    transcript: str
    confidence: float = 1.0

class VoiceRespondResponse(BaseModel):
    transcript: str
    reply_text: str
    reply_audio_b64: str
    task_state: TaskState
    audio_mime_type: str = "audio/mpeg"

@api_router.post("/voice/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    voice: VoiceService = Depends(get_voice_service),
) -> TranscribeResponse:
    mime_type = audio.content_type or "audio/wav"
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_AUDIO", "message": "Empty"}})
    try:
        transcript = await voice.transcribe(audio_bytes, mime_type)
    except VoiceServiceError as exc:
        raise HTTPException(status_code=503, detail={"error": {"code": "STT_FAILED", "message": str(exc)}})
    return TranscribeResponse(transcript=transcript)

@api_router.post("/voice/respond", response_model=VoiceRespondResponse)
async def voice_respond(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    voice: VoiceService = Depends(get_voice_service),
    chatbot: ChatbotService = Depends(get_chatbot_service),
    db: SupabaseService = Depends(get_supabase_service),
) -> VoiceRespondResponse:
    mime_type = audio.content_type or "audio/wav"
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_AUDIO", "message": "Empty"}})
        
    try:
        transcript = await voice.transcribe(audio_bytes, mime_type)
    except VoiceServiceError as exc:
        raise HTTPException(status_code=503, detail={"error": {"code": "STT_FAILED", "message": str(exc)}})
        
    if not transcript.strip():
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_TRANSCRIPT", "message": "Empty"}})
        
    state = await db.get_task_state(session_id) or chatbot.create_initial_state(session_id)
    try:
        reply_text, updated_state = await chatbot.process_message(state, transcript)
    except Exception:
        raise HTTPException(status_code=500, detail={"error": {"code": "CHATBOT_ERROR", "message": "Error"}})
        
    await db.save_task_state(updated_state)
    
    reply_audio_b64 = ""
    try:
        reply_audio_bytes = await voice.synthesize(reply_text)
        if reply_audio_bytes:
            reply_audio_b64 = base64.b64encode(reply_audio_bytes).decode()
    except VoiceServiceError:
        pass
        
    return VoiceRespondResponse(
        transcript=transcript,
        reply_text=reply_text,
        reply_audio_b64=reply_audio_b64,
        task_state=updated_state,
    )
