import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.icode_state import ARTIFACT_KEYS, validate_metadata


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


if __name__ == "__main__":
    unittest.main()
