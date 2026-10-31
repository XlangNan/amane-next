"""谷歌免费翻译 (gtx 接口), 无需密钥. 非官方接口, 高频请求会被限流 (HTTP 429)."""

from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from ..enums import Language
from .base import TranslateError, is_rate_limited, short_reason

if TYPE_CHECKING:
    from ..net.http import WebClient

_ENDPOINTS = (
    "https://translate.googleapis.com/translate_a/single",
    "https://translate.google.com/translate_a/single",
)
"""同一接口的两个域名. 代理规则常把其中一个按「国内直连」处理而被掐断连接, 逐个尝试."""

_ATTEMPTS_PER_ENDPOINT = 2

_CODE: dict[Language, str] = {
    Language.ZH_CN: "zh-CN",
    Language.ZH_TW: "zh-TW",
    Language.JP: "ja",
    Language.EN: "en",
}


def parse_response(raw: Any) -> str | None:
    """取出 gtx 返回里按段拼接的译文; 结构不符时返回 ``None``."""
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], list):
        return None
    parts: list[str] = []
    for seg in raw[0]:
        if isinstance(seg, list) and seg and isinstance(seg[0], str):
            parts.append(seg[0])
    return "".join(parts) or None


class GoogleProvider:
    name = "谷歌"
    max_concurrent = 1
    min_interval = 0.6

    def __init__(self, web_client: "WebClient"):
        self._web = web_client

    async def translate_chunk(self, text: str, target: Language) -> str:
        query = urlencode({"client": "gtx", "sl": "auto", "tl": _CODE[target], "dt": "t", "q": text})
        reasons: list[str] = []
        limited = True
        for endpoint in _ENDPOINTS:
            host = endpoint.split("/")[2]
            try:
                resp = await self._web.request("GET", f"{endpoint}?{query}", max_attempts=_ATTEMPTS_PER_ENDPOINT)
                raw = resp.json()
            except Exception as e:
                reasons.append(f"{host}: {short_reason(e)}")
                limited = limited and is_rate_limited(e)
                continue
            translated = parse_response(raw)
            if translated is not None:
                return translated
            limited = False
            reasons.append(f"{host}: 返回了无法识别的内容")
        raise TranslateError("; ".join(reasons), rate_limited=limited)
