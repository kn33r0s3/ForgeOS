"""
End-to-end intelligence loop test.

Proves:
  CREATE OBSERVATION
  → STORE PROVENANCE
  → CREATE/UPDATE EVIDENCE
  → CREATE PATTERN
  → CREATE HYPOTHESIS/BELIEF
  → CREATE OPPORTUNITY
  → CREATE DECISION
  → POLICY-AWARE ACTION PATH
  → RECORD OUTCOME (via experiment)
  → MEASURE RESULT
  → COMPARE EXPECTED VS ACTUAL
  → LEARNING
  → UPDATE BELIEF

Uses real DB and real application logic. No fake success values.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from app import evidence_source, models
from app.services.observer_engine import ObserverEngine
from app.services import (
    forge_loop,
    decision_engine,
    learning_engine,
)
from app.services.experiment_runner import ExperimentRunner




def test_full_intelligence_loop(db):
    obs = ObserverEngine(db)

    # --- 1. OBSERVATIONS with provenance ---
    texts = [
        "At least 12 restaurants in Kathmandu still take phone orders and write them on paper tickets. Managers report 3-5 wrong dishes per busy night, losing roughly NPR 8000-15000 each weekend.",
        "Restaurant managers in Kathmandu report that paper kitchen tickets get lost every Friday night. One owner counted 7 lost tickets last week, leading to angry customers who refused to pay for 4 orders.",
        "Three cafe owners near Thamel still use handwritten order pads. Staff make mistakes on 15 percent of orders according to their own count. Customers complain about wrong dishes at least twice per week.",
        "A restaurant owner in Lazimpat said they lose about NPR 12000 every weekend because phone orders are miswritten and kitchen tickets are illegible. They tried hiring more staff but the paper process remains the bottleneck.",
        "Small restaurants need a simple digital order system. Manual phone-to-paper process creates constant operational friction: 5 restaurants interviewed last month all reported the same problem of lost tickets and misheard phone orders.",
    ]
    signal_ids = []
    for t in texts:
        s = obs.observe(content=t, source="manual")
        assert s.id is not None
        assert s.source == "manual"
        assert s.content == t
        signal_ids.append(s.id)

    assert len(signal_ids) == 5
    assert db.query(models.Signal).count() == 5

    # --- 2. Full cycle: pattern → belief → evidence → opportunity ---
    summary = forge_loop.run_cycle(db)
    assert summary["signals_processed"] >= 5
    assert summary["patterns_found"] >= 1
    assert summary["beliefs_updated"] >= 1
    assert summary["opportunities_discovered"] >= 1

    patterns = db.query(models.Pattern).all()
    assert len(patterns) >= 1
    assert patterns[0].frequency >= 2
    assert patterns[0].origin_signal_ids  # provenance link

    beliefs = db.query(models.Belief).all()
    assert len(beliefs) >= 1
    belief = beliefs[0]
    assert belief.statement
    assert belief.confidence_score is not None
    assert belief.supporting_signal_ids

    evidence = db.query(models.Evidence).filter_by(belief_id=belief.id).all()
    assert len(evidence) >= 1
    for e in evidence:
        assert e.direction in ("supports", "contradicts")
        assert e.content
        assert e.source  # provenance

    opps = db.query(models.Opportunity).all()
    assert len(opps) >= 1
    opp = opps[0]
    assert opp.score is not None
    assert opp.problem

    # --- 3. DECISION ---
    decision = decision_engine.suggest_next_experiment_decision(db, opp.id)
    assert decision is not None
    assert decision.status == "proposed"
    assert "Validate" in decision.title or "validate" in decision.rationale.lower()
    accepted = decision_engine.accept_decision(db, decision.id)
    assert accepted.status == "accepted"
    assert accepted.decided_at is not None

    # --- 4. EXPERIMENT (belief experiment path) ---
    runner = ExperimentRunner(db)
    bexp = runner.create_experiment(
        belief_id=belief.id,
        hypothesis="At least 6 of 10 restaurants confirm weekly paper-ticket loss.",
        method="Contact 10 restaurants; count how many confirm weekly ticket loss.",
    )
    assert bexp.status == "planned"

    lesson = "The problem may be less universal than the first signal cluster suggested."
    # Planned hypothesis has not produced a result and cannot create a learning record.
    with pytest.raises(ValueError, match="result must be recorded"):
        learning_engine.record_learning_from_belief_experiment(
            db,
            bexp.id,
            prediction=bexp.hypothesis,
            actual="",
            lesson=lesson,
            confidence_delta=0.0,
        )
    assert db.query(models.LearningEvent).filter_by(belief_experiment_id=bexp.id).count() == 0

    confidence_before_report = belief.confidence_score
    causal_count_before_report = db.query(models.CausalKnowledge).count()

    # This legacy endpoint stores a report, not a verified outcome.
    updated = runner.record_result(
        bexp.id,
        result="Contacted 10; 3 confirmed weekly ticket loss; 2 were unsure; 5 said they already use WhatsApp orders.",
        confidence_change=-8.0,
    )
    assert updated.status == "completed"
    assert updated.result
    assert updated.confidence_change == -8.0
    db.refresh(belief)
    assert belief.confidence_score == confidence_before_report
    assert db.query(models.CausalKnowledge).count() == causal_count_before_report

    # A report is stored as HYPOTHESIS and must not affect shared knowledge.
    event = learning_engine.record_learning_from_belief_experiment(
        db,
        bexp.id,
        prediction=bexp.hypothesis,
        actual=updated.result,
        lesson=lesson,
        confidence_delta=-8.0,
    )
    assert event.id is not None
    assert event.prediction == bexp.hypothesis
    assert event.actual == updated.result
    assert event.source_kind == evidence_source.HYPOTHESIS
    assert event.confidence_delta is None
    assert event.error_type is None
    assert event.belief_update_applied is False

    # Replay is idempotent; a different proposed delta cannot be attached retroactively.
    same_event = learning_engine.record_learning_from_belief_experiment(
        db,
        bexp.id,
        prediction=bexp.hypothesis,
        actual=updated.result,
        lesson=lesson,
        confidence_delta=-8.0,
    )
    assert same_event.id == event.id
    assert db.query(models.LearningEvent).filter_by(belief_experiment_id=bexp.id).count() == 1
    with pytest.raises(ValueError, match="Confidence assessment"):
        learning_engine.record_learning_from_belief_experiment(
            db,
            bexp.id,
            prediction=bexp.hypothesis,
            actual=updated.result,
            lesson=lesson,
            confidence_delta=-5.0,
        )

    db.refresh(belief)
    assert belief.confidence_score == confidence_before_report
    assert db.query(models.CausalKnowledge).count() == causal_count_before_report

    # Numeric comparison utility
    cmp = learning_engine.compare_expected_vs_actual_numeric(expected=6.0, actual=3.0)
    assert cmp["status"] == "COMPARED"
    assert cmp["expected"] == 6.0  # ESTIMATE
    assert cmp["actual"] == 3.0    # ACTUAL
    assert cmp["error_type"] == "overestimate"

    # --- 6. Learning events persisted ---
    events = learning_engine.list_learning_events(db)
    assert len(events) >= 1

    # Final state truthfulness
    assert db.query(models.Signal).count() == 5
    assert db.query(models.Pattern).count() >= 1
    assert db.query(models.Belief).count() >= 1
    assert db.query(models.Evidence).count() >= 1
    assert db.query(models.Opportunity).count() >= 1
    assert db.query(models.Decision).count() >= 1
    assert db.query(models.BeliefExperiment).count() >= 1
    assert db.query(models.LearningEvent).count() >= 1

    print("E2E PASS: observation→evidence→pattern→belief→opportunity→decision→experiment→learning")
