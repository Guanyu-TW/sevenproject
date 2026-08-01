from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.consultation_case import ConsultationCase


class CaseStatusHistory(TimestampMixin, Base):
    """Append-only audit trail of everything that moved a case.

    ``from_status`` / ``to_status`` are plain strings rather than the
    ``case_status`` enum on purpose: the very first entry records the handover
    from a *task* status (``ready_for_matching``) into a *case* status, and a
    single enum column could not express both vocabularies.
    """

    __tablename__ = "case_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("consultation_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Who caused the change: "system", "consumer", "vendor", "admin".
    actor: Mapped[str] = mapped_column(
        String(20), nullable=False, default="system", server_default="system"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped["ConsultationCase"] = relationship(back_populates="history")

    def __repr__(self) -> str:
        return (
            f"<CaseStatusHistory case_id={self.case_id} "
            f"{self.from_status}->{self.to_status}>"
        )
