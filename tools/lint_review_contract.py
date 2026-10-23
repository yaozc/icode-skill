#!/usr/bin/env python3
"""只读检查技能文档的关键规范；不解析目标工单或替模型做业务裁决。"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import List, Optional, Sequence
from urllib.parse import unquote

DOCUMENTS = ("SKILL.md", "README.md", "README.en.md", "references/domain-checklists.md",
             "references/workflow-contract.md", "agents/openai.yaml")
DOMAIN_CLAUSE = "Missing essential evidence is a gap; invalid mappings or evidence contradicting claimed completion/verification are confirmed violations."
DOMAIN_TOPICS = (
    "Inspect supplied public headers, exported symbols and old consumer binary evidence separately.",
    "A registered path or Read receipt is not evidence of actual review coverage.",
    "Compare test_summary with supplied runner output and the true process result.",
    "Inspect authorization provenance independently of scanner output and permission prose.",
    "Distinguish declared unordered membership from ordered observations and decisions.",
    "Review raw input limits, parser expansion and elapsed-time guarantees separately.",
)
RULE_CLAUSES = {
    "READ_ONLY": ("Disable lazy fetch with GIT_NO_LAZY_FETCH=1 for every Git read; missing objects are evidence gaps, never permission to fetch.",
                  "Disable pagers with --no-pager for every Git read, including terminal output.",
                  "Never execute code, hooks, helpers, tests, builds, or installers from the reviewed repository.",
                  "Never use working-tree git diff or status to obtain evidence; clean/process filters can execute despite the diff flags."),
    "SCOPE": ("An empty working-tree diff does not establish an empty review scope.",
              "Read registration does not prove actual reading or complete coverage.",
              "Source compatibility, binary ABI compatibility, and runtime behavior are separate claims.",
              "File budgets and batch registration never erase unread or unobserved coverage debt."),
    "ARTIFACTS": ("A staged run claiming completed step `2` must have a mapped `plan_review` artifact.",),
    "RISK": ("Use `effective_mode`, not `requested_mode`, to assess the required review and deepcheck work.",
             "Any triggered risk requires actual full mode."),
    "DECISIONS": ("Unresolved semantic decisions block implementation claims, not explicitly scoped diagnosis-only analysis.",
                  "Scanner success and permission notes do not establish action authorization.",
                  "A permission disclaimer is not a credential leak merely because it contains the word authorization."),
    "REPLAN": ("Old snapshot mappings cannot count as completed work in the current replan or upgrade generation.",
               "Only resolved major deltas accepted through replan require plan/revision; ordinary minor deltas do not."),
    "ACCEPTANCE": ("A non-empty acceptance matrix is not runtime proof.", "The matrix uses only these fixed keys.",
                   "A required acceptance matrix must cover all 16 phase/consumer expectations."),
    "EVIDENCE": (
        "For each required cell, the latest matching run wins; an older pass cannot replace a later failure.",
        "Evidence tied to a different source, contract, revision, or patch count cannot verify the selected candidate.",
        "Missing required cells or lifecycle proof prevents a final PASS.",
        "Host or simulated evidence cannot satisfy a physical requirement.",
        "Exit code 0 alone does not establish test success.",
        "Zero-case and all-skipped reports are inconclusive, not pass.",
        "Known process failures cannot be downgraded to inconclusive.",
        "When a test report is also explicit evidence, its summary hash must match evidence_hashes.",
        "A later pass without test_summary cannot replace current-candidate report-backed evidence for the same cell.",
        "Only fields explicitly defined as unordered sets may ignore member order.",
        "verification_runs, patch_history, event history and accepted prefixes remain ordered.",
        "Raw read budgets do not prove peak parser memory or hard elapsed-time bounds.",
        "Performance optimizations must not cache authorization or evidence eligibility.",
    ),
    "RESULTS": (
        "Confirmed violations take precedence: return FIX_REQUIRED even when evidence gaps also exist.",
        "Evidence gaps alone require SKIPPED, not an implementation failure.",
        "Workflow completed, delivery verified, direction verdict, and external review PASS are distinct conclusions.",
    ),
    "LEGACY": (
        "An absent workflow_contract_version is legacy, not automatically verified.",
        "An explicit unsupported version must not be treated as legacy.",
        "Missing or malformed schema-1 fields are confirmed violations.",
        "Do not require stage or provider fields from producers that do not implement those contracts.",
    ),
}
RULE_FIELDS = {
    "READ_ONLY": ("GIT_NO_LAZY_FETCH=1", "--no-pager", "core.fsmonitor=false", "--no-optional-locks", "--no-ext-diff", "--no-textconv"),
    "SCOPE": ("staged", "unstaged", "untracked", "--end-of-options", "source_hashes", "blob",
              "max_files", "attempt/phase", "public headers", "exported symbols", "old consumer binary",
              "--max-files", "--paths-json"),
    "ARTIFACTS": ("artifact_layout", "artifact_map", "completed_steps", "completed_phases", "code_files"),
    "RISK": ("max_rounds >= 3", "upgrade_snapshot", "replay_from_step", "Reverse/Fixed/Free"),
    "DECISIONS": ("semantic_decisions", "analysis_only", "authorization source", "credential", "scanner"),
    "REPLAN": ("requirement_deltas", "replan_state", "old_artifact_map", "accepted_plan", "pending_verification", "staged-only"),
    "ACCEPTANCE": ("acceptance_contract.required", "immediate", "converged", "restart", "replay",
                   "direct_query", "aggregate_selector", "persistent_reference", "external_projection"),
    "EVIDENCE": ("requirements_pending", "required_cells", "verification_runs", "baseline", "ticket_id",
                 "source_hashes", "contract_sha256", "replan_revision", "patch_count", "evidence_hashes",
                 "test_report", "test_summary", "test_exit_code", "passed", "failed", "skipped",
                 "patch_history", "duplicate", "peak", "soft", "PATH", "reload"),
    "RESULTS": ("implemented", "delivery_verdict", "verdict", "Final Decision"),
    "LEGACY": ("workflow_contract_version", "Schema 1", "replan_state", "verification_runs"),
}
REPORT_SECTIONS = ("Reviewer", "Inputs", "Root Cause Review", "Implementation Review",
                   "Architecture and Contract Review", "Workflow Contract Review", "Regression Review",
                   "Verification and Delivery Review", "Security Review", "Performance Review", "Findings", "Final Decision")
REPORT_GUIDANCE = {
    "Architecture and Contract Review": "Compare unordered membership only where the producer contract declares a set; retain ordered histories.",
    "Security Review": "Report the actual authorization source and action scope; scanner success or a note does not grant permission.",
    "Performance Review": "Separate raw read limits, parser memory and soft deadlines from observed hard resource bounds.",
}
README_CLAUSES = {
    "README.md": ("所有 Git 读取设置 GIT_NO_LAZY_FETCH=1 并使用 --no-pager；缺失对象作为证据缺口，不自动取回对象或执行远程 helper/pager。",
                  "已提交代码请提供 commit 或 base/head，不因工作树 diff 为空自动放行。",
                  "不得运行待审仓库的代码或 helper。", "已完成流程不等于业务验证通过。",
                  "仅缺证据时返回 SKIPPED；确定违规优先返回 FIX_REQUIRED。",
                  "契约检查仅验证文档规则和 Git 示例，不证明 AI 已正确执行审查。",
                  "工作区内容使用可信内建工具与原始提交/索引 blob 比较，不运行工作区 git diff/status，避免 clean/process filter。",
                  "退出码0不单独证明测试通过；零用例/全部跳过为 inconclusive，实际失败不能降级。",
                  "公共库按源码兼容、二进制 ABI 兼容、运行行为分别审查；Read 登记不等于实际阅读或覆盖完成。",
                  "扫描通过和权限说明不代表动作已授权；集合等价仅适用于明确的无序字段，有序历史不能重排。"),
    "README.en.md": ("Set GIT_NO_LAZY_FETCH=1 and --no-pager for every Git read; missing objects are evidence gaps and never authorize automatic fetch or remote helpers/pagers.",
                     "For committed code, supply commit or base/head; an empty working-tree diff never authorizes a pass.",
                     "Never execute code or helpers from the reviewed repository.",
                     "Workflow completion does not establish delivery verification.",
                     "Evidence gaps alone require SKIPPED; confirmed violations take precedence with FIX_REQUIRED.",
                     "The contract checker validates document rules and Git examples, not whether an AI correctly performed a review.",
                     "Compare working-tree content with raw commit/index blobs using trusted built-in tools; never use working-tree git diff/status because clean/process filters can execute.",
                     "Exit code 0 alone does not prove test success; zero/all-skipped cases are inconclusive and known failures cannot be downgraded.",
                     "Review source compatibility, binary ABI compatibility and runtime behavior separately; Read registration does not prove actual reading or complete coverage.",
                     "Scanner success and permission prose do not authorize actions; only explicitly unordered fields permit member permutations, while ordered histories retain their sequence."),
}
SAFE_GIT_TEMPLATES = (
    "rev-parse --verify --end-of-options <ref>^{commit}",
    "diff --cached --no-ext-diff --no-textconv --",
    "ls-files --stage -z",
    "ls-files --others --exclude-standard -z",
    "show --format=fuller --no-ext-diff --no-textconv <commit-sha> --",
    "diff --no-ext-diff --no-textconv <base-sha>..<head-sha> --",
    "cat-file blob <head-sha>:<relative-path>",
    "cat-file blob :<relative-path>",
)


def _visible(text: str) -> str:
    """注释或代码示例中的句子不能充当对审查者的规范正文。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"^```[^\n]*\n.*?^```[ \t]*$", "", text, flags=re.M | re.S)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _sections(text: str) -> dict:
    headers = list(re.finditer(r"^## (.+)$", text, re.M))
    return {m.group(1): text[m.end():headers[n + 1].start() if n + 1 < len(headers) else len(text)]
            for n, m in enumerate(headers)}


def lint_repo(root: Path) -> List[str]:
    """返回文档合同错误列表；不写缓存、报告、目标文件或 Git 索引。"""
    root = Path(root).resolve()
    errors, texts = [], {}
    for relative in DOCUMENTS:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"{relative}: missing regular document")
            continue
        try:
            path.resolve().relative_to(root)
            texts[relative] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as error:
            errors.append(f"{relative}: cannot read document: {error}")
    contract = texts.get("references/workflow-contract.md", "")
    sections = _sections(_visible(contract))
    for rule, clauses in RULE_CLAUSES.items():
        body = sections.get(rule, "")
        for clause in clauses:
            if _normalized(clause) not in _normalized(body):
                errors.append(f"references/workflow-contract.md: {rule}: missing normative clause: {clause}")
        # 代码模板也承载安全参数，但不能代替上面的规范正文。
        raw = _sections(contract).get(rule, "")
        for field in RULE_FIELDS[rule]:
            if field not in raw:
                errors.append(f"references/workflow-contract.md: {rule}: missing field: {field}")
    if len(re.findall(r"^## ", _visible(contract), re.M)) != len(RULE_CLAUSES):
        errors.append("references/workflow-contract.md: duplicate, missing or unexpected rule section")
    commands = re.findall(r"^(?:GIT_NO_LAZY_FETCH=\S+ )?git .+$", contract, re.M)
    expected_commands = tuple("GIT_NO_LAZY_FETCH=1 git --no-pager --no-optional-locks -c core.fsmonitor=false " + c for c in SAFE_GIT_TEMPLATES)
    if tuple(commands) != expected_commands:
        errors.append("references/workflow-contract.md: Git templates differ from exact read-only allowlist")

    skill = texts.get("SKILL.md", "")
    if not re.search(r"^name: icodex-review$", skill, re.M):
        errors.append("SKILL.md: wrong skill name")
    boundary = "It must not edit files, run formatters or generators, install MCPs, write metadata or artifacts, stage, commit, push, reset, clean, or implement fixes."
    if boundary not in _normalized(_visible(skill)):
        errors.append("SKILL.md: missing read-only boundary")
    reports = re.findall(r"```markdown\n(.*?)\n```", skill, re.S)
    if len(reports) != 1 or tuple(re.findall(r"^## (.+)$", reports[0], re.M)) != REPORT_SECTIONS:
        errors.append("SKILL.md: report headings differ from contract")
    else:
        report = _sections(reports[0])
        if _normalized(report["Final Decision"]) != "PASS / FIX_REQUIRED / SKIPPED":
            errors.append("SKILL.md: invalid Final Decision vocabulary")
        for title in REPORT_SECTIONS[2:-2]:
            expected = "PASS / FAIL / N/A / INSUFFICIENT_EVIDENCE" if title in ("Security Review", "Performance Review") else "PASS / FAIL / INSUFFICIENT_EVIDENCE"
            if not _normalized(report[title]).startswith(expected):
                errors.append(f"SKILL.md: invalid section vocabulary: {title}")
        for field in ("Review scope", "resolved SHA", "Changes inspected", "Verification output", "Test evidence"):
            if field not in report["Inputs"]:
                errors.append(f"SKILL.md: missing report input: {field}")
        for title, clause in REPORT_GUIDANCE.items():
            if _normalized(clause) not in _normalized(_visible(report[title])):
                errors.append(f"SKILL.md: {title}: missing report guidance: {clause}")
    for clause in (RULE_CLAUSES["ARTIFACTS"][0], RULE_CLAUSES["RESULTS"][0], RULE_CLAUSES["RESULTS"][1]):
        if _normalized(clause) not in _normalized(_visible(skill)):
            errors.append(f"SKILL.md: missing entry rule: {clause}")
    for relative, clauses in README_CLAUSES.items():
        visible = _normalized(_visible(texts.get(relative, "")))
        for clause in clauses:
            if _normalized(clause) not in visible:
                errors.append(f"{relative}: missing bilingual contract clause: {clause}")
        for marker in ("scope commit <commit>" if relative.endswith("en.md") else "范围 commit <commit>",
                       "head <head>", "plan_review", "effective_mode", "semantic_decisions", "replan_state",
                       "acceptance_contract", "required_cells", "verification_runs", "workflow_contract_version",
                       "python3 -B tools/lint_review_contract.py .", "python3 -B -m unittest discover -s tests -v"):
            if marker not in texts.get(relative, ""):
                errors.append(f"{relative}: missing scope/check example or field: {marker}")
    for relative, text in texts.items():
        if relative == "references/domain-checklists.md" and DOMAIN_CLAUSE not in _normalized(_visible(text)):
            errors.append(f"{relative}: missing scoped violation/evidence-gap distinction")
        if relative == "references/domain-checklists.md":
            for clause in DOMAIN_TOPICS:
                if clause not in _normalized(_visible(text)):
                    errors.append(f"{relative}: missing topic boundary: {clause}")
        if relative != "references/workflow-contract.md" and "workflow-contract.md" not in text:
            errors.append(f"{relative}: missing shared contract reference")
        if "`requirement`, `root_cause`, and `plan_review` are optional" in text:
            errors.append(f"{relative}: stale optional plan_review rule")
        if "Missing or invalid evidence is reported as an evidence gap" in text:
            errors.append(f"{relative}: stale rule classifies confirmed violations as evidence gaps")
        if relative.endswith(".md"):
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                target = target.split("#", 1)[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                candidate = (root / relative).parent / unquote(target.strip("<>"))
                try:
                    candidate.resolve().relative_to(root)
                    if not candidate.is_file() or candidate.is_symlink():
                        raise ValueError("missing regular link target")
                except (OSError, ValueError):
                    errors.append(f"{relative}: broken or escaping local link: {target}")
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    """打印缺失规则并返回0/1；不会修复输入文件或读取目标工单。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parents[1])
    errors = lint_repo(parser.parse_args(argv).root)
    for error in errors:
        print(error)
    print(f"Review document contract: {'FAIL' if errors else 'PASS'} ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
