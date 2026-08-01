from fastapi import APIRouter, HTTPException, Path, status

from app.api.deps import DbSession
from app.models import LifeTask
from app.schemas.life_task import LifeTaskRead, LifeTaskUpdate
from app.services.life_task_service import (
    TaskTransitionError,
    get_task,
    update_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get(
    "/{task_id}",
    response_model=LifeTaskRead,
    summary="Read one LifeTask",
)
def read_task(db: DbSession, task_id: int = Path(ge=1)) -> LifeTask:
    try:
        return get_task(db, task_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.patch(
    "/{task_id}",
    response_model=LifeTaskRead,
    summary="Write back filled-in fields and/or move the task status",
)
def patch_task(
    payload: LifeTaskUpdate,
    db: DbSession,
    task_id: int = Path(ge=1),
) -> LifeTask:
    """Merge ``filled_fields`` into ``parsed_data`` and apply a status change.

    Stored fields are pruned from ``missing_fields``. An illegal status
    transition is a 409 rather than a silent no-op.
    """
    try:
        task = get_task(db, task_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    try:
        return update_task(
            db,
            task=task,
            filled_fields=payload.filled_fields,
            status=payload.status,
        )
    except TaskTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
