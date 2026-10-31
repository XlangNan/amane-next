"""normalize_calendar_date 表测试."""

from __future__ import annotations

import pytest

from amane.utils.dates import normalize_calendar_date

CASES: list[tuple[str | None, str | None]] = [
    (None, None),
    ("", None),
    ("   ", None),
    ("1994-08-26", "1994-08-26"),
    ("1994/8/26", "1994-08-26"),
    ("1994.08.26", "1994-08-26"),
    ("1994年8月26日", "1994-08-26"),
    ("生年月日：1994年8月26日（満）", "1994-08-26"),
    ("1994-08-26T00:00:00Z", "1994-08-26"),
    ("1994-08-26T12:34:56+09:00", "1994-08-26"),
    ("1994-08-26 00:00:00", "1994-08-26"),
    ("+1994-08-26T00:00:00Z", "1994-08-26"),
    ("1994-13-01", None),
    ("1994-02-30", None),
    ("not-a-date", None),
    ("2024-02-29", "2024-02-29"),
    ("2023-02-29", None),
]


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize_calendar_date(raw: str | None, expected: str | None) -> None:
    assert normalize_calendar_date(raw) == expected
