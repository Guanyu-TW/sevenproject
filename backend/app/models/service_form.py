from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.service_category import ServiceCategory


class ServiceForm(TimestampMixin, Base):
    """The field definition the AI has to fill in for a given category.

    ``schema_definition`` holds the declarative form spec (field name, type,
    required flag, prompt copy...) so new service types need no code change.
    """

    __tablename__ = "service_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("service_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    category: Mapped["ServiceCategory"] = relationship(back_populates="forms")

    def __repr__(self) -> str:
        return f"<ServiceForm id={self.id} category_id={self.category_id}>"
