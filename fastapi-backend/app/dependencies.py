

from __future__ import annotations

from functools import lru_cache

from app.services.chatbot_service import ChatbotService
from app.services.location_service import LocationService
from app.services.nlp_service import NLPService
from app.services.roadmap_service import RoadmapService
from app.services.supabase_service import SupabaseService
from app.services.voice_service import VoiceService


@lru_cache
def get_nlp_service() -> NLPService:
    return NLPService()


@lru_cache
def get_supabase_service() -> SupabaseService:
    return SupabaseService()


@lru_cache
def get_location_service() -> LocationService:
    return LocationService()


@lru_cache
def get_voice_service() -> VoiceService:
    return VoiceService()


def get_chatbot_service() -> ChatbotService:
    return ChatbotService(nlp_service=get_nlp_service())


def get_roadmap_service() -> RoadmapService:
    return RoadmapService(
        nlp_service=get_nlp_service(),
        supabase_service=get_supabase_service(),
    )
