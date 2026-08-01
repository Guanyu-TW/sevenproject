from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models import ConsultationCase, Vendor
from app.schemas.case import CaseRead, CreateCaseRequest
from app.services.case_service import (
    CaseCreationError,
    DuplicateCaseError,
    STATUS_LABELS,
    create_case,
    get_case,
    to_case_read,
)
from app.services.life_task_service import get_task

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post(
    "",
    response_model=CaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a ConsultationCase for the selected vendor",
)
def create_case_endpoint(payload: CreateCaseRequest, db: DbSession) -> CaseRead:
    """Dispatch a ready task to one vendor.

    Refuses with 409 if the task already has an active case, so a double click
    cannot produce two case numbers.
    """
    try:
        task = get_task(db, payload.task_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    vendor = db.scalars(
        select(Vendor)
        .options(selectinload(Vendor.categories))
        .where(Vendor.id == payload.selected_vendor_id)
    ).first()
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {payload.selected_vendor_id} does not exist",
        )

    try:
        case = create_case(
            db,
            task=task,
            vendor=vendor,
            form_data=payload.form_data,
            estimated_price=payload.estimated_price,
            recommendation_reason=payload.recommendation_reason,
        )
    except DuplicateCaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "case_id": exc.existing.id,
                "case_number": exc.existing.case_number,
                "status": str(exc.existing.status),
                "status_label": STATUS_LABELS.get(
                    exc.existing.status, str(exc.existing.status)
                ),
            },
        ) from exc
    except CaseCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return to_case_read(case)


@router.get(
    "/{case_id}",
    response_model=CaseRead,
    summary="Case detail, current status, next action and timeline",
)
def read_case(db: DbSession, case_id: int = Path(ge=1)) -> CaseRead:
    try:
        case = get_case(db, case_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return to_case_read(case)


@router.get(
    "/by-task/{task_id}",
    response_model=CaseRead | None,
    summary="The task's active case, or null",
)
def read_case_by_task(db: DbSession, task_id: int = Path(ge=1)) -> CaseRead | None:
    """Lets the UI restore the tracking board after a refresh."""
    case = db.scalars(
        select(ConsultationCase)
        .where(ConsultationCase.task_id == task_id)
        .order_by(ConsultationCase.id.desc())
        .limit(1)
    ).first()
    if case is None:
        return None
    return to_case_read(get_case(db, case.id))
