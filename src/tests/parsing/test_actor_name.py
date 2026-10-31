"""演员名 name(alias1, alias2) 拆分测试."""

import pytest

from amane.parsing import split_actor_aliases

SPLIT_CASES: list[tuple[str, str, list[str]]] = [
    # 全角单组 (DMM 月度页真实形式)
    ("河北彩花（河北彩伽）", "河北彩花", ["河北彩伽"]),
    # 半角单组
    ("Mikami Yua (みかみ ゆあ)", "Mikami Yua", ["みかみ ゆあ"]),
    # 多种分隔符
    ("A（B, C）", "A", ["B", "C"]),
    ("A（B，C）", "A", ["B", "C"]),
    ("A（B、C）", "A", ["B", "C"]),
    ("A（B・C）", "A", ["B", "C"]),
    # 多组括号: 从外向内拆分, 别名保源顺序
    ("A（B）（C）", "A", ["B", "C"]),
    ("A（B）（C、D）", "A", ["B", "C", "D"]),
    # 空白处理
    (" A （ B ） ", "A", ["B"]),
    # 括号不在尾部: 名字中段的括号不拆分
    ("A (B) C", "A (B) C", []),
    ("A（B）C（D）", "A（B）C", ["D"]),
    # 无括号 / 空组 / 空规范名: 原样返回
    ("三上悠亜", "三上悠亜", []),
    ("A（）", "A（）", []),
    ("（B）", "（B）", []),
    ("", "", []),
    ("   ", "", []),
    # 别名与最终规范名相同 → 丢弃
    ("A（A）", "A", []),
    # 同组内别名去重
    ("A（B、B）", "A", ["B"]),
]


@pytest.mark.parametrize(("raw", "expected_name", "expected_aliases"), SPLIT_CASES)
def test_split_actor_aliases(raw: str, expected_name: str, expected_aliases: list[str]) -> None:
    assert split_actor_aliases(raw) == (expected_name, expected_aliases)
