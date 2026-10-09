"""
ORCHESTRATOR — one canonical path through the whole ForgeOS loop.
===================================================================

This module does NOT add a new engine. It is a thin composition layer that
drives the EXISTING engines through one connected, idempotent flow so the
cycle produces a coherent operating record instead of isolated rows:

    OPPORTUNITY
      -> accepted DECISION (why + recalled past lessons)
      -> demand-validation EXPERIMENT = THE canonical executable action
            (hypothesis + X/Y success / failure criteria + time window,
             interview plan in required_inputs)  [execution_engine]
      -> HITL APPROVAL  (human enjoys the gate; nothing runs by itself)
      -> HITL EXECUTES   (human-only; a result is never fabricated)
      -> ACTUAL OUTCOME  [execution_engine.record_action_result +
                          outcome_learning.record_experiment_outcome]
      -> LEARNING EVENT -> LESSON (crosses through the SAME consolidation
         as the old experiment path)
      -> recall into NEXT decision                 [decision/lessons engine]
      -> validation gate -> PRODUCT                [product_engine]
      -> DISTRIBUTION CHANNEL                      [product_engine]
      -> CUSTOMER EVENT -> ACTUAL REVENUE          [product_engine + Outcome]
      -> LEARNING AGAIN (lesson feeds next decision)

DESIGN DECISION (inspect-first, no duplication): the codebase already has
TWO systems that both mean "an actionable unit": action_engine.Action and
execution_engine.Experiment. They collide — the autonomy duplicate-policy
guard sees an Experiment of type customer_interview as a duplicate of an
Action of the same type and blocks it. The revenue path (money_engine) owns
the Experiment lifecycle (planned -> ready -> in_progress -> completed ->
verified) and the honest revenue rollup, and its Experiment row carries
required_inputs + expected_result + policy_decision + requires_owner_approval.
So the canonical flow treats execution_engine's Experiment AS the single
actionable unit and embeds the interview plan in required_inputs. It does
NOT create a parallel action_engine.Action. action_engine.Action remains
available for the legacy manual-note path only.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import (
    decision_engine,
    execution_engine,
    outcome_learning,
    lessons_engine,
    product_engine,
    economic_intelligence,
)




# ---------------------------------------------------------------------------
# Validation-experiment defaults. Conservative, justifiable estimates an
# operator can override per run. NEVER presented as results.
# ---------------------------------------------------------------------------
DEFAULT_X_INTERVIEWS = 10          # how many prospects we aim to talk to
DEFAULT_Y_CONFIRM_PROBLEM = 5      # success bar: >=5 confirm the problem
DEFAULT_Z_WILLING_TO_PAY = 3       # success bar: >=3 willing to pay
DEFAULT_TIME_WINDOW = "72 hours"   # tight validation window (24-72h)


VALID_DATA_SCOPES = {"REAL", "SANDBOX"}
GENERIC_TARGET_MARKERS = ("to be refined", "matching the signals", "not yet identified", "target customer")

def normalize_data_scope(value: str | None) -> str:
    scope = (value or "REAL").strip().upper()
    if scope not in VALID_DATA_SCOPES:
        raise ValueError("data_scope must be REAL or SANDBOX")
    return scope

def _is_generic(value: str | None) -> bool:
    low = (value or "").strip().lower()
    return not low or any(marker in low for marker in GENERIC_TARGET_MARKERS)

def derive_opportunity_hypothesis(opp: models.Opportunity) -> dict:
    """Derive a traceable target/problem/value/offer from the opportunity's own evidence.

    This is deterministic extraction, not market validation. It replaces legacy
    placeholders such as "To be refined" without inventing customers or demand.
    """
    combined = " ".join(filter(None, [opp.problem, opp.economic_consequence, opp.solution]))
    extracted = economic_intelligence.extract_economic_signal(combined)
    target = opp.customer_segment or (None if _is_generic(opp.target_customer) else opp.target_customer)
    target = target or extracted.get("customer_type") or extracted.get("affected_customer")
    target = target or "Customer segment not yet identified from evidence"
    problem = (opp.problem or "Problem not yet specified").strip()
    low = problem.lower()
    if "no-show" in low or "no show" in low:
        value = "Reduce missed appointments and improve scheduling follow-through"
        offer = f"A service or tool that helps {target} reduce appointment no-shows"
        name = "Appointment No-Show Reduction Offer"
    elif "status" in low and ("phone" in low or "communication" in low):
        value = "Reduce staff time spent on repetitive status communication"
        offer = f"A service or tool that helps {target} automate routine status communication"
        name = "Status Communication Reduction Offer"
    else:
        consequence = (opp.economic_consequence or "").strip()
        value = f"Reduce the documented impact: {consequence}" if consequence else f"Reduce the documented problem for {target}"
        core = problem.rstrip(".")
        offer = f"A service or tool that helps {target} address: {core[:180]}"
        name = "Problem-Specific Offer Hypothesis"
    return {
        "target_customer": target,
        "problem": problem,
        "value_hypothesis": value,
        "offer_hypothesis": offer,
        "product_name": name,
        "evidence_signal_ids": opp.problem_evidence_signal_ids,
        "economic_evidence_summary": opp.economic_evidence_summary,
    }


def _interview_plan(opp: models.Opportunity, x: int, y: int, z: int) -> str:
    """Structured, human-executable interview instructions + questions."""
    derived = derive_opportunity_hypothesis(opp)
    price = opp.estimated_price
    return "\n".join([
        "DATA STATUS: HYPOTHESIS — not customer-validated",
        f"TARGET CUSTOMER TYPE: {derived['target_customer']}",
        f"SPECIFIC PROBLEM: {derived['problem']}",
        f"WHY THIS INTERVIEW: {derived['value_hypothesis']}",
        f"TASK: interview {x} real prospects matching the target customer type",
        "PLAN: contact and interview each; record their actual answer. "
        "Do NOT fabricate responses.",
        "QUESTIONS:",
        "  1. Does this problem happen often?",
        "  2. What does it cost in money, time, missed appointments, or staff effort?",
        "  3. How do you handle reminders or status communication today?",
        "  4. What does the current solution cost?",
        "  5. Would you pay for a service that measurably reduces the problem?",
        f"  6. What price would be reasonable? (Operator assumption to test: {price})",
        "EXPECTED SIGNAL: would-pay / would-not-pay / existing-solution / severity / price-sensitivity",
        f"SUCCESS BAR: >= {y} of {x} confirm the problem AND >= {z} willing to pay",
        f"TIME WINDOW: {DEFAULT_TIME_WINDOW}",
    ])


def promote_opportunity(
    db: Session,
    opportunity_id: int,
    *,
    x_interviews: int = DEFAULT_X_INTERVIEWS,
    y_confirm: int = DEFAULT_Y_CONFIRM_PROBLEM,
    z_willing: int = DEFAULT_Z_WILLING_TO_PAY,
    create_missing: bool = True,
    data_scope: str = "REAL",
    price_assumption: Optional[float] = None,
    time_window: str = DEFAULT_TIME_WINDOW,
) -> dict:
    """Ensure an opportunity has a reasoning DECISION + a validation EXECUTION
    (Experiment) with the interview plan, and report its current flow state.

    Idempotent and safe to call every cycle — only creates what is missing.
    NEVER fabricates a result and never executes an action by itself: it
    prepares the human-executable task and lets the operator perform the
    real-world part, then record the ACTUAL outcome through the existing
    execution/outcome APIs.
    """
    data_scope = normalize_data_scope(data_scope)
    opp = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opp:
        return {"status": "error", "error": f"opportunity {opportunity_id} not found"}

    derived = derive_opportunity_hypothesis(opp)
    target = derived["target_customer"]
    # Persist only a deterministic correction of a legacy placeholder. This is
    # a hypothesis derived from the opportunity text, not claimed validation.
    if create_missing and _is_generic(opp.target_customer) and not _is_generic(target):
        opp.target_customer = target
        if not opp.customer_segment:
            opp.customer_segment = target
        db.commit()

    # --- 1. Reasoning decision (with recalled past lessons) ---
    decision = (
        db.query(models.Decision)
        .filter_by(opportunity_id=opportunity_id)
        .filter(models.Decision.title.like("[SANDBOX]%") if data_scope == "SANDBOX" else ~models.Decision.title.like("[SANDBOX]%"))
        .order_by(models.Decision.created_at.desc())
        .first()
    )
    if not decision and create_missing:
        decision = decision_engine.suggest_next_experiment_decision(db, opportunity_id, data_scope=data_scope)
    if decision and decision.status == "proposed" and create_missing:
        decision = decision_engine.accept_decision(db, decision.id)

    # --- 2. The canonical validation Experiment (=== the actionable unit) ---
    experiment = (
        db.query(models.Experiment)
        .filter_by(opportunity_id=opportunity_id, action_type="customer_interview", data_scope=data_scope)
        .order_by(models.Experiment.created_at.desc())
        .first()
    )
    if not experiment and create_missing and decision and decision.status == "accepted":
        hypothesis = (
            f"{target} will pay for a service that addresses: {opp.problem[:140]}"
        )
        expected = (
            f"Success: >= {y_confirm} of {x_interviews} confirm the problem AND "
            f">= {z_willing} express willingness to pay within {time_window}. "
            f"Failure: problem is uncommon, already solved, or willingness to pay is weak."
        )
        experiment = execution_engine.create_action(
            db,
            opportunity_id=opportunity_id,
            action_type="customer_interview",
            description=f"Validate demand: interview up to {x_interviews} {target}.",
            required_inputs=_interview_plan(opp, x_interviews, y_confirm, z_willing),
            expected_result=expected,
            estimated_cost=0.0,
            data_scope=data_scope,
        )
        if experiment:
            experiment.data_scope = data_scope
            experiment.hypothesis = hypothesis
            db.commit()

    if create_missing and experiment and experiment.status == "planned" and (price_assumption is not None or time_window != DEFAULT_TIME_WINDOW):
        import math
        if price_assumption is not None and (not math.isfinite(price_assumption) or price_assumption < 0):
            raise ValueError("Price assumption must be finite and nonnegative")
        experiment.required_inputs = _interview_plan(opp, x_interviews, y_confirm, z_willing).replace(DEFAULT_TIME_WINDOW, time_window)
        assumption = f"Configurable experiment assumption: test ${price_assumption:g}/month, NOT market-validated." if price_assumption is not None else ""
        experiment.hypothesis = f"{assumption} {target} will pay for a service addressing {opp.problem[:140]}"
        experiment.required_inputs += "\n" + assumption
        experiment.expected_result = f"Assumptions: {y_confirm}/{x_interviews} confirm pain, {z_willing}/{x_interviews} willing to pay within {time_window}. " + assumption
        if decision:
            decision.expected_outcome = experiment.expected_result
        db.commit()

    # --- 3. Flow-state snapshot from REAL rows only ---
    lessons = lessons_engine.assist_decision(db, opportunity_id=opportunity_id, data_scope=data_scope)
    # outcomes link to the opportunity through the experiment (experiment_id),
    # not directly — the canonical action unit is the Experiment.
    outcomes = (
        db.query(models.Outcome)
        .filter(models.Outcome.experiment_id.isnot(None))
        .filter(
            models.Outcome.experiment_id.in_(
                db.query(models.Experiment.id).filter_by(opportunity_id=opportunity_id)
            )
        )
        .all()
    )
    products = (
        db.query(models.Product)
        .filter_by(opportunity_id=opportunity_id, data_scope=data_scope).all()
    )
    outcomes = [o for o in outcomes if o.data_scope == data_scope]
    stage = _experiment_stage(experiment)

    return {
        "data_scope": data_scope,
        "status": "advanced" if experiment else "not_started",
        "outcomes": [_row(o) for o in outcomes],
        "learning_events": [_row(e) for e in db.query(models.LearningEvent).filter_by(opportunity_id=opportunity_id, data_scope=data_scope).all()],
        "lessons": lessons["recalled_lessons"],
        "channels": [_row(c) for c in db.query(models.DistributionChannel).filter_by(opportunity_id=opportunity_id, data_scope=data_scope).all()],
        "customer_events": [_row(c) for c in db.query(models.CustomerEvent).filter_by(opportunity_id=opportunity_id, data_scope=data_scope).all()],
        "opportunity_id": opportunity_id,
        "opportunity": {
            "id": opp.id, "problem": opp.problem, "target_customer": target,
            "score": opp.score, "status": opp.status,
            "market_confidence": opp.market_confidence,
            "revenue_confidence": opp.revenue_confidence,
            "uncertainty": opp.uncertainty,
            "economic_evidence_summary": opp.economic_evidence_summary,
            "problem_evidence_signal_ids": opp.problem_evidence_signal_ids,
            "value_hypothesis": derived["value_hypothesis"],
            "offer_hypothesis": derived["offer_hypothesis"],
        },
        "decision": {
            "id": decision.id if decision else None,
            "title": decision.title if decision else None,
            "rationale": decision.rationale if decision else None,
            "status": decision.status if decision else None,
            "recalled_lessons": [l["title"] for l in lessons["recalled_lessons"]],
        },
        "experiment": {
            "id": experiment.id if experiment else None,
            "hypothesis": (experiment.hypothesis or experiment.action) if experiment else None,
            "expected_result": experiment.expected_result if experiment else None,
            "status": experiment.status if experiment else None,
            "policy_decision": experiment.policy_decision if experiment else None,
            "requires_owner_approval": bool(experiment and experiment.requires_owner_approval),
            "stage": stage,
            "required_inputs": (experiment.required_inputs or "").split("\n") if experiment else [],
            "result": experiment.result if experiment else None,
            "data_scope": experiment.data_scope if experiment else None,
            "revenue": experiment.revenue if experiment else None,
            "conversions": experiment.conversions if experiment else None,
        },
        "outcomes_count": len(outcomes),
        "products": [product_engine.product_summary(db, p) for p in products],
        "lessons_recalled": len(lessons["recalled_lessons"]),
    }


def _experiment_stage(exp: Optional[models.Experiment]) -> str:
    """Map the Experiment lifecycle to the §4 action lifecycle words."""
    if not exp:
        return "PROPOSED"
    if exp.status == "completed":
        return "LEARNED" if exp.lesson else "MEASURED"
    if exp.status == "in_progress":
        return "OUTCOME_PENDING"
    if exp.status == "ready":
        return "EXECUTABLE"
    if exp.status == "planned":
        return "APPROVAL_REQUIRED" if exp.requires_owner_approval else "APPROVED"
    if exp.status == "blocked":
        return "BLOCKED"
    if exp.status == "abandoned":
        return "CANCELLED"
    return "PROPOSED"


def create_product_for_validated(
    db: Session,
    opportunity_id: int,
    *,
    y_confirm: int = DEFAULT_Y_CONFIRM_PROBLEM,
    z_willing: int = DEFAULT_Z_WILLING_TO_PAY,
    name: Optional[str] = None,
    data_scope: str = "REAL",
) -> dict:
    """Create a validating Product for an opportunity whose real outcomes clear
    the demand bar. Idempotent: one product per opportunity."""
    opp = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opp:
        return {"status": "error", "error": "opportunity not found"}

    data_scope = normalize_data_scope(data_scope)
    existing = db.query(models.Product).filter_by(opportunity_id=opportunity_id, data_scope=data_scope).first()
    if existing:
        return {"status": "exists", "product_id": existing.id,
                "product": product_engine.product_summary(db, existing)}

    confirm_problem, will_pay = validation_counts(db, opportunity_id, data_scope)
    if y_confirm < 1 or z_willing < 1:
        raise ValueError("Validation thresholds must be positive")

    if confirm_problem < y_confirm or will_pay < z_willing:
        return {
            "status": "not_validated",
            "reason": (
                f"Demand not proven: {confirm_problem}/{y_confirm} confirmed the problem, "
                f"{will_pay}/{z_willing} showed willingness to pay."
            ),
            "confirm_problem": confirm_problem, "will_pay": will_pay,
        }

    derived = derive_opportunity_hypothesis(opp)
    product = product_engine.create_product(
        db,
        opportunity_id=opportunity_id,
        name=name or derived["product_name"],
        offer=derived["offer_hypothesis"],
        target_customer=derived["target_customer"],
        pricing=opp.pricing_idea,
        mvp_scope="Simplest version that solves the validated problem",
        hypothesis=(
            f"HYPOTHESIS: {derived['target_customer']} will pay for {derived['offer_hypothesis']}. "
            f"Value assumption: {derived['value_hypothesis']}."
        ),
        launch_state="not_launched",
        data_scope=data_scope,
    )
    product.status = "validating"
    if data_scope == "REAL":
        opp.status = "validating"
    db.commit()
    return {"status": "created", "product_id": product.id,
            "product": product_engine.product_summary(db, product)}


def _first_money(text: str | None) -> Optional[float]:
    match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else None

def record_demand_outcome(
    db: Session,
    experiment_id: int,
    *,
    actual: str,
    success: Optional[bool] = None,
    actual_value: Optional[float] = None,
    unit: Optional[str] = None,
    source: str = "human_interview",
    conversions: Optional[int] = None,
    contacts: Optional[list[dict]] = None,
    data_scope: str = "REAL",
) -> dict:
    """THE HITL bridge: an operator records the ACTUAL interview response for
    one human-executed action.

    Uses the canonical revenue path (execution_engine.record_action_result ->
    money_engine.record_revenue_result) so real recorded figures (revenue,
    conversions) land on the Experiment and pull the honest confidence
    updates, then records the Outcome + LearningEvent + Lesson through
    outcome_learning. Optionally logs each real interview as a CustomerEvent
    (the §8 ledger) when `contacts` is supplied. NEVER fabricates a customer
    answer — `actual` and `contacts` are the human-recorded reality.
    """
    data_scope = normalize_data_scope(data_scope)
    exp = db.get(models.Experiment, experiment_id)
    if not exp:
        raise ValueError(f"Experiment {experiment_id} not found")
    if exp.status in ("blocked", "abandoned"):
        raise ValueError(f"Cannot record an outcome for {exp.status} experiment")
    if exp.requires_owner_approval and exp.approved_at is None:
        raise ValueError("Owner approval is required before external execution/outcome recording")
    if exp.status != "in_progress" and exp.completed_at is None:
        raise ValueError("Mark the human task executed before recording the business outcome")
    if exp.data_scope != data_scope:
        raise ValueError(f"Outcome scope {data_scope} does not match experiment scope {exp.data_scope}")

    try:
        # The interview's stated price is a response measurement, NOT collected
        # revenue. Keep Experiment.revenue null unless a separate ACTUAL_REVENUE
        # event is explicitly recorded after money is genuinely collected.
        if not actual.strip() or (conversions is not None and conversions < 0):
            raise ValueError("Nonempty actual response and nonnegative willingness count required")
        existing = db.query(models.Outcome).filter_by(experiment_id=experiment_id, outcome_type="ACTUAL_RESPONSE").first()
        if existing:
            if existing.qualitative_result != actual or exp.conversions != conversions or existing.success != success or existing.actual_value != actual_value or existing.unit != unit:
                raise ValueError("Outcome already recorded; conflicting retry rejected")
            return {"outcome": existing, "learning": db.query(models.LearningEvent).filter_by(experiment_id=experiment_id).first(), "reused": True}
        exp.conversions = conversions
    
        expected_price = _first_money(exp.hypothesis or exp.expected_result or exp.action)
        # Prefer an explicit measured price over text that may mention both prices.
        actual_price = actual_value if unit and unit.lower() in ("usd", "usd/month", "usd_per_month") else None
        if actual_price is None:
            prices = re.findall(r"\$\s*(\d+(?:\.\d+)?)", actual)
            actual_price = float(prices[-1]) if prices else None
        if expected_price is None:
            opp = db.get(models.Opportunity, exp.opportunity_id)
            expected_price = opp.estimated_price
        prediction_error = None
        error_type = "confirmed" if success is True else "qualitative_miss" if success is False else None
        lesson = "Actual outcome recorded; causal explanation remains uncertain unless separately supported."
        if expected_price and actual_price and actual_price < expected_price:
            prediction_error = (actual_price - expected_price) / expected_price
            error_type = "overestimate"
            lesson = (f"Price sensitivity: the sandbox/real outcome rejected about ${expected_price:g} "
                      f"and indicated about ${actual_price:g}. Test the lower price rather than repeating the higher assumption.")
    
        # Outcome + LearningEvent + Lesson consolidation (idempotent).
        result = outcome_learning.record_experiment_outcome(
            db, experiment_id, actual=actual, success=success, source=source,
            actual_value=actual_value, unit=unit, lesson=lesson,
            prediction_error=prediction_error, error_type=error_type,
            data_scope=data_scope, outcome_type="ACTUAL_RESPONSE", commit=False,
        )
    
        # 3) Optional per-interview ledger entries (real contacts, honest stages).
        if contacts:
            exp = db.get(models.Experiment, experiment_id)  # SQLAlchemy 2.x Session.get
            opp_id = exp.opportunity_id if exp else None
            for c in contacts:
                product_engine.create_customer_event(
                    db,
                    opportunity_id=opp_id,
                    contact_name=c.get("name"),
                    contact_identifier=c.get("identifier"),
                    segment=c.get("segment"),
                    stage=c.get("stage", "lead"),
                    event_type=c.get("event_type", "response"),
                    notes=c.get("notes"),
                    outcome_id=result["outcome"].id,
                    data_scope=data_scope,
                    commit=False,
                )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def run_orchestration_flow(
    db: Session,
    *,
    limit: int = 5,
    opportunity_id: Optional[int] = None,
    data_scope: str = "REAL",
) -> dict:
    """Advance the highest-value unvalidated opportunities and report the
    full operating snapshot. The single orchestration point the cycle,
    scheduler, and frontend call. Idempotent."""
    if opportunity_id is not None:
        opps = db.query(models.Opportunity).filter_by(id=opportunity_id).all()
    else:
        opps = [o for o in ranked_opportunities(db, 10000) if o.status == "identified"][:limit]

    advanced = []
    for opp in opps:
        advanced.append(promote_opportunity(db, opp.id, data_scope=data_scope))

    return {
        "opportunities_advanced": len(advanced),
        "flow": advanced,
        "pipeline": _flow_snapshot(db),
    }


def _flow_snapshot(db: Session) -> dict:
    """Honest stage counts — how much of the chain has really been exercised."""
    real_revenue = db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE", data_scope="REAL").all()
    sandbox_revenue = db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE", data_scope="SANDBOX").all()
    return {
        "signals": db.query(models.Signal).count(),
        "opportunities": db.query(models.Opportunity).count(),
        # an opportunity is 'live' once it has started a validation execution
        "decisions_accepted": db.query(models.Decision).filter_by(status="accepted").count(),
        "validation_experiments": db.query(models.Experiment).filter_by(action_type="customer_interview").count(),
        "experiments_completed": db.query(models.Experiment).filter_by(status="completed").count(),
        "outcomes": db.query(models.Outcome).filter_by(data_scope="REAL").count(),
        "learning_events": db.query(models.LearningEvent).filter_by(data_scope="REAL").count(),
        "lessons": db.query(models.Lesson).filter_by(data_scope="REAL").count(),
        "products": db.query(models.Product).filter_by(data_scope="REAL").count(),
        "distribution_channels": db.query(models.DistributionChannel).filter_by(data_scope="REAL").count(),
        "customer_events": db.query(models.CustomerEvent).filter_by(data_scope="REAL").count(),
        "actions_awaiting_approval": db.query(models.Experiment)
            .filter(models.Experiment.status.in_(["planned"])).count(),
        "actual_revenue": round(sum(float(o.actual_value or 0) for o in real_revenue if (o.unit or "USD").upper() == "USD"), 2),
        "real_customers": int(sum(float(o.actual_value or 0) for o in db.query(models.Outcome).filter_by(outcome_type="ACTUAL_CUSTOMERS", data_scope="REAL").all())),
        "sandbox": {
            "actual_revenue": round(sum(float(o.actual_value or 0) for o in sandbox_revenue if (o.unit or "USD").upper() == "USD"), 2),
            "outcomes": db.query(models.Outcome).filter_by(data_scope="SANDBOX").count(),
            "products": db.query(models.Product).filter_by(data_scope="SANDBOX").count(),
            "label": "TEST/SANDBOX — not real business traction",
        },
        "products_with_revenue": db.query(models.Product)
            .filter_by(data_scope="REAL").filter(models.Product.actual_revenue > 0.0).count(),
    }


def _row(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def ranked_opportunities(db, limit=50):
    """Preserve legacy records, deprioritize ones failing current quality gate."""
    from app.services.economic_intelligence import is_economically_strong, extract_economic_signal, score_economic_signal
    rows = db.query(models.Opportunity).all()
    def quality(o):
        try:
            extraction = extract_economic_signal(o.problem)
            return is_economically_strong(extraction, score_economic_signal(extraction))
        except (TypeError, AttributeError):
            return False
    return sorted(rows, key=lambda o: (quality(o), o.score or 0), reverse=True)[:limit]


def validation_counts(db, opportunity_id, data_scope):
    experiments = (
        db.query(models.Experiment).filter_by(opportunity_id=opportunity_id).all()
    )
    # confirm_problem: real interview outcomes marked success + any customer
    # event that reached an interested/paying stage (recorded by the human).
    outcomes = (
        db.query(models.Outcome)
        .filter(models.Outcome.experiment_id.isnot(None))
        .filter(
            models.Outcome.experiment_id.in_(
                db.query(models.Experiment.id).filter_by(opportunity_id=opportunity_id)
            )
        )
        .all()
    )
    outcomes = [o for o in outcomes if o.data_scope == data_scope]
    response_ids = {o.id for o in outcomes if o.outcome_type == "ACTUAL_RESPONSE"}
    interest_events = db.query(models.CustomerEvent).filter_by(opportunity_id=opportunity_id, data_scope=data_scope).all()
    interest_events = [c for c in interest_events if c.outcome_id in response_ids]
    # Prefer per-contact evidence. Fall back to one aggregate confirmation only
    # when no contact ledger exists; never double-count the same interview.
    # Unique identifiable contacts only; repeated events are not new people.
    groups = {}
    for ce in interest_events:
        key = (ce.contact_identifier or ce.contact_name or "").strip().lower()
        if key:
            groups.setdefault(key, []).append(ce)
    confirm_problem = sum(any(c.stage in ("interested", "paid_customer") or
        (c.notes or "").lower().startswith("confirmed") for c in rows) for rows in groups.values())
    # Aggregate willingness is capped by unique respondents and never adds
    # revenue a second time. This remains reported demand, not paid customers.
    eligible_exp_ids = {o.experiment_id for o in outcomes if o.outcome_type == "ACTUAL_RESPONSE"}
    willing_contacts = sum(any(c.stage in ("interested", "paid_customer") for c in rows) for rows in groups.values())
    will_pay = min(willing_contacts, sum(int(e.conversions or 0) for e in experiments
        if e.id in eligible_exp_ids and e.data_scope == data_scope and e.status == "completed"))
    return confirm_problem, will_pay
