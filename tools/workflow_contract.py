"""业务合同、阶段门控和交付证据；写入与文件锁由状态入口负责。"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

PHASES = ("immediate", "converged", "restart", "replay")
CONSUMERS = ("direct_query", "aggregate_selector", "persistent_reference", "external_projection")
LAYERS = ("static", "unit", "build", "host", "deploy", "delivery", "consumption",
          "settings_preview", "operation_view", "closed_client", "physical")
FIELDS = {"workflow_contract_version", "semantic_decisions", "requirement_deltas", "replan_state",
          "acceptance_contract", "verification_contract", "verification_runs", "delivery_verdict"}
STEP_KEYS = ("plan", "plan_review", "final_plan", "implementation", "deepcheck", "audit")
VERIFICATION_INPUT = {"id", "cell", "outcome", "baseline", "evidence", "summary"}
TEST_INPUT = {"test_report", "test_exit_code"}


@lru_cache(maxsize=1)
def test_report_module():
    # 按当前安装位置解析，兼容状态 CLI 的隔离动态导入。
    spec = importlib.util.spec_from_file_location("codex_test_report", Path(__file__).with_name("test_result_summary.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _test_report_name(name):
    if (not isinstance(name, str) or not name or "\0" in name or "\\" in name
            or PureWindowsPath(name).drive or PurePosixPath(name).is_absolute()
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("test_report must be a canonical project-relative POSIX path")


def _test_exit_code(item):
    if "test_exit_code" in item:
        if type(item["test_exit_code"]) is not int:
            raise ValueError("test_exit_code must be an integer")
        if item["test_exit_code"] != 0 and item.get("outcome") != "fail":
            raise ValueError("nonzero test_exit_code requires fail")


def _test_observation(item):
    """历史摘要只校验保存的观察，不重新打开旧报告。"""
    _test_exit_code(item)
    if ("test_report" in item) != ("test_summary" in item):
        raise ValueError("test_report and machine test_summary must be stored together")
    if "test_report" in item:
        _test_report_name(item["test_report"])
        test_report_module().validate_summary(item["test_summary"], item["outcome"])
        for name, digest in item.get("evidence_hashes", {}).items():
            if (PurePosixPath(name) == PurePosixPath(item["test_report"])
                    and digest != item["test_summary"]["report"]["sha256"]):
                raise ValueError("test report summary disagrees with explicit evidence hash")


def initialize(metadata: dict) -> None:
    """仅为无版本的新种子或显式迁移建立合同，不能修补损坏的版本1状态。"""
    if "workflow_contract_version" in metadata:
        return
    defaults = dict(workflow_contract_version=1, semantic_decisions=[], requirement_deltas=[],
                    replan_state=None, verification_runs=[],
                    acceptance_contract={"required": False, "matrix": {}},
                    verification_contract={"required": False, "requirements_pending": False, "required_cells": []})
    for key, value in defaults.items():
        metadata.setdefault(key, value)
    _contract_shapes(metadata)
    sync_risk(metadata)


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")


def _object(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")


def _bool(value: Any, label: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")


def _risk_flags(metadata: Mapping[str, Any]) -> dict:
    profile = metadata.get("risk_profile")
    if profile is None:
        return {}
    _object(profile, "risk_profile")
    flags = profile.get("risk_flags", {})
    _object(flags, "risk_flags")
    return flags


def implemented(metadata: Mapping[str, Any]) -> bool:
    """concise 与 staged 分别依据其阶段合同判断实现是否完成。"""
    if metadata.get("artifact_layout") == "concise":
        return "implement" in metadata.get("completed_phases", [])
    return metadata.get("status") in ("code_done", "deepcheck_in_progress", "deepcheck_done", "completed")


def cell_key(cell: Mapping[str, Any]) -> tuple:
    """环境和生命周期均属于单元身份，宿主证明不能匹配实机单元。"""
    return tuple(cell.get(k) for k in ("layer", "consumer", "scenario", "environment", "phase"))


def _cell(cell: Any) -> None:
    _object(cell, "verification cell")
    if set(cell) - {"layer", "consumer", "scenario", "environment", "phase"}:
        raise ValueError("unknown verification cell field")
    if cell.get("layer") not in LAYERS or cell.get("environment") not in ("host", "simulated", "physical"):
        raise ValueError("invalid verification layer or environment")
    for key in ("consumer", "scenario"):
        _text(cell.get(key), key)
    if "phase" in cell and cell["phase"] not in PHASES:
        raise ValueError("invalid lifecycle phase")
    if cell["layer"] == "physical" and cell["environment"] != "physical":
        raise ValueError("physical layer requires physical environment")


def _contract_shapes(metadata: Mapping[str, Any]) -> None:
    acceptance, verification = metadata.get("acceptance_contract"), metadata.get("verification_contract")
    _object(acceptance, "acceptance_contract")
    _object(verification, "verification_contract")
    _bool(acceptance.get("required"), "acceptance required")
    _object(acceptance.get("matrix"), "acceptance matrix")
    for phase, row in acceptance["matrix"].items():
        if phase not in PHASES:
            raise ValueError("unknown acceptance phase")
        _object(row, "acceptance row")
        for consumer, expected in row.items():
            if consumer not in CONSUMERS or not isinstance(expected, str):
                raise ValueError("invalid acceptance consumer or expectation")
    _bool(verification.get("required"), "verification required")
    _bool(verification.get("requirements_pending"), "verification requirements_pending")
    cells = verification.get("required_cells")
    if not isinstance(cells, list):
        raise ValueError("required_cells must be an array")
    for cell in cells:
        _cell(cell)
    if len({cell_key(c) for c in cells}) != len(cells):
        raise ValueError("duplicate verification cells")


def _contracts(metadata: Mapping[str, Any]) -> None:
    _contract_shapes(metadata)
    acceptance, verification = metadata["acceptance_contract"], metadata["verification_contract"]
    flags = _risk_flags(metadata)
    if flags.get("real_env_verification") and not verification["required"]:
        raise ValueError("real_env_verification requires verification debt")
    if (flags.get("persistent_identity_change") or flags.get("restart_replay_semantics")) and not acceptance["required"]:
        raise ValueError("lifecycle risk requires acceptance matrix")
    if acceptance["required"] and not verification["required"]:
        raise ValueError("lifecycle acceptance requires verification")


def schema_errors(metadata: Mapping[str, Any]) -> list:
    """schema 校验允许保存阻断事实；执行权限另由 gate 判定。旧票不隐式迁移。"""
    if "workflow_contract_version" not in metadata:
        return []
    try:
        if type(metadata["workflow_contract_version"]) is not int or metadata["workflow_contract_version"] != 1:
            raise ValueError("workflow_contract_version must be 1")
        missing = (FIELDS - {"delivery_verdict"}) - set(metadata)
        if missing:
            raise ValueError("missing contract fields: " + ", ".join(sorted(missing)))
        _contracts(metadata)
        for field in ("semantic_decisions", "requirement_deltas", "verification_runs"):
            values = metadata.get(field)
            if not isinstance(values, list):
                raise ValueError(f"{field} must be an array")
            ids = set()
            for item in values:
                _object(item, field)
                _text(item.get("id"), field + " id")
                if item["id"] in ids:
                    raise ValueError(f"duplicate {field} id")
                ids.add(item["id"])
                if field == "semantic_decisions":
                    _decision(item)
                elif field == "requirement_deltas":
                    _delta(item)
                else:
                    _cell(item.get("cell"))
                    if item.get("outcome") not in ("pass", "fail", "inconclusive", "skipped"):
                        raise ValueError("invalid verification outcome")
                    _object(item.get("baseline"), "verification baseline")
                    if not isinstance(item.get("evidence_hashes"), dict) or not item["evidence_hashes"]:
                        raise ValueError("verification evidence hashes are required")
                    _test_observation(item)
        replan = metadata.get("replan_state")
        if replan is not None:
            _object(replan, "replan_state")
        major = [d for d in metadata["requirement_deltas"] if d["severity"] == "major"]
        if any(d["status"] == "open" for d in major) and (not replan or not replan.get("pending")):
            raise ValueError("unresolved major delta requires pending replan")
        if replan is not None:
            if not major:
                raise ValueError("replan requires a recorded major delta")
            if type(replan.get("revision")) is not int or replan["revision"] < 1:
                raise ValueError("invalid replan revision")
            _bool(replan.get("pending"), "replan pending")
            _object(replan.get("old_artifact_map"), "old artifact map")
            if metadata.get("mode") != "full":
                raise ValueError("replan must remain full")
            if type(metadata.get("max_rounds")) is not int or metadata["max_rounds"] < 3:
                raise ValueError("replan review rounds must remain >= 3")
            steps = metadata.get("completed_steps", [])
            if replan["pending"] and any(s in steps for s in ("2", "3", "4", "5", "6")):
                raise ValueError("pending replan cannot advance")
            for n, key in enumerate(STEP_KEYS[1:], 2):
                if str(n) in steps and metadata["artifact_map"].get(key) == replan["old_artifact_map"].get(key):
                    raise ValueError(f"replan requires newly published {key}")
    except (ValueError, KeyError, TypeError) as error:
        return ["workflow contract: " + str(error)]
    return []


def _decision(item: dict) -> None:
    if item.get("status") not in ("open", "resolved"):
        raise ValueError("decision status must be open or resolved")
    _text(item.get("question"), "decision question")
    _text(item.get("evidence"), "decision evidence")
    if item["status"] == "resolved":
        _text(item.get("decision"), "resolved decision")


def _delta(item: dict) -> None:
    if item.get("severity") not in ("major", "minor") or item.get("status") not in ("open", "resolved"):
        raise ValueError("invalid delta severity/status")
    _bool(item.get("needs_replan"), "needs_replan")
    _text(item.get("summary"), "delta summary")
    _text(item.get("evidence"), "delta evidence")
    if item["severity"] == "major" and not item["needs_replan"]:
        raise ValueError("major delta requires replan")
    if item["severity"] == "minor" and item["needs_replan"]:
        raise ValueError("a delta requiring replan must be classified major")


def acceptance_gaps(metadata: Mapping[str, Any]) -> list:
    """返回缺失预期的生命周期单元；不把书面预期当作运行证明。"""
    contract = metadata.get("acceptance_contract", {})
    if not contract.get("required"):
        return []
    matrix = contract.get("matrix", {})
    return [f"{phase}/{consumer}" for phase in PHASES for consumer in CONSUMERS
            if not matrix.get(phase, {}).get(consumer, "").strip()]


def gate(metadata: Mapping[str, Any], stage: str) -> list:
    """阶段权限：允许诊断记录，但禁止未决需求继续实施。"""
    if "workflow_contract_version" not in metadata:
        return []
    errors = schema_errors(metadata)
    if errors:
        return errors
    if stage == "diagnosis":
        return []
    reasons = []
    if any(d["status"] != "resolved" for d in metadata["semantic_decisions"]):
        reasons.append("unresolved semantic decision")
    if metadata["replan_state"] and metadata["replan_state"]["pending"] and stage != "plan":
        reasons.append("major requirement delta: return to plan")
    if stage in ("code", "patch") and acceptance_gaps(metadata):
        reasons.append("lifecycle acceptance matrix is incomplete")
    if (stage in ("code", "patch") and metadata["replan_state"]
            and "3" not in metadata["completed_steps"]):
        reasons.append("replan review and final plan required before implementation")
    return reasons


def sync_risk(metadata: dict) -> None:
    """真实环境与生命周期风险建立债务，不因再次低风险评估而消失。"""
    if "workflow_contract_version" not in metadata:
        return
    flags = _risk_flags(metadata)
    if flags.get("persistent_identity_change") or flags.get("restart_replay_semantics"):
        metadata["acceptance_contract"]["required"] = True
    if flags.get("real_env_verification") or metadata["acceptance_contract"]["required"]:
        contract = metadata["verification_contract"]
        contract["required"] = True
        if not contract["required_cells"]:
            contract["requirements_pending"] = True


def _project(metadata: Mapping[str, Any], run_dir: Path) -> Path:
    if len(run_dir.resolve().parents) < 3:
        raise ValueError("verification requires a native project run")
    root = run_dir.resolve().parents[2]
    if run_dir.resolve().parent != root / ".ai" / "icode":
        raise ValueError("verification requires a native project run")
    if Path(metadata.get("project_path", str(root))).resolve() != root:
        raise ValueError("project_path does not match run directory")
    return root


def file_hash(root: Path, name: str, require_nonempty: bool = True) -> str:
    """只读取项目内普通文件并检测读取期间变化；拒绝链接和逃逸。"""
    _text(name, "evidence/source path")
    relative = Path(name)
    if ("\\" in name or PureWindowsPath(name).drive or relative.is_absolute()
            or ".." in relative.parts or not relative.parts):
        raise ValueError("file path must be project-relative POSIX")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("symlink source/evidence is forbidden")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("file path escapes the project root") from error
    if not path.is_file():
        raise ValueError(f"source/evidence file is missing: {name}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
    after = path.stat()
    if (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size):
        raise ValueError("source/evidence changed during read")
    if require_nonempty and before.st_size == 0:
        raise ValueError("source/evidence must be non-empty")
    return digest.hexdigest()


def context(metadata: Mapping[str, Any], run_dir: Path) -> dict:
    """执行前只读候选基线；范围仅为声明源码，不能声称覆盖整个 Git 候选。"""
    root = _project(metadata, run_dir)
    files = metadata.get("code_files")
    if (not isinstance(files, list) or not files or not all(isinstance(p, str) for p in files)
            or len(set(files)) != len(files)):
        raise ValueError("verification requires unique non-empty code_files")
    contract = {k: metadata.get(k) for k in ("acceptance_contract", "verification_contract", "semantic_decisions")}
    digest = hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"ticket_id": metadata.get("ticket_id"), "source_hashes": {p: file_hash(root, p, False) for p in sorted(files)},
            "contract_sha256": digest, "replan_revision": (metadata.get("replan_state") or {}).get("revision", 0),
            "patch_count": metadata.get("patch_count", 0)}


def apply(metadata: dict, run_dir: Path, action: str, payload: dict) -> None:
    """在调用方事务内修改合同；错误抛 ValueError，调用方不得写回。"""
    _object(payload, "workflow input")
    if action in ("record-delta", "accept-replan") and metadata.get("artifact_layout") != "staged":
        raise ValueError("replan commands require staged layout")
    initialize(metadata)
    errors = schema_errors(metadata)
    if errors:
        raise ValueError("; ".join(errors))
    if action == "configure-workflow":
        if set(payload) - {"acceptance_contract", "verification_contract"} or not payload:
            raise ValueError("configure requires acceptance/verification contracts only")
        for key, value in payload.items():
            _object(value, key)
            if metadata[key]["required"] and value.get("required") is not True:
                raise ValueError("required contract cannot be disabled")
            metadata[key] = copy.deepcopy(value)
        _contract_shapes(metadata)
        sync_risk(metadata)
    elif action == "record-decision":
        if set(payload) - {"id", "status", "question", "decision", "evidence"}:
            raise ValueError("unknown decision field")
        _decision(payload)
        _text(payload.get("id"), "decision id")
        prior = next((d for d in metadata["semantic_decisions"] if d["id"] == payload["id"]), None)
        if prior and prior["status"] == "resolved" and prior != payload:
            raise ValueError("resolved decision is immutable; record a requirement delta")
        if prior:
            metadata["semantic_decisions"][metadata["semantic_decisions"].index(prior)] = copy.deepcopy(payload)
        else:
            metadata["semantic_decisions"].append(copy.deepcopy(payload))
    elif action == "record-delta":
        if set(payload) != {"id", "severity", "needs_replan", "summary", "evidence"}:
            raise ValueError("delta requires id/severity/needs_replan/summary/evidence")
        _text(payload["id"], "delta id")
        item = dict(payload, status="open" if payload["severity"] == "major" else "resolved")
        _delta(item)
        prior = next((d for d in metadata["requirement_deltas"] if d["id"] == item["id"]), None)
        if prior:
            if any(prior.get(k) != v for k, v in payload.items()):
                raise ValueError("delta id already has different content")
            return
        metadata["requirement_deltas"].append(item)
        if item["severity"] == "major":
            old = metadata.get("replan_state") or {}
            metadata["replan_state"] = {"revision": old.get("revision", 0) + 1, "pending": True,
                "requested_mode": old.get("requested_mode", (metadata.get("risk_profile") or {}).get("requested_mode", metadata.get("mode", "full"))),
                "old_artifact_map": copy.deepcopy(metadata["artifact_map"]),
                "snapshot": {k: copy.deepcopy(metadata.get(k)) for k in ("status", "completed_steps", "pending_verification")}}
            metadata.update(mode="full", workflow_kind="staged_full", max_rounds=max(3, metadata.get("max_rounds", 3)),
                            completed_steps=[s for s in metadata["completed_steps"] if s in ("0", "log", "1")],
                            status="plan_done" if "1" in metadata["completed_steps"] else metadata["status"],
                            total_rounds=0, clean_rounds=0, extended_rounds=0,
                            deepcheck_phase="reverse", deepcheck_clean_rounds=0, delivery_report_generated=False)
    elif action == "accept-replan":
        if payload:
            raise ValueError("accept-replan does not accept override fields")
        replan = metadata.get("replan_state")
        if not replan or not replan["pending"]:
            raise ValueError("no pending replan")
        reasons = gate(metadata, "plan") + acceptance_gaps(metadata)
        if reasons:
            raise ValueError("; ".join(reasons))
        plan = metadata["artifact_map"].get("plan")
        if not plan or plan == replan["old_artifact_map"].get("plan"):
            raise ValueError("replan requires newly published plan")
        replan["pending"] = False
        replan["accepted_plan"] = plan
        for delta in metadata["requirement_deltas"]:
            if delta["status"] == "open":
                delta.update(status="resolved", plan=plan, revision=replan["revision"])
    elif action == "record-verification":
        if not VERIFICATION_INPUT <= set(payload) or set(payload) - (VERIFICATION_INPUT | TEST_INPUT):
            raise ValueError("verification requires id/cell/outcome/baseline/evidence/summary; optional test_report/test_exit_code only")
        _text(payload["id"], "verification id")
        _text(payload["summary"], "verification summary")
        _cell(payload["cell"])
        if payload["outcome"] not in ("pass", "fail", "inconclusive", "skipped"):
            raise ValueError("invalid verification outcome")
        _test_exit_code(payload)
        if "test_report" in payload:
            _test_report_name(payload["test_report"])
        prior = next((r for r in metadata["verification_runs"] if r["id"] == payload["id"]), None)
        if prior:
            # 可选字段的省略也是请求身份，不能借省略报告复用另一条回执。
            request = {k: prior[k] for k in VERIFICATION_INPUT | TEST_INPUT if k in prior}
            if request != payload:
                raise ValueError("verification id already has different content")
            return
        if not implemented(metadata):
            raise ValueError("verification recording requires implemented code")
        if gate(metadata, "code"):
            raise ValueError("workflow is blocked")
        if payload["baseline"] != context(metadata, run_dir):
            raise ValueError("verification baseline is stale or does not match current candidate")
        evidence = payload["evidence"]
        if not isinstance(evidence, list) or not evidence or not all(isinstance(p, str) for p in evidence):
            raise ValueError("verification evidence must be non-empty paths")
        root = _project(metadata, run_dir)
        record = dict(copy.deepcopy(payload), evidence_hashes={p: file_hash(root, p) for p in evidence})
        if "test_report" in payload:
            record["test_summary"] = test_report_module().summarize_report(payload["test_report"], root)
            report = record["test_summary"]["report"]
            # 同一文件可能通过大小写别名或硬链接登记，不能只比较路径字符串。
            for name, digest in record["evidence_hashes"].items():
                if (root / name).samefile(report["path"]) and digest != report["sha256"]:
                    raise ValueError("test report summary disagrees with explicit evidence hash")
        _test_observation(record)
        metadata["verification_runs"].append(record)
    else:
        raise ValueError("unknown workflow action")
    errors = schema_errors(metadata)
    if errors:
        raise ValueError("; ".join(errors))


def pending(metadata: Mapping[str, Any], run_dir: Path) -> dict:
    """只读派生债务；最新失败不沿用旧 pass，陈旧源码/证据不能放行。"""
    if "workflow_contract_version" not in metadata:
        return {"ticket_id": metadata.get("ticket_id"), "implemented": implemented(metadata),
                "delivery_verdict": "not_assessed", "blocking_reasons": [], "pending": [], "legacy_contract": True}
    reasons = gate(metadata, "code")
    contract = metadata.get("verification_contract", {})
    debt = []
    if contract.get("required"):
        if not implemented(metadata):
            debt.append({"reason": "implementation_incomplete"})
        if contract.get("requirements_pending") or not contract.get("required_cells"):
            debt.append({"reason": "requirements_pending"})
        flags = _risk_flags(metadata)
        if flags.get("real_env_verification") and not any(c["environment"] == "physical" for c in contract["required_cells"]):
            debt.append({"reason": "physical_requirement_missing"})
        if metadata["acceptance_contract"]["required"]:
            coverage = {(c.get("phase"), c["consumer"]) for c in contract["required_cells"]}
            debt.extend({"reason": "lifecycle_verification_missing", "phase": p, "consumer": c}
                        for p in PHASES for c in CONSUMERS if (p, c) not in coverage)
        try:
            current = context(metadata, run_dir)
        except (ValueError, OSError, TypeError) as error:
            current = None
            debt.append({"reason": "candidate_unavailable", "detail": str(error)})
        root = _project(metadata, run_dir)
        for cell in contract["required_cells"]:
            runs = [r for r in metadata["verification_runs"] if cell_key(r["cell"]) == cell_key(cell)]
            tracked = any("test_summary" in r and r["baseline"] == current for r in runs)
            # 先绑定当前候选与单元；无计数 pass 不覆盖已观察的报告，负面结果始终保留。
            latest = next((r for r in reversed(runs) if not (tracked and r["baseline"] == current
                          and r["outcome"] == "pass" and "test_summary" not in r)), None)
            reason = "missing_run"
            if latest:
                reason = latest["outcome"] if latest["outcome"] != "pass" else ""
                if latest["baseline"] != current:
                    reason = "stale_candidate"
                elif not reason:
                    try:
                        if any(file_hash(root, p) != sha for p, sha in latest["evidence_hashes"].items()):
                            reason = "stale_evidence"
                    except (ValueError, OSError):
                        reason = "missing_evidence"
            if reason:
                debt.append({"cell": copy.deepcopy(cell), "reason": reason, "run_id": latest["id"] if latest else None})
    verdict = "blocked" if reasons else ("verification_pending" if debt else ("verified" if contract.get("required") else "not_assessed"))
    return {"ticket_id": metadata.get("ticket_id"), "implemented": implemented(metadata),
            "delivery_verdict": verdict, "blocking_reasons": reasons, "pending": debt}
