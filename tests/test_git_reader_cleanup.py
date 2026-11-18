"""Git reader 的初始化、超时和管道失败不得遗留子进程。"""
import io
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from tools import inspection_worklist as api


class Process:
    def __init__(self):
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self.returncode = None
        self.waits = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return self.returncode


@pytest.mark.parametrize("failure", ["construct", "enter", "stdout", "stderr"])
def test_selector_setup_failure_reaps_child_with_bounded_wait(tmp_path, monkeypatch, failure):
    if os.name == "nt":
        pytest.skip("POSIX selector initialization")
    process = Process()
    monkeypatch.setattr(api.subprocess, "Popen", lambda *a, **kw: process)
    class Selector:
        def __init__(self):
            if failure == "construct":
                raise RuntimeError("selector setup failed")
        def __enter__(self):
            if failure == "enter":
                raise RuntimeError("selector setup failed")
            return self
        def __exit__(self, *args):
            pass
        def register(self, stream, *args):
            if stream is getattr(process, failure):
                raise RuntimeError("selector setup failed")
    monkeypatch.setattr(api.selectors, "DefaultSelector", Selector)
    with pytest.raises(api.InspectionError, match="unavailable"):
        api._git(tmp_path, ["status"])
    assert process.poll() == -9 and process.stdout.closed and process.stderr.closed
    assert process.waits and all(t is not None and 0 < t <= 1 for t in process.waits)


def test_windows_readiness_setup_failure_reaps_child_and_closes_pipes(tmp_path, monkeypatch):
    process = Process()
    process.stdout = (tmp_path / "pipe").open("w+b")
    def unavailable():
        raise OSError("pipe readiness unavailable")
    monkeypatch.setattr(api, "os", SimpleNamespace(**dict(vars(os), name="nt")))
    monkeypatch.setattr(api, "_git_windows_ready", unavailable, raising=False)
    with pytest.raises(api.InspectionError, match="readiness unavailable"):
        api._git_pipe(process, 10, time.monotonic() + 1)
    assert process.poll() == -9 and process.stdout.closed and process.stderr.closed
    assert process.waits == [1]


def test_windows_readiness_poll_failure_reaps_child_and_closes_pipes(monkeypatch):
    process = Process()
    def fail(stream):
        raise OSError("pipe poll failed")
    monkeypatch.setattr(api, "os", SimpleNamespace(**dict(vars(os), name="nt")))
    monkeypatch.setattr(api, "_git_windows_ready", lambda: fail, raising=False)
    with pytest.raises(api.InspectionError, match="pipe poll failed"):
        api._git_pipe(process, 10, time.monotonic() + 1)
    assert process.poll() == -9 and process.stdout.closed and process.stderr.closed


def test_cleanup_timeout_is_reported_and_closes_pipe():
    process = Process()
    def timeout_wait(timeout):
        raise subprocess.TimeoutExpired("fixture", timeout)
    process.wait = timeout_wait
    with pytest.raises(api.InspectionError, match="cleanup timeout"):
        api._close_git_process(process)
    assert process.stdout.closed and process.stderr.closed


def test_pipe_wait_uses_remaining_execution_budget(monkeypatch):
    process = Process()
    process.returncode = 0
    monkeypatch.setattr(api, "os", SimpleNamespace(**dict(vars(os), name="nt")))
    monkeypatch.setattr(api, "_git_windows_ready", lambda: lambda stream: None)
    clock = iter([9.8, 9.95])
    monkeypatch.setattr(api.time, "monotonic", lambda: next(clock))
    assert api._git_pipe(process, 100, 10) == (b"", False, "stderr [complete]: ")
    assert process.waits == [pytest.approx(.05), api._GIT_CLEANUP_TIMEOUT_SECONDS]
    assert process.stdout.closed and process.stderr.closed


def test_pipe_timeout_does_not_wait_for_an_inherited_writer(monkeypatch):
    read_fd, write_fd = os.pipe()
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"],
                               stdout=write_fd, stderr=subprocess.PIPE)
    process.stdout = os.fdopen(read_fd, "rb")
    release = threading.Event()
    # 保留额外写端，模拟 Git 后代继承 stdout；兜底释放使旧实现也能结束。
    def hold_writer():
        try:
            release.wait(1.5)
        finally:
            os.close(write_fd)
    holder = threading.Thread(target=hold_writer)
    holder.start()
    before = set(threading.enumerate())
    monkeypatch.setattr(api, "_GIT_CLEANUP_TIMEOUT_SECONDS", .1)
    started = time.monotonic()
    try:
        with pytest.raises(api.InspectionError, match="timeout"):
            api._git_pipe(process, 100, started + .05)
        assert time.monotonic() - started < 1
        assert process.poll() is not None and process.stdout.closed
        assert process.stderr.closed
        assert set(threading.enumerate()) <= before
    finally:
        release.set()
        holder.join(timeout=2)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


@pytest.mark.parametrize("script,limit,expected", [
    ("import time; time.sleep(3)", 100, "timeout"),
    ("print('x' * 1000000)", 20, "truncated"),
])
def test_real_child_is_reaped_on_timeout_or_output_limit(tmp_path, monkeypatch, script, limit, expected):
    processes = []
    popen = subprocess.Popen
    def spawn(command, **kwargs):
        assert kwargs["env"].get("GIT_NO_LAZY_FETCH") == "1"
        child = popen([sys.executable, "-c", script], **kwargs)
        processes.append(child)
        return child
    monkeypatch.setattr(api.subprocess, "Popen", spawn)
    monkeypatch.setattr(api, "_GIT_READ_TIMEOUT_SECONDS", .05, raising=False)
    if expected == "timeout":
        with pytest.raises(api.InspectionError, match="timeout"):
            api._git(tmp_path, ["fixture"], limit)
    else:
        _, truncated = api._git(tmp_path, ["fixture"], limit)
        assert truncated
    assert len(processes) == 1
    assert processes[0].poll() is not None and processes[0].stdout.closed
    assert processes[0].stderr is not None and processes[0].stderr.closed
