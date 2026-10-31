"""在线翻译: 先谷歌, 失败 (含被限流) 改用必应. 中文简繁经 ``zhconv`` 本地转换. 出站 HTTP 一律经 ``WebClient``.

任何失败都返回 ``None``, 由调用方保留原文. 各源各自限并发与限速, 连续失败后短暂停用, 被限流 (429) 则停用更久.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
import zhconv

from ..enums import Language
from ..utils.language import needs_translation
from .base import Provider, TranslateError
from .edge import EdgeProvider
from .google import GoogleProvider

if TYPE_CHECKING:
    from ..net.http import WebClient

logger = structlog.get_logger()

_CHUNK_CHARS = 1500
"""单次请求的文本上限; 超长简介按行 / 句号拆开后分段翻译."""

_BREAKER_THRESHOLD = 3
_BREAKER_SECONDS = 30.0
_RATE_LIMIT_SECONDS = 180.0

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


@dataclass
class _Slot:
    provider: Provider
    sem: asyncio.Semaphore
    failures: int = 0
    blocked_until: float = 0.0
    last_done: float = field(default=0.0)

    def blocked(self) -> bool:
        return time.monotonic() < self.blocked_until


class Translator:
    def __init__(self, web_client: "WebClient", providers: list[Provider] | None = None):
        chosen = providers if providers is not None else [GoogleProvider(web_client), EdgeProvider(web_client)]
        self._slots = [_Slot(p, asyncio.Semaphore(p.max_concurrent)) for p in chosen]

    async def translate(self, text: str, target: Language) -> str | None:
        """无需翻译或失败时返回 ``None``, 调用方保留原值. 不抛异常."""
        text = text.strip()
        if not text:
            return None

        if needs_translation(text, target):
            out: list[str] = []
            for chunk in split_text(text):
                if not chunk.strip():
                    out.append(chunk)
                    continue
                try:
                    translated, _ = await self._chunk(chunk, target, respect_breaker=True)
                except TranslateError as e:
                    logger.warning("translate failed", error=str(e))
                    return None
                out.append(translated)
            return "".join(out)

        # 中文文本: 简繁字形转换 (幂等); 已是目标变体时结果等于原文 → None.
        locale = _ZHCONV_LOCALE.get(target)
        if locale is not None:
            converted = zhconv.convert(text, locale)
            return converted if converted != text else None
        return None

    async def probe(self, text: str, target: Language) -> tuple[str, str]:
        """不做语种判断、无视停用状态地请求一次, 返回 (译文, 源名); 失败抛 ``TranslateError`` 并带各源原因."""
        return await self._chunk(text, target, respect_breaker=False)

    async def _chunk(self, chunk: str, target: Language, *, respect_breaker: bool) -> tuple[str, str]:
        reasons: list[str] = []
        for slot in self._slots:
            if respect_breaker and slot.blocked():
                reasons.append(f"{slot.provider.name}: 暂时停用")
                continue
            try:
                translated = await self._run(slot, chunk, target)
            except TranslateError as e:
                self._record_failure(slot, e)
                reasons.append(f"{slot.provider.name}: {e}")
                continue
            slot.failures = 0
            return translated, slot.provider.name
        raise TranslateError(" | ".join(reasons))

    async def _run(self, slot: _Slot, chunk: str, target: Language) -> str:
        async with slot.sem:
            wait = slot.last_done + slot.provider.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await slot.provider.translate_chunk(chunk, target)
            finally:
                slot.last_done = time.monotonic()

    @staticmethod
    def _record_failure(slot: _Slot, error: TranslateError) -> None:
        slot.failures += 1
        if error.rate_limited:
            slot.blocked_until = time.monotonic() + _RATE_LIMIT_SECONDS
            slot.failures = 0
        elif slot.failures >= _BREAKER_THRESHOLD:
            slot.blocked_until = time.monotonic() + _BREAKER_SECONDS
            slot.failures = 0
