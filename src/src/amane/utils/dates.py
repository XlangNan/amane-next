"""日历日期规范化 - 影片 release / 演员 birthday 等存库统一为 YYYY-MM-DD."""

from __future__ import annotations

import calendar
import re
import unicodedata

# 已是规范格式, ISO 日期时间 (取日部分), 常见分隔 / 日文年月日.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 2020-01-01 / 2020-01-01T12:00:00Z / 2020-01-01 12:00:00+09:00
    re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?:[Tt\s].*)?$"),
    re.compile(r"^(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})$"),
    re.compile(r"(?P<y>\d{4})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"),
)


def normalize_calendar_date(value: str | None) -> str | None:
    """将多种日历写法规范为 ``YYYY-MM-DD``; 空串/无法解析返回 None.

    含 ISO-8601 日期时间 (``...T...`` / 空格分隔时分秒): 只保留日历日, 不保留时刻与时区.
    Wikidata 时间串前导 ``+`` 会先剥掉再解析.
    """
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", value).strip()
    if not text:
        return None
    if text.startswith("+"):
        text = text[1:].lstrip()
    for pat in _PATTERNS:
        m = pat.fullmatch(text) if pat.pattern.startswith("^") else pat.search(text)
        if not m:
            continue
        year, month, day = int(m.group("y")), int(m.group("m")), int(m.group("d"))
        if not _valid_ymd(year, month, day):
            return None
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _valid_ymd(year: int, month: int, day: int) -> bool:
    if year < 1 or year > 9999 or month < 1 or month > 12 or day < 1:
        return False
    return day <= calendar.monthrange(year, month)[1]
