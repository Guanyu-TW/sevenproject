"""Health / readiness checks."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def check_database(db: Session) -> tuple[bool, str | None]:
    """Run a trivial query to prove the connection really works.

    Returns ``(True, None)`` on success, ``(False, reason)`` otherwise.
    """
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as exc:  # connection refused, auth failure, ...
        logger.warning("Database health check failed: %s", exc)
        return False, exc.__class__.__name__
