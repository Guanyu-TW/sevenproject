"""vendor matching fields, category link table, ready_for_matching status

Revision ID: 0003_vendor_matching
Revises: 0002_seed_categories
Create Date: 2026-08-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_vendor_matching"
down_revision: Union[str, None] = "0002_seed_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_KWARGS = {"timezone": True}


def upgrade() -> None:
    # 'ready' was never used by any row, so a rename is safe and keeps the
    # single source of truth in sync with TaskStatus.READY_FOR_MATCHING.
    op.execute("ALTER TYPE task_status RENAME VALUE 'ready' TO 'ready_for_matching'")

    op.add_column("vendors", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "vendors", sa.Column("service_city", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "vendors",
        sa.Column(
            "service_districts",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("vendors", sa.Column("price_min", sa.Integer(), nullable=True))
    op.add_column("vendors", sa.Column("price_max", sa.Integer(), nullable=True))
    op.add_column(
        "vendors",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_index("ix_vendors_service_city", "vendors", ["service_city"])
    op.create_index("ix_vendors_is_active", "vendors", ["is_active"])

    op.create_table(
        "vendor_service_categories",
        sa.Column("vendor_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("category_id", sa.Integer(), primary_key=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name="fk_vendor_service_categories_vendor_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["service_categories.id"],
            name="fk_vendor_service_categories_category_id",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("vendor_service_categories")

    op.drop_index("ix_vendors_is_active", table_name="vendors")
    op.drop_index("ix_vendors_service_city", table_name="vendors")
    op.drop_column("vendors", "is_active")
    op.drop_column("vendors", "price_max")
    op.drop_column("vendors", "price_min")
    op.drop_column("vendors", "service_districts")
    op.drop_column("vendors", "service_city")
    op.drop_column("vendors", "description")

    op.execute(
        "UPDATE life_tasks SET status = 'draft' WHERE status = 'ready_for_matching'"
    )
    op.execute("ALTER TYPE task_status RENAME VALUE 'ready_for_matching' TO 'ready'")
