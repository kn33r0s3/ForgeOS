"""Scout + Draft + Approval Queue (2026-10-05).

Candidate registry for potential sellers, built on the six primitives:
- candidates are SubstrateEntity rows (entity_type="scout_candidate")
- observations are Evidence rows (subject_kind="scout_candidate")
- sends are WorldEvent + Action rows

HARD RULE: nothing here sends a message. Drafts are prepared; the OWNER
sends from their own account and marks SENT. No autonomous sending
exists anywhere in this codebase.

Source governance: public pages only. Obey the allowlist, robots.txt,
no login scraping, no private data. Only collect what the business
itself publishes for contact.
"""

import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow

CANDIDATE_ENTITY_TYPE = "scout_candidate"

# Signal types that evidence the slow-reply constraint, with weights.
# Higher weight = stronger evidence that slow replies cost this seller.
SIGNAL_WEIGHTS = {
    "unanswered_inquiry": 3.0,  # public inquiry comment with no reply
    "slow_reply_observed": 2.0,  # reply took > 24h (observed publicly)
    "payment_methods_listed": 0.5,  # business lists payment methods (reachability signal)
    "posting_active": 0.5,  # posted in last 7 days (business is alive)
}


def register_candidate(
    db: Session,
    display_name: str,
    source_url: str,
    public_contact_route: str,
    observed_signals: Optional[dict] = None,
    observed_on: Optional[date] = None,
) -> models.SubstrateEntity:
    """Register a potential seller. Public data only."""
    observed = (observed_on or date.today()).isoformat()
    attributes = {
        "source_url": source_url,
        "public_contact_route": public_contact_route,
        "observed_signals": observed_signals or {},
        "date_observed": observed,
    }
    entity = models.SubstrateEntity(
        entity_type=CANDIDATE_ENTITY_TYPE,
        display_name=display_name,
        attributes=json.dumps(attributes),
        identity_key=f"scout:{source_url}",
        source_system="scout",
        identity_state="candidate",
        created_by="scout",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def record_signal(
    db: Session,
    entity_id: int,
    signal_type: str,
    detail: str,
    confidence: float = 0.7,
) -> models.Evidence:
    """Record one observable signal as Evidence on a candidate."""
    ev = models.Evidence(
        subject_kind="entity",
        subject_id=entity_id,
        claim=f"{signal_type}: {detail}",
        content=detail,
        source="scout",
        provenance="public observation",
        support_level="possible",
        substrate_confidence=confidence,
        recorded_at=utcnow(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def score_candidate(db: Session, entity_id: int) -> Optional[float]:
    """Rank by recorded evidence of the slow-reply constraint.
    No signal = unscored (None)."""
    signals = (
        db.query(models.Evidence)
        .filter(
            models.Evidence.subject_kind == "entity",
            models.Evidence.subject_id == entity_id,
        )
        .all()
    )
    if not signals:
        return None
    score = 0.0
    for s in signals:
        claim = (s.claim or "").split(":")[0]
        weight = SIGNAL_WEIGHTS.get(claim, 0.25)
        score += weight * (s.substrate_confidence or 0.5)
    return round(score, 2)


def rank_candidates(db: Session):
    """All active candidates, scored first, unscored last."""
    entities = (
        db.query(models.SubstrateEntity)
        .filter(
            models.SubstrateEntity.entity_type == CANDIDATE_ENTITY_TYPE,
            models.SubstrateEntity.status == "active",
        )
        .all()
    )
    ranked = [(e, score_candidate(db, e.id)) for e in entities]
    ranked.sort(key=lambda pair: (pair[1] is None, -(pair[1] or 0)))
    return ranked


def is_do_not_contact(db: Session, entity_id: int) -> bool:
    return (
        db.query(models.DoNotContact)
        .filter(models.DoNotContact.candidate_entity_id == entity_id)
        .first()
        is not None
    )


def get_daily_cap(db: Session) -> int:
    cfg = db.query(models.OutreachConfig).first()
    if not cfg:
        cfg = models.OutreachConfig(daily_cap=5)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg.daily_cap


def sends_today(db: Session) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(models.OutreachDraft)
        .filter(
            models.OutreachDraft.status == "SENT",
            models.OutreachDraft.sent_at >= today_start,
        )
        .count()
    )


def check_send_allowed(db: Session, entity_id: int) -> None:
    """Raise ValueError if sending to this candidate is not allowed."""
    if is_do_not_contact(db, entity_id):
        raise ValueError("Do-not-contact list: this candidate must never be contacted.")
    # Never message anyone twice without a reply.
    prior = (
        db.query(models.OutreachDraft)
        .filter(
            models.OutreachDraft.candidate_entity_id == entity_id,
            models.OutreachDraft.status == "SENT",
            models.OutreachDraft.reply_received == False,  # noqa: E712
        )
        .first()
    )
    if prior is not None:
        raise ValueError("Already messaged without a reply — wait for a reply first.")
    if sends_today(db) >= get_daily_cap(db):
        raise ValueError(f"Daily cap reached ({get_daily_cap(db)}/day).")


DRAFT_EN = """Hi {name} — I noticed {fact}. I help online sellers recover sales lost to slow replies, and I'd like to understand how you handle inquiries today. Could we talk for 10 minutes this week? If not, just say so and I won't message again. — Niroj"""

DRAFT_NE = """नमस्ते {name} — मैले {fact} देखेँ। म अनलाइन बिक्रेताहरूलाई ढिलो जवाफका कारण गुमेका बिक्री फिर्ता ल्याउन सहयोग गर्छु, र तपाईं आज सोधपुछ कसरी सम्हाल्नुहुन्छ भनेर बुझ्न चाहन्छु। के यस हप्ता १० मिनेट कुरा गर्न सकिन्छ? यदि चाहनुहुन्न भने भन्नुहोस्, म फेरि सन्देश पठाउने छैन। — निरोज"""


def generate_draft(db: Session, entity_id: int, observed_fact: str) -> models.OutreachDraft:
    """Create a DRAFT (never sent) for a candidate. Owner approves and sends.
    Drafts are cheap hypotheses — send guards apply at mark_sent, not here."""
    entity = db.get(models.SubstrateEntity, entity_id)
    if not entity:
        raise ValueError("Candidate not found.")
    if is_do_not_contact(db, entity_id):
        raise ValueError("Do-not-contact list: this candidate must never be contacted.")
    name = entity.display_name.split()[0]
    draft = models.OutreachDraft(
        candidate_entity_id=entity_id,
        observed_fact=observed_fact,
        message_en=DRAFT_EN.format(name=name, fact=observed_fact),
        message_ne=DRAFT_NE.format(name=name, fact=observed_fact),
        status="DRAFT",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def approve_draft(db: Session, draft_id: int) -> models.OutreachDraft:
    draft = db.get(models.OutreachDraft, draft_id)
    if not draft:
        raise ValueError("Draft not found.")
    if is_do_not_contact(db, draft.candidate_entity_id):
        raise ValueError("Do-not-contact list: this candidate must never be contacted.")
    draft.status = "APPROVED"
    draft.approved_at = utcnow()
    draft.approved_by = "owner"
    db.commit()
    db.refresh(draft)
    return draft


def skip_draft(db: Session, draft_id: int) -> models.OutreachDraft:
    draft = db.get(models.OutreachDraft, draft_id)
    if not draft:
        raise ValueError("Draft not found.")
    draft.status = "SKIPPED"
    db.commit()
    db.refresh(draft)
    return draft


def mark_sent(
    db: Session, draft_id: int, channel: str, sent_by: str = "owner"
) -> models.OutreachDraft:
    """Owner confirms they sent the message from their own account.
    Logs the send as a WorldEvent + Action with authorization.
    This function never sends anything itself."""
    draft = db.get(models.OutreachDraft, draft_id)
    if not draft:
        raise ValueError("Draft not found.")
    if draft.status != "APPROVED":
        raise ValueError("Only APPROVED drafts can be marked sent.")
    check_send_allowed(db, draft.candidate_entity_id)
    draft.status = "SENT"
    draft.sent_at = utcnow()
    draft.sent_by = sent_by
    draft.send_channel = channel
    # Log as Event with authorization.
    event = models.WorldEvent(
        event_type="outreach.sent",
        entity_id=draft.candidate_entity_id,
        payload=json.dumps(
            {
                "draft_id": draft.id,
                "channel": channel,
                "sent_by": sent_by,
                "authorized_by": "owner",
                "message_en": draft.message_en,
            }
        ),
        source="owner",
    )
    db.add(event)
    # Log as Action (requires owner approval type).
    action = models.Action(
        action_type="outreach",
        objective=f"First contact with {draft.candidate_entity_id}: {draft.observed_fact}",
        status="SUCCEEDED",
        policy_result="ALLOW",
        policy_reason="Owner-approved draft, sent by owner from own account.",
        approved_at=utcnow(),
        verification_state="UNVERIFIED",
    )
    db.add(action)
    db.commit()
    db.refresh(draft)
    return draft


def record_reply(db: Session, draft_id: int, summary: str) -> models.OutreachDraft:
    draft = db.get(models.OutreachDraft, draft_id)
    if not draft:
        raise ValueError("Draft not found.")
    draft.reply_received = True
    draft.reply_at = utcnow()
    draft.reply_summary = summary
    event = models.WorldEvent(
        event_type="outreach.reply",
        entity_id=draft.candidate_entity_id,
        payload=json.dumps({"draft_id": draft.id, "summary": summary}),
        source="owner",
    )
    db.add(event)
    db.commit()
    db.refresh(draft)
    return draft


# ---------------------------------------------------------------------
# Experiments registry seed
# ---------------------------------------------------------------------

SEED_EXPERIMENTS = [
    {
        "action": "Reply-visibility sampling",
        "experiment_kind": "OBSERVATION",
        "five_fields": {
            "reality": "Seller inquiry threads are public on Facebook/Instagram; replies (or their absence) are observable without contact.",
            "possibility": "A sample of threads could show how often inquiries go unanswered — grounding the slow-reply constraint in observed data.",
            "constraint": "No sampled data yet; the constraint is still hypothesis from discovery rounds.",
            "constraint_state": "hypothesis",
            "intervention": "Sample 50 public inquiry threads across 10 seller pages; record reply presence and latency.",
            "outcome": "not started",
        },
    },
    {
        "action": "Payment-methods-listed sampling",
        "experiment_kind": "OBSERVATION",
        "five_fields": {
            "reality": "Sellers list payment methods (eSewa, Khalti, COD, bank) publicly on their pages.",
            "possibility": "Mapping listed payment methods shows which sellers can actually receive money — a precondition for recovered-sale revenue.",
            "constraint": "Unknown which sellers have real receiving capability vs. display-only listings.",
            "constraint_state": "hypothesis",
            "intervention": "Record listed payment methods for 30 seller pages from public profiles.",
            "outcome": "not started",
        },
    },
    {
        "action": "Five open conversations",
        "experiment_kind": "CONVERSATION",
        "five_fields": {
            "reality": "No real seller conversations have happened yet (0 recorded).",
            "possibility": "Five open 10-minute conversations would surface the real constraints sellers feel, in their words.",
            "constraint": "No seller named; no contact authorized yet.",
            "constraint_state": "hypothesis",
            "intervention": "Owner holds five 10-minute open-question conversations (guide in docs/FIRST_CONTACT when built); log as evidence.",
            "outcome": "not started",
        },
    },
    {
        "action": "Message A/B (two wordings)",
        "experiment_kind": "CONVERSATION",
        "five_fields": {
            "reality": "No outreach messages have been sent (0).",
            "possibility": "Two honest wordings tested against each other could show which earns replies without deception.",
            "constraint": "Requires owner-approved drafts and owner-sent messages; daily cap applies.",
            "constraint_state": "hypothesis",
            "intervention": "Draft wording A (fact-led) and wording B (question-led); owner approves; owner sends; reply rates compared.",
            "outcome": "not started",
        },
    },
    {
        "action": "Experiment 1: slow-reply recovery",
        "experiment_kind": "INTERVENTION",
        "five_fields": {
            "reality": "Social sellers in Kathmandu receive inquiries across Viber/WhatsApp/Facebook; replies are often slow. No seller has agreed yet.",
            "possibility": "Faster replies might recover lost sales — measurable within one week.",
            "constraint": "The binding constraint is response presence, not demand.",
            "constraint_state": "hypothesis",
            "intervention": "One seller, one week: a human answers inquiries fast; recovered vs lost counted; Hami takes a cut of recovered sales.",
            "outcome": "not started",
        },
    },
]


def seed_registry_experiments(db: Session) -> list:
    """Seed the experiments registry. Idempotent — skips existing."""
    created = []
    for spec in SEED_EXPERIMENTS:
        existing = (
            db.query(models.Experiment)
            .filter(models.Experiment.action == spec["action"])
            .first()
        )
        if existing:
            # Backfill kind + five fields if missing.
            if not existing.experiment_kind:
                existing.experiment_kind = spec["experiment_kind"]
            if not existing.five_fields_json:
                existing.five_fields_json = json.dumps(spec["five_fields"])
            db.commit()
            continue
        exp = models.Experiment(
            action=spec["action"],
            experiment_kind=spec["experiment_kind"],
            five_fields_json=json.dumps(spec["five_fields"]),
            hypothesis=spec["five_fields"]["constraint"],
            status="planned",
            execution_status="proposed",
            data_scope="REAL",
        )
        db.add(exp)
        created.append(exp)
    db.commit()
    return created
