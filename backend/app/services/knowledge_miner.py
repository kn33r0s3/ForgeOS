"""
KNOWLEDGE MINING ENGINE
=========================

Ingests long-form text — books, papers, stories, public writing — and
extracts sentences that read like strategies, human-behavior claims,
or problem-solving patterns. Each extracted sentence becomes a Signal
via the normal Observer Engine pipeline, so a repeated insight across
multiple mined texts becomes a Pattern -> Belief exactly like a
repeated real-world complaint does. No new pipeline was needed — this
is just a new front door into the existing one.

Sentence selection is keyword-triggered, not model-based (same
tradeoff as everywhere else in Forge): a sentence is kept if it
contains phrasing that tends to signal a generalized claim about how
to act or how people behave ("the key is...", "people tend to...",
"never..."), and is a reasonable single-sentence length.
"""

import re

from sqlalchemy.orm import Session

from app.services.observer_engine import ObserverEngine

INSIGHT_MARKERS = [
    "always", "never", "people tend to", "the key is", "the secret is",
    "in order to succeed", "the best way to", "strategy", "rule of thumb",
    "if you want to", "the biggest mistake", "successful people",
    "the trick is", "what works is", "the reason most", "most people",
]

MIN_SENTENCE_WORDS = 6
MAX_SENTENCE_WORDS = 40


def extract_insights(text: str) -> list[str]:
    """Split text into sentences and keep the ones that read like a
    strategy / behavior claim / problem-solving pattern."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    insights = []

    for raw_sentence in sentences:
        sentence = raw_sentence.strip()
        word_count = len(sentence.split())
        if word_count < MIN_SENTENCE_WORDS or word_count > MAX_SENTENCE_WORDS:
            continue

        lowered = sentence.lower()
        if any(marker in lowered for marker in INSIGHT_MARKERS):
            insights.append(sentence)

    return insights


def mine_document(db: Session, text: str, source_label: str = "book") -> list[int]:
    """Extract insights from a long document and store each as a
    Signal via ObserverEngine, tagged with the given source label
    (e.g. "book", "paper", or a custom label). Returns the created
    Signal ids."""
    observer = ObserverEngine(db)
    insights = extract_insights(text)

    created_ids = []
    for insight in insights:
        signal = observer.observe(insight, source=source_label)
        created_ids.append(signal.id)

    return created_ids
