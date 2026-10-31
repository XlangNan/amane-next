"""翻译源的公共约定."""

from typing import Protocol

from ..enums import Language


class TranslateError(Exception):
    """翻译请求失败或返回内容无法解析. ``rate_limited`` 表示被对方限流 (HTTP 429)."""

    def __init__(self, message: str, *, rate_limited: bool = False):
        super().__init__(message)
        self.rate_limited = rate_limited


class Provider(Protocol):
    """单个在线翻译源. 只负责把一段文本译成目标语言, 语种判断与重试策略在 ``Translator``."""

    name: str
    max_concurrent: int
    min_interval: float
    """同一源两次请求之间的最短间隔 (秒), 用于避免触发限流."""

    async def translate_chunk(self, text: str, target: Language) -> str: ...


def is_rate_limited(exc: Exception) -> bool:
    return "429" in str(exc)


def short_reason(exc: Exception, limit: int = 160) -> str:
    """去掉整段 URL 与 curl 手册指引, 只留能看出原因的部分."""
    text = str(exc).split(" See https://curl.se")[0]
    return text if len(text) <= limit else text[:limit] + "..."
