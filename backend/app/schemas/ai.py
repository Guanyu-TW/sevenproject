"""Schemas for the demand analysis flow.

Two families live here on purpose:

* ``MissingField`` / ``DemandAnalysis`` -- our internal, snake_case contract.
* ``Bedrock*`` -- the exact JSON we force the LLM to emit. Keeping it separate
  means a provider swap never leaks its wire format into the database or the
  frontend.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

InputType = Literal[
    "text",
    "textarea",
    "number",
    "tel",
    "date",
    "datetime-local",
    "file",
]


class MissingField(BaseModel):
    """One piece of information the AI could not extract yet.

    Stored verbatim inside ``LifeTask.missing_fields`` and used by the frontend
    to render an input control, so it carries presentation hints too.
    """

    field: str = Field(description="Canonical machine name, e.g. 'address'.")
    label: str = Field(description="Human label shown in the UI, e.g. '詳細地址'.")
    reason: str | None = Field(default=None, description="Why it is needed.")
    required: bool = Field(default=True)
    input_type: InputType = Field(
        default="text", description="Which control the frontend should render."
    )
    placeholder: str | None = None
    unit: str | None = Field(default=None, description="Suffix such as 'TWD' or '坪'.")


class CategoryHint(BaseModel):
    """Allowed service category, injected into the prompt from the database."""

    code: str
    name: str


class DemandAnalysis(BaseModel):
    """Normalised output every AI provider must produce."""

    title: str
    summary: str | None = None
    intent: str | None = None
    category_code: str | None = Field(
        default=None,
        description="Must match ServiceCategory.code, e.g. 'plumbing'.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model: str | None = Field(default=None, description="Model that produced this.")
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


# --------------------------------------------------------------------------- #
# LLM wire format
# --------------------------------------------------------------------------- #


class BedrockLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    city: str | None = None
    district: str | None = None
    address: str | None = None


class BedrockBudget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    amount: float | None = None
    currency: str | None = "TWD"
    note: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, value: Any) -> Any:
        """Models sometimes answer '2000 元' or '約2000'. Keep the digits."""
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
            return digits or None
        return value


class BedrockMissingField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str
    label: str | None = None
    reason: str | None = None


class BedrockDemandPayload(BaseModel):
    """The tool input schema we force Claude to fill in on Bedrock.

    ``populate_by_name`` lets us accept both ``serviceType`` and
    ``service_type``, so a model that drifts on casing still validates.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    intent: str = Field(default="service_request")
    service_type: str | None = Field(default=None, alias="serviceType")
    category_code: str | None = Field(default=None, alias="categoryCode")
    title: str
    summary: str | None = None
    location: BedrockLocation = Field(default_factory=BedrockLocation)
    budget: BedrockBudget = Field(default_factory=BedrockBudget)
    urgency: str | None = None
    preferred_time: str | None = Field(default=None, alias="preferredTime")
    keywords: list[str] = Field(default_factory=list)
    missing_fields: list[BedrockMissingField] = Field(
        default_factory=list, alias="missingFields"
    )
    confidence: float = 0.5

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        """Accept 0-1 or 0-100 and clamp, rather than failing the request."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.5
        if number > 1.0:
            number = number / 100.0
        return min(max(number, 0.0), 1.0)
