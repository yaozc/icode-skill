"""Link classification and pre-resolution checks across evidence entry points."""
import importlib
import json
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools import icode_crosscheck as crosscheck
from tools import icode_state as state
from tools import inspection_worklist as worklist
from tools import test_result_summary as reports
from tools import workflow_contract as contract


def tag_path(monkeypatch, path, tag=0xA000001D, attributes=0):
    original = Path.lstat

    def lstat(self, *args, **kwargs):
        if self == path:
            info = original(self, *args, **kwargs)
            values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
            values.update(st_mode=stat.S_IFREG | 0o600, st_reparse_tag=tag,
                          st_file_attributes=attributes)
            return SimpleNamespace(**values)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)


@pytest.mark.parametrize("tag,expected", [
    (0xA000001D, True), (0xA000000C, True), (0xA0000003, True),
    (0x80000017, False), (0, False),
])
def test_link_tags_are_classified_by_type(tmp_path, monkeypatch, tag, expected):
    api = importlib.import_module("tools.path_safety")
    path = tmp_path / "file"
    path.write_text("source")
    tag_path(monkeypatch, path, tag, attributes=0x400)
    assert api.is_link(path) is expected


@pytest.mark.parametrize("component", ["root", "parent", "leaf"])
def test_lx_link_is_rejected_before_source_read(tmp_path, monkeypatch, component):
    root = tmp_path / "project"
    parent = root / "src"
    parent.mkdir(parents=True)
    source = parent / "feature.py"
    source.write_text("value = 1\n")
    tagged = {"root": root, "parent": parent, "leaf": source}[component]
    tag_path(monkeypatch, tagged)
    with pytest.raises(ValueError, match="(?i)link"):
        contract.file_hash(root, "src/feature.py")
    assert state._validate_code_files(["src/feature.py"], root)
    with pytest.raises(worklist.InspectionError, match="link"):
        worklist._path(root, "src/feature.py")
    with pytest.raises(crosscheck.CrosscheckError, match="链接|link"):
        crosscheck.capture_target_snapshot(
            {"project_root": str(root), "ticket_dir": str(root)},
            {"code_files": ["src/feature.py"]},
        )


def test_nonlink_reparse_source_remains_readable(tmp_path, monkeypatch):
    source = tmp_path / "feature.py"
    source.write_text("value = 1\n")
    tag_path(monkeypatch, source, 0x80000017, attributes=0x400)
    assert len(contract.file_hash(tmp_path, "feature.py")) == 64
    assert worklist._path(tmp_path, "feature.py") == "feature.py"
    assert not state._validate_code_files(["feature.py"], tmp_path)


@pytest.mark.parametrize("component", ["root", "parent", "leaf"])
def test_report_entry_rejects_lx_without_attribute_bit(tmp_path, monkeypatch, component):
    root = tmp_path / "project"
    parent = root / "reports"
    parent.mkdir(parents=True)
    report = parent / "unit.xml"
    report.write_text('<testsuite><testcase name="ok"/></testsuite>')
    tag_path(monkeypatch, {"root": root, "parent": parent, "leaf": report}[component])
    with pytest.raises(reports.ReportError, match="link|reparse"):
        reports.report_path("reports/unit.xml", root)


def test_report_retains_stricter_nonlink_reparse_policy(tmp_path, monkeypatch):
    report = tmp_path / "unit.xml"
    report.write_text('<testsuite><testcase name="ok"/></testsuite>')
    tag_path(monkeypatch, report, 0x80000017, attributes=0x400)
    with pytest.raises(reports.ReportError, match="reparse"):
        reports.report_path("unit.xml", tmp_path)


def test_real_parent_alias_is_rejected_before_resolution(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "feature.py").write_text("value = 1\n")
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="link"):
        contract.file_hash(alias, "feature.py")
    assert state._validate_code_files(["feature.py"], alias)
    with pytest.raises(crosscheck.CrosscheckError, match="链接|link"):
        crosscheck.workspace_from_cwd(str(alias))


def test_artifact_parent_link_is_not_hidden_by_resolve(tmp_path, monkeypatch):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "plan.md").write_text("plan\n")
    tag_path(monkeypatch, nested)
    assert "link" in state._artifact_path_error(tmp_path, "plan", "nested/plan.md")


def test_snapshot_tree_never_reads_lx_target(tmp_path, monkeypatch):
    source = tmp_path / "file"
    source.write_text("unreadable link body")
    tag_path(monkeypatch, source)
    with pytest.raises(crosscheck.CrosscheckError, match="链接|link"):
        crosscheck.snapshot_tree(tmp_path)


def test_indexed_run_is_checked_before_resolve(tmp_path, monkeypatch):
    project = tmp_path / "project"
    run = project / ".ai" / "icode" / "icode_1"
    run.mkdir(parents=True)
    index = tmp_path / "index"
    index.mkdir()
    (index / "index.json").write_text(json.dumps({"tickets": [{
        "ticket_id": "ticket", "project_path": str(project),
        "out_dir": ".ai/icode/icode_1", "status": "completed",
    }]}))
    tag_path(monkeypatch, run)
    with pytest.raises(ValueError, match="out_dir.*symlink"):
        state._indexed_ticket_candidates(project, index, "ticket")


def test_contract_project_does_not_erase_raw_run_link(tmp_path, monkeypatch):
    run = tmp_path / ".ai" / "icode" / "icode_1"
    run.mkdir(parents=True)
    tag_path(monkeypatch, run)
    with pytest.raises(ValueError, match="symlink"):
        contract._project({"project_path": str(tmp_path)}, run)


def test_cli_link_finds_helpers_next_to_actual_script(tmp_path):
    tool = Path(crosscheck.__file__).resolve()
    launcher = tmp_path / "crosscheck.py"
    launcher.symlink_to(tool)
    result = subprocess.run([sys.executable, "-I", str(launcher), "--help"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_unrelated_index_project_cannot_block_local_resolution(tmp_path):
    project = tmp_path / "project"
    other = tmp_path / "other"
    index = tmp_path / "index"
    for directory in (project, other, index):
        directory.mkdir()
    alias = tmp_path / "other-alias"
    alias.symlink_to(other, target_is_directory=True)
    (index / "index.json").write_text(json.dumps({"tickets": [{
        "ticket_id": "same-id", "project_path": str(alias),
        "out_dir": ".ai/icode/icode_1", "status": "completed",
    }]}))
    assert state._indexed_ticket_candidates(project, index, "same-id") == []


def test_workspace_dotdot_does_not_erase_link_component(tmp_path):
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (project / "redirect").symlink_to(outside, target_is_directory=True)
    with pytest.raises(worklist.InspectionError, match="link"):
        worklist._workspace(project / "redirect" / "..")
