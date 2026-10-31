"""add facet_rules

Revision ID: 9777268db95b
Revises: b058160ffee4
Create Date: 2026-08-08 14:35:35.257157
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9777268db95b"
down_revision: str | None = "b058160ffee4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facet_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "source_name", name="uq_facet_rules_kind_source"),
    )
    op.create_index(op.f("ix_facet_rules_kind"), "facet_rules", ["kind"], unique=False)
    op.create_index(op.f("ix_facet_rules_source_name"), "facet_rules", ["source_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_facet_rules_source_name"), table_name="facet_rules")
    op.drop_index(op.f("ix_facet_rules_kind"), table_name="facet_rules")
    op.drop_table("facet_rules")
