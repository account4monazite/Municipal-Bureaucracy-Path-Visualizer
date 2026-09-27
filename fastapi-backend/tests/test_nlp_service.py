"""
Tests for NLPService — mock mode, failure handling, extract_task.
"""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import NLPServiceRequest
from app.services.nlp_service import NLPService, NLPServiceError


def _make_nlp(use_mock: bool = True) -> NLPService:
    with patch("app.services.nlp_service.get_settings") as ms:
        ms.return_value.nlp_service_url = "http://localhost:8001"
        ms.return_value.nlp_service_timeout = 10
        with patch.dict("os.environ", {"USE_MOCK_NLP": "true" if use_mock else "false"}):
            return NLPService()


@pytest.mark.asyncio
async def test_nlp_mock_returns_steps_for_business_registration():
    nlp = _make_nlp(use_mock=True)
    req = NLPServiceRequest(
        task="business_registration",
        location={"city": "Mumbai", "state": "Maharashtra"},
    )
    response = await nlp.fetch_requirements(req)
    assert response.task == "business_registration"
    assert len(response.steps) > 0


@pytest.mark.asyncio
async def test_nlp_mock_returns_empty_for_unknown_task():
    nlp = _make_nlp(use_mock=True)
    req = NLPServiceRequest(task="some_unknown_task", location={})
    response = await nlp.fetch_requirements(req)
    assert response.steps == []


@pytest.mark.asyncio
async def test_nlp_real_timeout_raises_error():
    nlp = _make_nlp(use_mock=False)
    req = NLPServiceRequest(task="business_registration", location={})

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        with pytest.raises(NLPServiceError) as exc_info:
            await nlp.fetch_requirements(req)

    assert exc_info.value.status_code == 504


@pytest.mark.asyncio
async def test_nlp_real_connection_error_raises_503():
    nlp = _make_nlp(use_mock=False)
    req = NLPServiceRequest(task="business_registration", location={})

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        with pytest.raises(NLPServiceError) as exc_info:
            await nlp.fetch_requirements(req)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_extract_task_mock_detects_business_registration():
    nlp = _make_nlp(use_mock=True)
    result = await nlp.extract_task("I want to register a small restaurant in Mumbai")
    assert result["intent"] == "business_registration"
    assert result["location"]["city"] == "Mumbai"
    assert result["details"]["business_type"] == "restaurant"


@pytest.mark.asyncio
async def test_extract_task_mock_unknown_intent():
    nlp = _make_nlp(use_mock=True)
    result = await nlp.extract_task("I want to do something random")
    assert result["intent"] is None


@pytest.mark.asyncio
async def test_extract_task_mock_detects_aadhaar_update():
    nlp = _make_nlp(use_mock=True)
    result = await nlp.extract_task("i want to update my aadhar card")
    assert result["intent"] == "aadhaar_update"
