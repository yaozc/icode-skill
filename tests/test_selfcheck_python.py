"""Maintenance shell dispatch; pytest calls in the fixture are recorded, not run."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENTRIES = (
    "tools/selfcheck_crosscheck.sh",
    "tools/selfcheck_inspection_worklist.sh",
    "tests/test_crosscheck_contract.sh",
    "tests/test_inspection_worklist_contract.sh",
    "tests/test_crosscheck_demo_sim.sh",
)


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def python_wrapper(path, *, target=None, launcher=False):
    body = (
        f"#!{sys.executable}\n"
        "import json, os, pathlib, runpy, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['CALL_LOG'], 'a') as stream:\n"
        "    stream.write(json.dumps({'exe': __file__, 'args': args,\n"
        "        'test': os.environ.get('ICODEX_TEST_PYTHON_BIN'),\n"
        "        'runtime': os.environ.get('ICODEX_ADAPTER_PYTHON_BIN')}) + '\\n')\n"
    )
    if target is not None:
        if launcher:
            body += "assert args.pop(0) == '-3'\n"
        body += f"os.execv({str(target)!r}, [{str(target)!r}, *args])\n"
    else:
        body += (
            "sys.executable = __file__\n"
            "if args[:2] == ['-m', 'pytest']:\n"
            "    print('fixture: pytest dispatch recorded')\n"
            "elif args[0] == '-c':\n"
            "    sys.argv = ['-c', *args[2:]]\n"
            "    exec(compile(args[1], '<string>', 'exec'), {'__name__': '__main__'})\n"
            "elif args[0] == '-m':\n"
            "    sys.argv = args[1:]\n"
            "    runpy.run_module(args[1], run_name='__main__', alter_sys=True)\n"
            "elif args[0] == '-':\n"
            "    sys.argv = args\n"
            "    exec(compile(sys.stdin.read(), '<stdin>', 'exec'), {'__name__': '__main__'})\n"
            "else:\n"
            "    sys.argv = args\n"
            "    runpy.run_path(args[0], run_name='__main__')\n"
        )
    return executable(path, body)


@pytest.fixture
def shell_case(tmp_path):
    if os.name == "nt" or not Path("/bin/bash").is_file():
        pytest.skip("POSIX Bash fixture; Windows launcher selection is simulated")
    repo = tmp_path / "repo"
    for directory in ("tools", "schemas", "demo"):
        shutil.copytree(ROOT / directory, repo / directory)
    (repo / "tests").mkdir()
    for relative in ENTRIES:
        if relative.startswith("tests/"):
            shutil.copy2(ROOT / relative, repo / relative)
    shutil.copy2(ROOT / "tests/test_crosscheck.py", repo / "tests/test_crosscheck.py")
    (repo / "mcp").mkdir()
    shutil.copy2(ROOT / "mcp/codex-python.sh", repo / "mcp/codex-python.sh")
    binary = tmp_path / "bin"
    binary.mkdir()
    for name in ("bash", "dirname", "mktemp", "sleep", "rm", "cmp", "seq",
                 "cp", "rg", "git", "tail"):
        command = shutil.which(name)
        assert command is not None, f"fixture command missing: {name}"
        (binary / name).symlink_to(command)
    executable(binary / "uname", "#!/bin/sh\nprintf 'Linux\\n'\n")
    chosen = python_wrapper(tmp_path / "Python runtime" / "python chosen")
    log = tmp_path / "calls.jsonl"
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("ICODEX_")
        and key not in {"MSYSTEM", "PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV"}
    }
    env.update(
        PATH=str(binary), CALL_LOG=str(log), PYTHONDONTWRITEBYTECODE="1",
        ICODEX_ADAPTER_PYTHON_BIN=str(tmp_path / "runtime override must not run"),
        ICODEX_PYTHON_BIN=str(tmp_path / "MCP override must not run"),
    )
    return repo, binary, chosen, log, env


def run_entry(case, relative, *, timeout=20):
    repo, _, _, _, env = case
    args = ["/bin/bash", str(repo / relative)]
    if relative.startswith("tools/selfcheck_"):
        args.append("1")
    return subprocess.run(args, env=env, text=True, capture_output=True, timeout=timeout)


def calls(log):
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def resolve(case):
    repo, _, _, _, env = case
    return subprocess.run(
        ["/bin/bash", "-c",
         'source "$1/tools/test-python.sh" || exit; printf "%s\\n" "$ICODEX_TEST_PYTHON_BIN"',
         "fixture", str(repo)],
        env=env, capture_output=True, text=True, timeout=8,
    )


@pytest.mark.parametrize("relative", ENTRIES)
def test_selected_python_reaches_every_shell_and_pytest(shell_case, relative):
    _, binary, chosen, log, env = shell_case
    fallback = python_wrapper(binary / "python3")
    env["ICODEX_TEST_PYTHON_BIN"] = str(chosen)
    result = run_entry(shell_case, relative)
    assert result.returncode == 0, result.stdout + result.stderr
    recorded = calls(log)
    assert recorded and not any(row["exe"] == str(fallback) for row in recorded)
    consumers = [row for row in recorded if row["args"][0] != "-c"]
    assert consumers
    assert all(row["exe"] == str(chosen) and row["test"] == str(chosen) for row in consumers)
    assert all(row["runtime"] == env["ICODEX_ADAPTER_PYTHON_BIN"] for row in consumers)
    if relative.startswith("tools/selfcheck_"):
        expected = ("tests/test_crosscheck.py" if "crosscheck" in relative
                    else "tests/test_inspection_worklist.py")
        assert any(row["args"] == ["-m", "pytest", "-p", "no:anyio", expected, "-q"]
                   for row in consumers)
    if relative == "tools/selfcheck_crosscheck.sh":
        assert any(row["args"][0].endswith("icode_crosscheck.py") for row in consumers)


@pytest.mark.parametrize("relative", ENTRIES)
def test_invalid_explicit_override_never_falls_back(shell_case, relative):
    _, binary, _, log, env = shell_case
    python_wrapper(binary / "python3")
    env["ICODEX_TEST_PYTHON_BIN"] = str(executable(binary / "broken", "#!/bin/sh\nexit 0\n"))
    result = run_entry(shell_case, relative)
    assert result.returncode != 0, result.stdout
    assert "ICODEX_TEST_PYTHON_BIN" in result.stderr
    assert calls(log) == []


@pytest.mark.parametrize("override", ["missing executable", "py -3"])
def test_missing_path_and_command_string_are_not_reinterpreted(shell_case, override):
    _, binary, _, log, env = shell_case
    python_wrapper(binary / "python3")
    env["ICODEX_TEST_PYTHON_BIN"] = override
    result = resolve(shell_case)
    assert result.returncode != 0
    assert "ICODEX_TEST_PYTHON_BIN" in result.stderr
    assert calls(log) == []


@pytest.mark.parametrize("windows", [False, True])
def test_launcher_is_pinned_to_sys_executable_for_child_shell(shell_case, windows):
    repo, binary, chosen, log, env = shell_case
    if windows:
        python_wrapper(binary / "python3")
        env["MSYSTEM"] = "MINGW64"
    else:
        executable(binary / "python3", "#!/bin/sh\nexit 0\n")
    launcher = python_wrapper(binary / "py", target=chosen, launcher=True)
    result = resolve(shell_case)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(chosen)
    selected = calls(log)
    assert selected[0]["exe"] == str(launcher) and selected[0]["args"][0] == "-3"
    assert not any(row["exe"] == str(binary / "python3") for row in selected)
    log.unlink()
    # The child cannot select the launcher again, even when it remains preferred.
    env["ICODEX_TEST_PYTHON_BIN"] = result.stdout.strip()
    child = run_entry(shell_case, "tests/test_crosscheck_contract.sh")
    assert child.returncode == 0, child.stdout + child.stderr
    assert all(row["exe"] == str(chosen) for row in calls(log))


def test_python_named_fallback_and_no_available_python(shell_case):
    _, binary, chosen, log, _ = shell_case
    fallback = python_wrapper(binary / "python", target=chosen)
    result = resolve(shell_case)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(chosen)
    fallback.unlink()
    log.unlink()
    result = resolve(shell_case)
    assert result.returncode != 0
    assert "ICODEX_TEST_PYTHON_BIN" in result.stderr
    assert calls(log) == []


def test_helper_does_not_mutate_runtime_override_or_array(shell_case):
    repo, _, chosen, _, env = shell_case
    env["ICODEX_TEST_PYTHON_BIN"] = str(chosen)
    result = subprocess.run(
        ["/bin/bash", "-uc",
         'ICODEX_ADAPTER_PYTHON=("runtime choice" "-flag"); '
         'source "$1/tools/test-python.sh" || exit; '
         'printf "%s\\n" "$ICODEX_ADAPTER_PYTHON_BIN" "${ICODEX_ADAPTER_PYTHON[@]}" "$ICODEX_PYTHON_BIN"',
         "fixture", str(repo)],
        env=env, text=True, capture_output=True, timeout=8,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        env["ICODEX_ADAPTER_PYTHON_BIN"], "runtime choice", "-flag", env["ICODEX_PYTHON_BIN"],
    ]


def test_explicit_probe_timeout_reaps_child_without_fallback(shell_case, tmp_path):
    _, binary, _, log, env = shell_case
    pid_path = tmp_path / "probe.pid"
    hanging = executable(
        binary / "hanging",
        f"#!{sys.executable}\nimport os, signal, time\nfrom pathlib import Path\n"
        f"Path({str(pid_path)!r}).write_text(str(os.getpid()))\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(30)\n",
    )
    python_wrapper(binary / "python3")
    env["ICODEX_TEST_PYTHON_BIN"] = str(hanging)
    result = resolve(shell_case)
    assert result.returncode != 0
    assert "ICODEX_TEST_PYTHON_BIN" in result.stderr and "timed out" in result.stderr
    assert pid_path.is_file(), result.stderr
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_path.read_text()), 0)
    assert calls(log) == []
