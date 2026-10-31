"""normalize metadata raw media url keys

Revision ID: c4f17334c3ea
Revises: 6d6ec00ff658
Create Date: 2026-08-07 02:08:00.000000

将 Metadata.raw 中遗留的单数字段 poster_url / thumb_url / trailer_url
规范为列表字段 poster_urls / thumb_urls / trailer_urls.
列上的同名结果字段已随 schema 迁移; raw JSON 快照未同步, 需在此单独修正.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f17334c3ea"
down_revision: str | None = "6d6ec00ff658"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SINGULAR_TO_LIST: tuple[tuple[str, str], ...] = (
    ("poster_url", "poster_urls"),
    ("thumb_url", "thumb_urls"),
    ("trailer_url", "trailer_urls"),
)


def _as_url_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _normalize_site(site: dict[str, Any]) -> bool:
    """就地改写单个站点 dump. 返回是否有改动."""
    changed = False
    for old_key, new_key in _SINGULAR_TO_LIST:
        if old_key not in site:
            continue
        old_val = site.pop(old_key)
        changed = True
        existing = site.get(new_key)
        if isinstance(existing, list) and existing:
            continue
        site[new_key] = _as_url_list(old_val)
    return changed


def _denormalize_site(site: dict[str, Any]) -> bool:
    """upgrade 的逆: list → 首元素标量 (空 → null)."""
    changed = False
    for old_key, new_key in _SINGULAR_TO_LIST:
        if new_key not in site:
            continue
        new_val = site.pop(new_key)
        changed = True
        urls = _as_url_list(new_val)
        site[old_key] = urls[0] if urls else None
    return changed


def _rewrite_raw(raw: Any, *, forward: bool) -> str | None:
    """解析 raw JSON, 按方向改写. 无改动返回 None (跳过写回)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        data = raw
    else:
        return None
    if not isinstance(data, dict):
        return None

    changed = False
    for site_key, site in list(data.items()):
        if not isinstance(site, dict):
            continue
        site_copy = dict(site)
        if forward:
            if _normalize_site(site_copy):
                data[site_key] = site_copy
                changed = True
        elif _denormalize_site(site_copy):
            data[site_key] = site_copy
            changed = True

    if not changed:
        return None
    return json.dumps(data, ensure_ascii=False)


def _migrate(*, forward: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, raw FROM metadata")).fetchall()
    for row in rows:
        meta_id = row[0]
        rewritten = _rewrite_raw(row[1], forward=forward)
        if rewritten is None:
            continue
        conn.execute(
            sa.text("UPDATE metadata SET raw = :raw WHERE id = :id"),
            {"raw": rewritten, "id": meta_id},
        )


def upgrade() -> None:
    _migrate(forward=True)


def downgrade() -> None:
    _migrate(forward=False)
