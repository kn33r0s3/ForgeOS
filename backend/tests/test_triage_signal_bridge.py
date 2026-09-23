"""Paid triage becomes a signal. Discovery and approval stay on existing gates."""

from app import models
from app.services.triage_signal_bridge import record_paid_triage

STRONG = (
    "Independent repair shops lose hours manually explaining appointment status "
    "to customers by phone and lost $500 in revenue. We would pay for a tool."
)
WEAK = "The weather was nice and people talked about lunch."


def _request(text: str) -> dict:
    return {"text": text, "source_kind": "user_report", "source_reliability": 80}


def _triage(text: str, *, meaningful: bool, fulfillment: str) -> dict:
    return {
        "fulfillment_id": fulfillment,
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "evidence": {
            "problem": text if meaningful else None,
            "evidence_text": text,
            "buying_intent": "would pay" in text,
            "monetary_impact": "$500" if meaningful else None,
        },
        "eligibility": {"economically_meaningful": meaningful},
    }


def test_weak_paid_triage_stays_a_signal(db):
    result = record_paid_triage(db, _request(WEAK), _triage(WEAK, meaningful=False, fulfillment="ful_weak"))

    assert result["persisted"] is True
    assert result["opportunity_id"] is None
    assert result["action_id"] is None
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Experiment).count() == 0
    assert db.query(models.Outcome).count() == 0


def test_strong_paid_triage_requires_approval_and_writes_no_revenue(db):
    result = record_paid_triage(
        db, _request(STRONG), _triage(STRONG, meaningful=True, fulfillment="ful_strong")
    )

    assert result["opportunity_id"] is not None
    opportunity = db.query(models.Opportunity).filter_by(id=result["opportunity_id"]).one()
    assert opportunity.revenue_confidence == 0.0
    assert opportunity.market_confidence == 0.0

    action = db.query(models.Experiment).filter_by(id=result["action_id"]).one()
    assert action.policy_decision == "require_approval"
    assert action.requires_owner_approval is True
    assert action.status == "planned"
    assert action.started_at is None
    assert action.execution_allowed is False
    assert (action.revenue or 0) == 0
    assert db.query(models.Outcome).count() == 0

    signal = db.query(models.Signal).filter_by(id=result["signal_id"]).one()
    assert STRONG in signal.content
    assert "paid_evidence_triage" in (signal.provenance or "")


def test_repeat_fulfillment_does_not_send_or_duplicate(db):
    body = _triage(STRONG, meaningful=True, fulfillment="ful_same")
    first = record_paid_triage(db, _request(STRONG), body)
    second = record_paid_triage(db, _request(STRONG), body)

    assert first["signal_id"] == second["signal_id"]
    assert db.query(models.Signal).filter_by(source="evidence_triage").count() == 1
    actions = db.query(models.Experiment).all()
    assert len(actions) == 1
    assert actions[0].started_at is None
    assert db.query(models.Outcome).count() == 0
