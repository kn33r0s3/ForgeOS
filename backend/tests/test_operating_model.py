"""Operating Model v2: assumptions, orientation, diagnosis, probes, capabilities."""

import pytest

from app import models
from app.services import operating_model


def test_seed_six_assumptions_ranked(db):
    created = operating_model.seed_assumptions(db)
    assert len(created) == 6
    # Idempotent.
    assert operating_model.seed_assumptions(db) == []
    ranked = operating_model.rank_assumptions(db)
    assert len(ranked) == 6
    # Deal-killers first.
    assert ranked[0].deal_killer is True
    assert ranked[1].deal_killer is True
    assert ranked[2].deal_killer is True
    # All start untested.
    assert all(a.status == "untested" for a in ranked)


def test_supported_requires_evidence(db):
    operating_model.seed_assumptions(db)
    a = operating_model.rank_assumptions(db)[0]
    with pytest.raises(ValueError, match="without linked evidence"):
        operating_model.set_assumption_status(db, a.id, "supported")
    # Add evidence, then it works.
    operating_model.add_evidence_link(db, a.id, "evidence:123")
    operating_model.set_assumption_status(db, a.id, "supported")
    assert db.get(models.Assumption, a.id).status == "supported"
    # Contradicted doesn't need evidence.
    operating_model.set_assumption_status(db, a.id, "contradicted")


def test_orientation_versioned_with_belief_links(db):
    operating_model.seed_assumptions(db)
    a = operating_model.rank_assumptions(db)[0]
    o1 = operating_model.record_orientation(
        db,
        observer_who="Niroj, Hami owner",
        observer_from_where="Kathmandu, Nepal",
        means="Direct observation, public pages, owner conversations",
        local_knowledge="Nepali social-commerce norms; eSewa/Khalti/COD payment culture",
        beliefs=[("Slow replies lose sales", a.id)],
    )
    assert o1.version == 1
    o2 = operating_model.record_orientation(
        db,
        observer_who="Niroj, Hami owner",
        observer_from_where="Kathmandu, Nepal",
        means="Direct observation",
        local_knowledge="Same",
        beliefs=[("Slow replies lose sales", a.id)],
    )
    assert o2.version == 2  # versioned, history kept
    beliefs = db.query(models.OrientationBelief).filter_by(orientation_id=o1.id).all()
    assert len(beliefs) == 1
    assert beliefs[0].assumption_id == a.id


def test_diagnosis_requires_one_binding(db):
    with pytest.raises(ValueError, match="Exactly one"):
        operating_model.diagnose_constraints(
            db, "situation", [("a", None, "not_binding_now"), ("b", None, "not_binding_now")]
        )
    with pytest.raises(ValueError, match="Exactly one"):
        operating_model.diagnose_constraints(
            db,
            "situation",
            [("a", None, "most_binding_hypothesis"), ("b", None, "most_binding_hypothesis")],
        )
    d = operating_model.diagnose_constraints(
        db,
        "No seller named yet",
        [
            ("No trusted human identified", "0 conversations recorded", "most_binding_hypothesis"),
            ("Legal review pending", None, "not_binding_now"),
            ("Payment rails", "no business PAN", "may_bind_later"),
        ],
    )
    nodes = db.query(models.DiagnosisNode).filter_by(diagnosis_id=d.id).all()
    assert len(nodes) == 3


def test_probe_rules(db):
    operating_model.seed_assumptions(db)
    a = operating_model.rank_assumptions(db)[0]
    # Observation probes: parallel OK.
    p1 = operating_model.record_probe(db, a.id, "observation", "Rs 0", "no signal in 50 threads")
    p2 = operating_model.record_probe(db, a.id, "observation", "Rs 0", "no signal in 50 threads")
    assert p1.id != p2.id
    # One intervention at a time.
    i1 = operating_model.record_probe(db, a.id, "intervention", "1 week", "no recovery")
    with pytest.raises(ValueError, match="one active intervention"):
        operating_model.record_probe(db, a.id, "intervention", "1 week", "no recovery")
    # Decide it, then another is allowed.
    operating_model.decide_probe(db, i1.id, "KILL", "no sales recovered")
    i2 = operating_model.record_probe(db, a.id, "intervention", "1 week", "no recovery")
    assert i2.id != i1.id
    # Conversation batches of 5.
    for _ in range(5):
        operating_model.record_probe(db, a.id, "conversation", "10 min", "no reply")
    with pytest.raises(ValueError, match="batches of 5"):
        operating_model.record_probe(db, a.id, "conversation", "10 min", "no reply")


def test_capability_requires_event_and_evidence(db):
    with pytest.raises(ValueError, match="Event not found"):
        operating_model.record_capability(db, "fast replies", event_id=99999, evidence_id=1)
    event = models.WorldEvent(event_type="test.outcome", payload="{}", source="test")
    db.add(event)
    db.flush()
    with pytest.raises(ValueError, match="Evidence not found"):
        operating_model.record_capability(db, "fast replies", event_id=event.id, evidence_id=99999)
    ev = models.Evidence(claim="test", content="test", source="test")
    db.add(ev)
    db.flush()
    c = operating_model.record_capability(
        db, "fast replies", event_id=event.id, evidence_id=ev.id, description="Answered within 5 min."
    )
    assert c.verified_by == "owner"
    with pytest.raises(ValueError, match="already recorded"):
        operating_model.record_capability(db, "fast replies", event_id=event.id, evidence_id=ev.id)
