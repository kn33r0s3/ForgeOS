"""Residue engine (2026-10-05).

Residue = observations whose perspective differs from every recorded
hypothesis. All hypotheses recorded before 2026-10-05 are SELLER-side,
so the first BUYER or CIRCLE observation is residue by definition:
it describes a side of reality no hypothesis covers.

Perspectives: SELLER | BUYER | CIRCLE
- SELLER: the seller's side (inquiries, replies, listings)
- BUYER: the buyer's own account of a purchase
- CIRCLE: the private discussion around a purchase (family, friends)
  that sellers never see
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow

PERSPECTIVES = ("SELLER", "BUYER", "CIRCLE")


def validate_perspective(value: Optional[str]) -> str:
    if value not in PERSPECTIVES:
        raise ValueError(f"perspective must be one of {PERSPECTIVES}")
    return value


def hypothesis_perspectives(db: Session) -> set:
    """Distinct perspectives across all recorded hypotheses (beliefs)."""
    rows = db.query(models.Belief.perspective).distinct().all()
    return {r[0] for r in rows if r[0]}


def flag_residue(db: Session, evidence_id: int) -> Optional[models.ResidueFlag]:
    """Flag an observation if its perspective differs from every
    recorded hypothesis. Returns the flag, or None if it fits."""
    ev = db.get(models.Evidence, evidence_id)
    if not ev:
        raise ValueError("Evidence not found.")
    if not ev.perspective:
        return None  # unrecorded perspective can't be judged
    hyps = hypothesis_perspectives(db)
    if ev.perspective in hyps:
        return None  # some hypothesis speaks for this side
    existing = (
        db.query(models.ResidueFlag)
        .filter(models.ResidueFlag.evidence_id == evidence_id)
        .first()
    )
    if existing:
        return existing
    flag = models.ResidueFlag(
        evidence_id=evidence_id,
        observation_perspective=ev.perspective,
        hypothesis_perspectives=json.dumps(sorted(hyps)),
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return flag


def scan_all(db: Session) -> list:
    """Flag every unflagged observation with a recorded perspective
    that no hypothesis covers."""
    flagged = []
    observations = (
        db.query(models.Evidence)
        .filter(models.Evidence.perspective.isnot(None))
        .all()
    )
    for ev in observations:
        flag = flag_residue(db, ev.id)
        if flag and flag.id not in {f.id for f in flagged}:
            flagged.append(flag)
    return flagged


def record_purchase_journey(
    db: Session,
    perspective: str,
    consulted_who_where: str,
    what_was_said: str,
    what_was_checked: str,
    what_almost_stopped: str,
    what_decided_it: str,
    consent_given: bool,
) -> models.Evidence:
    """Record a buyer-side purchase journey. Consent is required.
    No private chat content — only the person's own account."""
    validate_perspective(perspective)
    if perspective == "SELLER":
        raise ValueError("Purchase journeys are BUYER or CIRCLE perspective, not SELLER.")
    if not consent_given:
        raise ValueError("Consent is required before recording a purchase journey.")
    journey = {
        "consulted_who_where": consulted_who_where,
        "what_was_said": what_was_said,
        "what_was_checked": what_was_checked,
        "what_almost_stopped": what_almost_stopped,
        "what_decided_it": what_decided_it,
        "consent_given": True,
    }
    ev = models.Evidence(
        perspective=perspective,
        claim=f"Purchase journey ({perspective}): decided by '{what_decided_it[:80]}'",
        content=json.dumps(journey),
        source="owner-console intake",
        provenance="first-person account, consent recorded",
        substrate_confidence=0.8,
        recorded_at=utcnow(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    # Immediately check for residue.
    flag_residue(db, ev.id)
    return ev


def count_journeys(db: Session) -> int:
    return (
        db.query(models.Evidence)
        .filter(models.Evidence.perspective.in_(("BUYER", "CIRCLE")))
        .filter(models.Evidence.source == "owner-console intake")
        .count()
    )


SALE_DECIDED_EXPERIMENT = {
    "action": "Where is the sale decided?",
    "experiment_kind": "OBSERVATION",
    "five_fields": {
        "reality": "Sellers see inquiries and their own replies, but the buyer's decision process happens off-screen.",
        "possibility": "If sales are decided in private buyer-side talk, then seller-visible signals (reply speed, listing quality) may matter less than assumed — the real lever is elsewhere.",
        "constraint": "sales may be decided in private buyer-side talk that sellers never see",
        "constraint_state": "hypothesis",
        "intervention": "Collect >=10 buyer-side purchase journey accounts (consent-gated, first-person only); compare where the decision actually happened against seller-visible signals.",
        "outcome": "",
    },
}


def seed_sale_decided_experiment(db: Session):
    """Record the 'Where is the sale decided?' experiment. Idempotent.
    Outcome stays blank until >=10 journey accounts exist."""
    import json as _json

    existing = (
        db.query(models.Experiment)
        .filter(models.Experiment.action == SALE_DECIDED_EXPERIMENT["action"])
        .first()
    )
    if existing:
        return existing
    exp = models.Experiment(
        action=SALE_DECIDED_EXPERIMENT["action"],
        experiment_kind=SALE_DECIDED_EXPERIMENT["experiment_kind"],
        five_fields_json=_json.dumps(SALE_DECIDED_EXPERIMENT["five_fields"]),
        hypothesis=SALE_DECIDED_EXPERIMENT["five_fields"]["constraint"],
        status="planned",
        execution_status="proposed",
        data_scope="REAL",
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp
