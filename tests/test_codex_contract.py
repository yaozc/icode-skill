import tempfile
import unittest
from pathlib import Path

from tools.lint_codex_contract import (
    COMMAND_ROUTES,
    MCP_THREE_STATE_TRUTH_SOURCES,
    lint_active_boundaries,
    lint_mcp_fallback_contract,
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
