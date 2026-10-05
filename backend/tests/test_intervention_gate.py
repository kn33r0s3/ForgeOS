"""Single-active-intervention gate (doctrine): at most one ACTIVE intervention
involving a real person at a time; everything else stays hypothesis."""

import pytest

from app import models
from app.services import action_engine, intervention_gate


def _action(db, action_type, status="PROPOSED"):
    action = models.Action(
        action_type=action_type, objective="test objective", status=status
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def test_second_human_intervention_blocked_while_first_active(db):
    first = _action(db, "outreach")
    action_engine.approve_action(db, first.id)
    assert db.get(models.Action, first.id).status == "APPROVED"

    second = _action(db, "interview")
    with pytest.raises(ValueError, match="Single-active-intervention gate"):
        action_engine.approve_action(db, second.id)
    # The blocked action stays hypothesis.
    assert db.get(models.Action, second.id).status == "PROPOSED"


def test_non_human_actions_bypass_gate(db):
    first = _action(db, "outreach")
    action_engine.approve_action(db, first.id)

    research = _action(db, "research")
    action_engine.approve_action(db, research.id)
    assert db.get(models.Action, research.id).status == "APPROVED"


def test_gate_clears_when_first_completes(db):
    first = _action(db, "outreach")
    action_engine.approve_action(db, first.id)
    first.status = "SUCCEEDED"
    db.commit()

    second = _action(db, "interview")
    action_engine.approve_action(db, second.id)
    assert db.get(models.Action, second.id).status == "APPROVED"


def test_gate_helper_identifies_active_intervention(db):
    assert intervention_gate.active_human_intervention(db) is None
    first = _action(db, "outreach")
    action_engine.approve_action(db, first.id)
    found = intervention_gate.active_human_intervention(db)
    assert found is not None and found.id == first.id
    # Excluding itself finds nothing (idempotent re-approval is allowed).
    assert intervention_gate.active_human_intervention(db, exclude_id=first.id) is None
