"""feed group and item description

Revision ID: 765b775e77d9
Revises: 93228ccb7225
Create Date: 2026-08-18 00:35:31.153336
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "765b775e77d9"
down_revision: str | None = "93228ccb7225"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("feeds") as batch_op:
        batch_op.add_column(sa.Column("group", sa.String(), nullable=False, server_default=""))
    with op.batch_alter_table("feed_items") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("feed_items") as batch_op:
        batch_op.drop_column("description")
    with op.batch_alter_table("feeds") as batch_op:
        batch_op.drop_column("group")
