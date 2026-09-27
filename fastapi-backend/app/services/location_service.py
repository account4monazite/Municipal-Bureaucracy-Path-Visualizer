

from __future__ import annotations

import logging
import math
from typing import Optional, Protocol, runtime_checkable

import httpx

from app.core.settings import get_settings
from app.models import ResolvedLocation

logger = logging.getLogger(__name__)

# ── Provider protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class LocationProvider(Protocol):
    async def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[ResolvedLocation]: ...


# ── Nominatim (OpenStreetMap) ─────────────────────────────────────────────────


class NominatimProvider:
    BASE_URL = "https://nominatim.openstreetmap.org/reverse"

    async def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[ResolvedLocation]:
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
        }
        headers = {"User-Agent": "CivicTaskNavigator/1.0"}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(self.BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                logger.warning("Nominatim request failed: %s", exc)
                return None

        addr = data.get("address", {})
        return ResolvedLocation(
            latitude=latitude,
            longitude=longitude,
            city=(
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("municipality")
            ),
            district=addr.get("state_district") or addr.get("county"),
            state=addr.get("state"),
            country=addr.get("country"),
            pincode=addr.get("postcode"),
            geocoded=True,
        )


# ── Google Maps provider ──────────────────────────────────────────────────────


class GoogleMapsProvider:
    BASE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[ResolvedLocation]:
        params = {"latlng": f"{latitude},{longitude}", "key": self._key}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                logger.warning("Google Maps geocoding failed: %s", exc)
                return None

        if data.get("status") != "OK":
            logger.warning("Google Maps API status: %s", data.get("status"))
            return None

        result = data["results"][0] if data["results"] else {}
        components = result.get("address_components", [])

        def get_comp(component_type: str) -> Optional[str]:
            for c in components:
                if component_type in c.get("types", []):
                    return c.get("long_name")
            return None

        return ResolvedLocation(
            latitude=latitude,
            longitude=longitude,
            city=get_comp("locality") or get_comp("administrative_area_level_3"),
            district=get_comp("administrative_area_level_2"),
            state=get_comp("administrative_area_level_1"),
            country=get_comp("country"),
            pincode=get_comp("postal_code"),
            geocoded=True,
        )


# ── Distance helper ───────────────────────────────────────────────────────────


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


# ── Service facade ────────────────────────────────────────────────────────────


class LocationService:
    """
    Facade that selects the correct geocoding provider from config and
    provides a unified reverse-geocode interface.
    """

    def __init__(self) -> None:
        settings = get_settings()
        provider_name = settings.geocoding_provider.lower()

        if provider_name == "google":
            if not settings.geocoding_api_key:
                raise EnvironmentError(
                    "GEOCODING_API_KEY must be set when using the Google Maps provider."
                )
            self._provider: LocationProvider = GoogleMapsProvider(settings.geocoding_api_key)
        else:
            # Default: free Nominatim
            self._provider = NominatimProvider()

        logger.info("LocationService initialized with provider: %s", provider_name)

    async def resolve_coordinates(
        self, latitude: float, longitude: float
    ) -> ResolvedLocation:
        """Reverse-geocode GPS coordinates into administrative context."""
        result = await self._provider.reverse_geocode(latitude, longitude)
        if result is None:
            logger.warning(
                "Geocoding returned no result for (%s, %s)", latitude, longitude
            )
            return ResolvedLocation(latitude=latitude, longitude=longitude, geocoded=False)
        return result

    def resolve_manual(
        self,
        city: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        pincode: Optional[str] = None,
    ) -> ResolvedLocation:
        """Return a ResolvedLocation from manually provided fields (no API call)."""
        return ResolvedLocation(
            city=city,
            district=district,
            state=state,
            country=country,
            pincode=pincode,
            geocoded=False,
        )
