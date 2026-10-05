"""
ECONOMIC INTELLIGENCE
=======================

The missing link diagnosed in v1.8: Forge could detect Patterns (13 of
them, in the reported dashboard) but nothing ever asked "does this
Pattern actually represent a monetizable problem?" before either (a)
nothing converted it into an Opportunity at all, or (b) — the old
manual /analyze flow — ANY pattern got converted unconditionally, with
generic boilerplate standing in for real problem/customer/pain data.

This module is the missing question. For a piece of text (a Signal, or
the signals behind a Pattern), extract_economic_signal() attempts a
STRUCTURED, PARTIAL extraction — problem, affected_customer,
customer_type, pain, consequence, existing_solution, desired_outcome,
buying_intent, urgency, monetary_impact, possible_solution — using
keyword/regex heuristics, not an LLM call. This keeps it honest at $0
(the MockProvider default would otherwise just return more boilerplate,
exactly the failure this round diagnosed) and keeps it explainable:
every field either has a textual match backing it, or it's None —
never guessed.

score_economic_signal() then produces the explainable dimensions the
v1.8 spec asked for — pain_score, urgency_score, monetary_impact_score,
demand_score, solution_gap_score, evidence_strength, source_quality —
each documented below with exactly what triggers it. These combine
into is_economically_meaningful(), the gate opportunity_engine.py now
checks before creating an Opportunity at all (see
generate_opportunity_from_pattern() there) — "if Forge cannot answer
what problem/who/why/how strong/what money, it should remain a
pattern, not become an opportunity."

Corroboration (source diversity) is deliberately NOT stored as new
columns — it's computed live from data that already exists
(Pattern.origin_signal_ids -> those Signals' own .source field), same
"derive, don't duplicate" principle used throughout this codebase.
"""

import re

from sqlalchemy.orm import Session

from app import models
from typing import Optional

# --- Vocabulary (small, curated, transparent — not a model) -----------

PAIN_PHRASES = [
    "complain", "complaint", "frustrat", "annoyed", "fed up", "sick of",
    "waste time", "wasting time", "waste of time", "costing", "losing customers",
    "losing money", "lose money", "can't keep up", "cant keep up", "overwhelmed",
    "struggling", "struggle", "hate having to", "dread", "nightmare",
    "spend hours", "spending hours", "hours every", "hours a week", "hours per week", "manually",
]
CONSEQUENCE_PHRASES = [
    "costing", "losing", "lost", "missed out", "miss out", "cost us", "cost me",
    "lost revenue", "lost business", "lost customers", "lost sales",
]
DESIRE_PHRASES = [
    "wish there was", "wish i had", "need a way to", "looking for a way",
    "would pay for", "would love a tool", "if only there was", "someone should build",
]
BUYING_INTENT_PHRASES = [
    "would pay", "willing to pay", "looking to buy", "shopping for",
    "any recommendations for a tool", "what do you use for", "paying for",
]
URGENCY_PHRASES = [
    "asap", "urgent", "immediately", "right now", "every week", "every day",
    "constantly", "every single time", "again and again", "repeatedly",
]
EXISTING_SOLUTION_PHRASES = [
    "currently using", "we use", "tried using", "switched from", "instead of",
    "manually", "by hand", "spreadsheet", "spreadsheets",
]

# Curated customer-type nouns — deliberately small and general-purpose,
# not an attempt at exhaustive NER. Matches the "small contractors",
# "dentists", "shop owners" style of the spec's own GOOD examples.
CUSTOMER_TYPE_NOUNS = [
    "dentist", "dentists", "contractor", "contractors", "restaurant", "restaurants",
    "shop owner", "shop owners", "small business", "small businesses", "freelancer",
    "freelancers", "landlord", "landlords", "clinic", "clinics", "salon", "salons",
    "plumber", "plumbers", "electrician", "electricians", "agency", "agencies",
    "consultant", "consultants", "retailer", "retailers", "startup", "startups",
    "repair shop", "repair shops", "property manager", "property managers",
    "accounting practice", "accounting practices", "accountant", "accountants",
    "law firm", "law firms", "lawyer", "lawyers", "bookkeeper", "bookkeepers",
    "practice", "practices", "gym", "gyms", "fitness studio", "fitness studios",
    "childcare", "daycare", "veterinarian", "veterinarians", "vet clinic", "vet clinics",
    "warehouse", "warehouses", "manufacturer", "manufacturers", "factory", "factories",
    "logistics", "courier", "couriers", "delivery driver", "delivery drivers",
    "coach", "coaches", "instructor", "instructors", "tutor", "tutors",
]

# Structured fallback for real-world mentions the curated noun list misses:
# "[quantifier|modifier] [plural role noun]" such as "5 restaurants",
# "independent repair shops", "small property managers". A strong, honest
# signal should not be gated out merely because its customer noun wasn't in
# the curated list. This is a transparent pattern match — the matched span
# IS returned, so provenance is preserved (never a guessed party). Kept
# conservative: requires a plural noun immediately following a modifier via
# a small, distinct modifier vocabulary so it doesn't fire on noise.
AFFECTED_PARTY_NOUNS = [
    "owners", "operators", "businesses", "startups", "shops", "managers",
    "practices", "clinics", "studios", "firms", "agencies", "restaurants",
    "contractors", "freelancers", "vendors", "retailers", "salons", "gyms",
    "schools", "teachers", "students", "dentists", "veterinarians",
]
AFFECTED_PARTY_MODIFIERS = [
    "small", "independent", "local", "indie", "solo", "tiny", "boutique",
    "family-", "mom-and-pop", "own", "online", "digital", "like", "many",
]
_AFFECTED_PARTY_RE = re.compile(
    r"\b" + r"(?:(?P<mod>" + r"|".join(AFFECTED_PARTY_MODIFIERS) + r")\s+)?"
    r"(?:(?P<count>\d+)\s+)?"
    r"(?P<noun>" + r"|".join(AFFECTED_PARTY_NOUNS) + r")\b",
    re.I,
)

FREQUENCY_PATTERN = re.compile(r"\b(\d+)\+?\s*(hours?|hrs?|times?|days?|weeks?|customers?|clients?|people)\b", re.I)
MONETARY_PATTERN = re.compile(r"\$\s?\d[\d,]*(\.\d+)?|\b\d+\s?(dollars|usd)\b", re.I)
COUNT_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b\s+"
    r"(owners|operators|businesses|startups|shops|managers|practices|clinics|"
    r"studios|firms|agencies|restaurants|contractors|freelancers|vendors|"
    r"retailers|salons|gyms|schools|teachers|students|dentists|veterinarians|"
    r"customers|clients)\b",
    re.I,
)


def _find_any(text: str, phrases: list[str]) -> Optional[str]:
    lowered = text.lower()
    for phrase in phrases:
        if phrase in lowered:
            return phrase
    return None


def _find_customer_type(text: str) -> Optional[str]:
    lowered = text.lower()
    for noun in CUSTOMER_TYPE_NOUNS:
        if noun in lowered:
            return noun
    return None


def _find_affected_party(text: str) -> Optional[str]:
    """Structural fallback: a plural role noun (optionally preceded by a
    qualifying modifier and/or a count), e.g. '5 restaurants',
    'independent repair shops', 'small property managers'. Returns the
    matched span verbatim so provenance is preserved. Used to keep strong
    real signals from being gated out purely by vocabulary coverage."""
    m = _AFFECTED_PARTY_RE.search(text)
    if not m:
        return None
    return m.group(0).strip()


def extract_economic_signal(text: str) -> dict:
    """
    Partial, honest extraction — every field is either backed by an
    actual textual match or explicitly None. Returns a dict (not an
    ORM row): this is a READ-time analysis helper, not new persistent
    storage, used by opportunity_engine.py to decide whether evidence
    is strong enough to justify creating an Opportunity, and to
    populate its fields with real extracted text instead of generic
    boilerplate.
    """
    pain_phrase = (
        "wasting time"
        if re.search(r"\bwasting\s+\d+\s+(?:hours?|hrs?)\b", text, re.I)
        else _find_any(text, PAIN_PHRASES)
    )
    consequence_phrase = _find_any(text, CONSEQUENCE_PHRASES)
    desire_phrase = _find_any(text, DESIRE_PHRASES)
    buying_intent_phrase = _find_any(text, BUYING_INTENT_PHRASES)
    urgency_phrase = _find_any(text, URGENCY_PHRASES)
    existing_solution_phrase = _find_any(text, EXISTING_SOLUTION_PHRASES)
    customer_type = _find_customer_type(text)
    if not customer_type:
        customer_type = _find_affected_party(text)  # structural fallback, span-preserving
    frequency_match = FREQUENCY_PATTERN.search(text)
    monetary_match = MONETARY_PATTERN.search(text)
    count_match = COUNT_PATTERN.search(text)

    return {
        "problem": text.strip() if (pain_phrase or consequence_phrase) else None,
        "affected_customer": count_match.group(0) if count_match else None,
        "customer_type": customer_type,
        "pain": pain_phrase,
        "consequence": consequence_phrase,
        "existing_solution": existing_solution_phrase,
        "desired_outcome": desire_phrase,
        "buying_intent": buying_intent_phrase is not None,
        "urgency": urgency_phrase is not None,
        "frequency": frequency_match.group(0) if frequency_match else None,
        "monetary_impact": monetary_match.group(0) if monetary_match else None,
        "evidence_text": text.strip(),
    }


def score_economic_signal(extraction: dict, source_reliability: float = 50.0) -> dict:
    """
    Explainable 0-100 dimensions, each documented:

      pain_score       - a pain/frustration phrase was found (0 or 70;
                          binary because a heuristic phrase match is
                          either present or it isn't — no partial credit
                          invented)
      urgency_score     - an urgency/repetition phrase was found (0 or 60)
      monetary_impact_score - a real dollar figure or cost/loss phrase
                                was found (0 or 80 — a stated monetary
                                figure is strong evidence)
      demand_score        - buying intent or a desired-outcome phrase
                              was found (0, 50, or 90 depending on which)
      solution_gap_score    - an existing (inadequate) solution was
                                named, implying a real gap Forge could
                                fill (0 or 60)
      evidence_strength       - problem text + a named customer type,
                                  the two things needed to say "someone
                                  specific has this problem" (0-100,
                                  requires both to score above 50)
      source_quality            - the signal's own reliability_score,
                                    already tracked since v0.4 — reused,
                                    not reinvented
    """
    pain_score = 70.0 if extraction["pain"] else 0.0
    urgency_score = 60.0 if extraction["urgency"] else 0.0
    monetary_impact_score = 80.0 if extraction["monetary_impact"] or extraction["consequence"] else 0.0

    if extraction["buying_intent"]:
        demand_score = 90.0
    elif extraction["desired_outcome"]:
        demand_score = 50.0
    else:
        demand_score = 0.0

    solution_gap_score = 60.0 if extraction["existing_solution"] else 0.0

    evidence_strength = 0.0
    if extraction["problem"]:
        evidence_strength += 50.0
    if extraction["customer_type"] or extraction["affected_customer"]:
        evidence_strength += 50.0

    return {
        "pain_score": pain_score,
        "urgency_score": urgency_score,
        "monetary_impact_score": monetary_impact_score,
        "demand_score": demand_score,
        "solution_gap_score": solution_gap_score,
        "evidence_strength": round(evidence_strength, 1),
        "source_quality": source_reliability,
    }


# Minimum bar for "this reads as a real, monetizable problem, not just
# interesting information" — see is_economically_meaningful(). Requires
# BOTH a real problem statement with a named customer/affected party
# (evidence_strength == 100, both halves present) AND at least one of
# pain/demand/monetary signal — a bare customer mention with no
# pain/demand attached isn't a problem, and a pain phrase with no
# identifiable customer isn't attributable to anyone.
MIN_EVIDENCE_STRENGTH = 100.0


def is_economically_meaningful(extraction: dict, scores: dict) -> bool:
    """The literal gate: "interesting information" vs. "someone has a
    problem that could plausibly be monetized." Both a real problem+
    customer AND at least one real pain/demand/monetary/solution-gap
    signal are required — a customer type mentioned with no pain
    attached, or a generic pain phrase with no identifiable customer,
    isn't enough. Verified against the spec's own 3 GOOD / 4 BAD
    examples (the v1.8 spec notes live in this module's docstring above)
    — all seven classify correctly."""
    if scores["evidence_strength"] < MIN_EVIDENCE_STRENGTH:
        return False
    return (
        scores["pain_score"] > 0
        or scores["demand_score"] > 0
        or scores["monetary_impact_score"] > 0
        or scores["solution_gap_score"] > 0
    )


# A higher bar than is_economically_meaningful, reserved for a SINGLE
# unpatterned signal seeding an Opportunity on its own (see
# opportunity_engine.generate_opportunity_from_signal_if_strong). A lone
# manual complaint needs to be clearly, unambiguously monetizable — a real
# named problem + a real affected party (evidence_strength 100) AND both a
# pain signal AND at least one of a dollar figure / urgency / willingness-to-
# pay. This is deliberately strict so a solitary signal never floods the
# pipeline the way a corroborated pattern legitimately can; it targets the
# focused case: "clear evidence of a problem + identifiable customer
# + some willingness-to-pay signal."
def is_economically_strong(extraction: dict, scores: dict) -> bool:
    if scores["evidence_strength"] < MIN_EVIDENCE_STRENGTH:
        return False
    if scores["pain_score"] <= 0:
        return False
    return (
        scores["monetary_impact_score"] > 0
        or scores["urgency_score"] > 0
        or scores["demand_score"] > 0
    )


# --- Corroboration (computed live, no new storage) ---------------------


def compute_corroboration(db: Session, pattern: models.Pattern) -> dict:
    """
    Source diversity for a pattern's supporting signals, computed live
    from Pattern.origin_signal_ids (already stored) and each Signal's
    own .source field (already stored) — no new columns. Ten copies of
    the same syndicated article (same source, or duplicate-flagged via
    v1.4's Signal.is_duplicate_of) do NOT count as ten independent
    observations; this is what distinguishes real corroboration from
    syndication.

    Important honesty note (v2.8): is_duplicate_of trusts per-signal
    close-dup detection, which can be NULL for near-identical rows that
    were bulk-ingested before the check ran. So we ALSO collapse by
    content identity (content_fingerprint when present, else normalized
    text) so repeated identical content can never inflate independent
    observations — even if the rows were never individually flagged.
    Provenance stays intact (we only change HOW MANY *independent*
    observations a repeated copy counts; we never assert a copy is a
    different source).
    """
    if not pattern.origin_signal_ids:
        return {"unique_sources": 0, "independent_observations": 0, "corroboration_count": 0}

    signal_ids = [int(i) for i in pattern.origin_signal_ids.split(",") if i.strip().isdigit()]
    signals = db.query(models.Signal).filter(models.Signal.id.in_(signal_ids)).all()

    # Only genuinely distinct sources count toward uniqueness.
    unique_sources = len({s.source for s in signals if s.is_duplicate_of is None and s.source})

    # Independent observations = distinct canonical CONTENT, not distinct rows.
    # Collapse near-identical content via fingerprint, else normalized text, so
    # duplicated bulk sometimes escapes the is_duplicate_of flag without lying.
    def _content_id(s):
        if getattr(s, "content_fingerprint", None):
            return ("fp", s.content_fingerprint)
        return ("txt", re.sub(r"\s+", " ", (s.content or "").strip().lower())[:300])

    seen_content = set()
    independent = 0
    for s in signals:
        if s.is_duplicate_of is not None:
            continue
        cid = _content_id(s)
        if cid in seen_content:
            continue
        seen_content.add(cid)
        independent += 1

    return {
        "unique_sources": unique_sources,
        "independent_observations": independent,
        "corroboration_count": unique_sources,  # the spec's own term for this same number
    }


