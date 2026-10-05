"""Operating Model v4 (2026-10-05). See docs/OPERATING_MODEL.md.

Bet is a PROJECTION over SubstrateEntity (entity_type="bet") — not a new
primitive. All v4 rules enforced here.
"""

import json
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow

BET_ENTITY_TYPE = "bet"
BET_STATUSES = ("live", "amplified", "dampened", "killed")
MAX_LIVE_BETS = 3
STARVED_DAYS = 14

PROOF_LEVELS = {
    0: "idea / agent-written text — may suggest a Bet",
    1: "secondhand source (paper, forum, article) — may suggest; never decides",
    2: "direct observation — may shape priorities",
    3: "another person's consented account — may justify a probe or change a plan",
    4: "observed behavior — what they actually did",
    5: "costly signal — real time, money, effort, reputation, access, inventory, or other meaningful sacrifice",
    6: "repeated costly signals from independently observed participants",
    7: "repeated verified outcome, independently verified across repetitions",
}

SOURCE_TYPES = ("firsthand", "secondhand", "agent_written", "sensor", "third_party")


# ---------------------------------------------------------------------
# Bet as a projection over SubstrateEntity
# ---------------------------------------------------------------------

def _bet_attributes(bet: models.SubstrateEntity) -> dict:
    return json.loads(bet.attributes or "{}")


def live_bets(db: Session) -> list:
    bets = (
        db.query(models.SubstrateEntity)
        .filter(
            models.SubstrateEntity.entity_type == BET_ENTITY_TYPE,
            models.SubstrateEntity.status == "active",
        )
        .all()
    )
    return [b for b in bets if _bet_attributes(b).get("status") == "live"]


def create_bet(
    db: Session,
    claim: str,
    constraint: str,
    test: str,
    kill_criterion: str,
    decision_rule: str,
    skeptic_case: str,
    owner_time: Optional[str] = None,
    attention: Optional[str] = None,
    energy: Optional[str] = None,
    money_at_risk: Optional[str] = None,
    trust_at_risk: Optional[str] = None,
    deadline: Optional[datetime] = None,
    assumption_ids: Optional[list] = None,
) -> models.SubstrateEntity:
    if len(live_bets(db)) >= MAX_LIVE_BETS:
        raise ValueError(f"WIP limit: at most {MAX_LIVE_BETS} live Bets.")
    attributes = {
        "claim": claim,
        "constraint": constraint,
        "test": test,
        "affordable_loss": {
            "owner_time": owner_time,
            "attention": attention,
            "energy": energy,
            "money_at_risk": money_at_risk,
            "trust_at_risk": trust_at_risk,
        },
        "deadline": deadline.isoformat() if deadline else None,
        "kill_criterion": kill_criterion,
        "skeptic_case": skeptic_case,
        "decision_rule": decision_rule,
        "status": "live",
        "assumption_ids": assumption_ids or [],
    }
    bet = models.SubstrateEntity(
        entity_type=BET_ENTITY_TYPE,
        display_name=f"Bet: {claim[:80]}",
        attributes=json.dumps(attributes),
        identity_state="candidate",
        created_by="owner",
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


def decide_bet(db: Session, bet_id: int, decision: str, notes: Optional[str] = None):
    if decision not in ("amplified", "dampened", "killed"):
        raise ValueError("decision must be amplified|dampened|killed")
    bet = db.get(models.SubstrateEntity, bet_id)
    if not bet or bet.entity_type != BET_ENTITY_TYPE:
        raise ValueError("Bet not found.")
    attrs = _bet_attributes(bet)
    attrs["status"] = decision
    attrs["decided_at"] = utcnow().isoformat()
    attrs["decision_notes"] = notes
    bet.attributes = json.dumps(attrs)
    if decision == "killed":
        # Archive, never delete: keep the record, mark archived.
        bet.status = "archived"
    db.commit()
    db.refresh(bet)
    return bet


# ---------------------------------------------------------------------
# Proof ladder with provenance rules
# ---------------------------------------------------------------------

def set_proof_level(
    db: Session,
    evidence_id: int,
    level: int,
    source_type: Optional[str] = None,
    verifier: Optional[str] = None,
) -> models.Evidence:
    if level not in PROOF_LEVELS:
        raise ValueError(f"proof_level must be 0-7, got {level}")
    ev = db.get(models.Evidence, evidence_id)
    if not ev:
        raise ValueError("Evidence not found.")
    st = source_type or ev.source_type
    if st == "agent_written" and level > 0:
        ev.proof_level = 0
        ev.proof_capped_reason = "agent-written items are capped at L0"
    elif st == "secondhand" and level > 1:
        ev.proof_level = 1
        ev.proof_capped_reason = "secondhand items are capped at L1"
    elif level >= 5 and not (verifier or ev.verifier):
        raise ValueError(
            "L5+ requires external anchoring: counterparty confirmation or "
            "a third-party timestamp (verifier field). Anchoring establishes "
            "provenance, timing, or occurrence — not automatically a costly signal."
        )
    else:
        ev.proof_level = level
        ev.proof_capped_reason = None
    if source_type:
        ev.source_type = source_type
    if verifier:
        ev.verifier = verifier
    db.commit()
    db.refresh(ev)
    return ev


# ---------------------------------------------------------------------
# Contact clock, STARVED, scoreboard
# ---------------------------------------------------------------------

def days_since_last_contact(db: Session) -> Optional[int]:
    latest = (
        db.query(models.WorldEvent)
        .filter(
            models.WorldEvent.event_type.in_(
                ["outreach.sent", "outreach.reply", "conversation.held"]
            )
        )
        .order_by(models.WorldEvent.occurred_at.desc())
        .first()
    )
    if not latest or not latest.occurred_at:
        return None
    return (utcnow() - latest.occurred_at).days


def is_starved(db: Session) -> bool:
    days = days_since_last_contact(db)
    return days is None or days >= STARVED_DAYS


def check_build_allowed(db: Session, is_system_obligation: bool = False) -> None:
    """STARVED blocks build tasks except System Obligations."""
    if is_starved(db) and not is_system_obligation:
        raise ValueError(
            "STARVED: no real contact for 14+ days. Build tasks are blocked "
            "until a real conversation happens (System Obligations exempt)."
        )


def who_not_heard_from(db: Session) -> list:
    """Contributors with consent but no observations in 14+ days."""
    cutoff = utcnow() - timedelta_days(STARVED_DAYS)
    silent = []
    for c in db.query(models.SensorContributor).filter(
        models.SensorContributor.consent_given == True  # noqa: E712
    ).all():
        latest = (
            db.query(models.Evidence)
            .filter(models.Evidence.source == f"sensor-circle:{c.name}")
            .order_by(models.Evidence.id.desc())
            .first()
        )
        if not latest or (latest.recorded_at and latest.recorded_at < cutoff):
            silent.append(c.name)
    return silent


def timedelta_days(n: int):
    from datetime import timedelta
    return timedelta(days=n)


def scoreboard(db: Session) -> dict:
    """Read-only scoreboard. Agents read; they do not write.
    Fields per docs/OPERATING_MODEL.md honest scoreboard."""
    bets = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == BET_ENTITY_TYPE)
        .all()
    )
    by_status: dict = {}
    for b in bets:
        s = _bet_attributes(b).get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    highest = (
        db.query(models.Evidence.proof_level)
        .order_by(models.Evidence.proof_level.desc())
        .first()
    )
    # Sampling gaps: perspectives with zero observations.
    perspectives = ("SELLER", "BUYER", "CIRCLE")
    gaps = []
    for p in perspectives:
        count = (
            db.query(models.Evidence)
            .filter(models.Evidence.perspective == p)
            .count()
        )
        if count == 0:
            gaps.append(p)
    budget = _owner_budget(db)
    return {
        "days_since_last_contact": days_since_last_contact(db),
        "observations": db.query(models.Evidence).count(),
        "conversations": db.query(models.Evidence)
        .filter(models.Evidence.claim.ilike("%conversation%"))
        .count(),
        "live_bets": by_status.get("live", 0),
        "bets_killed": by_status.get("killed", 0),
        "bets_amplified": by_status.get("amplified", 0),
        "bets_by_status": by_status,
        "highest_proof_level": highest[0] if highest else 0,
        "verified_rupees": 0.0,  # real money moves update this; never estimated
        "sampling_gaps": gaps,
        "who_not_heard_from": who_not_heard_from(db),
        "owner_time_used": budget["used"],
        "owner_budget_remaining": budget["remaining"],
        "starved": is_starved(db),
    }


def _owner_budget(db: Session) -> dict:
    """Owner time budget from the singleton row."""
    b = db.query(models.OwnerBudget).first()
    if not b:
        return {"used": "unknown", "remaining": "unknown"}
    return {"used": b.hours_used, "remaining": b.hours_remaining}


# ---------------------------------------------------------------------
# Independent verifier (append-only)
# ---------------------------------------------------------------------

def record_verification(
    db: Session,
    deployed_sha: str,
    fetched_content: str,
    test_counts: str,
    passed: bool,
    source: str = "ci",
) -> models.DeployVerification:
    if not deployed_sha or not fetched_content or not test_counts:
        raise ValueError(
            "Reports without deployed SHA, fetched content, and test counts are rejected."
        )
    rec = models.DeployVerification(
        deployed_sha=deployed_sha,
        fetched_content=fetched_content,
        test_counts=test_counts,
        passed=passed,
        source=source,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# ---------------------------------------------------------------------
# Dormancy
# ---------------------------------------------------------------------

def _dormancy(db: Session) -> models.DormancyState:
    state = db.query(models.DormancyState).first()
    if not state:
        state = models.DormancyState(is_dormant=False)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def is_dormant(db: Session) -> bool:
    return _dormancy(db).is_dormant


def enter_dormancy(db: Session, by: str = "owner") -> models.DormancyState:
    state = _dormancy(db)
    state.is_dormant = True
    state.frozen_at = utcnow()
    state.frozen_by = by
    db.commit()
    return state


def check_agent_run_allowed(db: Session) -> None:
    if is_dormant(db):
        raise ValueError("Dormant: agent runs are stopped. Resume only from docs/RUN_STATE.md.")


def exit_dormancy(db: Session, run_state_path: str = "docs/RUN_STATE.md") -> models.DormancyState:
    if not os.path.exists(run_state_path):
        raise ValueError(
            f"Cannot resume: {run_state_path} does not exist. "
            "Resume only from docs/RUN_STATE.md."
        )
    state = _dormancy(db)
    state.is_dormant = False
    state.resume_note = f"Resumed from {run_state_path}"
    db.commit()
    return state


# ---------------------------------------------------------------------
# Frontier challenge
# ---------------------------------------------------------------------

def record_frontier_challenge(
    db: Session, month: str, alternative_frontier: str, comparison: str,
    verdict: Optional[str] = None,
) -> models.FrontierChallenge:
    existing = db.query(models.FrontierChallenge).filter(
        models.FrontierChallenge.month == month
    ).first()
    if existing:
        raise ValueError(f"Frontier challenge for {month} already recorded.")
    fc = models.FrontierChallenge(
        month=month,
        alternative_frontier=alternative_frontier,
        comparison=comparison,
        verdict=verdict,
    )
    db.add(fc)
    db.commit()
    db.refresh(fc)
    return fc


# ---------------------------------------------------------------------
# Frozen frontier (90 days from 2026-10-05)
# ---------------------------------------------------------------------

FROZEN_FRONTIER = (
    "How small online purchases in Nepal are actually decided, "
    "on both the buyer and seller side."
)
FRONTIER_START = "2026-10-05"
FRONTIER_DAY_90 = "2027-01-03"


def seed_frontier_gates(db: Session) -> list:
    """Seed Day 14/30/60/90 gates. Day 90 carries the model kill criterion.
    Idempotent."""
    from app.models import Gate  # local import to avoid cycles

    specs = [
        (14, "Day 14: contact check", "No real contact in 14 days => STARVED review"),
        (30, "Day 30: frontier review", "Zero L3+ signals => frontier challenged"),
        (60, "Day 60: frontier review", "Zero L5 signals => frontier challenged"),
        (
            90,
            "Day 90: model/frontier review",
            "Zero L5+ signals => model and frontier both under review",
        ),
    ]
    created = []
    for day, title, kill in specs:
        existing = db.query(Gate).filter(Gate.day == day).first()
        if existing:
            continue
        g = Gate(day=day, title=title, kill_criterion=kill)
        db.add(g)
        created.append(g)
    db.commit()
    return created
