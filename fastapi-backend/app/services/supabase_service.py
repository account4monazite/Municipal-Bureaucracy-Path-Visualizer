

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import AsyncClient, acreate_client

from app.core.settings import get_settings
from app.models import TaskState
from app.models import RoadmapProgress, StepProgress

logger = logging.getLogger(__name__)


class SupabaseService:
    """
    Thin async wrapper around the Supabase client.

    Handles:
    - Session / task-state persistence
    - Roadmap storage & retrieval
    - Progress tracking
    - Government office queries (owned by DB teammate; we query, not own)
    - Source reference retrieval
    """

    def __init__(self) -> None:
        self._client: Optional[AsyncClient] = None

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            settings = get_settings()
            if not settings.supabase_url or not settings.supabase_key:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_KEY must be set in environment variables."
                )
            self._client = await acreate_client(settings.supabase_url, settings.supabase_key)
        return self._client

    # ── Session / task state ─────────────────────────────────────────────────

    async def save_task_state(self, state: TaskState) -> None:
        """Upsert the task state for a session."""
        client = await self._get_client()
        payload = {
            "session_id": state.session_id,
            "intent": state.intent,
            "location": state.location.model_dump(),
            "details": state.details,
            "missing_information": state.missing_information,
            "conversation_history": [m.model_dump() for m in state.conversation_history],
            "roadmap_id": state.roadmap_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        response = (
            await client.table("sessions")
            .upsert(payload, on_conflict="session_id")
            .execute()
        )
        logger.debug("save_task_state: session_id=%s", state.session_id)
        return response

    async def get_task_state(self, session_id: str) -> Optional[TaskState]:
        """Return the task state for a session, or None if not found."""
        client = await self._get_client()
        response = (
            await client.table("sessions")
            .select("*")
            .eq("session_id", session_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            return None
        return TaskState(**response.data)

    # ── Roadmap ──────────────────────────────────────────────────────────────

    async def save_roadmap(self, roadmap_data: Dict[str, Any]) -> str:
        """Persist a generated roadmap.  Returns the roadmap_id."""
        client = await self._get_client()
        roadmap_id = roadmap_data.get("roadmap_id") or str(uuid.uuid4())
        payload = {**roadmap_data, "roadmap_id": roadmap_id}
        await client.table("roadmaps").upsert(payload, on_conflict="roadmap_id").execute()
        logger.info("Roadmap saved: roadmap_id=%s", roadmap_id)
        return roadmap_id

    async def get_roadmap(self, roadmap_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored roadmap by ID."""
        client = await self._get_client()
        response = (
            await client.table("roadmaps")
            .select("*")
            .eq("roadmap_id", roadmap_id)
            .maybe_single()
            .execute()
        )
        return response.data or None

    # ── Progress ─────────────────────────────────────────────────────────────

    async def upsert_step_progress(
        self,
        session_id: str,
        roadmap_id: str,
        step_id: str,
        completed: bool,
    ) -> None:
        client = await self._get_client()
        payload = {
            "session_id": session_id,
            "roadmap_id": roadmap_id,
            "step_id": step_id,
            "completed": completed,
            "completed_at": datetime.now(timezone.utc).isoformat() if completed else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await (
            client.table("progress")
            .upsert(payload, on_conflict="roadmap_id,step_id")
            .execute()
        )
        logger.debug(
            "Progress upsert: roadmap=%s step=%s completed=%s",
            roadmap_id,
            step_id,
            completed,
        )

    async def get_roadmap_progress(self, roadmap_id: str) -> List[StepProgress]:
        client = await self._get_client()
        response = (
            await client.table("progress")
            .select("*")
            .eq("roadmap_id", roadmap_id)
            .execute()
        )
        rows = response.data or []
        return [
            StepProgress(
                step_id=r["step_id"],
                completed=r["completed"],
                completed_at=r.get("completed_at"),
                notes=r.get("notes"),
            )
            for r in rows
        ]

    # ── Government offices (DB teammate owns the table) ──────────────────────

    async def get_nearby_offices(
        self,
        latitude: float,
        longitude: float,
        department: Optional[str] = None,
        radius_km: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """
        Query government offices from the DB teammate's table.
        Uses a PostGIS-compatible distance filter if available,
        otherwise falls back to a simple bounding box.
        """
        client = await self._get_client()
        query = client.table("government_offices").select("*")

        if department:
            query = query.ilike("department", f"%{department}%")

        # Rough bounding-box filter (1 degree ≈ 111 km)
        delta = radius_km / 111.0
        query = (
            query.gte("latitude", latitude - delta)
            .lte("latitude", latitude + delta)
            .gte("longitude", longitude - delta)
            .lte("longitude", longitude + delta)
        )

        response = await query.execute()
        return response.data or []
