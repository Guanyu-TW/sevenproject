"""vendor response fields and vendor_rejected status

Revision ID: 0006_vendor_response
Revises: 0005_consultation_cases
Create Date: 2026-08-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_vendor_response"
down_revision: Union[str, None] = "0005_consultation_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_KWARGS = {"timezone": True}


def upgrade() -> None:
    # Align with the vocabulary used by the vendor portal spec. No row uses the
    # old label, so a rename is safe.
    op.execute(
        "ALTER TYPE case_status RENAME VALUE 'vendor_declined' TO 'vendor_rejected'"
    )

    op.add_column("consultation_cases", sa.Column("vendor_note", sa.Text(), nullable=True))
    op.add_column(
        "consultation_cases",
        sa.Column("proposed_time", sa.DateTime(**TIMESTAMP_KWARGS), nullable=True),
    )
    op.add_column(
        "consultation_cases",
        sa.Column("responded_at", sa.DateTime(**TIMESTAMP_KWARGS), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consultation_cases", "responded_at")
    op.drop_column("consultation_cases", "proposed_time")
    op.drop_column("consultation_cases", "vendor_note")

    op.execute(
        "ALTER TYPE case_status RENAME VALUE 'vendor_rejected' TO 'vendor_declined'"
    )
