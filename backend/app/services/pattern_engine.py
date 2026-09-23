"""
PATTERN ENGINE
==============

Finds repeated problems across stored Signals without any heavy
ML dependency (no numpy/sklearn/torch) — deliberately, to keep RAM
and install size low enough for a low-end laptop. It uses simple word
frequency + co-occurrence clustering:

  1. Tokenize every signal into meaningful keywords (stopwords removed).
  2. Count how many DISTINCT signals each keyword appears in.
  3. Keywords appearing in >= MIN_SIGNAL_SUPPORT signals are treated as
     "themes".
  4. Group signals sharing a theme keyword into a cluster.
  5. Merge overlapping clusters (signals sharing >=2 theme keywords)
     into a single pattern.
  6. Build a human-readable title/description and a confidence score
     from cluster size vs. total signal count, and record the exact
     supporting Signal ids as the pattern's origin (origin_signal_ids)
     for traceability — this is what forge_loop.py used to have to
     approximate by re-matching keywords; now it's exact and direct.

This is a heuristic, not a language model — it's meant to be fast,
free, and good enough to bootstrap the opportunity engine. It can be
swapped for an embedding-based clustering approach later without
changing its public function signature (`run_pattern_detection`).
"""

import re
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

from sqlalchemy.orm import Session

from app import models


def utcnow():
    return datetime.now(timezone.utc)

MIN_SIGNAL_SUPPORT = 2  # a keyword must appear in >=2 signals to count as a theme
MIN_CLUSTER_SIZE = 2    # a pattern needs >=2 supporting signals

# Signals below this quality (or flagged as duplicates) don't
# contribute to clustering — see signal_quality.py's module docstring
# for the full reasoning ("if garbage enters at Signals, everything
# downstream can become confidently wrong"). Duplicated as a literal
# here rather than imported: signal_quality.py already imports
# tokenize FROM this module, so importing signal_quality.py back here
# would create a circular import. Keep this value in sync with
# signal_quality.MIN_QUALITY_FOR_PATTERN if either ever changes.
MIN_QUALITY_FOR_PATTERN = 40.0

# Bulk high-volume sources that mainly carry informational content (news
# wire, research dumps, changelog activity) rather than expressed demand,
# complaints, or pain. A pattern whose supporting signals are dominated by
# one such source is usually a broad "around-the-water-cooler" theme (e.g.
# "software / business / customer support") that repeats purely because the
# feed is large — not because real people keep hitting a monetizable
# problem. We don't delete or hide those patterns (provenance is preserved);
# we only deprioritize them for ranking so genuine, specific pains aren't
# drowned by bulk volume. This is consistent with everything else in Forge:
# a transparent, documented, $0 heuristic — no model call, easy to swap.
BULK_NEUTRAL_SOURCES = {"rss", "arxiv", "github"}
BULK_NEUTRAL_DOMINANCE_PENALTY = 0.35  # multiplicative confidence haircut when dominated

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "because", "so", "of", "to", "in",
    "on", "for", "with", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "this", "that", "these", "those", "they", "them", "their",
    "we", "our", "you", "your", "i", "he", "she", "his", "her", "as", "at",
    "by", "from", "than", "then", "too", "very", "can", "cannot", "cant",
    "not", "no", "do", "does", "did", "have", "has", "had", "will", "would",
    "should", "could", "about", "into", "out", "up", "down", "over", "under",
    "again", "there", "here", "when", "where", "why", "how", "all", "any",
    "both", "each", "more", "most", "other", "some", "such", "only", "own",
    "same", "just", "get", "gets", "getting",
}


def tokenize(text: str) -> set[str]:
    """Extract meaningful keywords from text (stopwords removed, 3+
    letters). Public so other modules — e.g. reality_checker.py, which
    needs to compare a Belief statement's keywords against Signals —
    can reuse the same keyword logic instead of duplicating it."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


# Kept as an alias: the rest of this file was written against the
# private name before tokenize() was made public for reuse elsewhere.
_tokenize = tokenize


def run_pattern_detection(db: Session) -> list[models.Pattern]:
    """
    Analyze QUALITY-GATED signals, detect repeated themes, and persist
    them as Pattern rows. Idempotent by title: if a cluster with the
    same top keywords already has a Pattern row, it's updated in place
    (frequency, confidence, origin, last_seen) rather than duplicated —
    re-running this on every worker.py cycle doesn't pile up near-
    identical rows over time.

    Signals with quality_score below MIN_QUALITY_FOR_PATTERN, or
    flagged as a duplicate of another signal (v1.4, see
    signal_quality.py), are excluded from clustering — they're never
    deleted or hidden from the raw signal list, just kept from
    confidently seeding a Pattern/Belief/Opportunity chain built on
    noise. Signals observed before v1.4 have quality_score = NULL and
    are treated as acceptable (not penalized for predating the check).
    """
    signals = (
        db.query(models.Signal)
        .filter(
            models.Signal.is_duplicate_of.is_(None),
            (models.Signal.quality_score.is_(None))
            | (models.Signal.quality_score >= MIN_QUALITY_FOR_PATTERN),
        )
        .all()
    )
    if len(signals) < MIN_CLUSTER_SIZE:
        return []

    # keyword -> set of signal ids containing it
    keyword_to_signals: dict[str, set[int]] = defaultdict(set)
    signal_keywords: dict[int, set[str]] = {}

    for sig in signals:
        kws = _tokenize(sig.content)
        # Fold in Observer Engine tags (e.g. "customer support", "automation")
        # as extra keywords. Tags are pre-normalized short phrases, so two
        # signals sharing a tag cluster together even if their raw wording
        # differs — this is the Observer -> Pattern Engine connection.
        if sig.tags:
            kws |= {t.strip().lower() for t in sig.tags.split(",") if t.strip()}
        signal_keywords[sig.id] = kws
        for kw in kws:
            keyword_to_signals[kw].add(sig.id)

    # Keep only keywords that show up across multiple distinct signals —
    # these are candidate "themes".
    themes = {
        kw: sig_ids
        for kw, sig_ids in keyword_to_signals.items()
        if len(sig_ids) >= MIN_SIGNAL_SUPPORT
    }

    if not themes:
        return []

    # Merge themes whose signal sets overlap heavily into single clusters,
    # so "slow", "reply", "response" don't produce three near-duplicate
    # patterns when they're really describing one problem.
    theme_keys = list(themes.keys())
    parent = {k: k for k in theme_keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for kw_a, kw_b in combinations(theme_keys, 2):
        overlap = themes[kw_a] & themes[kw_b]
        smaller = min(len(themes[kw_a]), len(themes[kw_b]))
        if smaller and len(overlap) / smaller >= 0.5:
            union(kw_a, kw_b)

    clusters: dict[str, set[str]] = defaultdict(set)  # root -> keywords
    for kw in theme_keys:
        clusters[find(kw)].add(kw)

    total_signals = len(signals)
    detected_patterns = []

    for root, keywords in clusters.items():
        supporting_signal_ids: set[int] = set()
        for kw in keywords:
            supporting_signal_ids |= themes[kw]

        if len(supporting_signal_ids) < MIN_CLUSTER_SIZE:
            continue

        top_keywords = sorted(keywords, key=lambda k: -len(themes[k]))[:4]
        title = _build_title(top_keywords)
        description = _build_description(top_keywords, supporting_signal_ids, signals)
        frequency = len(supporting_signal_ids)

        base_confidence = min(95.0, (frequency / total_signals) * 100 + frequency * 5)
        # Small boost from how important the Observer Engine judged the
        # supporting signals to be — a pattern built from high-importance
        # signals is more likely to be worth acting on than one built from
        # low-importance noise, even at the same frequency.
        avg_importance = _average_importance(supporting_signal_ids, signals)
        importance_boost = (avg_importance / 100) * 10  # up to +10 points
        confidence = round(min(95.0, base_confidence + importance_boost), 1)

        # Bulk-neutal-source de-prioritization: if the pattern's supporting
        # signals are overwhelmingly from one high-volume informational feed
        # (rss/arxiv/github), a large chunk of its confidence is pure volume,
        # not corroborated human pain. Haircut it so generic themes don't rank
        # at the top purely because the feed is enormous.
        dominance = _bulk_dominance(supporting_signal_ids, signals)
        if dominance >= 0.75:
            confidence = round(confidence * BULK_NEUTRAL_DOMINANCE_PENALTY, 1)

        pattern = (
            db.query(models.Pattern).filter(models.Pattern.title == title).first()
        )
        if pattern:
            # Same keyword cluster re-detected (e.g. the next worker.py
            # cycle) — update it in place instead of inserting a
            # duplicate row. This is the fix for a bug that's been
            # sitting in the roadmap: patterns used to pile up
            # unboundedly every cycle. Matching on title is a
            # deliberate heuristic, not a perfect key — same tradeoff
            # as everywhere else in Forge (good enough, free, no model
            # call) — see the module docstring.
            pattern.description = description
            pattern.frequency = frequency
            pattern.confidence_score = confidence
            pattern.origin_signal_ids = ",".join(str(i) for i in sorted(supporting_signal_ids))
            pattern.last_seen = utcnow()
        else:
            pattern = models.Pattern(
                title=title,
                description=description,
                frequency=frequency,
                confidence_score=confidence,
                origin_signal_ids=",".join(str(i) for i in sorted(supporting_signal_ids)),
            )
            db.add(pattern)
        detected_patterns.append(pattern)

    db.commit()
    for p in detected_patterns:
        db.refresh(p)

    # Sort strongest pattern first for downstream consumers.
    detected_patterns.sort(key=lambda p: p.confidence_score, reverse=True)
    return detected_patterns


def _average_importance(signal_ids: set[int], signals: list[models.Signal]) -> float:
    """Average Observer Engine importance_score across a set of
    supporting signals. Defaults to 0 for signals scored before the
    Observer Engine existed (importance_score defaults to 0.0)."""
    scores = [s.importance_score or 0.0 for s in signals if s.id in signal_ids]
    return sum(scores) / len(scores) if scores else 0.0


def _bulk_dominance(signal_ids: set[int], signals: list[models.Signal]) -> float:
    """Fraction (0..1) of a pattern's supporting signals that come from
    bulk high-volume neutral sources (rss/arxiv/github). Used to cap how
    much raw frequency may inflate a generic theme's confidence. If the
    source field is unknown/missing we count it as neutral-safe (treat it
    as non-bulk) so we never penalize something we can't attribute."""
    if not signal_ids:
        return 0.0
    by_source = {s.id: (s.source or "") for s in signals if s.id in signal_ids}
    if not by_source:
        return 0.0
    bulk = sum(1 for sid in by_source if by_source.get(sid) in BULK_NEUTRAL_SOURCES)
    return bulk / len(by_source)


def _build_title(keywords: list[str]) -> str:
    words = ", ".join(keywords)
    return f"Recurring theme: {words}"


def _build_description(keywords: list[str], signal_ids: set[int], signals: list[models.Signal]) -> str:
    examples = [s.content for s in signals if s.id in signal_ids][:3]
    examples_text = " | ".join(f'"{e.strip()}"' for e in examples)
    kw_text = ", ".join(keywords)
    return (
        f"{len(signal_ids)} signals repeatedly mention: {kw_text}. "
        f"Examples: {examples_text}"
    )
