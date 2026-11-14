"""
GOAL ENGINE
============

The Goal Engine stores the durable target and connects it to Hami's
reasoning and work systems. Its original goal-relevance functions remain
additive. The proposal-only planning path now interprets any active Goal
through the replaceable cognition provider, records a bounded plan on an
existing WorkerTask, and emits an auditable WorldEvent. Plans identify
success criteria, assumptions, unknowns, evidence, capability gaps,
permissions, blockers and verification. They are hypotheses, not evidence,
authority, or executable Actions; this module does not perform the work.

  1. Opportunities can optionally link to the goal they serve
     (link_opportunity()).
  2. Curiosity Engine boosts a research question's priority when the
     QUESTION TEXT overlaps an active goal's keywords
     (goal_relevance_boost()).
  3. Curiosity Engine also boosts priority when the underlying PATTERN
     is structurally connected to an active goal via a real
     Opportunity link — pattern -> opportunity -> goal — not just
     wording (structural_goal_relevance()). This is a stronger signal
     than keyword overlap: it means Forge already has an Opportunity
     serving that goal built from this exact pattern, not just similar
     phrasing.
  4. The World Model (world_model.py) reports both, combined, as one
     number for display (belief_goal_relevance()) — the two are kept
     separate at the scoring/boosting call sites specifically to avoid
     double-counting the same textual signal twice.

With no goals defined, every function here returns 0.0 and nothing
downstream changes behavior — goals are strictly additive.
"""


import hashlib
import json

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services.pattern_engine import tokenize
from typing import Optional

# How much a question's priority can be boosted by TEXTUAL goal
# relevance (keyword overlap). Kept modest relative to Curiosity
# Engine's own priority scale (0-100) so a goal nudges ranking rather
# than dominating it.
MAX_GOAL_BOOST = 20.0

# How much STRUCTURAL goal relevance (a real pattern -> opportunity ->
# goal link) can contribute. Weighted higher than the textual boost —
# an actual causal connection is stronger evidence of relevance than
# shared wording.
MAX_STRUCTURAL_GOAL_BOOST = 40.0




class GoalEngine:
    def __init__(self, db: Session):
        self.db = db

    def create_goal(self, statement: str, target_metric: Optional[str] = None, priority: float = 50.0) -> models.Goal:
        goal = models.Goal(
            statement=statement.strip(),
            target_metric=target_metric,
            priority=round(max(0.0, min(100.0, priority)), 1),
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def list_goals(self, status: Optional[str] = None) -> list[models.Goal]:
        query = self.db.query(models.Goal)
        if status:
            query = query.filter(models.Goal.status == status)
        return query.order_by(models.Goal.priority.desc()).all()

    def get_goal(self, goal_id: int) -> Optional[models.Goal]:
        return self.db.query(models.Goal).filter(models.Goal.id == goal_id).first()

    def update_goal(
        self, goal: models.Goal, status: Optional[str] = None, priority: Optional[float] = None
    ) -> models.Goal:
        if status is not None:
            goal.status = status
        if priority is not None:
            goal.priority = round(max(0.0, min(100.0, priority)), 1)
        goal.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def link_opportunity(self, opportunity: models.Opportunity, goal: models.Goal) -> models.Opportunity:
        opportunity.goal_id = goal.id
        self.db.commit()
        self.db.refresh(opportunity)
        return opportunity


def goal_relevance_boost(db: Session, text: str) -> float:
    """
    Additive priority boost (0 to MAX_GOAL_BOOST) based on keyword
    overlap between `text` (e.g. a Curiosity Engine research question)
    and any ACTIVE goal's statement, scaled by that goal's own
    priority. No active goals, or no overlap with any of them -> 0.0
    (goals are an optional prioritization signal, never a requirement —
    Curiosity Engine works exactly as before if none exist).
    """
    active_goals = db.query(models.Goal).filter(models.Goal.status == "active").all()
    if not active_goals:
        return 0.0

    text_keywords = tokenize(text)
    if not text_keywords:
        return 0.0

    best_boost = 0.0
    for goal in active_goals:
        overlap = text_keywords & tokenize(goal.statement)
        if not overlap:
            continue
        raw_score = min(MAX_GOAL_BOOST, len(overlap) * 5.0)
        weighted_score = raw_score * (goal.priority / 100.0)
        best_boost = max(best_boost, weighted_score)

    return round(best_boost, 1)


def _active_goals_connected_to_pattern(db: Session, pattern_id: Optional[int]) -> list[models.Goal]:
    """Active Goals reachable via pattern -> Opportunity -> goal_id —
    a real, structural link, not keyword overlap. Empty if the pattern
    has no linked Opportunities, or none of those Opportunities serve
    an active goal."""
    if pattern_id is None:
        return []

    linked_goal_ids = {
        opportunity.goal_id
        for opportunity in db.query(models.Opportunity)
        .filter(models.Opportunity.pattern_id == pattern_id, models.Opportunity.goal_id.isnot(None))
        .all()
    }
    if not linked_goal_ids:
        return []

    return (
        db.query(models.Goal)
        .filter(models.Goal.id.in_(linked_goal_ids), models.Goal.status == "active")
        .all()
    )


def structural_goal_relevance(db: Session, pattern_id: Optional[int]) -> float:
    """
    Additive priority boost (0 to MAX_STRUCTURAL_GOAL_BOOST) when a
    Pattern is structurally connected to an active goal — i.e. Forge
    has already built a real Opportunity from this pattern that serves
    that goal. This is a stronger signal than goal_relevance_boost()'s
    keyword overlap: it means the connection already exists in the
    database, not just in the wording. 0.0 if no such connection exists
    (which is the common case — most patterns won't have a linked
    Opportunity yet).
    """
    connected_goals = _active_goals_connected_to_pattern(db, pattern_id)
    if not connected_goals:
        return 0.0
    strongest_priority = max(goal.priority for goal in connected_goals)
    return round(min(MAX_STRUCTURAL_GOAL_BOOST, strongest_priority * (MAX_STRUCTURAL_GOAL_BOOST / 100.0)), 1)


def belief_goal_relevance(db: Session, belief: models.Belief) -> float:
    """
    Combined structural + textual goal relevance for a belief, for
    DISPLAY (the World Model) rather than for priority boosting —
    Curiosity Engine calls the two components separately at their
    respective call sites to avoid double-counting the same textual
    signal twice (see run_curiosity_scan() in curiosity_engine.py).
    0.0 if there are no active goals or no relevance of either kind.
    """
    structural = structural_goal_relevance(db, belief.pattern_id)
    textual = goal_relevance_boost(db, belief.statement)
    return round(min(100.0, structural + textual), 1)



def _goal_revision(goal: models.Goal) -> str:
    """Stable digest of the exact goal version being planned."""
    payload = {
        "goal_id": goal.id,
        "statement": goal.statement,
        "target_metric": goal.target_metric,
        "status": goal.status,
        "updated_at": goal.updated_at.isoformat() if goal.updated_at else None,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def queue_goal_plan(db: Session, goal: models.Goal) -> models.WorkerTask:
    """Create or reuse one proposal-only WorkerTask for this exact goal revision."""
    if goal.status != "active":
        raise ValueError("Only an active goal can be planned")
    revision = _goal_revision(goal)
    key = f"goal-plan:v1:{goal.id}:{revision}"
    existing = db.query(models.WorkerTask).filter_by(idempotency_key=key).one_or_none()
    if existing is not None:
        return existing
    task = models.WorkerTask(
        idempotency_key=key,
        worker_type="goal_plan",
        task_name="interpret_goal_and_propose_verified_path",
        status="queued",
        priority=int(max(0, min(100, goal.priority))),
        inputs={"goal_id": goal.id, "goal_revision": revision},
        max_attempts=2,
    )
    db.add(task)
    db.flush()
    return task


def run_goal_plan_task(
    db: Session,
    worker_task: models.WorkerTask,
    *,
    provider=None,
) -> dict:
    """Produce a bounded goal plan from the replaceable provider; never execute it."""
    from app.services import cognitive_provider, tool_registry, world_graph

    if worker_task.worker_type != "goal_plan":
        raise ValueError("worker task is not a goal_plan task")
    inputs = worker_task.inputs
    if not isinstance(inputs, dict) or set(inputs) != {"goal_id", "goal_revision"}:
        raise ValueError("goal-plan task inputs do not match the contract")
    goal_id = inputs.get("goal_id")
    if type(goal_id) is not int or goal_id <= 0:
        raise ValueError("goal-plan task references an invalid goal")
    goal = db.get(models.Goal, goal_id)
    if goal is None or goal.status != "active":
        raise ValueError("goal is missing or no longer active")
    revision = _goal_revision(goal)
    if inputs.get("goal_revision") != revision:
        raise ValueError("goal changed after this plan task was queued; create a fresh plan task")
    objective = (goal.statement or "").strip()
    if not objective or len(objective) > cognitive_provider.MAX_GOAL_OBJECTIVE_CHARS:
        raise cognitive_provider.CognitiveTaskBoundsError(
            f"goal objective must contain 1 to {cognitive_provider.MAX_GOAL_OBJECTIVE_CHARS} characters"
        )
    target_metric = (goal.target_metric or "").strip() or None
    if target_metric and len(target_metric) > 500:
        raise cognitive_provider.CognitiveTaskBoundsError("goal target metric exceeds 500 characters")

    # These are declared metadata only. No availability probe or tool invocation occurs here.
    declarations = tuple(
        {
            "name": item.name,
            "category": item.category,
            "input_types": list(item.input_types),
            "output_types": list(item.output_types),
            "capabilities": list(item.capabilities),
        }
        for item in tool_registry.default_registry().list_capabilities()[
            : cognitive_provider.MAX_GOAL_CAPABILITIES
        ]
    )
    context = cognitive_provider.GoalPlanningContext(
        goal_id=goal.id,
        objective=objective,
        target_metric=target_metric,
        declared_capabilities=declarations,
    )
    selected_provider = provider or cognitive_provider.get_cognitive_provider()
    raw_plan = selected_provider.plan_goal(context)
    plan = cognitive_provider.validate_goal_plan(raw_plan)
    plan_status = plan["status"]
    provider_mode = str(getattr(selected_provider, "mode", "UNKNOWN"))
    classification = (
        "MOCK" if provider_mode == "MOCK"
        else ("HYPOTHESIS" if plan_status == "PROPOSED" else "UNKNOWN")
    )
    context_payload = {
        "goal_id": goal.id,
        "goal_revision": revision,
        "objective": objective,
        "target_metric": target_metric,
        "declared_capabilities": list(declarations),
    }
    context_digest = hashlib.sha256(
        json.dumps(context_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    plan_digest = hashlib.sha256(
        json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    provider_metadata = getattr(selected_provider, "last_call_metadata", {})
    safe_provider_metadata = {
        key: provider_metadata.get(key)
        for key in ("prompt_eval_tokens", "completion_eval_tokens", "total_duration_ms")
        if isinstance(provider_metadata, dict) and provider_metadata.get(key) is not None
    }

    world_graph.seed_core_types(db)
    world_graph.create_event(
        db,
        event_type="goal_plan_assessed",
        source="goal_engine",
        payload={
            "goal_id": goal.id,
            "worker_task_id": worker_task.id,
            "goal_revision_sha256": revision,
            "context_sha256": context_digest,
            "plan_sha256": plan_digest,
            "provider": str(getattr(selected_provider, "name", "unknown"))[:80],
            "provider_version": str(getattr(selected_provider, "version", "unknown"))[:120],
            "provider_mode": provider_mode[:32],
            "plan_status": plan_status,
            "classification": classification,
            "execution_allowed": False,
        },
        idempotency_key=f"goal-plan-assessed:v1:{worker_task.id}",
    )
    return {
        "status": plan_status,
        "classification": classification,
        "execution_allowed": False,
        "plan": plan,
        "provenance": {
            "provider": str(getattr(selected_provider, "name", "unknown"))[:80],
            "provider_version": str(getattr(selected_provider, "version", "unknown"))[:120],
            "provider_mode": provider_mode[:32],
            "goal_revision_sha256": revision,
            "context_sha256": context_digest,
            "plan_sha256": plan_digest,
            "provider_metrics": safe_provider_metadata,
        },
    }
