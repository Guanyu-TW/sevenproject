"""Aggregates a resident's tasks and cases for the overview dashboard.

Everything is fetched in one pass with ``selectinload`` so rendering N task
cards does not turn into N+1 queries for the case and vendor of each one.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CaseStatus,
    ConsultationCase,
    LifeTask,
    TaskStatus,
    Vendor,
)
from app.schemas.dashboard import (
    DashboardCaseRef,
    DashboardResponse,
    DashboardStats,
    DashboardTaskItem,
    DashboardUser,
)
from app.services.case_service import STATUS_LABELS as CASE_STATUS_LABELS

logger = logging.getLogger(__name__)

TASK_STATUS_LABELS: dict[TaskStatus, str] = {
    TaskStatus.DRAFT: "草稿",
    TaskStatus.NEEDS_INFO: "待補資料",
    TaskStatus.READY_FOR_MATCHING: "待媒合",
    TaskStatus.MATCHING: "媒合中",
    TaskStatus.COMPLETED: "已完成",
    TaskStatus.CANCELLED: "已取消",
}

#: Coarse buckets so the UI picks a badge colour without duplicating the
#: status vocabulary. The case status wins when a case exists, because that is
#: what the resident actually cares about once a vendor is involved.
_CASE_TONES: dict[CaseStatus, str] = {
    # vendor_accepted needs the resident to act (confirm), so it reads as
    # "waiting on you" rather than "running smoothly".
    CaseStatus.WAITING_VENDOR_RESPONSE: "pending",
    CaseStatus.VENDOR_ACCEPTED: "pending",
    CaseStatus.CONTACT_SHARED: "active",
    CaseStatus.COMPLETED: "done",
    CaseStatus.VENDOR_REJECTED: "failed",
    CaseStatus.CANCELLED: "failed",
}

_TASK_TONES: dict[TaskStatus, str] = {
    TaskStatus.DRAFT: "draft",
    TaskStatus.NEEDS_INFO: "draft",
    TaskStatus.READY_FOR_MATCHING: "pending",
    TaskStatus.MATCHING: "active",
    TaskStatus.COMPLETED: "done",
    TaskStatus.CANCELLED: "failed",
}

#: Cases that count as "進行中" on the stats row.
_IN_PROGRESS_CASE_STATUSES = frozenset(
    {CaseStatus.VENDOR_ACCEPTED, CaseStatus.CONTACT_SHARED}
)

URGENCY_TAGS: dict[str, str] = {
    "emergency": "緊急",
    "high": "急件",
    "normal": "一般",
    "low": "不急",
}

MAX_TAGS = 6


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_tags(task: LifeTask) -> list[str]:
    """AI-derived labels for the card.

    Sourced from what the model already extracted rather than recomputed, so
    the dashboard never disagrees with the task detail view.
    """
    parsed: dict[str, Any] = task.parsed_data or {}
    tags: list[str] = []

    if task.category is not None:
        tags.append(task.category.name)

    # The finer service item, right after the category, so a list of plumbing
    # jobs is scannable instead of six identical 水電維修 chips. Skipped when it
    # just repeats the card's own heading.
    service_label = parsed.get("service_label")
    title = parsed.get("title")
    if isinstance(service_label, str):
        service_label = service_label.strip()
        if service_label and service_label not in tags and service_label != title:
            tags.append(service_label)

    urgency = parsed.get("urgency")
    if isinstance(urgency, str) and urgency in URGENCY_TAGS:
        # "一般" adds nothing to a card, so only surface the notable ones.
        if urgency in ("emergency", "high"):
            tags.append(URGENCY_TAGS[urgency])

    for keyword in parsed.get("keywords") or []:
        if isinstance(keyword, str):
            keyword = keyword.strip()
            if keyword and keyword not in tags:
                tags.append(keyword)

    if task.missing_fields:
        tags.append(f"缺 {len(task.missing_fields)} 項資料")

    return tags[:MAX_TAGS]


def _latest_case(task: LifeTask) -> ConsultationCase | None:
    """The newest case on the task.

    A task can hold several over time: a rejection frees it to pick another
    vendor, so the highest id is the one that reflects reality now.
    """
    if not task.consultation_cases:
        return None
    return max(task.consultation_cases, key=lambda c: c.id)


def _to_case_ref(case: ConsultationCase) -> DashboardCaseRef:
    return DashboardCaseRef(
        case_id=case.id,
        case_number=case.case_number,
        status=case.status,
        status_label=CASE_STATUS_LABELS.get(case.status, str(case.status)),
        vendor_id=case.vendor_id,
        vendor_name=case.vendor.name,
        vendor_rating=float(case.vendor.rating) if case.vendor.rating is not None else None,
        estimated_price=case.estimated_price,
        proposed_time=case.proposed_time,
        vendor_note=case.vendor_note,
        responded_at=case.responded_at,
    )


def _to_task_item(task: LifeTask) -> DashboardTaskItem:
    parsed: dict[str, Any] = task.parsed_data or {}
    budget = parsed.get("budget") or {}
    location = parsed.get("location") or {}
    case = _latest_case(task)

    # A case, once it exists, is the more meaningful thing to show: "媒合中"
    # tells the resident far less than "廠商已接單". Colour and text are derived
    # from the same source so a red badge can never read "待媒合".
    task_label = TASK_STATUS_LABELS.get(task.status, str(task.status))
    if case is not None:
        tone = _CASE_TONES.get(case.status, "pending")
        display_label = CASE_STATUS_LABELS.get(case.status, str(case.status))
    else:
        tone = _TASK_TONES.get(task.status, "draft")
        display_label = task_label

    return DashboardTaskItem(
        task_id=task.id,
        title=parsed.get("title"),
        summary=parsed.get("summary"),
        raw_input=task.raw_input,
        status=task.status,
        status_label=task_label,
        display_label=display_label,
        badge_tone=tone,
        category_code=task.category.code if task.category else None,
        category_name=task.category.name if task.category else None,
        tags=_build_tags(task),
        budget_amount=_as_float(budget.get("amount")),
        currency=budget.get("currency"),
        city=location.get("city"),
        district=location.get("district"),
        urgency=parsed.get("urgency"),
        next_action=task.next_action,
        missing_count=len(task.missing_fields or []),
        case_count=len(task.consultation_cases or []),
        latest_case=_to_case_ref(case) if case is not None else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _build_stats(db: Session, user_id: int) -> DashboardStats:
    """Counters computed in SQL so they cover every task, not just the page."""
    task_counts = dict(
        db.execute(
            select(LifeTask.status, func.count(LifeTask.id))
            .where(LifeTask.user_id == user_id)
            .group_by(LifeTask.status)
        ).all()
    )

    case_counts = dict(
        db.execute(
            select(ConsultationCase.status, func.count(ConsultationCase.id))
            .join(LifeTask, LifeTask.id == ConsultationCase.task_id)
            .where(LifeTask.user_id == user_id)
            .group_by(ConsultationCase.status)
        ).all()
    )

    def tasks(*statuses: TaskStatus) -> int:
        return sum(task_counts.get(s, 0) for s in statuses)

    def cases(*statuses: CaseStatus) -> int:
        return sum(case_counts.get(s, 0) for s in statuses)

    return DashboardStats(
        total_tasks=sum(task_counts.values()),
        needs_input=tasks(TaskStatus.DRAFT, TaskStatus.NEEDS_INFO),
        ready_for_matching=tasks(TaskStatus.READY_FOR_MATCHING),
        waiting_vendor=cases(CaseStatus.WAITING_VENDOR_RESPONSE),
        in_progress=cases(*_IN_PROGRESS_CASE_STATUSES),
        # Counted on tasks, not tasks + cases: completing a case also completes
        # its task, so adding both would double-count every finished job.
        completed=tasks(TaskStatus.COMPLETED),
        rejected=cases(CaseStatus.VENDOR_REJECTED),
        cancelled=tasks(TaskStatus.CANCELLED),
        awaiting_confirmation=cases(CaseStatus.VENDOR_ACCEPTED),
    )


def build_dashboard(
    db: Session,
    *,
    user,
    limit: int = 50,
) -> DashboardResponse:
    """Every task belonging to ``user``, newest first, with its latest case."""
    total = (
        db.scalar(
            select(func.count())
            .select_from(LifeTask)
            .where(LifeTask.user_id == user.id)
        )
        or 0
    )

    tasks = list(
        db.scalars(
            select(LifeTask)
            .options(
                selectinload(LifeTask.category),
                selectinload(LifeTask.consultation_cases).selectinload(
                    ConsultationCase.vendor
                ),
            )
            .where(LifeTask.user_id == user.id)
            .order_by(LifeTask.created_at.desc(), LifeTask.id.desc())
            .limit(limit)
        ).all()
    )

    logger.info(
        "Dashboard for user %s: %d of %d tasks", user.id, len(tasks), total
    )

    return DashboardResponse(
        user=DashboardUser(id=user.id, name=user.name),
        stats=_build_stats(db, user.id),
        total=total,
        returned=len(tasks),
        truncated=len(tasks) < total,
        tasks=[_to_task_item(t) for t in tasks],
    )


__all__ = ["TASK_STATUS_LABELS", "build_dashboard"]
