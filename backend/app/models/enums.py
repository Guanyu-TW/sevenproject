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
    READY = "ready"
    MATCHING = "matching"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CaseStatus(StrEnum):
    """Lifecycle of a single vendor <-> task consultation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
