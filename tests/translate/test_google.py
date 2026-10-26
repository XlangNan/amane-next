from typing import Any

import pytest

from amane.enums import Language
from amane.translate.google import GoogleTranslator, parse_response, split_text


class FakeWeb:
    def __init__(self, reply: Any = None, *, fail: bool = False) -> None:
        self.reply = reply
        self.fail = fail
        self.urls: list[str] = []

    async def get_json(self, url: str) -> Any:
        self.urls.append(url)
        if self.fail:
            raise RuntimeError("blocked")
        return self.reply


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([[["你好", "Hello", None, None, 1], ["世界", " world", None, None, 1]], None, "en"], "你好世界"),
        ([[]], None),
        ([], None),
        ({"a": 1}, None),
        (None, None),
        ([[["x"]]], "x"),
        ([[[None, "y"]]], None),
    ],
)
def test_parse_response(raw: Any, expected: str | None) -> None:
    assert parse_response(raw) == expected


@pytest.mark.parametrize("text", ["short", "a。" * 1000, "x" * 4000, "第一行\n" * 700])
def test_split_text_roundtrip_and_limit(text: str) -> None:
    chunks = split_text(text, 1500)
    assert "".join(chunks) == text
    assert all(len(c) <= 1500 for c in chunks)


@pytest.mark.parametrize(
    ("text", "target", "called", "expected"),
    [
        ("Hello world", Language.ZH_CN, True, "你好"),
        ("こんにちは", Language.ZH_CN, True, "你好"),
        ("你好世界", Language.ZH_CN, False, None),  # 已是简体
        ("後愛上你", Language.ZH_CN, False, "后爱上你"),  # 简繁走 zhconv
        ("Hello", Language.EN, False, None),
        ("  ", Language.ZH_CN, False, None),
    ],
)
async def test_translate_routing(text: str, target: Language, called: bool, expected: str | None) -> None:
    web = FakeWeb([[["你好", "x"]]])
    result = await GoogleTranslator(web).translate(text, target)  # type: ignore[arg-type]
    assert bool(web.urls) is called
    assert result == expected


async def test_translate_failure_returns_none() -> None:
    web = FakeWeb(fail=True)
    assert await GoogleTranslator(web).translate("Hello", Language.ZH_CN) is None  # type: ignore[arg-type]


async def test_translate_long_text_is_chunked_and_any_failure_aborts() -> None:
    web = FakeWeb([[["段", "x"]]])
    long_text = "Hello world. " * 400
    result = await GoogleTranslator(web).translate(long_text, Language.ZH_CN)  # type: ignore[arg-type]
    assert len(web.urls) > 1
    assert result == "段" * len(web.urls)
    assert "tl=zh-CN" in web.urls[0]
    assert await GoogleTranslator(FakeWeb([])).translate(long_text, Language.ZH_CN) is None  # type: ignore[arg-type]
