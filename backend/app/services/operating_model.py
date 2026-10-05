"""Operating Model v2 (2026-10-05).

Assumption register -> Orientation -> Constraint diagnosis ->
Probe portfolio -> Capability map.

Capabilities come only from verified outcomes (Event + Evidence),
never from prose.
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow

ASSUMPTION_STATUSES = ("untested", "supported", "contradicted")
PROBE_TYPES = ("observation", "conversation", "intervention")
PROBE_DECISIONS = ("AMPLIFY", "DAMPEN", "KILL")
BINDING_STATUSES = ("most_binding_hypothesis", "not_binding_now", "may_bind_later")


# The six load-bearing assumptions of the Hami operating model, derived
# from docs/ORIGIN.md (Doctrine v1.0) and the recorded operating history.
# Source note on each says where it came from; the owner confirms or
# corrects. Ranked deal-killer + cheap-to-test first.
SEED_ASSUMPTIONS = [
    {
        "statement": "Slow replies cost online sellers real sales.",
        "deal_killer": True,
        "cost_to_test": "Rs 0",
        "cheapest_test": "Reply-visibility sampling: count unanswered public inquiry comments across 10 seller pages.",
        "milestone": "Rs 1",
        "source_note": "Doctrine v1.0 (ORIGIN.md); slow-reply constraint from discovery rounds D1-D10.",
    },
    {
        "statement": "Sellers will pay for sales recovered from slow replies.",
        "deal_killer": True,
        "cost_to_test": "1 week of human time",
        "cheapest_test": "First Rupee Sprint: one seller, one week, human answers fast; ask for a cut of recovered sales.",
        "milestone": "Rs 1",
        "source_note": "Revenue milestone ladder (MEMORY.md); FIRST_RUPEE_SPRINT.md.",
    },
    {
        "statement": "Faster replies recover lost sales (the intervention works).",
        "deal_killer": True,
        "cost_to_test": "1 week of human time",
        "cheapest_test": "Experiment 1: one seller, one week; count recovered vs lost with fast replies.",
        "milestone": "Rs 1",
        "source_note": "Experiment 1 five-field template; intervention_gate single-active rule.",
    },
    {
        "statement": "Sales may be decided in private buyer-side talk that sellers never see.",
        "deal_killer": False,
        "cost_to_test": "Rs 0",
        "cheapest_test": "Collect 10 buyer-side purchase journey accounts (consent-gated); compare decision points to seller-visible signals.",
        "milestone": "Rs 10,000",
        "source_note": "Buyer-perspective work 2026-10-05; 'Where is the sale decided?' experiment.",
    },
    {
        "statement": "Response capacity and verification are the open gap (ledgers and payments are taken).",
        "deal_killer": False,
        "cost_to_test": "Rs 0 (research)",
        "cheapest_test": "Map which seller tools already cover response vs ledger vs payments; confirm no incumbent owns fast-reply recovery.",
        "milestone": "Rs 10,000",
        "source_note": "EXPANSION_STRATEGY.md 2026-10-04: ledgers (Karobar) and payments (Fonepay/eSewa) taken.",
    },
    {
        "statement": "One seller, one week is enough to prove or kill the value thesis.",
        "deal_killer": False,
        "cost_to_test": "1 week of human time",
        "cheapest_test": "Run the First Rupee Sprint exactly as specified; if no sales recovered, the thesis dies honestly.",
        "milestone": "Rs 1",
        "source_note": "SPRINT_BRIEF.md 2026-10-04; 'if no sales are recovered the thesis dies honestly'.",
    },
]


def seed_assumptions(db: Session) -> list:
    """Seed the six assumptions. Idempotent."""
    created = []
    for spec in SEED_ASSUMPTIONS:
        existing = (
            db.query(models.Assumption)
            .filter(models.Assumption.statement == spec["statement"])
            .first()
        )
        if existing:
            continue
        a = models.Assumption(
            statement=spec["statement"],
            status="untested",
            deal_killer=spec["deal_killer"],
            cost_to_test=spec["cost_to_test"],
            cheapest_test=spec["cheapest_test"],
            milestone=spec["milestone"],
            source_note=spec["source_note"],
        )
        db.add(a)
        created.append(a)
    db.commit()
    return created


def rank_assumptions(db: Session) -> list:
    """Deal-killer first, then cheapest to test. Cost ordering is
    heuristic: Rs 0 < research < 1 week."""
    def cost_rank(a: models.Assumption) -> int:
        cost = (a.cost_to_test or "").lower()
        if "rs 0" in cost:
            return 0
        if "research" in cost:
            return 1
        return 2

    assumptions = db.query(models.Assumption).all()
    assumptions.sort(key=lambda a: (not a.deal_killer, cost_rank(a), a.id))
    return assumptions


def set_assumption_status(db: Session, assumption_id: int, status: str) -> models.Assumption:
    if status not in ASSUMPTION_STATUSES:
        raise ValueError(f"status must be one of {ASSUMPTION_STATUSES}")
    a = db.get(models.Assumption, assumption_id)
    if not a:
        raise ValueError("Assumption not found.")
    if status == "supported":
        links = json.loads(a.evidence_links or "[]")
        if not links:
            raise ValueError(
                "Cannot mark 'supported' without linked evidence. "
                "Record evidence links first."
            )
    a.status = status
    a.updated_at = utcnow()
    db.commit()
    db.refresh(a)
    return a


def add_evidence_link(db: Session, assumption_id: int, evidence_ref: str) -> models.Assumption:
    a = db.get(models.Assumption, assumption_id)
    if not a:
        raise ValueError("Assumption not found.")
    links = json.loads(a.evidence_links or "[]")
    if evidence_ref not in links:
        links.append(evidence_ref)
    a.evidence_links = json.dumps(links)
    a.updated_at = utcnow()
    db.commit()
    db.refresh(a)
    return a


def record_orientation(
    db: Session,
    observer_who: str,
    observer_from_where: str,
    means: str,
    local_knowledge: str,
    beliefs: list,
) -> models.Orientation:
    """Record a new versioned orientation. Beliefs are (belief_text, assumption_id) pairs."""
    latest = db.query(models.Orientation).order_by(models.Orientation.version.desc()).first()
    version = (latest.version + 1) if latest else 1
    o = models.Orientation(
        version=version,
        observer_who=observer_who,
        observer_from_where=observer_from_where,
        means=means,
        local_knowledge=local_knowledge,
    )
    db.add(o)
    db.flush()
    for belief_text, assumption_id in beliefs:
        if assumption_id is not None and not db.get(models.Assumption, assumption_id):
            raise ValueError(f"Assumption {assumption_id} not found.")
        db.add(
            models.OrientationBelief(
                orientation_id=o.id,
                belief_text=belief_text,
                assumption_id=assumption_id,
            )
        )
    db.commit()
    db.refresh(o)
    return o


def diagnose_constraints(db: Session, situation: str, nodes: list) -> models.ConstraintDiagnosis:
    """Record a constraint diagnosis. Exactly one node must be marked
    'most_binding_hypothesis'. Nodes are (node_text, evidence, binding_status)."""
    binding = [n for n in nodes if n[2] == "most_binding_hypothesis"]
    if len(binding) != 1:
        raise ValueError(
            f"Exactly one node must be 'most_binding_hypothesis', got {len(binding)}."
        )
    for _, _, status in nodes:
        if status not in BINDING_STATUSES:
            raise ValueError(f"binding_status must be one of {BINDING_STATUSES}")
    d = models.ConstraintDiagnosis(situation=situation)
    db.add(d)
    db.flush()
    for node_text, evidence, binding_status in nodes:
        db.add(
            models.DiagnosisNode(
                diagnosis_id=d.id,
                node_text=node_text,
                evidence=evidence,
                binding_status=binding_status,
            )
        )
    db.commit()
    db.refresh(d)
    return d


def active_intervention_count(db: Session) -> int:
    return (
        db.query(models.Probe)
        .filter(
            models.Probe.probe_type == "intervention",
            models.Probe.decision.is_(None),
            models.Probe.ended_at.is_(None),
        )
        .count()
    )


def active_conversation_count(db: Session) -> int:
    return (
        db.query(models.Probe)
        .filter(
            models.Probe.probe_type == "conversation",
            models.Probe.decision.is_(None),
            models.Probe.ended_at.is_(None),
        )
        .count()
    )


def record_probe(
    db: Session,
    assumption_id: int,
    probe_type: str,
    affordable_loss: str,
    kill_criterion: str,
) -> models.Probe:
    if probe_type not in PROBE_TYPES:
        raise ValueError(f"probe_type must be one of {PROBE_TYPES}")
    if not db.get(models.Assumption, assumption_id):
        raise ValueError("Assumption not found.")
    # One intervention at a time.
    if probe_type == "intervention" and active_intervention_count(db) >= 1:
        raise ValueError("Only one active intervention at a time.")
    # Conversation probes in batches of 5.
    if probe_type == "conversation" and active_conversation_count(db) >= 5:
        raise ValueError("Conversation probes run in batches of 5 — close or decide existing ones first.")
    p = models.Probe(
        assumption_id=assumption_id,
        probe_type=probe_type,
        affordable_loss=affordable_loss,
        kill_criterion=kill_criterion,
        started_at=utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def decide_probe(
    db: Session, probe_id: int, decision: str, result: Optional[str] = None
) -> models.Probe:
    if decision not in PROBE_DECISIONS:
        raise ValueError(f"decision must be one of {PROBE_DECISIONS}")
    p = db.get(models.Probe, probe_id)
    if not p:
        raise ValueError("Probe not found.")
    p.decision = decision
    if result is not None:
        p.result = result
    p.ended_at = utcnow()
    db.commit()
    db.refresh(p)
    return p


def record_capability(
    db: Session, name: str, event_id: int, evidence_id: int, description: Optional[str] = None
) -> models.Capability:
    """Record a capability ONLY from a verified outcome (Event + Evidence).
    Never from prose."""
    event = db.get(models.WorldEvent, event_id)
    if not event:
        raise ValueError("Event not found — capabilities require a real recorded event.")
    evidence = db.get(models.Evidence, evidence_id)
    if not evidence:
        raise ValueError("Evidence not found — capabilities require real recorded evidence.")
    existing = db.query(models.Capability).filter(models.Capability.name == name).first()
    if existing:
        raise ValueError("Capability already recorded.")
    c = models.Capability(
        name=name,
        description=description,
        event_id=event_id,
        evidence_id=evidence_id,
        verified_by="owner",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
