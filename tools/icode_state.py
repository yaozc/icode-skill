#!/usr/bin/env python3
"""State and artifact helpers shared by the Codex iCode workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import stat
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


ARTIFACT_KEYS: Tuple[str, ...] = (
    "requirement",
    "root_cause",
    "plan",
    "plan_review",
    "final_plan",
    "implementation",
    "deepcheck",
    "audit",
    "patches",
    "delivery_report",
    "delivery_brief",
)

FULL_PHASES: Tuple[str, ...] = (
    "diagnose",
    "plan",
    "implement",
    "self_review",
    "audit",
    "verify",
)

STAGED_STEPS: Tuple[str, ...] = ("1", "2", "3", "4", "5", "6")

MUTABLE_OVERLAY_FIELDS: Tuple[str, ...] = (
    "hit_count",
    "last_used_at",
    "stale",
    "stale_reason",
)


class PortableFileLock:
    """Advisory lock with bounded waiting and visible owner information."""

    def __init__(self, path: Path, timeout_seconds: float = 10.0):
        self.path = Path(path)
        self.timeout_seconds = timeout_seconds
        self._handle: Any = None

    def __enter__(self) -> "PortableFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._lock_nonblocking()
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    self._handle.seek(0)
                    owner = self._handle.read().strip() or "unknown owner"
                    self._handle.close()
                    self._handle = None
                    raise TimeoutError(f"timed out waiting for {self.path}; holder: {owner}")
                time.sleep(0.05)

        owner = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }
        self._handle.seek(0)
        self._handle.truncate()
        json.dump(owner, self._handle, sort_keys=True)
        self._handle.flush()
        os.fsync(self._handle.fileno())
        return self

    def _lock_nonblocking(self) -> None:
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            self._handle.write("\0")
            self._handle.flush()
            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _read_json(temporary)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _is_ordered_prefix(values: Any, expected: Sequence[str]) -> bool:
    return isinstance(values, list) and values == list(expected[: len(values)])


def _artifact_path_error(run_dir: Path, key: str, relative_path: Any) -> Optional[str]:
    if relative_path is None:
        return None
    if not isinstance(relative_path, str) or not relative_path:
        return f"artifact_map.{key} must be null or a non-empty relative path"

    root = run_dir.resolve()
    candidate = (run_dir / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return f"artifact_map.{key} escapes the run directory"
    if not candidate.is_file():
        return f"artifact_map.{key} does not reference a regular file"
    return None


def _validate_staged_prefix(completed_steps: Any) -> bool:
    if not isinstance(completed_steps, list):
        return False
    steps = list(completed_steps)
    if steps and steps[0] in ("0", "log"):
        steps = steps[1:]
    if any(step in ("0", "log") for step in steps):
        return False
    return steps == list(STAGED_STEPS[: len(steps)])


def validate_metadata(metadata: Mapping[str, Any], run_dir: Path) -> List[str]:
    """Return deterministic contract violations for one run metadata document."""

    errors: List[str] = []
    layout = metadata.get("artifact_layout")
    artifact_map = metadata.get("artifact_map")

    if layout not in ("concise", "staged"):
        errors.append("artifact_layout must be concise or staged")

    if not isinstance(artifact_map, dict):
        errors.append("artifact_map must be an object")
        artifact_map = {}
    else:
        missing = [key for key in ARTIFACT_KEYS if key not in artifact_map]
        unknown = sorted(set(artifact_map) - set(ARTIFACT_KEYS))
        if missing:
            errors.append("artifact_map is missing stable keys: " + ", ".join(missing))
        if unknown:
            errors.append("artifact_map has unknown keys: " + ", ".join(unknown))

    for key in ARTIFACT_KEYS:
        if key not in artifact_map:
            continue
        error = _artifact_path_error(run_dir, key, artifact_map[key])
        if error:
            errors.append(error)

    completed_phases = metadata.get("completed_phases")
    completed_steps = metadata.get("completed_steps")
    if layout == "concise":
        if not _is_ordered_prefix(completed_phases, FULL_PHASES):
            errors.append("completed_phases must be an ordered prefix")
        if completed_steps != []:
            errors.append("completed_steps must be empty for concise runs")
        current_phase = metadata.get("current_phase")
        if current_phase is not None and current_phase not in FULL_PHASES:
            errors.append("current_phase must be null or a full workflow phase")
        if _is_ordered_prefix(completed_phases, FULL_PHASES):
            is_complete = len(completed_phases) == len(FULL_PHASES)
            expected_phase = None if is_complete else FULL_PHASES[len(completed_phases)]
            expected_status = "completed" if is_complete else "full_in_progress"
            if current_phase != expected_phase:
                errors.append("current_phase must be the next incomplete phase")
            if metadata.get("status") != expected_status:
                errors.append(f"status must be {expected_status} for concise state")

            required_by_phase = {
                "diagnose": "root_cause",
                "plan": "plan",
                "implement": "implementation",
                "self_review": "deepcheck",
                "audit": "audit",
            }
            for phase in completed_phases:
                key = required_by_phase.get(phase)
                if key and not artifact_map.get(key):
                    errors.append(f"artifact_map.{key} is required after full phase {phase}")
    elif layout == "staged":
        if not _validate_staged_prefix(completed_steps):
            errors.append("completed_steps must be an ordered prefix")
        if completed_phases != []:
            errors.append("completed_phases must be empty for staged runs")

        status = metadata.get("status")
        if _validate_staged_prefix(completed_steps):
            numbered_steps = [step for step in completed_steps if step in STAGED_STEPS]
            allowed_status_by_count = {
                0: {"init_in_progress", "log_in_progress", "log_done"},
                1: {"plan_done", "review_in_progress"},
                2: {"review_done"},
                3: {"plan_finalized", "code_in_progress"},
                4: {"code_done", "deepcheck_in_progress"},
                5: {"deepcheck_done"},
                6: {"completed"},
            }
            if status not in allowed_status_by_count[len(numbered_steps)]:
                errors.append("status is inconsistent with completed_steps")
        status_requirements = {
            "init_in_progress": ("requirement",),
            "log_done": ("requirement", "root_cause"),
            "plan_done": ("plan",),
            "review_in_progress": ("plan",),
            "review_done": ("plan", "plan_review"),
            "plan_finalized": ("plan", "final_plan"),
            "code_in_progress": ("final_plan",),
            "code_done": ("final_plan", "implementation"),
            "deepcheck_in_progress": ("implementation",),
            "deepcheck_done": ("implementation", "deepcheck"),
            "completed": ("plan", "final_plan", "implementation", "deepcheck", "audit"),
        }
        if status in status_requirements:
            for key in status_requirements[status]:
                if not artifact_map.get(key):
                    errors.append(f"artifact_map.{key} is required for status {status}")
        if status == "code_done" and not metadata.get("code_files"):
            errors.append("code_files must be non-empty for status code_done")

    patch_count = metadata.get("patch_count", 0)
    if not isinstance(patch_count, int) or isinstance(patch_count, bool) or patch_count < 0:
        errors.append("patch_count must be a non-negative integer")
    elif patch_count > 0 and not artifact_map.get("patches"):
        errors.append("artifact_map.patches is required when patch_count > 0")

    patch_history = metadata.get("patch_history")
    if not isinstance(patch_history, list):
        errors.append("patch_history must be an array")
    elif isinstance(patch_count, int) and not isinstance(patch_count, bool):
        if len(patch_history) != patch_count:
            errors.append("patch_history length must equal patch_count")

    if metadata.get("delivery_report_generated"):
        if not artifact_map.get("delivery_report"):
            errors.append("artifact_map.delivery_report is required after delivery generation")
        if not artifact_map.get("delivery_brief"):
            errors.append("artifact_map.delivery_brief is required after delivery generation")

    if layout == "staged":
        steps = set(completed_steps if isinstance(completed_steps, list) else [])
        if "0" in steps and not artifact_map.get("requirement"):
            errors.append("artifact_map.requirement is required after staged init")
        if "log" in steps:
            if not artifact_map.get("requirement"):
                errors.append("artifact_map.requirement is required after staged log")
            if not artifact_map.get("root_cause"):
                errors.append("artifact_map.root_cause is required after staged log")
        required_by_step = {
            "1": ("plan",),
            "2": ("plan_review",),
            "3": ("final_plan",),
            "4": ("implementation",),
            "5": ("deepcheck",),
            "6": ("audit",),
        }
        for step, keys in required_by_step.items():
            if step not in steps:
                continue
            for key in keys:
                if not artifact_map.get(key):
                    errors.append(f"artifact_map.{key} is required after staged step {step}")

    return errors


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _safe_relative_target(root: Path, relative_name: str) -> Path:
    if not relative_name or Path(relative_name).is_absolute():
        raise ValueError("artifact name must be a non-empty relative path")
    target = (root / relative_name).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("artifact path escapes the run directory") from error
    return target


def publish_artifact(
    run_dir: Path,
    key: str,
    source: Path,
    relative_name: str,
    metadata_seed: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Publish a verified file, then atomically expose it through artifact_map."""

    run_dir = Path(run_dir)
    source = Path(source)
    if key not in ARTIFACT_KEYS:
        raise ValueError(f"unknown artifact key: {key}")
    if not source.is_file() or source.is_symlink():
        raise ValueError("artifact source must be a regular non-symlink file")
    target = _safe_relative_target(run_dir, relative_name)
    metadata_path = run_dir / ".ico_metadata.json"

    with PortableFileLock(run_dir / ".ico.lock"):
        if metadata_path.is_file():
            metadata = _read_json(metadata_path)
            if metadata_seed is not None:
                raise ValueError("metadata seed is only allowed when metadata does not exist")
        else:
            if metadata_seed is None:
                raise FileNotFoundError(f"metadata does not exist: {metadata_path}")
            metadata = dict(metadata_seed)
            supplied_map = metadata.get("artifact_map")
            if supplied_map not in (None, {}) and supplied_map != {key: None for key in ARTIFACT_KEYS}:
                raise ValueError("metadata seed artifact_map must be absent, empty, or all-null stable keys")
            metadata["artifact_map"] = {stable_key: None for stable_key in ARTIFACT_KEYS}
            metadata.setdefault("artifact_layout", "staged")
            metadata.setdefault(
                "workflow_kind",
                "staged_fast" if metadata.get("mode") == "fast" else "staged_full",
            )
            metadata.setdefault("current_phase", None)
            metadata.setdefault("completed_phases", [])
            metadata.setdefault("patch_count", 0)
            metadata.setdefault("patch_history", [])
            metadata.setdefault("code_files", [])
        artifact_map = metadata.get("artifact_map")
        if not isinstance(artifact_map, dict) or key not in artifact_map:
            raise ValueError("metadata does not contain the stable artifact map")

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not target.is_file() or target.is_symlink():
                raise ValueError("existing artifact target is not a regular file")
            if _sha256_file(target) != _sha256_file(source):
                raise FileExistsError(f"artifact target already contains different content: {target}")
        else:
            temporary: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    with source.open("rb") as source_handle:
                        shutil.copyfileobj(source_handle, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                if _sha256_file(temporary) != _sha256_file(source):
                    raise OSError("artifact copy verification failed")
                os.replace(temporary, target)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        metadata["artifact_map"] = dict(artifact_map)
        metadata["artifact_map"][key] = str(target.relative_to(run_dir.resolve()))
        errors = validate_metadata(metadata, run_dir)
        unrelated = [error for error in errors if not error.startswith(f"artifact_map.{key} ")]
        if unrelated:
            raise ValueError("metadata validation failed: " + "; ".join(unrelated))
        _atomic_write_json(metadata_path, metadata)
    return target


def reserve_patch_number(run_dir: Path) -> int:
    """Atomically reserve a unique patch number for one run."""

    run_dir = Path(run_dir)
    metadata_path = run_dir / ".ico_metadata.json"
    with PortableFileLock(run_dir / ".ico.lock"):
        metadata = _read_json(metadata_path)
        patch_count = metadata.get("patch_count", 0)
        patch_history = metadata.get("patch_history", [])
        if not isinstance(patch_count, int) or isinstance(patch_count, bool) or patch_count < 0:
            raise ValueError("patch_count must be a non-negative integer")
        if not isinstance(patch_history, list):
            raise ValueError("patch_history must be an array")
        number = patch_count + 1
        metadata["patch_count"] = number
        metadata["patch_history"] = list(patch_history) + [
            {
                "number": number,
                "status": "in_progress",
                "reserved_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        _atomic_write_json(metadata_path, metadata)
        return number


def finalize_patch(run_dir: Path, number: int, status: str, summary: str = "") -> Dict[str, Any]:
    """Finalize one reserved patch after its mapped artifact has been published."""

    if number < 1:
        raise ValueError("patch number must be positive")
    if status not in ("completed", "issues", "analysis_only"):
        raise ValueError("patch status must be completed, issues, or analysis_only")
    run_dir = Path(run_dir)
    metadata_path = run_dir / ".ico_metadata.json"
    with PortableFileLock(run_dir / ".ico.lock"):
        metadata = _read_json(metadata_path)
        history = metadata.get("patch_history")
        if not isinstance(history, list):
            raise ValueError("patch_history must be an array")
        matches = [position for position, item in enumerate(history) if isinstance(item, dict) and item.get("number") == number]
        if len(matches) != 1:
            raise ValueError(f"patch reservation {number} was not found exactly once")
        entry = dict(history[matches[0]])
        if entry.get("status") not in ("in_progress", status):
            raise ValueError(f"patch {number} is already finalized as {entry.get('status')}")
        if not metadata.get("artifact_map", {}).get("patches"):
            raise ValueError("patch artifact must be published before finalization")
        entry.update(
            {
                "status": status,
                "summary": summary,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        updated_history = list(history)
        updated_history[matches[0]] = entry
        metadata["patch_history"] = updated_history
        errors = validate_metadata(metadata, run_dir)
        if errors:
            raise ValueError("metadata validation failed: " + "; ".join(errors))
        _atomic_write_json(metadata_path, metadata)
        return entry


def update_metadata(run_dir: Path, updates: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply a shallow metadata transition under the run lock and validate it."""

    run_dir = Path(run_dir)
    metadata_path = run_dir / ".ico_metadata.json"
    forbidden = {"artifact_map", "patch_count", "patch_history"}.intersection(updates)
    if forbidden:
        raise ValueError("dedicated commands must update: " + ", ".join(sorted(forbidden)))
    with PortableFileLock(run_dir / ".ico.lock"):
        metadata = _read_json(metadata_path)
        metadata.update(dict(updates))
        errors = validate_metadata(metadata, run_dir)
        if errors:
            raise ValueError("metadata validation failed: " + "; ".join(errors))
        _atomic_write_json(metadata_path, metadata)
        return metadata


def upsert_index_entry(codex_root: Path, entry: Mapping[str, Any]) -> Dict[str, Any]:
    """Insert or replace one Codex index record without losing concurrent writes."""

    ticket_id = entry.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        raise ValueError("index entry requires a non-empty ticket_id")
    if entry.get("legacy_overlay") is True:
        required = {"legacy_source", "legacy_ticket_id"}
        if not required.issubset(entry):
            raise ValueError("legacy overlay requires legacy_source and legacy_ticket_id")
        allowed = {
            "ticket_id",
            "legacy_overlay",
            "legacy_source",
            "legacy_ticket_id",
            "migration_id",
            *MUTABLE_OVERLAY_FIELDS,
        }
        unexpected = sorted(set(entry) - allowed)
        if unexpected:
            raise ValueError("legacy overlay contains immutable fields: " + ", ".join(unexpected))

    codex_root = Path(codex_root)
    codex_root.mkdir(parents=True, exist_ok=True)
    with PortableFileLock(codex_root / ".index.lock"):
        index = _load_index(codex_root)
        tickets = [dict(item) for item in index.get("tickets", []) if isinstance(item, dict)]
        replacement = dict(entry)
        for position, existing in enumerate(tickets):
            if existing.get("ticket_id") == ticket_id:
                tickets[position] = replacement
                break
        else:
            tickets.append(replacement)
        updated = dict(index)
        updated["tickets"] = tickets
        updated["updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_json(codex_root / "index.json", updated)
        return updated


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_index(root: Path) -> Dict[str, Any]:
    path = Path(root) / "index.json"
    return _read_json(path) if path.is_file() else {"tickets": []}


def _entry_source(entry: Mapping[str, Any]) -> str:
    value = entry.get("legacy_source") or entry.get("out_dir") or entry.get("project_path") or ""
    return str(Path(str(value)).expanduser().resolve()) if value else ""


def _display_legacy_id(ticket_id: str, source: str) -> str:
    path_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
    return f"legacy:{ticket_id}:{path_hash}"


def load_merged_index(codex_root: Path, claude_root: Path) -> Dict[str, Any]:
    """Return a read-only ticket view with Codex precedence and legacy overlays."""

    codex_index = _load_index(codex_root)
    claude_index = _load_index(claude_root)
    codex_tickets = [dict(item) for item in codex_index.get("tickets", []) if isinstance(item, dict)]
    claude_tickets = [dict(item) for item in claude_index.get("tickets", []) if isinstance(item, dict)]

    overlays: Dict[Tuple[str, str], Dict[str, Any]] = {}
    normal_codex: List[Dict[str, Any]] = []
    for entry in codex_tickets:
        if entry.get("legacy_overlay") is True:
            key = (str(entry.get("legacy_ticket_id", "")), _entry_source(entry))
            overlays[key] = entry
        else:
            entry["source"] = "codex"
            normal_codex.append(entry)

    merged = list(normal_codex)
    codex_by_id = {str(item.get("ticket_id")): item for item in normal_codex}
    for legacy in claude_tickets:
        original_id = str(legacy.get("ticket_id", ""))
        source = _entry_source(legacy)
        overlay = overlays.get((original_id, source))
        if overlay:
            for field in MUTABLE_OVERLAY_FIELDS:
                if field in overlay:
                    legacy[field] = overlay[field]

        codex_entry = codex_by_id.get(original_id)
        if codex_entry and _entry_source(codex_entry) == source:
            continue
        if codex_entry:
            legacy["legacy_ticket_id"] = original_id
            legacy["ticket_id"] = _display_legacy_id(original_id, source)
        elif overlay:
            legacy["legacy_ticket_id"] = original_id
            legacy["ticket_id"] = str(overlay.get("ticket_id") or _display_legacy_id(original_id, source))
        legacy["source"] = "claude"
        merged.append(legacy)

    result = dict(claude_index)
    result.update({key: value for key, value in codex_index.items() if key != "tickets"})
    result["tickets"] = merged
    return result


@dataclass(frozen=True)
class MergedFile:
    key: str
    path: Path
    source: str


def _files_for_kind(kind: str, root: Path, source: str) -> Dict[str, MergedFile]:
    base = Path(root) / kind
    if not base.is_dir():
        return {}
    files: Dict[str, MergedFile] = {}
    for path in sorted(base.rglob("*")):
        if path.is_file() and not path.is_symlink():
            key = path.relative_to(base).as_posix()
            files[key] = MergedFile(key=key, path=path, source=source)
    return files


def iter_merged_files(kind: str, codex_root: Path, claude_root: Path) -> List[MergedFile]:
    if kind not in ("project_docs", "module_docs", "limits"):
        raise ValueError("kind must be project_docs, module_docs, or limits")
    files = _files_for_kind(kind, claude_root, "claude")
    files.update(_files_for_kind(kind, codex_root, "codex"))
    return [files[key] for key in sorted(files)]


def merged_source_digest(codex_root: Path, claude_root: Path) -> str:
    digest = hashlib.sha256()
    for source, root in (("codex", Path(codex_root)), ("claude", Path(claude_root))):
        index = root / "index.json"
        digest.update(f"{source}:index.json\0".encode("utf-8"))
        digest.update(_sha256_file(index).encode("ascii") if index.is_file() else b"missing")
    for kind in ("project_docs", "module_docs", "limits"):
        for item in iter_merged_files(kind, codex_root, claude_root):
            digest.update(f"{kind}:{item.key}:{item.source}\0".encode("utf-8"))
            digest.update(_sha256_file(item.path).encode("ascii"))
    return digest.hexdigest()


def _legacy_file_manifest(legacy_run: Path) -> Tuple[List[Tuple[str, str]], str]:
    entries: List[Tuple[str, str]] = []
    for root, directory_names, file_names in os.walk(legacy_run, followlinks=False):
        root_path = Path(root)
        for name in list(directory_names):
            path = root_path / name
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f"legacy migration rejects non-regular directory: {path}")
        for name in file_names:
            path = root_path / name
            mode = path.lstat().st_mode
            if path.is_symlink() or not stat.S_ISREG(mode):
                raise ValueError(f"legacy migration rejects symlink or special file: {path}")
            relative = path.relative_to(legacy_run).as_posix()
            entries.append((relative, _sha256_file(path)))
    entries.sort()
    digest = hashlib.sha256()
    for relative, file_digest in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return entries, digest.hexdigest()


def _legacy_artifact_map(directory: Path, metadata: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    candidates = {
        "requirement": ("00_init.md",),
        "root_cause": ("log_analysis.md",),
        "plan": ("01_plan.md",),
        "plan_review": ("02_review.md",),
        "final_plan": ("03_plan_final.md",),
        "implementation": ("04_code_review_fix.md",),
        "deepcheck": ("05_deepcheck.md",),
        "audit": ("06_audit.md",),
        "patches": ("08_patch.md",),
    }
    artifact_map: Dict[str, Optional[str]] = {key: None for key in ARTIFACT_KEYS}
    existing_map = metadata.get("artifact_map")
    if isinstance(existing_map, dict):
        for key in ARTIFACT_KEYS:
            value = existing_map.get(key)
            if isinstance(value, str) and value and _safe_existing_migration_file(directory, value):
                artifact_map[key] = value
    for key, names in candidates.items():
        if artifact_map[key] is not None:
            continue
        for name in names:
            if (directory / name).is_file():
                artifact_map[key] = name
                break
    return artifact_map


def _safe_existing_migration_file(directory: Path, relative: str) -> bool:
    try:
        target = _safe_relative_target(directory, relative)
    except ValueError:
        return False
    return target.is_file() and not target.is_symlink()


def _safe_ticket_id(ticket_id: str) -> str:
    safe = "".join(
        character
        if character.isascii() and (character.isalnum() or character in "._-")
        else "_"
        for character in ticket_id
    )
    return safe or "legacy"


def _validate_legacy_location(project_root: Path, legacy_run: Path) -> Tuple[Path, Path]:
    project_root = Path(project_root)
    legacy_run = Path(legacy_run)
    if project_root.is_symlink() or legacy_run.is_symlink():
        raise ValueError("project root and legacy run must not be symlinks")
    if not project_root.is_dir() or not legacy_run.is_dir():
        raise ValueError("project root and legacy run must be real directories")
    project_real = project_root.resolve()
    legacy_real = legacy_run.resolve()
    legacy_container = (project_real / ".icode_output").resolve()
    try:
        legacy_real.relative_to(legacy_container)
    except ValueError as error:
        raise ValueError("legacy run must be below project .icode_output") from error
    if legacy_real == legacy_container:
        raise ValueError("legacy run must be a child of project .icode_output")
    metadata_path = legacy_real / ".ico_metadata.json"
    _read_json(metadata_path)
    return project_real, legacy_real


def _migration_index_entry(metadata: Mapping[str, Any], target: Path, ticket_id: str) -> Dict[str, Any]:
    entry = {
        key: value
        for key, value in metadata.items()
        if key
        in {
            "requirement_summary",
            "requirement_points",
            "keywords",
            "status",
            "created_at",
            "last_used_at",
            "hit_count",
            "stale",
            "stale_reason",
            "verdict",
        }
    }
    entry.update(
        {
            "ticket_id": ticket_id,
            "legacy_ticket_id": metadata["legacy_ticket_id"],
            "legacy_source": metadata["legacy_source"],
            "migration_id": metadata["migration_id"],
            "project_path": str(target.parents[2]),
            "out_dir": str(target),
        }
    )
    return entry


def _publish_migration_index(codex_root: Path, metadata: Mapping[str, Any], target: Path) -> None:
    codex_root.mkdir(parents=True, exist_ok=True)
    with PortableFileLock(codex_root / ".index.lock"):
        index = _load_index(codex_root)
        tickets = [dict(item) for item in index.get("tickets", []) if isinstance(item, dict)]
        migration_id = str(metadata["migration_id"])
        legacy_ticket_id = str(metadata["legacy_ticket_id"])

        for entry in tickets:
            if entry.get("migration_id") == migration_id:
                return

        tickets = [
            entry
            for entry in tickets
            if not (
                entry.get("legacy_overlay") is True
                and entry.get("legacy_ticket_id") == legacy_ticket_id
                and _entry_source(entry) == str(metadata["legacy_source"])
            )
        ]
        used_ids = {str(entry.get("ticket_id")) for entry in tickets}
        ticket_id = legacy_ticket_id
        if ticket_id in used_ids:
            ticket_id = f"{legacy_ticket_id}-migrated-{migration_id[:8]}"
        tickets.append(_migration_index_entry(metadata, target, ticket_id))
        updated = dict(index)
        updated["tickets"] = tickets
        _atomic_write_json(codex_root / "index.json", updated)


def migrate_legacy_run(project_root: Path, legacy_run: Path, codex_root: Path) -> Path:
    """Copy one legacy run into Codex storage using a resumable two-stage publish."""

    project_real, legacy_real = _validate_legacy_location(project_root, legacy_run)
    source_metadata = _read_json(legacy_real / ".ico_metadata.json")
    legacy_ticket_id = str(source_metadata.get("ticket_id") or legacy_real.name)
    migration_id = hashlib.sha256(
        f"{legacy_real}{legacy_ticket_id}".encode("utf-8")
    ).hexdigest()[:16]
    destination_root = project_real / ".ai" / "icode"
    if not os.access(project_real, os.W_OK):
        raise PermissionError(f"project is not writable: {project_real}")
    destination_root.mkdir(parents=True, exist_ok=True)
    target = destination_root / f"legacy-{_safe_ticket_id(legacy_ticket_id)}-{migration_id}"
    _, manifest_digest = _legacy_file_manifest(legacy_real)

    migration_lock = destination_root / ".migration-locks" / f"{migration_id}.lock"
    with PortableFileLock(migration_lock):
        if target.exists():
            if not target.is_dir() or target.is_symlink():
                raise FileExistsError(f"migration target is not a real directory: {target}")
            prepared = _read_json(target / ".ico_metadata.json")
            if prepared.get("migration_id") != migration_id:
                raise FileExistsError(f"migration target belongs to another migration: {target}")
            if prepared.get("migration_state") not in ("prepared", "completed"):
                raise ValueError("migration target has an invalid migration_state")
            if prepared.get("legacy_manifest_sha256") != manifest_digest:
                raise ValueError("旧源在迁移后发生变化")
        else:
            temporary = Path(tempfile.mkdtemp(prefix=f".migrate-{_safe_ticket_id(legacy_ticket_id)}-", dir=destination_root))
            published = False
            try:
                entries, copied_source_digest = _legacy_file_manifest(legacy_real)
                if copied_source_digest != manifest_digest:
                    raise ValueError("legacy source changed while migration was being prepared")
                for relative, expected_digest in entries:
                    source = legacy_real / relative
                    copied = temporary / relative
                    copied.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, copied)
                    if _sha256_file(copied) != expected_digest:
                        raise OSError(f"migration copy verification failed: {relative}")

                prepared = dict(source_metadata)
                prepared.update(
                    {
                        "artifact_layout": "staged",
                        "artifact_map": _legacy_artifact_map(temporary, source_metadata),
                        "legacy_source": str(legacy_real),
                        "legacy_ticket_id": legacy_ticket_id,
                        "migration_id": migration_id,
                        "migration_at": datetime.now(timezone.utc).isoformat(),
                        "migration_schema": 1,
                        "migration_state": "prepared",
                        "legacy_manifest_sha256": manifest_digest,
                    }
                )
                _atomic_write_json(temporary / ".ico_metadata.json", prepared)
                reparsed = _read_json(temporary / ".ico_metadata.json")
                for key, value in reparsed["artifact_map"].items():
                    if value is not None and not _safe_existing_migration_file(temporary, value):
                        raise ValueError(f"migrated artifact_map.{key} is invalid")
                os.replace(temporary, target)
                published = True
            finally:
                if not published and temporary.exists():
                    shutil.rmtree(temporary)

    prepared = _read_json(target / ".ico_metadata.json")
    if prepared.get("legacy_manifest_sha256") != _legacy_file_manifest(legacy_real)[1]:
        raise ValueError("旧源在迁移后发生变化")
    _publish_migration_index(Path(codex_root), prepared, target)

    with PortableFileLock(target / ".ico.lock"):
        completed = _read_json(target / ".ico_metadata.json")
        if completed.get("migration_id") != migration_id:
            raise ValueError("published migration metadata changed unexpectedly")
        if completed.get("migration_state") != "completed":
            completed["migration_state"] = "completed"
            _atomic_write_json(target / ".ico_metadata.json", completed)
    return target


def _main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="validate run metadata")
    validate_parser.add_argument("--run-dir", required=True, type=Path)
    validate_parser.add_argument("--metadata", default=".ico_metadata.json")
    publish_parser = subparsers.add_parser("publish-artifact", help="publish a run artifact")
    publish_parser.add_argument("--run-dir", required=True, type=Path)
    publish_parser.add_argument("--key", required=True, choices=ARTIFACT_KEYS)
    publish_parser.add_argument("--source", required=True, type=Path)
    publish_parser.add_argument("--name", required=True)
    publish_parser.add_argument("--metadata-seed", type=Path)
    reserve_parser = subparsers.add_parser("reserve-patch", help="reserve a patch number")
    reserve_parser.add_argument("--run-dir", required=True, type=Path)
    finalize_parser = subparsers.add_parser("finalize-patch", help="finalize a published patch")
    finalize_parser.add_argument("--run-dir", required=True, type=Path)
    finalize_parser.add_argument("--number", required=True, type=int)
    finalize_parser.add_argument("--status", required=True, choices=("completed", "issues", "analysis_only"))
    finalize_parser.add_argument("--summary", default="")
    update_parser = subparsers.add_parser("update-metadata", help="apply a validated metadata transition")
    update_parser.add_argument("--run-dir", required=True, type=Path)
    update_parser.add_argument("--patch-json", required=True, type=Path)
    upsert_parser = subparsers.add_parser("upsert-index", help="atomically upsert one Codex index entry")
    upsert_parser.add_argument("--codex-root", required=True, type=Path)
    upsert_parser.add_argument("--entry-json", required=True, type=Path)
    merged_index_parser = subparsers.add_parser("merged-index", help="print the merged ticket index")
    merged_index_parser.add_argument("--codex-root", required=True, type=Path)
    merged_index_parser.add_argument("--claude-root", required=True, type=Path)
    merged_files_parser = subparsers.add_parser("merged-files", help="print merged knowledge files")
    merged_files_parser.add_argument("--kind", required=True, choices=("project_docs", "module_docs", "limits"))
    merged_files_parser.add_argument("--codex-root", required=True, type=Path)
    merged_files_parser.add_argument("--claude-root", required=True, type=Path)
    migrate_parser = subparsers.add_parser("migrate-legacy", help="migrate one legacy run")
    migrate_parser.add_argument("--project-root", required=True, type=Path)
    migrate_parser.add_argument("--legacy-run", required=True, type=Path)
    migrate_parser.add_argument("--codex-root", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.command == "validate":
        metadata = _read_json(args.run_dir / args.metadata)
        errors = validate_metadata(metadata, args.run_dir)
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
        return 1 if errors else 0
    if args.command == "publish-artifact":
        seed = _read_json(args.metadata_seed) if args.metadata_seed else None
        print(publish_artifact(args.run_dir, args.key, args.source, args.name, seed))
        return 0
    if args.command == "reserve-patch":
        print(reserve_patch_number(args.run_dir))
        return 0
    if args.command == "finalize-patch":
        print(json.dumps(finalize_patch(args.run_dir, args.number, args.status, args.summary), ensure_ascii=False))
        return 0
    if args.command == "update-metadata":
        print(json.dumps(update_metadata(args.run_dir, _read_json(args.patch_json)), ensure_ascii=False, indent=2))
        return 0
    if args.command == "upsert-index":
        print(json.dumps(upsert_index_entry(args.codex_root, _read_json(args.entry_json)), ensure_ascii=False, indent=2))
        return 0
    if args.command == "merged-index":
        print(json.dumps(load_merged_index(args.codex_root, args.claude_root), ensure_ascii=False, indent=2))
        return 0
    if args.command == "merged-files":
        files = [
            {"key": item.key, "path": str(item.path), "source": item.source}
            for item in iter_merged_files(args.kind, args.codex_root, args.claude_root)
        ]
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return 0
    if args.command == "migrate-legacy":
        print(migrate_legacy_run(args.project_root, args.legacy_run, args.codex_root))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
