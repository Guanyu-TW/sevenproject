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
    # A vendor rejection sends the task back so the resident can pick again.
    TaskStatus.MATCHING: frozenset(
        {
            TaskStatus.READY_FOR_MATCHING,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


class CaseStatus(StrEnum):
    """Lifecycle of a single vendor <-> task consultation.

    Member order matches the PostgreSQL enum order after migration 0005 so the
    two stay readable side by side.
    """

    WAITING_VENDOR_RESPONSE = "waiting_vendor_response"
    VENDOR_ACCEPTED = "vendor_accepted"
    AWAITING_USER_CONFIRMATION = "awaiting_user_confirmation"
    CONFIRMED = "confirmed"
    VENDOR_REJECTED = "vendor_rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


#: A task may only hold one case in any of these states at a time. Anything
#: else (rejected / cancelled) frees the task up to pick another vendor.
ACTIVE_CASE_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.WAITING_VENDOR_RESPONSE,
        CaseStatus.VENDOR_ACCEPTED,
        CaseStatus.AWAITING_USER_CONFIRMATION,
        CaseStatus.CONFIRMED,
        CaseStatus.COMPLETED,
    }
)

#: Cases the vendor still has to act on.
VENDOR_ACTIONABLE_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.WAITING_VENDOR_RESPONSE}
)

#: Which case transitions the API will accept.
ALLOWED_CASE_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.WAITING_VENDOR_RESPONSE: frozenset(
        {
            CaseStatus.VENDOR_ACCEPTED,
            CaseStatus.VENDOR_REJECTED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.VENDOR_ACCEPTED: frozenset(
        {
            CaseStatus.AWAITING_USER_CONFIRMATION,
            CaseStatus.CONFIRMED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.AWAITING_USER_CONFIRMATION: frozenset(
        {CaseStatus.CONFIRMED, CaseStatus.CANCELLED}
    ),
    CaseStatus.CONFIRMED: frozenset({CaseStatus.COMPLETED, CaseStatus.CANCELLED}),
    CaseStatus.VENDOR_REJECTED: frozenset(),
    CaseStatus.COMPLETED: frozenset(),
    CaseStatus.CANCELLED: frozenset(),
}
