"""seed the four MVP service categories

Revision ID: 0002_seed_categories
Revises: 0001_initial_schema
Create Date: 2026-08-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_seed_categories"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORIES = [
    ("plumbing", "水電維修"),
    ("cleaning", "居家清潔"),
    ("dining", "餐飲訂購"),
    ("shopping", "代購採買"),
]


def upgrade() -> None:
    service_categories = sa.table(
        "service_categories",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        service_categories,
        [{"code": code, "name": name} for code, name in CATEGORIES],
    )


def downgrade() -> None:
    codes = tuple(code for code, _ in CATEGORIES)
    op.execute(
        sa.text("DELETE FROM service_categories WHERE code IN :codes").bindparams(
            sa.bindparam("codes", value=codes, expanding=True)
        )
    )
