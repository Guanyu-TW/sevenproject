"""Vendor-facing reads and the accept / reject transition.

A vendor response moves three things together, so they share one transaction:
the case status, an audit row in ``case_status_history``, and the resident's
``LifeTask`` (status plus ``next_action``). Doing them separately would let the
resident's dashboard disagree with the case.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ALLOWED_CASE_TRANSITIONS,
    VENDOR_ACTIONABLE_STATUSES,
    CaseStatus,
    CaseStatusHistory,
    ConsultationCase,
    LifeTask,
    TaskStatus,
    Vendor,
)
from app.schemas.vendor_portal import (
    VendorCaseListItem,
    VendorCaseListResponse,
    VendorRespondRequest,
    VendorRespondResponse,
    VendorSummary,
)
from app.services.case_service import (
    STATUS_GUIDANCE,
    STATUS_LABELS,
    _build_shared_view,
    get_case,
)

logger = logging.getLogger(__name__)


class VendorResponseError(RuntimeError):
    """The vendor cannot respond to this case in its current state."""

    def __init__(self, message: str, *, code: str = "invalid_state"):
        super().__init__(message)
        self.code = code


def list_vendors(db: Session) -> list[VendorSummary]:
    """Vendors plus their open-case counts, for the portal's identity picker."""
    open_counts = dict(
        db.execute(
            select(ConsultationCase.vendor_id, func.count(ConsultationCase.id))
            .where(ConsultationCase.status.in_(tuple(VENDOR_ACTIONABLE_STATUSES)))
            .group_by(ConsultationCase.vendor_id)
        ).all()
    )
    vendors = db.scalars(
        select(Vendor).where(Vendor.is_active.is_(True)).order_by(Vendor.id)
    ).all()
    return [
        VendorSummary(
            id=v.id,
            name=v.name,
            rating=float(v.rating),
            service_city=v.service_city,
            open_case_count=open_counts.get(v.id, 0),
        )
        for v in vendors
    ]


def list_vendor_cases(
    db: Session,
    *,
    vendor_id: int | None = None,
    statuses: list[CaseStatus] | None = None,
    limit: int = 20,
) -> VendorCaseListResponse:
    """Inbox for one vendor, or the whole platform when ``vendor_id`` is None.

    Raises:
        LookupError: if ``vendor_id`` does not exist.
    """
    summary: VendorSummary | None = None
    if vendor_id is not None:
        vendor = db.get(Vendor, vendor_id)
        if vendor is None:
            raise LookupError(f"Vendor {vendor_id} does not exist")
        summary = VendorSummary(
            id=vendor.id,
            name=vendor.name,
            rating=float(vendor.rating),
            service_city=vendor.service_city,
        )

    wanted = statuses or [
        CaseStatus.WAITING_VENDOR_RESPONSE,
        CaseStatus.VENDOR_ACCEPTED,
    ]
    pending_wanted = [s for s in wanted if s == CaseStatus.WAITING_VENDOR_RESPONSE]
    responded_wanted = [s for s in wanted if s != CaseStatus.WAITING_VENDOR_RESPONSE]

    def scoped(stmt):
        return stmt if vendor_id is None else stmt.where(
            ConsultationCase.vendor_id == vendor_id
        )

    def fetch(group: list[CaseStatus]) -> list[ConsultationCase]:
        """Newest ``limit`` cases in one status group."""
        if not group:
            return []
        return list(
            db.scalars(
                scoped(
                    select(ConsultationCase)
                    .options(
                        selectinload(ConsultationCase.task).selectinload(
                            LifeTask.category
                        ),
                        selectinload(ConsultationCase.vendor),
                    )
                    .where(ConsultationCase.status.in_(tuple(group)))
                )
                .order_by(ConsultationCase.id.desc())
                .limit(limit)
            ).all()
        )

    def count(group: list[CaseStatus]) -> int:
        if not group:
            return 0
        return (
            db.scalar(
                scoped(
                    select(func.count())
                    .select_from(ConsultationCase)
                    .where(ConsultationCase.status.in_(tuple(group)))
                )
            )
            or 0
        )

    # Two separate queries on purpose. A single query over both groups with one
    # LIMIT would starve the pending list whenever the newest cases happen to
    # be already-accepted ones -- the UI then claimed "83 待接單" while showing
    # none of them.
    pending_cases = fetch(pending_wanted)
    responded_cases = fetch(responded_wanted)
    cases = pending_cases + responded_cases

    pending_total = count([CaseStatus.WAITING_VENDOR_RESPONSE])
    responded_total = count(responded_wanted)

    if summary is not None:
        summary.open_case_count = pending_total

    return VendorCaseListResponse(
        vendor=summary,
        total=pending_total + responded_total,
        pending=pending_total,
        responded_total=responded_total,
        pending_shown=len(pending_cases),
        responded_shown=len(responded_cases),
        truncated=(
            len(pending_cases) < pending_total
            or len(responded_cases) < responded_total
        ),
        cases=[
            VendorCaseListItem(
                case_id=c.id,
                case_number=c.case_number,
                vendor_id=c.vendor_id,
                vendor_name=c.vendor.name,
                status=c.status,
                status_label=STATUS_LABELS.get(c.status, str(c.status)),
                estimated_price=c.estimated_price,
                recommendation_reason=c.recommendation_reason,
                vendor_note=c.vendor_note,
                proposed_time=c.proposed_time,
                responded_at=c.responded_at,
                contact_shared=c.contact_shared,
                # Redacted view: this is the real vendor-facing surface.
                demand=_build_shared_view(c),
                created_at=c.created_at,
            )
            for c in cases
        ],
    )


def respond_to_case(
    db: Session,
    *,
    case_id: int,
    payload: VendorRespondRequest,
    vendor_id: int | None = None,
) -> VendorRespondResponse:
    """Apply a vendor's accept / reject decision.

    Raises:
        LookupError: no such case.
        VendorResponseError: the case is not awaiting a response, or the case
            belongs to a different vendor.
    """
    # Lock the row BEFORE reading its status. Without this the check-then-write
    # below is a race: two concurrent accepts (two vendor tabs, a double click
    # that outruns the disabled button, or a direct API call) would both pass
    # the transition guard, and the second would overwrite the first's
    # proposed_time and append a duplicate history row.
    locked = db.execute(
        select(ConsultationCase.id)
        .where(ConsultationCase.id == case_id)
        .with_for_update()
    ).scalar_one_or_none()
    if locked is None:
        raise LookupError(f"Case {case_id} does not exist")

    case = get_case(db, case_id)

    if vendor_id is not None and case.vendor_id != vendor_id:
        raise VendorResponseError(
            f"案件 {case.case_number} 不屬於這家廠商，無法回覆。",
            code="wrong_vendor",
        )

    target = (
        CaseStatus.VENDOR_ACCEPTED
        if payload.action == "accept"
        else CaseStatus.VENDOR_REJECTED
    )

    allowed = ALLOWED_CASE_TRANSITIONS.get(case.status, frozenset())
    if target not in allowed:
        raise VendorResponseError(
            f"案件目前狀態是「{STATUS_LABELS.get(case.status, case.status)}」，"
            f"已經回覆過或無法再變更。",
            code="already_responded",
        )

    if payload.action == "accept" and payload.proposed_time is None:
        raise VendorResponseError(
            "接單時必須提供擬定到場時間。", code="missing_proposed_time"
        )

    previous = case.status
    next_action, blocked_reason = STATUS_GUIDANCE[target]

    case.status = target
    case.vendor_note = payload.vendor_note
    case.proposed_time = payload.proposed_time
    case.responded_at = datetime.now(timezone.utc)
    case.next_action = next_action
    case.blocked_reason = blocked_reason

    note_bits = [f"廠商「{case.vendor.name}」"]
    if payload.action == "accept":
        note_bits.append("確認接單")
        if payload.proposed_time:
            note_bits.append(
                "，預計到場 " + payload.proposed_time.strftime("%Y/%m/%d %H:%M")
            )
    else:
        note_bits.append("婉拒此案件")
    if payload.vendor_note:
        note_bits.append(f"。備註：{payload.vendor_note}")

    # Append through the relationship rather than db.add(): the session uses
    # expire_on_commit=False, so a bare add would persist the row but leave the
    # already-loaded case.history collection stale in the response.
    case.history.append(
        CaseStatusHistory(
            from_status=previous.value,
            to_status=target.value,
            actor="vendor",
            note="".join(note_bits),
        )
    )

    task = case.task
    task.next_action = next_action
    if payload.action == "reject":
        # Free the task so the resident can pick another vendor. The dedupe
        # check in case_service ignores rejected cases, so this is enough.
        task.status = TaskStatus.READY_FOR_MATCHING
        task.next_action = (
            "廠商婉拒了這次委託，請回到推薦清單改選其他廠商。"
        )
    db.add(task)
    db.add(case)
    db.commit()

    refreshed = get_case(db, case.id)
    logger.info(
        "Vendor %s %sed case %s (task %s -> %s)",
        case.vendor_id,
        payload.action,
        refreshed.case_number,
        task.id,
        task.status,
    )

    return VendorRespondResponse(
        case_id=refreshed.id,
        case_number=refreshed.case_number,
        status=refreshed.status,
        status_label=STATUS_LABELS.get(refreshed.status, str(refreshed.status)),
        task_id=refreshed.task_id,
        task_status=str(refreshed.task.status),
        task_next_action=refreshed.task.next_action,
        vendor_note=refreshed.vendor_note,
        proposed_time=refreshed.proposed_time,
        history=[
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "actor": h.actor,
                "note": h.note,
                "created_at": h.created_at.isoformat(),
            }
            for h in refreshed.history
        ],
    )


__all__ = [
    "VendorResponseError",
    "list_vendor_cases",
    "list_vendors",
    "respond_to_case",
]
