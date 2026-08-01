"""initial core schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_KWARGS = {"timezone": True}


def upgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
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
    )
    op.create_index(
        "ix_service_categories_code", "service_categories", ["code"], unique=True
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "role",
            sa.Enum("consumer", "vendor", "admin", name="user_role"),
            server_default="consumer",
            nullable=False,
        ),
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
    )

    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "rating", sa.Numeric(precision=2, scale=1), server_default="0", nullable=False
        ),
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
            ["user_id"], ["users.id"], name="fk_vendors_user_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_vendors_user_id", "vendors", ["user_id"], unique=True)

    op.create_table(
        "service_forms",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("schema_definition", postgresql.JSONB(), nullable=False),
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
            ["category_id"],
            ["service_categories.id"],
            name="fk_service_forms_category_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_service_forms_category_id", "service_forms", ["category_id"], unique=False
    )

    op.create_table(
        "life_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("raw_input", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "needs_info",
                "ready",
                "matching",
                "completed",
                "cancelled",
                name="task_status",
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "parsed_data",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "missing_fields",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
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
            ["user_id"], ["users.id"], name="fk_life_tasks_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["service_categories.id"],
            name="fk_life_tasks_category_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_life_tasks_user_id", "life_tasks", ["user_id"], unique=False)
    op.create_index(
        "ix_life_tasks_category_id", "life_tasks", ["category_id"], unique=False
    )
    op.create_index("ix_life_tasks_status", "life_tasks", ["status"], unique=False)

    op.create_table(
        "consultation_cases",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "declined",
                "completed",
                "cancelled",
                name="case_status",
            ),
            server_default="pending",
            nullable=False,
        ),
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
            ["task_id"],
            ["life_tasks.id"],
            name="fk_consultation_cases_task_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name="fk_consultation_cases_vendor_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("task_id", "vendor_id", name="uq_consultation_task_vendor"),
    )
    op.create_index(
        "ix_consultation_cases_task_id", "consultation_cases", ["task_id"], unique=False
    )
    op.create_index(
        "ix_consultation_cases_vendor_id",
        "consultation_cases",
        ["vendor_id"],
        unique=False,
    )
    op.create_index(
        "ix_consultation_cases_status", "consultation_cases", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_consultation_cases_status", table_name="consultation_cases")
    op.drop_index("ix_consultation_cases_vendor_id", table_name="consultation_cases")
    op.drop_index("ix_consultation_cases_task_id", table_name="consultation_cases")
    op.drop_table("consultation_cases")

    op.drop_index("ix_life_tasks_status", table_name="life_tasks")
    op.drop_index("ix_life_tasks_category_id", table_name="life_tasks")
    op.drop_index("ix_life_tasks_user_id", table_name="life_tasks")
    op.drop_table("life_tasks")

    op.drop_index("ix_service_forms_category_id", table_name="service_forms")
    op.drop_table("service_forms")

    op.drop_index("ix_vendors_user_id", table_name="vendors")
    op.drop_table("vendors")

    op.drop_table("users")

    op.drop_index("ix_service_categories_code", table_name="service_categories")
    op.drop_table("service_categories")

    # Enum types are not removed automatically.
    bind = op.get_bind()
    for enum_name in ("case_status", "task_status", "user_role"):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
