from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.consultation_case import ConsultationCase
    from app.models.user import User


class Vendor(TimestampMixin, Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    rating: Mapped[float] = mapped_column(
        Numeric(2, 1), nullable=False, default=0, server_default="0"
    )

    user: Mapped["User"] = relationship(back_populates="vendor")
    consultation_cases: Mapped[list["ConsultationCase"]] = relationship(
        back_populates="vendor",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name={self.name!r} rating={self.rating}>"
