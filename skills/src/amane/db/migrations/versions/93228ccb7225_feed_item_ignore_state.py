"""feed item ignore state

Revision ID: 93228ccb7225
Revises: a0271ff198e5
Create Date: 2026-08-17 12:32:44.863326
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "93228ccb7225"
down_revision: str | None = "a0271ff198e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("feed_items") as batch_op:
        batch_op.add_column(sa.Column("ignored_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("feed_items") as batch_op:
        batch_op.drop_column("ignored_at")
