"""Service-catalogue discovery.

Added for external agents: before an agent can decide whether this platform can
help with a request, it has to be able to ask what the platform actually covers.
The web UI never needed this because the AI classifies server-side.
"""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models import ServiceCategory
from app.schemas.service_category import ServiceCategoryRead

router = APIRouter(prefix="/service-categories", tags=["catalogue"])


@router.get(
    "",
    response_model=list[ServiceCategoryRead],
    summary="Every service domain the platform can dispatch",
)
def list_service_categories(db: DbSession) -> list[ServiceCategory]:
    """Ordered by id so the list is stable across calls."""
    return list(
        db.scalars(select(ServiceCategory).order_by(ServiceCategory.id)).all()
    )
