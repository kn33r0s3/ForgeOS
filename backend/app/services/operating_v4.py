"""Operating Model v4 (2026-10-05). See docs/OPERATING_MODEL.md.

Bet is a PROJECTION over SubstrateEntity (entity_type="bet") — not a new
primitive. All v4 rules enforced here.
"""

import json
import logging
import os
from functools import cmp_to_key
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from app import evidence_source, models
from app.models import utcnow

BET_ENTITY_TYPE = "bet"
BET_STATUSES = ("candidate", "live", "paused", "amplified", "dampened", "killed")
MAX_LIVE_BETS = 3
STARVED_DAYS = 14
CONTACT_PRIORITY_DAYS = 2

ASSESSMENT_LEVELS = ("high", "medium", "low", "unassessed")
ASSESSMENT_PROVENANCE = (
    "observed",
    "computed",
    "owner-confirmed",
    "model-proposed",
    "unassessed",
)
SELECTION_DIMENSIONS = (
    "stake",
    "uncertainty",
    "evidence_potential",
    "capability_gain",
    "transferability",
    "upside",
    "cost",
    "time",
    "reversibility",
    "harm",
)
# Two experiment lanes on the SAME candidate/Bet projection. Discovery is a
# classification, not a new table, primitive, or queue.
CANDIDATE_LANES = ("known_unknown", "unknown_unknown_discovery")
# Grounded origins for discovery candidates. A source that cannot be grounded
# in existing repository data is reported UNAVAILABLE, never fabricated.
DISCOVERY_SOURCES = (
    "map_gap",
    "evidence_contradiction",
    "outcome_anomaly",
    "capability_gap",
    "horizon_escape",
)
WATCH_HORIZON_NAME = "__current_watch_horizon__"

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


# Offers are projections stored on their existing Bet entity. They are not
# rows in a new table and do not extend Hami's six canonical primitives.
OFFER_STATUSES = ("draft", "owner-approved", "live", "killed")
OFFER_LEGAL_ACTION_OBJECTIVE = (
    "Lawyer read: Nepal personal-data handling and consent; online-business registration"
)
OFFER_LEGAL_ACTION_KIND = "hami_offer_legal_read"
OFFER_LEGAL_TOPICS = [
    "Personal-data handling and consent in Nepal, including what may be collected, retained, shared, and deleted.",
    "Online-business registration and any registration, tax, licensing, or disclosure duties that apply to the actual offer.",
]
OFFER_SEEDS = [
    {
        "id": "how-you-decided",
        "title": "How you decided",
        "linked_bet_code": "C",
        "audience": "CONTRIBUTOR",
        "one_sentence_offer": "Share how you decided on one recent purchase and receive a short, anonymized map of the factors you say mattered.",
        "they_give": "One voluntary first-person account of a recent decision, about 10 minutes; no screenshots or private chat quotes.",
        "they_get": "A short summary for review, with personal identifiers removed before any public learning is shared.",
        "cost_to_hami": {
            "cash_estimate_npr": 0,
            "owner_time_minutes_estimate": 20,
            "assumptions": "Estimate includes consent, a short conversation, preparing the summary, and checking that it is de-identified. Actual owner time must be recorded during the test.",
        },
        "consent_text": {
            "en": "Taking part is voluntary. You may skip any question or stop at any time. Please share only your own experience, not another person's private messages or identifying details. Hami will use your account to prepare a short summary; we will not publish your name or identifying details.",
            "ne": "सहभागिता स्वेच्छिक हो। तपाईंले कुनै प्रश्न छोड्न वा जुनसुकै बेला रोक्न सक्नुहुन्छ। आफ्नो अनुभव मात्र साझा गर्नुहोस्; अरूको निजी सन्देश वा पहिचान खुल्ने विवरण नदिनुहोस्। हामिले छोटो सारांश बनाउन तपाईंको विवरण प्रयोग गर्नेछ र तपाईंको नाम वा पहिचान खुल्ने विवरण सार्वजनिक गर्ने छैन।",
        },
        "terms_text": {
            "en": "This is an exploratory research exchange, not professional, financial, or purchasing advice. There is no fee and no promised result. You can decline or withdraw before the summary is anonymized. Hami will not claim your account represents other buyers.",
            "ne": "यो प्रारम्भिक अनुसन्धानका लागि गरिएको आदानप्रदान हो; व्यावसायिक, वित्तीय वा खरिदसम्बन्धी सल्लाह होइन। कुनै शुल्क छैन र निश्चित नतिजाको वाचा छैन। सारांशबाट पहिचान हटाइनुअघि तपाईं सहभागी नहुने वा सहभागिता फिर्ता लिन सक्नुहुन्छ। हामिले तपाईंको अनुभवलाई सबै खरिदकर्ताको प्रतिनिधि प्रमाण मान्ने छैन।",
        },
        "test": {
            "question": "Can a first-person decision account reveal a checkable step that existing seller-visible records miss?",
            "method": "Invite up to five consented contributors; record the decision sequence and what evidence they personally checked; compare each claim to what can be independently checked without retaining private messages.",
            "sample_size": "Up to 5 accounts; exploratory only",
            "success_signal": "At least one specific, checkable decision factor not represented in the existing record, with provenance and uncertainty retained.",
        },
        "kill_criterion": "Stop if informed consent is unclear, participants cannot share without disclosing another person's private data, or five accounts yield no specific checkable decision factor.",
        "depends_on": [],
    },
    {
        "id": "lost-sales-check",
        "title": "Lost-sales check",
        "linked_bet_code": "A",
        "audience": "SELLER",
        "one_sentence_offer": "Share a small, consented count of recent inquiries and get a simple reply-and-outcome audit without labelling unanswered inquiries as lost revenue.",
        "they_give": "A redacted count or owner-prepared summary of recent inquiries, replies, and known outcomes; no customer names, screenshots, or private message exports.",
        "they_get": "A short audit separating observed counts, unknown outcomes, and hypotheses for a next test.",
        "cost_to_hami": {
            "cash_estimate_npr": 0,
            "owner_time_minutes_estimate": 45,
            "assumptions": "Estimate includes agreeing the scope, reviewing a small redacted sample, and returning the audit. Actual owner time must be recorded.",
        },
        "consent_text": {
            "en": "You decide what to share and may stop at any time. Share only information you are permitted to share and remove buyer names, phone numbers, handles, message contents, and other identifying details. Hami will not contact your buyers.",
            "ne": "के साझा गर्ने भन्ने निर्णय तपाईंको हो र तपाईं जुनसुकै बेला रोक्न सक्नुहुन्छ। साझा गर्न अनुमति भएको जानकारी मात्र दिनुहोस् र खरिदकर्ताका नाम, फोन नम्बर, ह्यान्डल, सन्देशको सामग्री तथा पहिचान खुल्ने विवरण हटाउनुहोस्। हामिले तपाईंका खरिदकर्तालाई सम्पर्क गर्ने छैन।",
        },
        "terms_text": {
            "en": "This is a bounded diagnostic, not a promise to recover sales. Unanswered inquiries are not counted as lost sales unless an actual lost outcome is evidenced. No software installation, buyer contact, payment, or operational change is included in this check.",
            "ne": "यो सीमित जाँच हो; बिक्री फर्काउने वाचा होइन। वास्तविक बिक्री गुमेको प्रमाण नभएसम्म जवाफ नआएका सोधपुछलाई गुमेको बिक्री मानिने छैन। यस जाँचमा सफ्टवेयर जडान, खरिदकर्तासँग सम्पर्क, भुक्तानी वा सञ्चालन परिवर्तन समावेश छैन।",
        },
        "test": {
            "question": "Do the seller's records show an observable response/presence constraint, or are outcomes mostly unknown?",
            "method": "Review one agreed, redacted sample; count inquiries, replies, response latency where available, and known paid outcomes separately. Keep estimates separate from actual outcomes.",
            "sample_size": "One small seller-approved sample",
            "success_signal": "A reproducible baseline with known denominators and explicit unknowns, sufficient to decide whether any further test is justified.",
        },
        "kill_criterion": "Stop if consent or lawful authority to share is unclear, records cannot be safely redacted, or the sample cannot support a reproducible count.",
        "depends_on": [],
    },
    {
        "id": "buyer-voice-brief",
        "title": "Buyer-voice brief",
        "linked_bet_code": "C",
        "audience": "BUYER",
        "one_sentence_offer": "Describe your own recent purchase decision and receive a short summary of the checks, doubts, and factors you report as decisive.",
        "they_give": "One consented first-person account of a purchase decision, using their own words without private chat transcripts or other people's identifying details.",
        "they_get": "A concise, de-identified brief separating what the buyer reported from what is independently supported.",
        "cost_to_hami": {
            "cash_estimate_npr": 0,
            "owner_time_minutes_estimate": 25,
            "assumptions": "Estimate includes consent, recording structured notes, de-identifying, and preparing the brief. Actual owner time must be recorded.",
        },
        "consent_text": {
            "en": "Participation is voluntary. Share only your own experience and do not provide private messages, screenshots, account credentials, or another person's identifying information. You may stop at any time before your account is anonymized.",
            "ne": "सहभागिता स्वेच्छिक हो। आफ्नो अनुभव मात्र साझा गर्नुहोस्; निजी सन्देश, स्क्रिनसट, खाताको पासवर्ड वा अरूको पहिचान खुल्ने जानकारी नदिनुहोस्। तपाईंको विवरणबाट पहिचान हटाइनुअघि जुनसुकै बेला रोक्न सक्नुहुन्छ।",
        },
        "terms_text": {
            "en": "The brief is a research summary, not a recommendation to buy from any particular seller and not a guarantee of safety or quality. Hami will not present one account as representative of all buyers.",
            "ne": "यो संक्षिप्त विवरण अनुसन्धानका लागि हो; कुनै निश्चित विक्रेताबाट किन्न सिफारिस वा सुरक्षा/गुणस्तरको ग्यारेन्टी होइन। हामिले एउटा अनुभवलाई सबै खरिदकर्ताको प्रतिनिधि मानेर प्रस्तुत गर्ने छैन।",
        },
        "test": {
            "question": "Which checks and concerns do buyers themselves say changed a purchase decision?",
            "method": "Collect consented first-person accounts; code reported decision factors separately from independently checkable facts; note contradictions and missing evidence.",
            "sample_size": "One account per participant; exploratory until the 10-account threshold",
            "success_signal": "Decision factors can be categorized without exposing identities or turning self-report into verified fact.",
        },
        "kill_criterion": "Stop if consent is missing, the account requires private third-party chat content, or reported factors cannot be separated from unsupported inference.",
        "depends_on": [],
    },
    {
        "id": "rescue-week",
        "title": "Rescue week",
        "linked_bet_code": "A",
        "audience": "SELLER",
        "one_sentence_offer": "For one consenting seller, run a bounded human-led one-week response test and report observed inquiry and paid-outcome counts without promising recovered sales.",
        "they_give": "Written agreement to a defined scope, a lawful and consented baseline, and only the minimum de-identified records needed to measure actual outcomes.",
        "they_get": "A dated before/after report separating observed facts, unknowns, costs, and any counterparty-confirmed paid outcomes.",
        "cost_to_hami": {
            "cash_estimate_npr": 0,
            "owner_time_minutes_estimate": 420,
            "assumptions": "Planning estimate: up to 7 owner hours across setup, daily monitoring, and close-out. No software or cash spend assumed; record actual hours and stop if the cap is exceeded.",
        },
        "consent_text": {
            "en": "No activity starts until a lawyer has reviewed the relevant data/consent and registration questions and both parties agree to the written scope. Buyer data is minimized; Hami will not claim a sale was recovered without evidence of an actual paid outcome and a defensible comparison.",
            "ne": "सम्बन्धित डेटा/सहमति र दर्ताका विषयमा वकिलले समीक्षा नगरेसम्म तथा दुवै पक्षले लिखित दायरामा सहमति नदिएसम्म काम सुरु हुँदैन। खरिदकर्ताको डेटा न्यूनतम राखिनेछ; वास्तविक भुक्तानीको प्रमाण र उचित तुलना नभएसम्म बिक्री फर्किएको दाबी गरिने छैन।",
        },
        "terms_text": {
            "en": "A one-week observational/operational test with an agreed time cap; no guaranteed sales, recovery, or revenue. No messages are sent by agents. The owner conducts and records any authorized contact. Stop immediately if consent is withdrawn, legal permission is unclear, data handling is unsafe, or the cost cap is reached.",
            "ne": "सहमत समयसीमाभित्र एक हप्ताको अवलोकन/सञ्चालन परीक्षण हुनेछ; बिक्री, बिक्री पुनःप्राप्ति वा आम्दानीको ग्यारेन्टी छैन। एजेन्टले सन्देश पठाउँदैन। अनुमति प्राप्त सम्पर्क मालिकले स्वयं गर्छ र अभिलेख राख्छ। सहमति फिर्ता भए, कानुनी अनुमति अस्पष्ट भए, डेटा सुरक्षित राख्न नसकिए वा लागत सीमा पुगेमा तुरुन्त रोक्नुहोस्।",
        },
        "test": {
            "question": "Does a bounded response intervention change measured response and paid-outcome rates for this consenting seller?",
            "method": "Only after approval gates pass: define a baseline and denominator in advance; log each authorized contact as Event + Action; measure response and actual paid outcomes separately; record owner time and all costs. Do not infer recovered sales from unanswered inquiries.",
            "sample_size": "One seller, seven days, only after prerequisites are verified",
            "success_signal": "Complete auditable baseline and outcome records; a positive result is not assumed and must meet the pre-agreed comparison rule.",
        },
        "kill_criterion": "Do not start until lawyer-read status is recorded and relevant consented real seller evidence exists; kill if consent is withdrawn, actual outcomes cannot be verified, cost/time cap is exceeded, or evidence disconfirms the intervention.",
        "depends_on": ["evidence:real-consented-firsthand-seller-record"],
    },
    {
        "id": "before-you-pay-card",
        "title": "Before you pay card",
        "linked_bet_code": "B",
        "audience": "BUYER",
        "one_sentence_offer": "Use a concise pre-payment check card to review the seller, terms, and payment confirmation steps before deciding whether to pay.",
        "they_give": "Nothing beyond choosing to read the checklist; any feedback is optional and must be consented.",
        "they_get": "A plain-language checklist of practical checks and uncertainty signals, not a guarantee that a seller or payment is safe.",
        "cost_to_hami": {
            "cash_estimate_npr": 0,
            "owner_time_minutes_estimate": 180,
            "assumptions": "Planning estimate for reviewing ten consented purchase accounts and drafting a checklist. Actual owner time and any external costs must be recorded.",
        },
        "consent_text": {
            "en": "Reading the checklist does not require sharing personal data. Do not send Hami your payment PIN, password, OTP, full receipt, card details, or private messages. Optional feedback is voluntary.",
            "ne": "यो सूची पढ्न व्यक्तिगत डेटा साझा गर्नु पर्दैन। हामिलाई भुक्तानी PIN, पासवर्ड, OTP, पूरा रसिद, कार्ड विवरण वा निजी सन्देश नपठाउनुहोस्। वैकल्पिक प्रतिक्रिया स्वेच्छिक हो।",
        },
        "terms_text": {
            "en": "The card is informational and does not verify a merchant, payment, product, or transaction. Check the official payment app/account yourself and never rely on screenshots alone. This offer stays unavailable until at least ten consented purchase-journey accounts exist and the owner approves the public copy.",
            "ne": "यो कार्ड जानकारीका लागि हो; यसले व्यापारी, भुक्तानी, सामान वा कारोबार प्रमाणित गर्दैन। आधिकारिक भुक्तानी एप/खाता आफैं जाँच्नुहोस् र स्क्रिनसटलाई मात्र आधार नमान्नुहोस्। कम्तीमा दस सहमतिप्राप्त खरिद-अनुभव अभिलेख नभएसम्म र मालिकले सार्वजनिक सामग्री स्वीकृत नगरेसम्म यो उपलब्ध हुँदैन।",
        },
        "test": {
            "question": "Do ten consented purchase accounts support a checklist with specific, understandable checks that do not imply verification?",
            "method": "Wait for at least ten existing consented buyer/circle journey records; distinguish repeated reported concerns from independently verifiable payment controls; owner-review copy before it is shown publicly.",
            "sample_size": "At least 10 consented purchase-journey accounts",
            "success_signal": "Each checklist item has a traceable basis and wording that does not overstate safety or detection.",
        },
        "kill_criterion": "Keep blocked until ten consented purchase accounts exist; kill if no practical checks are supported, or if users could reasonably mistake the card for merchant/payment verification.",
        "depends_on": ["evidence:buyer-purchase-journeys>=10"],
    },
]


def _offer_seed_bet(db: Session, bet_code: str) -> models.SubstrateEntity:
    """Return the existing founding Bet projection, creating a paused founding
    projection only when that specific known seed is absent. Never revive a
    killed Bet and never consume a live-Bet slot just to attach an offer."""
    prefix = f"Bet {bet_code} —"
    candidates = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == BET_ENTITY_TYPE)
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )
    for candidate in candidates:
        claim = _bet_attributes(candidate).get("claim") or ""
        if claim.startswith(prefix):
            return candidate
    spec = next((item for item in SEED_FOUNDING_BETS if (item.get("claim") or "").startswith(prefix)), None)
    if spec is None:
        raise ValueError(f"Existing founding Bet {bet_code} is unavailable; offer was not seeded.")
    return create_bet(
        db,
        claim=spec["claim"],
        constraint=spec["constraint"],
        test=spec["test"],
        kill_criterion=spec["kill_criterion"],
        decision_rule=spec["decision_rule"],
        skeptic_case=spec["skeptic_case"],
        owner_time=spec.get("owner_time"),
        money_at_risk=spec.get("money_at_risk"),
        trust_at_risk=spec.get("trust_at_risk"),
        deadline=spec.get("deadline"),
        initial_status="paused",
    )


def _offer_records(db: Session) -> list[tuple[models.SubstrateEntity, dict, dict]]:
    records: list[tuple[models.SubstrateEntity, dict, dict]] = []
    bets = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == BET_ENTITY_TYPE)
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )
    for bet in bets:
        attributes = _bet_attributes(bet)
        offers = attributes.get("offers", [])
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if isinstance(offer, dict) and isinstance(offer.get("id"), str):
                records.append((bet, attributes, offer))
    return records


def _legal_read_action(db: Session, *, create: bool = False) -> models.Action | None:
    action = (
        db.query(models.Action)
        .filter(
            models.Action.action_type == OFFER_LEGAL_ACTION_KIND,
            models.Action.objective == OFFER_LEGAL_ACTION_OBJECTIVE,
        )
        .order_by(models.Action.id.asc())
        .first()
    )
    if action is not None or not create:
        return action
    from app import models as _models
    action = _models.Action(
        action_type=OFFER_LEGAL_ACTION_KIND,
        objective=OFFER_LEGAL_ACTION_OBJECTIVE,
        parameters_json=json.dumps({
            "item_id": "personal-data-consent-and-online-business-registration-nepal",
            "status": "not yet read by a lawyer",
            "topics": OFFER_LEGAL_TOPICS,
            "review_record": None,
        }, ensure_ascii=False),
        status="PROPOSED",
        policy_result="REQUIRE_APPROVAL",
        policy_reason="A qualified Nepal-lawyer review is required; Hami has not established legal compliance.",
        verification_state="UNVERIFIED",
    )
    db.add(action)
    db.flush()
    return action


def _legal_read_projection(db: Session) -> dict:
    action = _legal_read_action(db)
    parameters = {}
    if action and action.parameters_json:
        try:
            parameters = json.loads(action.parameters_json)
        except (TypeError, ValueError):
            parameters = {}
    recorded = parameters.get("status") == "read-by-lawyer" and isinstance(parameters.get("review_record"), dict)
    return {
        "item_id": "personal-data-consent-and-online-business-registration-nepal",
        "action_id": action.id if action else None,
        "title": "Nepal legal read: personal-data handling, consent, and online-business registration",
        "topics": OFFER_LEGAL_TOPICS,
        "status": (
            "recorded as read by a lawyer (owner-reported; not independently verified)"
            if recorded else "not yet read by a lawyer"
        ),
        "read_by_lawyer": bool(recorded),
        "review_record": parameters.get("review_record") if recorded else None,
    }


def count_linked_seller_evidence(db: Session, bet_id: int) -> int:
    """Only count real, consented, firsthand seller evidence linked to this Bet."""
    return (
        db.query(models.Evidence)
        .filter(
            models.Evidence.linked_bet_id == bet_id,
            models.Evidence.perspective == "SELLER",
            models.Evidence.consent_status == "granted",
            models.Evidence.source_type == "firsthand",
            models.Evidence.source_kind == "REAL",
        )
        .count()
    )


def _offer_gate_state(db: Session, bet: models.SubstrateEntity, offer: dict) -> dict:
    blockers: list[str] = []
    bet_attributes = _bet_attributes(bet)
    bet_status = bet_attributes.get("status", "unknown")
    if bet_status == "killed":
        blockers.append("The linked Bet is killed; this offer cannot be activated.")
    if offer.get("id") == "rescue-week":
        legal = _legal_read_projection(db)
        if not legal["read_by_lawyer"]:
            blockers.append("Blocked until the Nepal personal-data/consent and online-business-registration legal read is recorded.")
        seller_evidence = count_linked_seller_evidence(db, bet.id)
        if seller_evidence < 1:
            blockers.append("Blocked until at least one real, firsthand, consented seller evidence record exists.")
    if offer.get("id") == "before-you-pay-card":
        from app.services import residue_engine
        journey_count = residue_engine.count_journeys(db)
        if journey_count < 10:
            blockers.append(f"Blocked until at least 10 consented purchase-journey accounts exist ({journey_count}/10 recorded).")
    return {
        "blocked": bool(blockers),
        "blockers": blockers,
        "linked_bet_status": bet_status,
    }


def list_offer_views(db: Session, *, public_only: bool = False) -> list[dict]:
    """Return the Offer projection from existing Bet attributes and current gates."""
    rows = []
    for bet, _attributes, offer in _offer_records(db):
        gates = _offer_gate_state(db, bet, offer)
        approved = bool(offer.get("owner_approved_at"))
        if public_only and not (
            offer.get("status") in ("owner-approved", "live") and approved and not gates["blocked"]
        ):
            continue
        rows.append({
            **offer,
            "bet_id": bet.id,
            "bet_name": bet.display_name,
            "readiness": gates,
            "public_copy": bool(offer.get("status") in ("owner-approved", "live") and approved and not gates["blocked"]),
        })
    return rows


def seed_offer_views(db: Session) -> dict:
    """Idempotently seed five drafts as views of founding Bet projections.
    Adds no table or primitive; every seeded record lives on its existing Bet."""
    # Reuse the founding Bet seam. Missing seeds are created PAUSED and are
    # never silently promoted into the active operating slate.
    targets = {code: _offer_seed_bet(db, code) for code in ("A", "B", "C")}
    existing_ids = {offer["id"] for _bet, _attrs, offer in _offer_records(db)}
    created: list[str] = []
    now = utcnow().isoformat()
    from app.services import world_graph
    try:
        for spec in OFFER_SEEDS:
            if spec["id"] in existing_ids:
                continue
            bet = targets[spec["linked_bet_code"]]
            attributes = _bet_attributes(bet)
            stored_offers = attributes.get("offers", [])
            if not isinstance(stored_offers, list):
                raise ValueError(f"Bet {bet.id} has malformed offer projection; review before seeding.")
            record = {
                **spec,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "owner_approved_at": None,
                "owner_approved_by": None,
                "live_at": None,
                "killed_at": None,
                "kill_reason": None,
                "status_history": [{"status": "draft", "actor": "seed", "at": now}],
            }
            stored_offers.append(record)
            attributes["offers"] = stored_offers
            bet.attributes = json.dumps(attributes, ensure_ascii=False, sort_keys=True)
            db.add(bet)
            world_graph.create_event(
                db,
                event_type="state_changed",
                source="offer_projection",
                entity_id=bet.id,
                payload={
                    "change": "offer_seeded",
                    "offer_id": spec["id"],
                    "offer_status": "draft",
                    "owner_approval_required": True,
                },
                idempotency_key=f"hami-offer-seeded:{spec['id']}",
            )
            existing_ids.add(spec["id"])
            created.append(spec["id"])
        existing_legal_action = _legal_read_action(db)
        legal_action = _legal_read_action(db, create=True)
        if existing_legal_action is None and legal_action is not None:
            world_graph.create_event(
                db,
                event_type="state_changed",
                source="offer_legal_read",
                entity_id=targets["A"].id,
                payload={
                    "change": "legal_read_item_created",
                    "action_id": legal_action.id,
                    "item_id": "personal-data-consent-and-online-business-registration-nepal",
                    "status": "not yet read by a lawyer",
                },
                idempotency_key="hami-offer-legal-read-item-created:v1",
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "created": created,
        "offers": list_offer_views(db),
        "legal_read": _legal_read_projection(db),
    }


def set_offer_status(
    db: Session,
    offer_id: str,
    status: str,
    *,
    kill_reason: str | None = None,
    actor: str = "owner",
) -> dict:
    if status not in ("owner-approved", "live", "killed"):
        raise ValueError("status must be owner-approved|live|killed")
    entry = next((row for row in _offer_records(db) if row[2].get("id") == offer_id), None)
    if entry is None:
        raise ValueError("Offer not found.")
    bet, attributes, offer = entry
    current = offer.get("status", "draft")
    allowed = {
        "draft": {"owner-approved", "killed"},
        "owner-approved": {"live", "killed"},
        "live": {"killed"},
        "killed": set(),
    }
    if status not in allowed.get(current, set()):
        raise ValueError(f"Invalid offer transition: {current} -> {status}.")
    gates = _offer_gate_state(db, bet, offer)
    if status == "owner-approved" and gates["blocked"]:
        raise ValueError("Offer remains blocked: " + " ".join(gates["blockers"]))
    if status == "live":
        if not offer.get("owner_approved_at"):
            raise ValueError("Offer must be explicitly owner-approved before it can go live.")
        if gates["blocked"]:
            raise ValueError("Offer remains blocked: " + " ".join(gates["blockers"]))
        if gates.get("linked_bet_status") != "live":
            raise ValueError("Offer cannot go live until its linked Bet is live.")
    if status == "killed" and not (kill_reason or "").strip():
        raise ValueError("Killing an offer requires a non-empty reason.")
    now = utcnow().isoformat()
    offer["status"] = status
    offer["updated_at"] = now
    offer.setdefault("status_history", []).append({
        "status": status,
        "actor": actor,
        "at": now,
        "reason": (kill_reason or "").strip() or None,
    })
    if status == "owner-approved":
        offer["owner_approved_at"] = now
        offer["owner_approved_by"] = actor
    elif status == "live":
        offer["live_at"] = now
    elif status == "killed":
        offer["killed_at"] = now
        offer["kill_reason"] = (kill_reason or "").strip()
    attributes["offers"] = [
        offer if item.get("id") == offer_id else item
        for item in attributes.get("offers", [])
    ]
    bet.attributes = json.dumps(attributes, ensure_ascii=False, sort_keys=True)
    db.add(bet)
    from app.services import world_graph
    world_graph.create_event(
        db,
        event_type="state_changed",
        source="offer_projection",
        entity_id=bet.id,
        payload={
            "change": "offer_status_changed",
            "offer_id": offer_id,
            "from_status": current,
            "to_status": status,
            "authorized_by": actor,
            "kill_reason": (kill_reason or "").strip() or None,
        },
        idempotency_key=f"hami-offer-status:{offer_id}:{status}:{now}",
    )
    db.commit()
    return next(item for item in list_offer_views(db) if item["id"] == offer_id)


def record_offer_legal_read(
    db: Session,
    *,
    lawyer_name: str,
    review_date: str,
    source_reference: str,
    summary: str,
    actor: str = "owner",
) -> dict:
    lawyer = (lawyer_name or "").strip()
    reference = (source_reference or "").strip()
    note = (summary or "").strip()
    date_value = (review_date or "").strip()
    if len(lawyer) < 2 or len(lawyer) > 200:
        raise ValueError("Provide the reviewing lawyer's name (2–200 characters).")
    if len(reference) < 4 or len(reference) > 500:
        raise ValueError("Provide a retrievable review/evidence reference (4–500 characters).")
    if len(note) < 10 or len(note) > 3000:
        raise ValueError("Provide a concise review summary (10–3000 characters).")
    try:
        parsed_date = datetime.fromisoformat(date_value)
    except ValueError as exc:
        raise ValueError("review_date must be an ISO date or datetime.") from exc
    if parsed_date.date() > utcnow().date():
        raise ValueError("review_date cannot be in the future.")
    action = _legal_read_action(db, create=True)
    assert action is not None
    parameters = {}
    try:
        parameters = json.loads(action.parameters_json or "{}")
    except (TypeError, ValueError):
        parameters = {}
    now = utcnow().isoformat()
    record = {
        "lawyer_name": lawyer,
        "review_date": parsed_date.date().isoformat(),
        "source_reference": reference,
        "summary": note,
        "recorded_by": actor,
        "recorded_at": now,
        "verification": "owner-reported; not independently verified",
    }
    parameters.update({
        "item_id": "personal-data-consent-and-online-business-registration-nepal",
        "status": "read-by-lawyer",
        "topics": OFFER_LEGAL_TOPICS,
        "review_record": record,
    })
    action.parameters_json = json.dumps(parameters, ensure_ascii=False)
    action.status = "SUCCEEDED"
    action.execution_result = "Owner recorded a lawyer-read report; identity/content not independently verified."
    action.verification_state = "UNVERIFIED"
    db.add(action)
    from app.services import world_graph
    bet = _offer_seed_bet(db, "A")
    world_graph.create_event(
        db,
        event_type="state_changed",
        source="offer_legal_read",
        entity_id=bet.id,
        payload={
            "change": "legal_read_recorded",
            "action_id": action.id,
            "status": "read-by-lawyer",
            "review_date": record["review_date"],
            "source_reference": reference,
            "recorded_by": actor,
            "verification": record["verification"],
        },
        idempotency_key=f"hami-offer-legal-read:{action.id}:{record['review_date']}",
    )
    db.commit()
    return _legal_read_projection(db)


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


def overdue_bets(db: Session) -> list:
    """Live Bets past their deadline. Deadlines don't auto-kill — they
    surface for the amplify/dampen/kill decision the operating model
    requires. A Bet without a deadline is never overdue."""
    now = utcnow()
    result = []
    for bet in live_bets(db):
        deadline_str = _bet_attributes(bet).get("deadline")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if deadline < now:
                result.append(bet)
        except (ValueError, TypeError):
            continue
    return result


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
    initial_status: str = "live",
) -> models.SubstrateEntity:
    if initial_status not in ("live", "paused"):
        raise ValueError("initial_status must be live|paused")
    if initial_status == "live" and len(live_bets(db)) >= MAX_LIVE_BETS:
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
        "status": initial_status,
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
    if decision not in ("paused", "amplified", "dampened", "killed"):
        raise ValueError("decision must be paused|amplified|dampened|killed")
    if decision == "paused" and not (notes or "").strip():
        raise ValueError("Pausing a Bet requires an owner rationale.")
    bet = db.get(models.SubstrateEntity, bet_id)
    if not bet or bet.entity_type != BET_ENTITY_TYPE:
        raise ValueError("Bet not found.")
    attrs = _bet_attributes(bet)
    if decision == "paused" and attrs.get("status") != "live":
        raise ValueError("Only a live Bet can be paused.")
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


def _unknown_catalog() -> dict[str, dict]:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "unknowns.json")
    with open(path, encoding="utf-8") as source:
        rows = json.load(source)["unknowns"]
    return {row["id"]: row for row in rows}


def create_candidate(
    db: Session,
    *,
    source_unknown_id: Optional[str],
    claim: Optional[str],
    why_it_matters: Optional[str],
    disconfirming_test: Optional[str],
    kill_rule: Optional[str],
    consent_requirement: Optional[str],
    bounded_cost: Optional[str],
    bounded_harm: Optional[str],
    time_to_first_evidence_days: Optional[int],
    horizon_relation: str,
    assessments: dict,
    candidate_lane: str = "known_unknown",
    discovery_source: Optional[str] = None,
    discovery_basis: Optional[str] = None,
    provisional_unknown: bool = False,
    origin_bet_id: Optional[int] = None,
    origin_evidence_id: Optional[int] = None,
) -> models.SubstrateEntity:
    """Store an owner-proposed candidate on the existing Bet projection.

    This records a proposal only. It neither selects a live Bet nor authorizes
    or executes the test.

    Two lanes share this seam. ``known_unknown`` tests an explicitly
    represented unknown (source_unknown_id required, unless the candidate is a
    provisional unknown converted from a discovery finding). The
    ``unknown_unknown_discovery`` lane probes the boundary of current
    knowledge; it needs no pre-existing named unknown, but it must name the
    grounded discovery source and the observable reason Hami might be missing
    something (discovery_basis). Both lanes pass the same admission gates.
    """
    if candidate_lane not in CANDIDATE_LANES:
        raise ValueError(f"candidate_lane must be one of {CANDIDATE_LANES}.")
    if time_to_first_evidence_days is not None and time_to_first_evidence_days < 0:
        raise ValueError("time_to_first_evidence_days cannot be negative.")
    if horizon_relation not in ("inside", "outside", "unassessed"):
        raise ValueError("horizon_relation must be inside|outside|unassessed")
    unknown = None
    if candidate_lane == "known_unknown":
        if discovery_source is not None or (discovery_basis or "").strip():
            raise ValueError(
                "discovery_source/discovery_basis belong to the "
                "unknown_unknown_discovery lane only."
            )
        if source_unknown_id is None:
            if not provisional_unknown:
                raise ValueError(
                    "A known-unknown candidate requires a source_unknown_id, "
                    "or provisional_unknown=True when converted from a "
                    "discovery finding."
                )
        else:
            unknown = _unknown_catalog().get(source_unknown_id)
            if unknown is None:
                raise ValueError(
                    f"Unknown {source_unknown_id!r} is not in UNKNOWN_MAP.md."
                )
    else:  # unknown_unknown_discovery
        if not discovery_source or discovery_source not in DISCOVERY_SOURCES:
            raise ValueError(
                f"discovery_source must be one of {DISCOVERY_SOURCES}."
            )
        if not (discovery_basis or "").strip():
            raise ValueError(
                "A discovery candidate requires a discovery_basis: the "
                "observable reason Hami might be missing something."
            )
        if source_unknown_id is not None:
            unknown = _unknown_catalog().get(source_unknown_id)
            if unknown is None:
                raise ValueError(
                    f"Unknown {source_unknown_id!r} is not in UNKNOWN_MAP.md."
                )

    normalized_assessments = {}
    for dimension in SELECTION_DIMENSIONS:
        item = assessments.get(dimension, {}) if isinstance(assessments, dict) else {}
        level = item.get("level", "unassessed") if isinstance(item, dict) else "unassessed"
        provenance = (
            item.get("provenance", "unassessed")
            if isinstance(item, dict)
            else "unassessed"
        )
        if level not in ASSESSMENT_LEVELS:
            raise ValueError(f"{dimension} level must be one of {ASSESSMENT_LEVELS}.")
        if provenance not in ASSESSMENT_PROVENANCE:
            raise ValueError(
                f"{dimension} provenance must be one of {ASSESSMENT_PROVENANCE}."
            )
        if (level == "unassessed") != (provenance == "unassessed"):
            raise ValueError(
                f"{dimension} unassessed level and provenance must be paired."
            )
        normalized_assessments[dimension] = {
            "level": level,
            "provenance": provenance,
            "confirmed": provenance not in ("model-proposed", "unassessed"),
            "is_evidence": False,
        }

    claim_text = (claim or (unknown["question"] if unknown else "")).strip()
    if not claim_text:
        raise ValueError("A candidate requires a claim or question.")
    attributes = {
        "claim": claim_text,
        "constraint": (why_it_matters or (unknown.get("stake") if unknown else "") or "").strip(),
        "test": (disconfirming_test or "").strip(),
        "kill_criterion": (kill_rule or "").strip(),
        "decision_rule": "",
        "skeptic_case": "",
        "status": "candidate",
        "source_unknown_id": source_unknown_id,
        "candidate_lane": candidate_lane,
        "discovery_source": discovery_source,
        "discovery_basis": (discovery_basis or "").strip(),
        "provisional_unknown": bool(provisional_unknown),
        "origin_bet_id": origin_bet_id,
        "origin_evidence_id": origin_evidence_id,
        "consent_requirement": (consent_requirement or "").strip(),
        "bounded_cost": (bounded_cost or "").strip(),
        "bounded_harm": (bounded_harm or "").strip(),
        "time_to_first_evidence_days": time_to_first_evidence_days,
        "time_to_first_evidence_provenance": (
            "owner-confirmed" if time_to_first_evidence_days is not None else "unassessed"
        ),
        "horizon_relation": horizon_relation,
        "horizon_relation_provenance": (
            "owner-confirmed" if horizon_relation != "unassessed" else "unassessed"
        ),
        "assessments": normalized_assessments,
        "evidence_references": [],
    }
    from app.services import world_graph  # local import to avoid cycles

    candidate = world_graph.create_entity(
        db,
        entity_type=BET_ENTITY_TYPE,
        display_name=f"Candidate: {claim_text[:80]}",
        attributes=attributes,
        created_by="owner",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def _candidate_gate_blockers(attributes: dict) -> list[str]:
    blockers = []
    required = (
        ("claim", "falsifiable claim or question"),
        ("test", "named disconfirming test"),
        ("kill_criterion", "kill rule"),
        ("consent_requirement", "consent/permission requirement"),
        ("bounded_cost", "bounded expected cost"),
        ("bounded_harm", "bounded expected harm"),
    )
    for key, label in required:
        value = attributes.get(key)
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"Missing {label}.")
    assessments = attributes.get("assessments") or {}
    if not isinstance(assessments, dict):
        assessments = {}
    for dimension in ("cost", "harm"):
        item = assessments.get(dimension) or {}
        if not isinstance(item, dict):
            item = {}
        if (
            item.get("level") not in ("high", "medium", "low")
            or item.get("provenance") in ("unassessed", "model-proposed")
        ):
            blockers.append(
                f"{dimension.capitalize()} must have a bounded, non-model assessment."
            )
    return blockers


def _trusted_assessment(candidate: dict, dimension: str) -> Optional[str]:
    item = candidate["assessments"].get(dimension, {})
    if not item.get("confirmed"):
        return None
    return item["level"] if item["level"] != "unassessed" else None


def _compare_candidates(left: dict, right: dict) -> int:
    positive = (
        "uncertainty",
        "evidence_potential",
        "stake",
        "transferability",
        "capability_gain",
        "upside",
        "reversibility",
    )
    preference = {"low": 0, "medium": 1, "high": 2}
    for dimension in positive:
        a = _trusted_assessment(left, dimension)
        b = _trusted_assessment(right, dimension)
        if a is not None and b is not None and a != b:
            return preference[b] - preference[a]
    for dimension in ("harm", "cost", "time"):
        a = _trusted_assessment(left, dimension)
        b = _trusted_assessment(right, dimension)
        if a is not None and b is not None and a != b:
            return preference[a] - preference[b]
    return (left["candidate_id"] > right["candidate_id"]) - (
        left["candidate_id"] < right["candidate_id"]
    )


def select_next_candidates(db: Session) -> dict:
    """Rank owner-authored candidate Bets qualitatively; never score or execute.

    Gate failures are blockers, not negative scores. Unknown assessments and
    model proposals are surfaced but excluded from comparisons. Strategic
    learning/leverage factors precede ease, time, cost, and harm.
    """
    source_unknowns = _unknown_catalog()
    rows = (
        db.query(models.SubstrateEntity)
        .filter(
            models.SubstrateEntity.entity_type == BET_ENTITY_TYPE,
            models.SubstrateEntity.status == "active",
        )
        .order_by(models.SubstrateEntity.id.asc())
        .all()
    )
    candidates = []
    for row in rows:
        attributes = _bet_attributes(row)
        status = attributes.get("status")
        if status not in ("candidate", "live", "paused"):
            continue
        source_id = attributes.get("source_unknown_id")
        source = (
            source_unknowns.get(source_id)
            if isinstance(source_id, str)
            else None
        )
        raw_assessments = attributes.get("assessments") or {}
        if not isinstance(raw_assessments, dict):
            raw_assessments = {}
        assessments = {}
        missing_information = []
        for dimension in SELECTION_DIMENSIONS:
            raw = raw_assessments.get(dimension) or {}
            if not isinstance(raw, dict):
                raw = {}
            level = raw.get("level")
            provenance = raw.get("provenance")
            if level not in ASSESSMENT_LEVELS or provenance not in ASSESSMENT_PROVENANCE:
                level, provenance = "unassessed", "unassessed"
            confirmed = provenance not in ("model-proposed", "unassessed")
            assessments[dimension] = {
                "level": level,
                "provenance": provenance,
                "confirmed": confirmed,
                "is_evidence": False,
            }
            if level == "unassessed":
                missing_information.append(f"{dimension} assessment")
            elif provenance == "model-proposed":
                missing_information.append(f"{dimension} assessment needs confirmation")
        blockers = _candidate_gate_blockers(attributes)
        if status == "paused":
            blockers.insert(0, "Paused Bet preserved as history; not eligible for selection.")
        elif status == "live":
            blockers.insert(0, "Existing live Bet is not an unpromoted selection candidate.")
        if source_id and source is None:
            blockers.append("Source unknown is no longer present in the generated map projection.")
        if not source_id:
            missing_information.append("source unknown link")
        first_evidence_days = attributes.get("time_to_first_evidence_days")
        if first_evidence_days is None:
            missing_information.append("expected first-evidence timing")
        if attributes.get("horizon_relation") == "unassessed":
            missing_information.append("relationship to current watch horizon")
        evidence_refs = attributes.get("evidence_references") or []
        item = {
            "candidate_id": f"bet:{row.id}",
            "candidate": row.display_name,
            "source_unknown_id": source_id,
            "candidate_lane": attributes.get("candidate_lane", "known_unknown"),
            "discovery_source": attributes.get("discovery_source"),
            "discovery_basis": attributes.get("discovery_basis") or "",
            "provisional_unknown": bool(attributes.get("provisional_unknown")),
            "origin_bet_id": attributes.get("origin_bet_id"),
            "origin_evidence_id": attributes.get("origin_evidence_id"),
            "model_proposed": any(
                (raw_assessments.get(dimension) or {}).get("provenance") == "model-proposed"
                for dimension in SELECTION_DIMENSIONS
            ),
            "claim_or_question": attributes.get("claim") or "",
            "why_it_matters": attributes.get("constraint") or (
                source.get("stake", "") if source else ""
            ),
            "assessments": assessments,
            "evidence_status": (
                f"{len(evidence_refs)} linked reference(s); not independently verified here."
                if evidence_refs
                else "No evidence references recorded on this Bet; assessments are not evidence."
            ),
            "kill_rule": attributes.get("kill_criterion") or "Unassessed",
            "expected_first_evidence": (
                f"Within {first_evidence_days} day(s)"
                if isinstance(first_evidence_days, int)
                else "Unassessed"
            ),
            "time_to_first_evidence_days": first_evidence_days,
            "horizon_relation": attributes.get("horizon_relation", "unassessed"),
            "gate_blockers": blockers,
            "missing_information": sorted(set(missing_information)),
            "status": status,
            "rank": None,
            "selection_reason": None,
        }
        candidates.append(item)

    eligible = [item for item in candidates if not item["gate_blockers"]]
    eligible.sort(key=cmp_to_key(_compare_candidates))
    live_count = len(live_bets(db))
    available_slots = max(0, MAX_LIVE_BETS - live_count)
    selected: dict[str, str] = {}

    def choose(items: list[dict], reason: str) -> None:
        if len(selected) >= available_slots:
            return
        candidate = next(
            (item for item in items if item["candidate_id"] not in selected),
            None,
        )
        if candidate:
            selected[candidate["candidate_id"]] = reason

    choose(eligible, "Strongest overall by the qualitative global comparison.")
    choose(
        [
            item
            for item in eligible
            if item["horizon_relation"] == "outside"
            and item["horizon_relation"] != "unassessed"
        ],
        "Reserved exploration slot: explicitly outside the current watch horizon.",
    )
    choose(
        [
            item
            for item in eligible
            if isinstance(item["time_to_first_evidence_days"], int)
            and item["time_to_first_evidence_days"] <= 7
        ],
        "Meets the owner-approved first-evidence-within-7-days portfolio floor.",
    )
    for item in eligible:
        if len(selected) >= available_slots:
            break
        selected.setdefault(
            item["candidate_id"],
            "Next by qualitative merit within the remaining owner-review slots.",
        )

    ranked = eligible + sorted(
        (item for item in candidates if item["gate_blockers"]),
        key=lambda item: item["candidate_id"],
    )
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
        reason = selected.get(item["candidate_id"])
        if reason:
            item["selection_reason"] = f"Selected for owner review. {reason}"
        elif item["gate_blockers"]:
            item["selection_reason"] = "Blocked: " + " ".join(item["gate_blockers"])
        elif item["candidate_id"] in {c["candidate_id"] for c in eligible}:
            item["selection_reason"] = (
                "Not selected: ranked outside the available owner-review slots "
                "under the portfolio constraints."
            )

    selected_slate = [
        item for item in ranked if item["candidate_id"] in selected
    ]
    return {
        "ranked_candidates": ranked,
        "selected_slate": selected_slate,
        "live_bet_count": live_count,
        "available_live_slots": available_slots,
        "portfolio_requirements": {
            "first_evidence_within_7_days": any(
                item["time_to_first_evidence_days"] <= 7
                for item in selected_slate
                if isinstance(item["time_to_first_evidence_days"], int)
            ),
            "exploration_outside_watch_horizon": any(
                item["horizon_relation"] == "outside" for item in selected_slate
            ),
            "strongest_overall_included": bool(
                available_slots
                and eligible
                and selected_slate
                and selected_slate[0]["candidate_id"] == eligible[0]["candidate_id"]
            ),
        },
        "portfolio_gaps": [
            requirement
            for requirement, fulfilled in (
                (
                    "No admitted candidate has owner-confirmed first evidence within 7 days.",
                    any(
                        item["time_to_first_evidence_days"] <= 7
                        for item in selected_slate
                        if isinstance(item["time_to_first_evidence_days"], int)
                    ),
                ),
                (
                    "No admitted candidate is explicitly outside the current watch horizon.",
                    any(
                        item["horizon_relation"] == "outside" for item in selected_slate
                    ),
                ),
            )
            if available_slots and not fulfilled
        ],
        "comparison_method": (
            "Qualitative, lexicographic comparison; no aggregate numeric score. "
            "Strategic learning/leverage factors precede cost, time, and harm. "
            "Unassessed and model-proposed values do not become Low."
        ),
        "assessment_guidance": (
            "For stake, uncertainty, evidence potential, capability gain, "
            "transferability, upside, and reversibility, High indicates more "
            "of the named positive potential. For cost, time, and harm, High "
            "indicates greater burden, delay, or exposure. Unknown remains "
            "Unassessed. These judgments are not evidence."
        ),
        "responsibility": [
            {
                "stage": "unknown / observation",
                "performed_by": ["human", "code"],
                "current_boundary": "Humans record map unknowns and observations; code generates projections and imports Claims. AI output can suggest, not establish reality.",
                "authorization": "External observation/contact requires the applicable owner authorization and affected-party consent.",
            },
            {
                "stage": "hypothesis",
                "performed_by": ["human", "AI model"],
                "current_boundary": "Owners author Bet/unknown hypotheses; models may propose text in separate business-analysis flows. Model proposals are not evidence.",
                "authorization": "Hypothesis writing alone does not authorize contact, spend, publication, or action.",
            },
            {
                "stage": "candidate selection",
                "performed_by": ["code", "human"],
                "current_boundary": "This owner-only selector compares candidate Bet projections; a human must author/register each candidate. Legacy WTP and revenue rankers do not feed this comparison.",
                "authorization": "The read-only ranking requires owner API access; selection does not promote or authorize a Bet.",
            },
            {
                "stage": "experiment design",
                "performed_by": ["human", "code"],
                "current_boundary": "The owner supplies the disconfirming test, consent/permission requirement, bounded cost/harm, and kill rule; code validates admission fields.",
                "authorization": "Candidate registration is owner-guarded and does not authorize execution.",
            },
            {
                "stage": "execution",
                "performed_by": ["human", "code"],
                "current_boundary": "This selector executes nothing. Existing code workflows run only where their own capability and authorization gates permit.",
                "authorization": "Explicit owner authorization, affected-party consent, external permission, and available capability remain required.",
            },
            {
                "stage": "evidence",
                "performed_by": ["human", "code"],
                "current_boundary": "Humans or existing code paths record sourced evidence; model-proposed assessments are explicitly not evidence.",
                "authorization": "Evidence collection remains subject to consent, privacy, access, and legal constraints.",
            },
            {
                "stage": "verification",
                "performed_by": ["code", "human"],
                "current_boundary": "Existing evidence/proof gates validate recorded claims; some proof levels require a verifier or counterparty confirmation.",
                "authorization": "Verification does not substitute for permission to collect evidence or act.",
            },
            {
                "stage": "action",
                "performed_by": ["human", "code"],
                "current_boundary": "Owners authorize consequential actions; code can execute only through existing gated paths. The selector has no execution button.",
                "authorization": "Action-specific authorization and external permission remain mandatory.",
            },
            {
                "stage": "outcome",
                "performed_by": ["human", "code"],
                "current_boundary": "Real outcomes require attributable real-world evidence; code can persist records but cannot infer a transaction from a plan.",
                "authorization": "Outcome recording does not retroactively authorize the action.",
            },
            {
                "stage": "learning",
                "performed_by": ["human", "code"],
                "current_boundary": "Code preserves decision/evidence records; humans currently interpret results and update the authoritative unknown map.",
                "authorization": "Updating internal learning records is not authorization for a subsequent external step.",
            },
            {
                "stage": "next unknown",
                "performed_by": ["human"],
                "current_boundary": "A human currently notices or curates the next unknown; no automatic outcome-to-unknown loop is claimed.",
                "authorization": "Any resulting external test still needs its own authorization and consent.",
            },
        ],
    }


# ---------------------------------------------------------------------
# Founding evidence Bets (architect-approved 2026-10-07)
# ---------------------------------------------------------------------
# The Unknown -> Experiment -> Evidence -> Profit proposal was reviewed as a
# proposal, not an implementation request. Verdict: strategic direction
# APPROVED; E1-E5 APPROVED WITH STRUCTURAL CHANGES; schema/dashboard expansion
# (Experiment.unknown_id, new template system, UNKNOWN_MAP migration to DB)
# NOT APPROVED. These three Bets are historical founding material — seeded through
# the existing create_bet seam, with the anti-theater pre-registration carried
# by the Bet's own fields (kill_criterion, decision_rule, affordable_loss).
# No new tables, no new models, no dashboard. Bet A is retained as paused
# history and is never a privileged input to the global selector.
#
# Structural corrections baked in:
# - Cycle is UNKNOWN -> CHEAPEST LEGITIMATE PROBE -> EVIDENCE -> DECISION ->
#   REAL VALUE -> REVENUE, not a linear pipeline; UNKNOWN -> THESIS KILLED
#   counts as progress.
# - E1 records ACTUALS (inquiries, responses, latency, sales, amounts paid);
#   "lost revenue" is forbidden — only an explicitly labeled ESTIMATE.
# - E2 answers are reported belief, requiring behavioral verification.
# - E3 segments via historical episodes, not bill opinions.
# - E4 uses 30-day time-windowed reported incidence, not vague stories.
# - E5 is the human collection layer (five owner conversations), not a
#   separate experiment.
# - First verified rupee != profit: affordable_loss tracks owner time and
#   cash separately from day one.
# Unknown IDs refer to docs/UNKNOWN_MAP.md, the authoritative registry.

SEED_FOUNDING_BETS = [
    {
        "claim": (
            "Bet A — Response / Presence / Sale Path: for the target seller "
            "segment, slow or missing responses (not lack of demand) are what "
            "prevent inquiries from becoming paid sales, and the sale closes "
            "in the channel the seller already uses."
        ),
        "constraint": (
            "B1-B4 UNKNOWN (zero real seller conversations); D12/D1 UNKNOWN "
            "(no measured inquiry/response data); D2 UNKNOWN and "
            "thesis-threatening (demand vs presence); D11 UNKNOWN (segment "
            "split); D13 UNKNOWN (where sales close)."
        ),
        "test": (
            "Founding Merchant Reality Sprint — cheapest legitimate probes "
            "first. (1) Five owner-run 10-minute conversations = the human "
            "collection layer (open questions, no pitching, consent-first). "
            "In every conversation ask FIRST (D2): 'If I brought you 10 new "
            "customers tomorrow, what breaks?' — treat answers as reported "
            "belief only; a 'give me customers' answer must be checked against "
            "behavioral evidence (missed calls, slow replies) before it "
            "updates the thesis. (2) Extract two histories per conversation "
            "(D11): 'tell me about the last time you had too few customers' vs "
            "'the last time customers wanted to buy and you could not keep "
            "up' — historical episodes segment demand- vs presence-constrained "
            "sellers; 'which bill scares you most' is economic context, not "
            "the segmentation test. (3) 'Walk me through your last 5 sales "
            "step by step — how did each one actually close?' (D13). "
            "(4) One-week inquiry autopsy with up to 5 consenting sellers "
            "(D12/D1): record inquiries received, responses sent, response "
            "latency, no-response cases, conversations continued, offers "
            "made, sales completed, actual amount paid, channel where sale "
            "closed. NEVER record 'lost revenue' — an unanswered inquiry is "
            "not observed revenue. A separate, explicitly labeled 'estimated "
            "recoverable value' may be computed; it is an estimate, never "
            "revenue."
        ),
        "kill_criterion": (
            "Kill the bet if: the five conversations + autopsy cannot be "
            "completed within the owner-time budget; or evidence shows demand "
            "(not response/presence) is the binding constraint across the "
            "observed segment with no credible rescue segment; or no seller "
            "consents to the autopsy and no behavioral data can be obtained. "
            "Dampen/pivot (not full kill) if the constraint is "
            "segment-specific, e.g. demand binds for shutter retail while "
            "presence binds for social sellers."
        ),
        "decision_rule": (
            "An outcome is valid only if it changes this decision: is the "
            "first commercial wedge actually response/presence/recovery "
            "(-> proceed to First Rupee Sprint design) or is demand the "
            "binding constraint (-> pivot the wedge thesis per segment)? "
            "Secondarily: where does the transaction really close (-> shapes "
            "any future intervention's channel; if voice closes, Hami is a "
            "bridge, not a destination). 'We learned something interesting' "
            "without a decision change = experiment theater; the bet stays "
            "live."
        ),
        "skeptic_case": (
            "Owners may say 'give me customers' while routinely missing "
            "calls — reported belief is not proof of the constraint. Five "
            "conversations is a small, non-random sample; do not "
            "overgeneralize across segments. 'Estimated recoverable value' "
            "must never be presented as revenue. Provenance: "
            "architect-approved 2026-10-07 (Unknown->Experiment->Evidence->"
            "Profit review, relayed by owner); unknowns per "
            "docs/UNKNOWN_MAP.md."
        ),
        "owner_time": "Five 10-min conversations + scheduling (<=3h total); autopsy observation is seller-side, owner only sets it up.",
        "money_at_risk": "Rs 0 cash.",
        "trust_at_risk": "Seller relationships — open questions, no pitching, consent-first; one bad conversation burns the channel.",
        "deadline": datetime(2026, 10, 28, tzinfo=timezone.utc),
        "initial_status": "paused",
    },
    {
        "claim": (
            "Bet B — Payment Trust: fake payment confirmations are a "
            "frequent, costly merchant pain in Kathmandu retail, and "
            "merchants lack a reliable verification method — making "
            "adversarial-proof receipt verification a real intervention "
            "candidate."
        ),
        "constraint": (
            "D19/D20/D21 UNKNOWN. No measured incidence; unknown who verifies "
            "at the counter, with what, and whether disputes actually occur."
        ),
        "test": (
            "In the five owner conversations (shared collection layer) plus "
            "up to 5 additional merchant asks: 'In the last 30 days, how many "
            "times has someone shown you a payment confirmation you had to "
            "verify?' Per report capture: reported incidents, time window "
            "(30 days), whether an actual dispute occurred, verification "
            "method used, what happened. Also: 'Who checks the phone when a "
            "QR payment comes in — do you share one login?' (D20) and 'Which "
            "app do you actually use to confirm QR payments, and why?' "
            "(D21). This yields reported incidence, not prevalence — never a "
            "population frequency claim."
        ),
        "kill_criterion": (
            "Kill if: reported 30-day incidence is ~zero across 8+ merchants "
            "with no disputes; or merchants report a satisfactory existing "
            "verification method; or the pain is real but no intervention "
            "Hami could offer would change the outcome."
        ),
        "decision_rule": (
            "Valid only if it changes this decision: is payment verification "
            "a real merchant pain worth turning into an intervention (-> "
            "design a verification aid that survives a fake green tick, "
            "verified on the merchant's own device) or not (-> kill/dampen; "
            "D19 stays context)?"
        ),
        "skeptic_case": (
            "Self-reports overstate rare, salient events; 'had to verify' is "
            "not fraud. QR-app dissatisfaction (e.g. 2.73 rating) may reflect "
            "UX, not a verification gap. Provenance: architect-approved "
            "2026-10-07; unknowns per docs/UNKNOWN_MAP.md."
        ),
        "owner_time": "Rides the same five conversations; <=1h for additional merchant asks.",
        "money_at_risk": "Rs 0 cash.",
        "trust_at_risk": "Minimal — questions only, no intervention proposed yet.",
        "deadline": datetime(2026, 10, 28, tzinfo=timezone.utc),
    },
    {
        "claim": (
            "Bet C — Seller Behavior / Funnel: Nepali sellers deliberately "
            "withhold prices to force inbox engagement, so 'transparency' "
            "tooling would fight the seller's own strategy — Hami must work "
            "with the funnel, not against it."
        ),
        "constraint": (
            "D17 UNKNOWN. Unknown whether price withholding is deliberate "
            "lead-capture or habit; unknown whether it converts."
        ),
        "test": (
            "OBSERVATION first, no contact: manual audit of 50 posts across "
            "10 seller pages — price present/absent, comment counts. Then in "
            "conversations: ask 3 sellers whether withholding converts and "
            "why they do it. Comment counts are directional, not conversion "
            "proof."
        ),
        "kill_criterion": (
            "Kill if: the audit shows prices are usually present (no "
            "withholding pattern); or sellers report withholding does not "
            "convert; or the behavior is segment-specific with no wedge "
            "implication."
        ),
        "decision_rule": (
            "Valid only if it changes this decision: does the seller's "
            "existing commerce behavior invalidate the assumed wedge "
            "(-> pivot: build with the funnel) or confirm it (-> proceed)? "
            "May promote D14/D18/D32 depending on what Bet A exposes."
        ),
        "skeptic_case": (
            "Comment counts weakly proxy conversion; stated reasons may "
            "rationalize habit; 50 posts is directional, not statistical. "
            "Provenance: architect-approved 2026-10-07; unknowns per "
            "docs/UNKNOWN_MAP.md."
        ),
        "owner_time": "<=2h for the manual post audit; conversation questions ride the shared collection layer.",
        "money_at_risk": "Rs 0 cash.",
        "trust_at_risk": "None — public observation only.",
        "deadline": datetime(2026, 10, 28, tzinfo=timezone.utc),
    },
]


def seed_founding_bets(db: Session) -> list:
    """Seed the three architect-approved founding Bets. Idempotent.

    Skips any bet whose claim is already present (live OR decided — a killed
    bet is never resurrected by re-seeding). Respects the MAX_LIVE_BETS WIP
    cap: if the cap is full with other bets, remaining seeds are skipped
    with a warning instead of raising.
    """
    existing_claims = set()
    for b in (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == BET_ENTITY_TYPE)
        .all()
    ):
        claim = _bet_attributes(b).get("claim") or ""
        existing_claims.add(claim[:60])
    created = []
    for spec in SEED_FOUNDING_BETS:
        if spec["claim"][:60] in existing_claims:
            continue
        if len(live_bets(db)) >= MAX_LIVE_BETS:
            log.warning(
                "seed_founding_bets: WIP cap (%d live) reached with other "
                "bets; skipping remaining founding bets.",
                MAX_LIVE_BETS,
            )
            break
        bet = create_bet(
            db,
            claim=spec["claim"],
            constraint=spec["constraint"],
            test=spec["test"],
            kill_criterion=spec["kill_criterion"],
            decision_rule=spec["decision_rule"],
            skeptic_case=spec["skeptic_case"],
            owner_time=spec.get("owner_time"),
            money_at_risk=spec.get("money_at_risk"),
            trust_at_risk=spec.get("trust_at_risk"),
            deadline=spec.get("deadline"),
            initial_status=spec.get("initial_status", "live"),
        )
        created.append(bet)
        existing_claims.add(spec["claim"][:60])
    return created


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


def current_watch_horizon(db: Session) -> dict:
    """Return the editable Horizon-register focus, or the historical default."""
    for horizon in list_horizon_domains(db):
        if _horizon_attributes(horizon).get("name") == WATCH_HORIZON_NAME:
            return {
                "frontier": horizon.display_name.removeprefix("Horizon: "),
                "is_default": False,
            }
    return {"frontier": FROZEN_FRONTIER, "is_default": True}


def set_current_watch_horizon(db: Session, frontier: str) -> models.SubstrateEntity:
    """Owner-edited watch focus stored on the existing Horizon projection."""
    text = (frontier or "").strip()
    if not text:
        raise ValueError("Watch horizon text is required.")
    if len(text) > 2000:
        raise ValueError("Watch horizon text must be 2000 characters or fewer.")
    from app.services import world_graph  # local import to avoid cycles

    existing = next(
        (
            horizon
            for horizon in list_horizon_domains(db)
            if _horizon_attributes(horizon).get("name") == WATCH_HORIZON_NAME
        ),
        None,
    )
    if existing is None:
        previous = FROZEN_FRONTIER
        horizon = world_graph.create_entity(
            db,
            entity_type=HORIZON_DOMAIN_ENTITY_TYPE,
            display_name=f"Horizon: {text}",
            attributes={
                "name": WATCH_HORIZON_NAME,
                "reason_parked": "Owner-editable watch focus; not a universe boundary.",
                "status": "unparked",
                "parked_at": utcnow().isoformat(),
                "unparked_at": None,
            },
            created_by="owner",
        )
        world_graph.create_event(
            db,
            event_type="state_changed",
            source="owner",
            entity_id=horizon.id,
            payload={
                "change": "watch_horizon_initialized",
                "previous": previous,
                "current": text,
            },
        )
    else:
        previous = existing.display_name.removeprefix("Horizon: ")
        existing.display_name = f"Horizon: {text}"
        world_graph.create_event(
            db,
            event_type="state_changed",
            source="owner",
            entity_id=existing.id,
            payload={
                "change": "watch_horizon_updated",
                "previous": previous,
                "current": text,
            },
        )
        horizon = existing
    db.commit()
    db.refresh(horizon)
    return horizon


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
    return _set_proof_level(db, evidence_id, level, source_type, verifier, mark_real=False)


def set_real_proof_level(
    db: Session,
    evidence_id: int,
    level: int,
    source_type: Optional[str] = None,
    verifier: Optional[str] = None,
) -> models.Evidence:
    return _set_proof_level(db, evidence_id, level, source_type, verifier, mark_real=True)


def _set_proof_level(
    db: Session,
    evidence_id: int,
    level: int,
    source_type: Optional[str],
    verifier: Optional[str],
    *,
    mark_real: bool,
) -> models.Evidence:
    if level not in PROOF_LEVELS:
        raise ValueError(f"proof_level must be 0-7, got {level}")
    ev = db.get(models.Evidence, evidence_id)
    if not ev:
        raise ValueError("Evidence not found.")
    attached_to_verified_outcome = (
        db.query(models.EvidenceRelationship.id)
        .join(models.Outcome, models.Outcome.id == models.EvidenceRelationship.outcome_id)
        .filter(
            models.EvidenceRelationship.evidence_id == evidence_id,
            models.EvidenceRelationship.network_connection_id.isnot(None),
            models.Outcome.source_kind == evidence_source.REAL,
            models.Outcome.verification_state.in_(("VERIFIED", "SETTLED")),
            models.Outcome.notes.like("idempotency:network-connection:%:paid"),
        )
        .first()
    )
    if attached_to_verified_outcome:
        raise ValueError("evidence supporting a verified payment cannot be changed")
    st = (source_type or ev.source_type or "").strip().lower()
    clean_verifier = (verifier if verifier is not None else ev.verifier or "").strip()
    has_external_anchor = bool(
        (ev.canonical_url or "").strip() or (ev.external_id or "").strip()
    )
    if mark_real and (
        level < 5
        or st != "third_party"
        or not clean_verifier
        or not has_external_anchor
    ):
        raise ValueError(
            "REAL evidence requires third-party proof at L5+, an external verifier, "
            "and an external URL or provider reference"
        )
    if st == "agent_written" and level > 0:
        ev.proof_level = 0
        ev.proof_capped_reason = "agent-written items are capped at L0"
    elif st == "secondhand" and level > 1:
        ev.proof_level = 1
        ev.proof_capped_reason = "secondhand items are capped at L1"
    elif level >= 5 and not clean_verifier:
        raise ValueError(
            "L5+ requires external anchoring: counterparty confirmation or "
            "a third-party timestamp (verifier field). Anchoring establishes "
            "provenance, timing, or occurrence — not automatically a costly signal."
        )
    else:
        ev.proof_level = level
        ev.proof_capped_reason = None
    if source_type:
        ev.source_type = st
    if verifier is not None:
        ev.verifier = clean_verifier or None
    if mark_real:
        ev.source_kind = evidence_source.REAL
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
    # A sent outbound message is only an owner-reported attempt: Scout records
    # that the counterparty's receipt is unverified. Do not reset the real
    # contact clock until a reply or held conversation is recorded.
    latest = (
        db.query(models.WorldEvent)
        .filter(
            models.WorldEvent.event_type.in_(
                ["outreach.reply", "conversation.held"]
            )
        )
        .order_by(models.WorldEvent.occurred_at.desc())
        .first()
    )
    if not latest or not latest.occurred_at:
        return None
    occurred = latest.occurred_at
    if occurred.tzinfo is None:
        # SQLite returns naive datetimes; treat as UTC.
        occurred = occurred.replace(tzinfo=timezone.utc)
    return (utcnow() - occurred).days


def contact_state(db: Session) -> dict:
    """Return canonical contact priority without letting dry wells starve other work.

    Two days is a soft priority threshold for contact preparation; the
    existing 14-day STARVED rule remains the hard freeze. A pending contact
    outcome needing owner review outranks both. A previously recorded dry well
    remains available for late replies, but does not demand daily re-review.
    """
    days = days_since_last_contact(db)
    pending_contact_replies = (
        db.query(models.OutreachDraft)
        .filter(
            models.OutreachDraft.status == "SENT",
            models.OutreachDraft.reply_received.is_(False),
        )
        .count()
    )
    pending_contact_outcomes = (
        db.query(models.OutreachDraft)
        .filter(
            models.OutreachDraft.status == "SENT",
            models.OutreachDraft.reply_received.is_(False),
            (
                models.OutreachDraft.outcome_notes.is_(None)
                | (models.OutreachDraft.outcome_notes == "")
            ),
        )
        .count()
    )
    dry_wells_recorded = (
        db.query(models.OutreachDraft)
        .filter(
            models.OutreachDraft.status == "SENT",
            models.OutreachDraft.reply_received.is_(False),
            models.OutreachDraft.outcome_notes.isnot(None),
            models.OutreachDraft.outcome_notes != "",
        )
        .count()
    )
    contact_priority_due = days is None or days >= CONTACT_PRIORITY_DAYS
    next_priority = (
        "review_pending_contact_outcomes"
        if pending_contact_outcomes
        else "contact_preparation"
        if contact_priority_due
        else "evidence_and_value"
    )
    return {
        "days_since_last_contact": days,
        "contact_priority_due": contact_priority_due,
        "starved": days is None or days >= STARVED_DAYS,
        "pending_contact_replies": pending_contact_replies,
        "pending_contact_outcomes": pending_contact_outcomes,
        "dry_wells_recorded": dry_wells_recorded,
        "next_priority": next_priority,
    }


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
        "overdue_bets": len(overdue_bets(db)),
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
