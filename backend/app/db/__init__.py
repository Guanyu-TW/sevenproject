"""Database package.

Only the declarative base is re-exported here on purpose: importing
``app.db.session`` builds the engine, and Alembic's offline mode must be able
to load the metadata without a live driver/connection.
"""

from app.db.base_class import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
