import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.migrations import run_migrations
from app.services import demand_understanding, worker_manager


def _client_for(db):
    from app import security

    security.settings.FORGE_API_KEY = ""

    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=True)


def test_explicit_signal_request_enters_observation_and_demand_worker(db):
    client = _client_for(db)
    try:
        response = client.post(
            "/signals",
            json={
                "content": (
                    "Developer test request (not market demand): I need a "
                    "repair appointment. Contact test.user@example.test at +1-202-555-0147."
                ),
                "purpose": "demand_understanding",
            },
            headers={"Idempotency-Key": "developer-test-request-001"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    signal = db.get(models.Signal, response.json()["id"])
    assert signal.source == "user_request"
    assert signal.category is None
    assert "[redacted-email]" in signal.content
    assert "[redacted-phone]" in signal.content
    assert "test.user@example.test" not in signal.content
    assert "+1-202-555-0147" not in signal.content
    assert response.headers["x-demand-understanding-task-id"]

    event = db.query(models.WorldEvent).filter_by(event_type="demand_observed").one()
    assert json.loads(event.payload)["signal_id"] == signal.id
    evidence = db.query(models.Evidence).filter_by(
        idempotency_key=f"demand-observation-evidence:{signal.id}:v1"
    ).one()
    assert evidence.support_level == "possible"
    provenance = json.loads(evidence.provenance)["metadata"]["provenance"]
    assert provenance["request_boundary"] == "POST /signals"
    assert provenance["purpose"] == "demand_understanding"
    assert provenance["authorization_context"] == (
        "explicit_user_submission_for_demand_understanding"
    )
    assert provenance["idempotency_key_sha256"]
    assert datetime.fromisoformat(provenance["submitted_at"]).tzinfo is not None

    task = db.get(models.WorkerTask, int(response.headers["x-demand-understanding-task-id"]))
    result = worker_manager.HANDLERS[task.worker_type](db, task)
    assert result["state"] == "possible_demand"
    assert result["external_action"] is False
    assert result["need_id"] is None
    assert result["unresolved_questions"] == list(demand_understanding._DEFAULT_UNRESOLVED)
    assert db.query(models.SubstrateEntity).filter_by(entity_type="need").count() == 0
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.BookingRequest).count() == 0


def test_idempotent_signal_request_reuses_observation_event_evidence_and_task(db):
    client = _client_for(db)
    body = {
        "content": "Developer test request (not market demand): need a bicycle repair.",
        "purpose": "demand_understanding",
    }
    headers = {"Idempotency-Key": "developer-test-request-duplicate"}
    try:
        first = client.post("/signals", json=body, headers=headers)
        duplicate = client.post("/signals", json=body, headers=headers)
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert first.status_code == duplicate.status_code == 200
    assert first.json()["id"] == duplicate.json()["id"]
    assert (
        first.headers["x-demand-understanding-task-id"]
        == duplicate.headers["x-demand-understanding-task-id"]
    )
    assert db.query(models.Signal).filter_by(source="user_request").count() == 1
    assert db.query(models.WorldEvent).filter_by(event_type="demand_observed").count() == 1
    assert db.query(models.Evidence).filter(
        models.Evidence.idempotency_key.like("demand-observation-evidence:%")
    ).count() == 1
    assert db.query(models.WorkerTask).filter_by(worker_type="demand_understanding").count() == 1


def test_idempotency_key_reuse_with_different_content_is_rejected(db):
    client = _client_for(db)
    headers = {"Idempotency-Key": "developer-test-request-conflict"}
    try:
        first = client.post(
            "/signals",
            json={
                "content": "Developer test request (not market demand): need bicycle repair.",
                "purpose": "demand_understanding",
            },
            headers=headers,
        )
        conflict = client.post(
            "/signals",
            json={
                "content": "Developer test request (not market demand): need plumbing repair.",
                "purpose": "demand_understanding",
            },
            headers=headers,
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert db.query(models.Signal).filter_by(source="user_request").count() == 1
    assert db.query(models.WorldEvent).filter_by(event_type="demand_observed").count() == 1
    assert db.query(models.WorkerTask).filter_by(worker_type="demand_understanding").count() == 1


def test_ordinary_signal_api_behavior_is_unchanged(db):
    client = _client_for(db)
    try:
        response = client.post(
            "/signals",
            json={"content": "Existing generic signal", "source": "manual", "category": "test"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["category"] == "test"
    assert db.query(models.WorldEvent).filter_by(event_type="demand_observed").count() == 0
    assert db.query(models.WorkerTask).filter_by(worker_type="demand_understanding").count() == 0


def test_signal_request_sqlite_reopen_preserves_authorization_and_epistemic_boundary(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'request-observation.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    prior_overrides = dict(app.dependency_overrides)
    try:
        with factory() as db:
            client = _client_for(db)
            try:
                response = client.post(
                    "/signals",
                    json={
                        "content": (
                            "Developer test request (not market demand): "
                            "I need a bicycle repair appointment."
                        ),
                        "purpose": "demand_understanding",
                    },
                    headers={"Idempotency-Key": "sqlite-developer-request-001"},
                )
                assert response.status_code == 200, response.text
                signal_id = response.json()["id"]
                task_id = int(response.headers["x-demand-understanding-task-id"])
                task = db.get(models.WorkerTask, task_id)
                task.outputs = worker_manager.HANDLERS[task.worker_type](db, task)
                task.status = "completed"
                db.commit()
                event_id = db.query(models.WorldEvent).filter_by(
                    event_type="demand_observed"
                ).one().id
                evidence_id = db.query(models.Evidence).filter_by(
                    idempotency_key=f"demand-observation-evidence:{signal_id}:v1"
                ).one().id
            finally:
                client.close()
                db.close()
        with factory() as reopened:
            signal = reopened.get(models.Signal, signal_id)
            assert signal is not None
            assert signal.source == "user_request"
            assert signal.collection_status == "user_submitted"
            assert signal.retrieved_at is not None
            event = reopened.get(models.WorldEvent, event_id)
            assert json.loads(event.payload)["signal_id"] == signal_id
            evidence = reopened.get(models.Evidence, evidence_id)
            assert evidence.support_level == "possible"
            stored_provenance = json.loads(evidence.provenance)["metadata"]["provenance"]
            assert stored_provenance["purpose"] == "demand_understanding"
            assert stored_provenance["authorization_context"] == (
                "explicit_user_submission_for_demand_understanding"
            )
            task = reopened.get(models.WorkerTask, task_id)
            assert task.status == "completed"
            assert task.outputs["state"] == "possible_demand"
            assert task.outputs["unresolved_questions"] == list(
                demand_understanding._DEFAULT_UNRESOLVED
            )
            assert task.outputs["need_id"] is None
            assert reopened.query(models.SubstrateEntity).filter_by(entity_type="need").count() == 0
            assert reopened.query(models.Opportunity).count() == 0
            assert reopened.query(models.BookingRequest).count() == 0
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior_overrides)
        engine.dispose()
