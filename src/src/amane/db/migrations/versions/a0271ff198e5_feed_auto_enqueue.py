"""feed auto_enqueue

Revision ID: a0271ff198e5
Revises: e6bb72730558
Create Date: 2026-08-17 00:03:37.918040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0271ff198e5"
down_revision: str | None = "e6bb72730558"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("feeds") as batch_op:
        batch_op.add_column(sa.Column("auto_enqueue", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("feeds") as batch_op:
        batch_op.drop_column("auto_enqueue")
