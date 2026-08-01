from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.associations import vendor_service_categories

if TYPE_CHECKING:
    from app.models.consultation_case import ConsultationCase
    from app.models.service_category import ServiceCategory
    from app.models.user import User


class Vendor(TimestampMixin, Base):
    """A service provider that can be matched to a LifeTask.

    ``service_city`` plus ``service_districts`` drive the hard geographic
    filter: an empty district list means the vendor covers the whole city.
    """

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

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_city: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
    service_districts: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )

    user: Mapped["User"] = relationship(back_populates="vendor")
    categories: Mapped[list["ServiceCategory"]] = relationship(
        secondary=vendor_service_categories,
        back_populates="vendors",
    )
    consultation_cases: Mapped[list["ConsultationCase"]] = relationship(
        back_populates="vendor",
        cascade="all, delete-orphan",
    )

    def covers_district(self, district: str | None) -> bool:
        """True when this vendor serves ``district``.

        An empty ``service_districts`` list means city-wide coverage, and an
        unknown district is treated as coverable so we do not drop candidates
        just because the resident was vague.
        """
        if not self.service_districts:
            return True
        if not district:
            return True
        return any(str(d) in district or district in str(d) for d in self.service_districts)

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name={self.name!r} rating={self.rating}>"
