"""只做纯文本拆分, 落库语义见 ``db/repos/facet_helpers.py::clean_actor_names``."""

import re

_TRAILING_ALIAS_GROUP = re.compile(r"^(?P<name>.+?)\s*[（(]\s*(?P<aliases>[^（）()]*?)\s*[）)]$")
_ALIAS_SEPARATOR = re.compile(r"[,，、・]")


def split_actor_aliases(name: str) -> tuple[str, list[str]]:
    """拆分 ``name(alias1, alias2)`` 形式的演员名 → ``(规范名, 别名列表)``.

    - 支持全角 ``（）`` / 半角 ``()`` 括号与 ``,`` ``，`` ``、`` ``・`` 分隔.
    - 多组括号从外向内逐个拆分 (``A（B）（C）`` → ``A`` + ``[B, C]``), 别名保源顺序.
    - 括号组为空、拆分后规范名为空、别名与最终规范名相同 → 丢弃; 括号不在尾部
      (如 ``A (B) C``) 不拆分.
    - 无括号时原样返回空别名.
    """
    canonical = (name or "").strip()
    groups: list[list[str]] = []
    while True:
        m = _TRAILING_ALIAS_GROUP.match(canonical)
        if m is None:
            break
        head = m.group("name").strip()
        inner = m.group("aliases").strip()
        if not head or not inner:
            break
        group: list[str] = []
        for alias in _ALIAS_SEPARATOR.split(inner):
            alias = alias.strip()
            if alias and alias not in group:
                group.append(alias)
        groups.append(group)
        canonical = head
    # 组从外向内提取, 反转恢复源顺序; 跨组与最终规范名重复的别名丢弃.
    aliases: list[str] = []
    for group in reversed(groups):
        for alias in group:
            if alias not in aliases:
                aliases.append(alias)
    return canonical, [a for a in aliases if a != canonical]
