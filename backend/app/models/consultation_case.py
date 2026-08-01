from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import CaseStatus

if TYPE_CHECKING:
    from app.models.life_task import LifeTask
    from app.models.vendor import Vendor


class ConsultationCase(TimestampMixin, Base):
    """A task dispatched to one vendor for quoting / consultation."""

    __tablename__ = "consultation_cases"
    __table_args__ = (
        UniqueConstraint("task_id", "vendor_id", name="uq_consultation_task_vendor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("life_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CaseStatus.PENDING,
        server_default=CaseStatus.PENDING.value,
        index=True,
    )

    task: Mapped["LifeTask"] = relationship(back_populates="consultation_cases")
    vendor: Mapped["Vendor"] = relationship(back_populates="consultation_cases")

    def __repr__(self) -> str:
        return (
            f"<ConsultationCase id={self.id} task_id={self.task_id} "
            f"vendor_id={self.vendor_id} status={self.status}>"
        )
