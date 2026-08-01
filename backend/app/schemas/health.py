from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Payload of GET /api/health."""

    status: str = Field(examples=["ok"])
    db: str = Field(examples=["connected"])
    detail: str | None = Field(default=None, description="Only present on failure.")
