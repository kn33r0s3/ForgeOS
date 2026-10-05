"""Single-active-intervention gate (doctrine, owner-ordered 2026-10-05).

At most one ACTIVE intervention involving a real person at a time;
everything else stays hypothesis (PROPOSED). An intervention counts as
"involving a real person" when its action_type is outreach or interview —
the types that contact or converse with real humans.

The gate is enforced at activation points (approval and start), not at
proposal time: hypotheses are free, activation is scarce.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app import models

# Action types that involve a real person.
HUMAN_INVOLVING_ACTION_TYPES = frozenset({"outreach", "interview"})

# Statuses that count as ACTIVE for the gate.
ACTIVE_STATUSES = frozenset({"APPROVED", "RUNNING"})


def involves_real_person(action: models.Action) -> bool:
    """True when the action contacts or converses with a real human."""
    return (action.action_type or "") in HUMAN_INVOLVING_ACTION_TYPES


def active_human_intervention(db: Session, exclude_id: Optional[int] = None) -> Optional[models.Action]:
    """Return the currently ACTIVE human-involving action, if any."""
    query = db.query(models.Action).filter(
        models.Action.action_type.in_(HUMAN_INVOLVING_ACTION_TYPES),
        models.Action.status.in_(ACTIVE_STATUSES),
    )
    if exclude_id is not None:
        query = query.filter(models.Action.id != exclude_id)
    return query.order_by(models.Action.id.asc()).first()


def assert_single_active_intervention(db: Session, action: models.Action) -> None:
    """Raise ValueError if activating `action` would breach the gate.

    No-op for actions that do not involve a real person, and for actions
    that are themselves the currently active one (idempotent re-approval).
    """
    if not involves_real_person(action):
        return
    existing = active_human_intervention(db, exclude_id=action.id)
    if existing is not None:
        raise ValueError(
            "Single-active-intervention gate: action "
            f"{existing.id} ({existing.action_type}, {existing.status}) is already "
            "ACTIVE and involves a real person. Complete, cancel, or fail it "
            "before activating another. Everything else stays hypothesis."
        )
