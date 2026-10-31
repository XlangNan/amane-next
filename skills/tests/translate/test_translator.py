from typing import Any

import pytest

from amane.enums import Language
from amane.translate import TranslateError, Translator
from amane.translate import edge as edge_mod
from amane.translate import google as google_mod
from amane.translate.translator import split_text


class FakeProvider:
    max_concurrent = 1
    min_interval = 0.0

    def __init__(self, name: str, reply: str | None = "你好", *, rate_limited: bool = False) -> None:
        self.name = name
        self.reply = reply
        self.rate_limited = rate_limited
        self.calls = 0

    async def translate_chunk(self, text: str, target: Language) -> str:
        self.calls += 1
        if self.reply is None:
            raise TranslateError(f"{self.name} down", rate_limited=self.rate_limited)
        return self.reply


def make(*providers: FakeProvider) -> Translator:
    return Translator(None, list(providers))  # type: ignore[arg-type]


class FakeResp:
    def __init__(self, data: Any = None, text: str = "") -> None:
        self._data = data
        self.text = text

    def json(self) -> Any:
        return self._data


class FakeWeb:
    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = replies
        self.requests: list[tuple[str, str]] = []

    async def request(self, method: str, url: str, **_: Any) -> FakeResp:
        self.requests.append((method, url))
        for key, value in self.replies.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise RuntimeError("no route")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([[["你好", "Hello"], ["世界", " world"]], None, "en"], "你好世界"),
        ([[]], None),
        ([], None),
        ({"a": 1}, None),
        (None, None),
        ([[[None, "y"]]], None),
    ],
)
def test_google_parse_response(raw: Any, expected: str | None) -> None:
    assert google_mod.parse_response(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([{"translations": [{"text": "你好", "to": "zh-Hans"}]}], "你好"),
        ([{"translations": []}], None),
        ([{}], None),
        ([], None),
        ({"error": 1}, None),
        ([{"translations": [{"text": ""}]}], None),
    ],
)
def test_edge_parse_response(raw: Any, expected: str | None) -> None:
    assert edge_mod.parse_response(raw) == expected


@pytest.mark.parametrize("text", ["short", "a。" * 1000, "x" * 4000, "第一行\n" * 700])
def test_split_text_roundtrip_and_limit(text: str) -> None:
    chunks = split_text(text, 1500)
    assert "".join(chunks) == text
    assert all(len(c) <= 1500 for c in chunks)


@pytest.mark.parametrize(
    ("text", "target", "calls", "expected"),
    [
        ("Hello world", Language.ZH_CN, 1, "你好"),
        ("こんにちは", Language.ZH_CN, 1, "你好"),
        ("你好世界", Language.ZH_CN, 0, None),
        ("Hello", Language.EN, 0, None),
        ("  ", Language.ZH_CN, 0, None),
    ],
)
async def test_routing(text: str, target: Language, calls: int, expected: str | None) -> None:
    primary = FakeProvider("a")
    assert await make(primary).translate(text, target) == expected
    assert primary.calls == calls


async def test_fallback_to_second_provider_when_first_fails() -> None:
    first, second = FakeProvider("a", None), FakeProvider("b", "你好")
    assert await make(first, second).translate("Hello", Language.ZH_CN) == "你好"
    assert (first.calls, second.calls) == (1, 1)


async def test_all_providers_failing_returns_none() -> None:
    assert await make(FakeProvider("a", None), FakeProvider("b", None)).translate("Hello", Language.ZH_CN) is None


async def test_rate_limit_blocks_provider_immediately() -> None:
    limited, backup = FakeProvider("a", None, rate_limited=True), FakeProvider("b", "你好")
    translator = make(limited, backup)
    for word in ("Hello", "World", "Again"):
        assert await translator.translate(word, Language.ZH_CN) == "你好"
    assert limited.calls == 1  # 被限流后不再请求
    assert backup.calls == 3


async def test_three_plain_failures_trip_breaker() -> None:
    flaky = FakeProvider("a", None)
    translator = make(flaky)
    for word in ("a1", "a2", "a3", "a4"):
        assert await translator.translate(word, Language.ZH_CN) is None
    assert flaky.calls == 3


async def test_success_resets_failure_count() -> None:
    flaky = FakeProvider("a", None)
    translator = make(flaky)
    for word in ("a1", "a2"):
        await translator.translate(word, Language.ZH_CN)
    flaky.reply = "你好"
    assert await translator.translate("Hello", Language.ZH_CN) == "你好"
    flaky.reply = None
    for word in ("b1", "b2"):
        await translator.translate(word, Language.ZH_CN)
    flaky.reply = "你好"
    assert await translator.translate("Hello again", Language.ZH_CN) == "你好"


async def test_probe_reports_provider_ignores_breaker_and_lists_reasons() -> None:
    limited = FakeProvider("a", None, rate_limited=True)
    translator = make(limited, FakeProvider("b", "你好"))
    await translator.translate("Hello", Language.ZH_CN)
    assert await translator.probe("こんにちは", Language.ZH_CN) == ("你好", "b")
    assert limited.calls == 2  # probe 无视停用状态, 仍会先试第一个源
    with pytest.raises(TranslateError, match="a down"):
        await make(FakeProvider("a", None)).probe("x", Language.ZH_CN)


async def test_google_provider_tries_second_domain_and_marks_429() -> None:
    ok = FakeWeb(
        {"translate.googleapis.com": RuntimeError("curl reset"), "translate.google.com": FakeResp([[["你好", "x"]]])}
    )
    assert await google_mod.GoogleProvider(ok).translate_chunk("Hello", Language.ZH_CN) == "你好"  # type: ignore[arg-type]
    assert [u.split("/")[2] for _, u in ok.requests] == ["translate.googleapis.com", "translate.google.com"]

    limited = FakeWeb({"translate.googleapis.com": RuntimeError("HTTP 429"), "translate.google.com": RuntimeError("HTTP 429")})
    with pytest.raises(TranslateError) as info:
        await google_mod.GoogleProvider(limited).translate_chunk("Hello", Language.ZH_CN)  # type: ignore[arg-type]
    assert info.value.rate_limited is True

    mixed = FakeWeb({"translate.googleapis.com": RuntimeError("HTTP 429"), "translate.google.com": RuntimeError("reset")})
    with pytest.raises(TranslateError) as info2:
        await google_mod.GoogleProvider(mixed).translate_chunk("Hello", Language.ZH_CN)  # type: ignore[arg-type]
    assert info2.value.rate_limited is False


async def test_edge_provider_fetches_token_once_and_translates() -> None:
    web = FakeWeb(
        {
            "edge.microsoft.com/translate/auth": FakeResp(text=" TOKEN \n"),
            "api-edge.cognitive": FakeResp([{"translations": [{"text": "你好", "to": "zh-Hans"}]}]),
        }
    )
    provider = edge_mod.EdgeProvider(web)  # type: ignore[arg-type]
    assert await provider.translate_chunk("Hello", Language.ZH_CN) == "你好"
    assert await provider.translate_chunk("World", Language.ZH_CN) == "你好"
    assert sum("auth" in url for _, url in web.requests) == 1
    assert all("to=zh-Hans" in url for _, url in web.requests if "api-edge" in url)


@pytest.mark.parametrize(
    "replies",
    [
        {"edge.microsoft.com/translate/auth": FakeResp(text="")},
        {"edge.microsoft.com/translate/auth": RuntimeError("HTTP 429")},
        {"edge.microsoft.com/translate/auth": FakeResp(text="T"), "api-edge.cognitive": FakeResp([])},
    ],
)
async def test_edge_provider_errors_are_translate_errors(replies: dict[str, Any]) -> None:
    with pytest.raises(TranslateError):
        await edge_mod.EdgeProvider(FakeWeb(replies)).translate_chunk("Hello", Language.ZH_CN)  # type: ignore[arg-type]
