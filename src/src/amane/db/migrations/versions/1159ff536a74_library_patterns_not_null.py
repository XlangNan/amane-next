"""library patterns not null

Revision ID: 1159ff536a74
Revises: 27c1cec6341f
Create Date: 2026-08-20 22:55:45.944197
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1159ff536a74"
down_revision: str | None = "27c1cec6341f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE libraries SET patterns = '[]' WHERE patterns IS NULL OR patterns = 'null'"))
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.alter_column("patterns", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.alter_column("patterns", existing_type=sa.JSON(), nullable=True)
