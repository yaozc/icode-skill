import tempfile
import unittest
from pathlib import Path

from tools.lint_codex_contract import lint_active_boundaries, lint_repo


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
    def test_repository_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(lint_repo(root), [])


if __name__ == "__main__":
    unittest.main()
