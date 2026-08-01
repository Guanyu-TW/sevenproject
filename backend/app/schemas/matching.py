from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.vendor import VendorRecommendation


class MatchVendorsRequest(BaseModel):
    """Body of POST /api/matching/vendors.

    Only the task id is accepted on purpose: the demand already lives in
    ``life_tasks.parsed_data`` after the PATCH, so reading it server-side keeps
    a single source of truth and stops a client from matching against values
    that were never persisted.
    """

    task_id: int
    limit: int = Field(default=3, ge=1, le=10)


class MatchVendorsResponse(BaseModel):
    task_id: int
    status: str
    category_code: str | None
    candidate_count: int = Field(
        description="符合硬性條件的廠商總數，可能多於回傳的推薦數。"
    )
    recommendations: list[VendorRecommendation]
    provider: str
    model: str | None = None
    fallback_used: bool = Field(
        default=False,
        description="True 表示 AI 推薦失敗，改用規則式排序與樣板理由。",
    )
    fallback_reason: str | None = None


class BedrockVendorPick(BaseModel):
    """One entry of the LLM's ranking tool output."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    vendor_id: int = Field(alias="vendorId")
    estimated_price: float | None = Field(default=None, alias="estimatedPrice")
    match_score: float = Field(default=0.5, alias="matchScore")
    recommendation_reason: str = Field(alias="recommendationReason")

    @field_validator("estimated_price", mode="before")
    @classmethod
    def _digits_only(cls, value: Any) -> Any:
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
            return digits or None
        return value

    @field_validator("match_score", mode="before")
    @classmethod
    def _clamp(cls, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.5
        if number > 1.0:
            number = number / 100.0
        return min(max(number, 0.0), 1.0)


class BedrockVendorRanking(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    recommendations: list[BedrockVendorPick] = Field(default_factory=list)


class VendorContext(BaseModel):
    """Minimal vendor facts handed to the LLM for ranking.

    Deliberately not the ORM model: the provider layer must stay free of
    SQLAlchemy, and this keeps the prompt payload small and auditable.
    """

    id: int
    name: str
    rating: float
    description: str | None = None
    service_city: str | None = None
    service_districts: list[str] = Field(default_factory=list)
    price_min: int | None = None
    price_max: int | None = None
    categories: list[str] = Field(default_factory=list)


class DemandContext(BaseModel):
    """The resident's requirement, flattened for the ranking prompt."""

    task_id: int
    title: str | None = None
    summary: str | None = None
    category_name: str | None = None
    service_type: str | None = None
    budget_amount: float | None = None
    currency: str | None = "TWD"
    city: str | None = None
    district: str | None = None
    address: str | None = None
    urgency: str | None = None
    preferred_time: str | None = None
    preferred_date: str | None = None
    description: str | None = None
    raw_input: str | None = None
