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
