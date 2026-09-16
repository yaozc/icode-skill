import tempfile
import unittest
from pathlib import Path

from tools.lint_codex_contract import COMMAND_ROUTES, lint_active_boundaries, lint_repo


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


class RepositoryContractTests(unittest.TestCase):
    def test_start_and_run_share_full_chain_route(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        run_step = (root / "steps" / "run.md").read_text(encoding="utf-8")
        plan_step = (root / "steps" / "01_plan.md").read_text(encoding="utf-8")
        self.assertEqual(COMMAND_ROUTES["start"], "steps/run.md")
        self.assertEqual(COMMAND_ROUTES["start"], COMMAND_ROUTES["run"])
        self.assertEqual(COMMAND_ROUTES["plan"], "steps/01_plan.md")
        self.assertIn("`$icodex start` 是标准全流程入口", skill)
        self.assertIn("`$icodex plan` 只执行步骤 1 后暂停", skill)
        self.assertIn("行为完全一致", run_step)
        self.assertIn("单独调用 `plan` 随后停止", plan_step)

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
