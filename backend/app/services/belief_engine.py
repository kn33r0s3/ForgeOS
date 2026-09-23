"""
BELIEF ENGINE
==============

Beliefs are Forge's hypotheses about how reality works — one level up
from Patterns. A Pattern says "these signals repeat together." A
Belief says "here's what that probably means, and how sure we are."

    Pattern: "Businesses lose revenue because communication is slow"
        |
        v
    Belief: "Recurring signals about 'lose, customers, slow' indicate
             a real, addressable business problem."
             confidence: 62

Beliefs change over time:
  - Reality Checker (reality_checker.py) re-scores them against new
    signals as they arrive.
  - BeliefExperiment results (experiment_runner.py) push confidence up
    or down based on real-world tests.

Every belief records which Pattern it originated from (Belief.pattern_id,
set once at creation, never overwritten) — this is what lets Forge
actually answer "why does this belief exist?" / "which pattern created
this understanding?" via world_model.get_belief_graph(), instead of
only being able to explain a belief's wording without its cause.

Every belief links to evidence from the moment it's created — not just
after the first Reality Check runs. form_belief_from_pattern() records
an initial Evidence row for every supporting signal immediately, via
Reality Memory, so "every belief must link to evidence" holds from
birth, not eventually.

Every confidence change — from adjust_confidence() or the merge-path
nudge above — is appended to ConfidenceEvent, an append-only history
log (models.ConfidenceEvent). Nothing overwrites it; a belief's
confidence_score is a snapshot, ConfidenceEvent is the trail of how it
got there. See world_model.py, which surfaces this history.

Every belief is also synced into the Forge Memory Layer (Knowledge) on
creation and every confidence change, so it becomes part of Forge's
permanent, retrievable, embedded memory — see memory_layer.py.

Kept deliberately simple: no embeddings, no external model call to
"understand" a pattern — just a template that turns a Pattern's
keywords into a hypothesis sentence. The templating can be replaced
with an LLM call later (via ai_engine.py) without changing the public
functions here.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.services import reality_memory, memory_layer
from typing import Optional


def utcnow():
    return datetime.now(timezone.utc)


class BeliefEngine:
    def __init__(self, db: Session):
        self.db = db

    def form_or_update_belief(
        self,
        statement: str,
        supporting_signal_ids: list[int],
        initial_confidence: float,
        pattern_id: Optional[int] = None,
    ) -> models.Belief:
        """Create a new Belief, or if this exact statement already
        exists, merge in the new supporting signals and nudge its
        confidence toward the new evidence rather than overwriting it.

        pattern_id records which Pattern caused this belief to exist —
        its causal origin. Set once on creation and never overwritten
        afterward, even if a later call passes a different pattern_id
        (unlikely in practice since the statement is derived
        deterministically from the pattern's title, but a belief's
        origin should stay stable regardless). If an existing belief
        predates this field (pattern_id is currently None), a newly
        supplied pattern_id backfills it — a legacy row with no
        recorded origin is exactly the case worth filling in."""
        existing = (
            self.db.query(models.Belief).filter(models.Belief.statement == statement).first()
        )
        if existing:
            existing_ids = (
                set(existing.supporting_signal_ids.split(","))
                if existing.supporting_signal_ids
                else set()
            )
            new_ids = {str(i) for i in supporting_signal_ids}
            newly_added_ids = new_ids - existing_ids
            existing_ids |= new_ids
            existing.supporting_signal_ids = ",".join(sorted(existing_ids, key=lambda x: int(x)))
            if existing.pattern_id is None and pattern_id is not None:
                existing.pattern_id = pattern_id
            # Nudge toward the new reading rather than snapping to it —
            # one pattern re-run shouldn't erase prior evidence.
            previous_confidence = existing.confidence_score
            existing.confidence_score = round(
                (existing.confidence_score + initial_confidence) / 2, 1
            )
            existing.last_updated = utcnow()
            self.db.commit()
            self.db.refresh(existing)
            self._record_confidence_event(
                existing,
                previous_confidence,
                existing.confidence_score,
                reason="pattern_reoccurrence",
                evidence_signal_ids=[int(i) for i in newly_added_ids] if newly_added_ids else None,
            )

            if newly_added_ids:
                self._record_initial_evidence(existing, [int(i) for i in newly_added_ids])
            memory_layer.sync_belief_to_knowledge(self.db, existing)
            return existing

        belief = models.Belief(
            statement=statement,
            pattern_id=pattern_id,
            supporting_signal_ids=",".join(str(i) for i in supporting_signal_ids),
            confidence_score=round(max(0.0, min(100.0, initial_confidence)), 1),
        )
        self.db.add(belief)
        self.db.commit()
        self.db.refresh(belief)

        self._record_initial_evidence(belief, supporting_signal_ids)
        memory_layer.sync_belief_to_knowledge(self.db, belief)
        return belief

    def _record_initial_evidence(self, belief: models.Belief, signal_ids: list[int]) -> None:
        """Guarantee every belief links to evidence from the moment it
        exists, rather than waiting for the first Reality Check. Each
        supporting signal becomes a "supports" Evidence row."""
        if not signal_ids:
            return
        signals = self.db.query(models.Signal).filter(models.Signal.id.in_(signal_ids)).all()
        evidence_items = [
            {"signal_id": signal.id, "content": signal.content, "direction": "supports"}
            for signal in signals
        ]
        if evidence_items:
            reality_memory.record_evidence(self.db, belief, evidence_items)

    def _record_confidence_event(
        self,
        belief: models.Belief,
        previous_confidence: float,
        new_confidence: float,
        reason: str = "unspecified",
        evidence_signal_ids: Optional[list[int]] = None,
        experiment_id: Optional[int] = None,
    ) -> None:
        """Append-only log of a confidence change — never overwritten,
        only added to. No-ops if the value didn't actually move (a
        merge that nudges toward the same number isn't a real change).
        Every place confidence_score gets written (adjust_confidence
        and the merge-path nudge below) calls this, so nothing that
        changes a belief's confidence goes unrecorded — and now WHY it
        changed (reason) and WHAT evidence was involved are recorded
        alongside the number, not just the number itself."""
        if previous_confidence == new_confidence:
            return
        event = models.ConfidenceEvent(
            belief_id=belief.id,
            previous_confidence=previous_confidence,
            new_confidence=new_confidence,
            delta=round(new_confidence - previous_confidence, 1),
            reason=reason,
            evidence_signal_ids=(
                ",".join(str(i) for i in evidence_signal_ids) if evidence_signal_ids else None
            ),
            experiment_id=experiment_id,
        )
        self.db.add(event)
        self.db.commit()

    def form_belief_from_pattern(
        self, pattern: models.Pattern, supporting_signal_ids: list[int]
    ) -> models.Belief:
        """Turn a detected Pattern into (or update) a Belief. Records
        pattern.id as the belief's origin — this is the fix for the
        "Pattern -> Belief" link that used to be dropped after the
        pattern's title/confidence were read once to build the
        statement (see module docstring)."""
        statement = _pattern_to_belief_statement(pattern)
        return self.form_or_update_belief(
            statement,
            supporting_signal_ids,
            initial_confidence=pattern.confidence_score,
            pattern_id=pattern.id,
        )

    def adjust_confidence(
        self,
        belief: models.Belief,
        delta: float,
        reason: str = "unspecified",
        evidence_signal_ids: Optional[list[int]] = None,
        experiment_id: Optional[int] = None,
    ) -> models.Belief:
        """Apply a confidence change (positive = supporting evidence,
        negative = contradicting evidence), clamped to [0, 100].
        `reason`/`evidence_signal_ids`/`experiment_id` are optional so
        every existing caller keeps working unchanged — callers that
        care about traceable history (reality_checker.py,
        experiment_runner.py) now pass them through."""
        previous_confidence = belief.confidence_score
        belief.confidence_score = round(max(0.0, min(100.0, belief.confidence_score + delta)), 1)
        belief.last_updated = utcnow()
        self.db.commit()
        self.db.refresh(belief)
        self._record_confidence_event(
            belief,
            previous_confidence,
            belief.confidence_score,
            reason=reason,
            evidence_signal_ids=evidence_signal_ids,
            experiment_id=experiment_id,
        )
        memory_layer.sync_belief_to_knowledge(self.db, belief)
        return belief

    def list_beliefs(self, limit: int = 100) -> list[models.Belief]:
        return (
            self.db.query(models.Belief)
            .order_by(models.Belief.confidence_score.desc())
            .limit(limit)
            .all()
        )

    def get_belief(self, belief_id: int) -> Optional[models.Belief]:
        return self.db.query(models.Belief).filter(models.Belief.id == belief_id).first()


def _pattern_to_belief_statement(pattern: models.Pattern) -> str:
    """Template a Pattern into a hypothesis-style sentence. Simple and
    deterministic on purpose — see module docstring."""
    keywords = pattern.title.replace("Recurring theme:", "").strip()
    return f'Recurring signals about "{keywords}" indicate a real, addressable business problem.'
