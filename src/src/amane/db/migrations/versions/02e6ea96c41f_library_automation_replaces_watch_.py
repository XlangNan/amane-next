"""library automation replaces watch_enabled

Revision ID: 02e6ea96c41f
Revises: 1159ff536a74
Create Date: 2026-08-21 00:26:27.118195
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02e6ea96c41f"
down_revision: str | None = "1159ff536a74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.add_column(sa.Column("automation", sa.String(), nullable=False, server_default="scrape"))
    op.execute(sa.text("UPDATE libraries SET automation = 'none' WHERE watch_enabled = 0"))
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_column("watch_enabled")


def downgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.add_column(sa.Column("watch_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.execute(sa.text("UPDATE libraries SET watch_enabled = 0 WHERE automation = 'none'"))
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_column("automation")
