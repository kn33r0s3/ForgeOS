"""
MONEY ENGINE
=============

Turns Forge's accumulated understanding of reality into ranked,
evidence-grounded monetization opportunities for the owner — and,
critically, treats "will this make money" as something that must be
TESTED, not assumed. This module does not sell anything, contact
anyone, or process a payment; it scores what Forge already knows and
records the outcomes of real-world revenue tests.

    Opportunity (existing model, extended with monetization fields)
        |
        v
    score_opportunity() -> transparent 0-100 money_score, computed
                             LIVE from the opportunity's current
                             evidence fields — never stored/frozen,
                             so ranking always reflects current data
        |
        v
    rank_opportunities() -> every opportunity, ordered by money_score
        |
        v
    recommend_next_action() -> "what should I pursue today" — the
                                 single top-ranked opportunity plus a
                                 concrete next step, both rule-based

Revenue experiments reuse the EXISTING Experiment table (the one
already linked to Opportunity — see models.py's docstring on why) —
hypothesis/expected_result/revenue/conversions/confidence_change are
new columns on that same table, not a parallel one. record_revenue_result()
never silently rewrites a completed experiment: re-recording
identical data returns the row unchanged, re-recording conflicting
data raises (a genuinely new test plans a new Experiment row instead),
so the history of what was actually tried is never rewritten.

CRITICAL, and worth stating plainly: this module NEVER invents a
price, a revenue figure, or a confidence number. Every money-related
field on Opportunity starts at the "nothing known yet" end (0
confidence, 100 uncertainty, NULL revenue/price) and only moves when a
real Signal, Experiment, or explicit input provides evidence. If
Forge has no evidence, the honest answer is "unknown," not a plausible
guess dressed up as data — see score_opportunity()'s expected_value
logic specifically.

v1.2 adds three things beyond the v1.1 skeleton:

  - classify_evidence(): every money-relevant field gets an explicit
    epistemic label — "observed" (a real transaction happened),
    "inferred" (derived from experiment outcomes), "estimated" (a
    stated projection, never a fact), or "unknown" (nothing yet). This
    is the literal implementation of "Prediction ≠ Revenue, Belief ≠
    Customer, Interest ≠ Payment" — the distinction is enforced in
    code, not just asserted in a docstring.
  - infer_monetization_model(): keyword-driven (same tradeoff as
    everywhere else in Forge — no model call), reads existing
    business_model/offer/acquisition_path text. Falls back to
    "unknown" rather than guessing — a wrong confident label is worse
    than an honest unknown here.
  - rank_opportunities_for_owner(): a SEPARATE ranking mode from
    rank_opportunities() that explicitly rewards speed to first
    revenue — a $500 opportunity validated this week can outrank a
    theoretical $10M idea needing six months. Missing
    time_to_first_revenue_days is treated as a penalty (unknown speed
    is worse than known-slow), not ignored.
  - run_money_cycle(): the one integration point into Forge's
    autonomous loop (forge_loop.py / worker.py) — classifies
    monetization models and flags unvalidated opportunities on every
    cycle. Purely identification: never creates an experiment, never
    contacts anyone, never spends anything. Idempotent — an
    opportunity already classified is never reclassified, so repeated
    cycles don't churn or duplicate anything.

v1.3 adds Revenue Sources. An Opportunity can optionally link to
one (Opportunity.revenue_source_id). Startup does not insert payout
percentages. A grounding bonus applies only when the linked row stores
an https citation and a payout figure. A name alone does not ground a score.
suggest_revenue_sources() proposes candidates and does not link them.

Because platform payout terms change, every RevenueSource carries
data_as_of and source_citation — a number presented as current when
it's actually stale would itself be a kind of fabrication.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from typing import Optional
from app import models

# Composite score weights — sum to 1.0. Willingness-to-pay and revenue
# confidence are weighted highest: for a MONEY engine specifically,
# evidence that someone will actually pay matters more than evidence
# the problem merely exists.
WEIGHT_PROBLEM_EVIDENCE = 0.15
WEIGHT_WILLINGNESS_EVIDENCE = 0.20
WEIGHT_MARKET_CONFIDENCE = 0.10
WEIGHT_REVENUE_CONFIDENCE = 0.20
WEIGHT_EASE_IMPLEMENTATION = 0.10
WEIGHT_EASE_ACQUISITION = 0.10
WEIGHT_GOAL_PRIORITY = 0.10
WEIGHT_OWNER_PRIORITY = 0.05
UNCERTAINTY_PENALTY_WEIGHT = 0.25  # up to 25 points subtracted, same convention as strategy_engine.py

# Owner-first ranking (v1.2): blends the money_score with a dedicated
# speed-to-revenue score, weighted toward speed relative to pure
# money_score — the whole point of this ranking mode.
WEIGHT_OWNER_MONEY_SCORE = 0.6
WEIGHT_OWNER_SPEED_SCORE = 0.4
UNKNOWN_SPEED_PENALTY_SCORE = 20.0  # missing time_to_first_revenue_days is treated as slow, not ignored
SPEED_HORIZON_DAYS = 90.0  # days at/beyond which speed_score bottoms out at 0

MONETIZATION_MODELS = [
    "service", "productized_service", "saas", "digital_product", "lead_generation",
    "affiliate", "marketplace", "subscription", "consulting", "automation_service",
]
MONETIZATION_MODEL_KEYWORDS: dict[str, list[str]] = {
    "subscription": ["subscription", "monthly", "/mo", "recurring"],
    "saas": ["saas", "software as a service", "platform"],
    "lead_generation": ["lead gen", "referral fee", "commission per lead", "leads to"],
    "affiliate": ["affiliate", "revenue share", "rev share"],
    "marketplace": ["marketplace", "two-sided", "buyers and sellers"],
    "consulting": ["consult", "advisory", "audit"],
    "automation_service": ["automation", "ai service", "done-for-you", "managed service"],
    "productized_service": ["productized", "fixed-scope", "package"],
    "digital_product": ["download", "ebook", "template", "course"],
    "service": ["service", "hire", "hourly"],
}

# --- Revenue Sources (v1.3) -------------------------------------------
#
# A payout figure belongs on a row only when its citation is a stored
# primary page. Startup does not invent percentages for named platforms.
UNSOURCED_SEED_MARK = "web search, this session"
UNKNOWN_PAYOUT_TEXT = "Payout terms are unknown. No primary terms page is stored for this name."
UNKNOWN_CITATION = "No primary terms page is stored. Earlier percentages were not a sourced record."

REVENUE_SOURCE_GROUNDING_BONUS = 10.0  # flat, capped bonus for being tied to a KNOWN real payout mechanism, not an assumed one — see score_opportunity()

# Asymmetric on purpose, matching causal_engine.py's exact numbers —
# same principle throughout Forge: being wrong (no one paid) costs
# more than being right (someone paid) earns.
REVENUE_SUCCESS_BOOST = 15.0
REVENUE_FAILURE_PENALTY = 20.0
# Uncertainty drops after ANY completed test, success or failure —
# testing itself teaches Forge something regardless of outcome.
EVIDENCE_UNCERTAINTY_REDUCTION = 15.0

DEFAULT_DIFFICULTY = 50.0  # neutral assumption when difficulty hasn't been estimated yet


def utcnow():
    return datetime.now(timezone.utc)


def _evidence_strength(comma_ids: Optional[str]) -> float:
    """0-100 from how many distinct ids are listed in a comma-separated
    evidence field. Generic (works for problem_evidence_signal_ids,
    willingness_evidence_ids, or any future comma-id field) — not tied
    to one model's attribute, unlike strategy_engine.py's
    CausalKnowledge-specific version."""
    if not comma_ids:
        return 0.0
    count = len([part for part in comma_ids.split(",") if part.strip()])
    return round(min(100.0, count * 25.0), 1)


def score_opportunity(db: Session, opportunity: models.Opportunity) -> dict:
    """
    Transparent, deterministic 0-100 monetization score, computed LIVE
    from the opportunity's CURRENT persisted evidence fields — never
    fabricated, never frozen onto the row. Returns a full breakdown so
    every factor is inspectable, not just the final number ("Opportunity
    X is ranked first because...").
    """
    problem_evidence = _evidence_strength(opportunity.problem_evidence_signal_ids)
    willingness_evidence = _evidence_strength(opportunity.willingness_evidence_ids)

    goal_priority = 50.0
    if opportunity.goal_id is not None:
        goal = db.query(models.Goal).filter(models.Goal.id == opportunity.goal_id).first()
        if goal:
            goal_priority = goal.priority

    ease_implementation = 100.0 - (opportunity.implementation_difficulty or DEFAULT_DIFFICULTY)
    ease_acquisition = 100.0 - (opportunity.acquisition_difficulty or DEFAULT_DIFFICULTY)

    weighted = (
        problem_evidence * WEIGHT_PROBLEM_EVIDENCE
        + willingness_evidence * WEIGHT_WILLINGNESS_EVIDENCE
        + opportunity.market_confidence * WEIGHT_MARKET_CONFIDENCE
        + opportunity.revenue_confidence * WEIGHT_REVENUE_CONFIDENCE
        + ease_implementation * WEIGHT_EASE_IMPLEMENTATION
        + ease_acquisition * WEIGHT_EASE_ACQUISITION
        + goal_priority * WEIGHT_GOAL_PRIORITY
        + opportunity.owner_priority * WEIGHT_OWNER_PRIORITY
    )
    penalized = weighted - (opportunity.uncertainty * UNCERTAINTY_PENALTY_WEIGHT)
    # A small, capped, transparent bonus for being tied to a KNOWN real
    # payout mechanism rather than an assumed one — applied after the
    # normal weighted sum (not folded into the 1.0-summing weights
    # above) so it never changes behavior for any opportunity that
    # isn't linked to a revenue source (the common case, and every
    # scenario this module's prior scoring tests were verified against).
    grounded = _recorded_payout(db, opportunity.revenue_source_id)
    if grounded:
        penalized += REVENUE_SOURCE_GROUNDING_BONUS
    money_score = round(max(0.0, min(100.0, penalized)), 1)

    # expected_value: NEVER computed from a guess. Requires BOTH a
    # recorded figure (estimated_revenue, or estimated_price as an
    # explicit projection) AND nonzero revenue_confidence (meaning at
    # least one real experiment produced evidence). Either missing ->
    # None, reported honestly as unknown rather than invented. NOTE:
    # when only an estimated_price is present, expected_value is a
    # projection scaled by confidence, not an observed revenue figure —
    # and estimated_revenue is currently never populated by
    # record_revenue_result() (design gap, see classify_evidence).
    expected_value = None
    price_estimate = opportunity.estimated_revenue or opportunity.estimated_price
    if price_estimate is not None and opportunity.revenue_confidence > 0:
        expected_value = round(price_estimate * (opportunity.revenue_confidence / 100.0), 2)

    return {
        "money_score": money_score,
        "expected_value": expected_value,
        "revenue_source_grounded": grounded,
        "problem_evidence": problem_evidence,
        "willingness_evidence": willingness_evidence,
        "market_confidence": opportunity.market_confidence,
        "revenue_confidence": opportunity.revenue_confidence,
        "ease_implementation": round(ease_implementation, 1),
        "ease_acquisition": round(ease_acquisition, 1),
        "goal_priority": goal_priority,
        "owner_priority": opportunity.owner_priority,
        "uncertainty": opportunity.uncertainty,
    }


def _build_reasoning(opportunity: models.Opportunity, breakdown: dict) -> str:
    """Plain-text explanation generated from the same numbers used to
    score the opportunity — not an LLM call. This is the literal
    answer to "why is this ranked first.\""""
    parts = [
        f"Money score {breakdown['money_score']:.0f}/100.",
        f"Problem evidence: {breakdown['problem_evidence']:.0f}/100.",
        f"Willingness-to-pay evidence: {breakdown['willingness_evidence']:.0f}/100.",
    ]
    if breakdown["willingness_evidence"] == 0.0:
        parts.append("No willingness-to-pay evidence exists yet — this is unvalidated, not confirmed.")
    if breakdown.get("revenue_source_grounded"):
        parts.append("A payout figure is stored with an https citation.")
    if breakdown["expected_value"] is not None:
        parts.append(f"Expected value: ${breakdown['expected_value']:.2f} (from real recorded evidence).")
    else:
        parts.append("Expected value: unknown — no revenue has been recorded yet.")
    parts.append(
        f"Implementation ease {breakdown['ease_implementation']:.0f}/100, "
        f"acquisition ease {breakdown['ease_acquisition']:.0f}/100, "
        f"goal priority {breakdown['goal_priority']:.0f}/100."
    )
    if breakdown["uncertainty"] >= 60.0:
        parts.append("Uncertainty is high; treat this as exploratory.")
    return " ".join(parts)


def rank_opportunities(db: Session, goal_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    """Every opportunity (optionally scoped to one goal), scored and
    sorted by money_score descending. Returns
    [{"opportunity": Opportunity, **breakdown}, ...]."""
    query = db.query(models.Opportunity).filter(models.Opportunity.status != "archived")
    if goal_id is not None:
        query = query.filter(models.Opportunity.goal_id == goal_id)

    scored = []
    for opportunity in query.all():
        breakdown = score_opportunity(db, opportunity)
        scored.append({"opportunity": opportunity, **breakdown})

    scored.sort(key=lambda item: item["money_score"], reverse=True)
    return scored[:limit]


def recommend_next_action(db: Session) -> Optional[dict]:
    """
    "What should I pursue today to make money?" — the single highest-
    money_score opportunity across everything Forge knows, plus a
    concrete, rule-based (not LLM-judged) next step derived from its
    current experiment history. None if there are no opportunities at
    all yet.
    """
    ranked = rank_opportunities(db, limit=1)
    if not ranked:
        return None

    top = ranked[0]
    opportunity = top["opportunity"]

    experiments = (
        db.query(models.Experiment)
        .filter(models.Experiment.opportunity_id == opportunity.id)
        .order_by(models.Experiment.created_at.desc())
        .all()
    )
    pending = [e for e in experiments if e.result is None]

    if pending:
        first = pending[0]
        label = first.hypothesis or first.action or "the pending experiment"
        next_step = f'Complete the pending revenue experiment: "{label}".'
    elif not experiments:
        next_step = "Run a first revenue experiment to test willingness to pay — nothing has been tested yet."
    elif opportunity.revenue_confidence >= 60.0:
        next_step = "Evidence supports this working — consider scaling the validated approach."
    else:
        next_step = (
            "Run another revenue experiment (different price, segment, or offer) — "
            "current evidence isn't conclusive yet."
        )

    breakdown = {k: v for k, v in top.items() if k != "opportunity"}
    return {
        "opportunity": opportunity,
        "money_score": top["money_score"],
        "expected_value": top["expected_value"],
        "reasoning": _build_reasoning(opportunity, breakdown),
        "next_step": next_step,
    }


def record_revenue_experiment(
    db: Session, opportunity_id: int, hypothesis: str, action: str, expected_result: Optional[str] = None
) -> Optional[models.Experiment]:
    """Plan a revenue test against an opportunity — the Experiment row
    is created with result=None (pending) until record_revenue_result()
    completes it."""
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        return None

    experiment = models.Experiment(
        opportunity_id=opportunity_id,
        action=action,
        hypothesis=hypothesis,
        expected_result=expected_result,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def record_revenue_result(db: Session, experiment_id, result, revenue=None, conversions=None, *, data_scope=None, commit=True):
    """Atomic explicit result, cash ledger and learning. SANDBOX never trains REAL confidence."""
    import math
    from app.services import action_engine, learning_engine
    experiment = db.get(models.Experiment, experiment_id)
    if not experiment:
        return None
    scope = data_scope or experiment.data_scope
    if scope != experiment.data_scope:
        raise ValueError("Result scope must match experiment")
    if not result.strip() or (revenue is not None and (not math.isfinite(revenue) or revenue < 0)) or (conversions is not None and conversions < 0):
        raise ValueError("Result must be nonempty; amounts/counts must be finite and nonnegative")
    if experiment.status in ("blocked", "abandoned") or (experiment.requires_owner_approval and not experiment.approved_at):
        raise ValueError("Experiment is blocked/rejected or requires approval")
    if experiment.action_type == "customer_interview" and not experiment.started_at:
        raise ValueError("Record human execution first")
    if experiment.result is not None:
        if (experiment.result, experiment.revenue, experiment.conversions) != (result, revenue, conversions):
            raise ValueError("Conflicting immutable result")
        return experiment
    try:
        success = bool((revenue or 0) > 0 or (conversions or 0) > 0)
        delta = REVENUE_SUCCESS_BOOST if success else -REVENUE_FAILURE_PENALTY
        experiment.result, experiment.revenue, experiment.conversions = result, revenue, conversions
        experiment.confidence_change = delta
        experiment.status = "completed"
        experiment.completed_at = utcnow()
        action_engine.record_outcome(db, outcome_type="ACTUAL_REVENUE" if revenue is not None else "QUALITATIVE",
            experiment_id=experiment_id, actual_value=revenue, unit="USD" if revenue is not None else None,
            qualitative_result=result, success=success, data_scope=scope, commit=False,
            idempotency_key=f"experiment-result-{experiment_id}")
        learning_engine.record_learning_from_experiment(db, experiment_id,
            prediction=experiment.expected_result or experiment.hypothesis or experiment.action,
            actual=result, lesson="Explicit result recorded; revise the next test using this evidence, not estimated revenue.",
            error_type="confirmed" if success else "qualitative_miss", data_scope=scope, commit=False)
        opportunity = db.get(models.Opportunity, experiment.opportunity_id)
        if opportunity and scope == "REAL":
            opportunity.revenue_confidence = round(max(0, min(100, opportunity.revenue_confidence + delta)), 1)
            opportunity.market_confidence = round(max(0, min(100, opportunity.market_confidence + delta * .5)), 1)
            opportunity.uncertainty = max(0, opportunity.uncertainty - EVIDENCE_UNCERTAINTY_REDUCTION)
            if success:
                ids = set(filter(None, (opportunity.willingness_evidence_ids or "").split(",")))
                ids.add(str(experiment.id))
                opportunity.willingness_evidence_ids = ",".join(sorted(ids, key=int))
            opportunity.updated_at = utcnow()
        if commit:
            db.commit()
        else:
            db.flush()
        return experiment
    except Exception:
        db.rollback()
        raise


def list_revenue_experiments(db: Session, opportunity_id: Optional[int] = None) -> list[models.Experiment]:
    query = db.query(models.Experiment)
    if opportunity_id is not None:
        query = query.filter(models.Experiment.opportunity_id == opportunity_id)
    return query.order_by(models.Experiment.created_at.desc()).all()


# --- Epistemic status (v1.2) ---------------------------------------------


def classify_evidence(opportunity: models.Opportunity) -> dict:
    """
    For every money-relevant field, report its epistemic status —
    "observed" | "inferred" | "estimated" | "unknown" — never letting a
    populated number silently imply more certainty than it has earned.
    This is "Prediction ≠ Revenue, Belief ≠ Customer, Interest ≠
    Payment" enforced as code, not just stated as a principle.

      observed  - a real transaction/result actually happened
                   (estimated_revenue, populated only from a real
                   Experiment.revenue — see record_revenue_result())
      inferred  - derived from real experiment OUTCOMES but not itself
                   a direct observation (market_confidence,
                   revenue_confidence — moved by confidence deltas,
                   not observed directly)
      estimated - an explicit projection or input, never a fact
                   (estimated_price, estimated_revenue_30d/90d,
                   estimated_effort_hours, estimated_startup_cost,
                   time_to_first_revenue_days)
      unknown   - nothing has provided evidence yet
    """

    def confidence_status(value: float) -> str:
        return "inferred" if value and value > 0 else "unknown"

    def estimate_status(value) -> str:
        return "estimated" if value is not None else "unknown"

    return {
        "problem_existence": {
            "status": "observed" if opportunity.problem_evidence_signal_ids else "unknown",
            "value": opportunity.problem_evidence_signal_ids,
        },
        "willingness_to_pay": {
            "status": "observed" if opportunity.willingness_evidence_ids else "unknown",
            "value": opportunity.willingness_evidence_ids,
        },
        "revenue_source": {
            # A foreign key is not an observed payout. The score adds a
            # grounding bonus only after the linked row has an https
            # citation and a figure.
            "status": "unknown",
            "value": opportunity.revenue_source_id,
        },
        "estimated_revenue": {
            # Stated status is "estimated": the model comment intends
            # this field to be updated only from REAL recorded
            # Experiment.revenue, but nothing currently writes it —
            # record_revenue_result() updates confidence/uncertainty/
            # willingness evidence only. Until a writer exists, treat
            # any value here as a manually entered estimate, not an
            # observation (design gap, not yet resolved).
            "status": "estimated" if opportunity.estimated_revenue is not None else "unknown",
            "value": opportunity.estimated_revenue,
        },
        "estimated_price": {"status": estimate_status(opportunity.estimated_price), "value": opportunity.estimated_price},
        "revenue_confidence": {"status": confidence_status(opportunity.revenue_confidence), "value": opportunity.revenue_confidence},
        "market_confidence": {"status": confidence_status(opportunity.market_confidence), "value": opportunity.market_confidence},
        "estimated_revenue_30d": {"status": estimate_status(opportunity.estimated_revenue_30d), "value": opportunity.estimated_revenue_30d},
        "estimated_revenue_90d": {"status": estimate_status(opportunity.estimated_revenue_90d), "value": opportunity.estimated_revenue_90d},
        "time_to_first_revenue_days": {"status": estimate_status(opportunity.time_to_first_revenue_days), "value": opportunity.time_to_first_revenue_days},
        "estimated_effort_hours": {"status": estimate_status(opportunity.estimated_effort_hours), "value": opportunity.estimated_effort_hours},
        "estimated_startup_cost": {"status": estimate_status(opportunity.estimated_startup_cost), "value": opportunity.estimated_startup_cost},
    }


# --- Monetization model inference (v1.2) ----------------------------------


def infer_monetization_model(opportunity: models.Opportunity) -> str:
    """
    Rule-based (keyword-driven — same tradeoff as everywhere else in
    Forge, not a model call). Reads business_model/offer/
    acquisition_path text for signal words. Falls back to "unknown"
    rather than guessing — a wrong confident label is worse than an
    honest unknown here.
    """
    text = " ".join(
        filter(None, [opportunity.business_model, opportunity.offer, opportunity.acquisition_path])
    ).lower()
    if not text.strip():
        return "unknown"

    for model, keywords in MONETIZATION_MODEL_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return model
    return "unknown"


# --- Owner-first ranking (v1.2) -------------------------------------------


def _speed_score(time_to_first_revenue_days: Optional[float]) -> float:
    """0-100, higher = faster path to a first dollar. Missing data is a
    PENALTY (treated as slow/unproven), not neutral or ignored — an
    opportunity with no stated timeline shouldn't quietly rank as if it
    were fast."""
    if time_to_first_revenue_days is None:
        return UNKNOWN_SPEED_PENALTY_SCORE
    return round(max(0.0, min(100.0, 100.0 - (time_to_first_revenue_days / SPEED_HORIZON_DAYS) * 100.0)), 1)


def rank_opportunities_for_owner(db: Session, goal_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    """
    Owner-first ranking: explicitly rewards speed to first revenue over
    theoretical size, unlike rank_opportunities()'s pure money_score. A
    $500 opportunity validated this week can outrank a hypothetical
    $10M idea needing six months — that's the literal behavior this
    function implements.
    """
    scored = rank_opportunities(db, goal_id=goal_id, limit=1000)
    for item in scored:
        speed = _speed_score(item["opportunity"].time_to_first_revenue_days)
        item["speed_score"] = speed
        item["owner_score"] = round(
            item["money_score"] * WEIGHT_OWNER_MONEY_SCORE + speed * WEIGHT_OWNER_SPEED_SCORE, 1
        )
    scored.sort(key=lambda entry: entry["owner_score"], reverse=True)
    return scored[:limit]


# --- Money Dashboard (v1.2) ------------------------------------------------


def get_money_dashboard(db: Session) -> dict:
    """
    One consolidated read for the owner: best opportunities (both
    ranking modes), fastest path to revenue, highest 30-day estimate,
    highest confidence, what needs validation, active/completed
    revenue experiments, total real revenue recorded, conversion rate,
    and which offers won vs. failed. Every list here is a read of
    existing data — this function computes nothing new and stores
    nothing.
    """
    ranked = rank_opportunities(db, limit=200)
    owner_ranked = rank_opportunities_for_owner(db, limit=5)

    timed = [item for item in ranked if item["opportunity"].time_to_first_revenue_days is not None]
    fastest_to_revenue = sorted(timed, key=lambda item: item["opportunity"].time_to_first_revenue_days)[:5]

    projected = [item for item in ranked if item["opportunity"].estimated_revenue_30d is not None]
    highest_30d = sorted(projected, key=lambda item: item["opportunity"].estimated_revenue_30d, reverse=True)[:5]

    highest_confidence = sorted(ranked, key=lambda item: item["opportunity"].revenue_confidence, reverse=True)[:5]
    needing_validation = [item for item in ranked if item["opportunity"].revenue_confidence == 0.0][:10]

    all_revenue_experiments = (
        db.query(models.Experiment).filter(models.Experiment.hypothesis.isnot(None), models.Experiment.data_scope == "REAL").all()
    )
    completed = [e for e in all_revenue_experiments if e.result is not None]
    active = [e for e in all_revenue_experiments if e.result is None]
    winning = [e for e in completed if e.revenue and e.revenue > 0]
    failed = [e for e in completed if not (e.revenue and e.revenue > 0)]
    total_revenue = round(sum(o.actual_value or 0 for o in db.query(models.Outcome).filter_by(data_scope="REAL", outcome_type="ACTUAL_REVENUE").all()), 2)
    conversion_rate = round(len(winning) / len(completed) * 100.0, 1) if completed else None

    return {
        "best_opportunities": ranked[:5],
        "owner_priority_opportunities": owner_ranked,
        "fastest_to_revenue": fastest_to_revenue,
        "highest_30d_estimate": highest_30d,
        "highest_confidence": highest_confidence,
        "needing_validation": needing_validation,
        "active_experiments": active,
        "completed_experiments_count": len(completed),
        "total_revenue_recorded": total_revenue,
        "conversion_rate": conversion_rate,
        "winning_experiments": winning,
        "failed_experiments": failed,
    }


# --- Autonomous cycle integration (v1.2) -----------------------------------


def run_money_cycle(db: Session) -> dict:
    """
    The one integration point into Forge's autonomous loop
    (forge_loop.run_cycle(), and therefore worker.py). Per this
    round's explicit boundary: "autonomous intelligence is allowed,
    autonomous financial commitment is not" — this function only
    classifies and identifies, it NEVER creates a revenue experiment,
    contacts anyone, or spends anything.

    1. Infers monetization_model for any opportunity that doesn't have
       one yet — idempotent: an opportunity already classified is
       never reclassified, so repeated cycles neither churn the value
       nor duplicate work.
    2. Counts opportunities needing validation (zero revenue_confidence
       and no revenue experiment ever attempted) for visibility; does
       not act on them.
    """
    newly_classified = 0
    for opportunity in db.query(models.Opportunity).all():
        if opportunity.monetization_model is None:
            opportunity.monetization_model = infer_monetization_model(opportunity)
            newly_classified += 1
    if newly_classified:
        db.commit()

    needing_validation = 0
    for opportunity in db.query(models.Opportunity).filter(models.Opportunity.revenue_confidence == 0.0).all():
        has_attempt = (
            db.query(models.Experiment)
            .filter(models.Experiment.opportunity_id == opportunity.id, models.Experiment.hypothesis.isnot(None))
            .first()
        )
        if not has_attempt:
            needing_validation += 1

    return {
        "opportunities_classified": newly_classified,
        "opportunities_needing_validation": needing_validation,
    }


# --- Revenue Sources (v1.3) -------------------------------------------


def _recorded_payout(db: Session, revenue_source_id: Optional[int]) -> bool:
    """True only when the linked row stores both an https citation and a figure."""
    if revenue_source_id is None:
        return False
    source = db.query(models.RevenueSource).filter(models.RevenueSource.id == revenue_source_id).first()
    if source is None:
        return False
    citation = (source.source_citation or "").strip()
    has_figure = any(
        value is not None
        for value in (
            source.payout_share_percent_min,
            source.payout_share_percent_max,
            source.minimum_payout,
        )
    )
    return citation.startswith("https://") and has_figure


def seed_default_revenue_sources(db: Session) -> None:
    """Do not insert payout figures.

    Older startups stored platform percentages under a citation that
    said they came from a web search in that session. Those numbers are
    withdrawn. A row with any other citation is left as stored.
    """
    changed = False
    for row in db.query(models.RevenueSource).all():
        if UNSOURCED_SEED_MARK not in (row.source_citation or ""):
            continue
        row.payout_structure = UNKNOWN_PAYOUT_TEXT
        row.payout_share_percent_min = None
        row.payout_share_percent_max = None
        row.minimum_payout = None
        row.payment_frequency = None
        row.requires_approval = False
        row.source_citation = UNKNOWN_CITATION
        row.data_as_of = None
        changed = True
    if changed:
        db.commit()


def list_revenue_sources(db: Session) -> list[models.RevenueSource]:
    return db.query(models.RevenueSource).order_by(models.RevenueSource.name).all()


def suggest_revenue_sources(db: Session, opportunity: models.Opportunity) -> list[models.RevenueSource]:
    """
    Candidate RevenueSources for this opportunity, based on its already-
    inferred monetization_model — a SUGGESTION, never an assignment.
    Linking always requires an explicit call (link_revenue_source()),
    matching the "propose, don't assume" principle every other engine
    in Forge follows (Strategy Engine proposes candidates it never
    auto-selects; Curiosity Engine proposes questions it never
    auto-answers). Returns an empty list if the opportunity has no
    inferred model yet, or no seeded source matches its type.
    """
    if not opportunity.monetization_model or opportunity.monetization_model == "unknown":
        return []

    model_to_source_type = {
        "affiliate": "affiliate",
        "lead_generation": "affiliate",
        "digital_product": "marketplace",
        "productized_service": "marketplace",
        "service": "gig_platform",
        "consulting": "gig_platform",
        "automation_service": "gig_platform",
    }
    matching_type = model_to_source_type.get(opportunity.monetization_model)
    if not matching_type:
        return []

    return db.query(models.RevenueSource).filter(models.RevenueSource.source_type == matching_type).all()


def link_revenue_source(
    db: Session, opportunity_id: int, revenue_source_id: int
) -> Optional[models.Opportunity]:
    """Explicitly ground an opportunity in a real, known revenue
    source. This is the only way revenue_source_id ever gets set —
    never automatically, even when suggest_revenue_sources() returns an
    obvious match."""
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        return None
    source = db.query(models.RevenueSource).filter(models.RevenueSource.id == revenue_source_id).first()
    if not source:
        return None

    opportunity.revenue_source_id = revenue_source_id
    opportunity.updated_at = utcnow()
    db.commit()
    db.refresh(opportunity)
    return opportunity
