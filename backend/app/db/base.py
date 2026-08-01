"""Import target for Alembic: pulls every model into Base.metadata.

Do not remove the model imports even though they look unused.
"""

from app.db.base_class import Base  # noqa: F401
from app.models import (  # noqa: F401
    ConsultationCase,
    LifeTask,
    ServiceCategory,
    ServiceForm,
    User,
    Vendor,
)

__all__ = [
    "Base",
    "ConsultationCase",
    "LifeTask",
    "ServiceCategory",
    "ServiceForm",
    "User",
    "Vendor",
]
