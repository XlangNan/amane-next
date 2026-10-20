#!/usr/bin/env python3
"""发版管线里的检查与白名单提交. 不负责 ``uv version`` 与 ``just generate``.

``pyproject.toml`` 是产品版本的唯一手写源; ``CHANGELOG.md`` 对应版本节是 GitHub Release 正文的唯一手写源. 对外入口是 ``just bump`` (Justfile 编排预定义命令).

用法 (由 Justfile 调用)::

    uv run python scripts/bump_version.py precheck patch [--dry-run]
    uv run python scripts/bump_version.py commit

对外入口: ``just bump patch`` / ``just bump-dry patch``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]

BumpKind = Literal["major", "minor", "patch"]
BUMP_CHOICES: tuple[BumpKind, ...] = ("major", "minor", "patch")

# 整段 bump 管线结束后只允许这些相对路径出现在 git 变更里; 以 ``/`` 结尾的是目录前缀.
ALLOWED_PATHS: frozenset[str] = frozenset(
    {
        "CHANGELOG.md",
        "pyproject.toml",
        "uv.lock",
        "web/openapi.json",
        "web/src/client/",
    }
)

# precheck 时允许已写好、尚未提交的 changelog; 其它脏文件仍拒绝.
PREBUMP_ALLOWED_PATHS: frozenset[str] = frozenset({"CHANGELOG.md"})


class BumpError(Exception):
    """用户可见的失败, ``main`` 打印到 stderr 并以 1 退出."""


def _parse_kind(raw: str) -> BumpKind:
    if raw == "major" or raw == "minor" or raw == "patch":
        return raw
    raise BumpError(f"未知 bump: {raw}")


def commit_message(version: str) -> str:
    return f"release: {version}"


def tag_name(version: str) -> str:
    return f"v{version}"


def path_allowed(path: str, allowed: frozenset[str] = ALLOWED_PATHS) -> bool:
    if path in allowed:
        return True
    return any(path.startswith(prefix) for prefix in allowed if prefix.endswith("/"))


def extra_paths(changed: frozenset[str], allowed: frozenset[str] = ALLOWED_PATHS) -> frozenset[str]:
    return frozenset(p for p in changed if not path_allowed(p, allowed))


def allowed_changed(changed: frozenset[str], allowed: frozenset[str] = ALLOWED_PATHS) -> list[str]:
    return sorted(p for p in changed if path_allowed(p, allowed))


def parse_name_list(*chunks: str) -> frozenset[str]:
    paths: set[str] = set()
    for chunk in chunks:
        for line in chunk.splitlines():
            path = line.strip()
            if path:
                paths.add(path)
    return frozenset(paths)


def require_clean(changed: frozenset[str]) -> None:
    if changed:
        listing = ", ".join(sorted(changed))
        raise BumpError(f"工作区不干净, 拒绝 bump: {listing}")


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
        raise BumpError(f"{' '.join(cmd)} 失败: {detail}")
    return result.stdout


def git(root: Path, *args: str) -> str:
    return _run(["git", *args], cwd=root)


def git_changed_paths(root: Path) -> frozenset[str]:
    diff = git(root, "diff", "--name-only", "HEAD")
    untracked = git(root, "ls-files", "--others", "--exclude-standard")
    return parse_name_list(diff, untracked)


def tag_exists(root: Path, name: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{name}"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def read_uv_version(root: Path, *, bump: BumpKind | None = None, dry_run: bool = False) -> str:
    cmd = ["uv", "version", "--output-format", "json", "--no-sync"]
    if bump is not None:
        cmd.extend(["--bump", bump])
    if dry_run:
        cmd.append("--dry-run")
    raw = _run(cmd, cwd=root)
    try:
        data: object = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BumpError(f"uv version 不是 JSON: {raw!r}") from e
    if not isinstance(data, dict):
        raise BumpError(f"uv version JSON 应为 object: {raw!r}")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise BumpError(f"uv version 缺少 version: {raw!r}")
    return version


def print_plan(current: str, new: str) -> None:
    print(f"{current} => {new}")  # noqa: T201
    print(f"commit: {commit_message(new)}")  # noqa: T201
    print(f"tag: {tag_name(new)}")  # noqa: T201


def require_changelog(root: Path, version: str) -> None:
    script = Path(__file__).resolve().parent / "changelog.py"
    path = root / "CHANGELOG.md"
    result = subprocess.run(
        [sys.executable, str(script), "extract", version, "--file", str(path)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
        raise BumpError(detail)


def require_prebump_clean(changed: frozenset[str]) -> None:
    unexpected = extra_paths(changed, PREBUMP_ALLOWED_PATHS)
    if unexpected:
        listing = ", ".join(sorted(unexpected))
        raise BumpError(f"工作区不干净, 拒绝 bump: {listing}")


def precheck(root: Path, kind: BumpKind, *, dry_run: bool) -> str:
    require_prebump_clean(git_changed_paths(root))
    current = read_uv_version(root)
    new = read_uv_version(root, bump=kind, dry_run=True)
    if new == current:
        raise BumpError(f"版本未变化: {current}")
    tag = tag_name(new)
    if tag_exists(root, tag):
        raise BumpError(f"tag 已存在: {tag}")
    require_changelog(root, new)
    print_plan(current, new)
    if dry_run:
        print("dry-run: 未写入")  # noqa: T201
    return new


def commit_release(root: Path) -> None:
    version = read_uv_version(root)
    tag = tag_name(version)
    if tag_exists(root, tag):
        raise BumpError(f"tag 已存在: {tag}")
    require_changelog(root, version)
    changed = git_changed_paths(root)
    unexpected = extra_paths(changed)
    if unexpected:
        listing = ", ".join(sorted(unexpected))
        raise BumpError(f"bump 改动了白名单以外的文件, 已中止提交: {listing}")
    to_add = allowed_changed(changed)
    if "pyproject.toml" not in to_add:
        raise BumpError("uv version 未改 pyproject.toml")
    git(root, "add", "--", *to_add)
    git(root, "commit", "-m", commit_message(version))
    git(root, "tag", "-a", tag, "-m", tag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="step", required=True)

    pre = sub.add_parser("precheck", help="工作区 (changelog 除外) 干净、下一版本节存在、tag 不冲突")
    pre.add_argument("kind", choices=BUMP_CHOICES, help="要升高的 semver 段")
    pre.add_argument("--dry-run", action="store_true", help="只预览, 不写文件")

    sub.add_parser("commit", help="按白名单 git add / commit / tag")

    args = parser.parse_args(argv)
    try:
        if args.step == "precheck":
            precheck(ROOT, _parse_kind(args.kind), dry_run=args.dry_run)
        elif args.step == "commit":
            commit_release(ROOT)
        else:
            raise BumpError(f"未知步骤: {args.step}")
    except BumpError as e:
        print(e, file=sys.stderr)  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
