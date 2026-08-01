"""Shared enumerations used by the ORM models and the Pydantic schemas."""

from enum import StrEnum


class UserRole(StrEnum):
    CONSUMER = "consumer"
    VENDOR = "vendor"
    ADMIN = "admin"


class TaskStatus(StrEnum):
    """Lifecycle of a LifeTask, from raw user input to a closed request."""

    DRAFT = "draft"
    NEEDS_INFO = "needs_info"
    READY_FOR_MATCHING = "ready_for_matching"
    MATCHING = "matching"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


#: Which status changes the API will accept. Anything else is a 409.
ALLOWED_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset(
        {TaskStatus.NEEDS_INFO, TaskStatus.READY_FOR_MATCHING, TaskStatus.CANCELLED}
    ),
    TaskStatus.NEEDS_INFO: frozenset(
        {TaskStatus.READY_FOR_MATCHING, TaskStatus.CANCELLED}
    ),
    TaskStatus.READY_FOR_MATCHING: frozenset(
        {TaskStatus.MATCHING, TaskStatus.NEEDS_INFO, TaskStatus.CANCELLED}
    ),
    TaskStatus.MATCHING: frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


class CaseStatus(StrEnum):
    """Lifecycle of a single vendor <-> task consultation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
