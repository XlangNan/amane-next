"""钉钉加签与发送."""

from typing import Any, cast

import pytest
from pydantic import ValidationError

from amane.config import NotifyConfig
from amane.net.http import WebClient
from amane.notify.dingtalk import build_url, send_markdown, sign

TOKEN = "tok123456"
WEBHOOK = f"https://oapi.dingtalk.com/robot/send?access_token={TOKEN}"
SECRET = "SEC0123456789abcdef"


class _FakeClient:
    """记录请求; ``reply`` 是 post_json 的返回, ``fail`` 非空时抛出."""

    def __init__(self, reply: Any = None, fail: Exception | None = None) -> None:
        self.reply = {"errcode": 0, "errmsg": "ok"} if reply is None else reply
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def post_json(self, url: str, *, json: Any = None, use_proxy: bool = True, **_: Any) -> Any:
        self.calls.append({"url": url, "json": json, "use_proxy": use_proxy})
        if self.fail is not None:
            raise self.fail
        return self.reply


def _cfg(**overrides: Any) -> NotifyConfig:
    return NotifyConfig(dingtalk_enabled=True, dingtalk_webhook=WEBHOOK, **overrides)


def test_sign_matches_dingtalk_algorithm() -> None:
    """固定向量: HMAC-SHA256(secret, "{ts}\\n{secret}") → Base64 → URL 编码 (钉钉文档的算法)."""
    assert sign(SECRET, 1700000000000) == "TSZbRFUuvaSQaRKUpF970OPCb2%2FLcQAP3wOvwZIzBZk%3D"


def test_build_url_without_secret_is_unchanged() -> None:
    assert build_url(WEBHOOK, "") == WEBHOOK


def test_build_url_with_secret_appends_timestamp_and_sign() -> None:
    url = build_url(WEBHOOK, SECRET, now_ms=1700000000000)
    assert url == f"{WEBHOOK}&timestamp=1700000000000&sign={sign(SECRET, 1700000000000)}"


@pytest.mark.parametrize(
    "webhook",
    [
        "",
        WEBHOOK,
        f"{WEBHOOK}&extra=1",
    ],
    ids=["empty-means-off", "official", "official-with-extra-query"],
)
def test_webhook_accepts(webhook: str) -> None:
    assert NotifyConfig(dingtalk_webhook=webhook).dingtalk_webhook == webhook


@pytest.mark.parametrize(
    "webhook",
    [
        "https://example.com/robot/send?access_token=abc",
        "http://oapi.dingtalk.com/robot/send?access_token=abc",
        "https://oapi.dingtalk.com/robot/send?access_token=",
        "https://oapi.dingtalk.com/robot/send",
        "https://oapi.dingtalk.com.evil.com/robot/send?access_token=abc",
        "not a url",
    ],
    ids=["foreign-host", "http", "empty-token", "no-token", "lookalike-host", "garbage"],
)
def test_webhook_rejects(webhook: str) -> None:
    """只放行钉钉官方域名, 配置接口不能被用来让服务端向任意地址发 POST."""
    with pytest.raises(ValidationError):
        NotifyConfig(dingtalk_webhook=webhook)


@pytest.mark.asyncio
async def test_send_posts_markdown_and_reports_success() -> None:
    client = _FakeClient()
    result = await send_markdown(cast("WebClient", client), _cfg(), "标题", "正文")
    assert result is None
    (call,) = client.calls
    assert call["url"] == WEBHOOK
    assert call["json"] == {"msgtype": "markdown", "markdown": {"title": "标题", "text": "正文"}}
    assert call["use_proxy"] is False


@pytest.mark.asyncio
async def test_send_signs_when_secret_set_and_honors_proxy_flag() -> None:
    client = _FakeClient()
    await send_markdown(cast("WebClient", client), _cfg(dingtalk_secret=SECRET, use_proxy=True), "t", "x")
    (call,) = client.calls
    assert call["url"].startswith(f"{WEBHOOK}&timestamp=")
    assert "&sign=" in call["url"]
    assert call["use_proxy"] is True


@pytest.mark.asyncio
async def test_send_reports_dingtalk_error_without_leaking_credentials() -> None:
    reply = {"errcode": 310000, "errmsg": f"keywords not in content, token {TOKEN} secret {SECRET}"}
    client = _FakeClient(reply)
    result = await send_markdown(cast("WebClient", client), _cfg(dingtalk_secret=SECRET), "t", "x")
    assert result is not None
    assert "310000" in result
    assert TOKEN not in result
    assert SECRET not in result


@pytest.mark.asyncio
async def test_send_swallows_transport_errors_and_redacts() -> None:
    client = _FakeClient(fail=RuntimeError(f"failed: {WEBHOOK}"))
    result = await send_markdown(cast("WebClient", client), _cfg(), "t", "x")
    assert result is not None
    assert TOKEN not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ["oops", [], {"errmsg": "no code"}], ids=["str", "list", "missing-errcode"])
async def test_send_rejects_unreadable_reply(reply: Any) -> None:
    client = _FakeClient(reply)
    result = await send_markdown(cast("WebClient", client), _cfg(), "t", "x")
    assert result == "无法解析钉钉的返回"
