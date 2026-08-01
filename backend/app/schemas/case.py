from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CaseStatus
from app.schemas.vendor import VendorRead


class CreateCaseRequest(BaseModel):
    """Body of POST /api/cases.

    camelCase aliases are accepted so the frontend can send ``taskId`` /
    ``selectedVendorId`` / ``formData`` while the server stays snake_case.
    """

    model_config = ConfigDict(populate_by_name=True)

    task_id: int = Field(alias="taskId")
    selected_vendor_id: int = Field(alias="selectedVendorId")
    form_data: dict[str, Any] = Field(default_factory=dict, alias="formData")
    #: Snapshotted from the matching response so the case keeps the numbers and
    #: wording the resident actually saw, without re-calling the LLM.
    estimated_price: int | None = Field(default=None, alias="estimatedPrice")
    recommendation_reason: str | None = Field(
        default=None, alias="recommendationReason"
    )


class CaseTimelineStep(BaseModel):
    """One node of the tracking timeline, including not-yet-reached steps."""

    key: str
    label: str
    state: Literal["done", "current", "upcoming"]
    at: datetime | None = None
    note: str | None = None


class CaseHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    actor: str
    note: str | None
    created_at: datetime


class SharedWithVendor(BaseModel):
    """Exactly what the vendor can see right now.

    Returned so the privacy promise in the UI is verifiable rather than
    decorative: anything the vendor cannot see is listed in ``withheld``, and
    the locked fields below stay ``None`` until the resident confirms.
    """

    title: str | None = None
    summary: str | None = None
    category_name: str | None = None
    city: str | None = None
    district: str | None = None
    budget_amount: float | None = None
    urgency: str | None = None
    preferred_time: str | None = None

    #: Coarse location, always shared: enough to judge "is this my area?".
    area: str | None = Field(
        default=None, description="縣市 + 行政區，例如「台北市信義區」。"
    )

    # --- unlocked only once the case reaches contact_shared -------------- #
    contact_unlocked: bool = False
    address: str | None = Field(
        default=None, description="完整門牌，未解鎖時為 null。"
    )
    contact_name: str | None = None
    contact_phone: str | None = None

    withheld: list[str] = Field(default_factory=list)


class CaseRead(BaseModel):
    """Payload of POST /api/cases and GET /api/cases/{id}."""

    id: int
    case_number: str
    status: CaseStatus
    status_label: str
    task_id: int
    task_status: str
    next_action: str | None = None
    blocked_reason: str | None = None
    estimated_price: int | None = None
    recommendation_reason: str | None = None
    vendor_note: str | None = None
    proposed_time: datetime | None = None
    responded_at: datetime | None = None
    contact_shared: bool = False
    privacy_notice: str
    vendor: VendorRead
    shared_with_vendor: SharedWithVendor
    # form_data is deliberately NOT exposed: it holds the resident's full
    # address and phone, nothing in the UI reads it, and this endpoint has no
    # authentication yet. The snapshot still lives in the database.
    timeline: list[CaseTimelineStep] = Field(default_factory=list)
    history: list[CaseHistoryEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CaseConflict(BaseModel):
    """Detail payload for the duplicate-case 409."""

    message: str
    case_id: int
    case_number: str
    status: CaseStatus
