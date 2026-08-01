"""Persistence rules for LifeTask records produced by the AI layer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import LifeTask, ServiceCategory, TaskStatus, User, UserRole
from app.schemas.ai import DemandAnalysis

logger = logging.getLogger(__name__)


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


__all__ = [
    "create_task_from_analysis",
    "get_or_create_demo_user",
    "resolve_user",
]
