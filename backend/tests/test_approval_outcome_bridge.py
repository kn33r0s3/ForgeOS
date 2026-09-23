"""Approval package cites stored evidence. A result needs a human approval."""

import pytest

from app import models
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
