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

from app.core.config import settings
from app.models import (
    ACTIVE_CASE_STATUSES,
    ALLOWED_CASE_TRANSITIONS,
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
    CaseStatus.VENDOR_ACCEPTED: "廠商已接單",
    CaseStatus.CONTACT_SHARED: "已交換聯絡資訊",
    CaseStatus.COMPLETED: "已完成",
    CaseStatus.VENDOR_REJECTED: "廠商婉拒",
    CaseStatus.CANCELLED: "已取消",
}

#: status -> (next_action, blocked_reason)
STATUS_GUIDANCE: dict[CaseStatus, tuple[str, str | None]] = {
    CaseStatus.WAITING_VENDOR_RESPONSE: (
        "目前不需要你操作，等待廠商確認與回覆。",
        None,
    ),
    CaseStatus.VENDOR_ACCEPTED: (
        "廠商已確認接案！請確認報價與到場時間，確認後才會把完整地址與電話提供給廠商。",
        None,
    ),
    CaseStatus.CONTACT_SHARED: (
        "已與廠商交換聯絡資訊，請等待廠商到場服務。",
        None,
    ),
    CaseStatus.COMPLETED: ("服務已完成，感謝您的使用！", None),
    CaseStatus.VENDOR_REJECTED: (
        "建議回到推薦清單改選其他廠商。",
        "廠商婉拒了這次委託。",
    ),
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
            # _build_shared_view falls back to the account name, so eager-load
            # the user too rather than lazy-loading it per case.
            selectinload(ConsultationCase.task).selectinload(LifeTask.user),
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
        )
        db.add(case)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            # Either the number collided or (task, vendor) already exists.
            if "uq_consultation_task_vendor" in str(exc.orig):
                previous_case = _require_existing(db, task.id, vendor.id)
                if previous_case.status == CaseStatus.VENDOR_REJECTED:
                    message = (
                        f"廠商「{vendor.name}」先前已婉拒這個需求"
                        f"（{previous_case.case_number}），請改選其他廠商。"
                    )
                else:
                    message = f"任務 #{task.id} 已經對廠商「{vendor.name}」建立過案件。"
                raise DuplicateCaseError(message, existing=previous_case) from exc
            logger.warning(
                "case_number %s collided, retrying (attempt %d)", case_number, attempt + 1
            )
            continue
        break
    else:  # pragma: no cover - needs sustained contention
        raise CaseCreationError(
            "產生案件編號時持續衝突，請重試。", code="case_number_exhausted"
        ) from last_error

    # Appended through the relationship for the same reason as in
    # vendor_service.respond_to_case: keep the in-memory graph consistent with
    # the database when expire_on_commit is off.
    case.history.append(
        CaseStatusHistory(
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

    contact = parsed.get("contact") or {}
    city = location.get("city")
    district = location.get("district")
    area = " ".join(p for p in (city, district) if p) or None

    unlocked = case.contact_shared
    title = parsed.get("title")
    summary = parsed.get("summary")

    if not unlocked:
        # Redact the LLM-written free text too: it happily repeats a street name
        # the resident mentioned in their original sentence, which would leak
        # the address around the structured field being withheld.
        terms = sensitive_terms(parsed, case.form_data)
        title = redact(title, terms)
        summary = redact(summary, terms)

    return SharedWithVendor(
        title=title,
        summary=summary,
        category_name=case.task.category.name if case.task.category else None,
        city=city,
        district=district,
        area=area,
        budget_amount=amount,
        urgency=parsed.get("urgency"),
        preferred_time=parsed.get("preferred_time"),
        contact_unlocked=unlocked,
        address=location.get("address") if unlocked else None,
        # Fall back to the account holder. Whether the AI asks for
        # contact_name is its own judgement call, so parsed contact.name is
        # genuinely often null -- and a vendor standing at the door with no
        # name to ask for is worse than showing the account name. Still gated
        # behind `unlocked`, so this leaks nothing earlier than before.
        contact_name=(contact.get("name") or case.task.user.name)
        if unlocked
        else None,
        contact_phone=contact.get("phone") if unlocked else None,
        withheld=[] if unlocked else list(WITHHELD_LABELS),
    )


class CaseTransitionError(RuntimeError):
    """The case is not in a state where this action makes sense."""

    def __init__(self, message: str, *, code: str = "invalid_state"):
        super().__init__(message)
        self.code = code


def _advance(
    db: Session,
    *,
    case_id: int,
    target: CaseStatus,
    actor: str,
    note: str,
    task_status: TaskStatus | None = None,
) -> ConsultationCase:
    """Move a case to ``target``, writing history and the task's next_action.

    Locks the row before reading its status: without that, two concurrent calls
    would both pass the transition guard and the second would silently overwrite
    the first, appending a duplicate history entry.
    """
    locked = db.execute(
        select(ConsultationCase.id)
        .where(ConsultationCase.id == case_id)
        .with_for_update()
    ).scalar_one_or_none()
    if locked is None:
        raise LookupError(f"Case {case_id} does not exist")

    case = get_case(db, case_id)
    previous = case.status

    if target not in ALLOWED_CASE_TRANSITIONS.get(previous, frozenset()):
        raise CaseTransitionError(
            f"案件目前狀態是「{STATUS_LABELS.get(previous, previous)}」，"
            f"無法執行這個操作。",
            code="invalid_state",
        )

    now = datetime.now(timezone.utc)
    next_action, blocked_reason = STATUS_GUIDANCE[target]

    case.status = target
    case.next_action = next_action
    case.blocked_reason = blocked_reason
    if target is CaseStatus.CONTACT_SHARED:
        case.confirmed_at = now
    elif target is CaseStatus.COMPLETED:
        case.completed_at = now

    # Appended through the relationship so the already-loaded collection stays
    # in step with the database (the session uses expire_on_commit=False).
    case.history.append(
        CaseStatusHistory(
            from_status=previous.value,
            to_status=target.value,
            actor=actor,
            note=note,
        )
    )

    task = case.task
    task.next_action = next_action
    if task_status is not None:
        task.status = task_status

    db.add(case)
    db.add(task)
    db.commit()

    logger.info(
        "Case %s %s -> %s by %s", case.case_number, previous, target, actor
    )
    return get_case(db, case_id)


def confirm_case(db: Session, *, case_id: int) -> ConsultationCase:
    """Resident accepts the quote, unlocking their contact details.

    Raises:
        LookupError: no such case.
        CaseTransitionError: the case is not at vendor_accepted.
    """
    case = _advance(
        db,
        case_id=case_id,
        target=CaseStatus.CONTACT_SHARED,
        actor="consumer",
        note="住戶確認報價與到場時間，已將完整地址與聯絡電話提供給廠商。",
    )
    return case


def complete_case(db: Session, *, case_id: int, actor: str = "consumer") -> ConsultationCase:
    """Mark the service as delivered. Callable by either side.

    Also closes the owning task, which is what makes the dashboard's
    "已完成任務" counter move.

    Raises:
        LookupError: no such case.
        CaseTransitionError: the case is not at contact_shared.
    """
    who = "廠商" if actor == "vendor" else "住戶"
    return _advance(
        db,
        case_id=case_id,
        target=CaseStatus.COMPLETED,
        actor=actor,
        note=f"{who}標記服務已完成。",
        task_status=TaskStatus.COMPLETED,
    )


def _vendor_response_note(case: ConsultationCase) -> str | None:
    """Surface the vendor's own words on the resident's timeline."""
    if case.status == CaseStatus.VENDOR_REJECTED:
        return case.vendor_note or "廠商婉拒了這次委託。"
    if case.vendor_note or case.proposed_time:
        bits = []
        if case.proposed_time:
            # PostgreSQL hands timestamptz back in UTC; showing that verbatim
            # would tell the resident to expect the vendor 8 hours early.
            local = case.proposed_time.astimezone(settings.tzinfo)
            bits.append("預計到場：" + local.strftime("%Y/%m/%d %H:%M"))
        if case.vendor_note:
            bits.append(f"廠商備註：{case.vendor_note}")
        return "　".join(bits)
    return None


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
            in (CaseStatus.VENDOR_ACCEPTED.value, CaseStatus.VENDOR_REJECTED.value)
        ),
        None,
    )
    confirmed = next(
        (h for h in case.history if h.to_status == CaseStatus.CONTACT_SHARED.value),
        None,
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
                status in (CaseStatus.VENDOR_ACCEPTED, CaseStatus.VENDOR_REJECTED),
            ),
            at=responded.created_at if responded else None,
            note=_vendor_response_note(case),
        ),
        CaseTimelineStep(
            key="confirmed",
            label="你確認並交換聯絡資訊",
            state=state(completed is not None, status == CaseStatus.CONTACT_SHARED),
            at=confirmed.created_at if confirmed else None,
            note="廠商已可看到完整地址與聯絡電話。" if confirmed else None,
        ),
        CaseTimelineStep(
            key="completed",
            label="服務完成",
            state="done" if status == CaseStatus.COMPLETED else "upcoming",
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
        vendor_note=case.vendor_note,
        proposed_time=case.proposed_time,
        responded_at=case.responded_at,
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
    "CaseTransitionError",
    "DuplicateCaseError",
    "PRIVACY_NOTICE",
    "STATUS_GUIDANCE",
    "STATUS_LABELS",
    "complete_case",
    "confirm_case",
    "create_case",
    "find_active_case",
    "get_case",
    "to_case_read",
]
