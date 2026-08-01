from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import TaskStatus

if TYPE_CHECKING:
    from app.models.consultation_case import ConsultationCase
    from app.models.service_category import ServiceCategory
    from app.models.user import User


class LifeTask(TimestampMixin, Base):
    """One life need expressed by a resident.

    ``parsed_data`` is what the AI understood, ``missing_fields`` is what it
    still needs to ask about before the task can be matched to vendors.
    """

    __tablename__ = "life_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=TaskStatus.DRAFT,
        server_default=TaskStatus.DRAFT.value,
        index=True,
    )
    parsed_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    missing_fields: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    #: Plain-language description of what the resident should do next, kept in
    #: sync with the task status so the UI never has to infer it.
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="life_tasks")
    category: Mapped["ServiceCategory | None"] = relationship(back_populates="life_tasks")
    consultation_cases: Mapped[list["ConsultationCase"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<LifeTask id={self.id} user_id={self.user_id} status={self.status}>"
