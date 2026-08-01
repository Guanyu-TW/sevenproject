"""Creating and reading ConsultationCases.

Case creation is the point where a task stops being editable guesswork and
becomes a commitment to one vendor, so three things happen atomically: the case
row, its first history entry, and the task's status/next_action.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ACTIVE_CASE_STATUSES,
    CaseStatus,
    CaseStatusHistory,
    ConsultationCase,
    LifeTask,
    TaskStatus,
    Vendor,
)
from app.schemas.case import (
    CaseHistoryEntry,
    CaseRead,
    CaseTimelineStep,
    SharedWithVendor,
)
from app.schemas.vendor import VendorRead
from app.services.privacy import redact, sensitive_terms

logger = logging.getLogger(__name__)

CASE_NUMBER_PREFIX = "CASE"
MAX_CASE_NUMBER_ATTEMPTS = 8

PRIVACY_NOTICE = (
    "已將需求摘要發送給廠商。媒合成功且你確認之後，才會提供完整地址與聯絡資訊。"
)

STATUS_LABELS: dict[CaseStatus, str] = {
    CaseStatus.WAITING_VENDOR_RESPONSE: "等待廠商回覆",
    CaseStatus.VENDOR_ACCEPTED: "廠商已接受",
    CaseStatus.AWAITING_USER_CONFIRMATION: "等待你確認",
    CaseStatus.CONFIRMED: "已確認，等待到場",
    CaseStatus.VENDOR_DECLINED: "廠商婉拒",
    CaseStatus.COMPLETED: "已完成",
    CaseStatus.CANCELLED: "已取消",
}

#: status -> (next_action, blocked_reason)
STATUS_GUIDANCE: dict[CaseStatus, tuple[str, str | None]] = {
    CaseStatus.WAITING_VENDOR_RESPONSE: (
        "目前不需要你操作，等待廠商確認與回覆。",
        None,
    ),
    CaseStatus.VENDOR_ACCEPTED: (
        "廠商已接受委託，請確認報價與到場時間。",
        None,
    ),
    CaseStatus.AWAITING_USER_CONFIRMATION: (
        "請確認是否成立案件，確認後才會把聯絡資訊提供給廠商。",
        None,
    ),
    CaseStatus.CONFIRMED: ("已確認，等待廠商到場服務。", None),
    CaseStatus.VENDOR_DECLINED: (
        "建議回到推薦清單改選其他廠商。",
        "廠商婉拒了這次委託。",
    ),
    CaseStatus.COMPLETED: ("案件已完成，歡迎給廠商評價。", None),
    CaseStatus.CANCELLED: ("案件已取消，可以重新提出需求。", "案件已取消。"),
}

#: Fields the vendor must not see until the resident confirms.
WITHHELD_LABELS = ["完整門牌地址", "聯絡人姓名", "聯絡電話", "上傳的照片"]


class CaseCreationError(RuntimeError):
    """Case cannot be created from the current state."""

    def __init__(self, message: str, *, code: str = "invalid_state"):
        super().__init__(message)
        self.code = code


class DuplicateCaseError(RuntimeError):
    """The task already has an active case."""

    def __init__(self, message: str, *, existing: ConsultationCase):
        super().__init__(message)
        self.existing = existing


def find_active_case(db: Session, task_id: int) -> ConsultationCase | None:
    """The task's current case, if it is still in play."""
    return db.scalars(
        select(ConsultationCase)
        .where(
            ConsultationCase.task_id == task_id,
            ConsultationCase.status.in_(tuple(ACTIVE_CASE_STATUSES)),
        )
        .order_by(ConsultationCase.id.desc())
        .limit(1)
    ).first()


def _next_case_number(db: Session, today: date) -> str:
    """Build ``CASE-YYYYMMDD-NNNN`` from the count of cases created today.

    Not race-proof on its own, which is why ``case_number`` carries a unique
    index and :func:`create_case` retries on IntegrityError.
    """
    stamp = today.strftime("%Y%m%d")
    prefix = f"{CASE_NUMBER_PREFIX}-{stamp}-"
    used = db.scalar(
        select(func.count())
        .select_from(ConsultationCase)
        .where(ConsultationCase.case_number.like(f"{prefix}%"))
    )
    return f"{prefix}{(used or 0) + 1:04d}"


def get_case(db: Session, case_id: int) -> ConsultationCase:
    """Load a case with vendor, task and history attached.

    Raises:
        LookupError: if no such case exists.
    """
    case = db.scalars(
        select(ConsultationCase)
        .options(
            selectinload(ConsultationCase.vendor).selectinload(Vendor.categories),
            selectinload(ConsultationCase.task).selectinload(LifeTask.category),
            selectinload(ConsultationCase.history),
        )
        .where(ConsultationCase.id == case_id)
    ).first()
    if case is None:
        raise LookupError(f"Case {case_id} does not exist")
    return case


def create_case(
    db: Session,
    *,
    task: LifeTask,
    vendor: Vendor,
    form_data: dict[str, Any],
    estimated_price: int | None = None,
    recommendation_reason: str | None = None,
) -> ConsultationCase:
    """Dispatch ``task`` to ``vendor`` as a formal case.

    Raises:
        DuplicateCaseError: the task already has an active case.
        CaseCreationError: the task is not in a dispatchable state, or the
            vendor cannot serve the task's category.
    """
    existing = find_active_case(db, task.id)
    if existing is not None:
        raise DuplicateCaseError(
            f"任務 #{task.id} 已經建立過案件 {existing.case_number}"
            f"（狀態：{STATUS_LABELS.get(existing.status, existing.status)}），"
            "不會重複建單。",
            existing=existing,
        )

    if task.status not in (TaskStatus.READY_FOR_MATCHING, TaskStatus.MATCHING):
        raise CaseCreationError(
            f"任務目前狀態是 {task.status}，必須先補齊資料並轉為 "
            f"{TaskStatus.READY_FOR_MATCHING} 才能建立案件。"
        )

    if task.category_id is not None:
        vendor_category_ids = {c.id for c in vendor.categories}
        if task.category_id not in vendor_category_ids:
            raise CaseCreationError(
                f"廠商「{vendor.name}」沒有提供這個服務類型，無法建立案件。",
                code="category_mismatch",
            )

    previous_task_status = str(task.status)
    next_action, blocked_reason = STATUS_GUIDANCE[CaseStatus.WAITING_VENDOR_RESPONSE]

    last_error: IntegrityError | None = None
    for attempt in range(MAX_CASE_NUMBER_ATTEMPTS):
        case_number = _next_case_number(db, datetime.now(timezone.utc).date())
        case = ConsultationCase(
            case_number=case_number,
            task_id=task.id,
            vendor_id=vendor.id,
            status=CaseStatus.WAITING_VENDOR_RESPONSE,
            estimated_price=estimated_price,
            recommendation_reason=recommendation_reason,
            form_data=form_data or {},
            next_action=next_action,
            blocked_reason=blocked_reason,
            contact_shared=False,
        )
        db.add(case)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            # Either the number collided or (task, vendor) already exists.
            if "uq_consultation_task_vendor" in str(exc.orig):
                raise DuplicateCaseError(
                    f"任務 #{task.id} 已經對廠商「{vendor.name}」建立過案件。",
                    existing=_require_existing(db, task.id, vendor.id),
                ) from exc
            logger.warning(
                "case_number %s collided, retrying (attempt %d)", case_number, attempt + 1
            )
            continue
        break
    else:  # pragma: no cover - needs sustained contention
        raise CaseCreationError(
            "產生案件編號時持續衝突，請重試。", code="case_number_exhausted"
        ) from last_error

    db.add(
        CaseStatusHistory(
            case_id=case.id,
            from_status=previous_task_status,
            to_status=CaseStatus.WAITING_VENDOR_RESPONSE.value,
            actor="consumer",
            note=f"住戶選擇廠商「{vendor.name}」，案件 {case.case_number} 已送出。",
        )
    )

    task.status = TaskStatus.MATCHING
    task.next_action = next_action
    db.add(task)

    db.commit()
    logger.info(
        "Created case %s (id=%s) task=%s vendor=%s",
        case.case_number,
        case.id,
        task.id,
        vendor.id,
    )
    return get_case(db, case.id)


def _require_existing(db: Session, task_id: int, vendor_id: int) -> ConsultationCase:
    case = db.scalars(
        select(ConsultationCase).where(
            ConsultationCase.task_id == task_id,
            ConsultationCase.vendor_id == vendor_id,
        )
    ).first()
    if case is None:  # pragma: no cover - only if the row vanished mid-request
        raise CaseCreationError("案件狀態不一致，請重新整理後再試。")
    return case


def _build_shared_view(case: ConsultationCase) -> SharedWithVendor:
    """What the vendor sees before the resident confirms.

    ``title`` and ``summary`` are LLM-written free text, so they are redacted
    rather than passed through: the model will repeat a street name the
    resident mentioned in their original sentence, which would make the
    withheld-address promise false.
    """
    parsed: dict[str, Any] = case.task.parsed_data or {}
    budget = parsed.get("budget") or {}
    location = parsed.get("location") or {}

    amount = budget.get("amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None

    title = parsed.get("title")
    summary = parsed.get("summary")
    if not case.contact_shared:
        terms = sensitive_terms(parsed, case.form_data)
        title = redact(title, terms)
        summary = redact(summary, terms)

    return SharedWithVendor(
        title=title,
        summary=summary,
        category_name=case.task.category.name if case.task.category else None,
        city=location.get("city"),
        district=location.get("district"),
        budget_amount=amount,
        urgency=parsed.get("urgency"),
        preferred_time=parsed.get("preferred_time"),
        withheld=[] if case.contact_shared else list(WITHHELD_LABELS),
    )


def _build_timeline(case: ConsultationCase) -> list[CaseTimelineStep]:
    """Project the whole journey, not just what already happened."""
    created = next(
        (h for h in case.history if h.to_status == CaseStatus.WAITING_VENDOR_RESPONSE.value),
        None,
    )
    responded = next(
        (
            h
            for h in case.history
            if h.to_status
            in (CaseStatus.VENDOR_ACCEPTED.value, CaseStatus.VENDOR_DECLINED.value)
        ),
        None,
    )
    confirmed = next(
        (h for h in case.history if h.to_status == CaseStatus.CONFIRMED.value), None
    )
    completed = next(
        (h for h in case.history if h.to_status == CaseStatus.COMPLETED.value), None
    )

    status = case.status

    def state(done: bool, current: bool) -> str:
        return "done" if done else "current" if current else "upcoming"

    steps = [
        CaseTimelineStep(
            key="analyzed",
            label="需求解析完成",
            state="done",
            at=case.task.created_at,
            note="AI 已擷取服務類型、地區與預算。",
        ),
        CaseTimelineStep(
            key="dispatched",
            label="案件已送出，等待廠商確認",
            state=state(
                responded is not None,
                status == CaseStatus.WAITING_VENDOR_RESPONSE,
            ),
            at=created.created_at if created else case.created_at,
            note=f"案件編號 {case.case_number}",
        ),
        CaseTimelineStep(
            key="vendor_response",
            label="廠商回覆",
            state=state(
                confirmed is not None or completed is not None,
                status
                in (
                    CaseStatus.VENDOR_ACCEPTED,
                    CaseStatus.VENDOR_DECLINED,
                    CaseStatus.AWAITING_USER_CONFIRMATION,
                ),
            ),
            at=responded.created_at if responded else None,
        ),
        CaseTimelineStep(
            key="confirmed",
            label="你確認並交換聯絡資訊",
            state=state(completed is not None, status == CaseStatus.CONFIRMED),
            at=confirmed.created_at if confirmed else None,
        ),
        CaseTimelineStep(
            key="completed",
            label="服務完成",
            state=state(False, status == CaseStatus.COMPLETED),
            at=completed.created_at if completed else None,
        ),
    ]

    if status == CaseStatus.CANCELLED:
        for step in steps:
            if step.state == "current":
                step.state = "upcoming"
                step.note = "案件已取消"

    return steps


def to_case_read(case: ConsultationCase) -> CaseRead:
    """Assemble the API view of a case."""
    next_action, blocked_reason = STATUS_GUIDANCE.get(
        case.status, (case.next_action, case.blocked_reason)
    )

    return CaseRead(
        id=case.id,
        case_number=case.case_number,
        status=case.status,
        status_label=STATUS_LABELS.get(case.status, str(case.status)),
        task_id=case.task_id,
        task_status=str(case.task.status),
        next_action=case.next_action or next_action,
        blocked_reason=case.blocked_reason or blocked_reason,
        estimated_price=case.estimated_price,
        recommendation_reason=case.recommendation_reason,
        contact_shared=case.contact_shared,
        privacy_notice=PRIVACY_NOTICE,
        vendor=VendorRead.model_validate(case.vendor),
        shared_with_vendor=_build_shared_view(case),
        timeline=_build_timeline(case),
        history=[CaseHistoryEntry.model_validate(h) for h in case.history],
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


__all__ = [
    "CaseCreationError",
    "DuplicateCaseError",
    "PRIVACY_NOTICE",
    "STATUS_LABELS",
    "create_case",
    "find_active_case",
    "get_case",
    "to_case_read",
]
