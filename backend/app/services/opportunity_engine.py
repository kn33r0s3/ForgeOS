"""
OPPORTUNITY ENGINE
===================

Turns a Pattern (or a raw free-text idea) into a structured business
Opportunity: problem, target customer, solution, business model,
pricing idea, difficulty, and an overall opportunity score.

Two entry points:

  - opportunity_from_pattern(db, pattern)
        Used by POST /analyze's pattern-driven flow and by any future
        batch job that walks newly-detected patterns. UNCONDITIONAL —
        converts whatever pattern it's given, no evidence gate. This is
        correct for its use case (a human explicitly asked to analyze
        THIS specific pattern) but was, until v1.8, the only path that
        ever created an Opportunity from a Pattern at all — and nothing
        autonomous ever called it, which is why a real Forge instance
        could accumulate dozens of patterns and zero opportunities.

  - opportunity_from_idea(db, idea_text)
        Used directly by POST /analyze when the user types a free-text
        business idea/problem on the Analyze page. Not tied to a
        stored pattern.

Both delegate the actual writing (market analysis, MVP plan, etc.) to
app.services.ai_engine — passing `db` through so generation is
retrieval-augmented against Forge's own Memory Layer (existing
beliefs/patterns), not generated in isolation — and both compute a
0-100 opportunity score from a few simple heuristics (kept transparent
and inspectable rather than another opaque model call).

v1.8 adds a THIRD entry point, the one forge_loop.run_cycle() actually
calls: generate_opportunity_from_pattern_if_economic(). Unlike the two
above, it is NOT unconditional — it requires real economic evidence
(economic_intelligence.py: a problem, an identifiable customer, and at
least one of pain/demand/monetary-impact/solution-gap, all backed by
actual matched text, never guessed) before creating anything. It also
does NOT call ai_engine — with AI_PROVIDER defaulting to "mock" ($0),
ai_engine's output is templated boilerplate, which is exactly the
"treating keyword clusters as opportunities" failure mode v1.8 was
built to stop. Its problem/target_customer/economic_consequence come
from real extracted text instead.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
import hashlib
import json
import re

from app import models
from app.services import ai_engine, economic_intelligence
from typing import Optional


def _estimate_difficulty(problem_text: str) -> str:
    """Very simple heuristic: longer/more technical-sounding problems
    are assumed harder. This is a placeholder scoring rule that can be
    replaced with a model-based estimate later."""
    hard_signals = ["regulat", "hardware", "medical", "bank", "compliance", "legal", "government"]
    text = problem_text.lower()
    if any(h in text for h in hard_signals):
        return "high"
    if len(text.split()) > 40:
        return "medium"
    return "low"


def _score_opportunity(frequency: int, confidence: float, difficulty: str) -> float:
    """
    Transparent scoring formula (0-100) built from three explicit axes:

      Friction Score   — how big / painful is the problem?
                         (driven by pattern confidence + frequency of signals)
      Market Viability — will people pay for a solution?
                         (baseline + confidence signal; refined later by money_engine evidence)
      Feasibility      — can an indie hacker / small team build & ship it?
                         (inverse of difficulty)

    Final score = weighted combination of the three, clamped to [0, 100].
    """
    # Friction (0-40): confidence * weight + frequency evidence
    friction = min(40.0, confidence * 0.35 + min(15.0, frequency * 3))
    # Market viability (0-35): starts from a modest base; rises with confidence
    viability = min(35.0, 12.0 + confidence * 0.23)
    # Feasibility (0-25): high when difficulty is low
    feasibility = {"low": 25.0, "medium": 15.0, "high": 5.0}.get(difficulty, 15.0)
    score = friction + viability + feasibility
    return round(max(0.0, min(100.0, score)), 1)


def normalize_problem_text(text: str) -> str:
    """Deterministic normalization boundary for problem statements:
    strips whitespace, casefolds to lower case, removes non-alphanumeric chars,
    and joins words with a single space."""
    words = re.findall(r"[a-z0-9]+", (text or "").casefold())
    return " ".join(words)


def _identity_key(problem: str, pattern_id: int | None = None) -> str:
    """Stable normalized SHA-256 identity key based on problem text.
    Independent of pattern_id, cycle runs, or supporting signal count."""
    norm = normalize_problem_text(problem)
    return "problem:" + hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _record_event(
    db: Session,
    opportunity: models.Opportunity,
    event_type: str,
    details: dict | None = None,
    event_key: str | None = None,
) -> models.OpportunityEvent | None:
    payload = details or {}
    key = event_key or hashlib.sha256(
        f"{event_type}:{json.dumps(payload, sort_keys=True, default=str)}".encode("utf-8")
    ).hexdigest()
    if db.query(models.OpportunityEvent).filter_by(opportunity_id=opportunity.id, event_key=key).first():
        return None
    event = models.OpportunityEvent(
        opportunity_id=opportunity.id,
        event_type=event_type,
        event_key=key,
        details=json.dumps(payload, sort_keys=True, default=str),
    )
    db.add(event)
    return event


def _append_signal_id(existing: str | None, signal_id: int) -> str:
    ids = [part for part in (existing or "").split(",") if part.strip().isdigit()]
    if str(signal_id) not in ids:
        ids.append(str(signal_id))
    return ",".join(ids)


def _is_generic_target(value: str | None) -> bool:
    low = (value or "").strip().lower()
    return not low or "to be refined" in low or "not yet identified" in low or "matching the signals" in low


def _derive_target_customer(problem: str, fallback: str | None = None) -> str | None:
    extraction = economic_intelligence.extract_economic_signal(problem)
    return (
        extraction.get("customer_type")
        or extraction.get("affected_customer")
        or fallback
        or fallback
    )


def _looks_like_imported_instruction(text: str | None) -> bool:
    low = (text or "").casefold()
    markers = (
        "allowed-tools:",
        "prompt-injected",
        "prompt injection",
        "pre-approves those skills",
        "skill grants to read",
    )
    return sum(marker in low for marker in markers) >= 2


def opportunity_from_pattern(db: Session, pattern: models.Pattern) -> models.Opportunity:
    """Build and persist a full Opportunity from an existing Pattern."""
    problem_text = pattern.title or pattern.description
    key = _identity_key(problem_text)

    existing = db.query(models.Opportunity).filter(
        (models.Opportunity.identity_key == key) | (models.Opportunity.pattern_id == pattern.id)
    ).first()
    if not existing:
        norm = normalize_problem_text(problem_text)
        all_opps = db.query(models.Opportunity).filter(models.Opportunity.status != "archived").all()
        for opp in all_opps:
            if normalize_problem_text(opp.problem) == norm:
                existing = opp
                if not existing.identity_key:
                    existing.identity_key = key
                    db.commit()
                break

    if existing:
        if pattern.origin_signal_ids:
            for sig_id in pattern.origin_signal_ids.split(","):
                if sig_id.strip().isdigit():
                    existing.problem_evidence_signal_ids = _append_signal_id(
                        existing.problem_evidence_signal_ids, int(sig_id.strip())
                    )
            db.commit()
        return existing
    problem_text = pattern.description

    difficulty = _estimate_difficulty(problem_text)
    score = _score_opportunity(pattern.frequency, pattern.confidence_score, difficulty)

    opportunity = models.Opportunity(
        pattern_id=pattern.id,
        problem=pattern.title,
        target_customer=_derive_target_customer(problem_text),
        solution=None,
        business_model=None,
        pricing_idea=None,
        market_analysis=None,
        mvp_plan=None,
        validation_plan=None,
        difficulty=difficulty,
        score=score,
        identity_key=_identity_key(pattern.title, pattern.id),
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    _record_event(db, opportunity, "created", {"pattern_id": pattern.id, "score": score})
    db.commit()
    return opportunity


def opportunity_from_idea(db: Session, idea_text: str) -> models.Opportunity:
    """Build and persist a full Opportunity directly from free-text
    input (the Analyze page), with no pattern required."""

    identity_key = _identity_key(idea_text.strip())
    existing = db.query(models.Opportunity).filter(models.Opportunity.identity_key == identity_key).first()
    if existing:
        return existing

    difficulty = _estimate_difficulty(idea_text)
    # No pattern confidence/frequency available for a one-off idea, so
    # score from a moderate baseline plus a small text-richness signal.
    richness_bonus = min(15.0, len(idea_text.split()) * 0.5)
    confidence_stub = 50.0
    score = _score_opportunity(frequency=1, confidence=confidence_stub, difficulty=difficulty)
    score = round(min(100.0, score + richness_bonus - 15), 1)  # normalize baseline vs pattern flow

    opportunity = models.Opportunity(
        pattern_id=None,
        problem=idea_text.strip(),
        target_customer=_derive_target_customer(idea_text),
        solution=None,
        business_model=None,
        pricing_idea=None,
        market_analysis=None,
        mvp_plan=None,
        validation_plan=None,
        difficulty=difficulty,
        score=score,
        identity_key=identity_key,
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    _record_event(db, opportunity, "created", {"source": "manual", "score": score})
    db.commit()
    return opportunity


def list_opportunities(db: Session, limit: int = 200) -> list[models.Opportunity]:
    """List actionable opportunities while preserving noisy rows as history.

    Older imports could turn arbitrary security/prompt-injection text into
    zero-score opportunities. They remain in the database for provenance but
    are excluded from the actionable list unless they have an economic signal.
    Legacy generic targets are deterministically repaired from the opportunity
    text; this is a hypothesis, never validation.
    """
    candidates = (
        db.query(models.Opportunity)
        .order_by(models.Opportunity.score.desc(), models.Opportunity.id.asc())
        .all()
    )
    visible: list[models.Opportunity] = []
    changed = False
    for opportunity in candidates:
        if _looks_like_imported_instruction(opportunity.problem):
            continue
        extraction = economic_intelligence.extract_economic_signal(
            " ".join(filter(None, [opportunity.problem, opportunity.economic_consequence, opportunity.solution]))
        )
        has_customer = bool(extraction.get("customer_type") or extraction.get("affected_customer"))
        has_economic_signal = bool(
            extraction.get("problem")
            and (extraction.get("pain") or extraction.get("consequence")
                 or extraction.get("monetary_impact") or extraction.get("buying_intent"))
        )
        if not has_customer and not has_economic_signal:
            continue
        if _is_generic_target(opportunity.target_customer) and has_customer:
            opportunity.target_customer = _derive_target_customer(opportunity.problem)
            if not opportunity.customer_segment:
                opportunity.customer_segment = opportunity.target_customer
            changed = True
        visible.append(opportunity)
        if len(visible) >= limit:
            break
    if changed:
        db.commit()
    return visible


# --- Autonomous, evidence-gated discovery (v1.8) -----------------------


def generate_opportunity_from_pattern_if_economic(db: Session, pattern: models.Pattern) -> Optional[models.Opportunity]:
    """
    The autonomous counterpart to opportunity_from_pattern() — see
    module docstring for why it's a separate function rather than a
    modification of the existing one (that one stays unconditional,
    for its own manual/explicit use case).

    Runs economic_intelligence extraction across every non-duplicate
    signal behind this pattern, keeps the single strongest one (highest
    combined evidence+pain), and only creates an Opportunity if that
    signal clears is_economically_meaningful(). Returns None — no
    Opportunity created — if nothing behind the pattern clears the bar;
    the pattern remains just a pattern, exactly as the spec requires
    ("if Forge cannot answer those questions, it should remain a
    pattern/signal rather than becoming an opportunity").
    """
    if pattern.origin_signal_ids:
        signal_ids = [int(i) for i in pattern.origin_signal_ids.split(",") if i.strip().isdigit()]
        signals = db.query(models.Signal).filter(models.Signal.id.in_(signal_ids)).all()
    else:
        signals = []

    candidates = []
    for signal in signals:
        if signal.is_duplicate_of is not None:
            continue  # a syndicated duplicate isn't independent evidence — see economic_intelligence.compute_corroboration()
        extraction = economic_intelligence.extract_economic_signal(signal.content)
        scores = economic_intelligence.score_economic_signal(extraction, signal.reliability_score)
        if not economic_intelligence.is_economically_meaningful(extraction, scores):
            continue
        rank = scores["evidence_strength"] + scores["pain_score"] + scores["demand_score"]
        candidates.append((rank, signal, extraction, scores))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1].id))
    _, best_signal, best_extraction, best_scores = candidates[0]
    problem_text = best_extraction["problem"]
    key = _identity_key(problem_text)
    existing_opportunity = db.query(models.Opportunity).filter(
        (models.Opportunity.identity_key == key) | (models.Opportunity.pattern_id == pattern.id)
    ).first()
    if existing_opportunity:
        added = 0
        for _, signal, extraction, scores in candidates:
            evidence_key = _evidence_hash(signal)
            if db.query(models.Evidence).filter_by(provenance_hash=evidence_key).first():
                continue
            db.add(models.Evidence(
                opportunity_id=existing_opportunity.id,
                signal_id=signal.id,
                provenance_hash=evidence_key,
                content=extraction["evidence_text"],
                direction="supports",
                confidence=scores["evidence_strength"],
            ))
            existing_opportunity.problem_evidence_signal_ids = _append_signal_id(
                existing_opportunity.problem_evidence_signal_ids, signal.id
            )
            _record_event(db, existing_opportunity, "evidence_added", {"signal_id": signal.id}, event_key=evidence_key)
            added += 1
        if added:
            existing_opportunity.updated_at = datetime.now(timezone.utc)
            existing_opportunity.no_meaningful_change = False
            db.commit()
        return existing_opportunity

    prov_hash = _evidence_hash(best_signal)

    corroboration = economic_intelligence.compute_corroboration(db, pattern)
    difficulty = _estimate_difficulty(best_extraction["problem"])
    score = _score_opportunity(pattern.frequency, pattern.confidence_score, difficulty)

    core_signal = best_extraction["pain"] or best_extraction["consequence"] or best_extraction["existing_solution"] or "identified pattern"
    summary_parts = [
        f'Grounded in a real signal: "{core_signal}".',
        f"Evidence strength {best_scores['evidence_strength']:.0f}/100.",
        f"Corroborated by {corroboration['unique_sources']} unique source(s) across "
        f"{corroboration['independent_observations']} independent observation(s).",
    ]
    if best_extraction["monetary_impact"]:
        summary_parts.append(f"Monetary impact mentioned: {best_extraction['monetary_impact']}.")
    if best_extraction["urgency"]:
        summary_parts.append("Urgency signal present (repeated/ongoing pain).")
    if best_extraction["existing_solution"]:
        summary_parts.append(f"Existing (inadequate) workaround: {best_extraction['existing_solution']}.")

    opportunity = models.Opportunity(
        pattern_id=pattern.id,
        problem=best_extraction["problem"],
        target_customer=best_extraction["customer_type"] or best_extraction["affected_customer"],
        solution=None,
        business_model=None,
        customer_segment=best_extraction["customer_type"],
        economic_consequence=best_extraction["consequence"] or best_extraction["monetary_impact"],
        problem_evidence_signal_ids=str(best_signal.id),
        difficulty=difficulty,
        score=score,
        economic_evidence_summary=" ".join(summary_parts),
        identity_key=_identity_key(best_extraction["problem"], pattern.id),
    )
    db.add(opportunity)
    db.flush()

    evidence = models.Evidence(
        opportunity_id=opportunity.id,
        signal_id=best_signal.id,
        provenance_hash=prov_hash,
        content=core_signal,
        direction="supports",
        confidence=best_scores["evidence_strength"]
    )
    db.add(evidence)
    db.commit()
    db.refresh(opportunity)
    _record_event(db, opportunity, "created", {"pattern_id": pattern.id, "signal_id": best_signal.id})
    db.commit()
    return opportunity


def generate_opportunity_from_signal_if_strong(db: Session, signal: models.Signal) -> Optional[models.Opportunity]:
    """
    Opportunity from a SINGLE strong signal — the complement to the
    pattern path. A pattern requires >= MIN_CLUSTER_SIZE supporting
    signals to be corroborated, but CURRENT_FOCUS.md explicitly names a
    lone, unambiguous complaint as a valid first real result:
    "clear evidence of a problem + identifiable customer + some
    willingness-to-pay signal." Those sharp signals tend to arrive one
    at a time (a single manual observation, one Reddit complaint) and
    would otherwise sit forever as an unpatterned signal while the loop
    reports zero opportunities.

    This path is deliberately GATED by economic_intelligence.is_economically_strong():
    a strict bar (named problem + named affected party + pain AND at
    least one of dollar-figure/urgency/willingness-to-pay). A lone signal
    that clears the strong bar seeds an Opportunity with full provenance
    (the signal's own content + evidence row), exactly like the pattern
    path does. Anything weaker stays a signal and nothing is invented.
    """
    if signal.is_duplicate_of is not None:
        return None  # a syndicated duplicate isn't independent evidence

    extraction = economic_intelligence.extract_economic_signal(signal.content)
    scores = economic_intelligence.score_economic_signal(extraction, signal.reliability_score)
    if not economic_intelligence.is_economically_strong(extraction, scores):
        return None  # not strong enough to stand on its own — honest, no fabrication

    # Prefer a clean identity key derived from the extracted problem.
    problem_text = extraction["problem"] or signal.content
    identity = _identity_key(problem_text, None)
    existing = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.identity_key == identity)
        .first()
    )
    if existing:
        # Already have an opportunity for this exact problem — link any
        # missing evidence, don't duplicate.
        existing.problem_evidence_signal_ids = _append_signal_id(
            existing.problem_evidence_signal_ids, signal.id
        )
        if not db.query(models.Evidence).filter_by(signal_id=signal.id, opportunity_id=existing.id).first():
            db.add(models.Evidence(
                opportunity_id=existing.id,
                signal_id=signal.id,
                provenance_hash=_evidence_hash(signal),
                content=extraction["pain"] or extraction["consequence"] or signal.content,
                direction="supports",
                confidence=scores["evidence_strength"],
            ))
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return existing

    difficulty = _estimate_difficulty(problem_text)

    core_signal = extraction["pain"] or extraction["consequence"] or extraction["existing_solution"] or "identified problem"
    summary_parts = [
        f'Grounded in a single strong signal: "{core_signal}".',
        f"Evidence strength {scores['evidence_strength']:.0f}/100.",
        "Single-signal opportunity (no corroborating pattern yet) — flagged for cheap validation.",
    ]
    if extraction["monetary_impact"]:
        summary_parts.append(f"Monetary impact mentioned: {extraction['monetary_impact']}.")
    if extraction["urgency"]:
        summary_parts.append("Urgency signal present (repeated/ongoing pain).")
    if extraction["buying_intent"] or extraction["desired_outcome"]:
        summary_parts.append("Willingness-to-pay / demand signal present.")

    opportunity = models.Opportunity(
        problem=problem_text,
        target_customer=extraction["customer_type"] or extraction["affected_customer"],
        solution=None,
        business_model=None,
        customer_segment=extraction["customer_type"],
        economic_consequence=extraction["consequence"] or extraction["monetary_impact"],
        problem_evidence_signal_ids=str(signal.id),
        difficulty=difficulty,
        score=_score_opportunity(1, scores["evidence_strength"], difficulty),
        economic_evidence_summary=" ".join(summary_parts),
        identity_key=identity,
    )
    db.add(opportunity)
    db.flush()

    db.add(models.Evidence(
        opportunity_id=opportunity.id,
        signal_id=signal.id,
        provenance_hash=_evidence_hash(signal),
        content=core_signal,
        direction="supports",
        confidence=scores["evidence_strength"],
    ))
    db.commit()
    db.refresh(opportunity)
    _record_event(db, opportunity, "created", {"signal_id": signal.id, "mode": "single_strong"})
    db.commit()
    return opportunity


def _evidence_hash(signal: models.Signal) -> str:
    identity = signal.content_fingerprint or signal.external_id or signal.canonical_url or str(signal.id)
    return hashlib.sha256(f"{signal.source}:{identity}".encode("utf-8")).hexdigest()


def run_autonomous_opportunity_discovery(db: Session) -> dict:
    """
    forge_loop.run_cycle()'s new step (v1.8): scans every Pattern with
    no Opportunity yet and evaluates each against real economic
    evidence. This is the direct fix for the diagnosed failure —
    patterns accumulating with nothing ever autonomously reviewing them
    for opportunities. Every pattern gets reviewed every cycle it lacks
    an opportunity; once one is created (or the pattern is reviewed and
    found wanting), it's not re-created — a pattern that gains a new
    corroborating signal next cycle would need a fresh review to be
    reconsidered, which happens naturally since only patterns still
    lacking an opportunity are scanned.
    """
    existing_pattern_ids = {
        row[0]
        for row in db.query(models.Opportunity.pattern_id).filter(models.Opportunity.pattern_id.isnot(None)).all()
    }
    candidates = [p for p in db.query(models.Pattern).all() if p.id not in existing_pattern_ids]

    created = 0
    for pattern in candidates:
        before_ids = {row[0] for row in db.query(models.Opportunity.id).filter(models.Opportunity.pattern_id == pattern.id).all()}
        result = generate_opportunity_from_pattern_if_economic(db, pattern)
        if result and result.id not in before_ids:
            created += 1

    # --- Single-strong-signal pass (v2.8) ---
    # Every reviewed pattern above is gate-protected by corroboration; but
    # CURRENT_FOCUS.md's sharp, monetizable pains (a lone complaint with a
    # named customer + dollar figure / urgency / willingness-to-pay) often
    # arrive WITHOUT a corroborating pair of signals, so they never form a
    # Pattern and the loop reports zero opportunities forever. Scan recent
    # quality-gated signals that are NOT yet attached to any Opportunity
    # and let an economically-STRONG one seed an opportunity on its own.
    # This is a narrower, stricter bar than the pattern path (is_economically_strong),
    # so it surfaces genuine lone pains without flooding noise.
    attached_signal_ids = set()
    for opp in db.query(models.Opportunity.problem_evidence_signal_ids).all():
        raw = opp.problem_evidence_signal_ids
        if raw:
            attached_signal_ids.update(int(pid) for pid in raw.split(",") if pid.strip().isdigit())

    signal_query = (
        db.query(models.Signal)
        .filter(models.Signal.is_duplicate_of.is_(None))
    )
    if attached_signal_ids:
        signal_query = signal_query.filter(models.Signal.id.notin_(list(attached_signal_ids)))
    signal_scan = signal_query.order_by(models.Signal.id.desc()).limit(400).all()
    single_signals_created = 0
    for signal in signal_scan:
        # Only consider it a candidate for the STRONG single-signal bar once.
        # idempotent by identity_key inside the helper, so repeats are safe.
        result = generate_opportunity_from_signal_if_strong(db, signal)
        if result:
            single_signals_created += 1
            # cap per cycle: surface at most a few lone signals so a burst
            # of complaints doesn't flood the pipeline in one pass.
            if single_signals_created >= 3:
                break

    return {
        "patterns_reviewed": len(candidates),
        "opportunities_created": created,
        "patterns_without_sufficient_evidence": len(candidates) - created,
        "single_strong_signals_scanned": len(signal_scan),
        "single_signal_opportunities_created": single_signals_created,
    }
