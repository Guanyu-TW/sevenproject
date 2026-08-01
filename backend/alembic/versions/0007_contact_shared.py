"""contact_shared status, confirm/complete timestamps, drop contact_shared flag

Revision ID: 0007_contact_shared
Revises: 0006_vendor_response
Create Date: 2026-08-02

The case_status enum is rebuilt rather than patched:

* ``confirmed`` becomes ``contact_shared``, which names what actually changes
  at that point -- the vendor gains access to the resident's address and phone.
* ``awaiting_user_confirmation`` is dropped. It was never reachable and was
  redundant with ``vendor_accepted``, which already means "waiting on the
  resident". PostgreSQL cannot drop an enum label in place, hence the full
  CREATE / ALTER COLUMN / DROP dance.

The ``contact_shared`` boolean column goes away for the same reason: the status
is now the single source of truth for the privacy gate, and a duplicate flag
could disagree with it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_contact_shared"
down_revision: Union[str, None] = "0006_vendor_response"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_KWARGS = {"timezone": True}

NEW_STATUSES = (
    "waiting_vendor_response",
    "vendor_accepted",
    "contact_shared",
    "completed",
    "vendor_rejected",
    "cancelled",
)

OLD_STATUSES = (
    "waiting_vendor_response",
    "vendor_accepted",
    "awaiting_user_confirmation",
    "confirmed",
    "vendor_rejected",
    "completed",
    "cancelled",
)


def _rebuild_enum(target: tuple[str, ...], mapping_sql: str) -> None:
    """Swap case_status for a new type with exactly ``target`` labels."""
    op.execute("ALTER TABLE consultation_cases ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "CREATE TYPE case_status_new AS ENUM ("
        + ", ".join(f"'{value}'" for value in target)
        + ")"
    )
    op.execute(
        "ALTER TABLE consultation_cases "
        "ALTER COLUMN status TYPE case_status_new "
        f"USING ({mapping_sql})::case_status_new"
    )
    op.execute("DROP TYPE case_status")
    op.execute("ALTER TYPE case_status_new RENAME TO case_status")
    op.execute(
        "ALTER TABLE consultation_cases "
        "ALTER COLUMN status SET DEFAULT 'waiting_vendor_response'"
    )


def upgrade() -> None:
    # No row uses the two labels being retired, but map them defensively so the
    # migration is safe to run against a database that somehow has them.
    _rebuild_enum(
        NEW_STATUSES,
        """
        CASE status::text
            WHEN 'confirmed' THEN 'contact_shared'
            WHEN 'awaiting_user_confirmation' THEN 'vendor_accepted'
            ELSE status::text
        END
        """,
    )

    op.add_column(
        "consultation_cases",
        sa.Column("confirmed_at", sa.DateTime(**TIMESTAMP_KWARGS), nullable=True),
    )
    op.add_column(
        "consultation_cases",
        sa.Column("completed_at", sa.DateTime(**TIMESTAMP_KWARGS), nullable=True),
    )

    # Backfill from the audit trail so existing rows keep a sensible timeline.
    op.execute(
        """
        UPDATE consultation_cases c
        SET completed_at = h.created_at
        FROM case_status_history h
        WHERE h.case_id = c.id
          AND h.to_status = 'completed'
          AND c.status = 'completed'
          AND c.completed_at IS NULL
        """
    )

    op.drop_column("consultation_cases", "contact_shared")


def downgrade() -> None:
    op.add_column(
        "consultation_cases",
        sa.Column(
            "contact_shared",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE consultation_cases SET contact_shared = true "
        "WHERE status::text IN ('contact_shared', 'completed')"
    )

    op.drop_column("consultation_cases", "completed_at")
    op.drop_column("consultation_cases", "confirmed_at")

    _rebuild_enum(
        OLD_STATUSES,
        """
        CASE status::text
            WHEN 'contact_shared' THEN 'confirmed'
            ELSE status::text
        END
        """,
    )
