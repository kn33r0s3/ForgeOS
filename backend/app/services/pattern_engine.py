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
  4. Merge theme pairs whose signal sets overlap heavily (Jaccard >= 0.5)
     via union-find, then merge keyword clusters that are near-identical
     (Jaccard >= 0.8) — so "slow", "reply", "response" become one pattern
     instead of three near-duplicates.
  5. Drop clusters with fewer than 4 theme keywords — a two-word fragment
     is not a separate concept.
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

    Clusters with fewer than 4 theme keywords are skipped silently —
    note this means a previously recorded pattern whose cluster decays
    below that floor keeps its last recorded state (no last_seen bump,
    no confidence refresh); retiring stale rows is a separate policy
    decision, not done here.
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

    for sig in signals:
        kws = _tokenize(sig.content)
        # Fold in Observer Engine tags (e.g. "customer support", "automation")
        # as extra keywords. Tags are pre-normalized short phrases, so two
        # signals sharing a tag cluster together even if their raw wording
        # differs — this is the Observer -> Pattern Engine connection.
        if sig.tags:
            kws |= {t.strip().lower() for t in sig.tags.split(",") if t.strip()}
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
        # Jaccard, not "small set inside a hub." A rare word that appears
        # beside a common word must not pull the whole vocabulary together.
        left, right = themes[kw_a], themes[kw_b]
        union_size = len(left | right)
        if union_size and len(left & right) / union_size >= 0.5:
            union(kw_a, kw_b)

    clusters: dict[str, set[str]] = defaultdict(set)  # root -> keywords
    for kw in theme_keys:
        clusters[find(kw)].add(kw)
    clusters = _merge_similar_keyword_sets(clusters)

    total_signals = len(signals)
    detected_patterns = []

    for root, keywords in clusters.items():
        supporting_signal_ids: set[int] = set()
        for kw in keywords:
            supporting_signal_ids |= themes[kw]

        if len(supporting_signal_ids) < MIN_CLUSTER_SIZE:
            continue

        # Identity is the whole sorted keyword set. A different order, or a
        # different slice of the same words, is not a new pattern.
        # A two-word fragment is not a separate concept. The shared set remains.
        if len(keywords) < 4:
            continue
        canonical_keywords = sorted(keywords)
        title = _build_title(canonical_keywords)
        description = _build_description(canonical_keywords, supporting_signal_ids, signals)
        frequency = len(supporting_signal_ids)
        independent = _independent_source_count(supporting_signal_ids, signals)

        base_confidence = min(95.0, (independent / max(total_signals, 1)) * 100 + independent * 5)
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


def _merge_similar_keyword_sets(clusters: dict[str, set[str]]) -> dict[str, set[str]]:
    """One extra or reordered token must not become a second concept."""
    items = list(clusters.items())
    parent = {key: key for key, _ in items}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def jaccard(left: set[str], right: set[str]) -> float:
        union = left | right
        return len(left & right) / len(union) if union else 0.0

    for index, (left_key, left_words) in enumerate(items):
        for right_key, right_words in items[index + 1:]:
            if jaccard(left_words, right_words) >= 0.8:
                parent[find(left_key)] = find(right_key)
    merged: dict[str, set[str]] = defaultdict(set)
    for key, words in items:
        merged[find(key)] |= words
    return merged


def _independent_source_count(signal_ids: set[int], signals: list[models.Signal]) -> int:
    """Copies of one URL or one body are one source, not many confirmations."""
    seen = set()
    for signal in signals:
        if signal.id not in signal_ids:
            continue
        seen.add((signal.source or "", signal.canonical_url or (signal.content or "").strip()))
    return len(seen)


def _build_title(keywords: list[str]) -> str:
    words = ", ".join(sorted(keywords))
    return f"Recurring theme: {words}"


# Bibliographic/metadata terms that, when dominant in a pattern whose signals
# come primarily from scholarly APIs, indicate a background observation rather
# than a real-world problem. This is not a blacklist — legitimate literature
# research with geographic/population context is preserved.
_BIBLIOGRAPHIC_TERMS = frozenset({
    "crossref", "metadata", "record", "records", "evidence", "bibliographic",
    "citation", "citations", "doi", "openalex", "scholarly", "bibliography",
})

_SCHOLARLY_SOURCES = frozenset({"crossref", "openalex", "world_bank", "gdelt", "govinfo"})


def _is_bibliographic_background(keywords: list[str], signal_ids: set[int], signals: list[models.Signal]) -> bool:
    """Detect patterns that are pure bibliographic metadata, not real-world problems.

    A pattern is classified as background if:
    1. The majority of its keywords are bibliographic/metadata terms, AND
    2. The majority of its supporting signals come from scholarly/bibliographic APIs.

    This preserves legitimate literature research that has geographic or
    population context (those patterns won't have bibliographic-dominant keywords).
    """
    if not keywords or not signal_ids:
        return False

    # Check keyword dominance
    biblio_kw_count = sum(1 for kw in keywords if kw.lower() in _BIBLIOGRAPHIC_TERMS)
    if biblio_kw_count < len(keywords) / 2:
        return False

    # Check source dominance
    signal_map = {s.id: s for s in signals}
    scholarly_count = 0
    total = 0
    for sid in signal_ids:
        sig = signal_map.get(sid)
        if sig and sig.source:
            total += 1
            if sig.source.lower() in _SCHOLARLY_SOURCES:
                scholarly_count += 1

    if total == 0:
        return False

    return scholarly_count >= total / 2


def _build_description(keywords: list[str], signal_ids: set[int], signals: list[models.Signal]) -> str:
    examples = [s.content for s in signals if s.id in signal_ids][:3]
    examples_text = " | ".join(f'"{e.strip()}"' for e in examples)
    kw_text = ", ".join(keywords)
    # Classify bibliographic background observations clearly
    prefix = ""
    if _is_bibliographic_background(keywords, signal_ids, signals):
        prefix = "[BIBLIOGRAPHIC BACKGROUND] "
    return (
        f"{prefix}{len(signal_ids)} signals repeatedly mention: {kw_text}. "
        f"Examples: {examples_text}"
    )
