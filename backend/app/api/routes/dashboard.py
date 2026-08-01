from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import build_dashboard
from app.services.life_task_service import resolve_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/tasks",
    response_model=DashboardResponse,
    summary="Every task for one resident, newest first, with its latest case",
)
def dashboard_tasks(
    db: DbSession,
    user_id: int | None = Query(
        default=None, ge=1, description="省略則使用共用的 demo 住戶。"
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> DashboardResponse:
    """Overview for the resident's own tasks.

    Stats are computed over every task in SQL, so they stay correct even when
    the task list itself is truncated by ``limit``.
    """
    try:
        user = resolve_user(db, user_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return build_dashboard(db, user=user, limit=limit)
