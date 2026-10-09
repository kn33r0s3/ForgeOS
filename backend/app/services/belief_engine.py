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


from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import reality_memory, memory_layer
from typing import Optional
import re




def _signal_id_sort_key(value: str) -> tuple[int, object]:
    """Sort key for comma-separated signal-id lists that never raises.

    Signal ids are ints in practice, but legacy rows under repair may
    carry non-numeric tokens; int() on one of those used to blow up the
    whole merge/repair path with a ValueError."""
    text = value.strip()
    if text.lstrip("+-").isdigit():
        return (0, int(text))
    return (1, text)


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
                set(x.strip() for x in existing.supporting_signal_ids.split(",") if x.strip())
                if existing.supporting_signal_ids
                else set()
            )
            new_ids = {str(i) for i in supporting_signal_ids}
            newly_added_ids = new_ids - existing_ids
            existing_ids |= new_ids
            existing.supporting_signal_ids = ",".join(sorted(existing_ids, key=_signal_id_sort_key))
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
            label="observation",  # keyword-bag output starts as an observation
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
        rows = (
            self.db.query(models.Belief)
            .filter(models.Belief.merged_into_id.is_(None))
            .order_by(models.Belief.confidence_score.desc())
            .all()
        )
        return [row for row in rows if is_presentable_belief(row)][:limit]

    def get_belief(self, belief_id: int) -> Optional[models.Belief]:
        return self.db.query(models.Belief).filter(models.Belief.id == belief_id).first()


def repair_historical_beliefs(db: Session) -> int:
    """Converge legacy belief rows onto the canonical observation form.

    Merged rows are retained as historical records and point at their
    canonical row through ``merged_into_id``. Evidence and signal
    provenance are unioned onto that canonical row, while confidence uses
    the most conservative value already recorded. Running this repeatedly
    makes no further changes.
    """
    beliefs = db.query(models.Belief).order_by(models.Belief.id.asc()).all()
    active_beliefs = [belief for belief in beliefs if belief.merged_into_id is None]
    canonical_by_statement: dict[str, models.Belief] = {}
    merged_count = 0
    changed = False

    for belief in active_beliefs:
        statement = _canonical_statement_for_belief(db, belief)
        keywords = _keywords_from_canonical_statement(statement)
        canonical = None
        for existing_statement, existing in canonical_by_statement.items():
            if _keyword_jaccard(keywords, _keywords_from_canonical_statement(existing_statement)) >= 0.6:
                canonical = existing
                statement = existing_statement
                break
        if canonical is None:
            canonical = canonical_by_statement.get(statement)
        if canonical is None:
            existing = (
                db.query(models.Belief)
                .filter(
                    models.Belief.statement == statement,
                    models.Belief.merged_into_id.is_(None),
                )
                .order_by(models.Belief.id.asc())
                .first()
            )
            canonical = existing or belief
            canonical_by_statement[statement] = canonical

        if canonical.id == belief.id:
            if belief.statement != statement:
                belief.statement = statement
                changed = True
            continue

        _merge_belief_into(db, belief, canonical, statement)
        merged_count += 1
        changed = True

    for belief in beliefs:
        if belief.merged_into_id is None:
            continue
        root = belief
        seen: set[int] = set()
        while root.merged_into_id is not None and root.merged_into_id not in seen:
            seen.add(root.id)
            parent = db.get(models.Belief, root.merged_into_id)
            if parent is None:
                break
            root = parent
        if root.id == belief.id:
            continue
        _merge_belief_provenance(db, belief, root)
        if belief.merged_into_id != root.id:
            belief.merged_into_id = root.id
            changed = True

    if changed:
        db.commit()
        for canonical in canonical_by_statement.values():
            memory_layer.sync_belief_to_knowledge(db, canonical)
    return merged_count


def _canonical_statement_for_belief(db: Session, belief: models.Belief) -> str:
    keywords: set[str] = set()
    if belief.pattern_id is not None:
        pattern = db.get(models.Pattern, belief.pattern_id)
        if pattern:
            keywords = _keywords_from_pattern_title(pattern.title)
    if not keywords:
        keywords = _keywords_from_legacy_statement(belief.statement)
    canonical = ", ".join(sorted(keywords))
    return (
        f'Observed keyword cluster: "{canonical}". '
        "An observation, not a hypothesis — no actor, need, give-up, or evidence attached."
    )


def qualifies_as_hypothesis(belief: models.Belief) -> bool:
    """The strict gate. A record may be called a hypothesis only if it
    carries all four: an actor/segment, a stated need or pain, what that
    actor would give up (money/time/behavior), and >=1 evidence
    reference. Everything else is an observation — stored, never
    deleted, but never surfaced publicly as a hypothesis."""
    if belief.merged_into_id is not None:
        return False
    has_actor = bool((belief.actor_segment or "").strip())
    has_need = bool((belief.need_pain or "").strip())
    has_give_up = bool((belief.give_up or "").strip())
    signal_ids = [s for s in (belief.supporting_signal_ids or "").split(",") if s.strip()]
    return has_actor and has_need and has_give_up and len(signal_ids) >= 1


def relabel_keyword_bags_as_observations(db: Session) -> int:
    """Archive pass: any belief still wearing the old 'Uncorroborated
    keyword hypothesis' label becomes an observation with the reason
    recorded. Rows are never deleted; merged rows are left alone."""
    rows = (
        db.query(models.Belief)
        .filter(models.Belief.statement.like("Uncorroborated keyword hypothesis%"))
        .filter(models.Belief.merged_into_id.is_(None))
        .all()
    )
    count = 0
    for row in rows:
        old = row.statement
        row.statement = old.replace(
            "Uncorroborated keyword hypothesis", "Observed keyword cluster", 1
        ).replace(
            "This is not a verified business problem, demand claim, or price.",
            "An observation, not a hypothesis — no actor, need, give-up, or evidence attached.",
        )
        row.label = "observation"
        # The date is the run date, not a fixed constant — a future run
        # must not claim it happened on 2026-10-04.
        row.relabel_reason = (
            f"{utcnow().date().isoformat()}: keyword-bag output re-labeled from "
            "hypothesis to observation — it names no actor, need, give-up, or "
            "evidence. Archived with reason; row retained."
        )
        count += 1
    if count:
        db.commit()
    return count


MAX_HYPOTHESIS_KEYWORDS = 12


def is_presentable_belief(belief: models.Belief) -> bool:
    """Public-surface gate: only a qualifying hypothesis may be surfaced.
    An oversized keyword list is not one claim, and a keyword bag without
    actor/need/give-up/evidence is an observation. The row stays stored."""
    if not qualifies_as_hypothesis(belief):
        return False
    return len(_keywords_from_canonical_statement(belief.statement)) <= MAX_HYPOTHESIS_KEYWORDS


def _keywords_from_canonical_statement(statement: str) -> set[str]:
    quoted = re.search(r'"([^"]+)"', statement)
    source = quoted.group(1) if quoted else statement
    return {part.strip().lower() for part in source.split(",") if part.strip()}


def _keyword_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _keywords_from_pattern_title(title: str) -> set[str]:
    raw = title.replace("Recurring theme:", "").strip()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _keywords_from_legacy_statement(statement: str) -> set[str]:
    quoted = re.search(r'"([^"]+)"', statement)
    source = quoted.group(1) if quoted else statement
    return {
        word.lower()
        for word in re.findall(r"[a-zA-Z]+", source)
        if len(word) > 2 and word.lower() not in {"real", "addressable", "business", "problem"}
    }


def _merge_belief_into(
    db: Session,
    duplicate: models.Belief,
    canonical: models.Belief,
    statement: str,
) -> None:
    _merge_belief_provenance(db, duplicate, canonical)
    duplicate.merged_into_id = canonical.id
    if canonical.statement != statement:
        canonical.statement = statement


def _merge_belief_provenance(
    db: Session, duplicate: models.Belief, canonical: models.Belief
) -> None:
    existing_ids = {item for item in (canonical.supporting_signal_ids or "").split(",") if item}
    duplicate_ids = {item for item in (duplicate.supporting_signal_ids or "").split(",") if item}
    canonical.supporting_signal_ids = ",".join(
        sorted(existing_ids | duplicate_ids, key=_signal_id_sort_key)
    ) or None
    # The repair's "most conservative confidence" write is a real
    # confidence change, so it belongs in the append-only trail — the
    # same invariant _record_confidence_event() enforces everywhere
    # else. No commit here: repair_historical_beliefs() commits once
    # it has processed all merges.
    if duplicate.confidence_score < canonical.confidence_score:
        db.add(
            models.ConfidenceEvent(
                belief_id=canonical.id,
                previous_confidence=canonical.confidence_score,
                new_confidence=duplicate.confidence_score,
                delta=round(duplicate.confidence_score - canonical.confidence_score, 1),
                reason="merge_conservative",
            )
        )
        canonical.confidence_score = duplicate.confidence_score
    if canonical.pattern_id is None:
        canonical.pattern_id = duplicate.pattern_id
    db.query(models.Evidence).filter(models.Evidence.belief_id == duplicate.id).update(
        {"belief_id": canonical.id}, synchronize_session=False
    )
    db.query(models.ConfidenceEvent).filter(
        models.ConfidenceEvent.belief_id == duplicate.id
    ).update({"belief_id": canonical.id}, synchronize_session=False)


def _pattern_to_belief_statement(pattern: models.Pattern) -> str:
    """A keyword cluster is an observation, never a hypothesis."""
    keywords = pattern.title.replace("Recurring theme:", "").strip()
    parts = sorted(part.strip() for part in keywords.split(",") if part.strip())
    canonical = ", ".join(parts)
    return (
        f'Observed keyword cluster: "{canonical}". '
        "An observation, not a hypothesis — no actor, need, give-up, or evidence attached."
    )
