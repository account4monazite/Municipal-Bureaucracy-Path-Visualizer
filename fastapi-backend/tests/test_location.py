"""
Tests for LocationService and location validation.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import LocationResolveRequest, ResolvedLocation
from app.services.location_service import LocationService, NominatimProvider, haversine_km


# ── Unit: coordinate validation ───────────────────────────────────────────────


def test_location_request_requires_coords_or_manual():
    """Providing neither coords nor manual fields should raise ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LocationResolveRequest()


def test_location_request_accepts_coords():
    req = LocationResolveRequest(latitude=19.076, longitude=72.8777)
    assert req.latitude == 19.076


def test_location_request_accepts_manual():
    req = LocationResolveRequest(city="Mumbai", state="Maharashtra")
    assert req.city == "Mumbai"


def test_location_request_rejects_invalid_latitude():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LocationResolveRequest(latitude=200, longitude=72.8777)


# ── Unit: LocationService manual resolution ───────────────────────────────────


def test_resolve_manual_returns_correct_fields():
    with patch("app.services.location_service.get_settings") as mock_settings:
        mock_settings.return_value.geocoding_provider = "nominatim"
        mock_settings.return_value.geocoding_api_key = ""
        svc = LocationService()
    result = svc.resolve_manual(city="Mumbai", state="Maharashtra", pincode="400001")
    assert result.city == "Mumbai"
    assert result.state == "Maharashtra"
    assert result.pincode == "400001"
    assert result.geocoded is False


# ── Unit: haversine distance ──────────────────────────────────────────────────


def test_haversine_same_point():
    assert haversine_km(19.076, 72.877, 19.076, 72.877) == pytest.approx(0.0, abs=0.001)


def test_haversine_known_distance():
    # Mumbai to Pune ~120 km
    dist = haversine_km(19.076, 72.877, 18.5204, 73.8567)
    assert 110 < dist < 140


# ── Async: Nominatim provider with mocked HTTP ───────────────────────────────


@pytest.mark.asyncio
async def test_nominatim_provider_success():
    mock_response_data = {
        "address": {
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
            "postcode": "400001",
            "state_district": "Mumbai District",
        }
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        provider = NominatimProvider()
        result = await provider.reverse_geocode(19.076, 72.877)

    assert result is not None
    assert result.city == "Mumbai"
    assert result.state == "Maharashtra"
    assert result.geocoded is True


@pytest.mark.asyncio
async def test_nominatim_provider_failure_returns_none():
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        provider = NominatimProvider()
        result = await provider.reverse_geocode(19.076, 72.877)

    assert result is None


# ── Async: resolve_coordinates failure → geocoded=False ──────────────────────


@pytest.mark.asyncio
async def test_resolve_coordinates_geocoding_failure():
    with patch("app.services.location_service.get_settings") as mock_settings:
        mock_settings.return_value.geocoding_provider = "nominatim"
        mock_settings.return_value.geocoding_api_key = ""
        svc = LocationService()

    svc._provider = AsyncMock()
    svc._provider.reverse_geocode = AsyncMock(return_value=None)

    result = await svc.resolve_coordinates(0.0, 0.0)
    assert result.geocoded is False
    assert result.latitude == 0.0
