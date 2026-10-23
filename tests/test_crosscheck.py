import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "icode_crosscheck.py"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_fresh(path, value, env):
    """Real fixture Read declarations, separate from writing a result JSON."""
    report = json.loads(path.with_name(path.name.replace(".fresh.json", ".worklist.json")).read_text())
    for unit in report["units"]:
        for entry in unit["files"]:
            data = (Path(report["workspace"]) / entry["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]
            run_tool(env, "inspection", "--dir", path.parent, "--round", str(value["round"]),
                     "--phase", "read", "--path", entry["path"])
    write_json(path, value)


def tree_digest(root: Path, *, exclude_crosscheck: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if exclude_crosscheck and rel.parts[:3] == (".ai", "icode", ".crosscheck"):
            continue
        if path.is_symlink():
            digest.update(f"L:{rel}:{os.readlink(path)}\n".encode())
        elif path.is_file():
            digest.update(f"F:{rel}:".encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture()
def workspace(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    root = tmp_path / "project"
    ticket = root / ".ai" / "icode" / "icode_1"
    ticket.mkdir(parents=True)
    source = root / "src" / "feature.c"
    source.parent.mkdir(parents=True)
    source.write_text("int feature(void) { return 1; }\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "src"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "fixture baseline"], check=True)
    artifacts = {
        "requirement": "00_requirements.md",
        "root_cause": None,
        "plan": "01_plan.md",
        "plan_review": "02_plan_review.md",
        "final_plan": "03_plan_final.md",
        "implementation": "04_code_review_fix.md",
        "deepcheck": "05_deepcheck.md",
        "audit": "06_audit.md",
        "patches": None,
        "delivery_report": None,
        "delivery_brief": None,
    }
    for relative in (value for value in artifacts.values() if value):
        (ticket / relative).write_text(f"# {relative}\n\nFixture evidence.\n", encoding="utf-8")
    write_json(
        ticket / ".ico_metadata.json",
        {
            "ticket_id": "demo-1",
            "created_at": "2026-09-14T08:00:00",
            "status": "completed",
            "artifact_layout": "staged",
            "artifact_map": artifacts,
            "current_phase": None,
            "completed_phases": [],
            "completed_steps": ["0", "1", "2", "3", "4", "5", "6"],
            "project_path": str(root),
            "code_files": ["src/feature.c"],
            "patch_count": 0,
            "patch_history": [],
            "delivery_report_generated": False,
        },
    )
    index = tmp_path / "home" / ".codex" / "icode_data" / "index.json"
    write_json(index, {"schema_version": 1, "tickets": [{
        "ticket_id": "demo-1",
        "project_path": str(root),
        "out_dir": ".ai/icode/icode_1",
        "status": "completed",
    }]})
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return root, ticket, env


def run_tool(env: dict[str, str], *args: str, expected: int = 0) -> dict:
    proc = subprocess.run(
        [sys.executable, str(TOOL), *map(str, args)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == expected, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is (expected == 0)
    return payload


def fresh_payload(round_no: int, ticket_id: str = "demo-1") -> dict:
    return {
        "schema_version": 1,
        "target_ticket_id": ticket_id,
        "round": round_no,
        "reviewed_at": f"2026-09-14T08:0{round_no}:00",
        "verdict": "changes_recommended",
        "evidence_boundary": "静态检查；未运行设备验证",
        "summary": "发现一个可维护性建议",
        "findings": [
            {
                "finding_id": "CC-001",
                "title": "补充边界测试",
                "severity": "minor",
                "status": "new",
                "category": "test",
                "evidence": ["src/feature.c:1"],
                "analysis": "边界值尚未覆盖",
                "recommendation": "增加边界测试",
                "requires_change": True,
                "locations": [],
                "verification_status": "needs_more_evidence",
                "evidence_boundary": "静态模拟建议，尚未证明边界测试缺失",
            }
        ],
    }


def test_new_round_requires_independent_worklist(workspace):
    root, _, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    assert "inspection_worklist" in started
    directory = Path(started["crosscheck_dir"])
    # A result JSON alone must not satisfy a real new round's Read worklist.
    (directory / "crosscheck_round_1.fresh.json").write_text(json.dumps(fresh_payload(1)))
    failed = run_tool(env, "freeze", "--dir", directory, "--round", "1", expected=1)
    assert failed["gate_id"] == "inspection_worklist"


def worklist_files(started):
    report = json.loads(Path(started["inspection_worklist"]).read_text())
    return report, {f["path"]: f for u in report["units"] for f in u["files"]}


def read_batch(env, started, paths, *, identity=None, expected=0):
    args = ["inspection", "--dir", started["crosscheck_dir"], "--round", started["round"],
            "--phase", "read", "--paths-json", json.dumps(paths)]
    if identity is not None:
        args += ["--request-id", identity]
    return run_tool(env, *args, expected=expected)


def test_file_budget_is_frozen_resumed_and_inherited_by_next_round(workspace):
    root, ticket, env = workspace
    before = tree_digest(ticket)
    started = run_tool(env, "start", ticket, "--max-files", "350")
    assert worklist_files(started)[0]["max_files"] == 350
    assert run_tool(env, "start", ticket)["resumed"]
    directory = Path(started["crosscheck_dir"])
    saved = tree_digest(directory)
    denied = run_tool(env, "start", ticket, "--max-files", "351", expected=1)
    assert denied["gate_id"] == "inspection_budget"
    assert tree_digest(directory) == saved
    write_fresh(Path(started["fresh_output"]), fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    run_tool(env, "finish", "--dir", directory, "--round", "1")
    second = run_tool(env, "start", ticket)
    assert second["round"] == 2
    report, files = worklist_files(second)
    assert report["max_files"] == 350
    assert all(f["reads"] == {} for f in files.values())
    assert tree_digest(ticket) == before


def test_legacy_round_without_budget_field_keeps_its_worklist_budget(workspace):
    _, ticket, env = workspace
    started = run_tool(env, "start", ticket)
    directory = Path(started["crosscheck_dir"])
    manifest_path = directory / "crosscheck_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["rounds"][0].pop("inspection_max_files", None)
    write_json(manifest_path, manifest)
    saved = tree_digest(directory)
    assert run_tool(env, "start", ticket, "--max-files", "200")["resumed"]
    assert tree_digest(directory) == saved


def test_budget_is_durable_if_worklist_creation_is_interrupted(workspace, monkeypatch):
    from tools import icode_crosscheck as api
    _, ticket, env = workspace
    args = api.build_parser().parse_args(["start", str(ticket), "--max-files", "350"])
    writer = api.atomic_write_json
    def fail_worklist(path, value):
        if str(path).endswith(".worklist.json"):
            raise OSError("injected worklist failure")
        return writer(path, value)
    with monkeypatch.context() as patched:
        patched.setattr(api, "atomic_write_json", fail_worklist)
        with pytest.raises(OSError):
            api.cmd_start(args)
    started = run_tool(env, "start", ticket)
    assert worklist_files(started)[0]["max_files"] == 350


def test_budget_and_declaration_survive_binding_write_interruption(workspace, monkeypatch):
    from tools import icode_crosscheck as api
    _, ticket, env = workspace
    args = api.build_parser().parse_args(["start", str(ticket), "--max-files", "350"])
    writer = api.atomic_write_json
    manifest_writes = 0
    def fail_binding(path, value):
        nonlocal manifest_writes
        if path.name == "crosscheck_manifest.json":
            manifest_writes += 1
            if manifest_writes == 2:
                raise OSError("injected declaration binding failure")
        return writer(path, value)
    with monkeypatch.context() as patched:
        patched.setattr(api, "atomic_write_json", fail_binding)
        with pytest.raises(OSError):
            api.cmd_start(args)
    started = run_tool(env, "start", ticket)
    assert started["resumed"] and started["round"] == 1
    report, files = worklist_files(started)
    assert report["max_files"] == 350
    assert all(f["reads"] == {} for f in files.values())


@pytest.mark.parametrize("changed", ["src/feature.c", "src/feature.h"])
def test_source_drift_can_start_a_new_round_with_an_explicit_budget(workspace, changed):
    root, ticket, env = workspace
    (root / "src/feature.h").write_text("int feature(void);\n")
    first = run_tool(env, "start", ticket)
    (root / changed).write_text("int changed;\n")
    second = run_tool(env, "start", ticket, "--max-files", "350")
    assert second["round"] == first["round"] + 1 and not second["resumed"]
    assert worklist_files(second)[0]["max_files"] == 350


@pytest.mark.parametrize("budget", ["0", "-1"])
def test_invalid_budget_does_not_create_crosscheck_output(workspace, budget):
    root, ticket, env = workspace
    denied = run_tool(env, "start", ticket, "--max-files", budget, expected=1)
    assert denied["gate_id"] == "inspection_budget"
    assert not (root / ".ai/icode/.crosscheck").exists()


def test_batch_read_is_atomic_idempotent_and_does_not_read_for_the_agent(workspace):
    root, ticket, env = workspace
    (root / "src/feature.h").write_text("int feature(void);\n")
    (root / "src/extra.c").write_text("int extra;\n")
    started = run_tool(env, "start", ticket)
    directory = Path(started["crosscheck_dir"])
    # 单纯提交结果不能替代本轮实际阅读；登记只保存调用方声明。
    write_json(Path(started["fresh_output"]), dict(fresh_payload(1), verdict="pass", findings=[]))
    assert run_tool(env, "freeze", "--dir", directory, "--round", "1", expected=1)["gate_id"] == "inspection_worklist"
    report, files = worklist_files(started)
    paths = sorted(files)
    for path in paths:
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == files[path]["sha256"]
    before = tree_digest(ticket)
    registered = paths[:2]
    result = read_batch(env, started, registered, identity="batch-1")
    assert result["paths"] == registered and not result["already_applied"]
    run_tool(env, "inspection", "--dir", directory, "--round", "1", "--phase", "read", "--path", paths[2])
    report, files = worklist_files(started)
    assert all(f["reads"]["fresh"] == f["sha256"] for f in files.values())
    saved = Path(started["inspection_worklist"]).read_bytes()
    replay = read_batch(env, started, list(reversed(registered)), identity="batch-1")
    assert replay["already_applied"]
    assert Path(started["inspection_worklist"]).read_bytes() == saved
    denied = read_batch(env, started, paths[:1], identity="batch-1", expected=1)
    assert denied["gate_id"] == "inspection_worklist"
    assert Path(started["inspection_worklist"]).read_bytes() == saved
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    assert read_batch(env, started, paths, expected=1)["gate_id"] == "inspection_worklist"
    assert tree_digest(ticket) == before


@pytest.mark.parametrize("paths", [[], ["src/feature.c"] * 2, ["src/feature.c", "missing.c"],
    ["src/feature.c", "../outside.c"], ["./src/feature.c"], ["C:escape.c"],
    ["x" * 65536], [f"src/{i}.c" for i in range(257)]])
def test_bad_batch_has_no_partial_registration(workspace, paths):
    _, ticket, env = workspace
    started = run_tool(env, "start", ticket)
    before = Path(started["inspection_worklist"]).read_bytes()
    result = read_batch(env, started, paths, expected=1)
    assert result["gate_id"] == "inspection_worklist"
    assert Path(started["inspection_worklist"]).read_bytes() == before


def test_batch_write_failure_and_new_round_do_not_reuse_receipts(workspace, monkeypatch):
    from tools import icode_crosscheck as api
    root, ticket, env = workspace
    started = run_tool(env, "start", ticket)
    before = Path(started["inspection_worklist"]).read_bytes()
    args = api.build_parser().parse_args(["inspection", "--dir", started["crosscheck_dir"],
        "--round", "1", "--phase", "read", "--paths-json", '["src/feature.c"]', "--request-id", "retry"])
    with monkeypatch.context() as patched:
        patched.setattr(api, "atomic_write_json", lambda *a: (_ for _ in ()).throw(OSError("injected")))
        with pytest.raises(OSError):
            api.cmd_inspection(args)
    assert Path(started["inspection_worklist"]).read_bytes() == before
    assert not read_batch(env, started, ["src/feature.c"], identity="retry")["already_applied"]
    (root / "src/feature.c").write_text("int feature(void) { return 2; }\n")
    next_round = run_tool(env, "start", ticket)
    assert next_round["round"] == 2
    assert not worklist_files(next_round)[0].get("read_batches")
    assert not read_batch(env, next_round, ["src/feature.c"], identity="retry")["already_applied"]


def test_larger_budget_supports_an_actual_256_member_batch(workspace):
    root, ticket, env = workspace
    for index in range(255):
        (root / "src" / f"file_{index}.c").write_text("int x;\n")
    started = run_tool(env, "start", ticket, "--max-files", "300")
    report, files = worklist_files(started)
    assert len(files) == 256 and report["coverage_status"] == "complete_within_scope"
    paths = sorted(files)
    for path in paths:
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == files[path]["sha256"]
    result = read_batch(env, started, paths, identity="large")
    assert len(result["source_hashes"]) == 256
    assert run_tool(env, "inspection", "--dir", started["crosscheck_dir"], "--round", "1", "--phase", "check")["read_only"]


def test_batch_drift_bad_json_and_wrong_phase_leave_worklist_unchanged(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", ticket)
    before = Path(started["inspection_worklist"]).read_bytes()
    args = ("inspection", "--dir", started["crosscheck_dir"], "--round", "1")
    for tail in (("--phase", "read", "--paths-json", "["),
                 ("--phase", "read", "--paths-json", '["src/feature.c"]', "--path", "src/feature.c"),
                 ("--phase", "check", "--paths-json", '["src/feature.c"]'),
                 ("--phase", "read", "--paths-json", '["src/feature.c"]', "--request-id", "../bad")):
        assert run_tool(env, *args, *tail, expected=1)["gate_id"] == "inspection_worklist"
    (root / "src/feature.c").write_text("int changed;\n")
    assert read_batch(env, started, ["src/feature.c"], identity="stale", expected=1)["gate_id"] == "inspection_worklist"
    assert Path(started["inspection_worklist"]).read_bytes() == before


def test_saved_batch_receipt_cannot_forge_members_hashes_or_reads(workspace):
    _, ticket, env = workspace
    started = run_tool(env, "start", ticket)
    read_batch(env, started, ["src/feature.c"], identity="b")
    report, _ = worklist_files(started)
    path = Path(started["inspection_worklist"])
    for variant in ("members", "hash", "reads"):
        changed = json.loads(json.dumps(report))
        if variant == "members":
            changed["read_batches"]["b"]["paths"].append("missing.c")
        elif variant == "hash":
            changed["read_batches"]["b"]["source_hashes"]["src/feature.c"] = "0" * 64
        else:
            changed["units"][0]["files"][0]["reads"] = {}
        write_json(path, changed)
        before = path.read_bytes()
        assert read_batch(env, started, ["src/feature.c"], identity="b", expected=1)["gate_id"] == "inspection_worklist"
        assert path.read_bytes() == before


def test_redundant_related_resume_preserves_progress_but_new_consumer_is_rejected(workspace):
    root, ticket, env = workspace
    (root / "src/feature.h").write_text("int feature(void);\n")
    (root / "elsewhere").mkdir()
    (root / "elsewhere/caller.c").write_text("int caller(void);\n")
    started = run_tool(env, "start", ticket)
    run_tool(env, "inspection", "--dir", started["crosscheck_dir"], "--round", "1",
             "--phase", "read", "--path", "src/feature.c")
    before = Path(started["inspection_worklist"]).read_bytes()
    assert run_tool(env, "start", ticket, "--related", "src/feature.h")["resumed"]
    assert Path(started["inspection_worklist"]).read_bytes() == before
    result = run_tool(env, "start", ticket, "--related", "elsewhere/caller.c", expected=1)
    assert result["gate_id"] == "inspection_worklist"
    assert Path(started["inspection_worklist"]).read_bytes() == before


def test_start_recovers_only_empty_orphan_containers(workspace):
    root, ticket, env = workspace
    orphan = root / ".ai/icode/.crosscheck/icode_1"
    orphan.mkdir(parents=True)
    before = tree_digest(ticket)
    started = run_tool(env, "start", ticket)
    assert Path(started["crosscheck_dir"]) == orphan
    assert (orphan / "crosscheck_manifest.json").is_file()
    assert tree_digest(ticket) == before


def test_nonempty_orphan_is_preserved_and_rejected(workspace):
    root, ticket, env = workspace
    orphan = root / ".ai/icode/.crosscheck/icode_1"
    orphan.mkdir(parents=True)
    evidence = orphan / "unexplained.json"
    evidence.write_bytes(b"partial evidence")
    result = run_tool(env, "start", ticket, expected=1)
    assert result["gate_id"] == "crosscheck_manifest_missing"
    assert evidence.read_bytes() == b"partial evidence"


def test_container_inventory_does_not_remove_empty_directories(tmp_path):
    from tools import icode_crosscheck as api
    orphan = tmp_path / "icode_1"
    orphan.mkdir()
    assert api.matching_containers(tmp_path, {}) == ([], [])
    assert orphan.is_dir()


@pytest.mark.parametrize("failure", ["round", "publish", "after_publish"])
def test_start_failure_has_no_unrecoverable_empty_container(workspace, monkeypatch, failure):
    from tools import icode_crosscheck as api
    root, ticket, env = workspace
    args = api.build_parser().parse_args(["start", str(ticket)])
    before = tree_digest(ticket)
    with monkeypatch.context() as patcher:
        if failure == "round":
            def fail_round(*args):
                raise api.CrosscheckError("snapshot failed", gate_id="fixture")
            patcher.setattr(api, "new_round", fail_round)
        else:
            writer = api.atomic_write_json
            def fail_publish(path, value):
                if failure == "after_publish":
                    writer(path, value)
                raise OSError("injected publication failure")
            patcher.setattr(api, "atomic_write_json", fail_publish)
        with pytest.raises((api.CrosscheckError, OSError)):
            api.cmd_start(args)
    containers = list((root / ".ai/icode/.crosscheck").glob("icode_*"))
    if failure != "after_publish":
        assert containers == []
    else:
        assert (containers[0] / "crosscheck_manifest.json").is_file()
    run_tool(env, "start", ticket)
    assert tree_digest(ticket) == before


def test_root_seed_avoids_repository_wide_default_scope(workspace):
    root, ticket, env = workspace
    (root / "build.sh").write_text("#!/bin/sh\nexit 0\n")
    for index in range(220):
        path = root / "unrelated" / f"file_{index}.c"
        path.parent.mkdir(exist_ok=True)
        path.write_text("int unrelated;\n")
    metadata = json.loads((ticket / ".ico_metadata.json").read_text())
    metadata["code_files"].append("build.sh")
    write_json(ticket / ".ico_metadata.json", metadata)
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    report = json.loads(Path(started["inspection_worklist"]).read_text())
    assert report["scopes"] == ["build.sh", "src"]
    assert report["coverage_status"] == "complete_within_scope"
    assert {entry["path"] for unit in report["units"] for entry in unit["files"]} == {"build.sh", "src/feature.c"}
    assert run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")["resumed"]
    denied = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1", "--scope", ".", expected=1)
    assert denied["gate_id"] == "inspection_worklist"


def test_explicit_repository_scope_keeps_budget_debt_fail_closed(workspace):
    root, _, env = workspace
    for index in range(220):
        (root / f"file_{index}.c").write_text("int unrelated;\n")
    subprocess.run(["git", "-C", str(root), "add", "file_*.c"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "unrelated tracked fixture files"], check=True)
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1", "--scope", ".")
    report = json.loads(Path(started["inspection_worklist"]).read_text())
    assert report["scopes"] == ["."] and report["unobserved"]
    directory = Path(started["crosscheck_dir"])
    fresh = fresh_payload(1)
    fresh.update(verdict="pass", findings=[])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh, env)
    denied = run_tool(env, "freeze", "--dir", directory, "--round", "1", expected=1)
    assert denied["gate_id"] == "inspection_worklist"


def test_related_source_drift_reenters_a_new_round(workspace):
    root, _, env = workspace
    header = root / "src/feature.h"
    header.write_text("int feature(void);\n")
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    header.write_text("int feature(void); /* newer source, same untracked status */\n")
    restarted = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    assert restarted["round"] == 2 and not restarted["resumed"]
    manifest = json.loads((Path(started["crosscheck_dir"]) / "crosscheck_manifest.json").read_text())
    assert manifest["rounds"][0]["state"] == "stale_input"


def test_freeze_replay_rejects_worklist_symlink(workspace, tmp_path):
    root, _, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    path = Path(started["inspection_worklist"])
    copy = tmp_path / "same-worklist.json"
    copy.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(copy)
    assert run_tool(env, "freeze", "--dir", directory, "--round", "1", expected=1)["gate_id"] == "inspection_worklist"


def test_start_rejects_frozen_worklist_tampering_without_manifest_write(workspace):
    root, _, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    before = (directory / "crosscheck_manifest.json").read_bytes()
    path = Path(started["inspection_worklist"])
    report = json.loads(path.read_text())
    report["units"][0]["files"][0]["sha256"] = "0" * 64
    write_json(path, report)
    failed = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1", expected=1)
    assert failed["gate_id"] == "inspection_worklist"
    assert (directory / "crosscheck_manifest.json").read_bytes() == before


def test_finding_position_and_frozen_worklist_are_enforced(workspace):
    root, _, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    fresh = fresh_payload(1)
    finding = fresh["findings"][0]
    source = root / "src/feature.c"
    finding.update(verification_status="confirmed", locations=[dict(path="src/feature.c", start_line=1,
        end_line=1, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), excerpt="made-up source\n")])
    path = directory / "crosscheck_round_1.fresh.json"
    write_fresh(path, fresh, env)
    assert run_tool(env, "freeze", "--dir", directory, "--round", "1", expected=1)["gate_id"] == "inspection_worklist"
    finding["locations"][0]["excerpt"] = source.read_text()
    write_json(path, fresh)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh)
    run_tool(env, "finish", "--dir", directory, "--round", "1")
    # Historic immutable evidence remains valid after a later source update.
    source.write_text("int feature(void) { return 2; }\n")
    run_tool(env, "validate", "--dir", directory)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    worklist = Path(started["inspection_worklist"])
    report = json.loads(worklist.read_text())
    report["units"][0]["files"][0]["reads"] = {}
    write_json(worklist, report)
    assert run_tool(env, "finish", "--dir", directory, "--round", "1", expected=1)["gate_id"] == "inspection_worklist"


def test_new_round_does_not_reuse_old_reads_or_allow_scope_rewrite(workspace):
    root, _, env = workspace
    first = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(first["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    run_tool(env, "finish", "--dir", directory, "--round", "1")
    second = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    path = Path(second["inspection_worklist"])
    report = json.loads(path.read_text())
    assert all(f["reads"] == {} for u in report["units"] for f in u["files"])
    report["max_files"] = 1
    write_json(path, report)
    failed = run_tool(env, "inspection", "--dir", directory, "--round", "2", "--phase", "read", "--path", "src/feature.c", expected=1)
    assert failed["gate_id"] == "inspection_worklist"


def test_crosscheck_roundtrip_multi_round_and_zero_write(workspace):
    root, ticket, env = workspace
    index = Path(env["HOME"]) / ".codex" / "icode_data" / "index.json"
    target_before = tree_digest(ticket)
    source_before = tree_digest(root / "src")
    index_before = index.read_bytes()

    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    crosscheck_dir = Path(started["crosscheck_dir"])
    assert started["round"] == 1
    assert started["phase"] == "fresh_review"
    assert started["resumed"] is False
    assert "previous_round" not in started
    assert crosscheck_dir.parent == root / ".ai" / "icode" / ".crosscheck"
    assert not (crosscheck_dir / ".ico_metadata.json").exists()

    fresh = crosscheck_dir / "crosscheck_round_1.fresh.json"
    write_fresh(fresh, fresh_payload(1), env)
    frozen = run_tool(env, "freeze", "--dir", crosscheck_dir, "--round", "1")
    assert frozen["previous_round"] is None

    final = fresh_payload(1)
    write_json(crosscheck_dir / "crosscheck_round_1.json", final)
    finished = run_tool(env, "finish", "--dir", crosscheck_dir, "--round", "1")
    assert finished["state"] == "completed"
    assert (crosscheck_dir / "crosscheck_round_1.md").is_file()
    assert (crosscheck_dir / "findings.json").is_file()
    assert (crosscheck_dir / "crosscheck_report.md").is_file()
    run_tool(env, "validate", "--dir", crosscheck_dir)

    second = run_tool(env, "start", "--workspace", root, ticket / "03_plan_final.md")
    assert second["crosscheck_dir"] == str(crosscheck_dir)
    assert second["round"] == 2
    assert "previous_round" not in second
    resumed = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    assert resumed["round"] == 2
    assert resumed["resumed"] is True

    write_fresh(crosscheck_dir / "crosscheck_round_2.fresh.json", fresh_payload(2), env)
    frozen2 = run_tool(env, "freeze", "--dir", crosscheck_dir, "--round", "2")
    assert frozen2["previous_round"] == str(crosscheck_dir / "crosscheck_round_1.json")
    final2 = fresh_payload(2)
    final2["findings"][0]["status"] = "still_present"
    write_json(crosscheck_dir / "crosscheck_round_2.json", final2)
    run_tool(env, "finish", "--dir", crosscheck_dir, "--round", "2")
    validated = run_tool(env, "validate", "--dir", crosscheck_dir)
    assert validated["rounds"] == 2

    assert tree_digest(ticket) == target_before
    assert tree_digest(root / "src") == source_before
    assert index.read_bytes() == index_before
    assert not list(crosscheck_dir.rglob(".ico_metadata.json"))


def test_crosscheck_outputs_do_not_make_finish_stale(workspace):
    root, _ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    manifest = json.loads((directory / "crosscheck_manifest.json").read_text(encoding="utf-8"))
    status = manifest["rounds"][0]["start_snapshot"]["git"]["status"]
    assert all(".ai/icode" not in line for line in status)

    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    finished = run_tool(env, "finish", "--dir", directory, "--round", "1")
    assert finished["state"] == "completed"


def test_codex_lock_churn_does_not_make_finish_stale(workspace):
    root, ticket, env = workspace
    lock = ticket / ".ico.lock"
    lock.write_text("owner-a\n", encoding="utf-8")
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))

    lock.write_text("owner-b\n", encoding="utf-8")
    finished = run_tool(env, "finish", "--dir", directory, "--round", "1")

    assert finished["state"] == "completed"


def test_no_argument_never_guesses_latest(workspace):
    root, _ticket, env = workspace
    failed = run_tool(env, "start", "--workspace", root, expected=1)
    assert "当前工单" in failed["error"]


def test_stale_input_is_preserved_and_next_round_can_start(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    crosscheck_dir = Path(started["crosscheck_dir"])
    write_fresh(crosscheck_dir / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", crosscheck_dir, "--round", "1")
    write_json(crosscheck_dir / "crosscheck_round_1.json", fresh_payload(1))

    (ticket / "03_plan_final.md").write_text("# Plan\n\nChanged during review.\n", encoding="utf-8")
    stale = run_tool(env, "finish", "--dir", crosscheck_dir, "--round", "1", expected=1)
    assert stale["state"] == "stale_input"
    assert (crosscheck_dir / "crosscheck_round_1.json").is_file()

    next_round = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    assert next_round["round"] == 2


def test_rejects_ineligible_ambiguous_and_escaping_targets(workspace):
    root, ticket, env = workspace
    metadata = json.loads((ticket / ".ico_metadata.json").read_text(encoding="utf-8"))
    metadata["status"] = "code_done"
    write_json(ticket / ".ico_metadata.json", metadata)
    denied = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1", expected=1)
    assert "completed" in denied["error"]

    metadata["status"] = "completed"
    write_json(ticket / ".ico_metadata.json", metadata)
    first = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    first_dir = Path(first["crosscheck_dir"])
    duplicate = first_dir.parent / "icode_99"
    duplicate.mkdir()
    write_json(duplicate / "crosscheck_manifest.json", json.loads((first_dir / "crosscheck_manifest.json").read_text()))
    ambiguous = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1", expected=1)
    assert "多个 crosscheck" in ambiguous["error"]

    bad_root = root / ".ai" / "icode" / ".crosscheck-link"
    bad_root.symlink_to(root.parent, target_is_directory=True)
    escaped = run_tool(
        env,
        "start",
        "--workspace",
        root,
        "--ticket",
        "demo-1",
        "--crosscheck-root",
        bad_root,
        expected=1,
    )
    assert "crosscheck" in escaped["error"]


def test_fresh_file_is_immutable_after_freeze(workspace):
    root, _ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    crosscheck_dir = Path(started["crosscheck_dir"])
    fresh = crosscheck_dir / "crosscheck_round_1.fresh.json"
    write_fresh(fresh, fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", crosscheck_dir, "--round", "1")
    changed = fresh_payload(1)
    changed["summary"] = "tampered"
    write_json(fresh, changed)
    write_json(crosscheck_dir / "crosscheck_round_1.json", fresh_payload(1))
    denied = run_tool(env, "finish", "--dir", crosscheck_dir, "--round", "1", expected=1)
    assert "fresh" in denied["error"]


def test_finish_idempotently_repairs_missing_derived_reports(workspace):
    root, _ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    run_tool(env, "finish", "--dir", directory, "--round", "1")

    (directory / "findings.json").unlink()
    (directory / "crosscheck_report.md").unlink()
    repaired = run_tool(env, "finish", "--dir", directory, "--round", "1")
    assert repaired["already_applied"] is True
    assert (directory / "findings.json").is_file()
    assert (directory / "crosscheck_report.md").is_file()
    run_tool(env, "validate", "--dir", directory)


def test_validate_accepts_container_while_next_round_is_in_progress(workspace):
    root, _ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    run_tool(env, "finish", "--dir", directory, "--round", "1")

    run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    validated = run_tool(env, "validate", "--dir", directory)
    assert validated["rounds"] == 2
    assert validated["completed_rounds"] == 1


def test_history_compare_skips_stale_rounds(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    run_tool(env, "finish", "--dir", directory, "--round", "1")

    run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    write_fresh(directory / "crosscheck_round_2.fresh.json", fresh_payload(2), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "2")
    write_json(directory / "crosscheck_round_2.json", fresh_payload(2))
    (ticket / "04_code_review_fix.md").write_text("# changed\n", encoding="utf-8")
    run_tool(env, "finish", "--dir", directory, "--round", "2", expected=1)

    third = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    assert third["round"] == 3
    write_fresh(directory / "crosscheck_round_3.fresh.json", fresh_payload(3), env)
    frozen = run_tool(env, "freeze", "--dir", directory, "--round", "3")
    assert frozen["previous_round"].endswith("crosscheck_round_1.json")
    final = fresh_payload(3)
    final["findings"][0]["status"] = "still_present"
    write_json(directory / "crosscheck_round_3.json", final)
    run_tool(env, "finish", "--dir", directory, "--round", "3")
    run_tool(env, "validate", "--dir", directory)


def test_status_change_during_review_becomes_stale_input(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    metadata = json.loads((ticket / ".ico_metadata.json").read_text(encoding="utf-8"))
    metadata["status"] = "code_done"
    write_json(ticket / ".ico_metadata.json", metadata)
    stale = run_tool(env, "finish", "--dir", directory, "--round", "1", expected=1)
    assert stale["state"] == "stale_input"


def test_validate_detects_tampered_derived_report(workspace):
    root, _ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    write_json(directory / "crosscheck_round_1.json", fresh_payload(1))
    run_tool(env, "finish", "--dir", directory, "--round", "1")
    (directory / "crosscheck_report.md").write_text("tampered\n", encoding="utf-8")
    denied = run_tool(env, "validate", "--dir", directory, expected=1)
    assert "report" in denied["error"].lower() or "报告" in denied["error"]


def test_validate_detects_tampered_stale_final(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    write_fresh(directory / "crosscheck_round_1.fresh.json", fresh_payload(1), env)
    run_tool(env, "freeze", "--dir", directory, "--round", "1")
    final_path = directory / "crosscheck_round_1.json"
    write_json(final_path, fresh_payload(1))
    (ticket / "03_plan_final.md").write_text("changed\n", encoding="utf-8")
    run_tool(env, "finish", "--dir", directory, "--round", "1", expected=1)
    changed = fresh_payload(1)
    changed["summary"] = "tampered stale draft"
    write_json(final_path, changed)
    denied = run_tool(env, "validate", "--dir", directory, expected=1)
    assert "final" in denied["error"]


def test_ticket_physical_project_root_wins_over_stale_metadata_path(workspace, tmp_path):
    root, ticket, env = workspace
    stale_root = tmp_path / "old-existing-project"
    stale_root.mkdir()
    metadata = json.loads((ticket / ".ico_metadata.json").read_text(encoding="utf-8"))
    metadata["project_path"] = str(stale_root)
    write_json(ticket / ".ico_metadata.json", metadata)
    started = run_tool(env, "start", "--workspace", root, ticket)
    assert Path(started["crosscheck_dir"]).parent == root / ".ai" / "icode" / ".crosscheck"
    assert not (stale_root / ".ai" / "icode" / ".crosscheck").exists()


def test_manifest_paths_and_container_symlinks_fail_closed(workspace):
    root, _ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    manifest_path = directory / "crosscheck_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rounds"][0]["fresh_file"] = "../outside.json"
    write_json(manifest_path, manifest)
    denied = run_tool(env, "validate", "--dir", directory, expected=1)
    assert denied["gate_id"] == "crosscheck_manifest_schema"

    manifest["rounds"][0]["fresh_file"] = "crosscheck_round_1.fresh.json"
    write_json(manifest_path, manifest)
    alias = directory.parent / "icode_2"
    alias.symlink_to(directory, target_is_directory=True)
    denied_alias = run_tool(env, "validate", "--dir", alias, expected=1)
    assert denied_alias["gate_id"] == "crosscheck_symlink"


def test_manifest_target_cannot_be_redirected_by_symlink(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    directory = Path(started["crosscheck_dir"])
    replacement = ticket.parent / "icode_2"
    shutil.copytree(ticket, replacement)
    shutil.rmtree(ticket)
    ticket.symlink_to(replacement, target_is_directory=True)

    denied = run_tool(env, "validate", "--dir", directory, expected=1)
    assert denied["gate_id"] == "target_symlink"


def test_start_resume_rejects_nested_target_path_redirected_by_symlink(workspace):
    root, ticket, env = workspace
    started = run_tool(env, "start", "--workspace", root, "--ticket", "demo-1")
    manifest_path = Path(started["crosscheck_dir"]) / "crosscheck_manifest.json"
    manifest_before = manifest_path.read_bytes()
    replacement = ticket.parent / "icode_2"
    shutil.copytree(ticket, replacement)
    shutil.rmtree(ticket)
    ticket.symlink_to(replacement, target_is_directory=True)

    denied = run_tool(env, "start", "--workspace", root, ticket / "01_plan.md", expected=1)
    assert denied["gate_id"] == "crosscheck_manifest_identity"
    assert manifest_path.read_bytes() == manifest_before
