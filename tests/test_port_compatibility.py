"""Codex 上游移植的字节边界与跨平台资源回归。"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location("port_" + name, ROOT / "tools" / (name + ".py"))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icodex-port-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.inspection = module("inspection_worklist")
        self.crosscheck = module("icode_crosscheck")

    def pipe(self, code):
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.stdout.close())
        self.addCleanup(lambda: proc.wait(timeout=5))
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        return proc

    def test_pipe_output_and_budget(self):
        for size, limit, cut in ((8, 8, False), (200000, 128, True)):
            with self.subTest(size=size):
                proc = self.pipe(f"import sys; sys.stdout.buffer.write(b'x' * {size}); sys.stdout.flush()")
                data, truncated = self.inspection._git_pipe(proc, limit, time.monotonic() + 5)
                self.assertEqual(data, b"x" * min(size, limit))
                self.assertIs(truncated, cut)
                self.assertIsNotNone(proc.returncode)

    def test_pipe_timeout_reaps_process(self):
        proc = self.pipe("import time; time.sleep(30)")
        with self.assertRaisesRegex(ValueError, "timeout"):
            self.inspection._git_pipe(proc, 128, time.monotonic() + 0.1)
        self.assertIsNotNone(proc.returncode)

    def test_windows_git_dispatch_avoids_selector_and_rejects_failure(self):
        # 只替换被测模块的 os，避免改变宿主 pathlib/pytest 的平台判断。
        windows = SimpleNamespace(name="nt", environ=os.environ)
        with patch.object(self.inspection, "os", windows), patch.object(
                self.inspection.selectors, "DefaultSelector", side_effect=AssertionError("anonymous pipe select")):
            data, truncated = self.inspection._git(self.root, ["--version"])
            self.assertIn(b"git version", data)
            self.assertFalse(truncated)
            with self.assertRaisesRegex(ValueError, "git failed"):
                self.inspection._git(self.root, ["not-a-git-command"])

    def test_rooted_paths_rejected_even_with_windows_path_semantics(self):
        from pathlib import PureWindowsPath
        with patch.object(self.inspection, "Path", PureWindowsPath):
            for raw in ("/etc/passwd", "//server/share"):
                with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "unsafe path"):
                    self.inspection._path(self.root, raw)

    def test_lock_entry_failure_closes_stream(self):
        stream = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        self.addCleanup(stream.close)
        def reject(*args):
            raise PermissionError("denied")
        primitive = SimpleNamespace(LOCK_EX=1, flock=reject)
        with patch.object(Path, "open", return_value=stream), patch.object(self.crosscheck, "_fcntl_mod", primitive):
            with self.assertRaises(PermissionError):
                with self.crosscheck.DirectoryLock(self.root):
                    self.fail("lock failure entered the critical section")
        self.assertTrue(stream.closed)

    def test_windows_lock_uses_same_byte_and_closes_after_unlock_error(self):
        calls = []
        def locking(fd, operation, length):
            calls.append((os.lseek(fd, 0, os.SEEK_CUR), operation, length))
            if operation == 2:
                raise OSError("unlock denied")
        primitive = SimpleNamespace(LK_LOCK=1, LK_UNLCK=2, locking=locking)
        with patch.object(self.crosscheck, "_fcntl_mod", None), patch.object(self.crosscheck, "_msvcrt_mod", primitive):
            lock = self.crosscheck.DirectoryLock(self.root)
            with self.assertRaisesRegex(OSError, "unlock denied"):
                with lock:
                    self.assertEqual(lock.path.read_bytes(), b"\0")
            self.assertTrue(lock.stream.closed)
        self.assertEqual(calls, [(0, 1, 1), (0, 2, 1)])

    def test_real_lock_exclusion_and_release_after_owner_termination(self):
        code = """import importlib.util,sys,pathlib
spec=importlib.util.spec_from_file_location('lock_worker',sys.argv[1])
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
root=pathlib.Path(sys.argv[2]);marker=root/sys.argv[3]
marker.with_suffix('.attempt').write_bytes(b'attempt')
with api.DirectoryLock(root):
 marker.write_bytes(b'entered')
 sys.stdin.buffer.read(1)
"""
        processes = []
        def start(label):
            proc = subprocess.Popen([sys.executable, "-B", "-c", code,
                str(ROOT / "tools/icode_crosscheck.py"), str(self.root), label],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(proc)
            return proc
        def wait_file(path, proc):
            deadline = time.monotonic() + 5
            while not path.exists():
                if proc.poll() is not None:
                    self.fail("lock worker failed: " + repr(proc.communicate()[1]))
                if time.monotonic() >= deadline:
                    self.fail("lock barrier timeout")
                time.sleep(0.02)
        try:
            owner = start("owner")
            wait_file(self.root / "owner", owner)
            waiter = start("waiter")
            wait_file(self.root / "waiter.attempt", waiter)
            time.sleep(0.1)
            self.assertFalse((self.root / "waiter").exists())
            self.assertIsNone(waiter.poll())
            owner.terminate()
            owner.wait(timeout=5)
            wait_file(self.root / "waiter", waiter)
            waiter.stdin.write(b"x")
            waiter.stdin.flush()
            waiter.wait(timeout=5)
            self.assertEqual(waiter.returncode, 0, waiter.stderr.read())
            with self.crosscheck.DirectoryLock(self.root):
                pass
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    stream.close()

    def test_unsupported_lock_fails_closed(self):
        with patch.object(self.crosscheck, "_fcntl_mod", None), patch.object(self.crosscheck, "_msvcrt_mod", None):
            lock = self.crosscheck.DirectoryLock(self.root)
            with self.assertRaises(self.crosscheck.CrosscheckError):
                lock.__enter__()
            self.assertTrue(lock.stream.closed)

    def test_windows_atomic_write_skips_directory_open_and_preserves_failed_destination(self):
        target = self.root / "atomic.json"
        windows = SimpleNamespace(name="nt", fdopen=os.fdopen, fsync=os.fsync,
                                  replace=os.replace, unlink=os.unlink,
                                  open=lambda *args: self.fail("Windows directory open"))
        with patch.object(self.crosscheck, "os", windows):
            self.crosscheck.atomic_write(target, b"old\n")
            with patch.object(windows, "replace", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    self.crosscheck.atomic_write(target, b"new\n")
        self.assertEqual(target.read_bytes(), b"old\n")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_native_cli_utf8_and_imported_main_text_capture(self):
        tool = str(ROOT / "tools/icode_crosscheck.py")
        code = ("import sys,runpy;sys.stdout.reconfigure(encoding='cp1252');sys.argv="
                + repr([tool, "validate", "--dir", str(self.root / "missing")])
                + ";runpy.run_path(" + repr(tool) + ",run_name='__main__')")
        proc = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 1, proc.stderr.decode("utf-8", errors="replace"))
        self.assertIn("不存在", proc.stdout.decode("utf-8"))
        original = sys.stdout
        api = module("icode_crosscheck")
        self.assertIs(sys.stdout, original)
        text = io.StringIO()
        with patch.object(sys, "argv", [tool, "--help"]), contextlib.redirect_stdout(text):
            with self.assertRaises(SystemExit) as caught:
                api.main()
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("复评", text.getvalue())


if __name__ == "__main__":
    unittest.main()
