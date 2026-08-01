from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.life_task import LifeTask
    from app.models.service_form import ServiceForm


class ServiceCategory(TimestampMixin, Base):
    """A top-level service domain, e.g. plumbing / cleaning / dining / shopping."""

    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    forms: Mapped[list["ServiceForm"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )
    life_tasks: Mapped[list["LifeTask"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<ServiceCategory id={self.id} code={self.code!r}>"
