"""
Integration tests for the FastAPI app using TestClient.

Tests: health, chat endpoint, roadmap generation, progress tracking.
All external services (Supabase, NLP, LLM) are mocked.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import create_app
from app.dependencies import (
    get_chatbot_service,
    get_nlp_service,
    get_roadmap_service,
    get_supabase_service,
    get_voice_service,
)
from app.models import ChatMessage, TaskLocation, TaskState
from app.models import (
    Roadmap,
    RoadmapEdge,
    RoadmapNode,
    RelationshipType,
    StepType,
)
from app.models import StepProgress


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_test_task_state(session_id: str = "test_session") -> TaskState:
    return TaskState(
        session_id=session_id,
        intent="business_registration",
        location=TaskLocation(city="Mumbai", state="Maharashtra"),
        details={"business_type": "restaurant"},
        missing_information=[],
    )


def _make_test_roadmap() -> Roadmap:
    return Roadmap(
        roadmap_id="roadmap_test123",
        title="Business Registration — Mumbai",
        task="business_registration",
        location=TaskLocation(city="Mumbai", state="Maharashtra"),
        nodes=[
            RoadmapNode(id="step_1", title="Obtain PAN Card", type=StepType.document),
            RoadmapNode(id="step_2", title="GST Registration", type=StepType.registration),
        ],
        edges=[
            RoadmapEdge(source="step_1", target="step_2", relationship=RelationshipType.required_before)
        ],
        sources=[],
    )


@pytest.fixture
def client():
    """TestClient with all external services mocked."""
    app = create_app()

    # ── Mock Supabase ──────────────────────────────────────────────────────
    mock_db = MagicMock()
    mock_db.get_task_state = AsyncMock(return_value=None)
    mock_db.save_task_state = AsyncMock(return_value=None)
    mock_db.get_roadmap = AsyncMock(return_value=None)
    mock_db.save_roadmap = AsyncMock(return_value="roadmap_test123")
    mock_db.upsert_step_progress = AsyncMock(return_value=None)
    mock_db.get_roadmap_progress = AsyncMock(return_value=[])
    mock_db.get_nearby_offices = AsyncMock(return_value=[])

    # ── Mock ChatbotService ────────────────────────────────────────────────
    mock_chatbot = MagicMock()
    mock_chatbot.create_initial_state = MagicMock(
        side_effect=lambda sid: TaskState(session_id=sid)
    )
    mock_chatbot.process_message = AsyncMock(
        return_value=(
            "I can help you register a business. Which city are you in?",
            TaskState(
                session_id="test_session",
                intent="business_registration",
                missing_information=["location"],
            ),
        )
    )

    # ── Mock RoadmapService ────────────────────────────────────────────────
    mock_roadmap_svc = MagicMock()
    mock_roadmap_svc.generate = AsyncMock(return_value=_make_test_roadmap())

    app.dependency_overrides[get_supabase_service] = lambda: mock_db
    app.dependency_overrides[get_chatbot_service] = lambda: mock_chatbot
    app.dependency_overrides[get_roadmap_service] = lambda: mock_roadmap_svc

    with TestClient(app) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ── Chat ──────────────────────────────────────────────────────────────────────


def test_chat_returns_reply(client):
    resp = client.post(
        "/api/chat",
        json={"session_id": "test_session", "message": "I want to register a business"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert data["session_id"] == "test_session"
    assert "task_state" in data


def test_chat_missing_session_id(client):
    resp = client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 422  # Unprocessable entity


def test_chat_missing_message(client):
    resp = client.post("/api/chat", json={"session_id": "sess1"})
    assert resp.status_code == 422


# ── Roadmap ───────────────────────────────────────────────────────────────────


def test_roadmap_generate_returns_nodes_and_edges(client):
    resp = client.post(
        "/api/roadmap/generate",
        json={"session_id": "test_session"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert data["nodes"][0]["id"] == "step_1"
    assert data["edges"][0]["relationship"] == "required_before"


def test_roadmap_validation_error(client):
    from app.services.roadmap_service import RoadmapValidationError

    app = create_app()

    mock_roadmap_svc = MagicMock()
    mock_roadmap_svc.generate = AsyncMock(
        side_effect=RoadmapValidationError("Missing: location")
    )
    app.dependency_overrides[get_roadmap_service] = lambda: mock_roadmap_svc
    app.dependency_overrides[get_supabase_service] = lambda: MagicMock()

    with TestClient(app) as c:
        resp = c.post("/api/roadmap/generate", json={"session_id": "empty_session"})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INCOMPLETE_TASK_STATE"


def test_roadmap_nlp_failure(client):
    from app.services.nlp_service import NLPServiceError

    app = create_app()

    mock_roadmap_svc = MagicMock()
    mock_roadmap_svc.generate = AsyncMock(
        side_effect=NLPServiceError("timeout", status_code=504)
    )
    app.dependency_overrides[get_roadmap_service] = lambda: mock_roadmap_svc
    app.dependency_overrides[get_supabase_service] = lambda: MagicMock()

    with TestClient(app) as c:
        resp = c.post("/api/roadmap/generate", json={"session_id": "sess"})

    assert resp.status_code == 504
    assert resp.json()["error"]["code"] == "NLP_SERVICE_ERROR"


# ── Progress ──────────────────────────────────────────────────────────────────


def test_progress_update(client):
    resp = client.post(
        "/api/progress",
        json={
            "session_id": "test_session",
            "roadmap_id": "roadmap_test123",
            "step_id": "step_1",
            "completed": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "percentage" in data
    assert data["roadmap_id"] == "roadmap_test123"


def test_progress_get(client):
    resp = client.get("/api/progress/roadmap_test123")
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert "percentage" in data


def test_progress_with_completed_steps():
    """Verify percentage calculation with real step data."""
    app = create_app()

    mock_db = MagicMock()
    mock_db.upsert_step_progress = AsyncMock()
    mock_db.get_roadmap_progress = AsyncMock(
        return_value=[
            StepProgress(step_id="step_1", completed=True),
            StepProgress(step_id="step_2", completed=False),
            StepProgress(step_id="step_3", completed=False),
            StepProgress(step_id="step_4", completed=True),
        ]
    )
    app.dependency_overrides[get_supabase_service] = lambda: mock_db

    with TestClient(app) as c:
        resp = c.get("/api/progress/roadmap_abc")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_steps"] == 4
    assert data["completed_steps"] == 2
    assert data["percentage"] == pytest.approx(50.0)


# ── Location ──────────────────────────────────────────────────────────────────


def test_location_resolve_manual(client):
    resp = client.post(
        "/api/location/resolve",
        json={"city": "Mumbai", "state": "Maharashtra", "pincode": "400001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["city"] == "Mumbai"
    assert data["state"] == "Maharashtra"


def test_location_resolve_invalid_body(client):
    resp = client.post("/api/location/resolve", json={})
    assert resp.status_code == 422


# ── Voice ─────────────────────────────────────────────────────────────────────


def test_voice_transcribe_empty_file():
    app = create_app()
    mock_voice = MagicMock()
    mock_voice.transcribe = AsyncMock(return_value="test transcript")
    app.dependency_overrides[get_voice_service] = lambda: mock_voice
    app.dependency_overrides[get_supabase_service] = lambda: MagicMock()

    with TestClient(app) as c:
        resp = c.post(
            "/api/voice/transcribe",
            files={"audio": ("test.wav", b"", "audio/wav")},
        )
    # Empty audio should return 400
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMPTY_AUDIO"


def test_voice_service_failure():
    from app.services.voice_service import VoiceServiceError

    app = create_app()
    mock_voice = MagicMock()
    mock_voice.transcribe = AsyncMock(side_effect=VoiceServiceError("STT unavailable"))
    app.dependency_overrides[get_voice_service] = lambda: mock_voice
    app.dependency_overrides[get_supabase_service] = lambda: MagicMock()

    with TestClient(app) as c:
        resp = c.post(
            "/api/voice/transcribe",
            files={"audio": ("test.wav", b"fake audio bytes", "audio/wav")},
        )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "STT_FAILED"
