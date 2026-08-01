"""Schemas for the resident's overview dashboard."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CaseStatus, TaskStatus


class DashboardUser(BaseModel):
    id: int
    name: str


class DashboardStats(BaseModel):
    """Headline counters. Task-level and case-level counts are kept apart
    because a task without a case is a different situation from a case that is
    waiting on someone."""

    total_tasks: int = 0
    #: Tasks the resident still has to act on (draft / needs_info).
    needs_input: int = 0
    #: Ready to match but no case created yet.
    ready_for_matching: int = 0
    #: Cases sitting at waiting_vendor_response.
    waiting_vendor: int = 0
    #: Vendor said yes and the resident still has to confirm.
    awaiting_confirmation: int = 0
    #: Cases the vendor accepted and that are on their way to completion.
    in_progress: int = 0
    completed: int = 0
    rejected: int = 0
    cancelled: int = 0


class DashboardCaseRef(BaseModel):
    """The task's most recent case, flattened for list rendering."""

    case_id: int
    case_number: str
    status: CaseStatus
    status_label: str
    vendor_id: int
    vendor_name: str
    vendor_rating: float | None = None
    estimated_price: int | None = None
    proposed_time: datetime | None = None
    vendor_note: str | None = None
    responded_at: datetime | None = None


class DashboardTaskItem(BaseModel):
    task_id: int
    title: str | None = None
    summary: str | None = None
    raw_input: str | None = None
    status: TaskStatus
    status_label: str
    #: What the badge should read. Prefers the case status once a vendor is
    #: involved, so a red badge never reads "待媒合".
    display_label: str
    #: Coarse bucket used by the UI to pick a badge colour.
    badge_tone: str = Field(
        description="draft | pending | active | done | failed"
    )
    category_code: str | None = None
    category_name: str | None = None
    tags: list[str] = Field(default_factory=list, description="AI 擷取的關鍵詞與標籤。")
    budget_amount: float | None = None
    currency: str | None = None
    city: str | None = None
    district: str | None = None
    urgency: str | None = None
    next_action: str | None = None
    missing_count: int = 0
    case_count: int = 0
    latest_case: DashboardCaseRef | None = None
    created_at: datetime
    updated_at: datetime


class DashboardResponse(BaseModel):
    user: DashboardUser
    stats: DashboardStats
    total: int = Field(description="該使用者的任務總數（不受 limit 影響）。")
    returned: int = Field(description="本次回傳的任務數。")
    truncated: bool = False
    tasks: list[DashboardTaskItem] = Field(default_factory=list)
