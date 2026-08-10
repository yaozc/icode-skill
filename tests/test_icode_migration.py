import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tools.icode_state as state
from tools.icode_state import migrate_legacy_run


def migration_worker(project_root: str, legacy_run: str, codex_root: str, queue: multiprocessing.Queue) -> None:
    try:
        queue.put(("ok", str(migrate_legacy_run(Path(project_root), Path(legacy_run), Path(codex_root)))))
    except Exception as error:  # pragma: no cover - returned to the parent process
        queue.put(("error", repr(error)))


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.project = root / "project"
        self.legacy_root = self.project / ".icode_output"
        self.codex_root = root / "codex-data"
        self.legacy_root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_legacy_run(self, name: str = ".icode_output_1", ticket_id: str = "demo-1") -> Path:
        run = self.legacy_root / name
        run.mkdir()
        metadata = {
            "ticket_id": ticket_id,
            "status": "completed",
            "patch_count": 0,
            "patch_history": [],
            "code_files": ["src/demo.py"],
        }
        (run / ".ico_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (run / "01_plan.md").write_text("plan\n", encoding="utf-8")
        (run / "03_plan_final.md").write_text("final\n", encoding="utf-8")
        return run

    def test_successful_migration_and_idempotent_retry(self) -> None:
        legacy = self.make_legacy_run()
        target = migrate_legacy_run(self.project, legacy, self.codex_root)
        retried = migrate_legacy_run(self.project, legacy, self.codex_root)
        self.assertEqual(target, retried)
        migrated = json.loads((target / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(migrated["migration_state"], "completed")
        self.assertEqual(migrated["artifact_map"]["plan"], "01_plan.md")
        index = json.loads((self.codex_root / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["tickets"]), 1)
        self.assertEqual(index["tickets"][0]["migration_id"], migrated["migration_id"])
        self.assertTrue((legacy / "01_plan.md").is_file())

    def test_same_ticket_from_different_source_gets_unique_index_id(self) -> None:
        first = self.make_legacy_run(".icode_output_1", "demo-1")
        second = self.make_legacy_run(".icode_output_2", "demo-1")
        migrate_legacy_run(self.project, first, self.codex_root)
        migrate_legacy_run(self.project, second, self.codex_root)
        tickets = json.loads((self.codex_root / "index.json").read_text(encoding="utf-8"))["tickets"]
        self.assertEqual(len(tickets), 2)
        self.assertEqual(tickets[0]["ticket_id"], "demo-1")
        self.assertTrue(tickets[1]["ticket_id"].startswith("demo-1-migrated-"))

    def test_rejects_path_outside_legacy_container(self) -> None:
        outside = self.project / "outside"
        outside.mkdir()
        (outside / ".ico_metadata.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "below project .icode_output"):
            migrate_legacy_run(self.project, outside, self.codex_root)

    def test_rejects_symlink_in_legacy_tree(self) -> None:
        legacy = self.make_legacy_run()
        (legacy / "unsafe-link").symlink_to(legacy / "01_plan.md")
        with self.assertRaisesRegex(ValueError, "symlink or special file"):
            migrate_legacy_run(self.project, legacy, self.codex_root)

    def test_source_manifest_change_refuses_existing_target(self) -> None:
        legacy = self.make_legacy_run()
        migrate_legacy_run(self.project, legacy, self.codex_root)
        (legacy / "01_plan.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "旧源在迁移后发生变化"):
            migrate_legacy_run(self.project, legacy, self.codex_root)

    def test_index_failure_resumes_from_prepared_target(self) -> None:
        legacy = self.make_legacy_run()
        original_atomic_write = state._atomic_write_json

        def fail_index(path: Path, value: dict) -> None:
            if path == self.codex_root / "index.json":
                raise OSError("simulated index failure")
            original_atomic_write(path, value)

        with mock.patch.object(state, "_atomic_write_json", side_effect=fail_index):
            with self.assertRaisesRegex(OSError, "simulated index failure"):
                migrate_legacy_run(self.project, legacy, self.codex_root)

        targets = [path for path in (self.project / ".ai" / "icode").iterdir() if path.name.startswith("legacy-")]
        self.assertEqual(len(targets), 1)
        prepared = json.loads((targets[0] / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(prepared["migration_state"], "prepared")

        resumed = migrate_legacy_run(self.project, legacy, self.codex_root)
        self.assertEqual(resumed.resolve(), targets[0].resolve())
        completed = json.loads((resumed / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(completed["migration_state"], "completed")

    def test_concurrent_migrations_do_not_lose_index_entries(self) -> None:
        runs = [
            self.make_legacy_run(".icode_output_1", "demo-1"),
            self.make_legacy_run(".icode_output_2", "demo-2"),
        ]
        queue = multiprocessing.Queue()
        workers = [
            multiprocessing.Process(
                target=migration_worker,
                args=(str(self.project), str(run), str(self.codex_root), queue),
            )
            for run in runs
        ]
        for worker in workers:
            worker.start()
        results = [queue.get(timeout=10) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
        self.assertFalse([value for status, value in results if status == "error"])
        tickets = json.loads((self.codex_root / "index.json").read_text(encoding="utf-8"))["tickets"]
        self.assertEqual({ticket["ticket_id"] for ticket in tickets}, {"demo-1", "demo-2"})


if __name__ == "__main__":
    unittest.main()
