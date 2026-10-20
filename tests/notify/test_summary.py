"""批次汇总文案."""

import pytest

from amane.notify.summary import DETAIL_LIMIT, REASON_MAX_CHARS, FilmOutcome, build_summary, build_test_message


def _films(ok: int, failed: int, reason: str = "未找到元数据") -> list[FilmOutcome]:
    return [FilmOutcome(f"OK-{i}") for i in range(ok)] + [FilmOutcome(f"BAD-{i}", reason) for i in range(failed)]


@pytest.mark.parametrize(
    ("ok", "failed"),
    [(0, 0), (5, 0), (0, 3), (10, 2)],
    ids=["empty", "all-ok", "all-failed", "mixed"],
)
def test_counts_line(ok: int, failed: int) -> None:
    _, text = build_summary(_films(ok, failed))
    assert f"本次处理影片 **{ok + failed}** 部, 成功 **{ok}** 部, 失败 **{failed}** 部" in text
    assert ("失败明细" in text) is (failed > 0)


@pytest.mark.parametrize(
    ("keyword", "heading"),
    [("", "Amane 刮削汇总"), ("通知", "通知 Amane 刮削汇总"), ("Amane", "Amane 刮削汇总")],
    ids=["no-keyword", "keyword-prefixed", "keyword-already-present"],
)
def test_keyword_lands_in_title_and_body(keyword: str, heading: str) -> None:
    """机器人开了关键词校验时, 标题与正文都得含该词; 已含则不重复."""
    title, text = build_summary(_films(1, 0), keyword)
    assert title == heading
    assert text.startswith(f"### {heading}")


def test_failure_details_are_capped() -> None:
    _, text = build_summary(_films(0, DETAIL_LIMIT + 2))
    assert text.count("- BAD-") == DETAIL_LIMIT
    assert "- …另有 2 部" in text


def test_failure_details_at_limit_have_no_overflow_line() -> None:
    _, text = build_summary(_films(0, DETAIL_LIMIT))
    assert "另有" not in text


def test_reason_is_flattened_and_truncated() -> None:
    long_reason = "第一行\n第二行\t" + "长" * 200
    _, text = build_summary([FilmOutcome("X-1", long_reason)])
    line = next(line for line in text.splitlines() if line.startswith("- X-1: "))
    reason = line.removeprefix("- X-1: ")
    assert "\n" not in reason
    assert reason.startswith("第一行 第二行 ")
    assert len(reason) == REASON_MAX_CHARS
    assert reason.endswith("…")


def test_test_message_carries_keyword() -> None:
    title, text = build_test_message("通知")
    assert "通知" in title
    assert "通知" in text
