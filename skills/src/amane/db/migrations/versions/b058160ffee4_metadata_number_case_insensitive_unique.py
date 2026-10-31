"""metadata number case insensitive unique

Revision ID: b058160ffee4
Revises: c4f17334c3ea
Create Date: 2026-08-08 09:09:09.201000

将 Metadata.number 唯一索引改为 COLLATE NOCASE.
查重忽略大小写, 存库仍保留首次写入的原始大小写.
升级前合并仅大小写不同的重复行 (保留最小 id).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b058160ffee4"
down_revision: str | None = "c4f17334c3ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINK_TABLES: tuple[tuple[str, str], ...] = (
    ("metadata_actors", "actor_id"),
    ("metadata_directors", "director_id"),
    ("metadata_tags", "tag_id"),
    ("metadata_user_tags", "user_tag_id"),
)


def _merge_case_duplicate_numbers(bind: sa.Connection) -> None:
    """仅大小写不同的 number 合并到最小 id 行, 再删重复行."""
    rows = bind.execute(sa.text("SELECT id, number FROM metadata ORDER BY id")).fetchall()
    groups: dict[str, list[int]] = defaultdict(list)
    for metadata_id, number in rows:
        groups[str(number).lower()].append(int(metadata_id))

    for ids in groups.values():
        if len(ids) < 2:
            continue
        keeper_id = ids[0]
        for dup_id in ids[1:]:
            bind.execute(
                sa.text("UPDATE media_files SET metadata_id = :keeper WHERE metadata_id = :dup"),
                {"keeper": keeper_id, "dup": dup_id},
            )
            for table, fk in _LINK_TABLES:
                bind.execute(
                    sa.text(
                        f"DELETE FROM {table} WHERE metadata_id = :dup AND {fk} IN "
                        f"(SELECT {fk} FROM {table} WHERE metadata_id = :keeper)"
                    ),
                    {"dup": dup_id, "keeper": keeper_id},
                )
                bind.execute(
                    sa.text(f"UPDATE {table} SET metadata_id = :keeper WHERE metadata_id = :dup"),
                    {"keeper": keeper_id, "dup": dup_id},
                )
            bind.execute(
                sa.text("UPDATE comments SET metadata_id = :keeper WHERE metadata_id = :dup"),
                {"keeper": keeper_id, "dup": dup_id},
            )
            bind.execute(sa.text("DELETE FROM metadata WHERE id = :dup"), {"dup": dup_id})


def upgrade() -> None:
    bind = op.get_bind()
    _merge_case_duplicate_numbers(bind)

    op.drop_index("ix_metadata_number", table_name="metadata")
    op.execute(sa.text("CREATE UNIQUE INDEX ix_metadata_number ON metadata (number COLLATE NOCASE)"))


def downgrade() -> None:
    op.drop_index("ix_metadata_number", table_name="metadata")
    op.create_index("ix_metadata_number", "metadata", ["number"], unique=True)
