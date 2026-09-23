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
     based on simple sentiment word lists (want/need/adopt vs.
     avoid/refuse/distrust), falling back to "supporting" if the
     signal's Observer-assigned type is "problem" (a real complaint is
     evidence the underlying issue is real).
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

from app import models
from app.services import belief_engine, reality_memory
from app.services.pattern_engine import tokenize

POSITIVE_WORDS = ["want", "need", "adopt", "love", "prefer", "willing", "pay for"]
NEGATIVE_WORDS = ["avoid", "refuse", "distrust", "reject", "against", "won't", "wont", "skeptical"]

SUPPORT_WEIGHT = 4.0
CONTRADICT_WEIGHT = 6.0  # contradicting evidence counts for more — protects against overconfidence
SUPPORT_CAP = 20.0
CONTRADICT_CAP = 25.0


def check_belief(db: Session, belief: models.Belief) -> dict:
    """Re-score one Belief against all current signals. Applies the
    resulting confidence_change and returns a breakdown."""
    keywords = tokenize(belief.statement)
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
        # neutral weight rather than erroring or being skipped.
        weight = (sig.reliability_score or 50.0) / 100.0

        if any(word in text for word in NEGATIVE_WORDS):
            contradict_weight_sum += weight
            evidence.append({"signal_id": sig.id, "content": sig.content, "direction": "contradicts"})
        elif any(word in text for word in POSITIVE_WORDS) or sig.signal_type == "problem":
            support_weight_sum += weight
            evidence.append({"signal_id": sig.id, "content": sig.content, "direction": "supports"})

    support_score = min(SUPPORT_CAP, support_weight_sum * SUPPORT_WEIGHT)
    contradict_score = min(CONTRADICT_CAP, contradict_weight_sum * CONTRADICT_WEIGHT)
    confidence_change = round(support_score - contradict_score, 1)

    if confidence_change != 0:
        supporting_signal_ids = [item["signal_id"] for item in evidence if item.get("signal_id")]
        belief_engine.BeliefEngine(db).adjust_confidence(
            belief,
            confidence_change,
            reason="reality_check",
            evidence_signal_ids=supporting_signal_ids,
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
    intelligence cycle (forge_loop.py)."""
    beliefs = db.query(models.Belief).limit(limit).all()
    return [check_belief(db, b) for b in beliefs]
