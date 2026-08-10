#!/usr/bin/env python3
"""Lint the active Codex/legacy boundary, routes, and local Markdown links."""

from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


ACTIVE_GLOBS = (
    "SKILL.md",
    "README*.md",
    "steps/**",
    "references/**",
    "scripts/**",
    "templates/**",
    "tools/**",
    "mcp/install-codex.sh",
    "mcp/uninstall-codex.sh",
    "mcp/codex_adapter.py",
)

LEGACY_ALLOWLIST = (
    "mcp/install.sh",  # legacy allowlist
    "mcp/uninstall.sh",  # legacy allowlist
    "mcp/*/install.sh",  # legacy allowlist
    "mcp/*/uninstall.sh",  # legacy allowlist
    "mcp/*/scripts/register_mcp.py",
    "mcp/*/README.md",
)

COMMAND_ROUTES = {
    "help": "steps/help.md",
    "install": "steps/install.md",
    "init": "steps/00_init.md",
    "log": "steps/log.md",
    "plan": "steps/01_plan.md",
    "start": "steps/01_plan.md",
    "review": "steps/02_review.md",
    "merge": "steps/03_merge.md",
    "code": "steps/04_code.md",
    "deepcheck": "steps/05_deepcheck.md",
    "audit": "steps/06_audit.md",
    "run": "steps/run.md",
    "fast": "steps/fast.md",
    "patch": "steps/08_patch.md",
    "doc": "steps/doc.md",
    "limit": "steps/limit.md",
    "readme": "steps/07_readme.md",
    "status": "steps/status.md",
    "list": "steps/list.md",
}

LEGACY_MARKERS = ("legacy", "兼容", "只读", "read-only", "不写", "禁止", "不得", "never", "绝不")
OLD_RUN_TOKEN = ".icode" + "_output"
OLD_HOME_TOKEN = "~/" + ".claude"


def _matches(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def active_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if _matches(relative, ACTIVE_GLOBS) and not _matches(relative, LEGACY_ALLOWLIST):
            yield path


def _legacy_is_documented_read_only(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in LEGACY_MARKERS)


def _old_slash_command(line: str) -> bool:
    return re.search(r"(?<![.$A-Za-z0-9_-])/icode(?=\s|`|$)", line) is not None


def _legacy_installer_reference(line: str) -> bool:
    return re.search(r"mcp/(?:[A-Za-z0-9_-]+/)?(?:install|uninstall)\.sh", line) is not None


def lint_active_boundaries(root: Path) -> List[str]:
    errors: List[str] = []
    for path in active_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            has_old_path = OLD_RUN_TOKEN in line or OLD_HOME_TOKEN in line or _old_slash_command(line)
            if has_old_path and not _legacy_is_documented_read_only(line):
                errors.append(f"{relative}:{number}: legacy path/command lacks same-line read-only marker")
            if _legacy_installer_reference(line) and not _legacy_is_documented_read_only(line):
                errors.append(f"{relative}:{number}: active file references a legacy installer")
    return errors


def _markdown_links(path: Path) -> Iterable[Tuple[int, str]]:
    pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in pattern.finditer(line):
            yield number, match.group(1).split("#", 1)[0]


def lint_links(root: Path) -> List[str]:
    errors: List[str] = []
    for path in active_files(root):
        if path.suffix != ".md":
            continue
        relative = path.relative_to(root).as_posix()
        for number, target in _markdown_links(path):
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if any(marker in target for marker in ("<", ">", "xx.md", "xxx.md")):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{relative}:{number}: broken Markdown link: {target}")
    return errors


def _commands_in_help(root: Path) -> set[str]:
    text = (root / "steps/help.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\$icodex\s+([a-z]+)", text, re.MULTILINE))


def lint_routes(root: Path) -> List[str]:
    errors: List[str] = []
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if not re.search(r"^name:\s*icodex\s*$", skill, re.MULTILINE):
        errors.append("SKILL.md:2: frontmatter name must be icodex")
    for command, target in COMMAND_ROUTES.items():
        if not (root / target).is_file():
            errors.append(f"SKILL.md: missing route target for {command}: {target}")
        if f"`{command}`" not in skill and f"$icodex {command}" not in skill:
            errors.append(f"SKILL.md: missing route declaration for {command}")
    help_commands = _commands_in_help(root)
    expected = set(COMMAND_ROUTES)
    if help_commands != expected:
        errors.append(
            "steps/help.md: command set differs from routes; "
            f"missing={sorted(expected - help_commands)} extra={sorted(help_commands - expected)}"
        )
    if "`$icodex start` 永远只是 `$icodex plan`" not in skill:
        errors.append("SKILL.md: start must be documented as the plan alias")
    if "只有 `$icodex run` 会自动串联步骤 1→6" not in skill:
        errors.append("SKILL.md: run must be the automatic staged chain")
    return errors


def lint_readme_parity(root: Path) -> List[str]:
    errors: List[str] = []
    command_sets = {}
    for name in ("README.md", "README.zh-CN.md"):
        path = root / name
        if not path.is_file():
            errors.append(f"{name}: missing required README")
            continue
        text = path.read_text(encoding="utf-8")
        command_sets[name] = set(re.findall(r"\$icodex\s+([a-z]+)", text))
        for required in ("v2.17", ".ai/icode/", "~/.codex/icode_data/", "~/.codex/skills/icodex"):
            if required not in text:
                errors.append(f"{name}: missing required contract text: {required}")
    if len(command_sets) == 2:
        expected = set(COMMAND_ROUTES)
        for name, commands in command_sets.items():
            if commands != expected:
                errors.append(
                    f"{name}: command set mismatch; "
                    f"missing={sorted(expected - commands)} extra={sorted(commands - expected)}"
                )
        if command_sets["README.md"] != command_sets["README.zh-CN.md"]:
            errors.append("README.md and README.zh-CN.md command sets differ")
    return errors


def lint_repo(root: Path) -> List[str]:
    return lint_active_boundaries(root) + lint_links(root) + lint_routes(root) + lint_readme_parity(root)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors = lint_repo(root)
    for error in errors:
        print(error)
    if errors:
        print(f"Codex contract lint failed: {len(errors)} issue(s)")
        return 1
    print("Codex contract lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
