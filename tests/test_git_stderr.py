"""Bounded Git diagnostics must not block either output stream or cleanup."""
import os
import select
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from tools import inspection_worklist as api


@pytest.fixture(params=["native", "windows-poll"])
def backend(request, monkeypatch):
    if request.param == "windows-poll":
        if os.name == "nt":
            pytest.skip("POSIX readiness stand-in; native case exercises Windows")

        def windows_ready():
            return lambda stream: 65536 if select.select([stream], [], [], 0)[0] else 0

        monkeypatch.setattr(api, "_git_windows_ready", windows_ready, raising=False)
        monkeypatch.setattr(api, "os", SimpleNamespace(**dict(vars(os), name="nt")))
    return request.param


def spawn_script(monkeypatch, script):
    children = []
    popen = subprocess.Popen

    def spawn(command, **kwargs):
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        child = popen([sys.executable, "-B", "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(api.subprocess, "Popen", spawn)
    return children


def assert_closed(children):
    assert len(children) == 1
    child = children[0]
    assert child.poll() is not None
    assert child.stdout.closed
    assert child.stderr is not None and child.stderr.closed


def test_non_repository_reports_real_git_diagnostic(tmp_path, backend):
    with pytest.raises(api.InspectionError) as caught:
        api._git(tmp_path, ["status", "--porcelain"])
    assert "not a git repository" in str(caught.value)


@pytest.mark.parametrize("payload,marker,tail", [
    (b"", "complete", b""),
    (b"fatal: fixture failure\n", "complete", b"fatal: fixture failure\n"),
    (b"x" * 8192, "complete", b"x" * 8192),
    (b"HEAD-OMITTED" + b"x" * (1024 * 1024) + b"TAIL\n",
     "truncated", b"x" * (8192 - 5) + b"TAIL\n"),
    (b"x" * 8191 + b"\xff", "complete", b"x" * 8191 + b"\xff"),
], ids=["empty", "short", "exact-limit", "flood-tail", "invalid-utf8"])
def test_nonzero_exit_retains_only_last_8192_bytes(
        tmp_path, monkeypatch, backend, payload, marker, tail):
    # Generate the large body in the child, keeping argv below platform limits.
    if len(payload) > 8192:
        expression = "b'HEAD-OMITTED' + b'x' * (1024 * 1024) + b'TAIL\\n'"
    else:
        expression = repr(payload)
    children = spawn_script(
        monkeypatch, "import os,sys; os.write(2, " + expression + "); sys.exit(7)")
    with pytest.raises(api.InspectionError) as caught:
        api._git(tmp_path, ["fixture"])
    message = str(caught.value)
    assert "git failed: fixture" in message
    assert message.partition("stderr [" + marker + "]: ")[2] == tail.decode(
        "utf-8", errors="replace")
    assert "HEAD-OMITTED" not in message
    assert_closed(children)


def test_stderr_flood_is_drained_without_consuming_stdout_budget(
        tmp_path, monkeypatch, backend):
    children = spawn_script(monkeypatch, """
import os
for _ in range(64):
    os.write(2, b'e' * 65536)
    os.write(1, b'o')
""")
    assert api._git(tmp_path, ["fixture"], 64) == (b"o" * 64, False)
    assert_closed(children)


def test_stdout_limit_still_kills_and_reaps_child(
        tmp_path, monkeypatch, backend):
    children = spawn_script(monkeypatch, """
import os
while True:
    os.write(2, b'warning\\n')
    os.write(1, b'x' * 65536)
""")
    assert api._git(tmp_path, ["fixture"], 20) == (b"x" * 20, True)
    assert_closed(children)


def test_timeout_preserves_stderr_and_closes_both_pipes(
        tmp_path, monkeypatch, backend):
    children = spawn_script(monkeypatch, """
import os,time
os.write(2, b'fatal before timeout\\n')
time.sleep(10)
""")
    monkeypatch.setattr(api, "_GIT_READ_TIMEOUT_SECONDS", .2)
    monkeypatch.setattr(api, "_GIT_CLEANUP_TIMEOUT_SECONDS", .1)
    started = time.monotonic()
    with pytest.raises(api.InspectionError, match="timeout") as caught:
        api._git(tmp_path, ["fixture"])
    assert time.monotonic() - started < 1.5
    assert "stderr [incomplete]: fatal before timeout\n" in str(caught.value)
    assert_closed(children)


def test_continuous_stderr_flood_obeys_execution_deadline(
        tmp_path, monkeypatch, backend):
    children = spawn_script(monkeypatch, """
import os
while True:
    os.write(2, b'e' * 65536)
""")
    monkeypatch.setattr(api, "_GIT_READ_TIMEOUT_SECONDS", .2)
    monkeypatch.setattr(api, "_GIT_CLEANUP_TIMEOUT_SECONDS", .1)
    started = time.monotonic()
    with pytest.raises(api.InspectionError, match="timeout") as caught:
        api._git(tmp_path, ["fixture"])
    assert time.monotonic() - started < 1.5
    assert str(caught.value).partition("stderr [truncated, incomplete]: ")[2] == "e" * 8192
    assert_closed(children)


def test_wait_after_output_eof_uses_same_deadline(
        tmp_path, monkeypatch, backend):
    children = spawn_script(monkeypatch, """
import os,time
os.write(2, b'closed output\\n')
os.close(1)
os.close(2)
time.sleep(10)
""")
    monkeypatch.setattr(api, "_GIT_READ_TIMEOUT_SECONDS", .2)
    monkeypatch.setattr(api, "_GIT_CLEANUP_TIMEOUT_SECONDS", .1)
    started = time.monotonic()
    with pytest.raises(api.InspectionError, match="timeout") as caught:
        api._git(tmp_path, ["fixture"])
    assert time.monotonic() - started < 1.5
    assert "stderr [complete]: closed output\n" in str(caught.value)
    assert_closed(children)


def test_inherited_stderr_writer_does_not_leak_reader_or_wait_forever(
        tmp_path, monkeypatch, backend):
    read_fd, write_fd = os.pipe()
    children = []
    popen = subprocess.Popen

    def spawn(command, **kwargs):
        kwargs["stderr"] = write_fd
        child = popen([sys.executable, "-B", "-c",
                       "import os,sys; os.write(2,b'fatal held stderr\\n'); sys.exit(2)"],
                      **kwargs)
        child.stderr = os.fdopen(read_fd, "rb")
        children.append(child)
        return child

    monkeypatch.setattr(api.subprocess, "Popen", spawn)
    monkeypatch.setattr(api, "_GIT_READ_TIMEOUT_SECONDS", .2)
    monkeypatch.setattr(api, "_GIT_CLEANUP_TIMEOUT_SECONDS", .1)
    before = set(threading.enumerate())
    started = time.monotonic()
    try:
        with pytest.raises(api.InspectionError) as caught:
            api._git(tmp_path, ["fixture"])
        assert time.monotonic() - started < 1.5
        assert "stderr [incomplete]: fatal held stderr\n" in str(caught.value)
        assert set(threading.enumerate()) <= before
        assert_closed(children)
    finally:
        os.close(write_fd)
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=1)
            child.stdout.close()
            child.stderr.close()


@pytest.mark.parametrize("success,count,error,expected", [
    (True, 0, 0, 0),
    (True, 37, 0, 37),
    (False, 0, 109, None),
    (False, 0, 6, "error"),
], ids=["not-ready", "available-bytes", "broken-pipe", "invalid-handle"])
def test_windows_peek_readiness_and_handle_signature(
        monkeypatch, success, count, error, expected):
    import ctypes
    from ctypes import wintypes

    handle = 2 ** 40 + 7
    calls = []

    class Peek:
        def __call__(self, actual_handle, buffer, size, read, available, left):
            calls.append(actual_handle)
            assert (buffer, size, read, left) == (None, 0, None, None)
            available._obj.value = count
            return success

    peek = Peek()

    def load(name, **kwargs):
        assert name == "kernel32" and kwargs == {"use_last_error": True}
        return SimpleNamespace(PeekNamedPipe=peek)

    monkeypatch.setattr(ctypes, "WinDLL", load, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda code: OSError(code, "fixture"), raising=False)
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(get_osfhandle=lambda fd: handle))
    ready = api._git_windows_ready()
    stream = SimpleNamespace(fileno=lambda: 42)
    if expected == "error":
        with pytest.raises(OSError) as caught:
            ready(stream)
        assert caught.value.errno == error
    else:
        assert ready(stream) == expected
    assert calls == [handle]
    assert peek.argtypes[0] is wintypes.HANDLE
    assert peek.restype is wintypes.BOOL


def test_read_failure_reaps_child_and_closes_both_pipes(tmp_path, monkeypatch):
    children = spawn_script(monkeypatch, "print('ready', flush=True)")

    def fail(fd, size):
        raise OSError("fixture read failure")

    monkeypatch.setattr(api, "os", SimpleNamespace(**dict(vars(os), read=fail)))
    with pytest.raises(api.InspectionError, match="fixture read failure"):
        api._git(tmp_path, ["fixture"])
    assert_closed(children)
