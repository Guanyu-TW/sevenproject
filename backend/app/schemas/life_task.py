from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

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
