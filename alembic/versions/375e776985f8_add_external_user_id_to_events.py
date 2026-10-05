"""add external user id to events

Revision ID: 375e776985f8
Revises: 881b34673bca
Create Date: 2026-10-05 10:23:36.200504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '375e776985f8'
down_revision: Union[str, Sequence[str], None] = '881b34673bca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "external_user_id",
            sa.String(),
            nullable=True,
        )
    )


def downgrade() -> None:
    op.drop_column("events", "external_user_id")
