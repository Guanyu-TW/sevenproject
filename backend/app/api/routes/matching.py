from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.schemas.matching import MatchVendorsRequest, MatchVendorsResponse
from app.services.ai_service import get_ai_provider
from app.services.life_task_service import get_task
from app.services.matching_service import MatchingStateError, match_vendors

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post(
    "/vendors",
    response_model=MatchVendorsResponse,
    summary="Hard-filter vendors, then have the AI rank and justify them",
)
def match_vendors_endpoint(
    payload: MatchVendorsRequest, db: DbSession
) -> MatchVendorsResponse:
    """Return up to ``limit`` recommended vendors for a ready task.

    The task must already be ``ready_for_matching``; otherwise this is a 409.
    Matching is read-only and idempotent, so it can be re-run safely.
    """
    try:
        task = get_task(db, payload.task_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    try:
        provider = get_ai_provider()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    try:
        return match_vendors(db, task=task, provider=provider, limit=payload.limit)
    except MatchingStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
