

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from app.models import SourceReference, TaskState
from app.models import (
    NLPServiceRequest,
    NLPServiceResponse,
    Roadmap,
    RoadmapEdge,
    RoadmapNode,
    RelationshipType,
    StepType,
)
from app.services.nlp_service import NLPService, NLPServiceError
from app.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)


class RoadmapValidationError(Exception):
    """Raised when task state lacks required fields for roadmap generation."""


class RoadmapService:
    def __init__(self, nlp_service: NLPService, supabase_service: SupabaseService) -> None:
        self._nlp = nlp_service
        self._db = supabase_service

    async def generate(self, session_id: str) -> Roadmap:
        """
        Full roadmap generation pipeline.
        Raises RoadmapValidationError if task state is incomplete.
        Raises NLPServiceError on downstream failures.
        """
        # 1. Load task state
        state = await self._db.get_task_state(session_id)
        if state is None:
            raise RoadmapValidationError(
                f"No session found for session_id='{session_id}'. "
                "Start a conversation first via /api/chat."
            )

        # 2. Validate completeness
        self._validate_state(state)

        # 3. Fetch requirements from NLP service
        request = NLPServiceRequest(
            task=state.intent,  # type: ignore[arg-type]
            location=state.location.model_dump(exclude_none=True),
            details=state.details,
        )
        nlp_response = await self._nlp.fetch_requirements(request)

        # 4. Build roadmap
        roadmap = self._build_roadmap(state, nlp_response)

        # 5. Persist
        await self._db.save_roadmap(roadmap.model_dump())

        # 6. Update session with roadmap_id
        state.roadmap_id = roadmap.roadmap_id
        await self._db.save_task_state(state)

        logger.info(
            "Roadmap generated: roadmap_id=%s session_id=%s task=%s",
            roadmap.roadmap_id,
            session_id,
            state.intent,
        )
        return roadmap

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_state(self, state: TaskState) -> None:
        errors: List[str] = []
        if not state.intent:
            errors.append("civic task (e.g. business_registration)")
        if not state.location.city and not state.location.state:
            errors.append("location (city or state)")
        if errors:
            raise RoadmapValidationError(
                "Cannot generate roadmap. Missing: " + "; ".join(errors) + ". "
                "Please continue the conversation to provide these details."
            )

    def _build_roadmap(self, state: TaskState, nlp_response: NLPServiceResponse) -> Roadmap:
        """Transform raw NLP service data into a typed Roadmap."""
        roadmap_id = f"roadmap_{uuid.uuid4().hex[:12]}"
        task_display = (state.intent or "Civic Task").replace("_", " ").title()
        city = state.location.city or state.location.state or "India"

        nodes = [self._parse_node(step) for step in nlp_response.steps]
        edges = [self._parse_edge(dep) for dep in nlp_response.dependencies]
        sources = [self._parse_source(src) for src in nlp_response.sources]

        return Roadmap(
            roadmap_id=roadmap_id,
            title=f"{task_display} — {city}",
            task=state.intent or "unknown",
            location=state.location,
            nodes=nodes,
            edges=edges,
            sources=sources,
        )

    @staticmethod
    def _parse_node(step: Dict[str, Any]) -> RoadmapNode:
        source = SourceReference(
            source_url=step.get("source_url"),
            source_title=step.get("source_title"),
            last_verified=step.get("last_verified"),
            confidence="verified" if step.get("source_url") else "uncertain",
        )
        try:
            step_type = StepType(step.get("type", "other"))
        except ValueError:
            step_type = StepType.other

        return RoadmapNode(
            id=step.get("id", str(uuid.uuid4())),
            title=step.get("title", "Untitled Step"),
            type=step_type,
            description=step.get("description", ""),
            mandatory=step.get("mandatory", True),
            estimated_time=step.get("estimated_time"),
            estimated_cost=step.get("estimated_cost"),
            required_documents=step.get("required_documents", []),
            office_name=step.get("office_name"),
            office_id=step.get("office_id"),
            form_number=step.get("form_number"),
            source=source,
        )

    @staticmethod
    def _parse_edge(dep: Dict[str, Any]) -> RoadmapEdge:
        try:
            rel = RelationshipType(dep.get("relationship", "required_before"))
        except ValueError:
            rel = RelationshipType.required_before
        return RoadmapEdge(
            source=dep["source"],
            target=dep["target"],
            relationship=rel,
        )

    @staticmethod
    def _parse_source(src: Dict[str, Any]) -> SourceReference:
        return SourceReference(
            source_url=src.get("source_url"),
            source_title=src.get("source_title"),
            last_verified=src.get("last_verified"),
            confidence="verified" if src.get("source_url") else "uncertain",
        )
