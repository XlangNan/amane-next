"""批次汇总文案. 纯函数, 不依赖运行时."""

from collections.abc import Sequence
from dataclasses import dataclass

DETAIL_LIMIT = 10
"""失败明细最多列出的条数, 其余只给数量."""

REASON_MAX_CHARS = 60
"""单条失败原因的最大长度, 超出截断并补 `…`."""

SUMMARY_HEADING = "Amane 刮削汇总"
TEST_HEADING = "Amane 通知已启用"


@dataclass
class FilmOutcome:
    """一部影片在本批里的结果."""

    number: str
    error: str | None = None
    """None 表示成功; 否则是失败原因."""


def _one_line(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= REASON_MAX_CHARS:
        return flat
    return flat[: REASON_MAX_CHARS - 1] + "…"


def _heading(base: str, keyword: str) -> str:
    """机器人开了关键词校验时, 标题与正文都必须含该词."""
    return f"{keyword} {base}" if keyword and keyword not in base else base


def build_summary(films: Sequence[FilmOutcome], keyword: str = "") -> tuple[str, str]:
    """返回 (标题, markdown 正文)."""
    failed = [film for film in films if film.error is not None]
    total = len(films)
    heading = _heading(SUMMARY_HEADING, keyword)
    lines = [
        f"### {heading}",
        "",
        f"本次处理影片 **{total}** 部, 成功 **{total - len(failed)}** 部, 失败 **{len(failed)}** 部",
    ]
    if failed:
        lines += ["", "**失败明细**", ""]
        lines += [f"- {film.number}: {_one_line(film.error or '')}" for film in failed[:DETAIL_LIMIT]]
        if len(failed) > DETAIL_LIMIT:
            lines.append(f"- …另有 {len(failed) - DETAIL_LIMIT} 部")
    return heading, "\n".join(lines)


def build_test_message(keyword: str = "") -> tuple[str, str]:
    """保存通知配置后发的确认消息, 用来立刻验证地址 / 加签 / 关键词是否填对."""
    heading = _heading(TEST_HEADING, keyword)
    return heading, f"### {heading}\n\n之后每批影片处理完, 会在这里汇总处理数量与成败."
