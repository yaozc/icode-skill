"""Codex MCP 的解释器选择与 Windows transport，不启动真实 MCP。"""
import importlib.util
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_mcp_runtime", ROOT / "mcp/codex_adapter.py")
api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = api
SPEC.loader.exec_module(api)


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def shell_environment(tmp_path):
    if os.name == "nt" or not Path("/bin/bash").is_file():
        pytest.skip("Python launcher fixture requires POSIX Bash; Windows dispatch is simulated explicitly")
    binary = tmp_path / "bin"
    binary.mkdir()
    # 仅在夹具中控制 PATH，不改用户环境或系统解释器。
    for name in ("dirname", "mktemp", "sleep", "rm", "cmp"):
        (binary / name).symlink_to("/usr/bin/" + name if Path("/usr/bin/" + name).exists() else "/bin/" + name)
    executable(binary / "uname", "#!/bin/sh\nprintf 'Darwin\\n'\n")
    log = tmp_path / "calls.jsonl"
    codex = executable(binary / "codex", f"#!{sys.executable}\nimport json,os,sys\nwith open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps(['codex', *sys.argv[1:]])+'\\n')\nprint('[]')\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("ICODEX_") and k not in {"MSYSTEM", "PYTHONPATH"}}
    env.update(PATH=str(binary), CALL_LOG=str(log), ICODEX_CODEX_BIN=str(codex))
    return binary, log, env


def python_wrapper(path, label, *, launcher=False):
    return executable(path, f"#!{sys.executable}\nimport json,os,sys\nargs=sys.argv[1:]\nwith open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps([{label!r}, *args])+'\\n')\n" +
                      ("assert args.pop(0)=='-3'\n" if launcher else "") +
                      f"os.execv({sys.executable!r},[{sys.executable!r},*args])\n")


def entry(name, env):
    return subprocess.run(["/bin/bash", str(ROOT / "mcp" / name), "--dry-run", "memory"],
                          env=env, capture_output=True, text=True, timeout=10)


@contextmanager
def isolated_entry(name, env):
    # 进程组只用于 POSIX 测试收尾；生产代码不依赖、也不承诺后代树终止。
    process = subprocess.Popen(["/bin/bash", str(ROOT / "mcp" / name), "--dry-run", "memory"],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=7)
        yield subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=3)


def hanging_python(path, pid_path):
    return executable(path, f"#!{sys.executable}\nimport os,signal,time\nfrom pathlib import Path\nPath({str(pid_path)!r}).write_text(str(os.getpid()))\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(30)\n")


@pytest.mark.parametrize("name", ["install-codex.sh", "uninstall-codex.sh"])
def test_windows_timed_out_launcher_falls_back_and_reaps_direct_child(shell_environment, tmp_path, name):
    binary, log, env = shell_environment
    pid_path = tmp_path / "probe.pid"
    hanging_python(binary / "py", pid_path)
    python_wrapper(binary / "python3", "fallback")
    env["MSYSTEM"] = "MINGW64"
    with isolated_entry(name, env) as result:
        assert result.returncode == 0, result.stderr
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid_path.read_text()), 0)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert any(row[0] == "fallback" and row[1].endswith("codex_adapter.py") for row in calls)


@pytest.mark.parametrize("name", ["install-codex.sh", "uninstall-codex.sh"])
def test_explicit_timed_out_python_fails_without_fallback(shell_environment, tmp_path, name):
    binary, log, env = shell_environment
    pid_path = tmp_path / "probe.pid"
    env["ICODEX_ADAPTER_PYTHON_BIN"] = str(hanging_python(binary / "chosen", pid_path))
    python_wrapper(binary / "python3", "fallback")
    with isolated_entry(name, env) as result:
        assert result.returncode != 0
        assert "ICODEX_ADAPTER_PYTHON_BIN" in result.stderr and "timed out" in result.stderr
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid_path.read_text()), 0)
        assert not log.exists()


@pytest.mark.parametrize("name", ["install-codex.sh", "uninstall-codex.sh"])
def test_probe_does_not_wait_for_descendant_stdout_eof(shell_environment, tmp_path, name):
    binary, log, env = shell_environment
    child_path = tmp_path / "descendant.pid"
    executable(binary / "py", f"#!{sys.executable}\nimport subprocess,sys\nfrom pathlib import Path\nchild=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\nPath({str(child_path)!r}).write_text(str(child.pid))\nsys.stdout.write('invalid')\n")
    # 无效候选已退出，后代仍持有 stdout；回退不应等待管道 EOF。
    python_wrapper(binary / "python3", "fallback")
    env["MSYSTEM"] = "MINGW64"
    started = time.monotonic()
    with isolated_entry(name, env) as result:
        assert result.returncode == 0, result.stderr
        assert time.monotonic() - started < 4
        os.kill(int(child_path.read_text()), 0)
        assert log.exists()


@pytest.mark.parametrize("name", ["install-codex.sh", "uninstall-codex.sh"])
def test_zero_output_python_stub_falls_back_to_py_launcher(shell_environment, name):
    binary, log, env = shell_environment
    executable(binary / "python3", "#!/bin/sh\nexit 0\n")
    python_wrapper(binary / "py", "py", launcher=True)
    result = entry(name, env)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(row[0] == "py" and row[1] == "-3" and row[2].endswith("codex_adapter.py") for row in calls)


@pytest.mark.parametrize("name", ["install-codex.sh", "uninstall-codex.sh"])
def test_explicit_python_path_with_spaces_is_one_executable(shell_environment, tmp_path, name):
    _, log, env = shell_environment
    chosen = python_wrapper(tmp_path / "Python runtime" / "python chosen", "chosen")
    env["ICODEX_ADAPTER_PYTHON_BIN"] = str(chosen)
    result = entry(name, env)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[0][0] == "chosen" and calls[0][1] == "-c"
    assert any(row[0] == "chosen" and row[1].endswith("codex_adapter.py") for row in calls)


def test_explicit_invalid_python_does_not_silently_select_another(shell_environment):
    binary, log, env = shell_environment
    python_wrapper(binary / "python3", "fallback")
    broken = executable(binary / "broken", "#!/bin/sh\nexit 0\n")
    env["ICODEX_ADAPTER_PYTHON_BIN"] = str(broken)
    result = entry("install-codex.sh", env)
    assert result.returncode != 0
    assert "ICODEX_ADAPTER_PYTHON_BIN" in result.stderr
    assert not log.exists()


def test_explicit_python_command_string_is_not_shell_split(shell_environment):
    binary, log, env = shell_environment
    python_wrapper(binary / "py", "py", launcher=True)
    env["ICODEX_ADAPTER_PYTHON_BIN"] = "py -3"
    result = entry("install-codex.sh", env)
    assert result.returncode != 0
    assert "one working Python" in result.stderr
    assert not log.exists()


def test_windows_shell_prefers_py_argv_over_python3(shell_environment):
    binary, log, env = shell_environment
    python_wrapper(binary / "python3", "python3")
    python_wrapper(binary / "py", "py", launcher=True)
    env["MSYSTEM"] = "MINGW64"
    result = entry("install-codex.sh", env)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[0][:2] == ["py", "-3"]
    assert not any(row[0] == "python3" for row in calls)


def test_python_named_fallback_and_missing_runtime(shell_environment):
    binary, log, env = shell_environment
    chosen = python_wrapper(binary / "python", "python")
    result = entry("install-codex.sh", env)
    assert result.returncode == 0, result.stderr
    chosen.unlink()
    log.unlink()
    result = entry("install-codex.sh", env)
    assert result.returncode != 0
    assert "Python" in result.stderr
    assert not log.exists()


@pytest.fixture
def windows_runtime(tmp_path, monkeypatch):
    for key in ("ICODEX_NPX_BIN", "ICODEX_NODE_BIN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(api, "_is_windows", lambda: True, raising=False)
    runtime = tmp_path / "Node runtime"
    runtime.mkdir()
    node = executable(runtime / "node.exe", "fixture")
    npx = executable(runtime / "npx.cmd", "fixture")
    cli = runtime / "node_modules/npm/bin/npx-cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(api.shutil, "which", lambda name: {"node": str(node), "npx": str(npx)}.get(name))
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    return node, npx, cli


def test_windows_catalog_uses_node_cli_and_child_path(windows_runtime):
    node, _, cli = windows_runtime
    config = api.build_catalog(ROOT / "mcp")["memory"]
    assert config.command == str(node)
    assert config.args == [str(cli), "-y", api.NPM_PACKAGES["memory"]]
    assert config.env["PATH"].split(";")[0] == str(node.parent)
    assert r"C:\Windows\system32" in config.env["PATH"].split(";")
    assert "_fallback" not in vars(config)


def test_windows_child_environment_preserves_explicit_case_insensitive_path(windows_runtime):
    node, _, _ = windows_runtime
    for key in ("PATH", "Path", "path"):
        supplied = {key: r"C:\custom", "EXTRA": "kept"}
        before = dict(supplied)
        assert api._windows_env_with_node_path(str(node), supplied) == supplied
        assert supplied == before


def test_windows_explicit_npx_selects_its_own_runtime(windows_runtime, tmp_path, monkeypatch):
    _, _, _ = windows_runtime
    chosen = tmp_path / "Chosen runtime"
    chosen.mkdir()
    node = executable(chosen / "node.exe", "chosen")
    npx = executable(chosen / "npx.cmd", "chosen")
    cli = chosen / "node_modules/npm/bin/npx-cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("chosen", encoding="utf-8")
    monkeypatch.setenv("ICODEX_NPX_BIN", str(npx))
    config = api.build_catalog(ROOT / "mcp")["memory"]
    assert config.command == str(node)
    assert config.args[0] == str(cli)


def test_windows_conflicting_explicit_node_and_npx_are_rejected(windows_runtime, tmp_path, monkeypatch):
    _, npx, _ = windows_runtime
    other = executable(tmp_path / "different" / "node.exe", "other")
    other_cli = other.parent / "node_modules/npm/bin/npx-cli.js"
    other_cli.parent.mkdir(parents=True)
    other_cli.write_text("other", encoding="utf-8")
    monkeypatch.setenv("ICODEX_NPX_BIN", str(npx))
    monkeypatch.setenv("ICODEX_NODE_BIN", str(other))
    with pytest.raises(RuntimeError, match="pair|match"):
        api.build_catalog(ROOT / "mcp")


def test_windows_missing_npx_cli_does_not_fall_back_to_cmd(windows_runtime):
    _, _, cli = windows_runtime
    cli.unlink()
    with pytest.raises(RuntimeError, match="npx-cli"):
        api.build_catalog(ROOT / "mcp")


def test_explicit_node_runtime_does_not_require_npx_cmd(windows_runtime, monkeypatch):
    node, _, cli = windows_runtime
    monkeypatch.setattr(api.shutil, "which", lambda name: None)
    monkeypatch.setenv("ICODEX_NODE_BIN", str(node))
    config = api.build_catalog(ROOT / "mcp")["memory"]
    assert config.command == str(node) and config.args[0] == str(cli)


def test_missing_windows_npm_runtime_fails_before_registration(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_is_windows", lambda: True)
    monkeypatch.setattr(api.shutil, "which", lambda name: None)
    monkeypatch.delenv("ICODEX_NPX_BIN", raising=False)
    monkeypatch.delenv("ICODEX_NODE_BIN", raising=False)
    monkeypatch.setattr(api, "_list_names", lambda codex: pytest.fail("runtime failure must precede registration"))
    assert api.install(tmp_path, ["memory"], dry_run=False, auto_install=False) == 1


def test_nonwindows_catalog_preserves_existing_override(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_is_windows", lambda: False, raising=False)
    monkeypatch.setenv("ICODEX_NPX_BIN", str(tmp_path / "my npx"))
    config = api.build_catalog(ROOT / "mcp")["memory"]
    assert config.command == str(tmp_path / "my npx")
    assert config.args == ["-y", api.NPM_PACKAGES["memory"]]
    assert config.env is None


def test_windows_local_selection_and_uninstall_do_not_require_node(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_is_windows", lambda: True, raising=False)
    monkeypatch.setattr(api.shutil, "which", lambda name: None)
    monkeypatch.setattr(api, "_list_names", lambda codex: [])
    assert api.install(tmp_path, ["cheap-research"], dry_run=True, auto_install=False) == 0
    assert api.uninstall(tmp_path, ["memory"], dry_run=True, assume_yes=False) == 0


def test_windows_native_npx_override_remains_direct(windows_runtime, tmp_path, monkeypatch):
    chosen = executable(tmp_path / "custom npx.exe", "custom")
    monkeypatch.setenv("ICODEX_NPX_BIN", str(chosen))
    config = api.build_catalog(ROOT / "mcp")["memory"]
    assert config.command == str(chosen)
    assert config.args == ["-y", api.NPM_PACKAGES["memory"]]


def test_windows_native_wrapper_cannot_silently_ignore_explicit_node(windows_runtime, tmp_path, monkeypatch):
    node, _, _ = windows_runtime
    chosen = executable(tmp_path / "custom npx.exe", "custom")
    monkeypatch.setenv("ICODEX_NPX_BIN", str(chosen))
    monkeypatch.setenv("ICODEX_NODE_BIN", str(node))
    with pytest.raises(RuntimeError, match="wrapper"):
        api.build_catalog(ROOT / "mcp")


def test_windows_node_override_must_be_directly_spawnable(windows_runtime, tmp_path, monkeypatch):
    node, _, _ = windows_runtime
    shim = executable(node.parent / "node.cmd", "shim")
    monkeypatch.setenv("ICODEX_NODE_BIN", str(shim))
    with pytest.raises(RuntimeError, match="native|node.exe"):
        api.build_catalog(ROOT / "mcp")


def test_windows_registration_uses_env_argv_and_preserves_conflict(windows_runtime, monkeypatch):
    monkeypatch.setattr(api, "_list_names", lambda codex: [])
    calls = []
    monkeypatch.setattr(api, "_run_codex", lambda codex, args: calls.append(args) or subprocess.CompletedProcess(args, 0))
    assert api.install(ROOT / "mcp", ["memory"], dry_run=False, auto_install=False) == 0
    config = api.build_catalog(ROOT / "mcp")["memory"]
    assert calls == [["add", "memory", "--env", "PATH=" + config.env["PATH"], "--", config.command, *config.args]]
    calls.clear()
    assert api.install(ROOT / "mcp", ["memory"], dry_run=True, auto_install=False) == 0
    assert calls == []
    monkeypatch.setattr(api, "_list_names", lambda codex: ["memory"])
    monkeypatch.setattr(api, "_get_config", lambda *args: {"transport": api._desired_transport(config)})
    assert api.install(ROOT / "mcp", ["memory"], dry_run=False, auto_install=False) == 0
    assert calls == []
    monkeypatch.setattr(api, "_get_config", lambda *args: {"transport": {"type": "stdio", "command": "old-npx.cmd", "args": config.args}})
    assert api.install(ROOT / "mcp", ["memory"], dry_run=False, auto_install=False) == 2
    assert calls == []
