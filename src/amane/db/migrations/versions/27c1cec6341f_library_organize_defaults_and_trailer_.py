"""library organize defaults and trailer pattern

Revision ID: 27c1cec6341f
Revises: e08b11d79fbb
Create Date: 2026-08-20 20:10:50.725981
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27c1cec6341f"
down_revision: str | None = "e08b11d79fbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.add_column(sa.Column("write_nfo", sa.Boolean(), nullable=False, server_default=sa.text("1")))
        batch_op.add_column(
            sa.Column(
                "copy_resources",
                sa.JSON(),
                nullable=False,
                server_default='["thumb","poster","extrafanart","trailer"]',
            )
        )
        batch_op.add_column(sa.Column("trailer_pattern", sa.String(), nullable=False, server_default="(?i)trailer"))


def downgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_column("trailer_pattern")
        batch_op.drop_column("copy_resources")
        batch_op.drop_column("write_nfo")
