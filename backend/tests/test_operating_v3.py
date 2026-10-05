"""Operating Model v3: bets, proof ladder, WIP, pulse, tripwires, sensors, horizon, gates."""

import pytest

from app import models
from app.services import operating_v3


def _evidence(db):
    ev = models.Evidence(claim="test claim", content="test", source="test")
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def test_bet_wip_limit(db):
    for i in range(3):
        operating_v3.create_bet(
            db,
            claim=f"claim {i}",
            test="test",
            kill_criterion="kill",
            decision_rule="rule",
        )
    with pytest.raises(ValueError, match="WIP limit"):
        operating_v3.create_bet(db, claim="fourth", test="t", kill_criterion="k", decision_rule="r")
    # Decide one, then another is allowed.
    bets = db.query(models.Bet).all()
    operating_v3.decide_bet(db, bets[0].id, "killed", "did not work")
    b = operating_v3.create_bet(db, claim="fourth", test="t", kill_criterion="k", decision_rule="r")
    assert b.status == "live"


def test_bet_links_assumptions(db):
    a = models.Assumption(statement="test assumption", status="untested")
    db.add(a)
    db.commit()
    b = operating_v3.create_bet(
        db, claim="c", test="t", kill_criterion="k", decision_rule="r", assumption_ids=[a.id]
    )
    import json

    assert json.loads(b.assumption_ids) == [a.id]
    with pytest.raises(ValueError, match="Assumption 99999 not found"):
        operating_v3.create_bet(
            db, claim="c2", test="t", kill_criterion="k", decision_rule="r", assumption_ids=[99999]
        )


def test_proof_ladder_caps(db):
    ev = _evidence(db)
    # Agent-written capped at L0.
    operating_v3.set_proof_level(db, ev.id, 5, is_agent_written=True)
    ev = db.get(models.Evidence, ev.id)
    assert ev.proof_level == 0
    assert ev.proof_capped_reason is not None
    # Secondhand capped at L1.
    operating_v3.set_proof_level(db, ev.id, 4, is_secondhand=True)
    ev = db.get(models.Evidence, ev.id)
    assert ev.proof_level == 1
    # Firsthand can go higher.
    operating_v3.set_proof_level(db, ev.id, 5)
    assert db.get(models.Evidence, ev.id).proof_level == 5
    # Invalid level rejected.
    with pytest.raises(ValueError, match="0-7"):
        operating_v3.set_proof_level(db, ev.id, 9)


def test_found_wording_requires_l5(db):
    ev = _evidence(db)
    operating_v3.set_proof_level(db, ev.id, 4)
    with pytest.raises(ValueError, match=">= L5"):
        operating_v3.check_found_wording(db, ev.id)
    operating_v3.set_proof_level(db, ev.id, 5)
    operating_v3.check_found_wording(db, ev.id)  # no raise


def test_plan_change_requires_l3(db):
    ev = _evidence(db)
    operating_v3.set_proof_level(db, ev.id, 2)
    with pytest.raises(ValueError, match=">= L3"):
        operating_v3.check_plan_change([ev.id], db)
    operating_v3.set_proof_level(db, ev.id, 3)
    operating_v3.check_plan_change([ev.id], db)


def test_starved_blocks_build(db):
    # No contact events -> starved.
    assert operating_v3.is_starved(db) is True
    with pytest.raises(ValueError, match="STARVED"):
        operating_v3.check_build_allowed(db)


def test_report_validation(db):
    with pytest.raises(ValueError, match="missing verification fields"):
        operating_v3.validate_report({"deployed_sha": "abc"})
    operating_v3.validate_report(
        {"deployed_sha": "abc", "fetched_content": "html", "test_counts": "198/198"}
    )


def test_sensor_consent_gate(db):
    c = operating_v3.add_contributor(db, "Test Contributor")
    with pytest.raises(ValueError, match="Consent required"):
        operating_v3.record_sensor_observation(db, c.id, "claim", "content")
    operating_v3.record_consent(db, c.id)
    ev = operating_v3.record_sensor_observation(db, c.id, "claim", "content")
    assert ev.proof_level == 1  # secondhand capped


def test_horizon_parks(db):
    h = operating_v3.park_domain(db, "marketplace", "not now")
    assert h.unparked_at is None
    with pytest.raises(ValueError, match="already parked"):
        operating_v3.park_domain(db, "marketplace", "again")
    # Bets referencing parked domains are blocked.
    with pytest.raises(ValueError, match="parked"):
        operating_v3.create_bet(
            db, claim="build a marketplace", test="t", kill_criterion="k", decision_rule="r"
        )
    operating_v3.unpark_domain(db, h.id)
    b = operating_v3.create_bet(
        db, claim="build a marketplace", test="t", kill_criterion="k", decision_rule="r"
    )
    assert b.status == "live"


def test_gate_kill_before_result(db):
    g = operating_v3.upsert_gate(db, 14, "Day 14 check")
    assert g.kill_criterion is None
    with pytest.raises(ValueError, match="BEFORE"):
        operating_v3.record_gate_result(db, 14, "passed")
    operating_v3.upsert_gate(db, 14, "Day 14 check", kill_criterion="no seller named -> kill")
    g = operating_v3.record_gate_result(db, 14, "seller named, continue")
    assert g.result == "seller named, continue"
    # Kill criterion locked after result.
    with pytest.raises(ValueError, match="cannot be changed"):
        operating_v3.upsert_gate(db, 14, "Day 14 check", kill_criterion="new")


def test_pulse_scoreboard(db):
    board = operating_v3.pulse_scoreboard(db)
    assert "days_since_last_contact" in board
    assert "bets_by_status" in board
    assert "verified_rupees" in board
    assert board["starved"] is True
