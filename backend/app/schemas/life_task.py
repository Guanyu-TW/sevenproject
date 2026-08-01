from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskStatus
from app.schemas.ai import InputType, MissingField
from app.schemas.service_category import ServiceCategoryRead


class LifeTaskRead(BaseModel):
    """A persisted LifeTask as returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category_id: int | None
    category: ServiceCategoryRead | None
    status: TaskStatus
    raw_input: str | None
    parsed_data: dict[str, Any]
    missing_fields: list[MissingField]
    next_action: str | None = None
    created_at: datetime
    updated_at: datetime


class EditableField(BaseModel):
    """One condition of a request, with whatever value is on file right now.

    Same vocabulary as ``MissingField`` so the frontend can render both with one
    component; ``value`` and ``missing`` are the only additions.
    """

    field: str
    label: str
    input_type: InputType = "text"
    placeholder: str | None = None
    unit: str | None = None
    reason: str | None = None
    #: Current value rendered for an HTML input, None when nothing is stored.
    value: str | None = None
    #: True when the AI is still asking for this one.
    missing: bool = False


class TaskFieldsResponse(BaseModel):
    """Body of GET /api/tasks/{id}/fields."""

    task_id: int
    status: TaskStatus
    #: False once a vendor is working the request, so the UI can hide the form
    #: instead of offering an edit the API would reject.
    editable: bool
    #: Why editing is closed, when it is.
    locked_reason: str | None = None
    fields: list[EditableField]


class LifeTaskUpdate(BaseModel):
    """Body of PATCH /api/tasks/{id}.

    ``filled_fields`` uses the canonical keys from the missing-fields catalogue
    (``address``, ``contact_phone``, ...). The server decides where each value
    belongs inside ``parsed_data``, so the client never has to know the shape.
    """

    filled_fields: dict[str, Any] | None = Field(
        default=None,
        examples=[{"address": "嘉義市西區文化路 100 號", "contact_phone": "0912345678"}],
    )
    status: TaskStatus | None = Field(
        default=None,
        description="Optional status transition. Rejected with 409 if not allowed.",
    )
