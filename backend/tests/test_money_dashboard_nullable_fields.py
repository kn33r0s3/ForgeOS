"""Regression: /forge/money/dashboard must not 422 when an opportunity's
nullable text columns (solution, business_model, target_customer) are NULL."""
from fastapi.testclient import TestClient

from app import models, security
from app.database import get_db
from app.main import app


def _client_for(db, monkeypatch):
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "test-owner-key")

    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"X-API-Key": "test-owner-key"})
    return client


def test_money_dashboard_tolerates_null_solution_and_business_model(db, monkeypatch):
    db.add(
        models.Opportunity(
            problem="Repair shops lose bookings because availability is not visible",
            target_customer=None,
            solution=None,
            business_model=None,
        )
    )
    db.commit()

    client = _client_for(db, monkeypatch)
    try:
        response = client.get("/forge/money/dashboard")
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    ranked = response.json()["best_opportunities"]
    assert len(ranked) == 1
    opportunity = ranked[0]["opportunity"]
    assert opportunity["solution"] == ""
    assert opportunity["business_model"] == ""
    assert opportunity["target_customer"] == ""


def test_money_dashboard_keeps_recorded_text_unchanged(db, monkeypatch):
    db.add(
        models.Opportunity(
            problem="Trekking agencies retype permit details for every group",
            target_customer="Licensed trekking agencies",
            solution="Reusable permit template",
            business_model="Per-booking fee",
        )
    )
    db.commit()

    client = _client_for(db, monkeypatch)
    try:
        response = client.get("/forge/money/dashboard")
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    opportunity = response.json()["best_opportunities"][0]["opportunity"]
    assert opportunity["solution"] == "Reusable permit template"
    assert opportunity["business_model"] == "Per-booking fee"
    assert opportunity["target_customer"] == "Licensed trekking agencies"
