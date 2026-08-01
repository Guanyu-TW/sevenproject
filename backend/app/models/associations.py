"""Association tables shared between models."""

from sqlalchemy import Column, ForeignKey, Table

from app.db.base_class import Base

#: A vendor can serve several service categories (水電 + 清潔 is common), and a
#: category has many vendors, so this is a plain many-to-many link table.
vendor_service_categories = Table(
    "vendor_service_categories",
    Base.metadata,
    Column(
        "vendor_id",
        ForeignKey("vendors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        ForeignKey("service_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

__all__ = ["vendor_service_categories"]
