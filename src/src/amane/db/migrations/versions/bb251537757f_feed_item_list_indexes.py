"""feed item list indexes

Revision ID: bb251537757f
Revises: 02e6ea96c41f
Create Date: 2026-08-21 01:38:02.385187
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb251537757f"
down_revision: str | None = "02e6ea96c41f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_feed_items_ignored_at"), "feed_items", ["ignored_at"], unique=False)
    # 表达式索引: autogenerate 对 SQLite 无法反射, 须手补.
    op.execute(sa.text("CREATE INDEX ix_feed_items_list_order ON feed_items (coalesce(published_at, created_at), id)"))


def downgrade() -> None:
    op.drop_index("ix_feed_items_list_order", table_name="feed_items")
    op.drop_index(op.f("ix_feed_items_ignored_at"), table_name="feed_items")
