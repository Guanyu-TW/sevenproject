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
    #: The resident confirmed the quote, so the vendor may now see the full
    #: address and phone number. The status name *is* the privacy gate: there is
    #: deliberately no separate boolean that could drift out of step with it.
    CONTACT_SHARED = "contact_shared"
    COMPLETED = "completed"
    VENDOR_REJECTED = "vendor_rejected"
    CANCELLED = "cancelled"


#: Statuses in which the vendor is allowed to see the resident's full address,
#: name and phone number.
CONTACT_UNLOCKED_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.CONTACT_SHARED, CaseStatus.COMPLETED}
)

#: A task may only hold one case in any of these states at a time. Anything
#: else (rejected / cancelled) frees the task up to pick another vendor.
ACTIVE_CASE_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.WAITING_VENDOR_RESPONSE,
        CaseStatus.VENDOR_ACCEPTED,
        CaseStatus.CONTACT_SHARED,
        CaseStatus.COMPLETED,
    }
)

#: Cases the vendor still has to act on.
VENDOR_ACTIONABLE_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.WAITING_VENDOR_RESPONSE}
)

#: Cases in flight after the vendor accepted.
VENDOR_IN_PROGRESS_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.VENDOR_ACCEPTED, CaseStatus.CONTACT_SHARED}
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
        {CaseStatus.CONTACT_SHARED, CaseStatus.CANCELLED}
    ),
    CaseStatus.CONTACT_SHARED: frozenset(
        {CaseStatus.COMPLETED, CaseStatus.CANCELLED}
    ),
    CaseStatus.VENDOR_REJECTED: frozenset(),
    CaseStatus.COMPLETED: frozenset(),
    CaseStatus.CANCELLED: frozenset(),
}
