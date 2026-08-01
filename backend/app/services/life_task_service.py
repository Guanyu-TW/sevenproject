"""Persistence rules for LifeTask records produced by the AI layer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models import (
    ALLOWED_TASK_TRANSITIONS,
    LifeTask,
    ServiceCategory,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas.ai import CategoryHint, DemandAnalysis
from app.services.missing_fields import apply_filled_fields

logger = logging.getLogger(__name__)


def list_category_hints(db: Session) -> list[CategoryHint]:
    """Allowed classifications, read from the database.

    Injected into the AI prompt so adding a service category is a data change,
    not a prompt edit.
    """
    rows = db.scalars(select(ServiceCategory).order_by(ServiceCategory.id)).all()
    return [CategoryHint(code=row.code, name=row.name) for row in rows]


def get_or_create_demo_user(db: Session) -> User:
    """Return the shared demo resident, creating it on first use.

    Placeholder until real authentication exists.
    """
    user = db.scalars(
        select(User).where(User.name == settings.DEMO_USER_NAME).limit(1)
    ).first()
    if user is not None:
        return user

    user = User(name=settings.DEMO_USER_NAME, role=UserRole.CONSUMER)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created demo user id=%s", user.id)
    return user


def resolve_user(db: Session, user_id: int | None) -> User:
    """Look up ``user_id``, or fall back to the demo resident.

    Raises:
        LookupError: if an explicit ``user_id`` does not exist.
    """
    if user_id is None:
        return get_or_create_demo_user(db)

    user = db.get(User, user_id)
    if user is None:
        raise LookupError(f"User {user_id} does not exist")
    return user


def _find_category(db: Session, code: str | None) -> ServiceCategory | None:
    if not code:
        return None
    category = db.scalars(
        select(ServiceCategory).where(ServiceCategory.code == code).limit(1)
    ).first()
    if category is None:
        logger.warning("AI returned unknown category code %r", code)
    return category


def create_task_from_analysis(
    db: Session,
    *,
    user: User,
    prompt: str,
    analysis: DemandAnalysis,
    provider_name: str,
) -> LifeTask:
    """Store one analysis result as a draft LifeTask.

    ``parsed_data`` keeps the provider output plus a ``_meta`` block so we can
    always tell which provider produced a given task and how confident it was.
    """
    category = _find_category(db, analysis.category_code)

    parsed_data = dict(analysis.parsed_data)
    parsed_data.update(
        {
            "title": analysis.title,
            "summary": analysis.summary,
            "category_code": analysis.category_code,
            "category_name": category.name if category else None,
            "_meta": {
                "provider": provider_name,
                "model": analysis.model,
                "confidence": analysis.confidence,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    )

    task = LifeTask(
        user_id=user.id,
        category_id=category.id if category else None,
        raw_input=prompt,
        status=TaskStatus.DRAFT,
        parsed_data=parsed_data,
        missing_fields=[field.model_dump() for field in analysis.missing_fields],
    )
    db.add(task)
    db.commit()

    logger.info(
        "Created LifeTask id=%s user_id=%s category=%s missing=%d",
        task.id,
        user.id,
        analysis.category_code,
        len(analysis.missing_fields),
    )

    # Re-read with the category eagerly loaded so response serialisation never
    # triggers a lazy load after the request-scoped session is gone.
    return db.scalars(
        select(LifeTask)
        .options(selectinload(LifeTask.category))
        .where(LifeTask.id == task.id)
    ).one()


class TaskTransitionError(RuntimeError):
    """The requested status change is not allowed from the current status."""

    def __init__(self, message: str, *, current: str, requested: str):
        super().__init__(message)
        self.current = current
        self.requested = requested


def get_task(db: Session, task_id: int) -> LifeTask:
    """Load a task with its category eagerly attached.

    Raises:
        LookupError: if no such task exists.
    """
    task = db.scalars(
        select(LifeTask)
        .options(selectinload(LifeTask.category))
        .where(LifeTask.id == task_id)
    ).first()
    if task is None:
        raise LookupError(f"Task {task_id} does not exist")
    return task


def update_task(
    db: Session,
    *,
    task: LifeTask,
    filled_fields: dict[str, Any] | None = None,
    status: TaskStatus | None = None,
) -> LifeTask:
    """Merge submitted values into the task and optionally move its status.

    Fields that were successfully stored are removed from ``missing_fields``,
    so the frontend form shrinks as the resident fills it in.

    Raises:
        TaskTransitionError: if ``status`` is not reachable from the current one.
    """
    if status is not None and status != task.status:
        allowed = ALLOWED_TASK_TRANSITIONS.get(task.status, frozenset())
        if status not in allowed:
            allowed_text = ", ".join(sorted(allowed)) or "（無）"
            raise TaskTransitionError(
                f"無法從 {task.status} 轉換為 {status}。目前允許的狀態："
                f"{allowed_text}。",
                current=str(task.status),
                requested=str(status),
            )

        # Matching filters on category first, so a task without one can never
        # produce a candidate. Letting it become ready_for_matching would send
        # the resident through a form only to end at an empty vendor list.
        if status is TaskStatus.READY_FOR_MATCHING and task.category_id is None:
            intent = (task.parsed_data or {}).get("intent")
            if intent == "question":
                reason = "這是一個詢問，不是服務需求，所以不會進入媒合。"
            elif intent == "other":
                reason = "我沒有辨識出具體的服務需求。"
            else:
                reason = "這個需求不屬於平台目前提供的服務分類。"
            raise TaskTransitionError(
                f"{reason}請換一種說法描述你需要的服務，"
                "目前支援水電維修、居家清潔、餐飲訂購與代購採買。",
                current=str(task.status),
                requested=str(status),
            )

    if filled_fields:
        updated_parsed, applied = apply_filled_fields(task.parsed_data or {}, filled_fields)
        if applied:
            task.parsed_data = updated_parsed
            # JSONB columns are not mutation-tracked, and equality against the
            # previous value is not a reliable dirty check for nested dicts.
            # Flag it explicitly so the UPDATE always includes this column.
            flag_modified(task, "parsed_data")
            remaining = [
                field
                for field in (task.missing_fields or [])
                if _field_key(field) not in set(applied)
            ]
            task.missing_fields = remaining
            flag_modified(task, "missing_fields")
            logger.info(
                "Task %s filled %s, %d field(s) still missing",
                task.id,
                applied,
                len(remaining),
            )

    if status is not None:
        task.status = status

    db.add(task)
    db.commit()

    return get_task(db, task.id)


def _field_key(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("field") or "")
    return str(getattr(entry, "field", "") or "")


__all__ = [
    "TaskTransitionError",
    "create_task_from_analysis",
    "get_or_create_demo_user",
    "get_task",
    "list_category_hints",
    "resolve_user",
    "update_task",
]
