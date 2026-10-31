"""actor source_urls dict

Revision ID: d1cb1a39c9ff
Revises: eabbb93e03b4
Create Date: 2026-08-09 10:49:07.885114
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "d1cb1a39c9ff"
down_revision: str | None = "eabbb93e03b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _parse_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _build_source_urls(
    *,
    source_url: str | None,
    field_sources: dict[str, Any],
    raw: dict[str, Any],
) -> dict[str, str]:
    """按站点聚合 source URL: 优先 raw 内嵌的 source_url, 未命中再回退独立列
    source_url (站点名取 field_sources, 未知时用 "unknown"), 缺键才填补."""
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for site, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            url = payload.get("source_url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                out.setdefault(str(site), url)
    if source_url and source_url.startswith(("http://", "https://")):
        site = field_sources.get("source_url") if isinstance(field_sources, dict) else None
        key = site if isinstance(site, str) and site else "unknown"
        out.setdefault(key, source_url)
    return out


def upgrade() -> None:
    with op.batch_alter_table("actors") as batch_op:
        batch_op.add_column(sa.Column("source_urls", sa.JSON(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, source_url, field_sources, raw FROM actors")).mappings()
    for row in rows:
        urls = _build_source_urls(
            source_url=row["source_url"],
            field_sources=_parse_json(row["field_sources"], {}),
            raw=_parse_json(row["raw"], {}),
        )
        conn.execute(
            sa.text("UPDATE actors SET source_urls = :urls WHERE id = :id"),
            {"urls": json.dumps(urls, ensure_ascii=False), "id": row["id"]},
        )

    with op.batch_alter_table("actors") as batch_op:
        batch_op.drop_column("source_url")


def downgrade() -> None:
    with op.batch_alter_table("actors") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, source_urls, field_sources FROM actors")).mappings()
    for row in rows:
        urls = _parse_json(row["source_urls"], {})
        field_sources = _parse_json(row["field_sources"], {})
        preferred = field_sources.get("source_url") if isinstance(field_sources, dict) else None
        source_url: str | None = None
        if isinstance(urls, dict) and urls:
            if isinstance(preferred, str) and preferred in urls:
                source_url = urls[preferred]
            else:
                source_url = next(iter(urls.values()), None)
        conn.execute(
            sa.text("UPDATE actors SET source_url = :url WHERE id = :id"),
            {"url": source_url, "id": row["id"]},
        )

    with op.batch_alter_table("actors") as batch_op:
        batch_op.drop_column("source_urls")
