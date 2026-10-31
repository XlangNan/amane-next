"""actor person metadata fields

Revision ID: eabbb93e03b4
Revises: 9777268db95b
Create Date: 2026-08-09 09:24:15.563650
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "eabbb93e03b4"
down_revision: str | None = "9777268db95b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("actors") as batch_op:
        batch_op.add_column(sa.Column("aliases", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("birthday", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("birthplace", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("height", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bust", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("waist", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("hip", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cup", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("overview", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tagline", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("image_urls", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("provider_ids", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("source_url", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("field_sources", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("raw", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("actors") as batch_op:
        batch_op.drop_column("raw")
        batch_op.drop_column("field_sources")
        batch_op.drop_column("source_url")
        batch_op.drop_column("provider_ids")
        batch_op.drop_column("image_urls")
        batch_op.drop_column("tagline")
        batch_op.drop_column("overview")
        batch_op.drop_column("cup")
        batch_op.drop_column("hip")
        batch_op.drop_column("waist")
        batch_op.drop_column("bust")
        batch_op.drop_column("height")
        batch_op.drop_column("birthplace")
        batch_op.drop_column("birthday")
        batch_op.drop_column("aliases")
