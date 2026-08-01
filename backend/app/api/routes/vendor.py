from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.deps import DbSession
from app.models.enums import CaseStatus
from app.schemas.vendor_portal import (
    VendorCaseListResponse,
    VendorRespondRequest,
    VendorRespondResponse,
    VendorSummary,
)
from app.services.vendor_service import (
    VendorResponseError,
    list_vendor_cases,
    list_vendors,
    respond_to_case,
)

router = APIRouter(prefix="/vendor", tags=["vendor"])


@router.get(
    "/list",
    response_model=list[VendorSummary],
    summary="Vendors available to act as, with open-case counts",
)
def vendors(db: DbSession) -> list[VendorSummary]:
    """There is no vendor login yet, so the portal picks an identity from here."""
    return list_vendors(db)


@router.get(
    "/cases",
    response_model=VendorCaseListResponse,
    summary="Cases waiting on a vendor, or already accepted by one",
)
def vendor_cases(
    db: DbSession,
    vendor_id: int | None = Query(
        default=None, ge=1, description="省略則列出全平台的案件。"
    ),
    status_filter: list[CaseStatus] | None = Query(
        default=None,
        alias="status",
        description="預設為 waiting_vendor_response 與 vendor_accepted。",
    ),
    limit: int = Query(default=20, ge=1, le=100),
) -> VendorCaseListResponse:
    try:
        return list_vendor_cases(
            db, vendor_id=vendor_id, statuses=status_filter, limit=limit
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post(
    "/cases/{case_id}/respond",
    response_model=VendorRespondResponse,
    summary="Accept or reject a case",
)
def respond(
    payload: VendorRespondRequest,
    db: DbSession,
    case_id: int = Path(ge=1),
    vendor_id: int | None = Query(
        default=None, ge=1, description="帶入則驗證案件確實屬於這家廠商。"
    ),
) -> VendorRespondResponse:
    """Move the case forward and keep the resident's task in step.

    Responding twice is a 409 rather than a silent overwrite.
    """
    try:
        return respond_to_case(
            db, case_id=case_id, payload=payload, vendor_id=vendor_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except VendorResponseError as exc:
        code = (
            status.HTTP_403_FORBIDDEN
            if exc.code == "wrong_vendor"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
