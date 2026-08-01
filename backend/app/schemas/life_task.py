from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskStatus
from app.schemas.ai import MissingField
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
    created_at: datetime
    updated_at: datetime


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
