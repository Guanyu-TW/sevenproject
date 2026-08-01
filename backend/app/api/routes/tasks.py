from fastapi import APIRouter, HTTPException, Path, status

from app.api.deps import DbSession
from app.models import LifeTask, TaskStatus
from app.schemas.life_task import (
    EditableField,
    LifeTaskRead,
    LifeTaskUpdate,
    TaskFieldsResponse,
)
from app.services.case_service import STATUS_LABELS, find_active_case
from app.services.life_task_service import (
    TaskTransitionError,
    get_task,
    update_task,
)
from app.services.missing_fields import editable_fields

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


@router.get(
    "/{task_id}/fields",
    response_model=TaskFieldsResponse,
    summary="The conditions of one request, for editing",
)
def read_task_fields(db: DbSession, task_id: int = Path(ge=1)) -> TaskFieldsResponse:
    """Describe every condition on this task so the client can render a form.

    Values come back as strings ready for an ``<input>``; write them back with
    the same keys through ``PATCH /api/tasks/{id}``.
    """
    try:
        task = get_task(db, task_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    # Editing is closed once someone else is acting on the request. Silently
    # accepting a new address after a vendor has been dispatched to the old one
    # would be worse than refusing.
    locked_reason: str | None = None
    if task.status is TaskStatus.COMPLETED:
        locked_reason = "任務已完成，不能再修改需求內容。"
    elif task.status is TaskStatus.CANCELLED:
        locked_reason = "任務已取消，不能再修改需求內容。"
    else:
        active = find_active_case(db, task.id)
        if active is not None:
            locked_reason = (
                f"案件 {active.case_number} 已送給廠商"
                f"（{STATUS_LABELS.get(active.status, active.status)}），"
                "此時修改需求內容會和廠商手上的資料不一致。"
                "如需變動請直接與廠商聯繫。"
            )

    return TaskFieldsResponse(
        task_id=task.id,
        status=task.status,
        editable=locked_reason is None,
        locked_reason=locked_reason,
        fields=[
            EditableField(
                field=key,
                label=spec.label,
                input_type=spec.input_type,
                placeholder=spec.placeholder,
                unit=spec.unit,
                reason=spec.reason,
                value=current,
                missing=missing,
            )
            for key, spec, current, missing in editable_fields(
                task.parsed_data, task.missing_fields
            )
        ],
    )


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
