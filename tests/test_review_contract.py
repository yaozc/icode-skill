"""文档合同反向回归与隔离 Git 命令实验；不评估模型业务裁决。"""
import hashlib
import difflib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import lint_review_contract as lint

ROOT = Path(__file__).resolve().parents[1]
SAFE_GIT_PREFIX = ("--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false")
TOPIC_RULES = (
    ("Read registration does not prove actual reading or complete coverage.",
     "Batch registration proves every file was read."),
    ("Source compatibility, binary ABI compatibility, and runtime behavior are separate claims.",
     "Matching headers prove binary ABI compatibility."),
    ("Exit code 0 alone does not establish test success.", "Exit code 0 establishes all tests passed."),
    ("Zero-case and all-skipped reports are inconclusive, not pass.", "Zero-case reports pass."),
    ("Known process failures cannot be downgraded to inconclusive.", "Process failure may be inconclusive."),
    ("When a test report is also explicit evidence, its summary hash must match evidence_hashes.",
     "A report summary may disagree with the saved evidence hash."),
    ("A later pass without test_summary cannot replace current-candidate report-backed evidence for the same cell.",
     "A later uncounted pass replaces report-backed failure."),
)
PRECISE_RULES = (
    ("Scanner success and permission notes do not establish action authorization.",
     "A scanner pass grants permission for deployment."),
    ("A permission disclaimer is not a credential leak merely because it contains the word authorization.",
     "Every occurrence of authorization proves a credential leak."),
    ("Only fields explicitly defined as unordered sets may ignore member order.",
     "Every array may be compared as an unordered set."),
    ("verification_runs, patch_history, event history and accepted prefixes remain ordered.",
     "Sort and deduplicate verification_runs before deciding the latest result."),
    ("Raw read budgets do not prove peak parser memory or hard elapsed-time bounds.",
     "A 64 MiB input cap proves peak memory stays below 64 MiB."),
    ("Performance optimizations must not cache authorization or evidence eligibility.",
     "Cache an old authorization or evidence eligibility result to reduce checking."),
    ("File budgets and batch registration never erase unread or unobserved coverage debt.",
     "A larger file budget removes all unread coverage debt."),
    ("Do not require stage or provider fields from producers that do not implement those contracts.",
     "All schema-1 producers must provide stage and provider fields."),
)
EXECUTION_RULES = (
    ("EVIDENCE", "Verification registration and receipt replay do not establish a new execution.",
     "Registration and receipt replay prove a new execution."),
    ("EVIDENCE", "run_id names an existing verification id or supplied execution identity; it is not a new schema field.",
     "Every stored verification must add a run_id field."),
    ("EVIDENCE", "HANDOFF is a continuity summary, not an original runtime observation.",
     "HANDOFF replaces original runtime observations."),
    ("EVIDENCE", "Each new actual execution needs independently identifiable original output; exact same-id replay preserves the original receipt.",
     "New executions overwrite old output and exact retries require new paths."),
    ("EVIDENCE", "Source presence, installed artifacts, static registration, handshake and current-session callability are separate evidence layers.",
     "Static registration proves all MCP evidence layers."),
    ("EVIDENCE", "Keep MCP outcomes called, degraded_after_attempt and unavailable_before_call unchanged.",
     "Replace the three MCP outcomes with configured or missing."),
    ("EVIDENCE", "Review supplied MCP observations without running discovery, handshake, installation or target helpers to fill gaps.",
     "Run target discovery and handshake to fill missing MCP evidence."),
    ("LEGACY", "Execution identity and phase descriptions do not add required fields or naming rules to historical records.",
     "Historical records require new execution fields and paths."),
    ("READ_ONLY", "Reject symbolic links, directory links and Windows LX symlink tag 0xA000001D before resolving any root, parent or leaf.",
     "Resolve paths first and reject every reparse point."),
)
EXECUTION_REPORT = {
    "Inputs": "Execution evidence: declared step, observed phase, run_id (existing id or supplied execution identity), original path/hash, candidate, environment and observation window; mark missing proof.",
    "Workflow Contract Review": "Distinguish declared workflow step, lifecycle cell.phase and crosscheck round phase; do not add run_id or stage fields to old schemas.",
    "Verification and Delivery Review": "Compare registration with actual execution identity, phase and independent original output; HANDOFF and same-id replay are not new observations.",
}
MCP_REPORT = "Separate source, installation, registration, handshake and current-session callability; consume supplied observations and retain the three MCP outcomes."
EXECUTION_READMES = {
    "README.md": (
        "登记和同ID重放不等于新执行；run_id仅指既有id或供应方执行标识，不新增schema字段或追补旧票。",
        "新实际执行保留可独立定位的原始输出；HANDOFF仅作续接摘要，不能替代原始观测。",
        "源码、安装、注册、握手、当前会话可调用分层核对；保持called/degraded_after_attempt/unavailable_before_call，不为补证运行发现、握手、安装或目标helper。",
        "linter在resolve前检查根、父级和叶子的普通链接及LX tag 0xA000001D，不按reparse属性一刀切；报告解析器原有更严格策略不变。",
    ),
    "README.en.md": (
        "Registration and same-id replay do not establish a new execution; run_id names an existing id or supplied execution identity, without new schema fields or retroactive migration.",
        "Each new actual execution keeps independently identifiable original output; HANDOFF is only a continuity summary and cannot replace original observations.",
        "Review source, installation, registration, handshake and current-session callability separately; retain called/degraded_after_attempt/unavailable_before_call without running discovery, handshake, installation or target helpers to fill gaps.",
        "Before resolve, the linter checks roots, parents and leaves for ordinary links and LX tag 0xA000001D, without rejecting all reparse points; the report parser retains its stricter policy.",
    ),
}
EXECUTION_DOMAIN = (
    "Reconcile verification registration with original execution observations; HANDOFF and replay are not new runtime evidence.",
    "Separate source, installation, registration, handshake and current-session MCP evidence without performing target operations.",
)


class DocumentContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icodex-review-doc-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "skill"
        self.original = {}
        for name in lint.DOCUMENTS:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            self.original[name] = (ROOT / name).read_bytes(); path.write_bytes(self.original[name])

    def edit(self, name, old, new):
        text = self.original[name].decode()
        self.assertIn(old, text)
        (self.root / name).write_text(text.replace(old, new), encoding="utf-8")

    def test_current_documents_pass(self):
        self.assertEqual(lint.lint_repo(ROOT), [])
        self.assertEqual(lint.lint_repo(self.root), [])

    def test_execution_rules_reject_removal_inversion_and_hidden_text(self):
        name = "references/workflow-contract.md"
        for section, clause, opposite in EXECUTION_RULES:
            for replacement in ("", opposite, f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                with self.subTest(clause=clause, replacement=replacement):
                    self.edit(name, clause, replacement)
                    self.assertTrue(any(section in error for error in lint.lint_repo(self.root)))

    def test_execution_report_guidance_is_normative_in_existing_sections(self):
        for title, clause in {**EXECUTION_REPORT, "Performance Review": MCP_REPORT}.items():
            for replacement in ("", "The opposite rule applies.", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                with self.subTest(title=title, replacement=replacement):
                    self.edit("SKILL.md", clause, replacement)
                    self.assertTrue(lint.lint_repo(self.root))

    def test_execution_bilingual_guidance_cannot_be_hidden_or_reversed(self):
        for name, clauses in EXECUTION_READMES.items():
            for clause in clauses:
                for replacement in ("", "相反结论 / opposite conclusion", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                    with self.subTest(name=name, clause=clause, replacement=replacement):
                        self.edit(name, clause, replacement)
                        self.assertTrue(any(name in error for error in lint.lint_repo(self.root)))
                (self.root / name).write_bytes(self.original[name])

    def test_execution_domain_guidance_cannot_be_hidden_or_reversed(self):
        name = "references/domain-checklists.md"
        for clause in EXECUTION_DOMAIN:
            for replacement in ("", "The opposite rule applies.", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                with self.subTest(clause=clause, replacement=replacement):
                    self.edit(name, clause, replacement)
                    self.assertTrue(any(name in error for error in lint.lint_repo(self.root)))

    def test_legacy_target_metadata_is_not_read_or_migrated(self):
        target = self.root / ".ai/icode/legacy"
        target.mkdir(parents=True)
        metadata = target / ".ico_metadata.json"
        metadata.write_text('{"verification_runs":[{"id":"old"}]}')
        handoff = target / "HANDOFF.md"
        handoff.write_text("Historical summary; no original execution proof.\n")
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (metadata, handoff)}
        read_text = Path.read_text

        def document_only(path, *args, **kwargs):
            self.assertNotIn(target, path.parents, "linter must not inspect target runs")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", document_only):
            self.assertEqual(lint.lint_repo(self.root), [])
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_real_symlink_root_and_root_parent_are_rejected(self):
        alias = self.root.parent / "root-link"
        alias.symlink_to(self.root, target_is_directory=True)
        parent = self.root.parent / "parent-link"
        parent.symlink_to(self.root.parent, target_is_directory=True)
        for root in (alias, parent / self.root.name):
            with self.subTest(root=root):
                self.assertTrue(any("link" in e for e in lint.lint_repo(root)))

    def test_real_document_parent_link_inside_root_is_rejected(self):
        directory = self.root / "references"
        actual = self.root / "real-references"
        directory.rename(actual)
        directory.symlink_to(actual, target_is_directory=True)
        self.assertTrue(any("references/workflow-contract.md" in e and "link" in e
                            for e in lint.lint_repo(self.root)))

    def test_markdown_links_reject_leaf_and_parent_links_inside_root(self):
        notes = self.root / "notes"
        notes.mkdir()
        (notes / "actual.md").write_text("ordinary local document\n")
        (notes / "linked.md").symlink_to(notes / "actual.md")
        alias = self.root / "notes-link"
        alias.symlink_to(notes, target_is_directory=True)
        for target in ("notes/linked.md", "notes-link/actual.md", "notes-link/../README.md"):
            with self.subTest(target=target):
                self.edit("README.md", "references/workflow-contract.md", target)
                self.assertTrue(any("broken or escaping local link" in e for e in lint.lint_repo(self.root)))

    def test_windows_link_tags_reject_document_and_markdown_components(self):
        notes = self.root / "notes"
        notes.mkdir()
        ordinary = notes / "actual.md"
        ordinary.write_text("ordinary local document\n")
        (self.root / "README.md").write_text(
            self.original["README.md"].decode() + "\n[Local note](notes/actual.md)\n", encoding="utf-8")
        lstat = Path.lstat
        read_text = Path.read_text
        suspects = (self.root / "README.en.md", self.root / "references", ordinary, notes)
        for tag in (0xA000001D, 0xA000000C, 0xA0000003):
            for suspect in suspects:
                def tagged(path, *args, **kwargs):
                    result = lstat(path, *args, **kwargs)
                    if path == suspect:
                        return SimpleNamespace(st_mode=result.st_mode, st_reparse_tag=tag,
                                               st_file_attributes=0x400)
                    return result

                def no_follow(path, *args, **kwargs):
                    self.assertFalse(path == suspect or suspect in path.parents,
                                     "link components must be rejected before reading")
                    return read_text(path, *args, **kwargs)

                with self.subTest(tag=hex(tag), suspect=suspect):
                    with patch.object(Path, "lstat", tagged), patch.object(Path, "read_text", no_follow):
                        errors = lint.lint_repo(self.root)
                    self.assertTrue(any("link" in e for e in errors))

    def test_lx_root_and_ancestor_rejected_before_resolve(self):
        lstat = Path.lstat
        resolve = Path.resolve
        for suspect in (self.root, self.root.parent):
            def tagged(path, *args, **kwargs):
                result = lstat(path, *args, **kwargs)
                if path == suspect:
                    return SimpleNamespace(st_mode=result.st_mode, st_reparse_tag=0xA000001D)
                return result

            def no_resolve(path, *args, **kwargs):
                self.assertFalse(path == suspect or suspect in path.parents,
                                 "LX identity must be checked before resolve")
                return resolve(path, *args, **kwargs)

            with self.subTest(suspect=suspect):
                with patch.object(Path, "lstat", tagged), patch.object(Path, "resolve", no_resolve):
                    errors = lint.lint_repo(self.root)
                self.assertTrue(any("link" in e for e in errors))

    def test_non_link_reparse_components_remain_readable(self):
        notes = self.root / "notes"
        notes.mkdir()
        (notes / "ordinary.md").write_text("ordinary document\n")
        (self.root / "README.md").write_text(
            self.original["README.md"].decode() + "\n[Local note](notes/ordinary.md)\n", encoding="utf-8")
        lstat = Path.lstat

        def non_link(path, *args, **kwargs):
            result = lstat(path, *args, **kwargs)
            return SimpleNamespace(st_mode=result.st_mode, st_reparse_tag=0x80000020,
                                   st_file_attributes=0x400)

        with patch.object(Path, "lstat", non_link):
            self.assertEqual(lint.lint_repo(self.root), [])

    def test_test_truth_abi_and_coverage_contracts_are_present(self):
        text = (self.root / "references/workflow-contract.md").read_text()
        for clause, _ in TOPIC_RULES:
            self.assertIn(clause, text)

    def test_new_topics_reject_inversions_hidden_clauses_and_omissions(self):
        name = "references/workflow-contract.md"
        for clause, opposite in TOPIC_RULES:
            for replacement in ("", opposite, f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                with self.subTest(clause=clause, replacement=replacement):
                    self.edit(name, clause, replacement)
                    self.assertTrue(lint.lint_repo(self.root))

    def test_specialized_checklists_cannot_be_removed_or_hidden(self):
        for clause in ("Inspect supplied public headers, exported symbols and old consumer binary evidence separately.",
                       "A registered path or Read receipt is not evidence of actual review coverage.",
                       "Compare test_summary with supplied runner output and the true process result."):
            for replacement in ("", f"<!-- {clause} -->"):
                self.edit("references/domain-checklists.md", clause, replacement)
                self.assertTrue(lint.lint_repo(self.root))

    def test_authorization_order_and_resource_contracts_are_present(self):
        text = (self.root / "references/workflow-contract.md").read_text()
        for clause, _ in PRECISE_RULES:
            with self.subTest(clause=clause):
                self.assertIn(clause, text)

    def test_precise_rules_reject_inversions_hidden_clauses_and_omissions(self):
        name = "references/workflow-contract.md"
        for clause, opposite in PRECISE_RULES:
            for replacement in ("", opposite, f"<!-- {clause} -->", f"```text\n{clause}\n```"):
                with self.subTest(clause=clause, replacement=replacement):
                    self.edit(name, clause, replacement)
                    self.assertTrue(lint.lint_repo(self.root))

    def test_precise_report_instructions_cannot_be_hidden_or_reversed(self):
        for clause in (
                "Compare unordered membership only where the producer contract declares a set; retain ordered histories.",
                "Report the actual authorization source and action scope; scanner success or a note does not grant permission.",
                "Separate raw read limits, parser memory and soft deadlines from observed hard resource bounds."):
            for replacement in ("", "The opposite rule applies.", f"<!-- {clause} -->"):
                with self.subTest(clause=clause, replacement=replacement):
                    self.edit("SKILL.md", clause, replacement)
                    self.assertTrue(lint.lint_repo(self.root))

    def test_precise_domain_checks_cannot_be_removed_or_hidden(self):
        for clause in (
                "Inspect authorization provenance independently of scanner output and permission prose.",
                "Distinguish declared unordered membership from ordered observations and decisions.",
                "Review raw input limits, parser expansion and elapsed-time guarantees separately."):
            for replacement in ("", f"<!-- {clause} -->"):
                with self.subTest(clause=clause, replacement=replacement):
                    self.edit("references/domain-checklists.md", clause, replacement)
                    self.assertTrue(lint.lint_repo(self.root))

    def test_precise_rule_failure_cli_does_not_repair_documents_or_execute_target_helpers(self):
        clause = PRECISE_RULES[0][0]
        self.edit("references/workflow-contract.md", clause, "A scanner pass grants deployment permission.")
        # 目标项目内容不是本检查器的输入；真实 CLI 失败也不得执行或修复它。
        marker = self.root / "executed.marker"
        helper = self.root / "target-helper.py"
        helper.write_text("from pathlib import Path\nPath(__file__).with_name('executed.marker').write_text('ran')\n")
        before = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/lint_review_contract.py"), str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DECISIONS", result.stdout)
        self.assertFalse(marker.exists())
        self.assertEqual({p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
                          for p in self.root.rglob("*") if p.is_file()}, before)

    def test_each_required_clause_removal_is_detected(self):
        for rule, clauses in lint.RULE_CLAUSES.items():
            for clause in clauses:
                with self.subTest(rule=rule, clause=clause):
                    self.edit("references/workflow-contract.md", clause, "")
                    self.assertTrue(any(rule in error for error in lint.lint_repo(self.root)))

    def test_specific_unsafe_inversions_are_detected(self):
        pairs = (
            ("A staged run claiming completed step `2` must have a mapped `plan_review` artifact.", "plan_review is optional even after step 2."),
            (lint.RULE_CLAUSES["LEGACY"][1], "Unsupported versions are legacy."),
            (lint.RULE_CLAUSES["EVIDENCE"][0], "An older pass may replace a later failure."),
            (lint.RULE_CLAUSES["EVIDENCE"][1], "A different baseline may verify the candidate."),
            (lint.RULE_CLAUSES["EVIDENCE"][2], "Missing required proof permits a final PASS."),
            (lint.RULE_CLAUSES["EVIDENCE"][3], "Host evidence satisfies a physical requirement."),
            (lint.RULE_CLAUSES["REPLAN"][0], "Old mappings complete a new replan generation."),
            (lint.RULE_CLAUSES["DECISIONS"][0], "Open decisions permit implemented delivery."),
            (lint.RULE_CLAUSES["RESULTS"][0], "Evidence gaps hide confirmed violations with SKIPPED."),
            ("Any triggered risk requires actual full mode.", "Triggered risks may remain fast."),
            ("The matrix uses only these fixed keys.", "The matrix may omit any key."),
            ("Missing or malformed schema-1 fields are confirmed violations.", "Malformed schema-1 fields permit PASS."),
        )
        for old, new in pairs:
            with self.subTest(old=old):
                self.edit("references/workflow-contract.md", old, new)
                self.assertTrue(lint.lint_repo(self.root))

    def test_rule_names_or_hidden_sentences_cannot_replace_normative_body(self):
        name = "references/workflow-contract.md"
        clause = lint.RULE_CLAUSES["EVIDENCE"][0]
        for replacement in ("EVIDENCE", f"<!-- {clause} -->", f"```text\n{clause}\n```"):
            self.edit(name, clause, replacement)
            self.assertTrue(lint.lint_repo(self.root))

    def test_missing_fields_and_duplicate_sections_are_detected(self):
        name = "references/workflow-contract.md"
        for old, new in (("## EVIDENCE", "## RESULTS"), ("contract_sha256", "wrong_digest"),
                         ("replan_revision", "wrong_revision"), ("analysis_only", "wrong_intent")):
            self.edit(name, old, new)
            self.assertTrue(lint.lint_repo(self.root))

    def test_each_bilingual_boundary_is_guarded(self):
        for name, clauses in lint.README_CLAUSES.items():
            for clause in clauses:
                self.edit(name, clause, "相反结论 / opposite conclusion")
                self.assertTrue(lint.lint_repo(self.root))
                (self.root / name).write_bytes(self.original[name])

    def test_report_headers_vocabulary_and_scope_stay_compatible(self):
        for old, new in (("## Regression Review", "## Regressions"),
                         ("PASS / FIX_REQUIRED / SKIPPED", "verified / pending"),
                         ("PASS / FAIL / N/A / INSUFFICIENT_EVIDENCE", "PASS"),
                         ("resolved SHA(s)", "unknown ref"), ("## Workflow Contract Review", "## Contract")):
            self.edit("SKILL.md", old, new)
            self.assertTrue(lint.lint_repo(self.root))

    def test_old_optional_review_clause_cannot_be_reintroduced(self):
        path = self.root / "SKILL.md"
        path.write_text(path.read_text() + "\n`requirement`, `root_cause`, and `plan_review` are optional\n")
        self.assertTrue(lint.lint_repo(self.root))

    def test_old_evidence_gap_rule_cannot_hide_confirmed_violations(self):
        path = self.root / "references/domain-checklists.md"
        path.write_text(path.read_text() + "\nMissing or invalid evidence is reported as an evidence gap\n")
        self.assertTrue(lint.lint_repo(self.root))
        for replacement in ("", "Missing or invalid evidence is reported as an evidence gap.",
                            "Missing essential evidence is a gap; invalid mappings or contradictory evidence are confirmed violations."):
            self.edit("references/domain-checklists.md", lint.DOMAIN_CLAUSE, replacement)
            self.assertTrue(lint.lint_repo(self.root))

    def test_command_safety_is_checked_per_template(self):
        name = "references/workflow-contract.md"
        for old, new in (("--no-pager --no-optional-locks", "--no-optional-locks"),
                         ("GIT_NO_LAZY_FETCH=1 git", "git"),
                         ("GIT_NO_LAZY_FETCH=1 git", "GIT_NO_LAZY_FETCH=0 git"),
                         ("diff --cached --no-ext-diff", "diff --cached --ext-diff"),
                         ("show --format=fuller --no-ext-diff --no-textconv", "show --format=fuller --no-ext-diff"),
                         ("rev-parse --verify --end-of-options", "rev-parse --verify"),
                         ("git --no-pager --no-optional-locks -c core.fsmonitor=false ls-files", "git ls-files")):
            self.edit(name, old, new)
            self.assertTrue(lint.lint_repo(self.root))

    def test_safe_command_allowlist_rejects_writes_and_late_option_overrides(self):
        name = "references/workflow-contract.md"
        for old, new in (("cat-file blob <head-sha>:<relative-path>", "clean -fd # blob <head-sha>:<relative-path>"),
                         ("cat-file blob <head-sha>:<relative-path>", "push # blob <head-sha>:<relative-path>"),
                         ("diff --cached --no-ext-diff --no-textconv", "diff --cached --no-ext-diff --no-textconv --textconv"),
                         ("core.fsmonitor=false ls-files", "core.fsmonitor=false -c core.fsmonitor=true ls-files")):
            self.edit(name, old, new)
            self.assertTrue(lint.lint_repo(self.root))

    def test_links_references_missing_files_and_utf8_are_checked(self):
        path = self.root / "README.md"
        for target in ("missing.md", "../outside.md"):
            self.edit("README.md", "references/workflow-contract.md", target)
            self.assertTrue(lint.lint_repo(self.root))
        path.write_bytes(b"\xff")
        self.assertTrue(lint.lint_repo(self.root))
        path.unlink()
        self.assertTrue(lint.lint_repo(self.root))
        path.symlink_to(ROOT / "README.md")
        self.assertTrue(lint.lint_repo(self.root))

    def test_cli_is_read_only_and_reports_failure(self):
        before = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/lint_review_contract.py"), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        self.edit("README.md", lint.README_CLAUSES["README.md"][2], "")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/lint_review_contract.py"), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.md", result.stdout)


@unittest.skipUnless(shutil.which("git"), "Git command fixtures require Git")
class GitScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icodex-review-git-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        (self.root / "empty-hooks").mkdir()
        self.git("init", "-q", "--template=" + str(self.root / "empty-hooks"))
        self.git("config", "user.name", "Review fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.file = self.root / "example.txt"; self.file.write_text("first\n")
        self.git("add", "example.txt"); self.commit("root")
        self.first = self.safe("rev-parse", "HEAD").stdout.strip()

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True, check=check, timeout=10)

    def safe(self, *args, check=True):
        env = dict(self.env, GIT_NO_LAZY_FETCH="1")
        return subprocess.run(["git", *SAFE_GIT_PREFIX, *args],
                              cwd=self.root, env=env, capture_output=True, text=True, check=check, timeout=10)

    def commit(self, message):
        self.git("-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + str(self.root / "empty-hooks"), "commit", "-qm", message)

    def diff(self, *args):
        return self.safe("diff", "--no-ext-diff", "--no-textconv", *args).stdout

    def resolve(self, ref, check=True):
        return self.safe("rev-parse", "--verify", "--end-of-options", ref + "^{commit}", check=check)

    def dirty(self, before="HEAD"):
        # 原始 blob 与工作区字节比较，不触发目标仓库的内容转换程序。
        blob = "HEAD:example.txt" if before == "HEAD" else ":example.txt"
        old = self.safe("cat-file", "blob", blob).stdout
        return "".join(difflib.unified_diff(old.splitlines(keepends=True), self.file.read_text().splitlines(keepends=True)))

    def test_clean_tree_root_commit_still_has_reviewable_change(self):
        self.assertEqual(self.dirty(), "")
        resolved = self.resolve(self.first).stdout.strip()
        self.assertEqual(resolved, self.first)
        content = self.safe("show", "--format=fuller", "--no-ext-diff", "--no-textconv", resolved, "--").stdout
        self.assertIn("+first", content)

    def test_staged_only_and_staged_plus_unstaged_are_both_visible(self):
        self.file.write_text("staged\n"); self.git("add", "example.txt")
        self.assertEqual(self.dirty("index"), "")
        self.assertIn("+staged", self.diff("--cached", "--"))
        self.file.write_text("unstaged\n")
        self.assertIn("+staged", self.diff("--cached", "--"))
        self.assertIn("+unstaged", self.dirty("index"))
        self.assertIn("+unstaged", self.dirty())

    def test_cancelled_net_diff_does_not_hide_index_change(self):
        self.file.write_text("staged\n"); self.git("add", "example.txt")
        self.file.write_text("first\n")
        self.assertEqual(self.dirty(), "")
        self.assertIn("+staged", self.diff("--cached", "--"))
        self.assertIn("+first", self.dirty("index"))

    def test_untracked_source_is_inventory_evidence(self):
        (self.root / "new source.py").write_text("new = True\n")
        self.assertEqual(self.dirty(), "")
        inventory = self.safe("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
        self.assertIn("new source.py", inventory)

    def test_exact_range_and_old_candidate_hash_are_independent_of_worktree(self):
        self.file.write_text("second\n"); self.git("add", "example.txt"); self.commit("second")
        second = self.resolve("HEAD").stdout.strip()
        self.file.write_text("third\n")
        content = self.diff(self.first + ".." + second, "--")
        self.assertIn("+second", content); self.assertNotIn("+third", content)
        old = self.safe("cat-file", "blob", self.first + ":example.txt").stdout.encode()
        self.assertEqual(hashlib.sha256(old).hexdigest(), hashlib.sha256(b"first\n").hexdigest())
        self.assertNotEqual(hashlib.sha256(old).hexdigest(), hashlib.sha256(self.file.read_bytes()).hexdigest())

    def test_option_like_and_missing_refs_cannot_select_a_commit(self):
        for ref in ("--help", "--output=unexpected", "missing-ref", "HEAD;touch injected"):
            result = self.resolve(ref, check=False)
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "injected").exists())

    def test_git_reads_disable_configuration_driven_programs_and_index_writes(self):
        script = self.root / "probe.py"
        script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('executed')\nprint('converted')\n")
        markers = {kind: self.root / (kind + ".marker") for kind in ("external", "textconv", "fsmonitor")}
        command = lambda kind: shlex.join([sys.executable, str(script), str(markers[kind])])
        # 正控制证明探针可执行；被测 Git 读取不得执行它们。
        for marker in markers.values():
            subprocess.run([sys.executable, str(script), str(marker)], check=True, capture_output=True)
            self.assertTrue(marker.exists()); marker.unlink()
        self.git("config", "diff.external", command("external"))
        self.git("config", "diff.review.textconv", command("textconv"))
        self.git("config", "core.fsmonitor", command("fsmonitor"))
        (self.root / ".gitattributes").write_text("*.txt diff=review\n")
        self.env["GIT_EXTERNAL_DIFF"] = command("external")
        self.file.write_text("changed\n")
        index = self.root / ".git/index"
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        self.dirty(); self.dirty("index"); self.diff("--cached", "--")
        self.safe("show", "--format=fuller", "--no-ext-diff", "--no-textconv", self.first, "--")
        self.safe("ls-files", "--others", "--exclude-standard", "-z")
        self.safe("ls-files", "--stage", "-z")
        self.resolve(self.first)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertTrue(all(not marker.exists() for marker in markers.values()))

    def test_worktree_clean_and_process_filters_are_not_executed(self):
        script = self.root / "filter.py"
        marker = self.root / "filter.marker"
        script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('executed')\nprint('converted')\n")
        command = shlex.join([sys.executable, str(script), str(marker)])
        (self.root / ".gitattributes").write_text("*.txt filter=review\n")
        self.file.write_text("changed\n")
        for driver in ("clean", "process"):
            with self.subTest(driver=driver):
                if marker.exists(): marker.unlink()
                self.git("config", "filter.review." + driver, command)
                # 旧工作区diff的正控制只运行自建探针，证明配置入口可执行程序。
                self.safe("diff", "--no-ext-diff", "--no-textconv", "HEAD", "--", check=False)
                self.assertTrue(marker.exists()); marker.unlink()
                self.dirty()
                self.dirty("index")
                self.safe("ls-files", "--stage", "-z")
                self.diff("--cached", "--")
                self.assertFalse(marker.exists())

    def test_missing_promisor_blob_cannot_execute_remote_helper(self):
        marker = self.root / "remote.marker"
        blob = self.safe("rev-parse", "HEAD:example.txt").stdout.strip()
        self.git("config", "extensions.partialClone", "origin")
        self.git("config", "remote.origin.promisor", "true")
        self.git("config", "remote.origin.url", "ext::touch " + str(marker))
        self.git("config", "protocol.ext.allow", "always")
        (self.root / ".git/objects" / blob[:2] / blob[2:]).unlink()
        # 有效提交缺失blob的正控制证明lazy fetch可启动自建remote探针。
        self.git("cat-file", "blob", "HEAD:example.txt", check=False)
        self.assertTrue(marker.exists()); marker.unlink()
        result = self.safe("cat-file", "blob", "HEAD:example.txt", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_tty_reads_cannot_execute_configured_pager(self):
        script = self.root / "pager.py"
        marker = self.root / "pager.marker"
        script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('executed')\n")
        self.git("config", "core.pager", shlex.join([sys.executable, str(script), str(marker)]))
        master, slave = os.openpty()
        try:
            env = dict(self.env, GIT_NO_LAZY_FETCH="1", TERM="xterm")
            args = ("show", "--format=fuller", "--no-ext-diff", "--no-textconv", self.first, "--")
            def tty_read(prefix):
                return subprocess.run(["git", *prefix, *args], cwd=self.root, env=env,
                                      stdin=subprocess.DEVNULL, stdout=slave, stderr=subprocess.PIPE, timeout=10)
            # 管道输出不会启用pager；用PTY正控制验证真实的配置执行入口。
            tty_read(("--no-optional-locks", "-c", "core.fsmonitor=false"))
            self.assertTrue(marker.exists()); marker.unlink()
            result = tty_read(SAFE_GIT_PREFIX)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
        finally:
            os.close(slave); os.close(master)


if __name__ == "__main__":
    unittest.main()
