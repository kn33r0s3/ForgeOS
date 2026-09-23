"""
SIGNAL QUALITY ENGINE
=======================

Forge's chain is Reality -> Signals -> Patterns -> Beliefs ->
Opportunities -> Money. If garbage enters at Signals, everything
downstream can become confidently wrong: Pattern Engine would cluster
noise, Belief Engine would form beliefs from it, and the Money Engine
would rank opportunities that were never real. The Money Engine's own
scoring stayed honest (a garbage opportunity correctly scored
money_score=0, since it had zero real evidence) — but nothing upstream
stopped the garbage from becoming a confident-looking Signal and a
fully-written Opportunity in the first place. This module is that stop.

Every signal gets a quality assessment at the moment it's observed
(see observer_engine.py), and Pattern Engine refuses to build patterns
from signals below MIN_QUALITY_FOR_PATTERN or flagged as duplicates
(see pattern_engine.py's filter). Signals are NEVER discarded — Forge
never silently drops a real observation — they're just excluded from
contributing to Patterns/Beliefs/Opportunities until/unless a human
reviews them. This mirrors the append-only principle every other part
of Forge already follows.

Heuristic, not a model call — same tradeoff as every other scoring
engine in Forge. Five dimensions, each 0-100, combined transparently,
with two hard caps for genuinely disqualifying flags (near-duplicate,
incoherent) so they can't be masked by unrelated factors happening to
be fine:

  1. Concreteness  - does this read like a specific observation (a
                      number, several distinct content words) or a
                      vague, generic claim ("I need to make money asap")?
  2. Coherence      - is this one real thought, or multiple unrelated
                       fragments mashed together (a classic paste-error
                       pattern — e.g. a bare number sitting between two
                       unrelated sentences)?
  3. Duplication    - has Forge already seen this, or something nearly
                       identical? A near-duplicate isn't new evidence,
                       it's the same evidence counted twice.
  4. Signal type strength - an "observation"/"problem" (something that
                             happened) is stronger evidence than a
                             "demand" (someone wants something) — reuses
                             signal_processor.py's existing classifier,
                             doesn't reclassify.
  5. Length sanity   - too short to contain real content, or
                        implausibly long for one observation.

Source reliability is deliberately NOT re-weighted here — it's already
tracked on the Signal itself (reliability_score, snapshotted from
source_manager.py at observe time) and folded in as one modest factor,
not duplicated as a separate system.
"""

import re

from sqlalchemy.orm import Session

from app import models
from app.services.pattern_engine import tokenize
from typing import Optional

# Signals below this don't contribute to Pattern clustering — see
# pattern_engine.py. Duplicated there as a literal (not imported) to
# avoid a circular import: this module already imports tokenize FROM
# pattern_engine.py, so pattern_engine.py importing this module back
# would create a cycle. A single float constant is cheap to keep in
# sync; the alternative (restructuring where tokenize lives) touches
# more of a working system than this fix warrants.
MIN_QUALITY_FOR_PATTERN = 40.0

DUPLICATE_JACCARD_THRESHOLD = 0.75  # keyword-overlap ratio above which two signals count as near-duplicates
RECENT_DUPLICATE_CHECK_LIMIT = 500  # bounds the comparison to keep this fast on modest hardware, not O(all signals ever)

VAGUE_PHRASES = [
    "make money", "need money", "asap", "help me", "i need", "solve this",
    "get rich", "quick cash", "side hustle", "passive income",
]
DIGIT_PATTERN = re.compile(r"\d")


def _concreteness_score(text: str) -> float:
    """0-100. Rewards specifics (a number, several distinct content
    words), penalizes generic filler phrasing with nothing concrete
    behind it."""
    lowered = text.lower()
    keywords = tokenize(text)

    score = 30.0  # baseline: any tokenizable content starts here
    if DIGIT_PATTERN.search(text):
        score += 20.0  # a count, date, price, percentage — real specificity
    if len(keywords) >= 6:
        score += 25.0
    elif len(keywords) >= 3:
        score += 10.0

    vague_hits = sum(1 for phrase in VAGUE_PHRASES if phrase in lowered)
    score -= min(40.0, vague_hits * 15.0)

    return round(max(0.0, min(100.0, score)), 1)


def _coherence_score(text: str) -> float:
    """0-100. Flags classic paste-error patterns: a bare number sitting
    in the middle of prose, or multiple sentence-like fragments with no
    shared vocabulary (a sign of unrelated text concatenated together
    rather than one real observation).

    Multi-sentence observations about the same domain (e.g. restaurant
    + order + tickets across sentences) are treated as coherent even if
    no single keyword appears in every fragment.
    """
    fragments = [f.strip() for f in re.split(r"[\n.!?]+", text) if f.strip()]
    if len(fragments) <= 1:
        return 100.0

    if any(re.fullmatch(r"\d+", f) for f in fragments):
        return 30.0

    fragment_keywords = [tokenize(f) for f in fragments if len(f.split()) >= 2]
    if len(fragment_keywords) >= 2:
        shared = set.intersection(*fragment_keywords) if fragment_keywords else set()
        if shared:
            return 90.0
        # Pairwise overlap: if most adjacent fragments share at least one keyword, coherent
        pairwise_ok = 0
        for a, b in zip(fragment_keywords, fragment_keywords[1:]):
            if a & b:
                pairwise_ok += 1
        if pairwise_ok >= max(1, len(fragment_keywords) - 2):
            return 75.0
        # All keywords across document — if total unique is rich, likely one topic
        all_kw = set.union(*fragment_keywords) if fragment_keywords else set()
        if len(all_kw) >= 8:
            return 70.0
        return 45.0

    return 80.0


def _length_score(text: str) -> float:
    """0-100. Too short to be meaningful, or implausibly long for a
    single observation (more likely several ideas pasted together)."""
    word_count = len(text.split())
    if word_count < 4:
        return 20.0
    if word_count > 120:
        return 60.0
    return 100.0


def _signal_type_strength(signal_type: Optional[str]) -> float:
    """0-100. An observed fact/problem is stronger evidence than a
    stated want."""
    return {"observation": 90.0, "problem": 90.0, "demand": 60.0}.get(signal_type or "", 60.0)


def find_duplicate(db: Session, content: str) -> Optional[models.Signal]:
    """Check recent signals for an exact or near-duplicate match.
    Bounded to the most recent RECENT_DUPLICATE_CHECK_LIMIT signals — a
    personal, local Forge instance doesn't need (and shouldn't pay the
    cost of) an O(all signals ever) comparison on every observation."""
    normalized = re.sub(r"\s+", " ", content.strip().lower())
    keywords = tokenize(content)
    if not keywords:
        return None

    recent = (
        db.query(models.Signal)
        .order_by(models.Signal.timestamp.desc())
        .limit(RECENT_DUPLICATE_CHECK_LIMIT)
        .all()
    )
    for existing in recent:
        existing_normalized = re.sub(r"\s+", " ", existing.content.strip().lower())
        if existing_normalized == normalized:
            return existing
        existing_keywords = tokenize(existing.content)
        if not existing_keywords:
            continue
        overlap = keywords & existing_keywords
        union = keywords | existing_keywords
        jaccard = len(overlap) / len(union) if union else 0.0
        if jaccard >= DUPLICATE_JACCARD_THRESHOLD:
            return existing
    return None


def assess_quality(db: Session, content: str, signal_type: Optional[str], reliability_score: float) -> dict:
    """
    Full quality assessment for a piece of content BEFORE it's stored
    as a Signal — computed synchronously, all heuristic, all $0.
    Returns a composite quality_score (0-100), a list of human-readable
    flags (so the reasoning is inspectable, not a black-box number),
    and the id of the duplicate signal if one was found.

    Two hard caps apply after the weighted average: a near-duplicate or
    an incoherent (paste-error) signal is capped low REGARDLESS of
    other factors — a genuinely broken signal shouldn't sneak through
    with a passable composite score just because its length or source
    reliability happen to be fine.
    """
    flags: list[str] = []

    duplicate = find_duplicate(db, content)
    duplicate_score = 0.0 if duplicate else 100.0
    if duplicate:
        flags.append(f"duplicate_of_signal_{duplicate.id}")

    concreteness = _concreteness_score(content)
    if concreteness < 40.0:
        flags.append("vague_no_specifics")

    coherence = _coherence_score(content)
    if coherence < 60.0:
        flags.append("incoherent_fragments")

    length = _length_score(content)
    if length < 50.0:
        flags.append("too_short")
    elif length < 80.0:
        flags.append("unusually_long")

    type_strength = _signal_type_strength(signal_type)

    weighted = (
        concreteness * 0.30
        + coherence * 0.25
        + duplicate_score * 0.20
        + type_strength * 0.10
        + length * 0.10
        + reliability_score * 0.05
    )

    quality_score = weighted
    if duplicate:
        quality_score = min(quality_score, 25.0)
    if coherence < 50.0:
        quality_score = min(quality_score, 35.0)
    quality_score = round(max(0.0, min(100.0, quality_score)), 1)

    return {
        "quality_score": quality_score,
        "quality_flags": flags,
        "duplicate_of_signal_id": duplicate.id if duplicate else None,
    }
