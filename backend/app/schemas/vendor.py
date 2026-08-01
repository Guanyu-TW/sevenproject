from pydantic import BaseModel, ConfigDict, Field

from app.schemas.service_category import ServiceCategoryRead


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rating: float
    description: str | None
    service_city: str | None
    service_districts: list[str] = Field(default_factory=list)
    price_min: int | None
    price_max: int | None
    categories: list[ServiceCategoryRead] = Field(default_factory=list)


class VendorRecommendation(BaseModel):
    """One matched vendor plus the AI's justification."""

    vendor_id: int
    name: str
    rating: float
    description: str | None = None
    service_city: str | None = None
    service_districts: list[str] = Field(default_factory=list)
    price_min: int | None = None
    price_max: int | None = None
    categories: list[str] = Field(default_factory=list)

    estimated_price: int | None = Field(
        default=None, description="AI 依需求在廠商價格區間內推估的金額。"
    )
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation_reason: str
