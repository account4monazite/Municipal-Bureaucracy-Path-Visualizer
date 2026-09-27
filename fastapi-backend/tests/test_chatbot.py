"""
Tests for ChatbotService — intent extraction, state merging, missing info detection.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import ChatMessage, TaskState, TaskLocation
from app.services.chatbot_service import ChatbotService
from app.services.nlp_service import NLPService


def _make_chatbot() -> ChatbotService:
    """Create a ChatbotService with LLM disabled."""
    nlp = MagicMock(spec=NLPService)
    with patch("app.services.chatbot_service.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = ""
        mock_settings.return_value.groq_model = "openai/gpt-oss-20b"
        return ChatbotService(nlp_service=nlp)


# ── create_initial_state ──────────────────────────────────────────────────────


def test_create_initial_state_empty():
    cb = _make_chatbot()
    state = cb.create_initial_state("sess1")
    assert state.session_id == "sess1"
    assert state.intent is None
    assert state.missing_information == []


# ── _merge_extracted ──────────────────────────────────────────────────────────


def test_merge_extracted_populates_intent():
    cb = _make_chatbot()
    state = TaskState(session_id="s1")
    extracted = {
        "intent": "business_registration",
        "location": {"city": "Mumbai", "state": "Maharashtra"},
        "details": {"business_type": "restaurant"},
    }
    updated = cb._merge_extracted(state, extracted)
    assert updated.intent == "business_registration"
    assert updated.location.city == "Mumbai"
    assert updated.details["business_type"] == "restaurant"


def test_merge_extracted_updates_intent_for_new_explicit_task():
    cb = _make_chatbot()
    state = TaskState(session_id="s1", intent="passport_application")
    extracted = {"intent": "income_certificate", "location": None, "details": {}}
    updated = cb._merge_extracted(state, extracted)
    assert updated.intent == "income_certificate"


# ── _compute_missing ──────────────────────────────────────────────────────────


def test_compute_missing_no_intent_no_location():
    cb = _make_chatbot()
    state = TaskState(session_id="s1")
    missing = cb._compute_missing(state)
    assert "civic_task" in missing
    assert "location" in missing


def test_compute_missing_treats_unknown_intent_as_missing():
    cb = _make_chatbot()
    state = TaskState(session_id="s1", intent="unknown")

    assert "civic_task" in cb._compute_missing(state)


def test_merge_extracted_replaces_unknown_intent():
    cb = _make_chatbot()
    state = TaskState(session_id="s1", intent="unknown")

    updated = cb._merge_extracted(state, {"intent": "aadhaar_update"})

    assert updated.intent == "aadhaar_update"
def test_compute_missing_has_intent_no_location():
    cb = _make_chatbot()
    state = TaskState(session_id="s1", intent="business_registration")
    missing = cb._compute_missing(state)
    assert "civic_task" not in missing
    assert "location" in missing


def test_compute_missing_complete_state():
    cb = _make_chatbot()
    state = TaskState(
        session_id="s1",
        intent="business_registration",
        location=TaskLocation(city="Mumbai", state="Maharashtra"),
    )
    missing = cb._compute_missing(state)
    assert missing == []


# ── process_message (async, rule-based) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_process_message_asks_for_task():
    """No intent → asks what task the user wants to accomplish."""
    nlp = MagicMock(spec=NLPService)
    nlp.extract_task = AsyncMock(return_value={"intent": None, "location": None, "details": {}})

    with patch("app.services.chatbot_service.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = ""
        mock_settings.return_value.groq_model = "openai/gpt-oss-20b"
        cb = ChatbotService(nlp_service=nlp)

    state = cb.create_initial_state("sess1")
    reply, updated = await cb.process_message(state, "hello")
    assert "accomplish" in reply.lower() or "register" in reply.lower() or "help" in reply.lower()
    assert "civic_task" in updated.missing_information


@pytest.mark.asyncio
async def test_process_message_extracts_business_registration():
    """Detecting business registration intent from a message."""
    nlp = MagicMock(spec=NLPService)
    nlp.extract_task = AsyncMock(
        return_value={
            "intent": "business_registration",
            "location": {"city": "Mumbai", "state": "Maharashtra"},
            "details": {"business_type": "restaurant"},
        }
    )

    with patch("app.services.chatbot_service.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = ""
        mock_settings.return_value.groq_model = "openai/gpt-oss-20b"
        cb = ChatbotService(nlp_service=nlp)

    state = cb.create_initial_state("sess1")
    reply, updated = await cb.process_message(
        state, "I want to open a restaurant in Mumbai"
    )
    assert updated.intent == "business_registration"
    assert updated.location.city == "Mumbai"
    assert updated.missing_information == []
    assert "roadmap" in reply.lower() or "generate" in reply.lower() or "proceed" in reply.lower()


@pytest.mark.asyncio
async def test_groq_reply_uses_chat_history_and_configured_model():
    nlp = MagicMock(spec=NLPService)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Groq reply"))]
        )
    )
    mock_groq = MagicMock(AsyncGroq=MagicMock(return_value=mock_client))
    settings = SimpleNamespace(
        groq_api_key="test-key",
        groq_model="openai/gpt-oss-20b",
    )

    with patch("app.services.chatbot_service.get_settings", return_value=settings):
        with patch.dict("sys.modules", {"groq": mock_groq}):
            chatbot = ChatbotService(nlp_service=nlp)

    state = TaskState(session_id="groq-test")
    state.conversation_history.append(ChatMessage(role="user", content="Earlier question"))
    state.conversation_history.append(ChatMessage(role="user", content="Current question"))
    reply = await chatbot._llm_reply(state, "Current question")

    assert reply == "Groq reply"
    mock_client.chat.completions.create.assert_awaited_once()
    call = mock_client.chat.completions.create.await_args
    assert call is not None
    request = call.kwargs
    assert request["model"] == "openai/gpt-oss-20b"
    assert request["messages"][0]["role"] == "system"
    assert {"role": "user", "content": "Earlier question"} in request["messages"]
    assert request["messages"][-1] == {"role": "user", "content": "Current question"}
