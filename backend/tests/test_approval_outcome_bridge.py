"""Approval package cites stored evidence. A result needs a human approval."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app
from app.services import source_manager
from app.services.approval_outcome_bridge import (
    build_action_package,
    record_human_result,
    record_verified_revenue_evidence,
)
from app.services.execution_engine import approve_action
from app.services.triage_signal_bridge import record_paid_triage

STRONG = (
    "Independent repair shops lose hours manually explaining appointment status "
    "to customers by phone and lost $500 in revenue. We would pay for a tool."
)


def _seed(db):
    request = {"text": STRONG, "source_kind": "user_report", "source_reliability": 80}
    triage = {
        "fulfillment_id": "ful_pkg",
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "evidence": {
            "problem": STRONG,
            "evidence_text": STRONG,
            "buying_intent": True,
            "monetary_impact": "$500",
        },
        "eligibility": {"economically_meaningful": True},
    }
    return record_paid_triage(db, request, triage)


def test_package_cites_signal_and_writes_nothing(db):
    seeded = _seed(db)
    package = build_action_package(db, seeded["action_id"])

    assert package["approved"] is False
    assert package["execution_allowed"] is False
    assert package["revenue"] is None
    assert package["result"] is None
    assert package["evidence"][0]["text"] == STRONG
    assert db.query(models.Outcome).count() == 0


def test_result_before_approval_writes_nothing(db):
    seeded = _seed(db)
    with pytest.raises(ValueError, match="approval"):
        record_human_result(db, seeded["action_id"], "Owner spoke with one shop. No payment.")

    action = db.get(models.Experiment, seeded["action_id"])
    assert action.result is None
    assert action.revenue is None
    assert action.started_at is None
    assert db.query(models.Outcome).count() == 0


def test_approved_qualitative_result_leaves_revenue_empty(db):
    seeded = _seed(db)
    approve_action(db, seeded["action_id"])
    assert db.query(models.Outcome).count() == 0

    package = record_human_result(db, seeded["action_id"], "Spoke with one shop. They did not pay.")

    assert package["result"] == "Spoke with one shop. They did not pay."
    assert package["revenue"] is None
    assert package["execution_allowed"] is False
    outcomes = db.query(models.Outcome).all()
    assert len(outcomes) == 1
    assert outcomes[0].outcome_type == "QUALITATIVE"
    assert outcomes[0].actual_value is None
    action = db.get(models.Experiment, seeded["action_id"])
    assert action.status == "completed"
    assert action.revenue is None

    assert db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE").count() == 0


def test_verified_payment_evidence_creates_real_revenue_only_after_outcome(db):
    seeded = _seed(db)
    approve_action(db, seeded["action_id"])
    record_human_result(db, seeded["action_id"], "Spoke with one shop. They paid after follow-up.")

    assert db.query(models.Outcome).filter_by(outcome_type="QUALITATIVE").count() == 1
    assert db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE").count() == 0

    record_verified_revenue_evidence(
        db,
        seeded["action_id"],
        amount=25.0,
        currency="USD",
        source="stripe",
        reference="pi_123",
    )

    action = db.get(models.Experiment, seeded["action_id"])
    assert action.revenue == 25.0
    revenue_outcomes = db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE").all()
    assert len(revenue_outcomes) == 1
    assert revenue_outcomes[0].actual_value == 25.0
    assert revenue_outcomes[0].verification_state == "VERIFIED"
    assert revenue_outcomes[0].experiment_id == seeded["action_id"]
    assert revenue_outcomes[0].action_id is None


def test_verified_revenue_before_human_result_writes_nothing(db):
    seeded = _seed(db)
    approve_action(db, seeded["action_id"])
    with pytest.raises(ValueError, match="outcome"):
        record_verified_revenue_evidence(
            db,
            seeded["action_id"],
            amount=25.0,
            currency="USD",
            source="stripe",
            reference="pi_123",
        )
    action = db.get(models.Experiment, seeded["action_id"])
    assert action.revenue is None
    assert db.query(models.Outcome).count() == 0


def test_human_result_refuses_a_revenue_amount(db):
    seeded = _seed(db)
    approve_action(db, seeded["action_id"])
    with pytest.raises(ValueError, match="verified payment"):
        record_human_result(db, seeded["action_id"], "Spoke with one shop.", revenue=25.0)
    action = db.get(models.Experiment, seeded["action_id"])
    assert action.revenue is None
    assert action.result is None
    assert db.query(models.Outcome).count() == 0


@pytest.fixture
def httpdb(monkeypatch):
    from app import security

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "test-owner-key")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    source_manager.seed_default_sources(session)

    def dependency():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = dependency
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"X-API-Key": "test-owner-key"})
    yield client, session
    client.close()
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_package_http_keeps_revenue_off_the_human_result(httpdb):
    client, session = httpdb
    seeded = _seed(session)
    action_id = seeded["action_id"]

    unread = client.get(f"/forge/execution/actions/{action_id}/package")
    assert unread.status_code == 200, unread.text
    assert unread.json()["revenue"] is None
    assert unread.json()["evidence"][0]["text"] == STRONG
    assert session.query(models.Outcome).count() == 0

    early = client.post(
        f"/forge/execution/actions/{action_id}/human-result",
        json={"result": "Spoke with one shop. They did not pay."},
    )
    assert early.status_code == 409

    paid_early = client.post(
        f"/forge/execution/actions/{action_id}/verified-revenue",
        json={"amount": 25, "currency": "USD", "source": "stripe", "reference": "pi_123"},
    )
    assert paid_early.status_code == 409
    assert session.get(models.Experiment, action_id).revenue is None

    assert client.post(f"/forge/execution/actions/{action_id}/approve").status_code == 200
    smuggled = client.post(
        f"/forge/execution/actions/{action_id}/result",
        json={"result": "They paid on the call.", "revenue": 25},
    )
    assert smuggled.status_code == 409
    assert session.get(models.Experiment, action_id).revenue is None
    assert session.get(models.Experiment, action_id).result is None

    recorded = client.post(
        f"/forge/execution/actions/{action_id}/human-result",
        json={"result": "Spoke with one shop. They did not pay."},
    )
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["revenue"] is None
    assert recorded.json()["result"] == "Spoke with one shop. They did not pay."

    paid = client.post(
        f"/forge/execution/actions/{action_id}/verified-revenue",
        json={"amount": 25, "currency": "USD", "source": "stripe", "reference": "pi_123"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["revenue"] == 25.0
    revenue = session.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE").one()
    assert revenue.experiment_id == action_id
    assert revenue.action_id is None
    assert revenue.verification_state == "VERIFIED"
