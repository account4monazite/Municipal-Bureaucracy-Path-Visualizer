

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.settings import get_settings
from app.models import NLPServiceRequest, NLPServiceResponse

logger = logging.getLogger(__name__)


# ── Errors ────────────────────────────────────────────────────────────────────


class NLPServiceError(Exception):
    """Raised when the NLP service call fails."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ── Mock data for development ─────────────────────────────────────────────────

_MOCK_RESPONSES: Dict[str, Dict[str, Any]] = {
    "business_registration": {
        "task": "business_registration",
        "steps": [
            {
                "id": "step_1",
                "title": "Obtain PAN Card",
                "type": "document",
                "description": "A PAN card is mandatory for any business entity in India.",
                "mandatory": True,
                "estimated_time": "7-10 days",
                "source_url": "https://www.incometax.gov.in/iec/foportal/",
                "source_title": "Income Tax India — PAN",
                "last_verified": "2024-01-01",
            },
            {
                "id": "step_2",
                "title": "Register on Udyam Portal (MSME)",
                "type": "registration",
                "description": (
                    "Micro, Small & Medium Enterprises must register on the Udyam portal "
                    "for government benefits and recognition."
                ),
                "mandatory": True,
                "estimated_time": "1-2 days",
                "source_url": "https://udyamregistration.gov.in/",
                "source_title": "Udyam Registration Portal",
                "last_verified": "2024-01-01",
            },
            {
                "id": "step_3",
                "title": "GST Registration",
                "type": "registration",
                "description": (
                    "Businesses with turnover above the threshold must register for GST. "
                    "Restaurants serving food must collect GST."
                ),
                "mandatory": True,
                "estimated_time": "3-7 days",
                "source_url": "https://www.gst.gov.in/",
                "source_title": "GST Portal — India",
                "last_verified": "2024-01-01",
            },
            {
                "id": "step_4",
                "title": "FSSAI License (Food Business)",
                "type": "application",
                "description": (
                    "Food Safety and Standards Authority of India (FSSAI) license is "
                    "mandatory for all food businesses including restaurants."
                ),
                "mandatory": True,
                "estimated_time": "30-60 days",
                "estimated_cost": "₹100–₹7,500 per year depending on turnover",
                "source_url": "https://foscos.fssai.gov.in/",
                "source_title": "FSSAI FoSCoS Portal",
                "last_verified": "2024-01-01",
            },
            {
                "id": "step_5",
                "title": "Shop and Establishment Registration",
                "type": "registration",
                "description": (
                    "Register under the Maharashtra Shops and Establishments Act "
                    "with the local municipal authority."
                ),
                "mandatory": True,
                "estimated_time": "7-14 days",
                "source_url": "https://aaplesarkar.mahaonline.gov.in/",
                "source_title": "Maharashtra e-Services Portal",
                "last_verified": "2024-01-01",
            },
        ],
        "dependencies": [
            {"source": "step_1", "target": "step_2", "relationship": "required_before"},
            {"source": "step_1", "target": "step_3", "relationship": "required_before"},
            {"source": "step_2", "target": "step_4", "relationship": "recommended_before"},
            {"source": "step_3", "target": "step_4", "relationship": "recommended_before"},
            {"source": "step_4", "target": "step_5", "relationship": "parallel"},
        ],
        "sources": [
            {
                "source_url": "https://www.startupindia.gov.in/",
                "source_title": "Startup India Portal",
                "last_verified": "2024-01-01",
            }
        ],
    }
}


def _get_mock_response(task: str) -> NLPServiceResponse:
    mock = _MOCK_RESPONSES.get(task) or {
        "task": task,
        "steps": [],
        "requirements": [],
        "dependencies": [],
        "sources": [],
    }
    return NLPServiceResponse(**mock)


# ── NLP Service ───────────────────────────────────────────────────────────────


class NLPService:
    """
    Client for the NLP / government-scraping microservice.

    When NLP_SERVICE_URL is set and the service is reachable, the real service
    is called.  When USE_MOCK_NLP=true (default in development) or the service
    is unreachable, the mock data is used instead.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.nlp_service_url.rstrip("/")
        self._timeout = settings.nlp_service_timeout
        self._use_mock = settings.use_mock_nlp
        logger.info(
            "NLPService ready (base_url=%s, use_mock=%s)", self._base_url, self._use_mock
        )

    @staticmethod
    def _extract_location(user_message: str) -> Optional[Dict[str, str]]:
        msg = user_message.lower()
        locations = {
            "seawoods darave": {"city": "Navi Mumbai", "district": "Thane", "state": "Maharashtra"},
            "seawoods": {"city": "Navi Mumbai", "district": "Thane", "state": "Maharashtra"},
            "darave": {"city": "Navi Mumbai", "district": "Thane", "state": "Maharashtra"},
            "belapur": {"city": "Navi Mumbai", "district": "Thane", "state": "Maharashtra"},
            "mumbai": {"city": "Mumbai", "state": "Maharashtra"},
            "delhi": {"city": "Delhi", "state": "Delhi"},
            "bangalore": {"city": "Bangalore", "state": "Karnataka"},
            "bengaluru": {"city": "Bangalore", "state": "Karnataka"},
            "chennai": {"city": "Chennai", "state": "Tamil Nadu"},
            "hyderabad": {"city": "Hyderabad", "state": "Telangana"},
            "pune": {"city": "Pune", "state": "Maharashtra"},
            "kolkata": {"city": "Kolkata", "state": "West Bengal"},
        }
        for keyword, location in locations.items():
            if keyword in msg:
                return location
        return None

    @staticmethod
    def _extract_intent(user_message: str) -> Optional[str]:
        msg = user_message.lower()
        if any(word in msg for word in ["income certificate", "income cert", "income proof"]):
            return "income_certificate"
        if any(word in msg for word in ["aadhaar", "aadhar", "uidai"]):
            return "aadhaar_update"
        if "birth certificate" in msg:
            return "birth_certificate"
        if "passport" in msg:
            return "passport_application"
        if any(word in msg for word in ["driving", "licence", "license", "dl"]):
            return "driving_license"
        if any(word in msg for word in ["register", "registration", "business", "company", "firm"]):
            return "business_registration"
        return None

    async def fetch_requirements(self, request: NLPServiceRequest) -> NLPServiceResponse:
        """
        Call the NLP/scraping service to get structured government requirements.

        Falls back to mock data if:
          - USE_MOCK_NLP=true
          - The service is unreachable (connection error)
          - The request times out
        """
        if self._use_mock:
            logger.info("NLPService: using mock data for task=%s", request.task)
            return _get_mock_response(request.task)

        url = f"{self._base_url}/internal/government/search"
        payload = request.model_dump()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.TimeoutException:
                logger.error("NLPService timeout (url=%s, timeout=%ss)", url, self._timeout)
                raise NLPServiceError("NLP service timed out.", status_code=504)
            except httpx.ConnectError:
                logger.error("NLPService connection failed: %s", url)
                raise NLPServiceError("Cannot connect to NLP service.", status_code=503)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "NLPService HTTP error: %s %s", exc.response.status_code, exc.response.text
                )
                raise NLPServiceError(
                    f"NLP service returned {exc.response.status_code}.",
                    status_code=exc.response.status_code,
                )
            except json.JSONDecodeError:
                raise NLPServiceError("NLP service returned invalid JSON.", status_code=502)

        try:
            return NLPServiceResponse(**data)
        except Exception as exc:
            logger.error("NLPService response parse error: %s", exc)
            raise NLPServiceError(f"Invalid NLP service response schema: {exc}", status_code=502)

    async def extract_task(self, user_message: str, llm_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Ask the NLP service to extract structured task info from a user message.

        This is a lightweight call — not a full scrape.
        Falls back gracefully.
        """
        if self._use_mock:
            # Minimal keyword-based extraction for development
            intent = self._extract_intent(user_message)
            location = self._extract_location(user_message)
            details: Dict[str, Any] = {}

            msg = user_message.lower()

            if "restaurant" in msg:
                details["business_type"] = "restaurant"
            elif "shop" in msg or "store" in msg:
                details["business_type"] = "retail_shop"
            elif "cafe" in msg or "coffee" in msg:
                details["business_type"] = "cafe"

            return {"intent": intent, "location": location, "details": details}

        url = f"{self._base_url}/internal/nlp/extract"
        payload = {"message": user_message, "context": llm_context}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and not data.get("intent"):
                    extracted_intent = self._extract_intent(user_message)
                    if extracted_intent:
                        data["intent"] = extracted_intent
                extracted_location = self._extract_location(user_message)
                if extracted_location and isinstance(data, dict):
                    remote_location = data.get("location")
                    if not isinstance(remote_location, dict):
                        remote_location = {}
                        data["location"] = remote_location
                    for key, value in extracted_location.items():
                        remote_location.setdefault(key, value)
                return data
            except Exception as exc:
                logger.warning("NLPService extract_task failed, returning empty: %s", exc)
                return {"intent": None, "location": None, "details": {}}
