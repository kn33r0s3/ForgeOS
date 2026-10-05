"""
IMPORTANCE RANKER
==================

Scores a raw signal 0-100 on how likely it is to represent a real,
worthwhile business opportunity — using plain keyword weighting, not
a model call. This keeps Forge free to run and fast even on modest
hardware (Ryzen 3 / 16GB class laptops), and keeps the scoring logic
fully transparent and inspectable/tunable, unlike a black-box model
score.

Three indicator categories, matching the spec:
  - Pain indicators     : lose, problem, struggle, expensive, difficult, waste, cannot...
  - Business indicators  : customer, money, revenue, company, business...
  - Urgency indicators    : need, immediately, critical...

Score = base + weighted matches per category (each category capped so
one repeated word can't dominate the score), clamped to [0, 100].
"""

import re

PAIN_INDICATORS = [
    "lose", "losing", "lost", "problem", "problems", "struggle", "struggling",
    "expensive", "difficult", "waste", "wasting", "cannot", "can't", "slow",
    "frustrating",
]
BUSINESS_INDICATORS = [
    "customer", "customers", "money", "revenue", "company", "companies",
    "business", "businesses", "client", "clients", "sales",
]
URGENCY_INDICATORS = [
    "need", "needs", "immediately", "critical", "urgent", "asap",
]

BASE_SCORE = 25.0

PAIN_WEIGHT = 18.0
BUSINESS_WEIGHT = 12.0
URGENCY_WEIGHT = 20.0

PAIN_CAP = 40.0
BUSINESS_CAP = 30.0
URGENCY_CAP = 30.0


def _count_matches(text: str, indicators: list[str]) -> int:
    """Count how many distinct indicator words/phrases appear in the
    text (substring match, so plurals like 'businesses' still match
    'business'). Each indicator counts at most once, even if repeated,
    so a signal can't inflate its score by repetition alone."""
    return sum(1 for word in indicators if word in text)


def score_breakdown(content: str) -> dict:
    """Return the full scoring breakdown — useful for debugging/tuning
    and for anything (like a future admin view) that wants to show why
    a signal scored the way it did."""
    text = re.sub(r"\s+", " ", content.strip().lower())

    pain_matches = _count_matches(text, PAIN_INDICATORS)
    business_matches = _count_matches(text, BUSINESS_INDICATORS)
    urgency_matches = _count_matches(text, URGENCY_INDICATORS)

    pain_score = min(PAIN_CAP, pain_matches * PAIN_WEIGHT)
    business_score = min(BUSINESS_CAP, business_matches * BUSINESS_WEIGHT)
    urgency_score = min(URGENCY_CAP, urgency_matches * URGENCY_WEIGHT)

    raw_total = BASE_SCORE + pain_score + business_score + urgency_score
    total = round(min(100.0, raw_total), 1)

    return {
        "score": total,
        "pain_matches": pain_matches,
        "business_matches": business_matches,
        "urgency_matches": urgency_matches,
        "pain_score": pain_score,
        "business_score": business_score,
        "urgency_score": urgency_score,
        "base_score": BASE_SCORE,
    }


def score_importance(content: str) -> float:
    """Convenience entry point most callers want: just the 0-100 score."""
    return score_breakdown(content)["score"]
