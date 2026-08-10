import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.icode_state import (
    ARTIFACT_KEYS,
    finalize_patch,
    iter_merged_files,
    load_merged_index,
    merged_source_digest,
    publish_artifact,
    reserve_patch_number,
    update_metadata,
    upsert_index_entry,
    validate_metadata,
)


FIXTURES = Path(__file__).parent / "fixtures" / "metadata"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def materialize_mapped_files(run_dir: Path, metadata: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for relative_path in set(filter(None, metadata["artifact_map"].values())):
        target = run_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture\n", encoding="utf-8")


class MetadataValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_artifact_keys_are_stable(self) -> None:
        self.assertEqual(
            ARTIFACT_KEYS,
            (
                "requirement",
                "root_cause",
                "plan",
                "plan_review",
                "final_plan",
                "implementation",
                "deepcheck",
                "audit",
                "patches",
                "delivery_report",
                "delivery_brief",
            ),
        )

    def test_concise_fixture_is_valid(self) -> None:
        metadata = load_fixture("concise_in_progress.json")
        materialize_mapped_files(self.run_dir, metadata)
        self.assertEqual(validate_metadata(metadata, self.run_dir), [])

    def test_rejects_out_of_order_completed_phases(self) -> None:
        metadata = load_fixture("concise_in_progress.json")
        metadata["completed_phases"] = ["diagnose", "implement"]
        materialize_mapped_files(self.run_dir, metadata)
        self.assertIn(
            "completed_phases must be an ordered prefix",
            validate_metadata(metadata, self.run_dir),
        )

    def test_staged_fixture_is_valid(self) -> None:
        metadata = load_fixture("staged_completed.json")
        materialize_mapped_files(self.run_dir, metadata)
        self.assertEqual(validate_metadata(metadata, self.run_dir), [])

    def test_rejects_staged_step_gap(self) -> None:
        metadata = load_fixture("staged_completed.json")
        metadata["completed_steps"] = ["1", "3"]
        materialize_mapped_files(self.run_dir, metadata)
        self.assertIn(
            "completed_steps must be an ordered prefix",
            validate_metadata(metadata, self.run_dir),
        )

    def test_rejects_staged_status_mismatch(self) -> None:
        metadata = load_fixture("staged_completed.json")
        metadata["status"] = "code_done"
        materialize_mapped_files(self.run_dir, metadata)
        self.assertIn(
            "status is inconsistent with completed_steps",
            validate_metadata(metadata, self.run_dir),
        )

    def test_requires_patch_artifact_when_patch_count_is_positive(self) -> None:
        metadata = load_fixture("staged_completed.json")
        metadata["patch_count"] = 1
        materialize_mapped_files(self.run_dir, metadata)
        self.assertIn(
            "artifact_map.patches is required when patch_count > 0",
            validate_metadata(metadata, self.run_dir),
        )

    def test_rejects_artifact_path_escape(self) -> None:
        metadata = copy.deepcopy(load_fixture("concise_in_progress.json"))
        metadata["artifact_map"]["plan"] = "../PLAN.md"
        materialize_mapped_files(self.run_dir, metadata)
        self.assertIn(
            "artifact_map.plan escapes the run directory",
            validate_metadata(metadata, self.run_dir),
        )

    def test_rejects_inconsistent_full_phase(self) -> None:
        metadata = load_fixture("concise_in_progress.json")
        metadata["current_phase"] = "audit"
        materialize_mapped_files(self.run_dir, metadata)
        self.assertIn(
            "current_phase must be the next incomplete phase",
            validate_metadata(metadata, self.run_dir),
        )

    def test_publish_artifact_updates_mapping_after_file_publish(self) -> None:
        metadata = load_fixture("concise_in_progress.json")
        metadata["completed_phases"] = ["diagnose"]
        metadata["current_phase"] = "plan"
        metadata["artifact_map"]["plan"] = None
        metadata["artifact_map"]["final_plan"] = None
        materialize_mapped_files(self.run_dir, metadata)
        (self.run_dir / ".ico_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        source = self.run_dir / "draft.tmp"
        source.write_text("approved plan\n", encoding="utf-8")

        published = publish_artifact(self.run_dir, "plan", source, "PLAN.md")

        updated = json.loads((self.run_dir / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(published.read_text(encoding="utf-8"), "approved plan\n")
        self.assertEqual(updated["artifact_map"]["plan"], "PLAN.md")

    def test_first_artifact_can_atomically_create_metadata(self) -> None:
        source = self.run_dir / "draft.tmp"
        source.write_text("first plan\n", encoding="utf-8")
        seed = {
            "status": "plan_done",
            "completed_steps": ["1"],
        }
        publish_artifact(self.run_dir, "plan", source, "01_plan.md", seed)
        metadata = json.loads((self.run_dir / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["artifact_map"]["plan"], "01_plan.md")
        self.assertEqual(metadata["workflow_kind"], "staged_full")
        self.assertEqual(set(metadata["artifact_map"]), set(ARTIFACT_KEYS))
        self.assertEqual(validate_metadata(metadata, self.run_dir), [])

    def test_update_metadata_rejects_invalid_transition(self) -> None:
        metadata = load_fixture("concise_in_progress.json")
        materialize_mapped_files(self.run_dir, metadata)
        (self.run_dir / ".ico_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "current_phase"):
            update_metadata(self.run_dir, {"current_phase": "audit"})

    def test_patch_reservation_publish_and_finalize(self) -> None:
        metadata = load_fixture("staged_completed.json")
        materialize_mapped_files(self.run_dir, metadata)
        (self.run_dir / ".ico_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        number = reserve_patch_number(self.run_dir)
        source = self.run_dir / "patch-draft.tmp"
        source.write_text("# Patch 1\n", encoding="utf-8")
        publish_artifact(self.run_dir, "patches", source, "08_patch.md")
        entry = finalize_patch(self.run_dir, number, "completed", "verified patch")
        updated = json.loads((self.run_dir / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(updated["patch_history"][0]["summary"], "verified patch")
        self.assertEqual(validate_metadata(updated, self.run_dir), [])


class MergedViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.codex_root = root / "codex"
        self.claude_root = root / "claude"
        self.codex_root.mkdir()
        self.claude_root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_index(self, root: Path, tickets: list) -> None:
        (root / "index.json").write_text(json.dumps({"tickets": tickets}), encoding="utf-8")

    def test_same_id_different_sources_remain_visible(self) -> None:
        self.write_index(
            self.codex_root,
            [{"ticket_id": "demo-1", "out_dir": "/new/run", "status": "completed"}],
        )
        self.write_index(
            self.claude_root,
            [{"ticket_id": "demo-1", "out_dir": "/old/run", "status": "plan_done"}],
        )
        tickets = load_merged_index(self.codex_root, self.claude_root)["tickets"]
        self.assertEqual(len(tickets), 2)
        self.assertEqual(tickets[0]["ticket_id"], "demo-1")
        self.assertTrue(tickets[1]["ticket_id"].startswith("legacy:demo-1:"))

    def test_overlay_only_changes_mutable_fields(self) -> None:
        legacy = {"ticket_id": "demo-2", "out_dir": "/old/two", "status": "plan_done", "hit_count": 1}
        overlay = {
            "ticket_id": "legacy:demo-2:abcd1234",
            "legacy_ticket_id": "demo-2",
            "legacy_source": "/old/two",
            "legacy_overlay": True,
            "hit_count": 4,
            "status": "completed",
        }
        self.write_index(self.codex_root, [overlay])
        self.write_index(self.claude_root, [legacy])
        ticket = load_merged_index(self.codex_root, self.claude_root)["tickets"][0]
        self.assertEqual(ticket["hit_count"], 4)
        self.assertEqual(ticket["status"], "plan_done")

    def test_files_use_codex_precedence_and_digest_tracks_content(self) -> None:
        for root, content in ((self.claude_root, "old"), (self.codex_root, "new")):
            target = root / "project_docs" / "demo" / "overview.md"
            target.parent.mkdir(parents=True)
            target.write_text(content, encoding="utf-8")
        files = iter_merged_files("project_docs", self.codex_root, self.claude_root)
        self.assertEqual([(item.key, item.source) for item in files], [("demo/overview.md", "codex")])
        before = merged_source_digest(self.codex_root, self.claude_root)
        (self.codex_root / "project_docs" / "demo" / "overview.md").write_text("changed", encoding="utf-8")
        self.assertNotEqual(before, merged_source_digest(self.codex_root, self.claude_root))

    def test_index_upsert_preserves_other_entries(self) -> None:
        self.write_index(self.codex_root, [{"ticket_id": "demo-1", "status": "plan_done"}])
        upsert_index_entry(self.codex_root, {"ticket_id": "demo-2", "status": "completed"})
        tickets = json.loads((self.codex_root / "index.json").read_text(encoding="utf-8"))["tickets"]
        self.assertEqual({ticket["ticket_id"] for ticket in tickets}, {"demo-1", "demo-2"})

    def test_overlay_rejects_immutable_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "immutable fields"):
            upsert_index_entry(
                self.codex_root,
                {
                    "ticket_id": "legacy:demo-1:abc",
                    "legacy_overlay": True,
                    "legacy_ticket_id": "demo-1",
                    "legacy_source": "/old/run",
                    "status": "completed",
                },
            )


if __name__ == "__main__":
    unittest.main()
