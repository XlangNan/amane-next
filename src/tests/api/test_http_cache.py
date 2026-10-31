"""http_cache: ETag 匹配与 304 辅助."""

import pytest

from amane.api.support.http_cache import etag_matches, format_etag


@pytest.mark.parametrize(
    ("if_none_match", "content_hash", "expected", "desc"),
    [
        (None, "abc", False, "无头"),
        ("", "abc", False, "空头"),
        ('"abc"', "abc", True, "精确强 ETag"),
        ("abc", "abc", False, "无引号不匹配"),
        ('"xyz"', "abc", False, "不同哈希"),
        ('"xyz", "abc"', "abc", True, "列表命中其一"),
        ('W/"abc"', "abc", True, "弱 ETag 按值比"),
        ("*", "abc", True, "星号任意"),
        ('"abc"', "", False, "空 hash"),
    ],
)
def test_etag_matches(
    if_none_match: str | None,
    content_hash: str,
    expected: bool,
    desc: str,
):
    assert etag_matches(if_none_match, content_hash) is expected, desc


def test_format_etag():
    assert format_etag("deadbeef") == '"deadbeef"'
