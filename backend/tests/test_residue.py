"""Residue engine: perspective flags, journey intake, sale-decided experiment."""

import json

import pytest

from app import models
from app.services import residue_engine


_belief_counter = 0


def _belief(db, perspective="SELLER"):
    global _belief_counter
    _belief_counter += 1
    b = models.Belief(
        statement=f"Test belief {perspective} #{_belief_counter}",
        confidence_score=60.0,
        perspective=perspective,
    )
    db.add(b)
    db.commit()
    return b


def _evidence(db, perspective):
    ev = models.Evidence(
        perspective=perspective,
        claim=f"Observation from {perspective}",
        content="test",
        source="test",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def test_buyer_observation_is_residue_when_hypotheses_seller_only(db):
    _belief(db, "SELLER")
    ev = _evidence(db, "BUYER")
    flag = residue_engine.flag_residue(db, ev.id)
    assert flag is not None
    assert flag.observation_perspective == "BUYER"
    assert json.loads(flag.hypothesis_perspectives) == ["SELLER"]


def test_seller_observation_is_not_residue(db):
    _belief(db, "SELLER")
    ev = _evidence(db, "SELLER")
    assert residue_engine.flag_residue(db, ev.id) is None


def test_circle_observation_is_residue(db):
    _belief(db, "SELLER")
    ev = _evidence(db, "CIRCLE")
    flag = residue_engine.flag_residue(db, ev.id)
    assert flag is not None
    assert flag.observation_perspective == "CIRCLE"


def test_residue_clears_when_buyer_hypothesis_exists(db):
    _belief(db, "SELLER")
    _belief(db, "BUYER")
    ev = _evidence(db, "BUYER")
    assert residue_engine.flag_residue(db, ev.id) is None


def test_journey_requires_consent(db):
    with pytest.raises(ValueError, match="Consent is required"):
        residue_engine.record_purchase_journey(
            db,
            perspective="BUYER",
            consulted_who_where="x",
            what_was_said="x",
            what_was_checked="x",
            what_almost_stopped="x",
            what_decided_it="x",
            consent_given=False,
        )


def test_journey_rejects_seller_perspective(db):
    with pytest.raises(ValueError, match="BUYER or CIRCLE"):
        residue_engine.record_purchase_journey(
            db,
            perspective="SELLER",
            consulted_who_where="x",
            what_was_said="x",
            what_was_checked="x",
            what_almost_stopped="x",
            what_decided_it="x",
            consent_given=True,
        )


def test_journey_recorded_and_auto_flagged(db):
    _belief(db, "SELLER")
    ev = residue_engine.record_purchase_journey(
        db,
        perspective="BUYER",
        consulted_who_where="Asked my sister on Viber",
        what_was_said="She said the shop looked legit",
        what_was_checked="Facebook reviews and photos",
        what_almost_stopped="No COD option listed",
        what_decided_it="Sister's recommendation",
        consent_given=True,
    )
    assert ev.perspective == "BUYER"
    journey = json.loads(ev.content)
    assert journey["consulted_who_where"] == "Asked my sister on Viber"
    assert journey["consent_given"] is True
    # Auto-flagged as residue (no BUYER hypothesis).
    flag = (
        db.query(models.ResidueFlag)
        .filter(models.ResidueFlag.evidence_id == ev.id)
        .first()
    )
    assert flag is not None


def test_sale_decided_experiment_seed(db):
    exp = residue_engine.seed_sale_decided_experiment(db)
    assert exp.experiment_kind == "OBSERVATION"
    fields = json.loads(exp.five_fields_json)
    assert fields["constraint"] == "sales may be decided in private buyer-side talk that sellers never see"
    assert fields["constraint_state"] == "hypothesis"
    assert fields["outcome"] == ""  # blank until >=10 accounts
    # Idempotent.
    assert residue_engine.seed_sale_decided_experiment(db).id == exp.id
