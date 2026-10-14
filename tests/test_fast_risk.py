"""风险语义由代理评估；这些回归验证确定性升级、恢复和同工单分派。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import icode_state as state

ROOT = Path(__file__).resolve().parents[1]
FLAGS = (
    "cross_component", "persistent_identity_change", "dependency_migration",
    "async_observer_or_cache", "restart_replay_semantics", "external_consumer_change",
    "real_env_verification", "unresolved_semantic_decision", "major_requirement_delta",
)
KEYS = ("plan", "plan_review", "final_plan", "implementation", "deepcheck", "audit")
STATUSES = ("plan_done", "review_done", "plan_finalized", "code_done", "deepcheck_done", "completed")


def assessment(*hits):
    return {"risk_flags": {key: key in hits for key in FLAGS},
            "evidence": {key: "fixture: affected" if key in hits else "fixture: examined and not affected" for key in FLAGS}}


class FastRiskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icodex-fast-risk-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / "project"
        self.run = self.project / ".ai/icode/icode_1"
        self.run.mkdir(parents=True)
        (self.project / "src").mkdir()
        (self.project / "src/example.py").write_text("value = 1\n")
        self.path = self.run / ".ico_metadata.json"
        self.create()

    def create(self, completed=1, mode="fast", status=None, entry=None):
        metadata = json.loads((ROOT / "tests/fixtures/metadata/staged_completed.json").read_text())
        metadata.update(mode=mode, workflow_kind="staged_" + mode,
                        ticket_id="fixture-1", project_path=str(self.project),
                        status=status or STATUSES[completed - 1],
                        max_rounds=1 if mode == "fast" else 3,
                        completed_steps=([entry] if entry else []) + [str(n) for n in range(1, completed + 1)])
        for index, key in enumerate(KEYS):
            if index >= completed:
                metadata["artifact_map"][key] = None
            else:
                (self.run / metadata["artifact_map"][key]).write_text(f"old fixture {key}\n")
        if entry:
            metadata["artifact_map"]["requirement"] = "00_init.md"
            (self.run / "00_init.md").write_text("fixture requirements\n")
        self.path.write_text(json.dumps(metadata))
        self.assertEqual(state.validate_metadata(metadata, self.run), [])
        return metadata

    def read(self):
        return json.loads(self.path.read_text())

    def test_each_upstream_risk_upgrades_same_ticket(self):
        self.assertEqual(state.FAST_RISK_TRIGGERS, FLAGS)
        for flag in FLAGS:
            with self.subTest(flag=flag):
                before = self.create()
                updated = state.assess_fast_risk(self.run, assessment(flag))
                self.assertEqual(updated["ticket_id"], before["ticket_id"])
                self.assertEqual(updated["artifact_map"], before["artifact_map"])
                self.assertEqual(updated["mode"], "full")
                self.assertEqual(updated["workflow_kind"], "staged_full")
                self.assertEqual(updated["max_rounds"], 3)
                self.assertEqual(updated["risk_profile"]["requested_mode"], "fast")
                self.assertEqual(updated["risk_profile"]["triggers"], [flag])
                plan = state.workflow_plan(self.run)
                self.assertEqual(plan["next_step"], 2)
                self.assertTrue(plan["review_adversarial"])
                self.assertEqual(plan["deepcheck_phases"], ["reverse", "fixed", "free"])
                self.assertEqual(plan["remaining_steps"], [2, 3, 4, 5, 6])

    def test_low_risk_keeps_fast_and_legacy_must_be_assessed_before_execution(self):
        before = self.path.read_bytes()
        self.assertEqual(state.validate_metadata(self.read(), self.run), [])
        with self.assertRaisesRegex(ValueError, "assessment"):
            state.workflow_plan(self.run)
        self.assertEqual(self.path.read_bytes(), before)
        state.assess_fast_risk(self.run, assessment())
        plan = state.workflow_plan(self.run)
        self.assertEqual(plan["effective_mode"], "fast")
        self.assertEqual(plan["review_max_rounds"], 1)
        self.assertFalse(plan["review_adversarial"])
        self.assertEqual(plan["deepcheck_phases"], ["reverse"])

    def test_invalid_assessments_do_not_write_metadata(self):
        cases = []
        for value in (0, "false", None):
            broken = assessment()
            broken["risk_flags"][FLAGS[0]] = value
            cases.append(broken)
        missing = assessment()
        del missing["risk_flags"][FLAGS[-1]]
        cases.append(missing)
        unknown = assessment()
        unknown["risk_flags"]["unknown_risk"] = True
        cases.append(unknown)
        empty = assessment()
        empty["evidence"][FLAGS[0]] = " "
        cases.append(empty)
        cases.extend(([], {}, {"risk_flags": []}))
        before = self.path.read_bytes()
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                state.assess_fast_risk(self.run, value)
            self.assertEqual(self.path.read_bytes(), before)

    def test_upgrade_is_sticky_idempotent_and_recovery_does_not_rewind_again(self):
        state.assess_fast_risk(self.run, assessment("async_observer_or_cache"))
        before = self.path.read_bytes()
        state.assess_fast_risk(self.run, assessment("async_observer_or_cache"))
        self.assertEqual(self.path.read_bytes(), before)
        updated = state.assess_fast_risk(self.run, assessment())
        self.assertEqual(updated["mode"], "full")
        self.assertEqual(updated["risk_profile"]["triggers"], ["async_observer_or_cache"])
        state.update_metadata(self.run, {"status": "review_in_progress", "total_rounds": 2})
        state.assess_fast_risk(self.run, assessment("real_env_verification"))
        self.assertEqual(self.read()["status"], "review_in_progress")
        self.assertEqual(self.read()["total_rounds"], 2)

    def test_late_upgrade_replays_full_chain_without_new_ticket_or_overwriting_old_files(self):
        before = self.create(completed=5, entry="0")
        originals = {relative: (self.run / relative).read_bytes()
                     for relative in before["artifact_map"].values() if relative}
        upgraded = state.assess_fast_risk(self.run, assessment("major_requirement_delta"))
        self.assertEqual(upgraded["completed_steps"], ["0", "1"])
        self.assertEqual(upgraded["status"], "plan_done")
        self.assertEqual(upgraded["risk_profile"]["upgrade_snapshot"]["artifact_map"], before["artifact_map"])
        self.assertEqual(upgraded["risk_profile"]["replay_from_step"], 2)
        state.assess_fast_risk(self.run, assessment())
        for number in range(2, 7):
            plan = state.workflow_plan(self.run)
            self.assertEqual(plan["next_step"], number)
            self.assertEqual(plan["review_max_rounds"], 3)
            self.assertEqual(plan["deepcheck_phases"], ["reverse", "fixed", "free"])
            key = KEYS[number - 1]
            name = json.loads((ROOT / "tests/fixtures/metadata/staged_completed.json").read_text())["artifact_map"][key]
            draft = self.run / "draft.tmp"
            draft.write_text(f"full fixture {key}\n")
            published = state.publish_artifact(self.run, key, draft, name)
            self.assertEqual(published.read_text(), f"full fixture {key}\n")
            state.update_metadata(self.run, {"status": STATUSES[number - 1],
                "completed_steps": ["0"] + [str(n) for n in range(1, number + 1)]})
        self.assertIsNone(state.workflow_plan(self.run)["next_step"])
        self.assertEqual(self.read()["ticket_id"], "fixture-1")
        self.assertEqual(list(self.run.parent.glob("icode_*")), [self.run])
        for relative, data in originals.items():
            self.assertEqual((self.run / relative).read_bytes(), data)
        self.assertEqual(state.validate_metadata(self.read(), self.run), [])
        self.assertEqual(state.validate_completed_run(self.run, self.project)["ticket_id"], "fixture-1")

    def test_in_progress_fast_review_is_restarted_at_full_round_one(self):
        self.create(status="review_in_progress")
        state.update_metadata(self.run, {"total_rounds": 1, "clean_rounds": 1})
        state.assess_fast_risk(self.run, assessment("cross_component"))
        self.assertEqual(self.read()["status"], "plan_done")
        self.assertEqual(self.read()["total_rounds"], 0)
        self.assertEqual(self.read()["clean_rounds"], 0)

    def test_late_upgrade_cannot_count_old_fast_artifacts_as_full_completion(self):
        self.create(completed=6)
        state.assess_fast_risk(self.run, assessment("cross_component"))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "newly published"):
            state.update_metadata(self.run, {"status": "completed", "completed_steps": list(state.STAGED_STEPS)})
        self.assertEqual(self.path.read_bytes(), before)
        old = self.run / self.read()["artifact_map"]["plan_review"]
        source = self.project / "same-review.md"
        source.write_bytes(old.read_bytes())
        published = state.publish_artifact(self.run, "plan_review", source, old.name)
        self.assertNotEqual(published, old)
        self.assertEqual(published.read_bytes(), old.read_bytes())
        state.update_metadata(self.run, {"status": "review_done", "completed_steps": ["1", "2"]})

    def test_concurrent_assessments_merge_risks_under_the_same_lock(self):
        commands = []
        for number, flag in enumerate(("cross_component", "async_observer_or_cache")):
            payload = self.project / f"risk-{number}.json"
            payload.write_text(json.dumps(assessment(flag)))
            commands.append([sys.executable, str(ROOT / "tools/icode_state.py"), "assess-fast-risk",
                "--run-dir", str(self.run), "--assessment-json", str(payload)])
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
        try:
            for proc in processes:
                stdout, stderr = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0, stderr)
                self.assertEqual(json.loads(stdout)["mode"], "full")
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)
        self.assertEqual(self.read()["risk_profile"]["triggers"], ["async_observer_or_cache", "cross_component"])

    def test_full_and_concise_legacy_validation_is_unaffected(self):
        self.create(mode="full", completed=3)
        plan = state.workflow_plan(self.run)
        self.assertEqual(plan["next_step"], 4)
        self.assertEqual(plan["effective_mode"], "full")
        state.assess_fast_risk(self.run, assessment("cross_component"))
        self.assertEqual(self.read()["completed_steps"], ["1", "2", "3"])
        concise = json.loads((ROOT / "tests/fixtures/metadata/concise_in_progress.json").read_text())
        for relative in filter(None, concise["artifact_map"].values()):
            (self.run / relative).write_text("concise fixture\n")
        self.path.write_text(json.dumps(concise))
        self.assertEqual(state.validate_metadata(concise, self.run), [])
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "staged"):
            state.assess_fast_risk(self.run, assessment("cross_component"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_metadata_gate_rejects_risk_profile_tampering_and_downgrade(self):
        state.assess_fast_risk(self.run, assessment("cross_component"))
        before = self.path.read_bytes()
        for updates in ({"mode": "fast"}, {"max_rounds": 1}, {"risk_profile": None}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                state.update_metadata(self.run, updates)
            self.assertEqual(self.path.read_bytes(), before)
        for field, value in (("effective_mode", "fast"), ("triggers", []), ("override", True)):
            metadata = self.read()
            metadata["risk_profile"][field] = value
            self.assertTrue(state.validate_metadata(metadata, self.run))

    def test_failed_atomic_publish_preserves_previous_state(self):
        before = self.path.read_bytes()
        with patch.object(state.os, "replace", side_effect=OSError("fixture publish failure")):
            with self.assertRaises(OSError):
                state.assess_fast_risk(self.run, assessment("cross_component"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.run.glob("*.tmp")), [])

    def test_low_risk_explicit_review_round_override_still_works(self):
        state.assess_fast_risk(self.run, assessment())
        state.update_metadata(self.run, {"max_rounds": 5, "status": "review_in_progress"})
        self.assertEqual(self.read()["max_rounds"], 5)
        self.assertEqual(state.workflow_plan(self.run)["effective_mode"], "fast")

    def test_malformed_metadata_and_sticky_upgrade_are_rejected(self):
        self.create(completed=3)
        state.assess_fast_risk(self.run, assessment("cross_component"))
        for field, value in (("artifact_map", ["wrong"]), ("completed_steps", 3)):
            metadata = self.read()
            metadata[field] = value
            self.assertTrue(state.validate_metadata(metadata, self.run))
        metadata = self.read()
        metadata.update(mode="fast", workflow_kind="staged_fast", max_rounds=1)
        metadata["risk_profile"].update(effective_mode="fast", triggers=[],
            risk_flags=assessment()["risk_flags"], evidence=assessment()["evidence"])
        self.assertTrue(state.validate_metadata(metadata, self.run))

    def test_cli_assessment_then_read_only_plan(self):
        payload = self.project / "assessment.json"
        payload.write_text(json.dumps(assessment("dependency_migration")))
        tool = str(ROOT / "tools/icode_state.py")
        result = subprocess.run([sys.executable, tool, "assess-fast-risk", "--run-dir", str(self.run),
            "--assessment-json", str(payload)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "full")
        before = self.path.read_bytes()
        result = subprocess.run([sys.executable, tool, "workflow-plan", "--run-dir", str(self.run)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["effective_mode"], "full")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
