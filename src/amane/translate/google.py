"""谷歌免费翻译 (``translate.googleapis.com`` 的 gtx 接口), 无需密钥.

跨语系经该接口, 中文简繁经 ``zhconv`` 本地转换. 出站 HTTP 一律经 ``WebClient``, 因此沿用全局代理与限速.
接口是非官方的, 可能被限流或变更: 任何失败都返回 ``None``, 由调用方保留原文.
"""

from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import zhconv

from ..enums import Language
from ..utils.language import needs_translation

if TYPE_CHECKING:
    from ..net.http import WebClient

_ENDPOINT = "https://translate.googleapis.com/translate_a/single"

_CHUNK_CHARS = 1500
"""单次请求的文本上限; 超长简介按行 / 句号拆开后分段翻译."""

_GOOGLE_CODE: dict[Language, str] = {
    Language.ZH_CN: "zh-CN",
    Language.ZH_TW: "zh-TW",
    Language.JP: "ja",
    Language.EN: "en",
}

_ZHCONV_LOCALE: dict[Language, str] = {
    Language.ZH_CN: "zh-cn",
    Language.ZH_TW: "zh-tw",
}

_SENTENCE_ENDS = "。！？!?.\n"


def split_text(text: str, limit: int = _CHUNK_CHARS) -> list[str]:
    """按句末标点切成不超过 ``limit`` 字符的段, 拼接后与原文逐字相同."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            cut = max(text.rfind(c, start, end) for c in _SENTENCE_ENDS)
            if cut > start:
                end = cut + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def parse_response(raw: Any) -> str | None:
    """取出 gtx 返回里按段拼接的译文; 结构不符时返回 ``None``."""
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], list):
        return None
    parts: list[str] = []
    for seg in raw[0]:
        if isinstance(seg, list) and seg and isinstance(seg[0], str):
            parts.append(seg[0])
    return "".join(parts) or None


class GoogleTranslator:
    def __init__(self, web_client: "WebClient"):
        self._web = web_client

    async def translate(self, text: str, target: Language) -> str | None:
        """无需翻译或失败时返回 ``None``, 调用方保留原值. 不抛异常."""
        text = text.strip()
        if not text:
            return None

        if needs_translation(text, target):
            return await self._google(text, target)

        # 中文文本: 简繁字形转换 (幂等); 已是目标变体时结果等于原文 → None.
        locale = _ZHCONV_LOCALE.get(target)
        if locale is not None:
            converted = zhconv.convert(text, locale)
            return converted if converted != text else None
        return None

    async def _google(self, text: str, target: Language) -> str | None:
        out: list[str] = []
        for chunk in split_text(text):
            if not chunk.strip():
                out.append(chunk)
                continue
            translated = await self._one(chunk, target)
            if translated is None:
                return None
            out.append(translated)
        return "".join(out)

    async def _one(self, chunk: str, target: Language) -> str | None:
        query = urlencode({"client": "gtx", "sl": "auto", "tl": _GOOGLE_CODE[target], "dt": "t", "q": chunk})
        try:
            raw = await self._web.get_json(f"{_ENDPOINT}?{query}")
        except Exception:
            return None
        return parse_response(raw)
