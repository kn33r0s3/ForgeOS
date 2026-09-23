"""Regression proof that a failed Forge stage cannot poison autonomy."""
from types import SimpleNamespace

from scripts import run_daily_cycle


class FakeSession:
    def __init__(self):
        self.poisoned = False
        self.rollbacks = 0
        self.closed = False

    def rollback(self):
        self.poisoned = False
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_forge_failure_is_rolled_back_before_autonomy(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(run_daily_cycle, "SessionLocal", lambda: session)

    def fail_forge(db):
        db.poisoned = True
        raise RuntimeError("interrupted between stages")

    def autonomy(db):
        assert db.poisoned is False
        return SimpleNamespace(proposed=1, allowed=0, blocked=0, require_approval=1)

    monkeypatch.setattr(run_daily_cycle.forge_loop, "run_cycle", fail_forge)
    monkeypatch.setattr(run_daily_cycle.execution_engine, "run_autonomous_action_cycle", autonomy)

    record = run_daily_cycle.run_once()
    assert record["forge_cycle_recovered"] is True
    assert record["forge_cycle_error"].startswith("RuntimeError:")
    assert record["autonomy_cycle"]["proposed"] == 1
    assert session.rollbacks == 1
    assert session.closed is True


def test_rollback_failure_is_best_effort_and_does_not_escape():
    class BrokenSession:
        def rollback(self):
            raise RuntimeError("rollback itself failed")
        def expunge_all(self):
            raise RuntimeError("expunge failed")

    run_daily_cycle._rollback_if_needed(BrokenSession(), "test")
