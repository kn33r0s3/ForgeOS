"""
Focused tests for the v1.9 Scenario Engine (Phase 1) — a secondary,
parallel domain. No existing test suite/convention existed in this
repository prior to this file (confirmed by inspection before writing
it); this uses a fresh in-memory SQLite database per test via pytest
fixtures, the lowest-friction approach given the project's existing
SQLAlchemy + FastAPI stack.

Run with: pip install pytest --break-system-packages && pytest tests/test_scenario_engine.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models
from app.services import scenario_engine, forge_loop


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_1_scenario_records_can_be_created(db):
    scenario_engine.seed_default_scenarios(db)
    scenarios = db.query(models.Scenario).all()
    assert len(scenarios) == 6
    codes = {s.code for s in scenarios}
    assert codes == {"A", "B", "C", "D", "E", "F"}
    # Evidence-first: every scenario starts with NO fabricated probability
    for s in scenarios:
        assert s.probability is None
        assert s.probability_basis == "insufficient_evidence"


def test_2_forecaster_can_be_created(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_musk_forecaster_and_predictions(db)
    forecaster = db.query(models.Forecaster).filter(models.Forecaster.name == "Elon Musk").first()
    assert forecaster is not None
    # track_record_accuracy must NOT be fabricated at seed time
    assert forecaster.track_record_accuracy is None


def test_3_scenario_prediction_can_be_created(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_musk_forecaster_and_predictions(db)
    predictions = db.query(models.ScenarioPrediction).filter(models.ScenarioPrediction.forecaster_id.isnot(None)).all()
    assert len(predictions) == 2
    for p in predictions:
        assert p.status == "open"  # never pre-resolved
        assert p.probability is None  # Forge has not independently assessed likelihood
        assert p.source_url is not None and p.source_url.startswith("https://")
        assert p.original_quote is not None

    # The degree/skills prediction must NOT claim to be a verbatim
    # "university degree is irrelevant" quote — the interpretation_note
    # must explicitly flag this.
    skills_prediction = next(p for p in predictions if "college" in p.claim.lower())
    assert skills_prediction.interpretation_note is not None
    assert "NOT" in skills_prediction.interpretation_note
    assert "not fabricated" in skills_prediction.interpretation_note.lower()


def test_4_evidence_can_attach_to_scenario_prediction(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_phase1_indicators(db)
    indicator = db.query(models.ScenarioPrediction).filter(models.ScenarioPrediction.domain == "robotics").first()
    assert indicator is not None

    signal = models.Signal(source="manual", content="Tesla Optimus humanoid robot production accelerates")
    db.add(signal)
    db.commit()
    db.refresh(signal)

    evidence = models.Evidence(
        belief_id=None,
        scenario_prediction_id=indicator.id,
        signal_id=signal.id,
        source=signal.source,
        content=signal.content,
        direction="supports",
    )
    db.add(evidence)
    db.commit()

    linked = db.query(models.Evidence).filter(models.Evidence.scenario_prediction_id == indicator.id).all()
    assert len(linked) == 1
    assert linked[0].belief_id is None  # confirms the dual-use, never-both invariant


def test_scenario_cycle_evidence_uses_stable_identity(db):
    scenario_engine.seed_phase1_indicators(db)
    indicator = db.query(models.ScenarioPrediction).filter_by(domain="robotics").one()
    signal = models.Signal(source="manual", content="Humanoid robotics deployments are expanding.")
    db.add(signal)
    db.commit()
    db.refresh(signal)

    first = scenario_engine.run_scenario_engine_cycle(db)
    repeated = scenario_engine.run_scenario_engine_cycle(db)

    assert first["signals_classified"] == 1
    assert repeated["signals_classified"] == 0
    evidence = db.query(models.Evidence).filter_by(scenario_prediction_id=indicator.id).one()
    assert evidence.idempotency_key == f"scenario-prediction-signal:{indicator.id}:{signal.id}"


def test_5_confidence_event_can_attach_to_scenario_prediction(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_musk_forecaster_and_predictions(db)
    prediction = db.query(models.ScenarioPrediction).filter(models.ScenarioPrediction.forecaster_id.isnot(None)).first()

    event = models.ConfidenceEvent(
        belief_id=None,
        scenario_prediction_id=prediction.id,
        previous_confidence=0.0,
        new_confidence=20.0,
        delta=20.0,
        reason="new_evidence_observed",
    )
    db.add(event)
    db.commit()

    linked = db.query(models.ConfidenceEvent).filter(models.ConfidenceEvent.scenario_prediction_id == prediction.id).all()
    assert len(linked) == 1
    assert linked[0].belief_id is None


def test_6_unsupported_indicators_remain_insufficient_evidence(db):
    scenario_engine.seed_phase1_indicators(db)
    governance = db.query(models.ScenarioPrediction).filter(models.ScenarioPrediction.domain == "governance").first()
    assert governance is not None
    assert governance.probability is None
    assert governance.confidence is None
    assert "no classifier exists" in governance.reasoning.lower()


def test_7_noop_when_no_eligible_signals(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_phase1_indicators(db)
    # No signals exist at all.
    result = scenario_engine.run_scenario_engine_cycle(db)
    assert result["signals_reviewed"] == 0
    assert result["signals_classified"] == 0
    assert db.query(models.Evidence).count() == 0

    # Irrelevant (Revenue Intelligence style) signal must also not be misclassified.
    signal = models.Signal(source="manual", content="Small businesses lose customers because inquiries go unanswered")
    db.add(signal)
    db.commit()
    result2 = scenario_engine.run_scenario_engine_cycle(db)
    assert result2["signals_classified"] == 0


def test_8_forge_loop_scenario_step_is_wired_and_inert(db):
    """The new forge_loop.run_cycle() step must run without error and
    contribute zero scenario classifications when there's nothing
    eligible — proving it's genuinely additive, not a source of noise."""
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_phase1_indicators(db)
    summary = forge_loop.run_cycle(db)
    assert "scenario" in summary
    assert summary["scenario"]["status"] == "completed"
    assert summary["scenario"]["signals_classified"] == 0


def test_8b_scenario_engine_failure_does_not_break_revenue_intelligence(db, monkeypatch):
    """CRITICAL SAFETY PROPERTY: if scenario_engine.run_scenario_engine_cycle()
    raises for any reason, forge_loop.run_cycle() must still return
    normally, with the Revenue Intelligence result (everything computed
    before the scenario step) fully intact — not a 500, not a lost cycle."""

    def raise_error(db):
        raise RuntimeError("simulated scenario engine failure")

    monkeypatch.setattr(scenario_engine, "run_scenario_engine_cycle", raise_error)

    summary = forge_loop.run_cycle(db)  # must NOT raise
    assert summary["scenario"]["status"] == "failed"
    assert "simulated scenario engine failure" in summary["scenario"]["reason"]
    # Revenue Intelligence fields are still present and were not touched by the failure
    assert "signals_processed" in summary
    assert "opportunities_discovered" in summary
    assert "actions_blocked" in summary


def test_9_idempotent_seeding_no_duplicates(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_default_scenarios(db)
    assert db.query(models.Scenario).count() == 6

    scenario_engine.seed_musk_forecaster_and_predictions(db)
    scenario_engine.seed_musk_forecaster_and_predictions(db)
    assert db.query(models.Forecaster).count() == 1
    assert db.query(models.ScenarioPrediction).filter(models.ScenarioPrediction.forecaster_id.isnot(None)).count() == 2

    scenario_engine.seed_phase1_indicators(db)
    scenario_engine.seed_phase1_indicators(db)
    assert db.query(models.ScenarioPrediction).filter(models.ScenarioPrediction.forecaster_id.is_(None)).count() == 3


def test_10_read_overview_assembles_correctly(db):
    scenario_engine.seed_default_scenarios(db)
    scenario_engine.seed_musk_forecaster_and_predictions(db)
    scenario_engine.seed_phase1_indicators(db)

    overview = scenario_engine.get_scenario_overview(db)
    assert len(overview["scenarios"]) == 6
    assert len(overview["forecasters"]) == 1
    assert len(overview["predictions"]) == 5  # 2 Musk + 3 indicators
    for item in overview["predictions"]:
        assert "evidence_count" in item
        assert item["evidence_count"] == 0  # no signals observed in this test
