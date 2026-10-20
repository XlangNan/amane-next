"""钉钉自定义机器人: 加签与 markdown 消息. 出站 HTTP 一律经 ``WebClient``."""

import base64
import hashlib
import hmac
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, quote_plus, urlsplit

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from ..config import NotifyConfig
    from ..net.http import WebClient


class _Reply(BaseModel):
    errcode: int
    errmsg: str = ""


def sign(secret: str, timestamp_ms: int) -> str:
    """钉钉「加签」: HMAC-SHA256(secret, "{timestamp}\\n{secret}") → Base64 → URL 编码."""
    digest = hmac.new(secret.encode(), f"{timestamp_ms}\n{secret}".encode(), hashlib.sha256).digest()
    return quote_plus(base64.b64encode(digest))


def build_url(webhook: str, secret: str, *, now_ms: int | None = None) -> str:
    """未配密钥时原样返回. 配置校验保证 webhook 已带 ``?access_token=``, 所以这里用 ``&`` 续接."""
    if not secret:
        return webhook
    timestamp_ms = int(time.time() * 1000) if now_ms is None else now_ms
    return f"{webhook}&timestamp={timestamp_ms}&sign={sign(secret, timestamp_ms)}"


def _redact(text: str, cfg: NotifyConfig) -> str:
    """错误信息会进日志: 去掉 access_token 与密钥."""
    token = parse_qs(urlsplit(cfg.dingtalk_webhook).query).get("access_token", [""])[0]
    for secret in (token, cfg.dingtalk_secret):
        if secret:
            text = text.replace(secret, "***")
    return text


async def send_markdown(client: WebClient, cfg: NotifyConfig, title: str, text: str) -> str | None:
    """发一条 markdown 消息. 成功返回 None, 失败返回原因 (已脱敏); 从不抛出."""
    url = build_url(cfg.dingtalk_webhook, cfg.dingtalk_secret)
    body = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    try:
        raw = await client.post_json(url, json=body, use_proxy=cfg.use_proxy)
    except Exception as exc:
        return _redact(str(exc) or type(exc).__name__, cfg)
    try:
        reply = _Reply.model_validate(raw)
    except ValidationError:
        return "无法解析钉钉的返回"
    if reply.errcode == 0:
        return None
    return _redact(f"钉钉返回错误 {reply.errcode}: {reply.errmsg}", cfg)
