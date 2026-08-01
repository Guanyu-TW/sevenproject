"""Request / provider-output schemas for the demand analysis flow."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class MissingField(BaseModel):
    """One piece of information the AI could not extract yet.

    Stored verbatim inside ``LifeTask.missing_fields`` so the follow-up
    question flow in a later step can drive itself off this list.
    """

    field: str = Field(description="Machine name, e.g. 'address'.")
    label: str = Field(description="Human label shown in the UI, e.g. '地址'.")
    reason: str | None = Field(default=None, description="Why it is needed.")
    required: bool = Field(default=True)


class DemandAnalysis(BaseModel):
    """Normalised output every AI provider must produce."""

    title: str
    summary: str | None = None
    category_code: str | None = Field(
        default=None,
        description="Must match ServiceCategory.code, e.g. 'plumbing'.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    parsed_data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[MissingField] = Field(default_factory=list)


class AnalyzeDemandRequest(BaseModel):
    """Body of POST /api/ai/analyze-demand."""

    prompt: str = Field(min_length=1, max_length=2000, examples=["嘉義市水龍頭漏水，預算兩千"])
    user_id: int | None = Field(
        default=None,
        description="Omit to attach the task to the shared demo resident.",
    )

    @field_validator("prompt")
    @classmethod
    def _strip_prompt(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("prompt must not be blank")
        return stripped
