"""library cd suffix template

Revision ID: 5abbb79b1ae6
Revises: 6d548c449081
Create Date: 2026-08-23 02:22:35.975414
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5abbb79b1ae6"
down_revision: str | None = "6d548c449081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "libraries",
        sa.Column("cd_suffix_template", sa.String(), server_default="-CD{cd}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("libraries", "cd_suffix_template")
