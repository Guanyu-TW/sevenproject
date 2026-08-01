from fastapi import APIRouter, Response, status

from app.api.deps import DbSession
from app.schemas.health import HealthResponse
from app.services.health_service import check_database

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    summary="Liveness probe + database connectivity check",
)
def health(response: Response, db: DbSession) -> HealthResponse:
    connected, reason = check_database(db)

    if not connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", db="disconnected", detail=reason)

    return HealthResponse(status="ok", db="connected")
