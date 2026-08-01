"""case numbers, snapshots, status history, task next_action

Revision ID: 0005_consultation_cases
Revises: 0004_seed_vendors
Create Date: 2026-08-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_consultation_cases"
down_revision: Union[str, None] = "0004_seed_vendors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_KWARGS = {"timezone": True}

OLD_CASE_STATUSES = ("pending", "accepted", "declined", "completed", "cancelled")
NEW_CASE_STATUSES = (
    "waiting_vendor_response",
    "vendor_accepted",
    "awaiting_user_confirmation",
    "confirmed",
    "vendor_declined",
    "completed",
    "cancelled",
)


def upgrade() -> None:
    # --- rename the three labels that map 1:1 onto the new vocabulary ----- #
    op.execute(
        "ALTER TYPE case_status RENAME VALUE 'pending' TO 'waiting_vendor_response'"
    )
    op.execute("ALTER TYPE case_status RENAME VALUE 'accepted' TO 'vendor_accepted'")
    op.execute("ALTER TYPE case_status RENAME VALUE 'declined' TO 'vendor_declined'")
    op.execute(
        "ALTER TABLE consultation_cases "
        "ALTER COLUMN status SET DEFAULT 'waiting_vendor_response'"
    )

    # --- consultation_cases new columns ---------------------------------- #
    op.add_column(
        "consultation_cases", sa.Column("case_number", sa.String(length=32), nullable=True)
    )
    op.execute(
        "UPDATE consultation_cases "
        "SET case_number = 'CASE-LEGACY-' || lpad(id::text, 4, '0') "
        "WHERE case_number IS NULL"
    )
    op.alter_column("consultation_cases", "case_number", nullable=False)
    op.create_index(
        "ix_consultation_cases_case_number",
        "consultation_cases",
        ["case_number"],
        unique=True,
    )

    op.add_column(
        "consultation_cases", sa.Column("estimated_price", sa.Integer(), nullable=True)
    )
    op.add_column(
        "consultation_cases", sa.Column("recommendation_reason", sa.Text(), nullable=True)
    )
    op.add_column(
        "consultation_cases",
        sa.Column(
            "form_data",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("consultation_cases", sa.Column("next_action", sa.Text(), nullable=True))
    op.add_column(
        "consultation_cases", sa.Column("blocked_reason", sa.Text(), nullable=True)
    )
    op.add_column(
        "consultation_cases",
        sa.Column(
            "contact_shared",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # --- life_tasks.next_action ------------------------------------------ #
    op.add_column("life_tasks", sa.Column("next_action", sa.Text(), nullable=True))

    # --- case_status_history --------------------------------------------- #
    op.create_table(
        "case_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column(
            "actor",
            sa.String(length=20),
            server_default="system",
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(**TIMESTAMP_KWARGS),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(**TIMESTAMP_KWARGS),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["consultation_cases.id"],
            name="fk_case_status_history_case_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_case_status_history_case_id", "case_status_history", ["case_id"]
    )

    # --- brand new labels, added last -------------------------------------- #
    # PostgreSQL 12+ allows ADD VALUE inside a transaction as long as the new
    # label is not used before the transaction commits, so nothing below may
    # reference these two.
    op.execute(
        "ALTER TYPE case_status ADD VALUE IF NOT EXISTS "
        "'awaiting_user_confirmation' AFTER 'vendor_accepted'"
    )
    op.execute(
        "ALTER TYPE case_status ADD VALUE IF NOT EXISTS "
        "'confirmed' AFTER 'awaiting_user_confirmation'"
    )


def downgrade() -> None:
    op.drop_index("ix_case_status_history_case_id", table_name="case_status_history")
    op.drop_table("case_status_history")

    op.drop_column("life_tasks", "next_action")

    op.drop_column("consultation_cases", "contact_shared")
    op.drop_column("consultation_cases", "blocked_reason")
    op.drop_column("consultation_cases", "next_action")
    op.drop_column("consultation_cases", "form_data")
    op.drop_column("consultation_cases", "recommendation_reason")
    op.drop_column("consultation_cases", "estimated_price")
    op.drop_index(
        "ix_consultation_cases_case_number", table_name="consultation_cases"
    )
    op.drop_column("consultation_cases", "case_number")

    # PostgreSQL cannot drop an enum label, so rebuild the type from scratch.
    op.execute(
        "UPDATE consultation_cases SET status = 'waiting_vendor_response' "
        "WHERE status IN ('awaiting_user_confirmation', 'confirmed')"
    )
    op.execute("ALTER TABLE consultation_cases ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "CREATE TYPE case_status_old AS ENUM ("
        + ", ".join(f"'{value}'" for value in OLD_CASE_STATUSES)
        + ")"
    )
    op.execute(
        """
        ALTER TABLE consultation_cases
        ALTER COLUMN status TYPE case_status_old
        USING (
            CASE status::text
                WHEN 'waiting_vendor_response' THEN 'pending'
                WHEN 'vendor_accepted' THEN 'accepted'
                WHEN 'vendor_declined' THEN 'declined'
                ELSE status::text
            END
        )::case_status_old
        """
    )
    op.execute("DROP TYPE case_status")
    op.execute("ALTER TYPE case_status_old RENAME TO case_status")
    op.execute(
        "ALTER TABLE consultation_cases ALTER COLUMN status SET DEFAULT 'pending'"
    )
