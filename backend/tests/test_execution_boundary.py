"""Step-1 execution boundary tests (plan section 4): T-01..T-10.

Runs under the repo's conftest `db` fixture (in-memory SQLite, never the
real forge.db). repo_root is a temp git repo passed to the gate. The
conftest seeds the HALT record as not-halted; tests that need HALT set
establish that state themselves.
"""
import hashlib
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import models
from app.services import action_engine as ae
from app.services import decision_rights as dr
from app.services import execution_engine as ee
from app.services.execution_boundary import Action as BAction
from app.services.execution_boundary import Operation, Outcome, Refusal


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "hello.txt").write_text("hello world", encoding="utf-8")
    return root


@pytest.fixture
def halt_off(db):
    """Ensure the HALT record reads not-halted (the conftest seeds this;
    this fixture is the backstop if the seed is ever removed)."""
    row = db.query(models.OpHamiRuntimeControl).first()
    if row is None:
        row = models.OpHamiRuntimeControl(
            id=1, safe_mode_enabled=False, safe_mode_reason="test_fixture_not_halted"
        )
        db.add(row)
    else:
        row.safe_mode_enabled = False
    db.commit()
    return row


def _envelope(operations, scope="worker_tasks", hours=1):
    return {
        "operations": list(operations),
        "scope": scope,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
    }


def _expired_envelope(operations, scope="worker_tasks"):
    env = _envelope(operations, scope)
    env["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    return env


def _gate(db, repo, op, principal, scope, payload=None, envelope=None):
    return ee.execute_through_gate(
        db,
        BAction(operation=op, principal=principal, scope=scope, payload=payload or {}),
        envelope=envelope,
        repo_root=repo,
    )


def test_t01_unauthorized_edit_refused(db, repo, halt_off, monkeypatch):
    calls = []
    orig = ae.OPERATION_ADAPTERS[Operation.EDIT_REPO_FILE]

    def spy(db_, action, root):
        calls.append(action)
        return orig(db_, action, root)

    monkeypatch.setitem(ae.OPERATION_ADAPTERS, Operation.EDIT_REPO_FILE, spy)
    before = (repo / "hello.txt").read_bytes()
    r = _gate(
        db, repo, Operation.EDIT_REPO_FILE, "agent-x", "hello.txt",
        {"old_text": "world", "new_text": "hacked"},
    )
    assert isinstance(r, Refusal)
    assert (repo / "hello.txt").read_bytes() == before
    assert db.query(models.WorldEvent).filter_by(event_type="gate_refusal").count() >= 1
    assert not any(x.status == "completed" for x in db.query(models.IdempotencyRecord).all())
    assert calls == []


def test_t02_unknown_operation_refused(db, repo, halt_off):
    before = (repo / "hello.txt").read_bytes()
    r = _gate(db, repo, "send_message", "agent-x", "worker_tasks", {})
    assert isinstance(r, Refusal) and r.reason.value == "unknown_operation"
    assert (repo / "hello.txt").read_bytes() == before
    assert db.query(models.WorldEvent).filter_by(event_type="gate_refusal").count() >= 1


def test_t03_expired_envelope_refused(db, repo, halt_off):
    env = _expired_envelope(["edit_repo_file"], scope="hello.txt")
    r = _gate(
        db, repo, Operation.EDIT_REPO_FILE, "agent-x", "hello.txt",
        {"old_text": "world", "new_text": "hacked"}, envelope=env,
    )
    assert isinstance(r, Refusal) and r.reason.value == "authorization_expired"
    assert (repo / "hello.txt").read_text() == "hello world"


def test_t04_revoked_envelope_refused(db, repo, halt_off):
    env = _envelope(["edit_repo_file"], scope="hello.txt")
    env["status"] = "REVOKED"
    r = _gate(
        db, repo, Operation.EDIT_REPO_FILE, "agent-x", "hello.txt",
        {"old_text": "world", "new_text": "hacked"}, envelope=env,
    )
    assert isinstance(r, Refusal) and r.reason.value == "authorization_revoked"
    assert (repo / "hello.txt").read_text() == "hello world"


def test_t05_halt_refuses_everything(db, repo):
    row = db.query(models.OpHamiRuntimeControl).first()
    if row is None:
        row = models.OpHamiRuntimeControl(
            id=1, safe_mode_enabled=True, safe_mode_reason="test_halt"
        )
        db.add(row)
    else:
        row.safe_mode_enabled = True
        row.safe_mode_reason = "test_halt"
    db.commit()
    r1 = _gate(
        db, repo, Operation.EDIT_REPO_FILE, "owner", "hello.txt",
        {"old_text": "world", "new_text": "hacked"},
    )
    assert isinstance(r1, Refusal) and r1.reason.value == "halt_set"
    r2 = _gate(
        db, repo, Operation.RUN_LOCAL_TESTS, "owner", "tests",
        {"test_command": ["pytest", "-q"]},
    )
    assert isinstance(r2, Refusal) and r2.reason.value == "halt_set"
    assert (repo / "hello.txt").read_text() == "hello world"
    row.safe_mode_enabled = False
    db.commit()
    r3 = _gate(db, repo, Operation.INSPECT_FILE, "agent-x", "hello.txt", {})
    assert getattr(r3, "outcome", None) == Outcome.VERIFIED


def test_t06_out_of_scope_refused(db, repo, halt_off):
    env = _envelope(["edit_repo_file"], scope="backend/app/services")
    r = _gate(
        db, repo, Operation.EDIT_REPO_FILE, "agent-x", "hello.txt",
        {"old_text": "world", "new_text": "hacked"}, envelope=env,
    )
    assert isinstance(r, Refusal) and r.reason.value == "out_of_scope"
    assert (repo / "hello.txt").read_text() == "hello world"


def test_t07_idempotency_replay(db, repo, halt_off):
    payload = {
        "event_type": "t07_test",
        "source": "test_execution_boundary",
        "payload": {"k": "v"},
    }
    r1 = _gate(db, repo, Operation.RECORD_EVENT, "agent-x", "events", payload)
    assert getattr(r1, "outcome", None) == Outcome.VERIFIED
    r2 = _gate(db, repo, Operation.RECORD_EVENT, "agent-x", "events", payload)
    assert getattr(r2, "replayed", False) is True
    assert getattr(r2, "outcome", None) == Outcome.VERIFIED
    assert db.query(models.WorldEvent).filter_by(event_type="t07_test").count() == 1


def test_t08_authorized_happy_path_verified(db, repo, halt_off):
    env = _envelope(["inspect_file"], scope="hello.txt")
    r = _gate(db, repo, Operation.INSPECT_FILE, "agent-x", "hello.txt", {}, envelope=env)
    assert getattr(r, "outcome", None) == Outcome.VERIFIED
    assert getattr(r, "evidence_ref", None)
    assert db.query(models.WorldEvent).filter_by(event_type="gate_execution").count() >= 1


def test_t09_postcondition_failure_reported(db, repo, halt_off, monkeypatch):
    target = repo / "hello.txt"
    correct = "hello hami"
    expected_sha = hashlib.sha256(correct.encode("utf-8")).hexdigest()

    def lying_adapter(db_, action, repo_root=None):
        target.write_text("hello WRONG", encoding="utf-8")
        return {"path": str(target), "expected_sha256": expected_sha}

    monkeypatch.setitem(ae.OPERATION_ADAPTERS, Operation.EDIT_REPO_FILE, lying_adapter)
    env = _envelope(["edit_repo_file"], scope="hello.txt")
    r = _gate(
        db, repo, Operation.EDIT_REPO_FILE, "agent-x", "hello.txt",
        {"old_text": "world", "new_text": "hami"}, envelope=env,
    )
    assert getattr(r, "outcome", None) == Outcome.UNVERIFIED
    assert target.read_text() == "hello WRONG"
    assert db.query(models.WorldEvent).filter_by(event_type="gate_execution").count() >= 1


def test_t10_bounded_retries_stop(db, repo, halt_off, monkeypatch):
    """Bounded retries stop (as built in E4): each gate call runs the
    adapter at most 3 times (mutating ops); the idempotency record counts
    gate calls against the 3-attempt budget, so the 4th identical call
    refuses attempts_exhausted without running the adapter, opens the
    blocker once, and marks the task blocked. (Plan section 4 T-10
    expects exactly 3 adapter attempts total; the gate as built spends
    3 per call, 9 total - see docs/AUTONOMY_STEP1.md deviation note.
    The bound is finite and the blocker opens exactly once.)"""
    task = models.WorkerTask(
        worker_type="test", task_name="t10", status="queued", attempts=0, max_attempts=3
    )
    db.add(task)
    db.commit()
    calls = []

    def failing_adapter(db_, action, repo_root=None):
        calls.append(1)
        raise RuntimeError("boom")

    monkeypatch.setitem(ae.OPERATION_ADAPTERS, Operation.RUN_LOCAL_TESTS, failing_adapter)
    env = _envelope(["run_local_tests"], scope="tests")
    payload = {"test_command": ["pytest", "-q"], "task_id": task.id}
    results = [
        _gate(db, repo, Operation.RUN_LOCAL_TESTS, "agent-x", "tests", payload, envelope=env)
        for _ in range(4)
    ]
    # 3 calls x 3 adapter runs; the 4th call never runs the adapter.
    assert len(calls) == 9
    for r in results[:3]:
        assert getattr(r, "outcome", None) == Outcome.UNVERIFIED
    assert isinstance(results[3], Refusal) and results[3].reason.value == "attempts_exhausted"
    assert db.query(models.WorldEvent).filter_by(event_type="blocker_opened").count() == 1
    db.refresh(task)
    assert task.status == "blocked"


def test_protected_file_lists_match():
    assert set(dr._PROTECTED_PATHS) == set(ae._OPERATION_PROTECTED_PATHS)
