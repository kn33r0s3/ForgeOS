"""Renovation Phase 4: truth labels.

evidence_source labels, source_kind migration, REAL-only public_stats,
REAL-requires-proof refusal, NOT MEASURABLE metric, SANDBOX separation.
"""

import pytest
from sqlalchemy import MetaData, Table, create_engine, text

from app import evidence_source, models


def _outcome(db, **kw):
    base = dict(
        outcome_type="ACTUAL_REVENUE",
        actual_value=100.0,
        unit="USD",
        source="test",
        verification_state="VERIFIED",
        data_scope="REAL",
    )
    base.update(kw)
    row = models.Outcome(**base)
    db.add(row)
    db.commit()
    return row


def test_evidence_source_labels():
    assert evidence_source.ALL == ("REAL", "TEST", "MOCK", "HYPOTHESIS")
    for label in evidence_source.ALL:
        assert evidence_source.validate(label) == label
        assert evidence_source.validate(label.lower()) == label
    assert evidence_source.is_real("REAL") is True
    assert evidence_source.is_real("MOCK") is False
    with pytest.raises(ValueError):
        evidence_source.validate("SYNTHETIC")
    with pytest.raises(ValueError):
        evidence_source.validate("")


def test_source_kind_migration_is_idempotent_and_backfills_mock():
    """Old table without source_kind: first run adds it (old rows -> MOCK),
    second run changes nothing."""
    from app.migrations import run_migrations

    engine = create_engine("sqlite:///:memory:")
    old_meta = MetaData()
    old_cols = [
        c.copy() for c in models.Outcome.__table__.columns if c.name != "source_kind"
    ]
    old_outcomes = Table("outcomes", old_meta, *old_cols)
    old_meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            old_outcomes.insert().values(
                outcome_type="ACTUAL_REVENUE",
                actual_value=50.0,
                source="legacy",
                verification_state="REPORTED",
                data_scope="REAL",
            )
        )

    first = run_migrations(engine)
    assert any("source_kind" in stmt for stmt in first)

    with engine.begin() as conn:
        kinds = [r[0] for r in conn.execute(text("SELECT source_kind FROM outcomes"))]
    assert kinds == ["MOCK"]

    second = run_migrations(engine)
    assert not any("source_kind" in stmt for stmt in second)


def test_public_stats_empty_database_is_all_zeros(db):
    from app.services.public_stats import public_stats

    assert public_stats(db) == {
        "revenue": 0.0,
        "customers": 0,
        "verified_outcomes": 0,
    }


def test_public_stats_ignores_test_mock_hypothesis(db):
    """5 TEST + 5 MOCK + 5 HYPOTHESIS rows: every public number stays 0."""
    from app.services.public_stats import public_stats

    for label in ("TEST", "MOCK", "HYPOTHESIS"):
        for _ in range(5):
            _outcome(db, source_kind=label, verification_state="VERIFIED")
        for _ in range(5):
            db.add(
                models.CustomerEvent(
                    stage="paid_customer",
                    source_kind=label,
                    data_scope="REAL",
                )
            )
    db.commit()
    assert public_stats(db) == {
        "revenue": 0.0,
        "customers": 0,
        "verified_outcomes": 0,
    }


def test_public_stats_ignores_sandbox_scope(db):
    """REAL kind + VERIFIED proof but SANDBOX scope: contributes zero.

    A sandbox simulation of a real-world process is still not the real
    world. Both truth axes (source_kind and data_scope) must be REAL.
    """
    from app.services.public_stats import public_stats

    # Outcome: REAL kind, VERIFIED, but SANDBOX scope
    _outcome(
        db,
        source_kind="REAL",
        data_scope="SANDBOX",
        verification_state="VERIFIED",
    )
    # CustomerEvent: REAL kind, SANDBOX scope
    db.add(
        models.CustomerEvent(
            stage="paid_customer",
            source_kind="REAL",
            data_scope="SANDBOX",
        )
    )
    db.commit()
    assert public_stats(db) == {
        "revenue": 0.0,
        "customers": 0,
        "verified_outcomes": 0,
    }


def test_public_stats_counts_only_real_with_proof(db):
    from app.services.public_stats import public_stats

    _outcome(db, source_kind="REAL", verification_state="VERIFIED", actual_value=250.0)
    # REAL but unproven: must not count.
    _outcome(db, source_kind="REAL", verification_state="REPORTED", actual_value=999.0)
    db.add(models.CustomerEvent(stage="paid_customer", source_kind="REAL"))
    # Paid customer labeled MOCK: must not count.
    db.add(models.CustomerEvent(stage="paid_customer", source_kind="MOCK"))
    db.commit()

    stats = public_stats(db)
    assert stats["revenue"] == 250.0
    assert stats["customers"] == 1
    assert stats["verified_outcomes"] == 1


def test_internal_real_rollups_require_real_verified_provenance(db):
    from app.services import (
        execution_engine,
        money_engine,
        orchestrator,
        product_engine,
        truth_audit,
        world_model,
    )
    from app.services.observer_engine import ObserverEngine

    opportunity = models.Opportunity(
        problem="Provenance rollup fixture",
        target_customer="test-only segment",
        solution="test-only solution",
        business_model="test-only model",
    )
    db.add(opportunity)
    db.flush()
    product = models.Product(
        opportunity_id=opportunity.id,
        name="Rollup fixture",
        offer="Evidence filter test",
        data_scope="REAL",
    )
    revenue_experiment = models.Experiment(
        opportunity_id=opportunity.id,
        action="Synthetic unverified revenue result",
        hypothesis="This fixture must not become recorded revenue.",
        result="Reported only",
        revenue=99.0,
        data_scope="REAL",
        source_kind="MOCK",
    )
    validation_experiment = models.Experiment(
        opportunity_id=opportunity.id,
        action="Synthetic interview result",
        action_type="customer_interview",
        status="completed",
        conversions=1,
        data_scope="REAL",
        source_kind="REAL",
    )
    db.add_all([product, revenue_experiment, validation_experiment])
    db.flush()
    db.add_all([
        models.Outcome(
            product_id=product.id,
            outcome_type="ACTUAL_REVENUE",
            actual_value=99.0,
            unit="USD",
            verification_state="VERIFIED",
            data_scope="REAL",
            source_kind="MOCK",
        ),
        models.Outcome(
            product_id=product.id,
            outcome_type="ACTUAL_REVENUE",
            actual_value=50.0,
            unit="USD",
            verification_state="REPORTED",
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.Outcome(
            product_id=product.id,
            experiment_id=revenue_experiment.id,
            outcome_type="ACTUAL_REVENUE",
            actual_value=25.0,
            unit="USD",
            verification_state="VERIFIED",
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.Outcome(
            experiment_id=validation_experiment.id,
            outcome_type="ACTUAL_RESPONSE",
            qualitative_result="Verified synthetic response.",
            verification_state="VERIFIED",
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.CustomerEvent(
            product_id=product.id,
            opportunity_id=opportunity.id,
            contact_name="Synthetic respondent",
            stage="interested",
            outcome_id=None,
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.LearningEvent(
            prediction="Synthetic prediction",
            actual="Synthetic result",
            lesson="Mock learning must not count as reality.",
            data_scope="REAL",
            source_kind="MOCK",
        ),
        models.LearningEvent(
            prediction="Recorded prediction",
            actual="Recorded result",
            lesson="Verified learning fixture.",
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.Lesson(
            theme_key="mock-rollup-fixture",
            title="Mock lesson",
            summary="Not real evidence.",
            data_scope="REAL",
            source_kind="MOCK",
        ),
        models.Lesson(
            theme_key="real-rollup-fixture",
            title="Real lesson fixture",
            summary="Verified learning fixture.",
            data_scope="REAL",
            source_kind="REAL",
        ),
    ])
    db.flush()
    response_outcome = db.query(models.Outcome).filter_by(
        experiment_id=validation_experiment.id,
        outcome_type="ACTUAL_RESPONSE",
    ).one()
    customer_event = db.query(models.CustomerEvent).filter_by(
        opportunity_id=opportunity.id
    ).one()
    customer_event.outcome_id = response_outcome.id
    db.commit()

    assert product_engine.rollup_product(db, product)["actual_revenue"] == 25.0
    dashboard = money_engine.get_money_dashboard(db)
    assert dashboard["total_revenue_recorded"] == 25.0
    assert dashboard["completed_experiments_count"] == 0
    assert execution_engine.get_revenue_breakdown(db)["realized"] == 25.0
    flow = orchestrator._flow_snapshot(db)
    assert flow["actual_revenue"] == 25.0
    assert flow["outcomes"] == 2
    assert flow["learning_events"] == 1
    assert flow["lessons"] == 1
    assert flow["products_with_revenue"] == 1

    labels = truth_audit.snapshot(db)["epistemic_labels"]
    assert labels["actual_outcomes"] == 2
    assert labels["actual_revenue"] == 25.0
    assert labels["reality_learning_events"] == 1
    observer = ObserverEngine(db).stats()
    assert observer["outcomes_real"] == 2
    assert observer["verified_revenue"] == 25.0
    assert world_model.get_opportunity_money_graph(
        db,
        opportunity.id,
    )["total_revenue_recorded"] == 25.0
    assert orchestrator.validation_counts(db, opportunity.id, "REAL") == (1, 1)


def test_strategy_performance_requires_real_experiments_and_verified_outcomes(db):
    from datetime import datetime, timezone

    from app.services.execution_engine import get_strategy_performance

    goal = models.Goal(statement="Test strategy provenance")
    db.add(goal)
    db.flush()
    strategy = models.Strategy(
        goal_id=goal.id,
        title="Provenance strategy",
        description="Test-only strategy",
        rationale="Verify linked evidence filtering",
    )
    opportunity = models.Opportunity(
        problem="Strategy provenance fixture",
        target_customer="test-only segment",
        solution="test-only solution",
        business_model="test-only model",
    )
    db.add_all([strategy, opportunity])
    db.flush()
    completed_at = datetime.now(timezone.utc)
    mock_experiment = models.Experiment(
        strategy_id=strategy.id,
        opportunity_id=opportunity.id,
        action="Synthetic result",
        hypothesis="Must not count as strategy evidence",
        result="Synthetic revenue",
        revenue=99.0,
        costs=20.0,
        conversions=1,
        completed_at=completed_at,
        data_scope="REAL",
        source_kind="MOCK",
    )
    real_experiment = models.Experiment(
        strategy_id=strategy.id,
        opportunity_id=opportunity.id,
        action="Recorded result",
        hypothesis="Use verified outcome only for cash",
        result="Human-recorded response",
        revenue=500.0,
        costs=80.0,
        conversions=1,
        completed_at=completed_at,
        data_scope="REAL",
        source_kind="REAL",
    )
    db.add_all([mock_experiment, real_experiment])
    db.flush()
    db.add_all([
        models.Outcome(
            experiment_id=mock_experiment.id,
            outcome_type="ACTUAL_REVENUE",
            actual_value=999.0,
            unit="USD",
            source="test",
            verification_state="VERIFIED",
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.Outcome(
            experiment_id=real_experiment.id,
            outcome_type="ACTUAL_REVENUE",
            actual_value=25.0,
            unit="USD",
            source="test",
            verification_state="VERIFIED",
            data_scope="REAL",
            source_kind="REAL",
        ),
        models.Outcome(
            experiment_id=real_experiment.id,
            outcome_type="ACTUAL_COST",
            actual_value=3.0,
            unit="USD",
            source="test",
            verification_state="VERIFIED",
            data_scope="REAL",
            source_kind="REAL",
        ),
    ])
    db.commit()

    assert get_strategy_performance(db, strategy.id) == {
        "strategy_id": strategy.id,
        "attempts": 1,
        "successes": 1,
        "success_rate": 100.0,
        "total_revenue": 25.0,
        "total_cost": 3.0,
        "net_profit": 22.0,
    }


def test_reported_revenue_result_does_not_update_real_confidence(db):
    from app.services import execution_engine, money_engine

    opportunity = models.Opportunity(
        problem="Reported revenue fixture",
        target_customer="test-only segment",
        solution="test-only solution",
        business_model="test-only model",
        status="identified",
        market_confidence=0.0,
        revenue_confidence=0.0,
        uncertainty=100.0,
    )
    db.add(opportunity)
    db.flush()
    experiment = models.Experiment(
        opportunity_id=opportunity.id,
        action="Record an unverified report",
        hypothesis="Reported revenue is not verified revenue",
        data_scope="REAL",
        source_kind="MOCK",
    )
    db.add(experiment)
    db.commit()

    money_engine.record_revenue_result(
        db,
        experiment.id,
        "Reported $99; no payment proof",
        revenue=99.0,
    )

    outcome = db.query(models.Outcome).filter_by(experiment_id=experiment.id).one()
    assert outcome.source_kind == "MOCK"
    assert outcome.verification_state == "REPORTED"
    assert opportunity.status == "identified"
    assert opportunity.revenue_confidence == 0.0
    assert opportunity.market_confidence == 0.0
    assert opportunity.uncertainty == 100.0
    assert opportunity.willingness_evidence_ids is None
    assert execution_engine.get_revenue_breakdown(db)["realized"] == 0.0


def test_real_outcome_without_proof_is_refused(db):
    from app.services.action_engine import record_outcome

    with pytest.raises(ValueError, match="require VERIFIED proof"):
        record_outcome(
            db,
            outcome_type="ACTUAL_REVENUE",
            actual_value=10.0,
            unit="USD",
            source_kind="REAL",
        )
    with pytest.raises(ValueError, match="Invalid evidence source"):
        record_outcome(
            db,
            outcome_type="OTHER",
            source_kind="SYNTHETIC",
        )


def test_real_outcome_with_proof_is_allowed(db):
    from app.services.action_engine import record_outcome

    row = record_outcome(
        db,
        outcome_type="ACTUAL_REVENUE",
        actual_value=10.0,
        unit="USD",
        source_kind="REAL",
        verification_state="VERIFIED",
    )
    assert row.source_kind == "REAL"
    assert row.verification_state == "VERIFIED"


def test_owner_interventions_not_measurable_without_real_transactions(db):
    from app.services.public_stats import owner_interventions_per_real_transaction

    assert owner_interventions_per_real_transaction(db) == "NOT MEASURABLE"


def test_owner_interventions_ratio(db):
    # Regression: counting all Action rows as "owner interventions" is a
    # false positive. Actions include proposed/authorized/executed work
    # across all actors and purposes; a verified transaction does not
    # reveal how many owner interventions enabled it. Until the canonical
    # evidence path attributes actual owner interventions with provenance,
    # the metric is NOT MEASURABLE — even with verified transactions present.
    from app.services.public_stats import owner_interventions_per_real_transaction

    for _ in range(4):
        db.add(models.Action(action_type="owner_outreach", objective="test"))
    _outcome(db, source_kind="REAL", verification_state="VERIFIED")
    _outcome(db, source_kind="REAL", verification_state="VERIFIED")
    db.commit()
    assert owner_interventions_per_real_transaction(db) == "NOT MEASURABLE"


def test_sandbox_writes_stay_sandbox_downstream(db):
    """Synthetic/pretend work enters through data_scope=SANDBOX and the
    downstream learning event inherits the label."""
    from app.services.action_engine import record_outcome

    product = models.Product(
        name="sandbox rehearsal product",
        offer="pretend offer for synthetic rehearsal",
        data_scope="SANDBOX",
    )
    db.add(product)
    db.commit()

    row = record_outcome(
        db,
        outcome_type="OTHER",
        qualitative_result="synthetic rehearsal",
        data_scope="SANDBOX",
        product_id=product.id,
    )
    assert row.data_scope == "SANDBOX"
    event = (
        db.query(models.LearningEvent)
        .filter(models.LearningEvent.lesson.like(f"%outcome #{row.id}%"))
        .first()
    )
    assert event is not None
    assert event.data_scope == "SANDBOX"
