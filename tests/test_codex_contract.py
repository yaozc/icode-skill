import tempfile
import unittest
from pathlib import Path

from tools.lint_codex_contract import (
    COMMAND_ROUTES,
    MCP_THREE_STATE_TRUTH_SOURCES,
    PUBLIC_LIBRARY_CLAUSES,
    PUBLIC_LIBRARY_HOOK,
    lint_active_boundaries,
    lint_fast_risk_contract,
    lint_workflow_contract,
    lint_mcp_fallback_contract,
    lint_public_library_contract,
    lint_repo,
)


class BoundaryTests(unittest.TestCase):
    def make_root(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "steps").mkdir()
        (root / "mcp" / "demo").mkdir(parents=True)
        return temporary, root

    def test_active_claude_write_path_fails(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "steps" / "bad.md").write_text("write ~/.claude/config now\n", encoding="utf-8")
        self.assertTrue(lint_active_boundaries(root))

    def test_read_only_compatibility_line_passes(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "steps" / "ok.md").write_text("legacy read-only: ~/.claude/icode_data\n", encoding="utf-8")
        self.assertEqual(lint_active_boundaries(root), [])

    def test_legacy_allowlisted_installer_passes(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "mcp" / "demo" / "install.sh").write_text("write ~/.claude.json\n", encoding="utf-8")
        self.assertEqual(lint_active_boundaries(root), [])

    def test_active_legacy_installer_link_fails(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        (root / "steps" / "bad.md").write_text("run mcp/demo/install.sh\n", encoding="utf-8")
        self.assertTrue(lint_active_boundaries(root))

    def test_host_specific_mcp_fallback_fails(self) -> None:
        temporary, root = self.make_root()
        self.addCleanup(temporary.cleanup)
        for relative in MCP_THREE_STATE_TRUTH_SOURCES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("unavailable_before_call\n", encoding="utf-8")
        (root / "SKILL.md").write_text(
            'unavailable_before_call\nAgent(model="haiku")\n',
            encoding="utf-8",
        )
        self.assertTrue(lint_mcp_fallback_contract(root))


class RepositoryContractTests(unittest.TestCase):
    def test_public_library_evidence_layers_and_conditional_applicability(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_public_library_contract(root), [])

    def test_public_library_profile_cannot_be_weakened_or_hidden(self) -> None:
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = Path(__file__).resolve().parents[1]
            surfaces = ("references/domain-checklists.md", "steps/02_review.md",
                        "steps/05_deepcheck.md", "steps/06_audit.md")
            for relative in surfaces:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repository / relative, path)
            self.assertEqual(lint_public_library_contract(root), [])
            profile = root / surfaces[0]
            original = profile.read_text(encoding="utf-8")
            for clause in PUBLIC_LIBRARY_CLAUSES:
                for replacement in ("", f"<!-- {clause} -->", f"```text\n{clause}\n```",
                                    "Headers or a rebuilt consumer alone prove every compatibility layer."):
                    with self.subTest(clause=clause, replacement=replacement):
                        profile.write_text(original.replace(clause, replacement), encoding="utf-8")
                        self.assertTrue(lint_public_library_contract(root))
            profile.write_text(original, encoding="utf-8")
            for relative in surfaces[1:]:
                path = root / relative
                original_step = path.read_text(encoding="utf-8")
                path.write_text(original_step.replace(PUBLIC_LIBRARY_HOOK, "unrelated.md"), encoding="utf-8")
                self.assertTrue(any(relative in error for error in lint_public_library_contract(root)))
                path.write_text(original_step, encoding="utf-8")

    def test_workflow_hook_cannot_disappear_from_patch(self) -> None:
        import shutil
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        repository = Path(__file__).resolve().parents[1]
        for relative in ("SKILL.md", "references/codex_runtime.md", "references/dir_and_metadata.md",
                         "references/workflow_contract.md", "steps/verify.md", "steps/fast.md", "steps/01_plan.md",
                         "steps/02_review.md", "steps/03_merge.md", "steps/04_code.md", "steps/05_deepcheck.md",
                         "steps/06_audit.md", "steps/08_patch.md", "steps/status.md"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / relative, path)
        self.assertEqual(lint_workflow_contract(root), [])
        path = root / "steps/08_patch.md"
        path.write_text(path.read_text().replace("workflow-plan", "old-dispatch"))
        self.assertTrue(lint_workflow_contract(root))

    def test_risk_hook_cannot_disappear_from_a_downstream_step(self) -> None:
        import shutil
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        repository = Path(__file__).resolve().parents[1]
        for relative in ("SKILL.md", "steps/fast.md", "steps/01_plan.md", "steps/02_review.md",
                         "steps/03_merge.md", "steps/04_code.md", "steps/05_deepcheck.md", "steps/06_audit.md",
                         "references/dir_and_metadata.md", "references/codex_runtime.md", "references/fast_risk.md"):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / relative, destination)
        self.assertEqual(lint_fast_risk_contract(root), [])
        deepcheck = root / "steps/05_deepcheck.md"
        deepcheck.write_text(deepcheck.read_text().replace("workflow-plan", "missing-hook"))
        errors = lint_fast_risk_contract(root)
        self.assertTrue(any("steps/05_deepcheck.md" in error for error in errors))

    def test_mcp_fallback_contract_is_host_neutral_and_three_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_mcp_fallback_contract(root), [])

    def test_start_is_the_only_full_chain_route(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        plan_step = (root / "steps" / "01_plan.md").read_text(encoding="utf-8")
        directory_rules = (root / "references" / "dir_and_metadata.md").read_text(encoding="utf-8")
        self.assertEqual(COMMAND_ROUTES["start"], "steps/01_plan.md")
        self.assertNotIn("run", COMMAND_ROUTES)
        self.assertEqual(COMMAND_ROUTES["plan"], "steps/01_plan.md")
        self.assertFalse((root / "steps" / "run.md").exists())
        self.assertIn("`$icodex start` 是唯一标准全流程入口", skill)
        self.assertIn("`$icodex plan` 只执行步骤 1 后暂停", skill)
        self.assertNotIn("$icodex run", skill)
        self.assertIn("无参数时恢复最新未完成", skill)
        self.assertIn("单独调用 `plan` 随后停止", plan_step)
        self.assertIn("~/.codex/skills/icodex/tools/icode_state.py validate", plan_step)
        self.assertNotIn("python3 tools/icode_state.py validate", plan_step)
        self.assertIn("统一分派规则", plan_step)
        self.assertNotIn("立即继续执行步骤2", plan_step)
        self.assertIn("COMMAND=start|plan", directory_rules)
        self.assertIn("HAS_REQUIREMENT=1", directory_rules)
        self.assertIn("REUSE=1", directory_rules)
        resume_binding = 'if [ "$REUSE" = "1" ]; then\n  ICODE_OUT_DIR="$CAND"\nfi'
        self.assertIn(resume_binding, skill)
        self.assertIn(resume_binding, directory_rules)
        self.assertIn('if [ "$HAS_REQUIREMENT" = "0" ]; then', directory_rules)
        self.assertIn("无参数不得创建新目录", directory_rules)

    def test_crosscheck_is_persistent_but_target_read_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        step = (root / "steps" / "crosscheck.md").read_text(encoding="utf-8")
        self.assertEqual(COMMAND_ROUTES["crosscheck"], "steps/crosscheck.md")
        self.assertIn("$icodex crosscheck", skill)
        self.assertIn(".ai/icode/.crosscheck/", step)
        self.assertIn("不得修改目标工单", step)
        self.assertIn("$icodex-review", skill)

    def test_repository_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_repo(root), [])


if __name__ == "__main__":
    unittest.main()
