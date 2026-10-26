"""actor gender column

Revision ID: 53476adaa9cd
Revises: d1cb1a39c9ff
Create Date: 2026-08-09 11:23:40.288428
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "53476adaa9cd"
down_revision: str | None = "d1cb1a39c9ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("actors") as batch_op:
        batch_op.add_column(sa.Column("gender", sa.String(), nullable=False, server_default="unknown"))
        batch_op.create_index("ix_actors_gender", ["gender"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("actors") as batch_op:
        batch_op.drop_index("ix_actors_gender")
        batch_op.drop_column("gender")
