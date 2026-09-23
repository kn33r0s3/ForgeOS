"""
SIGNAL PROCESSOR
=================

Turns raw observed text into a structured shape the rest of Forge can
use: a normalized version of the text, a best-guess category, a
best-guess signal_type, and a small set of tags.

Deliberately dictionary/keyword based — no embeddings, no external
model calls — so it stays fast and free and runs comfortably on a
laptop with 16GB RAM. This is the same tradeoff pattern_engine.py
already makes; signal_processor is the per-signal counterpart to it.
"""

import re

# Tag name -> trigger words/substrings that imply that tag.
# Substring matching on the lowercased text (not strict word-boundary)
# so plurals ("restaurants", "customers") match for free.
TAG_KEYWORDS: dict[str, list[str]] = {
    "restaurant": ["restaurant", "cafe", "diner", "eatery"],
    "customer support": ["support", "call", "calls", "respond", "response", "customer service", "hold"],
    "lost revenue": ["lose", "losing", "lost", "revenue", "money"],
    "automation": ["manual", "repetitive", "automate", "automation", "tedious", "time-consuming"],
    "marketing": ["marketing", "advertis", "promot", "brand"],
    "pricing": ["price", "pricing", "expensive", "afford", "cost", "costly"],
    "small business": ["small business", "small businesses", "startup", "solo", "freelance"],
    "income opportunity": ["make money", "income", "side hustle", "earn"],
    "trust": ["trustworthy", "scam", "legitimate", "trust"],
    "hiring": ["hire", "hiring", "employee", "staff", "job"],
    "software": ["app", "software", "platform", "tool", "website"],
}

DEMAND_WORDS = ["want", "wish", "looking for", "need a", "would love", "wish there was"]
PAIN_WORDS = [
    "lose", "losing", "lost", "problem", "problems", "struggle", "struggling",
    "expensive", "difficult", "waste", "wasting", "cannot", "can't", "slow",
    "frustrat", "manual", "repetitive", "tedious",
]


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip stray punctuation at the
    edges. Keeps the text readable (unlike a full tokenizer) since it's
    used for both display and keyword matching."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def extract_basic_tags(text: str) -> list[str]:
    """Match the normalized text against TAG_KEYWORDS and return every
    tag whose trigger words appear. Order is insertion order of
    TAG_KEYWORDS, so results are stable and deterministic."""
    normalized = normalize_text(text)
    tags = []
    for tag, triggers in TAG_KEYWORDS.items():
        if any(trigger in normalized for trigger in triggers):
            tags.append(tag)
    return tags


def _guess_signal_type(normalized_text: str) -> str:
    """Very small heuristic classifier:
    - "demand"      : someone explicitly wants/is looking for something
    - "problem"      : pain/friction language is present
    - "observation"   : neither — a neutral note/fact
    """
    if any(word in normalized_text for word in DEMAND_WORDS):
        return "demand"
    if any(word in normalized_text for word in PAIN_WORDS):
        return "problem"
    return "observation"


def _guess_category(tags: list[str]) -> str:
    """Use the first matched tag as the category, or "general" if none
    matched. Keeps `category` (used elsewhere in Forge, e.g. for
    filtering) populated even for free-text input with no manual tag."""
    return tags[0] if tags else "general"


def process_signal(content: str) -> dict:
    """
    Run the full processing pipeline on one piece of raw text.

    Returns a dict with:
      normalized_text : str
      tags             : list[str]
      category          : str
      signal_type        : "problem" | "demand" | "observation"
    """
    normalized = normalize_text(content)
    tags = extract_basic_tags(content)
    return {
        "normalized_text": normalized,
        "tags": tags,
        "category": _guess_category(tags),
        "signal_type": _guess_signal_type(normalized),
    }
