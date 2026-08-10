import json
import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from tools.icode_state import PortableFileLock, reserve_patch_number


def reserve_worker(run_dir: str, queue: multiprocessing.Queue) -> None:
    try:
        queue.put(("ok", reserve_patch_number(Path(run_dir))))
    except Exception as error:  # pragma: no cover - returned to the parent process
        queue.put(("error", repr(error)))


def hold_lock_worker(lock_path: str, ready: multiprocessing.Event) -> None:
    with PortableFileLock(Path(lock_path), timeout_seconds=1.0):
        ready.set()
        time.sleep(0.5)


class ConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp_dir.name)
        metadata = {"patch_count": 0, "patch_history": []}
        (self.run_dir / ".ico_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_concurrent_patch_reservations_are_unique(self) -> None:
        queue = multiprocessing.Queue()
        workers = [multiprocessing.Process(target=reserve_worker, args=(str(self.run_dir), queue)) for _ in range(4)]
        for worker in workers:
            worker.start()
        results = [queue.get(timeout=5) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
        self.assertEqual(sorted(value for status, value in results if status == "ok"), [1, 2, 3, 4])
        self.assertFalse([value for status, value in results if status == "error"])
        metadata = json.loads((self.run_dir / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["patch_count"], 4)
        self.assertEqual(len(metadata["patch_history"]), 4)

    def test_lock_timeout_reports_holder_without_partial_write(self) -> None:
        lock_path = self.run_dir / ".ico.lock"
        ready = multiprocessing.Event()
        holder = multiprocessing.Process(target=hold_lock_worker, args=(str(lock_path), ready))
        holder.start()
        self.assertTrue(ready.wait(timeout=2))
        with self.assertRaisesRegex(TimeoutError, "holder"):
            with PortableFileLock(lock_path, timeout_seconds=0.1):
                pass
        holder.join(timeout=2)
        metadata = json.loads((self.run_dir / ".ico_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["patch_count"], 0)


if __name__ == "__main__":
    unittest.main()
