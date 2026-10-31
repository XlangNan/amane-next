"""facet indexes, comments, user tags

Revision ID: 6d6ec00ff658
Revises: 3a0088a88ce7
Create Date: 2026-08-05 22:32:39.743165
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d6ec00ff658"
down_revision: str | None = "3a0088a88ce7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table) if idx["name"]}


def upgrade() -> None:
    # SQLite DDL 常在失败后留下半成品表; 用 inspect 做幂等, 便于重跑.
    existing = _table_names()

    for table_name in ("actors", "directors", "tags", "studios", "publishers", "series", "user_tags"):
        if table_name not in existing:
            op.create_table(
                table_name,
                sa.Column("id", sa.Integer(), nullable=False),
                sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
                sa.Column("created_at", sa.DateTime(), nullable=False),
                sa.Column("updated_at", sa.DateTime(), nullable=False),
                sa.PrimaryKeyConstraint("id"),
            )
        idx_name = op.f(f"ix_{table_name}_name")
        if idx_name not in _index_names(table_name):
            op.create_index(idx_name, table_name, ["name"], unique=True)

    existing = _table_names()
    if "metadata_actors" not in existing:
        op.create_table(
            "metadata_actors",
            sa.Column("metadata_id", sa.Integer(), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["actor_id"], ["actors.id"]),
            sa.ForeignKeyConstraint(["metadata_id"], ["metadata.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("metadata_id", "actor_id"),
        )
    if "metadata_directors" not in existing:
        op.create_table(
            "metadata_directors",
            sa.Column("metadata_id", sa.Integer(), nullable=False),
            sa.Column("director_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["director_id"], ["directors.id"]),
            sa.ForeignKeyConstraint(["metadata_id"], ["metadata.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("metadata_id", "director_id"),
        )
    if "metadata_tags" not in existing:
        op.create_table(
            "metadata_tags",
            sa.Column("metadata_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]),
            sa.ForeignKeyConstraint(["metadata_id"], ["metadata.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("metadata_id", "tag_id"),
        )
    if "metadata_user_tags" not in existing:
        op.create_table(
            "metadata_user_tags",
            sa.Column("metadata_id", sa.Integer(), nullable=False),
            sa.Column("user_tag_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["metadata_id"], ["metadata.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_tag_id"], ["user_tags.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("metadata_id", "user_tag_id"),
        )
    if "comments" not in existing:
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("metadata_id", sa.Integer(), nullable=False),
            sa.Column("body", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["metadata_id"], ["metadata.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if op.f("ix_comments_metadata_id") not in _index_names("comments"):
        op.create_index(op.f("ix_comments_metadata_id"), "comments", ["metadata_id"], unique=False)

    meta_indexes = _index_names("metadata")
    need_studio = "ix_metadata_studio" not in meta_indexes
    need_publisher = "ix_metadata_publisher" not in meta_indexes
    need_series = "ix_metadata_series" not in meta_indexes
    if need_studio or need_publisher or need_series:
        with op.batch_alter_table("metadata", schema=None) as batch_op:
            if need_studio:
                batch_op.create_index(batch_op.f("ix_metadata_studio"), ["studio"], unique=False)
            if need_publisher:
                batch_op.create_index(batch_op.f("ix_metadata_publisher"), ["publisher"], unique=False)
            if need_series:
                batch_op.create_index(batch_op.f("ix_metadata_series"), ["series"], unique=False)

    _backfill_facets()


def _backfill_facets() -> None:
    """从现有 Metadata JSON/标量列重建分类投影. 已有关联行时跳过 (可重入)."""
    bind = op.get_bind()
    now = _utcnow()
    # 已回填过则跳过整段, 避免重复 INSERT 撞 PK
    existing_links = bind.execute(sa.text("SELECT COUNT(*) FROM metadata_actors")).scalar()
    if existing_links and int(existing_links) > 0:
        return

    rows = bind.execute(
        sa.text("SELECT id, actors, directors, tags, studio, publisher, series FROM metadata")
    ).fetchall()

    actor_ids: dict[str, int] = {}
    director_ids: dict[str, int] = {}
    tag_ids: dict[str, int] = {}
    studio_ids: dict[str, int] = {}
    publisher_ids: dict[str, int] = {}
    series_ids: dict[str, int] = {}

    def get_or_create(cache: dict[str, int], table: str, name: str) -> int:
        if name in cache:
            return cache[name]
        existing = bind.execute(sa.text(f"SELECT id FROM {table} WHERE name = :name"), {"name": name}).fetchone()
        if existing is not None:
            cache[name] = int(existing[0])
            return cache[name]
        result = bind.execute(
            sa.text(f"INSERT INTO {table} (name, created_at, updated_at) VALUES (:name, :created_at, :updated_at)"),
            {"name": name, "created_at": now, "updated_at": now},
        )
        entity_id = int(result.lastrowid)
        cache[name] = entity_id
        return entity_id

    for row in rows:
        metadata_id = int(row[0])
        for position, name in enumerate(_parse_list(row[1])):
            actor_id = get_or_create(actor_ids, "actors", name)
            bind.execute(
                sa.text(
                    "INSERT OR IGNORE INTO metadata_actors (metadata_id, actor_id, position) "
                    "VALUES (:metadata_id, :actor_id, :position)"
                ),
                {"metadata_id": metadata_id, "actor_id": actor_id, "position": position},
            )
        for position, name in enumerate(_parse_list(row[2])):
            director_id = get_or_create(director_ids, "directors", name)
            bind.execute(
                sa.text(
                    "INSERT OR IGNORE INTO metadata_directors (metadata_id, director_id, position) "
                    "VALUES (:metadata_id, :director_id, :position)"
                ),
                {"metadata_id": metadata_id, "director_id": director_id, "position": position},
            )
        for position, name in enumerate(_parse_list(row[3])):
            tag_id = get_or_create(tag_ids, "tags", name)
            bind.execute(
                sa.text(
                    "INSERT OR IGNORE INTO metadata_tags (metadata_id, tag_id, position) "
                    "VALUES (:metadata_id, :tag_id, :position)"
                ),
                {"metadata_id": metadata_id, "tag_id": tag_id, "position": position},
            )
        studio = row[4]
        if isinstance(studio, str) and studio:
            get_or_create(studio_ids, "studios", studio)
        publisher = row[5]
        if isinstance(publisher, str) and publisher:
            get_or_create(publisher_ids, "publishers", publisher)
        series_name = row[6]
        if isinstance(series_name, str) and series_name:
            get_or_create(series_ids, "series", series_name)


def downgrade() -> None:
    existing = _table_names()
    meta_indexes = _index_names("metadata") if "metadata" in existing else set()
    with op.batch_alter_table("metadata", schema=None) as batch_op:
        if batch_op.f("ix_metadata_series") in meta_indexes:
            batch_op.drop_index(batch_op.f("ix_metadata_series"))
        if batch_op.f("ix_metadata_publisher") in meta_indexes:
            batch_op.drop_index(batch_op.f("ix_metadata_publisher"))
        if batch_op.f("ix_metadata_studio") in meta_indexes:
            batch_op.drop_index(batch_op.f("ix_metadata_studio"))

    if "comments" in existing:
        if op.f("ix_comments_metadata_id") in _index_names("comments"):
            op.drop_index(op.f("ix_comments_metadata_id"), table_name="comments")
        op.drop_table("comments")
    for table_name in ("metadata_user_tags", "metadata_tags", "metadata_directors", "metadata_actors"):
        if table_name in existing:
            op.drop_table(table_name)
    for table_name in ("user_tags", "series", "publishers", "studios", "tags", "directors", "actors"):
        if table_name in existing:
            idx = op.f(f"ix_{table_name}_name")
            if idx in _index_names(table_name):
                op.drop_index(idx, table_name=table_name)
            op.drop_table(table_name)
