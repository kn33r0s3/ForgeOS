"""Step 2: scheduled observation via /scheduled/intelligence collection stage.

Verifies the smallest safe reconnection: the existing
collector_runner.run_pending_tasks() is invoked by the scheduled
intelligence endpoint, with failure isolation preserving the other stages.
"""
from fastapi.testclient import TestClient

from app.api import scheduled
from app.main import app


def _client_with_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    return TestClient(app, raise_server_exceptions=False)


def _auth_headers():
    return {"Authorization": "Bearer test-cron-secret"}


def test_intelligence_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    client = TestClient(app)
    res = client.get("/scheduled/intelligence", headers={"Authorization": "Bearer x"})
    assert res.status_code == 503


def test_intelligence_requires_bearer_secret(monkeypatch):
    client = _client_with_secret(monkeypatch)
    res = client.get("/scheduled/intelligence")
    assert res.status_code == 401


def test_intelligence_invokes_collection_stage(monkeypatch):
    """The collection stage calls run_pending_tasks; results are recorded."""
    client = _client_with_secret(monkeypatch)
    called = {}

    def fake_run_pending_tasks(db, limit=5):
        called["limit"] = limit
        return [
            {"task_id": 1, "source": "web", "status": "completed", "signals_created": 3},
        ]

    # Stub out the other stages to isolate the collection stage.
    import app.services.forge_loop as forge_loop
    import app.services.research_task_engine as rte
    import app.services.execution_engine as ee
    from app.services import collector_runner

    monkeypatch.setattr(forge_loop, "run_cycle", lambda db: {"cycle_id": 1, "signals_processed": 0, "stage_errors": {}})
    monkeypatch.setattr(collector_runner, "run_pending_tasks", fake_run_pending_tasks)
    monkeypatch.setattr(rte, "resume_running_tasks", lambda db, limit=10: [])
    monkeypatch.setattr(ee, "run_autonomous_action_cycle", lambda db: {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0})

    res = client.get("/scheduled/intelligence", headers=_auth_headers())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    # Collection stage was invoked with the expected limit.
    assert called["limit"] == 5
    collection = body["intelligence"]["collection_cycle"]
    assert collection["status"] == "ok"
    assert collection["tasks_executed"] == 1
    assert collection["outcomes"][0]["task_id"] == 1
    assert collection["outcomes"][0]["signals_created"] == 3


def test_intelligence_collection_failure_does_not_kill_cycle(monkeypatch):
    """A collection failure is isolated; other stages still run."""
    client = _client_with_secret(monkeypatch)

    def boom(db, limit=5):
        raise RuntimeError("collector exploded")

    import app.services.forge_loop as forge_loop
    import app.services.research_task_engine as rte
    import app.services.execution_engine as ee
    from app.services import collector_runner

    monkeypatch.setattr(forge_loop, "run_cycle", lambda db: {"cycle_id": 2, "signals_processed": 0, "stage_errors": {}})
    monkeypatch.setattr(collector_runner, "run_pending_tasks", boom)
    monkeypatch.setattr(rte, "resume_running_tasks", lambda db, limit=10: [])
    monkeypatch.setattr(ee, "run_autonomous_action_cycle", lambda db: {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0})

    res = client.get("/scheduled/intelligence", headers=_auth_headers())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    # Collection stage recorded the error...
    assert body["intelligence"]["collection_cycle"]["status"] == "error"
    # ...but the other stages still ran.
    assert body["intelligence"]["forge_cycle"]["status"] == "ok"
    assert body["intelligence"]["resumed_tasks"]["status"] == "ok"
    assert body["intelligence"]["autonomy_cycle"]["status"] == "ok"
