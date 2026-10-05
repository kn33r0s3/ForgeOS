"""Operating Model v4 (2026-10-05). See docs/OPERATING_MODEL.md.

Bet is a PROJECTION over SubstrateEntity (entity_type="bet") — not a new
primitive. All v4 rules enforced here.
"""

import json
import os
from datetime import datetime, timezone
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
    horizon_domain_id: Optional[int] = None,
) -> models.SubstrateEntity:
    if len(live_bets(db)) >= MAX_LIVE_BETS:
        raise ValueError(f"WIP limit: at most {MAX_LIVE_BETS} live Bets.")
    # Parked-domain enforcement: a Bet may not target a parked horizon domain.
    # Explicit reference (not v3's fragile name match).
    if horizon_domain_id is not None:
        domain = db.get(models.SubstrateEntity, horizon_domain_id)
        if not domain or domain.entity_type != HORIZON_DOMAIN_ENTITY_TYPE:
            raise ValueError("Horizon domain not found.")
        if is_domain_parked(db, horizon_domain_id):
            name = _horizon_attributes(domain).get("name")
            raise ValueError(f"Domain '{name}' is parked on the Horizon register.")
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
        "horizon_domain_id": horizon_domain_id,
    }
    # Canonical substrate write: validates the registered type, validates
    # attributes, sets candidate identity, and emits entity_created.
    from app.services import world_graph  # local import to avoid cycles

    bet = world_graph.create_entity(
        db,
        entity_type=BET_ENTITY_TYPE,
        display_name=f"Bet: {claim[:80]}",
        attributes=attributes,
        created_by="owner",
    )
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
        # Canonical archival: never assign archived status directly; the
        # substrate contract requires archive_entity() with actor + rationale.
        from app.services import world_graph  # local import to avoid cycles

        rationale = (
            notes
            or attrs.get("kill_criterion")
            or "Bet killed by owner decision"
        )
        world_graph.archive_entity(db, bet, actor="owner", rationale=rationale)
    db.commit()
    db.refresh(bet)
    return bet


# ---------------------------------------------------------------------
# Assumptions as projections over SubstrateEntity
# ---------------------------------------------------------------------
# Recovered from v2 5a3a484 (operating_model.py). v2's dedicated Assumption
# table is obsolete and NOT restored. An assumption is a SubstrateEntity with
# entity_type="assumption" — the same projection pattern as Bet and Probe.
# Status values (untested|supported|contradicted) are the projection's own
# decision field, not a new primitive. Supported requires linked evidence;
# links are references, never proof by themselves (proof stays governed by
# set_proof_level()).

ASSUMPTION_ENTITY_TYPE = "assumption"
ASSUMPTION_STATUSES = ("untested", "supported", "contradicted")

# The six load-bearing assumptions, preserved verbatim from v2. No later
# canonical Hami source corrects any statement (checked docs/ORIGIN.md,
# docs/OPERATING_MODEL.md 2026-10-05).
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


def _assumption_attributes(a: models.SubstrateEntity) -> dict:
    return json.loads(a.attributes or "{}")


def list_assumptions(db: Session) -> list:
    return (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == ASSUMPTION_ENTITY_TYPE)
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )


def seed_assumptions(db: Session) -> list:
    """Seed the six assumptions. Idempotent: skips statements already present."""
    from app.services import world_graph  # local import to avoid cycles

    existing_statements = {
        _assumption_attributes(a).get("statement") for a in list_assumptions(db)
    }
    created = []
    for spec in SEED_ASSUMPTIONS:
        if spec["statement"] in existing_statements:
            continue
        a = world_graph.create_entity(
            db,
            entity_type=ASSUMPTION_ENTITY_TYPE,
            display_name=f"Assumption: {spec['statement'][:60]}",
            attributes={
                "statement": spec["statement"],
                "status": "untested",
                "deal_killer": spec["deal_killer"],
                "cost_to_test": spec["cost_to_test"],
                "cheapest_test": spec["cheapest_test"],
                "milestone": spec["milestone"],
                "source_note": spec["source_note"],
                "evidence_links": [],
            },
            created_by="owner",
        )
        created.append(a)
    db.commit()
    return created


def rank_assumptions(db: Session) -> list:
    """Deal-killer first, then cheapest to test. Cost ordering is heuristic:
    Rs 0 < research < 1 week. Deterministic tie-break on entity id."""

    def cost_rank(attrs: dict) -> int:
        cost = (attrs.get("cost_to_test") or "").lower()
        if "rs 0" in cost:
            return 0
        if "research" in cost:
            return 1
        return 2

    assumptions = list_assumptions(db)
    assumptions.sort(
        key=lambda a: (
            not _assumption_attributes(a).get("deal_killer"),
            cost_rank(_assumption_attributes(a)),
            a.id,
        )
    )
    return assumptions


def _get_assumption(db: Session, assumption_id: int) -> models.SubstrateEntity:
    a = db.get(models.SubstrateEntity, assumption_id)
    if not a or a.entity_type != ASSUMPTION_ENTITY_TYPE:
        raise ValueError("Assumption not found.")
    return a


def set_assumption_status(
    db: Session, assumption_id: int, status: str
) -> models.SubstrateEntity:
    if status not in ASSUMPTION_STATUSES:
        raise ValueError(f"status must be one of {ASSUMPTION_STATUSES}")
    a = _get_assumption(db, assumption_id)
    attrs = _assumption_attributes(a)
    if status == "supported" and not attrs.get("evidence_links"):
        raise ValueError(
            "Cannot mark 'supported' without linked evidence. "
            "Attach evidence references first."
        )
    attrs["status"] = status
    a.attributes = json.dumps(attrs)
    db.commit()
    db.refresh(a)
    return a


def add_evidence_link(
    db: Session, assumption_id: int, evidence_ref: str
) -> models.SubstrateEntity:
    """Attach an evidence reference to an assumption. Idempotent.
    The link is a reference only — it does not set any proof level."""
    a = _get_assumption(db, assumption_id)
    attrs = _assumption_attributes(a)
    links = attrs.get("evidence_links") or []
    if evidence_ref not in links:
        links.append(evidence_ref)
    attrs["evidence_links"] = links
    a.attributes = json.dumps(attrs)
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------------
# Orientation as a projection over SubstrateEntity
# ---------------------------------------------------------------------
# Recovered from v2 5a3a484 (operating_model.py). v2's dedicated Orientation
# and OrientationBelief tables are obsolete and NOT restored. An orientation
# is a SubstrateEntity with entity_type="orientation"; beliefs are embedded
# as structured attributes. Versions increase monotonically from the latest
# recorded orientation — never inferred from timestamps.

ORIENTATION_ENTITY_TYPE = "orientation"


def _orientation_attributes(o: models.SubstrateEntity) -> dict:
    return json.loads(o.attributes or "{}")


def list_orientations(db: Session) -> list:
    return (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == ORIENTATION_ENTITY_TYPE)
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )


def record_orientation(
    db: Session,
    observer_who: str,
    observer_from_where: str,
    means: str,
    local_knowledge: str,
    beliefs: list,
) -> models.SubstrateEntity:
    """Record a new versioned orientation. Beliefs are dicts with
    belief_text and assumption_id (nullable). Assumption references must
    resolve to an existing assumption projection."""
    from app.services import world_graph  # local import to avoid cycles

    latest = list_orientations(db)
    version = (
        max(_orientation_attributes(o).get("version", 0) for o in latest) + 1
        if latest
        else 1
    )
    normalized_beliefs = []
    for b in beliefs:
        belief_text = b.get("belief_text") if isinstance(b, dict) else None
        assumption_id = b.get("assumption_id") if isinstance(b, dict) else None
        if not belief_text:
            raise ValueError("Each belief requires belief_text.")
        if assumption_id is not None:
            assumption = db.get(models.SubstrateEntity, assumption_id)
            if not assumption or assumption.entity_type != ASSUMPTION_ENTITY_TYPE:
                raise ValueError(f"Assumption {assumption_id} not found.")
        normalized_beliefs.append(
            {"belief_text": belief_text, "assumption_id": assumption_id}
        )
    o = world_graph.create_entity(
        db,
        entity_type=ORIENTATION_ENTITY_TYPE,
        display_name=f"Orientation v{version}: {observer_who[:60]}",
        attributes={
            "version": version,
            "observer_who": observer_who,
            "observer_from_where": observer_from_where,
            "means": means,
            "local_knowledge": local_knowledge,
            "beliefs": normalized_beliefs,
        },
        created_by="owner",
    )
    db.commit()
    db.refresh(o)
    return o


# ---------------------------------------------------------------------
# Constraint diagnosis as a projection over SubstrateEntity
# ---------------------------------------------------------------------
# Recovered from v2 5a3a484 (operating_model.py). v2's dedicated
# ConstraintDiagnosis and DiagnosisNode tables are obsolete and NOT restored.
# A diagnosis is a SubstrateEntity with entity_type="constraint_diagnosis";
# nodes are embedded as structured attributes. Exactly one node must be the
# most_binding_hypothesis — a hypothesis, not an established fact. Node
# evidence is a reference/context field, never a proof promotion.

DIAGNOSIS_ENTITY_TYPE = "constraint_diagnosis"
BINDING_STATUSES = (
    "most_binding_hypothesis",
    "not_binding_now",
    "may_bind_later",
)


def _diagnosis_attributes(d: models.SubstrateEntity) -> dict:
    return json.loads(d.attributes or "{}")


def list_diagnoses(db: Session) -> list:
    return (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == DIAGNOSIS_ENTITY_TYPE)
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )


def diagnose_constraints(
    db: Session, situation: str, nodes: list
) -> models.SubstrateEntity:
    """Record a constraint diagnosis. Nodes are dicts with node_text,
    evidence (reference/context only), and binding_status. Exactly one node
    must be 'most_binding_hypothesis'."""
    from app.services import world_graph  # local import to avoid cycles

    normalized_nodes = []
    for n in nodes:
        node_text = n.get("node_text") if isinstance(n, dict) else None
        evidence = n.get("evidence") if isinstance(n, dict) else ""
        binding_status = n.get("binding_status") if isinstance(n, dict) else None
        if not node_text:
            raise ValueError("Each node requires node_text.")
        if binding_status not in BINDING_STATUSES:
            raise ValueError(f"binding_status must be one of {BINDING_STATUSES}")
        normalized_nodes.append(
            {
                "node_text": node_text,
                "evidence": evidence or "",
                "binding_status": binding_status,
            }
        )
    binding = [
        n for n in normalized_nodes if n["binding_status"] == "most_binding_hypothesis"
    ]
    if len(binding) != 1:
        raise ValueError(
            f"Exactly one node must be 'most_binding_hypothesis', got {len(binding)}."
        )
    d = world_graph.create_entity(
        db,
        entity_type=DIAGNOSIS_ENTITY_TYPE,
        display_name=f"Diagnosis: {situation[:60]}",
        attributes={"situation": situation, "nodes": normalized_nodes},
        created_by="owner",
    )
    db.commit()
    db.refresh(d)
    return d


# ---------------------------------------------------------------------
# Sensor circle (recovered from v3 a5ed491)
# ---------------------------------------------------------------------
# Uses the existing models.SensorContributor — no duplicate infrastructure.
# Observations are Evidence rows with contributor provenance; proof stays
# governed by set_proof_level() (sensor observations start low, never
# promoted by this path).

def add_contributor(
    db: Session, name: str, notes: Optional[str] = None
) -> models.SensorContributor:
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
        source_type="sensor",
        provenance="consent-based contributor observation",
        recorded_at=utcnow(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    # Canonical proof path: sensor observations start low (L1). They are
    # never promoted by this path — only set_proof_level() with real
    # verification can raise them.
    return set_proof_level(db, ev.id, 1, source_type="sensor")


# ---------------------------------------------------------------------
# Horizon register as a projection over SubstrateEntity
# ---------------------------------------------------------------------
# Recovered from v3 a5ed491. v3's dedicated HorizonDomain table is obsolete
# and NOT restored. A horizon domain is a SubstrateEntity with
# entity_type="horizon_domain". Parked domains stay visible; unparking
# changes state without deleting history. A parked domain cannot become a
# new live Bet (enforced via explicit horizon_domain_id reference on Bet).

HORIZON_DOMAIN_ENTITY_TYPE = "horizon_domain"


def _horizon_attributes(h: models.SubstrateEntity) -> dict:
    return json.loads(h.attributes or "{}")


def list_horizon_domains(db: Session) -> list:
    return (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == HORIZON_DOMAIN_ENTITY_TYPE)
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )


def _get_horizon_domain(db: Session, domain_id: int) -> models.SubstrateEntity:
    h = db.get(models.SubstrateEntity, domain_id)
    if not h or h.entity_type != HORIZON_DOMAIN_ENTITY_TYPE:
        raise ValueError("Horizon domain not found.")
    return h


def is_domain_parked(db: Session, domain_id: int) -> bool:
    h = _get_horizon_domain(db, domain_id)
    return _horizon_attributes(h).get("status") == "parked"


def park_domain(db: Session, name: str, reason: str) -> models.SubstrateEntity:
    from app.services import world_graph  # local import to avoid cycles

    for h in list_horizon_domains(db):
        attrs = _horizon_attributes(h)
        if attrs.get("name") == name and attrs.get("status") == "parked":
            raise ValueError(f"Domain '{name}' is already parked.")
    h = world_graph.create_entity(
        db,
        entity_type=HORIZON_DOMAIN_ENTITY_TYPE,
        display_name=f"Horizon: {name[:60]}",
        attributes={
            "name": name,
            "reason_parked": reason,
            "status": "parked",
            "parked_at": utcnow().isoformat(),
            "unparked_at": None,
        },
        created_by="owner",
    )
    db.commit()
    db.refresh(h)
    return h


def unpark_domain(db: Session, domain_id: int) -> models.SubstrateEntity:
    h = _get_horizon_domain(db, domain_id)
    attrs = _horizon_attributes(h)
    attrs["status"] = "unparked"
    attrs["unparked_at"] = utcnow().isoformat()
    h.attributes = json.dumps(attrs)
    db.commit()
    db.refresh(h)
    return h


# ---------------------------------------------------------------------
# Probes as projections over SubstrateEntity
# ---------------------------------------------------------------------
# Recovered from v2 5a3a484 (operating_model.py). v2's dedicated Probe and
# Assumption tables are obsolete and NOT restored. A probe is a
# SubstrateEntity with entity_type="probe" — the same projection pattern as
# Bet. Assumption references resolve to SubstrateEntity rows with
# entity_type="assumption" (seeded by the assumption projection).
#
# A probe is an operational experiment record. Recording one does NOT mean
# the probe actually happened. Probes are not a seventh primitive.

PROBE_ENTITY_TYPE = "probe"
PROBE_TYPES = ("observation", "conversation", "intervention")
PROBE_DECISIONS = ("AMPLIFY", "DAMPEN", "KILL")
MAX_ACTIVE_INTERVENTIONS = 1
MAX_ACTIVE_CONVERSATIONS = 5


def _probe_attributes(probe: models.SubstrateEntity) -> dict:
    return json.loads(probe.attributes or "{}")


def active_probes(db: Session, probe_type: Optional[str] = None) -> list:
    probes = (
        db.query(models.SubstrateEntity)
        .filter(
            models.SubstrateEntity.entity_type == PROBE_ENTITY_TYPE,
            models.SubstrateEntity.status == "active",
        )
        .all()
    )
    active = [p for p in probes if _probe_attributes(p).get("status") == "active"]
    if probe_type:
        active = [
            p for p in active if _probe_attributes(p).get("probe_type") == probe_type
        ]
    return active


def record_probe(
    db: Session,
    assumption_id: int,
    probe_type: str,
    affordable_loss: str,
    kill_criterion: str,
) -> models.SubstrateEntity:
    if probe_type not in PROBE_TYPES:
        raise ValueError(f"probe_type must be one of {PROBE_TYPES}")
    if not affordable_loss:
        raise ValueError("affordable_loss is required.")
    if not kill_criterion:
        raise ValueError("kill_criterion is required.")
    assumption = db.get(models.SubstrateEntity, assumption_id)
    if not assumption or assumption.entity_type != ASSUMPTION_ENTITY_TYPE:
        raise ValueError("Assumption not found.")
    if probe_type == "intervention" and (
        len(active_probes(db, "intervention")) >= MAX_ACTIVE_INTERVENTIONS
    ):
        raise ValueError("Only one active intervention at a time.")
    if probe_type == "conversation" and (
        len(active_probes(db, "conversation")) >= MAX_ACTIVE_CONVERSATIONS
    ):
        raise ValueError(
            "Conversation probes run in batches of 5 — "
            "close or decide existing ones first."
        )
    attributes = {
        "probe_type": probe_type,
        "affordable_loss": affordable_loss,
        "kill_criterion": kill_criterion,
        "assumption_id": assumption_id,
        "status": "active",
    }
    # Canonical substrate write: validates the registered type, validates
    # attributes, and emits the entity_created event. Never db.add() raw.
    from app.services import world_graph  # local import to avoid cycles

    probe = world_graph.create_entity(
        db,
        entity_type=PROBE_ENTITY_TYPE,
        display_name=f"Probe ({probe_type}): {assumption.display_name[:60]}",
        attributes=attributes,
        created_by="owner",
    )
    db.commit()
    db.refresh(probe)
    return probe


def decide_probe(
    db: Session, probe_id: int, decision: str, result: Optional[str] = None
) -> models.SubstrateEntity:
    if decision not in PROBE_DECISIONS:
        raise ValueError(f"decision must be one of {PROBE_DECISIONS}")
    probe = db.get(models.SubstrateEntity, probe_id)
    if not probe or probe.entity_type != PROBE_ENTITY_TYPE:
        raise ValueError("Probe not found.")
    attrs = _probe_attributes(probe)
    attrs["status"] = "decided"
    attrs["decision"] = decision
    if result is not None:
        attrs["result"] = result
    attrs["decided_at"] = utcnow().isoformat()
    probe.attributes = json.dumps(attrs)
    db.commit()
    db.refresh(probe)
    return probe


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
# Proof guards (recovered from v3 a5ed491; adapted to v4 semantics)
#
# v4's L0-L7 ladder and external-anchoring rules remain authoritative.
# These guards enforce wording/discipline on top of the ladder — they do
# not redefine it. set_proof_level() above is unchanged in responsibility.
# ---------------------------------------------------------------------

def check_found_wording(db: Session, evidence_id: int) -> None:
    """Public 'found' wording requires proof >= L5.

    Call before publishing a 'found' claim about this evidence.
    Raises ValueError if the evidence is below L5.
    """
    ev = db.get(models.Evidence, evidence_id)
    if not ev:
        raise ValueError("Evidence not found.")
    if (ev.proof_level or 0) < 5:
        raise ValueError(
            f"Public 'found' wording requires proof level >= L5; "
            f"evidence #{evidence_id} is L{ev.proof_level}."
        )


def check_plan_change(db: Session, evidence_ids: list) -> None:
    """Plan/priority changes require supporting evidence >= L3.

    Takes real Evidence IDs — never assumption IDs, never bet IDs.
    Raises ValueError if any listed evidence is missing or below L3.

    INTEGRATION BOUNDARY: no existing v4 caller represents a plan/priority
    change (decide_bet() takes no evidence input), so this is a helper for
    future wiring, not wired into any current path.
    """
    for eid in evidence_ids:
        ev = db.get(models.Evidence, eid)
        if not ev:
            raise ValueError(f"Evidence #{eid} not found.")
        if (ev.proof_level or 0) < 3:
            raise ValueError(
                f"Plan/priority changes require proof >= L3; "
                f"evidence #{eid} is L{ev.proof_level}."
            )


def flag_proof_violations(db: Session) -> list:
    """Heuristic audit: evidence whose claim wording asserts a 'found'
    finding while sitting below L5.

    This is an audit helper, not authoritative publication validation:
    there is no proof-gated publication path in v4 (public_feed.py does not
    filter by proof level, and Evidence has no public-wording field), so a
    'found' in claim text is treated as a candidate violation for owner
    review — not as proof of publication.
    Returns [{"evidence_id", "proof_level", "claim_excerpt"}].
    """
    violations = []
    for ev in db.query(models.Evidence).all():
        claim = ev.claim or ""
        if "found" in claim.lower() and (ev.proof_level or 0) < 5:
            violations.append(
                {
                    "evidence_id": ev.id,
                    "proof_level": ev.proof_level,
                    "claim_excerpt": claim[:120],
                }
            )
    return violations


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
        if not latest:
            silent.append(c.name)
            continue
        recorded = latest.recorded_at
        if recorded is not None and recorded.tzinfo is None:
            # SQLite returns naive datetimes; treat as UTC.
            recorded = recorded.replace(tzinfo=timezone.utc)
        if recorded is None or recorded < cutoff:
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


# ---------------------------------------------------------------------
# Gate enforcement (recovered from v3 a5ed491)
#
# Kill criterion must exist BEFORE a gate result can be recorded, and the
# criterion cannot be silently changed once a result exists. The v4 Gate
# model docstring already claims this; these functions enforce it.
# ---------------------------------------------------------------------

GATE_DAYS = (14, 30, 60, 90)


def upsert_gate(
    db: Session, day: int, title: str, kill_criterion: Optional[str] = None
) -> models.Gate:
    from app.models import Gate  # local import to avoid cycles

    if day not in GATE_DAYS:
        raise ValueError(f"Gate day must be one of {GATE_DAYS}")
    gate = db.query(Gate).filter(Gate.day == day).first()
    if not gate:
        gate = Gate(day=day, title=title)
        db.add(gate)
    else:
        gate.title = title
    if kill_criterion is not None:
        if gate.result is not None:
            raise ValueError(
                "Kill criterion cannot be changed after a result is recorded."
            )
        gate.kill_criterion = kill_criterion
    gate.updated_at = utcnow()
    db.commit()
    db.refresh(gate)
    return gate


def record_gate_result(db: Session, day: int, result: str) -> models.Gate:
    from app.models import Gate  # local import to avoid cycles

    gate = db.query(Gate).filter(Gate.day == day).first()
    if not gate:
        raise ValueError("Gate not found.")
    if not gate.kill_criterion:
        raise ValueError("Kill criterion must be stored BEFORE any result.")
    gate.result = result
    gate.decided_at = utcnow()
    db.commit()
    db.refresh(gate)
    return gate
