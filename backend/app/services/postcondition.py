"""Hami Autonomy - Step 1: independent postcondition checks (C3).

One checker per operation in the step-1 table (plan sections 2 and 3d).
Each checker verifies the outcome by reading state the adapter did
not produce: re-read the file from disk, re-query the store, re-read
the run record - never trust the adapter's return value.

The gate (E4) calls :func:`check_postcondition` with the adapter's
result and the pre-execution snapshot the GATE captured before running
the adapter. The snapshot is the gate's, not the adapter's, so the
checker compares durable state against an independent baseline.

Outcomes: ``verified`` (checker passed - the gate may report success),
``unverified`` (checker failed or could not run - the gate reports
``unverified``, writes an EVENT, and does NOT claim success). A checker
never raises: any error inside a checker is an ``unverified`` outcome,
never a crash of the gate.

Adapter contracts the checkers rely on (the E1 adapters must return
these fields; the gate takes the snapshot before running the adapter):
- OP-01/OP-02/OP-07/OP-10: snapshot carries the pre-execution state
  (file hash+mtime, tree fingerprint, task status/attempts, halt flag).
- OP-03 run_local_tests: result carries ``run_record_path`` (a JSON
  file the adapter wrote with the exit code) and ``output_path``
  (the test output artifact). The checker reads both from disk.
- OP-04 edit_repo_file: result carries ``expected_sha256`` (the hash
  of the file as the adapter claims to have left it). The checker
  re-reads the file and compares hashes.
- OP-05 create_repo_file: result carries ``expected_sha256``; snapshot
  carries ``existed_before`` (False when the adapter truly created it).
- OP-06 record_event: result carries ``event_id`` and the claimed
  ``fields`` (event_type, source). The checker re-reads the WorldEvent
  row by id. The gate's audit trail is WorldEvent rows (table
  ``events``); the big Evidence model is reality-checker evidence,
  not the gate's audit trail.
- OP-08 requeue_task: the adapter records the checkpoint id in the
  task's ``evidence`` JSON under ``checkpoint_id``. The checker reads
  the task fresh and requires status "queued", attempts exactly
  previous+1, and the same checkpoint id.
- OP-09 open_blocker: the adapter marks the task "blocked" (the
  existing WorkerTask vocabulary - there is no separate blocker
  table) and writes a WorldEvent with event_type "blocker_opened"
  whose payload names the task id. The checker verifies both.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.execution_boundary import Action, Operation, Outcome

# Directories the tree fingerprint ignores: version-control metadata,
# caches, virtualenvs, and the live database file (which changes on
# every write and is not part of the repo working tree).
_FINGERPRINT_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv", "storage", ".pytest_cache",
})


def _sha256_file(path: str) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _file_mtime_ns(path: str) -> Optional[int]:
    try:
        return os.stat(path).st_mtime_ns
    except Exception:
        return None


def tree_fingerprint(root: str) -> Optional[str]:
    """Deterministic fingerprint of a working tree (relpath, size, mtime).

    Used by the gate for the OP-02 pre-execution snapshot and by the
    checker for the second read. Returns None when the root is unreadable.
    """
    try:
        digest = hashlib.sha256()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in _FINGERPRINT_SKIP_DIRS)
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                try:
                    stat = os.stat(full)
                except Exception:
                    continue
                rel = os.path.relpath(full, root)
                digest.update(f"{rel}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
        return digest.hexdigest()
    except Exception:
        return None


def _result(outcome: Outcome, evidence_ref: Optional[str], detail: str) -> dict[str, Any]:
    return {"outcome": outcome, "evidence_ref": evidence_ref, "detail": detail}


def _verified(evidence_ref: Optional[str], detail: str) -> dict[str, Any]:
    return _result(Outcome.VERIFIED, evidence_ref, detail)


def _unverified(detail: str) -> dict[str, Any]:
    return _result(Outcome.UNVERIFIED, None, detail)


# --- Individual checkers --------------------------------------------------
# Each takes (db, action, result, snapshot) and returns the dict above.


def _check_inspect_file(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    path = snapshot.get("path")
    if not isinstance(path, str) or not path:
        return _unverified("inspect_file: snapshot carries no file path.")
    current_hash = _sha256_file(path)
    if current_hash is None:
        return _unverified(f"inspect_file: file unreadable after execution: {path}.")
    if current_hash != snapshot.get("sha256"):
        return _unverified("inspect_file: file bytes changed during a read-only inspection.")
    if _file_mtime_ns(path) != snapshot.get("mtime_ns"):
        return _unverified("inspect_file: file mtime changed during a read-only inspection.")
    return _verified(f"file:{path}#{current_hash[:12]}", "inspect_file: re-read returns the same bytes; no write occurred.")


def _check_inspect_repo_state(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    root = snapshot.get("repo_root")
    if not isinstance(root, str) or not root:
        return _unverified("inspect_repo_state: snapshot carries no repo root.")
    current = tree_fingerprint(root)
    if current is None:
        return _unverified("inspect_repo_state: working tree unreadable on second read.")
    if current != snapshot.get("fingerprint"):
        return _unverified("inspect_repo_state: working tree changed during a read-only inspection.")
    if not isinstance(result.get("summary"), str) or not result["summary"].strip():
        return _unverified("inspect_repo_state: adapter returned no status summary.")
    return _verified(f"tree:{root}#{current[:12]}", "inspect_repo_state: second read agrees; no file modified.")


def _check_run_local_tests(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    record_path = result.get("run_record_path")
    output_path = result.get("output_path")
    if not isinstance(record_path, str) or not record_path:
        return _unverified("run_local_tests: adapter returned no run-record path.")
    if not isinstance(output_path, str) or not output_path:
        return _unverified("run_local_tests: adapter returned no output path.")
    try:
        with open(record_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except Exception as exc:
        return _unverified(f"run_local_tests: run record unreadable: {exc!r}.")
    if not isinstance(record, dict):
        return _unverified("run_local_tests: run record is not a JSON object.")
    recorded_exit = record.get("exit_code")
    if recorded_exit != 0:
        return _unverified(f"run_local_tests: recorded exit code is {recorded_exit!r}, not 0.")
    if result.get("exit_code") != recorded_exit:
        return _unverified("run_local_tests: adapter exit code disagrees with the stored run record.")
    try:
        size = os.path.getsize(output_path)
    except Exception:
        return _unverified(f"run_local_tests: output artifact missing: {output_path}.")
    if size <= 0:
        return _unverified("run_local_tests: output artifact is empty.")
    return _verified(f"run:{record_path}", "run_local_tests: stored run record shows exit 0 and a non-empty output artifact.")


def _check_edit_repo_file(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    path = snapshot.get("path")
    expected = result.get("expected_sha256")
    if not isinstance(path, str) or not path:
        return _unverified("edit_repo_file: snapshot carries no file path.")
    if not isinstance(expected, str) or not expected:
        return _unverified("edit_repo_file: adapter returned no expected hash.")
    current = _sha256_file(path)
    if current is None:
        return _unverified(f"edit_repo_file: file unreadable after execution: {path}.")
    if current != expected:
        return _unverified("edit_repo_file: file bytes differ from what the adapter claimed to write.")
    if current == snapshot.get("sha256"):
        return _unverified("edit_repo_file: file is unchanged - the specified edit did not land.")
    return _verified(f"file:{path}#{current[:12]}", "edit_repo_file: re-read matches the claimed edit and nothing else changed.")


def _check_create_repo_file(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    path = result.get("path") or snapshot.get("path")
    expected = result.get("expected_sha256")
    if not isinstance(path, str) or not path:
        return _unverified("create_repo_file: no file path in result or snapshot.")
    if snapshot.get("existed_before"):
        return _unverified("create_repo_file: file already existed before execution - not a creation.")
    if not isinstance(expected, str) or not expected:
        return _unverified("create_repo_file: adapter returned no expected hash.")
    current = _sha256_file(path)
    if current is None:
        return _unverified(f"create_repo_file: file missing after execution: {path}.")
    if current != expected:
        return _unverified("create_repo_file: file bytes differ from what the adapter claimed to write.")
    return _verified(f"file:{path}#{current[:12]}", "create_repo_file: file exists and its bytes match exactly.")


def _check_record_event(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    event_id = result.get("event_id")
    if not isinstance(event_id, int):
        return _unverified("record_event: adapter returned no event id.")
    row = db.get(models.WorldEvent, event_id)
    if row is None:
        return _unverified(f"record_event: no WorldEvent row with id {event_id}.")
    claimed = result.get("fields") or {}
    for field in ("event_type", "source"):
        if field in claimed and getattr(row, field, None) != claimed[field]:
            return _unverified(f"record_event: stored {field} {getattr(row, field, None)!r} != claimed {claimed[field]!r}.")
    return _verified(f"worldevent:{event_id}", "record_event: re-read by id exists with the same fields.")


def _check_read_task_state(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    task_id = snapshot.get("task_id")
    if not isinstance(task_id, int):
        return _unverified("read_task_state: snapshot carries no task id.")
    task = db.get(models.WorkerTask, task_id)
    if task is None:
        return _unverified(f"read_task_state: no WorkerTask with id {task_id}.")
    if task.status != snapshot.get("status") or task.attempts != snapshot.get("attempts"):
        return _unverified("read_task_state: second read disagrees with the first (task changed during a read).")
    return _verified(f"workertask:{task_id}", "read_task_state: second read agrees.")


def _check_requeue_task(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    task_id = snapshot.get("task_id")
    if not isinstance(task_id, int):
        return _unverified("requeue_task: snapshot carries no task id.")
    task = db.get(models.WorkerTask, task_id)
    if task is None:
        return _unverified(f"requeue_task: no WorkerTask with id {task_id}.")
    if task.status != "queued":
        return _unverified(f"requeue_task: task status is {task.status!r}, not 'queued'.")
    if task.attempts != snapshot.get("previous_attempt", 0) + 1:
        return _unverified("requeue_task: attempt count did not increment by exactly one.")
    evidence = task.evidence if isinstance(task.evidence, dict) else {}
    if evidence.get("checkpoint_id") != snapshot.get("checkpoint_id"):
        return _unverified("requeue_task: checkpoint id changed or missing after requeue.")
    return _verified(f"workertask:{task_id}", "requeue_task: queued with attempt +1 and the same checkpoint id.")


def _check_open_blocker(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    task_id = result.get("task_id")
    event_id = result.get("event_id")
    if not isinstance(task_id, int) or not isinstance(event_id, int):
        return _unverified("open_blocker: adapter returned no task id / event id.")
    task = db.get(models.WorkerTask, task_id)
    if task is None:
        return _unverified(f"open_blocker: no WorkerTask with id {task_id}.")
    if task.status != "blocked":
        return _unverified(f"open_blocker: failing task status is {task.status!r}, not 'blocked' (stopped).")
    row = db.get(models.WorldEvent, event_id)
    if row is None or row.event_type != "blocker_opened":
        return _unverified("open_blocker: no blocker_opened event record found.")
    try:
        payload = json.loads(row.payload or "{}")
    except Exception:
        payload = {}
    if isinstance(payload, dict) and payload.get("task_id") not in (task_id, str(task_id)):
        return _unverified("open_blocker: blocker event does not name the failing task.")
    return _verified(f"worldevent:{event_id}", "open_blocker: blocker record exists and the failing task is stopped.")


def _check_read_halt_state(db: Session, action: Action, result: dict, snapshot: dict) -> dict[str, Any]:
    row = db.query(models.OpHamiRuntimeControl).first()
    if row is None:
        # Fail closed: no HALT row at all is a store anomaly, read as HALT SET.
        halted = True
    else:
        halted = bool(getattr(row, "safe_mode_enabled", False))
    if halted != snapshot.get("halted"):
        return _unverified("read_halt_state: second read disagrees with the first.")
    return _verified("halt-state", "read_halt_state: second read agrees.")


_CHECKERS = {
    Operation.INSPECT_FILE: _check_inspect_file,
    Operation.INSPECT_REPO_STATE: _check_inspect_repo_state,
    Operation.RUN_LOCAL_TESTS: _check_run_local_tests,
    Operation.EDIT_REPO_FILE: _check_edit_repo_file,
    Operation.CREATE_REPO_FILE: _check_create_repo_file,
    Operation.RECORD_EVENT: _check_record_event,
    Operation.READ_TASK_STATE: _check_read_task_state,
    Operation.REQUEUE_TASK: _check_requeue_task,
    Operation.OPEN_BLOCKER: _check_open_blocker,
    Operation.READ_HALT_STATE: _check_read_halt_state,
}


def check_postcondition(
    db: Session,
    action: Action,
    result: dict | None,
    snapshot: dict | None,
) -> dict[str, Any]:
    """Run the independent postcondition check for one executed Action.

    Returns ``{"outcome": Outcome, "evidence_ref": str|None, "detail": str}``.
    Never raises: a missing checker, a bad snapshot, or any error inside
    a checker is an ``unverified`` outcome.
    """
    try:
        checker = _CHECKERS.get(action.operation)
        if checker is None:
            return _unverified(f"No postcondition checker registered for operation {action.operation!r}.")
        return checker(db, action, result or {}, snapshot or {})
    except Exception as exc:
        return _unverified(f"Postcondition checker failed closed: {exc!r}.")
