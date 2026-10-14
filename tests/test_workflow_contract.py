"""合同门控、原工单重计划和交付证据失效的回归。"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from tools import icode_state as state
from tools import workflow_contract as contract
from tests.test_fast_risk import assessment

ROOT = Path(__file__).resolve().parents[1]


def cell(environment="host", phase=None):
    result = dict(layer="physical" if environment == "physical" else "unit", consumer="direct_query",
                  scenario="regression", environment=environment)
    if phase:
        result["phase"] = phase
    return result


def verification(cells=None):
    return dict(required=True, requirements_pending=False, required_cells=cells or [cell()])


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icodex-workflow-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / "project"
        self.run = self.project / ".ai/icode/icode_1"
        self.run.mkdir(parents=True)
        (self.project / "src").mkdir()
        (self.project / "src/example.py").write_text("value = 1\n")
        (self.project / "evidence.log").write_text("actual result\n")
        self.path = self.run / ".ico_metadata.json"
        metadata = json.loads((ROOT / "tests/fixtures/metadata/staged_completed.json").read_text())
        metadata.update(project_path=str(self.project), ticket_id="project-1", mode="full", max_rounds=3,
                        pending_verification=[{"id": "review-hypothesis"}])
        for name in metadata["artifact_map"].values():
            if name:
                (self.run / name).write_text("old artifact\n")
        self.path.write_text(json.dumps(metadata))

    def read(self):
        return json.loads(self.path.read_text())

    def change(self, action, value):
        return state.workflow_change(self.run, action, value)

    def configure(self, value=None):
        return self.change("configure-workflow", {"verification_contract": value or verification()})

    def decision(self, status="open"):
        return dict(id="policy", status=status, question="retain or replace?", evidence="user requirement section 2",
                    **({"decision": "retain; explicitly authorized"} if status == "resolved" else {}))

    def delta(self, identity="delta-1"):
        return dict(id=identity, severity="major", needs_replan=True, summary="new external behavior", evidence="user added lifecycle requirement")

    def record(self, identity="run-1", outcome="pass", target=None, baseline=None):
        return dict(id=identity, cell=target or cell(), outcome=outcome, summary="actual isolated execution",
                    baseline=baseline or state.verification_query(self.run, "verification-context"), evidence=["evidence.log"])

    def assert_rejected_unchanged(self, function, pattern=None):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, pattern or "."):
            function()
        self.assertEqual(self.path.read_bytes(), before)

    def test_new_seed_enables_version_and_legacy_requires_explicit_migration(self):
        self.assertEqual(state.validate_metadata(self.read(), self.run), [])
        self.assertEqual(state.verification_query(self.run)["delivery_verdict"], "not_assessed")
        seed_run = self.run.parent / "icode_2"
        seed = dict(status="plan_done", completed_steps=["1"], mode="full", max_rounds=3)
        draft = self.project / "plan.md"
        draft.write_text("plan\n")
        state.publish_artifact(seed_run, "plan", draft, "01_plan.md", seed)
        new = json.loads((seed_run / ".ico_metadata.json").read_text())
        self.assertEqual(new["workflow_contract_version"], 1)
        del new["semantic_decisions"]
        self.assertTrue(contract.schema_errors(new))
        self.configure()
        self.assertEqual(self.read()["workflow_contract_version"], 1)

    def test_semantic_gate_blocks_state_and_publish_before_side_effects(self):
        self.configure()
        self.change("record-decision", self.decision())
        self.assertIn("unresolved semantic", state.workflow_plan(self.run)["blocking_reasons"][0])
        self.assert_rejected_unchanged(lambda: state.update_metadata(self.run, {"status": "code_in_progress", "completed_steps": ["1", "2", "3"]}), "blocked")
        draft = self.project / "draft.md"
        draft.write_text("proposed plan\n")
        self.assert_rejected_unchanged(lambda: state.publish_artifact(self.run, "plan", draft, "blocked/new.md"), "blocked")
        self.assertFalse((self.run / "blocked").exists())
        self.change("record-decision", self.decision("resolved"))
        self.assertEqual(state.workflow_plan(self.run)["blocking_reasons"], [])
        self.assert_rejected_unchanged(lambda: self.change("record-decision", self.decision()), "immutable")

    def test_patch_intent_preserves_diagnosis_and_blocks_resume(self):
        self.configure()
        normal = state.reserve_patch_number(self.run)
        draft = self.project / "patch.md"
        draft.write_text("patch record\n")
        state.publish_artifact(self.run, "patches", draft, "08_patch.md")
        self.change("record-decision", self.decision())
        self.assert_rejected_unchanged(lambda: state.reserve_patch_number(self.run), "blocked")
        self.assert_rejected_unchanged(lambda: state.finalize_patch(self.run, normal, "completed"), "blocked")
        self.assert_rejected_unchanged(lambda: state.publish_artifact(self.run, "patches", draft, "blocked.md"), "blocked")
        diagnostic = state.reserve_patch_number(self.run, "analysis_only")
        state.publish_artifact(self.run, "patches", draft, "08_patch.md", patch_number=diagnostic)
        self.assert_rejected_unchanged(lambda: state.finalize_patch(self.run, diagnostic, "completed"), "analysis_only")
        state.finalize_patch(self.run, diagnostic, "analysis_only")

    def test_major_delta_replays_same_ticket_preserving_old_files_and_review_hypotheses(self):
        self.configure()
        metadata = self.read()
        originals = {n: (self.run / n).read_bytes() for n in metadata["artifact_map"].values() if n}
        # 已完成 fast 的旧产物不能计入新 full；旧风险 replay 与 replan 共存。
        state.update_metadata(self.run, {"mode": "fast", "workflow_kind": "staged_fast", "max_rounds": 1})
        state.assess_fast_risk(self.run, assessment("cross_component"))
        updated = self.change("record-delta", self.delta())
        self.assertEqual(updated["pending_verification"], [{"id": "review-hypothesis"}])
        state.update_metadata(self.run, {"pending_verification": [{"id": "new-hypothesis"}]})
        before = self.path.read_bytes()
        self.change("record-delta", self.delta())
        self.assertEqual(self.path.read_bytes(), before)
        route = state.workflow_plan(self.run)
        self.assertEqual(route["next_step"], 1)
        self.assertEqual(route["effective_mode"], "full")
        self.assert_rejected_unchanged(lambda: self.change("accept-replan", {}), "newly published")
        self.assert_rejected_unchanged(lambda: state.update_metadata(self.run, {"status": "completed", "completed_steps": list(state.STAGED_STEPS)}))
        draft = self.project / "new.md"
        draft.write_text("revised plan\n")
        plan = state.publish_artifact(self.run, "plan", draft, "01_plan.md")
        self.assertIn("replan/1", str(plan))
        self.change("accept-replan", {})
        statuses = ("review_done", "plan_finalized", "code_done", "deepcheck_done", "completed")
        for number, key, status in zip(range(2, 7), contract.STEP_KEYS[1:], statuses):
            published = state.publish_artifact(self.run, key, draft, metadata["artifact_map"][key])
            self.assertEqual(state.publish_artifact(self.run, key, draft, metadata["artifact_map"][key]), published)
            state.update_metadata(self.run, {"status": status, "completed_steps": [str(n) for n in range(1, number + 1)]})
        self.assertEqual(self.read()["ticket_id"], "project-1")
        self.assertEqual(self.read()["pending_verification"], [{"id": "new-hypothesis"}])
        for name, data in originals.items():
            self.assertEqual((self.run / name).read_bytes(), data)
        self.assertEqual(state.validate_completed_run(self.run, self.project)["ticket_id"], "project-1")

    def test_delta_preserves_review_hypotheses_and_rejects_downgrade_or_minor_replan(self):
        self.configure()
        self.change("record-delta", self.delta())
        self.assertEqual(self.read()["pending_verification"], [{"id": "review-hypothesis"}])
        self.assert_rejected_unchanged(lambda: state.update_metadata(self.run, {"mode": "fast"}), "full")
        broken = dict(self.delta("minor"), severity="minor", needs_replan=True)
        self.assert_rejected_unchanged(lambda: self.change("record-delta", broken))

    def test_lifecycle_expectations_and_proofs_are_separate(self):
        self.configure()
        state.assess_fast_risk(self.run, assessment("persistent_identity_change"))
        self.assertEqual(len(contract.acceptance_gaps(self.read())), 16)
        self.assertIn("matrix", state.workflow_plan(self.run)["blocking_reasons"][0])
        matrix = {p: {c: "expected survivor set" for c in contract.CONSUMERS} for p in contract.PHASES}
        self.change("configure-workflow", {"acceptance_contract": dict(required=True, matrix=matrix)})
        self.assertEqual(state.workflow_plan(self.run)["blocking_reasons"], [])
        report = state.verification_query(self.run)
        self.assertEqual(report["delivery_verdict"], "verification_pending")
        self.assertEqual(sum(d["reason"] == "lifecycle_verification_missing" for d in report["pending"]), 16)
        cells = [dict(cell(phase=p), consumer=c) for p in contract.PHASES for c in contract.CONSUMERS]
        self.configure(verification(cells))
        baseline = state.verification_query(self.run, "verification-context")
        for number, target in enumerate(cells):
            self.change("record-verification", self.record(str(number), target=target, baseline=baseline))
        self.assertEqual(state.verification_query(self.run)["delivery_verdict"], "verified")

    def test_real_environment_debt_cannot_be_disabled_or_satisfied_by_host(self):
        self.configure()
        state.assess_fast_risk(self.run, assessment("real_env_verification"))
        self.assert_rejected_unchanged(lambda: self.configure(dict(required=False, requirements_pending=False, required_cells=[])), "disabled")
        self.change("record-verification", self.record())
        self.assertEqual(state.verification_query(self.run)["delivery_verdict"], "verification_pending")
        self.configure(verification([cell("physical")]))
        self.change("record-verification", self.record("physical-result", target=cell("physical")))
        self.assertEqual(state.verification_query(self.run)["delivery_verdict"], "verified")

    def test_stale_execution_baseline_contract_and_candidate_are_rejected(self):
        self.configure()
        result = self.record()
        (self.project / "src/example.py").write_text("value = 2\n")
        self.assert_rejected_unchanged(lambda: self.change("record-verification", result), "baseline")
        result = self.record()
        self.configure(verification([dict(cell(), scenario="changed")]))
        self.assert_rejected_unchanged(lambda: self.change("record-verification", result), "baseline")

    def test_latest_failure_and_changed_evidence_keep_debt(self):
        self.configure()
        result = self.record()
        self.change("record-verification", result)
        before = self.path.read_bytes()
        self.change("record-verification", result)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(state.verification_query(self.run)["delivery_verdict"], "verified")
        (self.project / "evidence.log").write_text("changed evidence\n")
        self.assertEqual(state.verification_query(self.run)["pending"][0]["reason"], "stale_evidence")
        self.change("record-verification", self.record("failed", "fail"))
        self.assertEqual(state.verification_query(self.run)["pending"][0]["reason"], "fail")
        (self.project / "src/example.py").write_text("value = 3\n")
        self.assertEqual(state.verification_query(self.run)["pending"][0]["reason"], "stale_candidate")

    def test_protected_fields_malformed_input_and_paths_do_not_write(self):
        self.configure()
        for field in contract.FIELDS:
            self.assert_rejected_unchanged(lambda: state.update_metadata(self.run, {field: None}), "dedicated")
        for target in (dict(cell(), environment="unknown"), dict(cell(), layer="physical"), dict(cell(), phase="later")):
            self.assert_rejected_unchanged(lambda: self.configure(verification([target])))
        for name in ("../outside", str(self.project / "evidence.log"), "missing", "empty"):
            (self.project / "empty").touch()
            result = self.record(); result["evidence"] = [name]
            self.assert_rejected_unchanged(lambda: self.change("record-verification", result))
        (self.project / "linked").symlink_to(self.project / "evidence.log")
        result = self.record(); result["evidence"] = ["linked"]
        self.assert_rejected_unchanged(lambda: self.change("record-verification", result))

    def test_concise_replan_rejection_atomic_failure_concurrent_runs_and_dynamic_import(self):
        self.configure()
        before = self.path.read_bytes()
        with patch.object(state, "_atomic_write_json", side_effect=OSError("injected failure")):
            with self.assertRaises(OSError):
                self.change("record-decision", self.decision())
        self.assertEqual(self.path.read_bytes(), before)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda n: self.change("record-verification", self.record(str(n))), range(8)))
        self.assertEqual(len(self.read()["verification_runs"]), 8)
        metadata = self.read(); metadata["artifact_layout"] = "concise"
        original = copy.deepcopy(metadata)
        with self.assertRaisesRegex(ValueError, "staged"):
            contract.apply(metadata, self.run, "record-delta", self.delta())
        self.assertEqual(metadata, original)
        code = "import importlib.util,sys; s=importlib.util.spec_from_file_location('dynamic',sys.argv[1]); m=importlib.util.module_from_spec(s); sys.modules['dynamic']=m;s.loader.exec_module(m);assert m.contract.PHASES[-1]=='replay'"
        process = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT / "tools/icode_state.py")], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_cli_debt_queries_are_read_only_and_failures_structured(self):
        self.configure()
        before = {p: p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        for action in ("verification-context", "verification-pending", "verification-plan"):
            result = subprocess.run([sys.executable, str(ROOT / "tools/icode_state.py"), action, "--run-dir", str(self.run)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            json.loads(result.stdout)
        self.assertEqual({p: p.read_bytes() for p in self.run.rglob("*") if p.is_file()}, before)
        bad = self.project / "bad.json"; bad.write_text("{}")
        result = subprocess.run([sys.executable, str(ROOT / "tools/icode_state.py"), "record-verification", "--run-dir", str(self.run), "--input-json", str(bad)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])

    def test_verified_requires_current_implementation_completion(self):
        self.configure()
        self.change("record-verification", self.record())
        state.update_metadata(self.run, {"status": "code_in_progress", "completed_steps": ["1", "2", "3"]})
        result = state.verification_query(self.run)
        self.assertFalse(result["implemented"])
        self.assertEqual(result["delivery_verdict"], "verification_pending")
        self.assertIn("implementation_incomplete", [d["reason"] for d in result["pending"]])

    def test_concise_phase_transition_respects_semantic_gate(self):
        self.configure()
        metadata = self.read()
        metadata.update(artifact_layout="concise", workflow_kind="codex_full", status="full_in_progress",
                        completed_steps=[], completed_phases=["diagnose", "plan"], current_phase="implement")
        metadata["artifact_map"]["root_cause"] = "RCA.md"
        (self.run / "RCA.md").write_text("diagnosis\n")
        self.path.write_text(json.dumps(metadata))
        self.assertEqual(state.validate_metadata(metadata, self.run), [])
        self.change("record-decision", self.decision())
        self.assert_rejected_unchanged(lambda: state.update_metadata(self.run, {
            "completed_phases": ["diagnose", "plan", "implement"], "current_phase": "self_review"}), "blocked")

    def test_first_patch_reservation_allows_facts_and_replan_but_not_completion_bypass(self):
        self.configure()
        number = state.reserve_patch_number(self.run)
        self.change("record-decision", self.decision())
        self.assertIn("semantic", state.workflow_plan(self.run)["blocking_reasons"][0])
        self.change("record-delta", self.delta())
        self.assertEqual(state.workflow_plan(self.run)["next_step"], 1)
        self.assert_rejected_unchanged(lambda: state.finalize_patch(self.run, number, "completed"), "blocked")
        self.change("record-decision", self.decision("resolved"))
        draft = self.project / "replan.md"; draft.write_text("replanned\n")
        state.publish_artifact(self.run, "plan", draft, "01_plan.md")
        self.change("accept-replan", {})
        self.assert_rejected_unchanged(lambda: state.publish_artifact(self.run, "patches", draft, "08_patch.md"), "review")
        self.assert_rejected_unchanged(lambda: state.update_metadata(self.run, {"max_rounds": 1}), "rounds")
        self.assert_rejected_unchanged(lambda: state.validate_completed_run(self.run, self.project))

    def test_risk_null_compatibility_and_windows_path_guard(self):
        metadata = self.read(); metadata["risk_profile"] = None; self.path.write_text(json.dumps(metadata))
        self.configure()
        self.assertEqual(state.validate_metadata(self.read(), self.run), [])
        for name in ("C:outside.log", "\\outside.log", "D:/outside.log"):
            # POSIX 上创建 Windows 风险名称，验证跨平台拒绝而非只因缺文件失败。
            target = self.project / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text("evidence\n")
            result = self.record(); result["evidence"] = [name]
            self.assert_rejected_unchanged(lambda: self.change("record-verification", result), "path|relative")
        for broken in ([], "invalid"):
            metadata = self.read(); metadata["risk_profile"] = broken
            self.assertTrue(state.validate_metadata(metadata, self.run))

    def test_version_one_requires_all_containers(self):
        self.configure()
        for field in contract.FIELDS - {"delivery_verdict", "workflow_contract_version"}:
            metadata = self.read(); del metadata[field]
            self.assertTrue(contract.schema_errors(metadata), field)
        metadata = self.read(); metadata["replan_state"] = "invalid"
        self.assertTrue(contract.schema_errors(metadata))
        metadata = self.read(); metadata["requirement_deltas"] = [dict(self.delta(), status="open")]
        self.assertTrue(contract.schema_errors(metadata))
        supplied = {"semantic_decisions": [self.decision()]}
        contract.initialize(supplied)
        self.assertEqual(supplied["semantic_decisions"], [self.decision()])

    def test_old_delta_retry_does_not_change_current_risk_evidence(self):
        self.configure()
        state.assess_fast_risk(self.run, assessment("cross_component"))
        first = self.delta()
        self.change("record-delta", first)
        self.change("record-delta", dict(self.delta("delta-2"), evidence="second requirement evidence"))
        before = self.path.read_bytes()
        self.change("record-delta", first)
        self.assertEqual(self.path.read_bytes(), before)

    def test_major_delta_before_first_plan_preserves_legal_entry_state(self):
        for entry, status in (("0", "init_in_progress"), ("log", "log_done")):
            with self.subTest(entry=entry):
                run = self.run.parent / ("icode_2" if entry == "0" else "icode_3")
                draft = self.project / "entry.md"; draft.write_text("initial requirements\n")
                seed = dict(status=status, completed_steps=[entry], mode="fast", max_rounds=1, project_path=str(self.project))
                if entry == "log":
                    # log 的首个发布需要完整 requirement/root_cause；先以初稿种子合法创建。
                    seed.update(status="init_in_progress", completed_steps=["0"])
                state.publish_artifact(run, "requirement", draft, "00_init.md", seed)
                if entry == "log":
                    state.publish_artifact(run, "root_cause", draft, "log_analysis.md")
                    state.update_metadata(run, {"status": "log_done", "completed_steps": ["log"]})
                state.workflow_change(run, "record-delta", self.delta())
                state.assess_fast_risk(run, assessment())
                self.assertEqual(state.workflow_plan(run)["next_step"], 1)
                self.assertEqual(state.workflow_plan(run)["requested_mode"], "fast")
                state.publish_artifact(run, "plan", draft, "01_plan.md")
                state.workflow_change(run, "accept-replan", {})
                state.update_metadata(run, {"status": "plan_done", "completed_steps": [entry, "1"]})
                self.assertEqual(state.workflow_plan(run)["next_step"], 2)

    def test_malformed_configure_returns_structured_error_before_risk_sync(self):
        self.configure()
        for payload in ({"acceptance_contract": {}}, {"verification_contract": {"required": True, "requirements_pending": False}}):
            before = self.path.read_bytes()
            path = self.project / "config.json"; path.write_text(json.dumps(payload))
            result = subprocess.run([sys.executable, str(ROOT / "tools/icode_state.py"), "configure-workflow", "--run-dir", str(self.run), "--input-json", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["ok"])
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.path.read_bytes(), before)
