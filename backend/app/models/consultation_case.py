from datetime import datetime
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import CONTACT_UNLOCKED_STATUSES, CaseStatus

if TYPE_CHECKING:
    from app.models.case_status_history import CaseStatusHistory
    from app.models.life_task import LifeTask
    from app.models.vendor import Vendor


class ConsultationCase(TimestampMixin, Base):
    """A task formally dispatched to one vendor.

    ``form_data`` is a snapshot of what the resident submitted at the moment
    the case was created, so later edits to the task cannot silently rewrite
    what the vendor was asked to quote on.
    """

    __tablename__ = "consultation_cases"
    __table_args__ = (
        UniqueConstraint("task_id", "vendor_id", name="uq_consultation_task_vendor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("life_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CaseStatus.WAITING_VENDOR_RESPONSE,
        server_default=CaseStatus.WAITING_VENDOR_RESPONSE.value,
        index=True,
    )

    estimated_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Filled in when the vendor responds.
    vendor_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    task: Mapped["LifeTask"] = relationship(back_populates="consultation_cases")
    vendor: Mapped["Vendor"] = relationship(back_populates="consultation_cases")
    history: Mapped[list["CaseStatusHistory"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseStatusHistory.id",
    )

    @property
    def contact_shared(self) -> bool:
        """Whether the vendor may see the resident's address, name and phone.

        Derived from ``status`` rather than stored: a separate boolean column
        was a second source of truth that could disagree with the status.
        """
        return self.status in CONTACT_UNLOCKED_STATUSES

    def __repr__(self) -> str:
        return (
            f"<ConsultationCase id={self.id} number={self.case_number!r} "
            f"status={self.status}>"
        )
