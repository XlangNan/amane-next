"""library move_mode

Revision ID: 4a030237ec13
Revises: cf5ce9fc0b22
Create Date: 2026-08-15 12:14:39.489531
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a030237ec13"
down_revision: str | None = "cf5ce9fc0b22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.add_column(sa.Column("move_mode", sa.String(), nullable=False, server_default="move"))


def downgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_column("move_mode")
