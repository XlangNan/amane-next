"""feed item published_at

Revision ID: e08b11d79fbb
Revises: 765b775e77d9
Create Date: 2026-08-18 03:05:04.606480
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e08b11d79fbb"
down_revision: str | None = "765b775e77d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("feed_items") as batch_op:
        batch_op.add_column(sa.Column("published_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("feed_items") as batch_op:
        batch_op.drop_column("published_at")
