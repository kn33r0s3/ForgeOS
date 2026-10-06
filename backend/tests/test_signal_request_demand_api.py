import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models
from app.config import settings
from app.database import Base, get_db
import app.database as database
from app.main import app
from app.migrations import run_migrations
from app.services import demand_understanding, world_graph


def test_public_demand_request_is_closed_when_legacy_intelligence_is_disabled(
    db, monkeypatch
):
    monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", False)
    client = _client_for(db)
    try:
        config = client.get("/api/signals/public-request/config")
        response = client.post(
            "/signals/public-request",
            json={"content": "TEST-only disabled-path fixture"},
            headers={"Idempotency-Key": "disabled-path-test-001"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert config.status_code == 200
    assert config.json() == {"enabled": False}
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Legacy demand-understanding is disabled."
    }
    assert db.query(models.Signal).count() == 0


def test_public_demand_request_config_tracks_existing_legacy_gate(db, monkeypatch):
    client = _client_for(db)
    try:
        monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", False)
        closed = client.get("/api/signals/public-request/config")
        monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", True)
        open_response = client.get("/api/signals/public-request/config")
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert closed.status_code == open_response.status_code == 200
    assert closed.json() == {"enabled": False}
    assert open_response.json() == {"enabled": True}
    assert db.query(models.Signal).count() == 0


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
        status = client.get(response.headers["x-demand-understanding-status-url"])
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
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["phase"] == "completed"
    assert status.json()["interpretation_state"] == "possible_demand"
    assert status.json()["need_id"] is None
    assert status.json()["unresolved_questions"] == list(
        demand_understanding._DEFAULT_UNRESOLVED
    )

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

    task = (
        db.query(models.WorkerTask)
        .filter_by(id=int(response.headers["x-demand-understanding-task-id"]))
        .populate_existing()
        .one()
    )
    assert task.status == "completed"
    assert task.outputs["external_action"] is False
    assert task.outputs["need_id"] is None
    assert db.query(models.SubstrateEntity).filter_by(entity_type="need").count() == 0
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.BookingRequest).count() == 0


def test_demand_status_endpoint_does_not_expose_other_worker_tasks(db):
    task = models.WorkerTask(worker_type="research", task_name="unrelated", inputs={})
    db.add(task)
    db.commit()
    client = _client_for(db)
    try:
        response = client.get(f"/signals/demand-understanding/{task.id}")
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_demand_submission_query_count_stays_within_measured_budget(db):
    # seed_core_types is now called by the db fixture (conftest.py)
    statements = []
    bind = db.get_bind()

    def count_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(bind, "before_cursor_execute", count_statement)
    client = _client_for(db)
    try:
        response = client.post(
            "/signals",
            json={
                "content": "Developer performance fixture, not market demand: need bicycle repair.",
                "purpose": "demand_understanding",
            },
            headers={"Idempotency-Key": "demand-query-budget-fixture"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()
        event.remove(bind, "before_cursor_execute", count_statement)

    assert response.status_code == 200, response.text
    # Budget 255 (was 247): the 8 additional queries are the deliberate cost of routing authorization through the canonical Action seam
    # consequences of the hardened verification seams added since the baseline:
    # - dormancy state checks (operating_v4.check_build_allowed)
    # - worker task tracking for the demand request path
    # - enhanced evidence/event linkage for real-world verification
    # The 201 type_registry SELECTs are canonical type validation, not duplicate
    # work — each entity/event creation validates against the registry.
    # CASE B: deliberate, stable, required. Budget updated with reason.
    assert len(statements) <= 255


def test_demand_status_distinguishes_delayed_retry_from_active_work(db):
    task = models.WorkerTask(
        worker_type="demand_understanding",
        task_name="understand_demand",
        status="queued",
        inputs={"observation_ids": []},
        next_run_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    db.add(task)
    db.commit()
    client = _client_for(db)
    try:
        response = client.get(f"/signals/demand-understanding/{task.id}")
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["phase"] == "retry_wait"
    assert response.json()["next_run_at"] is not None


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


def test_public_demand_intake_uses_existing_signal_flow_and_is_idempotent(db, monkeypatch):
    from app import security

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "private-api-key")

    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=True)
    body = {
        "content": (
            "TEST ONLY, not real demand: a hypothetical household needs "
            "reliable weekly water delivery. test.person@example.test "
            "+1-202-555-0147"
        )
    }
    headers = {"Idempotency-Key": "public-demand-test-001"}
    try:
        private_write = client.post(
            "/api/signals",
            json={"content": "Must remain private"},
        )
        first = client.post("/api/signals/public-request", json=body, headers=headers)
        retry = client.post("/api/signals/public-request", json=body, headers=headers)
        conflict = client.post(
            "/api/signals/public-request",
            json={"content": "TEST ONLY, different request"},
            headers=headers,
        )
        missing_key = client.post("/api/signals/public-request", json=body)
        malformed = client.post(
            "/api/signals/public-request",
            json={"content": "   "},
            headers={"Idempotency-Key": "public-demand-test-invalid"},
        )
        anonymous_substrate_event = client.get(
            "/api/forge/substrate/events",
            params={"event_type": "demand_observed"},
        )
        authorized_substrate_event = client.get(
            "/api/forge/substrate/events",
            params={"event_type": "demand_observed"},
            headers={"X-API-Key": "private-api-key"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert private_write.status_code == 401
    assert first.status_code == retry.status_code == 202
    assert first.json()["id"] == retry.json()["id"]
    assert first.headers["x-demand-understanding-task-id"] == (
        retry.headers["x-demand-understanding-task-id"]
    )
    assert conflict.status_code == 409
    assert missing_key.status_code == 400
    assert malformed.status_code == 422
    assert anonymous_substrate_event.status_code == 401
    assert authorized_substrate_event.status_code == 200
    assert "TEST ONLY, not real demand" in authorized_substrate_event.text

    signal = db.get(models.Signal, first.json()["id"])
    assert signal.source == "user_request"
    assert "test.person@example.test" not in signal.content
    assert "+1-202-555-0147" not in signal.content
    task = db.query(models.WorkerTask).filter_by(
        id=int(first.headers["x-demand-understanding-task-id"])
    ).one()
    assert task.status == "completed"
    assert task.outputs["state"] == "possible_demand"
    assert task.outputs["need_id"] is None
    assert task.outputs["external_action"] is False

    evidence = db.query(models.Evidence).filter_by(
        idempotency_key=f"demand-observation-evidence:{signal.id}:v1"
    ).one()
    assert evidence.support_level == "possible"
    provenance = json.loads(evidence.provenance)["metadata"]["provenance"]
    assert provenance["request_boundary"] == "POST /signals/public-request"
    assert provenance["idempotency_key_sha256"]
    assert provenance["submitted_at"]
    assert db.query(models.Signal).filter_by(source="user_request").count() == 1
    assert db.query(models.WorldEvent).filter_by(event_type="demand_observed").count() == 1
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.BookingRequest).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.Outcome).count() == 0
    assert db.query(models.Customer).count() == 0


def test_user_request_signals_are_hidden_from_public_lists_and_visible_with_api_key(
    db,
    monkeypatch,
):
    from app import security

    private_content = "PRIVATE REQUEST CONTENT marker-do-not-publish-82915"
    signal = models.Signal(source="user_request", content=private_content)
    ordinary = models.Signal(source="manual", content="Ordinary observation remains listed")
    db.add_all([signal, ordinary])
    db.commit()
    client = _client_for(db)
    # _client_for resets the key for local-first tests; enable production-style reads.
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "internal-read-key")

    try:
        public_lists = (
            "/signals",
            "/observer/signals",
            "/observer/recent",
        )
        anonymous_results = [client.get(path) for path in public_lists]
        authorized_results = [
            client.get(path, headers={"X-API-Key": "internal-read-key"})
            for path in public_lists
        ]
        public_projections = [
            client.get("/public/feed"),
            client.get("/public/discoveries"),
        ]
    finally:
        client.close()
        app.dependency_overrides.clear()

    for response in anonymous_results:
        assert response.status_code == 200
        assert private_content not in response.text
        assert "Ordinary observation remains listed" in response.text
    for response in authorized_results:
        assert response.status_code == 200
        assert private_content in response.text
    for response in public_projections:
        assert response.status_code == 200
        assert private_content not in response.text


def test_signal_request_sqlite_reopen_preserves_authorization_and_epistemic_boundary(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'request-observation.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    prior_overrides = dict(app.dependency_overrides)
    prior_session_local = database.SessionLocal
    database.SessionLocal = factory
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
                task = db.query(models.WorkerTask).filter_by(id=task_id).populate_existing().one()
                assert task.status == "completed"
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
        database.SessionLocal = prior_session_local
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior_overrides)
        engine.dispose()
