"""Schemas for the vendor-facing portal."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.models.enums import CaseStatus
from app.schemas.case import SharedWithVendor


class VendorSummary(BaseModel):
    """Vendor picker entry. No auth yet, so the portal chooses an identity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rating: float
    service_city: str | None = None
    open_case_count: int = 0


class VendorCaseListItem(BaseModel):
    """One row of the vendor's inbox.

    Only ``shared_with_vendor`` is exposed, never the resident's raw
    ``parsed_data``: this endpoint is the actual vendor-facing surface, so the
    redaction that :mod:`app.services.privacy` performs is what keeps the
    resident's address and phone out of it.
    """

    case_id: int
    case_number: str
    #: Needed by the platform-wide view, where rows span several vendors.
    vendor_id: int
    vendor_name: str
    status: CaseStatus
    status_label: str
    estimated_price: int | None = None
    recommendation_reason: str | None = None
    vendor_note: str | None = None
    proposed_time: datetime | None = None
    responded_at: datetime | None = None
    contact_shared: bool = False
    demand: SharedWithVendor
    created_at: datetime


class VendorCaseListResponse(BaseModel):
    """Inbox payload.

    ``cases`` is built from two independent queries -- one per group -- so the
    pending list can never be starved by a run of recently accepted cases. The
    ``*_total`` counts are unbounded, the ``*_shown`` counts describe what is
    actually in ``cases``, and the UI is expected to show both when they differ.
    """

    vendor: VendorSummary | None = None
    total: int = Field(description="範圍內的案件總數（待接單 + 已接單）。")
    pending: int = Field(description="狀態為 waiting_vendor_response 的總件數。")
    responded_total: int = Field(default=0, description="已回覆案件的總件數。")
    pending_shown: int = Field(default=0, description="本次回傳的待接單件數。")
    responded_shown: int = Field(default=0, description="本次回傳的已回覆件數。")
    truncated: bool = Field(
        default=False, description="True 表示有案件因為 limit 沒有回傳。"
    )
    cases: list[VendorCaseListItem] = Field(default_factory=list)


class VendorRespondRequest(BaseModel):
    """Body of POST /api/vendor/cases/{id}/respond."""

    model_config = ConfigDict(populate_by_name=True)

    action: Literal["accept", "reject"]
    vendor_note: str | None = Field(
        default=None, max_length=1000, alias="vendorNote",
        examples=["現場確認後報價，若需更換零件會先告知。"],
    )
    proposed_time: datetime | None = Field(
        default=None, alias="proposedTime", examples=["2026-08-08T19:30"]
    )

    @field_validator("vendor_note")
    @classmethod
    def _strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("proposed_time", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        """Treat an empty datetime-local field as "not provided".

        Otherwise a blank submission fails Pydantic parsing and the caller gets
        a 422 type error instead of the clear 409 explaining that the arrival
        time is required.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("proposed_time")
    @classmethod
    def _localize(cls, value: datetime | None) -> datetime | None:
        """Attach Asia/Taipei to a naive value from an <input datetime-local>."""
        if value is None:
            return None
        if value.tzinfo is None:
            # A datetime-local input carries no zone; treat it as local time
            # rather than UTC, or an evening slot becomes a morning one.
            return value.replace(tzinfo=settings.tzinfo)
        return value


class VendorRespondResponse(BaseModel):
    case_id: int
    case_number: str
    status: CaseStatus
    status_label: str
    task_id: int
    task_status: str
    task_next_action: str | None = None
    vendor_note: str | None = None
    proposed_time: datetime | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
