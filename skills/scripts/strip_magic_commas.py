#!/usr/bin/env python3
"""去掉 magic trailing comma, 交由 ruff format 决定是否折成单行.

规则:
1. 所有多行 ``from x import ( ... )``: 去掉末尾逗号.
2. 参数个数 ≤ ``--max-args`` (默认 3) 的函数定义 / 调用: 去掉参数列表末尾逗号.
3. 默认跳过 Alembic ``migrations/versions/``.
4. 写盘后跑 ``ruff format``; 若折不回单行, format 可能加回逗号 —— 最终与原文相同则视为无变更.

用法::

    uv run python scripts/strip_magic_commas.py
    uv run python scripts/strip_magic_commas.py --dry-run
    just strip-commas
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (ROOT / "src" / "amane", ROOT / "tests", ROOT / "scripts")


def count_def_params(node: ast.AsyncFunctionDef | ast.FunctionDef) -> int:
    a = node.args
    return len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs) + (1 if a.vararg else 0) + (1 if a.kwarg else 0)


def count_call_args(node: ast.Call) -> int:
    return len(node.args) + len(node.keywords)


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for ln in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(ln))
    return starts


def find_matching_paren(text: str, open_idx: int) -> int:
    """Find closing paren matching ``text[open_idx] == '('``; skip strings/comments."""
    if text[open_idx] != "(":
        raise ValueError("open_idx must point to '('")
    depth = 0
    i = open_idx
    n = len(text)
    in_s: str | None = None
    triple = False
    while i < n:
        c = text[i]
        if in_s:
            if triple:
                if text.startswith(in_s, i):
                    in_s = None
                    triple = False
                    i += 3
                    continue
            else:
                if c == "\\":
                    i += 2
                    continue
                if c == in_s:
                    in_s = None
            i += 1
            continue
        if c in ('"', "'"):
            if text.startswith(c * 3, i):
                in_s = c * 3
                triple = True
                i += 3
                continue
            in_s = c
            triple = False
            i += 1
            continue
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"no matching paren at {open_idx}")


def strip_comma_before_closing_paren(text: str, open_idx: int, close_idx: int) -> str | None:
    inner = text[open_idx + 1 : close_idx]
    m = re.search(r",\s*$", inner, re.DOTALL)
    if not m:
        return None
    comma_at = open_idx + 1 + m.start()
    return text[:comma_at] + text[comma_at + 1 :]


def find_call_open_paren(text: str, node: ast.Call, line_starts: list[int]) -> int:
    if node.func.end_lineno is None or node.func.end_col_offset is None:
        raise ValueError("call func missing end position")
    start = line_starts[node.func.end_lineno - 1] + node.func.end_col_offset
    i = start
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i < len(text) and text[i] == "(":
        return i
    if node.end_lineno is None or node.end_col_offset is None:
        raise ValueError("call missing end position")
    node_start = line_starts[node.lineno - 1] + node.col_offset
    end = line_starts[node.end_lineno - 1] + node.end_col_offset
    close = end - 1
    while close > node_start and text[close] != ")":
        close -= 1
    depth = 0
    for j in range(close, node_start - 1, -1):
        if text[j] == ")":
            depth += 1
        elif text[j] == "(":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError("call paren not found")


def find_def_open_paren(text: str, node: ast.AsyncFunctionDef | ast.FunctionDef, line_starts: list[int]) -> int:
    start = line_starts[node.lineno - 1] + node.col_offset
    body_start = line_starts[node.body[0].lineno - 1] + node.body[0].col_offset
    region = text[start:body_start]
    idx = region.find(node.name)
    if idx < 0:
        raise ValueError(f"name {node.name} not found")
    j = start + idx + len(node.name)
    while j < body_start and text[j] in " \t\n":
        j += 1
    # PEP 695 type params: def foo[T](...):
    if j < body_start and text[j] == "[":
        depth = 0
        while j < body_start:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        while j < body_start and text[j] in " \t\n":
            j += 1
    if j >= body_start or text[j] != "(":
        raise ValueError(f"no ( for def {node.name} at line {node.lineno}")
    return j


def process_source(text: str, *, max_args: int) -> tuple[str, int]:
    edits = 0

    import_pat = re.compile(r"(from\s+[\w.]+\s+import\s*\()((?:[^)]|\n)*?)(\))", re.MULTILINE)

    def import_repl(m: re.Match[str]) -> str:
        nonlocal edits
        head, body, tail = m.group(1), m.group(2), m.group(3)
        if "\n" not in body:
            return m.group(0)
        new_body, n = re.subn(r",(\s*)$", r"\1", body)
        if n:
            edits += 1
        return head + new_body + tail

    text = import_pat.sub(import_repl, text)
    tree = ast.parse(text)
    line_starts = _line_starts(text)
    targets: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if count_def_params(node) > max_args or node.end_lineno is None:
                continue
            try:
                open_idx = find_def_open_paren(text, node, line_starts)
                close_idx = find_matching_paren(text, open_idx)
            except ValueError:
                continue
            if "\n" not in text[open_idx : close_idx + 1]:
                continue
            targets.append((open_idx, close_idx))
        elif isinstance(node, ast.Call):
            if count_call_args(node) > max_args:
                continue
            if node.end_lineno is None or node.lineno == node.end_lineno:
                continue
            try:
                open_idx = find_call_open_paren(text, node, line_starts)
                close_idx = find_matching_paren(text, open_idx)
            except ValueError:
                continue
            if "\n" not in text[open_idx : close_idx + 1]:
                continue
            targets.append((open_idx, close_idx))

    for open_idx, close_idx in sorted(set(targets), key=lambda x: -x[0]):
        new_text = strip_comma_before_closing_paren(text, open_idx, close_idx)
        if new_text is not None:
            text = new_text
            edits += 1

    return text, edits


def iter_py_files(roots: list[Path], *, skip_migration_versions: bool) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix == ".py":
                files.append(root)
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if skip_migration_versions and "migrations" in path.parts and "versions" in path.parts:
                continue
            files.append(path)
    return files


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="要处理的目录或文件 (默认: src/amane tests scripts)",
    )
    parser.add_argument("--max-args", type=int, default=3, help="函数定义/调用参数个数上限 (默认 3)")
    parser.add_argument("--dry-run", action="store_true", help="只报告 strip 阶段会动的文件, 不写入")
    parser.add_argument(
        "--include-migrations", action="store_true", help="也处理 Alembic migrations/versions (默认跳过)"
    )
    parser.add_argument("--no-format", action="store_true", help="改完后不自动 ruff format")
    args = parser.parse_args(argv)

    roots = [p.resolve() for p in args.paths] if args.paths else list(DEFAULT_ROOTS)
    files = iter_py_files(roots, skip_migration_versions=not args.include_migrations)

    originals: dict[Path, str] = {}
    stripped_files: list[Path] = []
    total_edits = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        try:
            new, edits = process_source(original, max_args=args.max_args)
        except SyntaxError as e:
            print(f"skip (syntax): {path}: {e}", file=sys.stderr)  # noqa: T201
            continue
        if new == original:
            continue
        originals[path] = original
        stripped_files.append(path)
        total_edits += edits
        if not args.dry_run:
            path.write_text(new, encoding="utf-8")

    if args.dry_run:
        print(f"dry-run strip: {len(stripped_files)} files, {total_edits} comma strips")  # noqa: T201
        for path in stripped_files:
            print(f"  {_rel(path)}")  # noqa: T201
        return 0

    if stripped_files and not args.no_format:
        cmd = ["uv", "run", "ruff", "format", *[str(p) for p in stripped_files]]
        print("+", " ".join(cmd))  # noqa: T201
        subprocess.run(cmd, check=True, cwd=ROOT)

    final_changed = [p for p in stripped_files if p.read_text(encoding="utf-8") != originals[p]]
    noop = len(stripped_files) - len(final_changed)
    print(  # noqa: T201
        f"wrote: {len(final_changed)} files changed after format "
        f"({noop} no-op; {total_edits} commas stripped before format)"
    )
    for path in final_changed:
        print(f"  {_rel(path)}")  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
