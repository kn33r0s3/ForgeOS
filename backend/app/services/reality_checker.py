"""
REALITY CHECKER
=================

Challenges an existing Belief against the current pool of Signals.
This is what keeps Forge honest — a belief formed once from an early
pattern shouldn't just sit at its initial confidence forever; new
evidence should be able to strengthen OR weaken it.

Method (heuristic, no model call — same tradeoff as pattern_engine.py
and importance_ranker.py):

  1. Extract keywords from the belief's statement.
  2. Find signals that share at least one keyword.
  3. Classify each matching signal as supporting or contradicting
     based on whole-word sentiment word lists (want/need/adopt vs.
     avoid/refuse/distrust), with a negation guard ("don't want" is not
     support), falling back to "supporting" if the signal's
     Observer-assigned type is "problem" (a real complaint is evidence
     the underlying issue is real).
  4. Weight each matching signal by its own reliability_score (a
     snapshot of its source's trustworthiness at observe time — see
     ObserverEngine.observe()) rather than counting every signal
     equally. A signal from a 90%-reliable manual observation should
     move confidence more than one from a 40%-reliable web scrape. This
     was a real gap until now: reliability previously only affected
     things AFTER a Prediction resolved (reality_memory.py), not the
     evidence-weighing itself.
  5. Compute a confidence_change from the weighted support/contradict
     totals (each capped so one repeated word — or one source — can't
     dominate) and apply it via BeliefEngine.

Signal ≠ Truth, Pattern ≠ Proof, Belief ≠ Reality — this function is
the mechanism that's supposed to keep that distinction real rather
than aspirational: beliefs can and do lose confidence here.
"""

from sqlalchemy.orm import Session
from typing import Optional

from app import models
from app.services import belief_engine, reality_memory
from app.services.pattern_engine import tokenize

import re

POSITIVE_WORDS = ["want", "need", "adopt", "love", "prefer", "willing", "pay for"]
NEGATIVE_WORDS = ["avoid", "refuse", "distrust", "reject", "against", "won't", "wont", "skeptical"]

# Word-boundary regexes so sentiment words match whole words only —
# "want" must not fire inside "unwanted", "need" inside "needle".
_WORD_PATTERN = {word: re.compile(r"\b" + re.escape(word) + r"\b") for word in POSITIVE_WORDS + NEGATIVE_WORDS}

# A sentiment word preceded by a negation within a few tokens says the
# opposite of its surface reading ("customers don't want this" is not
# support). Negated sentiment words count as neither support nor
# contradict — better no classification than a wrong one.
_NEGATION_WORDS = {
    "not", "no", "never", "cannot", "can't", "dont", "don't", "didnt", "didn't",
    "doesnt", "doesn't", "isnt", "isn't", "arent", "aren't", "wont", "won't",
    "without", "hardly", "barely", "neither", "nor",
}
_NEGATION_WINDOW = 3


def _classify_sentiment(text: str) -> Optional[str]:
    """Classify signal text as 'supports', 'contradicts', or None.

    Whole-word matching with a negation guard: a sentiment word that is
    negated within the preceding few tokens ("don't want", "not willing")
    is not counted as evidence in either direction.
    """
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9']+", lowered)
    # map each token index to the sentiment words it matches
    matched_at: dict[int, list[str]] = {}
    for word in POSITIVE_WORDS + NEGATIVE_WORDS:
        for m in _WORD_PATTERN[word].finditer(lowered):
            # locate the token index containing this match start
            idx = len(re.findall(r"[a-z0-9']+", lowered[: m.start()]))
            matched_at.setdefault(idx, []).append(word)

    direction: Optional[str] = None
    for idx, words in matched_at.items():
        window = tokens[max(0, idx - _NEGATION_WINDOW) : idx]
        if any(tok in _NEGATION_WORDS or tok.endswith("n't") for tok in window):
            continue  # negated — says the opposite of its surface reading
        for word in words:
            if word in NEGATIVE_WORDS:
                return "contradicts"  # negative sentiment dominates
            direction = "supports"
    return direction

SUPPORT_WEIGHT = 4.0
CONTRADICT_WEIGHT = 6.0  # contradicting evidence counts for more — protects against overconfidence
SUPPORT_CAP = 20.0
CONTRADICT_CAP = 25.0


def check_belief(db: Session, belief: models.Belief, signals: Optional[list] = None) -> dict:
    """Re-score one Belief against all current signals. Applies the
    resulting confidence_change and returns a breakdown.

    `signals` may be supplied by the caller to avoid re-loading the full
    signal table on every belief (the forge loop checks up to 200 beliefs
    per cycle). When omitted, the table is loaded here.
    """
    keywords = tokenize(belief.statement)
    if signals is None:
        signals = db.query(models.Signal).all()

    evidence: list[dict] = []
    support_weight_sum = 0.0
    contradict_weight_sum = 0.0

    for sig in signals:
        text = sig.content.lower()
        sig_keywords = tokenize(sig.content)
        if not (keywords & sig_keywords):
            continue  # not relevant to this belief

        # A signal's reliability_score (0-100, snapshotted from its
        # source at observe time) becomes its evidence WEIGHT, not just
        # a count of 1. reliability_score defaults to 50.0 if somehow
        # unset, so pre-Source-Engine signals still contribute at a
        # neutral weight rather than erroring or being skipped. (None
        # check, not `or`: a genuine 0.0 reliability must stay 0.0.)
        weight = (50.0 if sig.reliability_score is None else sig.reliability_score) / 100.0

        direction = _classify_sentiment(text)
        if direction == "contradicts":
            contradict_weight_sum += weight
            evidence.append({"signal_id": sig.id, "content": sig.content, "direction": "contradicts"})
        elif direction == "supports" or sig.signal_type == "problem":
            support_weight_sum += weight
            evidence.append({"signal_id": sig.id, "content": sig.content, "direction": "supports"})

    support_score = min(SUPPORT_CAP, support_weight_sum * SUPPORT_WEIGHT)
    contradict_score = min(CONTRADICT_CAP, contradict_weight_sum * CONTRADICT_WEIGHT)
    confidence_change = round(support_score - contradict_score, 1)

    if confidence_change != 0:
        evidence_signal_ids = [item["signal_id"] for item in evidence if item.get("signal_id")]
        belief_engine.BeliefEngine(db).adjust_confidence(
            belief,
            confidence_change,
            reason="reality_check",
            evidence_signal_ids=evidence_signal_ids,
        )

    # Persist evidence to Reality Memory regardless of net confidence
    # change (support and contradiction can cancel out to ~0 net while
    # both still being real, inspectable evidence).
    reality_memory.record_evidence(db, belief, evidence)

    return {
        "belief": belief.statement,
        "evidence_found": evidence[:10],  # cap payload size
        "confidence_change": confidence_change,
    }


def check_all_beliefs(db: Session, limit: int = 100) -> list[dict]:
    """Run check_belief() across every stored belief. Used by the Forge
    intelligence cycle (forge_loop.py). The signal pool is loaded once
    and shared across beliefs instead of once per belief."""
    beliefs = db.query(models.Belief).limit(limit).all()
    signals = db.query(models.Signal).all()
    return [check_belief(db, b, signals=signals) for b in beliefs]
