#!/usr/bin/env python3
"""Mirror shared rule sections from SKILL.md into references/full_workflow.md.

SKILL.md is the single authoring point: it is the always-loaded entry document, while
references/full_workflow.md is loaded on demand for the full workflow. Both must state the
same rules, and hand-maintaining two copies already drifted (the full-workflow copy kept
"首轮必须写 JSON" while the entry copy lost it; the lite status flow was listed in
neither).

Each region is delimited in the target by a marker pair:

    <!-- BEGIN shared:<name> (generated from SKILL.md by tools/sync_shared_docs.py; do not edit inline) -->
    ...
    <!-- END shared:<name> -->

`--check` (used by tests and CI) fails when any mirror is stale; `--write` regenerates the
mirrors. Relative links are rewritten because the target lives in references/.
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "SKILL.md"
TARGET = ROOT / "references/full_workflow.md"

# name -> (start heading in both documents, end heading in both documents)
REGIONS = {
    "natural-language-entry": ("## 自然语言入口", "## 调用命令"),
    "command-catalog": ("## 调用命令", "## 控制面"),
    "artifact-vocabulary": ("### 产物命名 + status 词表速查表", "### 强制阻断边界矩阵"),
    "execution-mode": ("### 执行模式", "### 强制思考前置"),
}


class SyncError(RuntimeError):
    pass


def retarget(link):
    """Rewrite a SKILL.md-relative link for a document that lives in references/."""
    if link.startswith(("http://", "https://", "mailto:", "#", "../")):
        return link
    path, _, anchor = link.partition("#")
    suffix = "#" + anchor if anchor else ""
    if path.startswith("references/"):
        return path[len("references/"):] + suffix
    if not path or path.endswith("/"):
        return link
    return "../" + path + suffix


def block(text, name, headings):
    """Authored section between two headings, with references/ links flattened."""
    start_marker, end_marker = headings
    try:
        start = text.index(start_marker)
        end = text.index(end_marker, start + len(start_marker))
    except ValueError as exc:
        raise SyncError(f"缺少「{name}」的段边界（{start_marker} / {end_marker}）") from exc
    section = text[start:end].rstrip("\n") + "\n"
    return re.sub(r"\]\(([^)\s]+)\)", lambda m: "](" + retarget(m.group(1)) + ")", section)


def markers(name):
    begin = (f"<!-- BEGIN shared:{name} "
             "(generated from SKILL.md by tools/sync_shared_docs.py; do not edit inline) -->")
    return begin, f"<!-- END shared:{name} -->"


def render(target_text, source_text):
    result = target_text
    for name, headings in REGIONS.items():
        begin, end = markers(name)
        try:
            head, rest = result.split(begin, 1)
            _, tail = rest.split(end, 1)
        except ValueError as exc:
            raise SyncError(f"references/full_workflow.md 缺少「{name}」的标记对") from exc
        result = head + begin + "\n" + block(source_text, name, headings) + end + tail
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只校验镜像是否同步（默认）")
    mode.add_argument("--write", action="store_true", help="重写 full_workflow.md 的镜像段")
    args = parser.parse_args(argv)
    try:
        source_text = SOURCE.read_text(encoding="utf-8")
        target_text = TARGET.read_text(encoding="utf-8")
        expected = render(target_text, source_text)
    except (OSError, SyncError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    if expected == target_text:
        print(f"✅ 共享段已同步（{', '.join(REGIONS)}）")
        return 0
    if args.write:
        TARGET.write_text(expected, encoding="utf-8")
        print(f"✅ 已重写 {TARGET.relative_to(ROOT)} 的共享段（{', '.join(REGIONS)}）")
        return 0
    print("❌ 共享段与 SKILL.md 不同步，运行 tools/sync_shared_docs.py --write 修复：",
          file=sys.stderr)
    diff = difflib.unified_diff(target_text.splitlines(), expected.splitlines(),
                                "references/full_workflow.md", "expected", lineterm="", n=1)
    for line in list(diff)[:40]:
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
