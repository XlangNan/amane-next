"""RSS/Atom 字节 → 条目. 调用方负责 HTTP; 禁止把 URL 交给 feedparser."""

from calendar import timegm
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time

import feedparser


@dataclass(frozen=True)
class ParsedFeedEntry:
    item_key: str
    title: str
    link: str | None
    description: str | None
    published_at: datetime | None = None


@dataclass(frozen=True)
class ParsedFeed:
    title: str | None
    entries: list[ParsedFeedEntry]


def _entry_text(entry: feedparser.FeedParserDict, *keys: str) -> str | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _mapping_text(block: object, key: str) -> str | None:
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _entry_body(entry: feedparser.FeedParserDict) -> str | None:
    """优先 Atom/RSS content, 再 summary/description. 原样保留 HTML."""
    content = entry.get("content")
    if isinstance(content, list):
        for block in content:
            value = _mapping_text(block, "value")
            if value is not None:
                return value
    detail_value = _mapping_text(entry.get("summary_detail"), "value")
    if detail_value is not None:
        return detail_value
    return _entry_text(entry, "summary", "description")


def _struct_to_utc(value: object) -> datetime | None:
    if not isinstance(value, struct_time):
        return None
    try:
        return datetime.fromtimestamp(timegm(value), tz=UTC)
    except OverflowError, OSError, ValueError:
        return None


def _entry_published_at(entry: feedparser.FeedParserDict) -> datetime | None:
    """RSS pubDate / Atom published, 没有再用 updated. feedparser 已把二者解析成 UTC struct_time.

    ``updated_parsed`` 必须使用 ``dict.get``: FeedParserDict 在缺该键时会映射到
    ``published_parsed``, 触发 DeprecationWarning 且将被移除.
    """
    return _struct_to_utc(entry.get("published_parsed")) or _struct_to_utc(dict.get(entry, "updated_parsed"))


def parse_feed_bytes(body: bytes) -> ParsedFeed | None:
    """解析 RSS/Atom. 无法得到任何条目且标记为损坏时返回 None."""
    if not body.strip():
        return None
    parsed = feedparser.parse(body)
    title = _entry_text(parsed.feed, "title")
    entries = parsed.entries
    if not entries:
        return None if parsed.bozo else ParsedFeed(title=title, entries=[])

    result: list[ParsedFeedEntry] = []
    for entry in entries:
        entry_title = _entry_text(entry, "title") or ""
        link = _entry_text(entry, "link")
        description = _entry_body(entry)
        item_key = _entry_text(entry, "id", "guid") or link or entry_title
        if not item_key:
            continue
        result.append(
            ParsedFeedEntry(
                item_key=item_key,
                title=entry_title,
                link=link,
                description=description,
                published_at=_entry_published_at(entry),
            )
        )
    return ParsedFeed(title=title, entries=result)
