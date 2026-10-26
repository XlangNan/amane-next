"""AMANE_TEST_LOG=1 时以随机间隔发射结构化日志, 供前端日志页开发."""

import asyncio
import random

import structlog

logger = structlog.get_logger("amane.random_logging")

_EVENTS: list[tuple[str, str, dict]] = [
    ("info", "task started", {"task_id": None, "task_type": "scrape"}),
    ("info", "task completed", {"task_id": None, "task_type": "scrape", "duration_s": None}),
    ("info", "file scanned", {"path": "/media/movies/example.mp4", "size_mb": None}),
    ("info", "metadata saved", {"number": "ABC-123", "title": "Example Title", "source": "javdb"}),
    ("info", "cron job fired", {"schedule_id": None, "cron": "*/5 * * * *"}),
    ("warning", "slow response", {"url": "https://javdb.com/v/abcde", "duration_s": None}),
    ("warning", "retry scheduled", {"task_id": None, "attempt": None, "reason": "timeout"}),
    ("warning", "rate limited", {"host": "javdb.com", "wait_s": None}),
    ("error", "scrape failed", {"task_id": None, "number": "XYZ-456", "error": "ConnectionTimeout"}),
    ("error", "download failed", {"url": "https://pics.example.com/cover.jpg", "error": "HTTP 403"}),
    ("debug", "cache hit", {"url": "https://javdb.com/v/12345", "age_s": None}),
    ("debug", "ws client connected", {"client_count": None}),
]


async def run_random_logging() -> None:
    log = logger.bind(component="random_logging")
    log.info("random log emitter started")

    try:
        while True:
            await asyncio.sleep(random.uniform(0.1, 0.7))
            level, event, payload_template = random.choice(_EVENTS)

            payload: dict = {}
            for k, v in payload_template.items():
                payload[k] = _random_value(k) if v is None else v

            getattr(log, level)(event, **payload)
    except asyncio.CancelledError:
        log.info("random log emitter stopped")
        raise


def _random_value(key: str) -> str | int | float:
    if "task_id" in key or "schedule_id" in key:
        return random.randint(100, 9999)
    if "duration" in key or "wait" in key or "age" in key:
        return round(random.uniform(0.1, 12.0), 2)
    if "size" in key:
        return round(random.uniform(0.5, 500.0), 1)
    if "attempt" in key or "count" in key:
        return random.randint(1, 5)
    return random.randint(1, 1000)
