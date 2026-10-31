"""微软 Edge 浏览器内置翻译的免费接口, 无需密钥, 国内一般可直连. 作为谷歌被限流或连不上时的备用."""

import time
from typing import TYPE_CHECKING, Any

from ..enums import Language
from .base import TranslateError, is_rate_limited, short_reason

if TYPE_CHECKING:
    from ..net.http import WebClient

_AUTH_URL = "https://edge.microsoft.com/translate/auth"
_TRANSLATE_URL = "https://api-edge.cognitive.microsofttranslator.com/translate"
_TOKEN_TTL = 480.0
"""令牌有效期约 10 分钟, 提前换新."""

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
        self._token = ""
        self._token_at = 0.0

    async def _auth(self) -> str:
        if self._token and time.monotonic() - self._token_at < _TOKEN_TTL:
            return self._token
        resp = await self._web.request("GET", _AUTH_URL, max_attempts=2)
        token = resp.text.strip()
        if not token:
            raise TranslateError("取不到必应翻译的令牌")
        self._token = token
        self._token_at = time.monotonic()
        return token

    async def translate_chunk(self, text: str, target: Language) -> str:
        try:
            token = await self._auth()
            resp = await self._web.request(
                "POST",
                f"{_TRANSLATE_URL}?api-version=3.0&to={_CODE[target]}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=[{"Text": text}],
                max_attempts=2,
            )
            raw = resp.json()
        except TranslateError:
            raise
        except Exception as e:
            self._token = ""
            raise TranslateError(short_reason(e), rate_limited=is_rate_limited(e)) from e
        translated = parse_response(raw)
        if translated is None:
            raise TranslateError("返回了无法识别的内容")
        return translated
