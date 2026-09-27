

from __future__ import annotations

import json
import logging
import os
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
        self._use_mock = os.getenv("USE_MOCK_NLP", "true").lower() == "true"
        logger.info(
            "NLPService ready (base_url=%s, use_mock=%s)", self._base_url, self._use_mock
        )

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
            msg = user_message.lower()
            intent = None
            location = None
            details: Dict[str, Any] = {}

            if any(w in msg for w in ["register", "registration", "business", "company", "firm"]):
                intent = "business_registration"
            elif any(w in msg for w in ["passport"]):
                intent = "passport_application"
            elif any(w in msg for w in ["driving", "licence", "license", "dl"]):
                intent = "driving_license"
            elif any(w in msg for w in ["birth certificate"]):
                intent = "birth_certificate"
            elif any(w in msg for w in ["aadhaar", "aadhar", "uidai"]):
                intent = "aadhaar_update"

            # Very basic location extraction
            cities = {
                "mumbai": ("Mumbai", "Maharashtra"),
                "delhi": ("Delhi", "Delhi"),
                "bangalore": ("Bangalore", "Karnataka"),
                "bengaluru": ("Bangalore", "Karnataka"),
                "chennai": ("Chennai", "Tamil Nadu"),
                "hyderabad": ("Hyderabad", "Telangana"),
                "pune": ("Pune", "Maharashtra"),
                "kolkata": ("Kolkata", "West Bengal"),
            }
            for keyword, (city, state) in cities.items():
                if keyword in msg:
                    location = {"city": city, "state": state}
                    break

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
                return resp.json()
            except Exception as exc:
                logger.warning("NLPService extract_task failed, returning empty: %s", exc)
                return {"intent": None, "location": None, "details": {}}
