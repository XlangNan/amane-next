"""微软 Edge 浏览器内置翻译的免费接口, 无需密钥与令牌. 作为谷歌被限流或连不上时的备用."""

from typing import TYPE_CHECKING, Any

from ..enums import Language
from .base import TranslateError, is_rate_limited, short_reason

if TYPE_CHECKING:
    from ..net.http import WebClient

_URL = "https://edge.microsoft.com/translate/translatetext"
"""微软已下线带令牌的旧接口, 现在这个接口不需要令牌; 非官方, 可能随时变动."""

_CODE: dict[Language, str] = {
    Language.ZH_CN: "zh-Hans",
    Language.ZH_TW: "zh-Hant",
    Language.JP: "ja",
    Language.EN: "en",
}


def parse_response(raw: Any) -> str | None:
    """取出返回里第一条译文; 结构不符时返回 ``None``."""
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        return None
    translations = raw[0].get("translations")
    if not isinstance(translations, list) or not translations or not isinstance(translations[0], dict):
        return None
    text = translations[0].get("text")
    return text if isinstance(text, str) and text else None


class EdgeProvider:
    name = "必应"
    max_concurrent = 2
    min_interval = 0.2

    def __init__(self, web_client: "WebClient"):
        self._web = web_client

    async def translate_chunk(self, text: str, target: Language) -> str:
        try:
            resp = await self._web.request(
                "POST",
                f"{_URL}?from=&to={_CODE[target]}&isEnterpriseClient=false",
                headers={"Content-Type": "application/json"},
                json=[text],
                max_attempts=2,
            )
            raw = resp.json()
        except Exception as e:
            raise TranslateError(short_reason(e), rate_limited=is_rate_limited(e)) from e
        translated = parse_response(raw)
        if translated is None:
            raise TranslateError("返回了无法识别的内容")
        return translated
