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
    "crosscheck": "steps/crosscheck.md",
    "verify": "steps/verify.md",
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
STALE_START_TEXT = (
    "`$icodex start` 永远只是 `$icodex plan`",
    "`start` 是 `plan` 的兼容别名",
    "`start` is a compatibility alias for `plan`",
    "`$icodex start` 不路由到本文件",
    "`plan/start` 随后停止",
    "`start` 不会串联后续步骤",
    "`$icodex plan` 与 `$icodex start` 都只执行步骤1",
    "`$icodex plan` and `$icodex start` execute only step 1",
)
STALE_RUN_COMMAND = re.compile(r"\$icodex\s+run\b")

MCP_FALLBACK_SURFACES = (
    "SKILL.md",
    "steps/fast.md",
    "references/anti_laziness.md",
    "references/mcp_integration.md",
    "references/mcp_per_step.md",
    "references/thinking_core.md",
    "mcp/cheap-research/README.md",
)
MCP_THREE_STATE_TRUTH_SOURCES = (
    "SKILL.md",
    "references/anti_laziness.md",
    "references/mcp_per_step.md",
    "references/thinking_core.md",
)
HOST_SPECIFIC_MCP_FALLBACKS = (
    (re.compile(r"Agent\s*\(\s*model\s*="), "Agent(model=...)"),
    (re.compile(r"Claude\s*家族最便宜模型"), "Claude-specific cheapest-model fallback"),
)

PUBLIC_LIBRARY_CLAUSES = (
    "Apply this profile only to an affected public library, package, or binding boundary and its compatibility promise.",
    "Source compatibility, binary ABI compatibility, and runtime behavior are separate claims.",
    "When backward binary compatibility is promised, exercise a preserved old consumer binary against the candidate without recompiling it.",
    "Missing baseline, artifact, compiler, or target environment leaves the corresponding layer unresolved.",
)
PUBLIC_LIBRARY_HOOK = "../references/domain-checklists.md#public-library-apiabi"

STATIC_READ_SURFACES = (
    "SKILL.md",
    "references/thinking_core.md",
    "references/thinking_detail.md",
    "references/anti_laziness.md",
    "references/mcp_integration.md",
    "references/workflow_contract.md",
    "steps/verify.md",
    "steps/06_audit.md",
)
STATIC_READ_HOOK = "thinking_core.md#静态-references-读取与复用合同"
STATIC_READ_CLAUSES = (
    "首次必须完整实读静态 references 正文并计算 SHA256。",
    "仅当绝对 skill 根、文件路径、SHA256 均一致，且完整正文仍在当前上下文时，才可复用。",
    "上下文压缩、正文丢失、切换 skill 根或内容变化时，必须重新完整实读并计算 SHA256。",
    "SHA256 只证明字节身份，不证明已实读；摘要、确认行和文件哈希不能替代完整正文。",
    "确认行必须区分实际实读与复用，并列出绝对 skill 根、文件路径和 SHA256。",
    "业务源码实读、每轮判断和 Read/worklist 登记不得复用。",
)
EXECUTION_EVIDENCE_CLAUSES = (
    "实际流程步骤、verification_runs[].id 或供应方执行标识必须与原始日志逐项对账。",
    "每次新执行必须使用新的执行标识和独立证据路径，保留独立原始日志，不覆盖旧执行。",
    "HANDOFF 只定位上下文，不是原始观测，不能替代原始日志或实际执行证据。",
    "同 ID 原样重放只是幂等登记，不是新执行。",
    "这些是报告证据要求，不新增 schema 字段，也不追补旧票的命名要求。",
)
MCP_EVIDENCE_CLAUSES = (
    "| 源码 |",
    "| 安装 |",
    "| 注册 |",
    "| 握手 |",
    "| 当前会话可用 |",
    "配置存在不等于当前会话可调用。",
    "源码、安装、注册、握手和当前会话可用不能混淆，也不是五种执行状态。",
    "called",
    "degraded_after_attempt",
    "unavailable_before_call",
    "attempted=false",
)
DEDUP_COVERAGE_HOOK = "mcp_integration.md#语义去重覆盖规则"
DEDUP_COVERAGE_CLAUSES = (
    "只有可信枚举才能判定低于阈值。",
    "枚举不完整或不可信时，记录未覆盖范围和原因，不能把未知计为零。",
    "工具不可用或调用失败时，记录实际核查范围和剩余覆盖缺口。",
    "仅当当前候选、范围与输入身份一致时复用目录或分类。",
)
STALE_STATIC_READ = re.compile(
    r"同会话已读不豁免|每步(?:必须|仍须)?重新\s*Read|每步必须重新读取"
)
MCP_EVIDENCE_SHORTCUTS = (
    re.compile(r"任一即视为[“\"']?(?:已配置)?可用"),
    re.compile(r"配置存在即(?:可用|可调用)"),
    re.compile(r"安装完成即可调用"),
    re.compile(r"握手成功即证明当前会话可用"),
)
EXECUTION_EVIDENCE_SHORTCUTS = (
    re.compile(r"HANDOFF\s*(?:即可|可以|可)(?:替代|作为)(?:原始日志|原始观测)"),
    re.compile(r"同\s*ID\s*(?:原样)?重放(?:就是|即为|视为|算作)新执行"),
    re.compile(r"新执行(?:可以|可|允许)复用(?:原始日志|旧证据路径)"),
)


def _contract_prose(text: str) -> str:
    """示例和注释不能充当活动合同条款。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(
        r"^[ \t]*(?:(?:[-+*]|\d+[.)])\s+)?(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$",
        "", text, flags=re.M | re.S,
    )
    return " ".join(text.split())


def lint_read_and_evidence_contract(root: Path) -> List[str]:
    """锁住文档证据边界；不声称静态 lint 能证明阅读或实际执行。"""
    errors: List[str] = []
    requirements = {
        "references/thinking_core.md": STATIC_READ_CLAUSES,
        "references/mcp_integration.md": MCP_EVIDENCE_CLAUSES + DEDUP_COVERAGE_CLAUSES,
        "references/mcp_per_step.md": (DEDUP_COVERAGE_HOOK,),
        "references/workflow_contract.md": EXECUTION_EVIDENCE_CLAUSES,
        "steps/verify.md": EXECUTION_EVIDENCE_CLAUSES,
        "steps/06_audit.md": EXECUTION_EVIDENCE_CLAUSES,
        "steps/02_review.md": (DEDUP_COVERAGE_HOOK,),
        "steps/05_deepcheck.md": (DEDUP_COVERAGE_HOOK,),
        "README.md": ("ICODEX_TEST_PYTHON_BIN", "sys.executable", "HANDOFF", "verification_runs[].id"),
        "README.zh-CN.md": ("ICODEX_TEST_PYTHON_BIN", "sys.executable", "HANDOFF", "verification_runs[].id"),
    }
    for relative in STATIC_READ_SURFACES:
        if relative != "references/thinking_core.md":
            requirements[relative] = requirements.get(relative, ()) + (STATIC_READ_HOOK,)
    for relative, clauses in requirements.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing read/execution evidence contract")
            continue
        prose = _contract_prose(path.read_text(encoding="utf-8"))
        for clause in clauses:
            if clause not in prose:
                errors.append(f"{relative}: missing read/execution evidence clause: {clause}")
        if relative in STATIC_READ_SURFACES and STALE_STATIC_READ.search(prose):
            errors.append(f"{relative}: unconditional static references reread conflicts with reuse contract")
        if relative in STATIC_READ_SURFACES and any(pattern.search(prose) for pattern in MCP_EVIDENCE_SHORTCUTS):
            errors.append(f"{relative}: MCP configuration/installation/handshake cannot prove session availability")
        if relative in STATIC_READ_SURFACES and any(pattern.search(prose) for pattern in EXECUTION_EVIDENCE_SHORTCUTS):
            errors.append(f"{relative}: replay/handoff/reused evidence cannot prove a new execution")
    return errors


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
    plan_step = (root / "steps/01_plan.md").read_text(encoding="utf-8")
    directory_rules = (root / "references/dir_and_metadata.md").read_text(encoding="utf-8")
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
    if COMMAND_ROUTES["start"] != "steps/01_plan.md":
        errors.append("SKILL.md: start must use steps/01_plan.md as the full-chain entry")
    if "run" in COMMAND_ROUTES:
        errors.append("SKILL.md: run must not be exposed as a command")
    if (root / "steps" / "run.md").exists():
        errors.append("steps/run.md: removed run route file must not exist")
    if COMMAND_ROUTES["plan"] != "steps/01_plan.md":
        errors.append("SKILL.md: plan must remain the single-step route")
    if "`$icodex start` 是唯一标准全流程入口" not in skill:
        errors.append("SKILL.md: start must be documented as the only standard full chain")
    if "`$icodex plan` 只执行步骤 1 后暂停" not in skill:
        errors.append("SKILL.md: plan must be documented as step 1 only")
    if "~/.codex/skills/icodex/tools/icode_state.py validate" not in plan_step:
        errors.append("steps/01_plan.md: resume validation must use the installed icodex helper")
    if "python3 tools/icode_state.py validate" in plan_step:
        errors.append("steps/01_plan.md: repository-relative resume validator is invalid in user projects")
    if "统一分派规则" not in plan_step or "立即继续执行步骤2" in plan_step:
        errors.append("steps/01_plan.md: start resume must dispatch to the actual next incomplete step")
    for marker in ("COMMAND=start|plan", "HAS_REQUIREMENT=1", "REUSE=1", "无参数不得创建新目录"):
        if marker not in directory_rules:
            errors.append(f"references/dir_and_metadata.md: incomplete directory decision contract: {marker}")
    for path in active_files(root):
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        if STALE_RUN_COMMAND.search(text):
            errors.append(f"{path.relative_to(root).as_posix()}: removed $icodex run command is still documented")
        for stale in STALE_START_TEXT:
            if stale in text:
                errors.append(f"{path.relative_to(root).as_posix()}: stale start-as-plan statement: {stale}")
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


def lint_mcp_fallback_contract(root: Path) -> List[str]:
    """Keep MCP degradation honest and independent from Claude-only APIs."""
    errors: List[str] = []
    for relative in MCP_FALLBACK_SURFACES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, label in HOST_SPECIFIC_MCP_FALLBACKS:
            if pattern.search(text):
                errors.append(f"{relative}: host-specific MCP fallback is forbidden: {label}")

    for relative in MCP_THREE_STATE_TRUTH_SOURCES:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing MCP fallback truth source")
            continue
        text = path.read_text(encoding="utf-8")
        if "unavailable_before_call" not in text:
            errors.append(f"{relative}: missing unavailable_before_call MCP state")
    return errors


def lint_fast_risk_contract(root: Path) -> List[str]:
    """防止文档只有升级声明，而实际步骤仍绕过风险分派。"""
    errors: List[str] = []
    surfaces = ("SKILL.md", "steps/fast.md", "steps/01_plan.md", "steps/02_review.md",
                "steps/03_merge.md", "steps/04_code.md", "steps/05_deepcheck.md", "steps/06_audit.md",
                "references/dir_and_metadata.md", "references/codex_runtime.md", "references/fast_risk.md")
    for relative in surfaces:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing fast risk contract")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("assess-fast-risk", "workflow-plan"):
            if marker not in text:
                errors.append(f"{relative}: missing fast risk execution hook: {marker}")
    risk_reference = root / "references/fast_risk.md"
    if risk_reference.is_file():
        text = risk_reference.read_text(encoding="utf-8")
        for marker in ("requested_mode", "effective_mode", "upgrade_snapshot", "artifact_map"):
            if marker not in text:
                errors.append(f"references/fast_risk.md: missing recovery boundary: {marker}")
    return errors


def lint_repo(root: Path) -> List[str]:
    return (
        lint_active_boundaries(root)
        + lint_links(root)
        + lint_routes(root)
        + lint_readme_parity(root)
        + lint_mcp_fallback_contract(root)
        + lint_fast_risk_contract(root)
        + lint_workflow_contract(root)
        + lint_public_library_contract(root)
        + lint_read_and_evidence_contract(root)
    )


def lint_public_library_contract(root: Path) -> List[str]:
    """只保护按需审查与证据分层规则，不判断具体工程是否兼容。"""
    errors: List[str] = []
    reference = root / "references/domain-checklists.md"
    if not reference.is_file():
        errors.append("references/domain-checklists.md: missing public library profile")
    else:
        content = reference.read_text(encoding="utf-8")
        content = re.sub(r"<!--.*?-->", "", content, flags=re.S)
        content = re.sub(r"^```[^\n]*\n.*?^```[ \t]*$", "", content, flags=re.M | re.S)
        match = re.search(r"^## Public Library API/ABI\n(.*?)(?=^## |\Z)", content, re.M | re.S)
        body = " ".join(match.group(1).split()) if match else ""
        for clause in PUBLIC_LIBRARY_CLAUSES:
            if clause not in body:
                errors.append(f"references/domain-checklists.md: missing public library boundary: {clause}")
    for relative in ("steps/02_review.md", "steps/05_deepcheck.md", "steps/06_audit.md"):
        path = root / relative
        if not path.is_file() or PUBLIC_LIBRARY_HOOK not in path.read_text(encoding="utf-8"):
            errors.append(f"{relative}: missing public library review hook")
    return errors


def lint_workflow_contract(root: Path) -> List[str]:
    """所有实际推进入口必须消费业务 gate，而不只是帮助里列出能力。"""
    errors: List[str] = []
    surfaces = ("SKILL.md", "references/codex_runtime.md", "references/dir_and_metadata.md",
                "steps/fast.md", "steps/01_plan.md", "steps/02_review.md", "steps/03_merge.md",
                "steps/04_code.md", "steps/05_deepcheck.md", "steps/06_audit.md", "steps/08_patch.md", "steps/status.md")
    for relative in surfaces:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing workflow contract surface")
            continue
        content = path.read_text(encoding="utf-8")
        for marker in ("workflow_contract.md", "workflow-plan", "verification-pending"):
            if marker not in content:
                errors.append(f"{relative}: missing workflow execution hook: {marker}")
    for relative, markers in {
        "references/workflow_contract.md": ("record-decision", "record-delta", "accept-replan", "verification-context", "analysis_only"),
        "steps/verify.md": ("verification-pending", "verification-plan", "verification-context", "record-verification"),
    }.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing workflow truth source")
        else:
            for marker in markers:
                if marker not in path.read_text(encoding="utf-8"):
                    errors.append(f"{relative}: missing workflow command: {marker}")
    return errors


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
