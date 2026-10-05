from fastapi.testclient import TestClient

from app import models, security
from app.database import get_db
from app.main import app


_TEST_API_KEY = "test-experiment-api-key"


def _api_headers():
    return {"X-API-Key": _TEST_API_KEY}


def _client_for(db):
    security.settings.FORGE_API_KEY = _TEST_API_KEY

    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    return client


def test_research_first_experiment_lifecycle_rejection_is_real_and_no_opportunity_needed(
    db, monkeypatch
):
    from app.services import collector_runner

    monkeypatch.setattr(collector_runner, "run_pending_tasks", lambda *args, **kwargs: [])
    client = _client_for(db)

    analyze = client.post(
        "/analyze",
        json={"idea": "Local bike shops churn because customers do not know which tune-ups they need."},
        headers=_api_headers(),
    )
    assert analyze.status_code == 200, analyze.text

    proposal = client.post(
        "/experiments/proposed",
        json={
            "source_analyze_id": 1,
            "source_signal_id": 1,
            "source_research_question_id": 1,
            "source_research_task_ids": [101, 102],
            "problem_statement": "Customers do not know which tune-up is needed.",
            "hypothesis": "A simple tune-up checklist will reduce churn.",
            "evidence_summary": "A research question and two signals indicate confusion.",
            "target": "Local bike shops",
            "offer": "A checklist-based tune-up guide",
            "action_type": "research",
            "channel": "email",
        },
        headers=_api_headers(),
    )
    assert proposal.status_code == 200, proposal.text
    created = proposal.json()
    experiment_id = created["id"]
    assert created["opportunity_id"] is None
    assert created["authorization_status"] == "require_approval"
    assert created["execution_status"] == "proposed"
    assert created["response_received"] == "none"
    assert created["revenue_amount"] == 0.0

    authorize = client.post(
        f"/experiments/{experiment_id}/authorize",
        json={
            "authorization_status": "allowed",
            "authorization_reason": "Research is complete and the check is justified.",
            "authorized_by": "owner",
        },
        headers=_api_headers(),
    )
    assert authorize.status_code == 200, authorize.text
    authorized = authorize.json()
    assert authorized["authorization_status"] == "allowed"
    assert authorized["execution_status"] == "authorized"
    assert authorized["authorized_at"] is not None

    execute = client.post(f"/experiments/{experiment_id}/execute", headers=_api_headers())
    assert execute.status_code == 200, execute.text
    executed = execute.json()
    assert executed["execution_status"] == "executed"

    outcome = client.post(
        f"/experiments/{experiment_id}/outcome",
        json={
            "response_received": "rejection",
            "response_raw": "No shop owner wanted the checklist at this stage.",
            "execution_notes": "Decision was made after research and a real rejection.",
            "revenue_amount": 0.0,
            "revenue_currency": "USD",
        },
        headers=_api_headers(),
    )
    assert outcome.status_code == 200, outcome.text
    outcome_payload = outcome.json()
    assert outcome_payload["response_received"] == "rejection"
    assert outcome_payload["execution_status"] == "completed"
    assert outcome_payload["revenue_amount"] == 0.0
    assert outcome_payload["opportunity_id"] is None

    app.dependency_overrides.clear()
    client.close()


def test_revenue_invariants_enforce_real_money_rules(db):
    client = _client_for(db)

    proposal = client.post(
        "/experiments/proposed",
        json={
            "problem_statement": "SaaS teams need a lighter onboarding flow.",
            "hypothesis": "A paid onboarding checklist improves retention.",
            "evidence_summary": "This is a structured research-first test.",
            "action_type": "research",
        },
        headers=_api_headers(),
    )
    experiment_id = proposal.json()["id"]

    client.post(
        f"/experiments/{experiment_id}/authorize",
        json={"authorization_status": "allowed", "authorized_by": "owner"},
        headers=_api_headers(),
    )
    client.post(f"/experiments/{experiment_id}/execute", headers=_api_headers())

    payment = client.post(
        f"/experiments/{experiment_id}/outcome",
        json={
            "response_received": "payment",
            "response_raw": "Customer paid the checklist.",
            "revenue_amount": 49.0,
            "revenue_currency": "USD",
        },
        headers=_api_headers(),
    )
    assert payment.status_code == 200, payment.text
    assert payment.json()["revenue_amount"] == 49.0
    assert payment.json()["execution_status"] == "completed"

    second = client.post(
        "/experiments/proposed",
        json={
            "problem_statement": "A second test for the same idea.",
            "hypothesis": "Customers show interest but do not pay.",
            "evidence_summary": "This is a second research-first test.",
            "action_type": "research",
        },
        headers=_api_headers(),
    )
    second_id = second.json()["id"]
    client.post(
        f"/experiments/{second_id}/authorize",
        json={"authorization_status": "allowed", "authorized_by": "owner"},
        headers=_api_headers(),
    )
    client.post(f"/experiments/{second_id}/execute", headers=_api_headers())

    interest = client.post(
        f"/experiments/{second_id}/outcome",
        json={
            "response_received": "interest",
            "response_raw": "People showed interest but never paid.",
            "revenue_amount": 25.0,
            "revenue_currency": "USD",
        },
        headers=_api_headers(),
    )
    assert interest.status_code == 422, interest.text

    third = client.post(
        "/experiments/proposed",
        json={
            "problem_statement": "A rejection case with money attached.",
            "hypothesis": "Customers reject the offer, but a payment event is later mistaken as success.",
            "evidence_summary": "Testing the invariant boundary.",
            "action_type": "research",
        },
        headers=_api_headers(),
    )
    third_id = third.json()["id"]
    client.post(
        f"/experiments/{third_id}/authorize",
        json={"authorization_status": "allowed", "authorized_by": "owner"},
        headers=_api_headers(),
    )
    client.post(f"/experiments/{third_id}/execute", headers=_api_headers())

    rejection = client.post(
        f"/experiments/{third_id}/outcome",
        json={
            "response_received": "rejection",
            "response_raw": "Customer rejected the offer.",
            "revenue_amount": 10.0,
            "revenue_currency": "USD",
        },
        headers=_api_headers(),
    )
    assert rejection.status_code == 422, rejection.text

    app.dependency_overrides.clear()
    client.close()


def test_experiment_write_endpoints_reject_anonymous_writes(db):
    """Cycle 64: the /experiments write surface is owner-guarded; an
    anonymous caller must fail closed with 401 even when FORGE_API_KEY
    is configured, and must never create a row."""
    client = _client_for(db)  # sets FORGE_API_KEY; no X-API-Key header sent
    body = {
        "problem_statement": "Anonymous write attempt.",
        "hypothesis": "Anonymous callers can create experiments.",
        "evidence_summary": "Negative-control test.",
        "action_type": "research",
    }
    resp = client.post("/experiments/proposed", json=body)
    assert resp.status_code == 401, resp.text
    assert db.query(models.Experiment).count() == 0
    app.dependency_overrides.clear()
    client.close()


def test_experiment_write_endpoints_unavailable_when_key_unset(db):
    """Cycle 64: require_owner_api_key fails closed with 503 (not open
    writes) when FORGE_API_KEY is not configured at all."""
    security.settings.FORGE_API_KEY = ""
    client = TestClient(app, raise_server_exceptions=False)

    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.post(
            "/experiments/proposed",
            json={
                "problem_statement": "Key-unset write attempt.",
                "hypothesis": "No key means open writes.",
                "evidence_summary": "Negative-control test.",
                "action_type": "research",
            },
        )
        assert resp.status_code == 503, resp.text
        assert db.query(models.Experiment).count() == 0
    finally:
        app.dependency_overrides.clear()
        client.close()
