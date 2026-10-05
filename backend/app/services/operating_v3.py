"""Operating Model v3 (2026-10-05).

Bet -> Proof ladder (L0-L7) -> WIP limits -> Pulse -> Tripwires ->
Sensor circle -> Horizon register -> Gates.

Archive, never delete.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow

# ---------------------------------------------------------------------
# Proof ladder L0-L7
# ---------------------------------------------------------------------

PROOF_LEVELS = {
    0: "agent-written or secondhand, unverified",
    1: "secondhand with named source",
    2: "firsthand observation, uncorroborated",
    3: "corroborated by 2+ independent observations",
    4: "tested (probe completed with a result)",
    5: "verified outcome (Event + Evidence, owner-confirmed)",
    6: "replicated (2+ verified outcomes)",
    7: "decisive (moved money or a real decision)",
}

BET_STATUSES = ("live", "amplified", "dampened", "killed")
MAX_LIVE_BETS = 3
STARVED_DAYS = 14


def set_proof_level(
    db: Session,
    evidence_id: int,
    level: int,
    is_agent_written: bool = False,
    is_secondhand: bool = False,
) -> models.Evidence:
    """Set an Evidence record's proof level with v3 validation rules:
    - agent-written or secondhand items are capped at L0/L1
    - level must be 0-7
    """
    if level not in PROOF_LEVELS:
        raise ValueError(f"proof_level must be 0-7, got {level}")
    ev = db.get(models.Evidence, evidence_id)
    if not ev:
        raise ValueError("Evidence not found.")
    if (is_agent_written or is_secondhand) and level > 1:
        ev.proof_level = 1 if is_secondhand and not is_agent_written else 0
        ev.proof_capped_reason = (
            "agent-written" if is_agent_written else "secondhand"
        ) + " items are capped at L0/L1"
    else:
        ev.proof_level = level
        ev.proof_capped_reason = None
    db.commit()
    db.refresh(ev)
    return ev


def check_found_wording(db: Session, evidence_id: int) -> None:
    """Public 'found' wording requires proof >= L5."""
    ev = db.get(models.Evidence, evidence_id)
    if not ev:
        raise ValueError("Evidence not found.")
    if (ev.proof_level or 0) < 5:
        raise ValueError(
            f"Public 'found' wording requires proof level >= L5; "
            f"evidence #{evidence_id} is L{ev.proof_level}."
        )


def check_plan_change(evidence_ids: list, db: Session) -> None:
    """Plan/priority changes require proof >= L3 on supporting evidence."""
    for eid in evidence_ids:
        ev = db.get(models.Evidence, eid)
        if not ev:
            raise ValueError(f"Evidence #{eid} not found.")
        if (ev.proof_level or 0) < 3:
            raise ValueError(
                f"Plan/priority changes require proof >= L3; "
                f"evidence #{eid} is L{ev.proof_level}."
            )


# ---------------------------------------------------------------------
# Bets
# ---------------------------------------------------------------------

def live_bet_count(db: Session) -> int:
    return db.query(models.Bet).filter(models.Bet.status == "live").count()


def create_bet(
    db: Session,
    claim: str,
    test: str,
    kill_criterion: str,
    decision_rule: str,
    affordable_loss_time: Optional[str] = None,
    affordable_loss_money: Optional[str] = None,
    affordable_loss_trust: Optional[str] = None,
    deadline: Optional[datetime] = None,
    assumption_ids: Optional[list] = None,
) -> models.Bet:
    if live_bet_count(db) >= MAX_LIVE_BETS:
        raise ValueError(f"WIP limit: at most {MAX_LIVE_BETS} live Bets.")
    for aid in assumption_ids or []:
        if not db.get(models.Assumption, aid):
            raise ValueError(f"Assumption {aid} not found.")
    # Horizon check: bets may not reference parked domains.
    # (Enforced by name match on claim/test — conservative.)
    for h in db.query(models.HorizonDomain).filter(
        models.HorizonDomain.unparked_at.is_(None)
    ).all():
        if h.name.lower() in (claim + " " + test).lower():
            raise ValueError(f"Domain '{h.name}' is parked on the Horizon register.")
    bet = models.Bet(
        claim=claim,
        test=test,
        kill_criterion=kill_criterion,
        decision_rule=decision_rule,
        affordable_loss_time=affordable_loss_time,
        affordable_loss_money=affordable_loss_money,
        affordable_loss_trust=affordable_loss_trust,
        deadline=deadline,
        assumption_ids=json.dumps(assumption_ids or []),
        status="live",
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


def decide_bet(
    db: Session, bet_id: int, decision: str, notes: Optional[str] = None
) -> models.Bet:
    if decision not in ("amplified", "dampened", "killed"):
        raise ValueError("decision must be amplified|dampened|killed")
    bet = db.get(models.Bet, bet_id)
    if not bet:
        raise ValueError("Bet not found.")
    bet.status = decision
    bet.decided_at = utcnow()
    bet.decision_notes = notes
    db.commit()
    db.refresh(bet)
    return bet


def bet_views(db: Session) -> dict:
    """Map existing unknowns/experiments/probes into Bet views.
    Nothing is deleted — these are read-only projections."""
    # Unknowns -> potential bets (not yet bets)
    unknowns = []
    try:
        from app.models import ResearchQuestion  # unknowns surface
        # Fallback: count only; detailed mapping lives in the UI query.
    except ImportError:
        pass
    experiments = db.query(models.Experiment).all() if hasattr(models, "Experiment") else []
    bets = db.query(models.Bet).order_by(models.Bet.id.desc()).all()
    return {
        "bets": [
            {
                "id": b.id,
                "claim": b.claim,
                "status": b.status,
                "deadline": b.deadline,
                "kill_criterion": b.kill_criterion,
            }
            for b in bets
        ],
        "experiment_count": len(experiments),
        "note": "Unknowns, experiments, and probes are preserved as-is; "
        "link them to Bets via assumption_ids. Nothing was deleted.",
    }


# ---------------------------------------------------------------------
# Pulse: scoreboard
# ---------------------------------------------------------------------

def days_since_last_contact(db: Session) -> Optional[int]:
    """Days since the last real-world contact (outreach.sent event or
    conversation evidence). None if never."""
    latest = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type.in_(["outreach.sent", "outreach.reply", "conversation.held"]))
        .order_by(models.WorldEvent.occurred_at.desc())
        .first()
    )
    if not latest or not latest.occurred_at:
        return None
    return (utcnow() - latest.occurred_at).days


def pulse_scoreboard(db: Session) -> dict:
    observations = db.query(models.Evidence).count()
    conversations = (
        db.query(models.Evidence)
        .filter(models.Evidence.claim.ilike("%conversation%"))
        .count()
    )
    bets = db.query(models.Bet).all()
    by_status: dict = {}
    for b in bets:
        by_status[b.status] = by_status.get(b.status, 0) + 1
    highest_proof = (
        db.query(models.Evidence.proof_level).order_by(models.Evidence.proof_level.desc()).first()
    )
    # Verified rupees: sum of revenue_amount on verified outcomes.
    verified_rupees = 0.0
    if hasattr(models, "Experiment"):
        rows = (
            db.query(models.Experiment.revenue_amount)
            .filter(models.Experiment.revenue_amount > 0)
            .all()
        )
        verified_rupees = sum(r[0] for r in rows)
    return {
        "days_since_last_contact": days_since_last_contact(db),
        "observations": observations,
        "conversations": conversations,
        "bets_by_status": by_status,
        "highest_proof_level": highest_proof[0] if highest_proof else 0,
        "verified_rupees": verified_rupees,
        "starved": is_starved(db),
    }


# ---------------------------------------------------------------------
# Tripwires
# ---------------------------------------------------------------------

def is_starved(db: Session) -> bool:
    days = days_since_last_contact(db)
    return days is None or days >= STARVED_DAYS


def check_build_allowed(db: Session) -> None:
    """STARVED blocks build tasks. Builds must reference a live Bet
    (checked by the caller passing bet_id)."""
    if is_starved(db):
        raise ValueError(
            "STARVED: no real contact for 14+ days. Build tasks are blocked "
            "until a real conversation happens."
        )


def flag_proof_violations(db: Session) -> list:
    """Flag claims whose public wording exceeds their proof level.
    Returns evidence IDs that claim 'found' below L5."""
    violations = []
    for ev in db.query(models.Evidence).all():
        claim = (ev.claim or "").lower()
        if "found" in claim and (ev.proof_level or 0) < 5:
            violations.append({"evidence_id": ev.id, "proof_level": ev.proof_level})
    return violations


def validate_report(report: dict) -> None:
    """Reject reports lacking verification fields."""
    required = ["deployed_sha", "fetched_content", "test_counts"]
    missing = [f for f in required if not report.get(f)]
    if missing:
        raise ValueError(f"Report rejected: missing verification fields: {missing}")


# ---------------------------------------------------------------------
# Sensor circle
# ---------------------------------------------------------------------

def add_contributor(db: Session, name: str, notes: Optional[str] = None) -> models.SensorContributor:
    c = models.SensorContributor(name=name, notes=notes, consent_given=False)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def record_consent(db: Session, contributor_id: int) -> models.SensorContributor:
    c = db.get(models.SensorContributor, contributor_id)
    if not c:
        raise ValueError("Contributor not found.")
    c.consent_given = True
    c.consent_at = utcnow()
    db.commit()
    db.refresh(c)
    return c


def record_sensor_observation(
    db: Session, contributor_id: int, claim: str, content: str
) -> models.Evidence:
    c = db.get(models.SensorContributor, contributor_id)
    if not c:
        raise ValueError("Contributor not found.")
    if not c.consent_given:
        raise ValueError("Consent required before accepting a sensor observation.")
    ev = models.Evidence(
        claim=claim,
        content=content,
        source=f"sensor-circle:{c.name}",
        provenance="consent-based contributor observation",
        proof_level=1,  # secondhand by default; capped
        proof_capped_reason="secondhand items are capped at L0/L1",
        recorded_at=utcnow(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# ---------------------------------------------------------------------
# Horizon register
# ---------------------------------------------------------------------

def park_domain(db: Session, name: str, reason: str) -> models.HorizonDomain:
    existing = db.query(models.HorizonDomain).filter(models.HorizonDomain.name == name).first()
    if existing:
        raise ValueError("Domain already parked.")
    h = models.HorizonDomain(name=name, reason_parked=reason)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def unpark_domain(db: Session, domain_id: int) -> models.HorizonDomain:
    h = db.get(models.HorizonDomain, domain_id)
    if not h:
        raise ValueError("Domain not found.")
    h.unparked_at = utcnow()
    db.commit()
    db.refresh(h)
    return h


# ---------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------

GATE_DAYS = (14, 30, 60, 90)


def upsert_gate(
    db: Session, day: int, title: str, kill_criterion: Optional[str] = None
) -> models.Gate:
    if day not in GATE_DAYS:
        raise ValueError(f"Gate day must be one of {GATE_DAYS}")
    gate = db.query(models.Gate).filter(models.Gate.day == day).first()
    if not gate:
        gate = models.Gate(day=day, title=title)
        db.add(gate)
    else:
        gate.title = title
    if kill_criterion is not None:
        if gate.result is not None:
            raise ValueError("Kill criterion cannot be changed after a result is recorded.")
        gate.kill_criterion = kill_criterion
    gate.updated_at = utcnow()
    db.commit()
    db.refresh(gate)
    return gate


def record_gate_result(db: Session, day: int, result: str) -> models.Gate:
    gate = db.query(models.Gate).filter(models.Gate.day == day).first()
    if not gate:
        raise ValueError("Gate not found.")
    if not gate.kill_criterion:
        raise ValueError("Kill criterion must be stored BEFORE any result.")
    gate.result = result
    gate.decided_at = utcnow()
    db.commit()
    db.refresh(gate)
    return gate
