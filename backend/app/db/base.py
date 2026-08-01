"""Import target for Alembic: pulls every model into Base.metadata.

Do not remove the model imports even though they look unused.
"""

from app.db.base_class import Base  # noqa: F401
from app.models import (  # noqa: F401
    CaseStatusHistory,
    ConsultationCase,
    LifeTask,
    ServiceCategory,
    ServiceForm,
    User,
    Vendor,
    vendor_service_categories,
)

__all__ = [
    "Base",
    "CaseStatusHistory",
    "ConsultationCase",
    "LifeTask",
    "ServiceCategory",
    "ServiceForm",
    "User",
    "Vendor",
    "vendor_service_categories",
]
