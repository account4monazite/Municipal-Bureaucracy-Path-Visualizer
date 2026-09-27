from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):

    role: str = Field(..., examples=["user", "assistant"])
    content: str


class ChatRequest(BaseModel):

    session_id: str = Field(..., min_length=1, examples=["abc123"])
    message: str = Field(..., min_length=1, examples=["I want to register a small business"])


class ChatResponse(BaseModel):

    session_id: str
    reply: str
    task_state: "TaskState"
    sources: List["SourceReference"] = []




class TaskLocation(BaseModel):

    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None


class TaskState(BaseModel):
    

    session_id: str
    intent: Optional[str] = None  # e.g. "business_registration"
    location: TaskLocation = Field(default_factory=TaskLocation)
    details: Dict[str, Any] = Field(default_factory=dict)
    missing_information: List[str] = Field(default_factory=list)
    conversation_history: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    roadmap_id: Optional[str] = None


class SourceReference(BaseModel):

    source_url: Optional[str] = None
    source_title: Optional[str] = None
    last_verified: Optional[str] = None
    confidence: Optional[str] = None  





class CoordinatesInput(BaseModel):

    latitude: float = Field(..., ge=-90, le=90, examples=[19.076])
    longitude: float = Field(..., ge=-180, le=180, examples=[72.8777])


class ManualLocationInput(BaseModel):

    city: Optional[str] = Field(None, examples=["Mumbai"])
    district: Optional[str] = Field(None, examples=["Mumbai"])
    state: Optional[str] = Field(None, examples=["Maharashtra"])
    country: Optional[str] = Field(None, examples=["India"])
    pincode: Optional[str] = Field(None, examples=["400001"])


class LocationResolveRequest(BaseModel):
    

    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None

    @model_validator(mode="after")
    def validate_at_least_one_source(self) -> "LocationResolveRequest":
        has_coords = self.latitude is not None and self.longitude is not None
        has_manual = any(
            [self.city, self.district, self.state, self.country, self.pincode]
        )
        if not has_coords and not has_manual:
            raise ValueError(
                "Provide either (latitude + longitude) or at least one of "
                "(city, district, state, country, pincode)."
            )
        return self


class ResolvedLocation(BaseModel):

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None

    # Indicates whether coords were successfully reverse-geocoded
    geocoded: bool = False


class NearbyOfficesRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    department: Optional[str] = None
    radius_km: float = Field(default=10.0, gt=0, le=100)


class GovernmentOffice(BaseModel):
    id: str
    name: str
    department: str
    address: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    source_url: Optional[str] = None


class NearbyOfficesResponse(BaseModel):
    offices: list[GovernmentOffice] = []






class StepType(str, Enum):
    document = "document"
    application = "application"
    payment = "payment"
    inspection = "inspection"
    registration = "registration"
    verification = "verification"
    appointment = "appointment"
    other = "other"


class RelationshipType(str, Enum):
    required_before = "required_before"
    recommended_before = "recommended_before"
    parallel = "parallel"


class RoadmapNode(BaseModel):

    id: str = Field(..., examples=["step_1"])
    title: str
    type: StepType = StepType.other
    description: str = ""
    mandatory: bool = True
    estimated_time: Optional[str] = None  # e.g. "2-3 days"
    estimated_cost: Optional[str] = None  # e.g. "₹500"
    required_documents: List[str] = []
    office_name: Optional[str] = None
    office_id: Optional[str] = None
    form_number: Optional[str] = None
    source: SourceReference = Field(default_factory=SourceReference)


class RoadmapEdge(BaseModel):

    source: str = Field(..., description="ID of the prerequisite step")
    target: str = Field(..., description="ID of the dependent step")
    relationship: RelationshipType = RelationshipType.required_before


class RoadmapGenerateRequest(BaseModel):

    session_id: str = Field(..., min_length=1)


class Roadmap(BaseModel):

    roadmap_id: str
    title: str
    task: str
    location: TaskLocation
    nodes: List[RoadmapNode] = []
    edges: List[RoadmapEdge] = []
    sources: List[SourceReference] = []
    disclaimer: str = (
        "This roadmap is generated from official government sources. "
        "Requirements may change. Always verify with the relevant authority."
    )


class NLPServiceRequest(BaseModel):

    task: str
    location: Dict[str, Any]
    details: Dict[str, Any] = {}


class NLPServiceResponse(BaseModel):

    task: str
    steps: List[Dict[str, Any]] = []
    requirements: List[Dict[str, Any]] = []
    dependencies: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []






class ProgressUpdateRequest(BaseModel):
    

    session_id: str
    roadmap_id: str
    step_id: str
    completed: bool


class StepProgress(BaseModel):
    step_id: str
    completed: bool
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class RoadmapProgress(BaseModel):
    

    roadmap_id: str
    session_id: str
    steps: List[StepProgress] = []
    total_steps: int = 0
    completed_steps: int = 0
    percentage: float = 0.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
