import re
from typing import Optional
"""
API routes for Forge's intelligence layer: the cycle orchestrator,
Belief Engine, Curiosity Engine output, Research Planner output, and
Source reliability tracking.

    POST /forge/cycle                       -> run one full intelligence cycle
    GET  /forge/questions                    -> what Forge currently wants to learn
    GET  /forge/tasks                         -> planned research tasks
    GET  /forge/beliefs                        -> current beliefs, highest confidence first
    GET  /forge/unknowns                       -> discovery unknowns from Claim primitives
    POST /forge/beliefs/{id}/check              -> re-score one belief against current signals
    POST /forge/beliefs/{id}/experiments          -> plan a real-world test of a belief
    POST /forge/experiments/{id}/result            -> record what actually happened
    GET  /forge/experiments                         -> list belief experiments
    GET  /forge/sources                               -> tracked source reliability
    GET  /forge/causal-knowledge                       -> structured condition/action/outcome facts
    POST /forge/goals/{id}/strategies                    -> generate candidate strategies for a goal
    GET  /forge/goals/{id}/strategies                     -> list candidate strategies for a goal
    GET  /forge/strategies/compare                         -> compare two strategies, with explanation
    GET  /forge/world/goals/{id}                             -> the Strategic (goal-scoped) World Model view
    GET  /forge/money/opportunities                            -> ranked opportunities by money_score
    GET  /forge/money/opportunities/{id}                        -> full monetization view of one opportunity
    GET  /forge/money/recommend                                  -> "what should I pursue today"
    POST /forge/opportunities/{id}/revenue-experiments             -> plan a revenue test
    POST /forge/revenue-experiments/{id}/result                     -> record what actually happened
    GET  /forge/money/opportunities/{id}/evidence                    -> observed/inferred/estimated/unknown labels
    GET  /forge/money/opportunities/owner-ranked                      -> ranked by speed to first revenue, not just money_score
    GET  /forge/money/dashboard                                        -> consolidated owner view
    GET  /forge/revenue-sources                                         -> known real payout mechanisms (sourced, dated)
    GET  /forge/money/opportunities/{id}/suggested-sources                -> candidate sources for one opportunity
    POST /forge/money/opportunities/{id}/revenue-source                    -> explicitly link a real source
    POST /forge/execution/actions                                          -> create a trackable executable action
    GET  /forge/execution/actions                                          -> list execution actions
    GET  /forge/execution/actions/{id}                                     -> one action's full state
    POST /forge/execution/actions/{id}/approve                             -> explicit owner approval gate
    POST /forge/execution/actions/{id}/start                               -> mark in progress
    POST /forge/execution/actions/{id}/result                              -> record what actually happened
    GET  /forge/execution/actions/{id}/package                             -> evidence cited for a require_approval action
    POST /forge/execution/actions/{id}/human-result                        -> human outcome after approval, no revenue
    POST /forge/execution/actions/{id}/verified-revenue                    -> revenue only from a verified payment
    GET  /forge/execution/rank                                             -> ranked pending actions
    GET  /forge/execution/recommend                                        -> "what should I do right now"
    GET  /forge/autonomy/policy                                             -> the owner's current operating boundary
    PATCH /forge/autonomy/policy                                            -> adjust the boundary
    GET  /forge/autonomy/evaluate                                           -> preview a policy decision without creating an action
    GET  /forge/execution/actions/blocked                                   -> actions policy blocked outright
    GET  /forge/money/revenue-breakdown                                     -> potential vs expected vs realized
    GET  /forge/strategies/{id}/performance                                 -> real recorded track record for one strategy
    POST /forge/autonomy/run-cycle                                          -> manually trigger one autonomous proposal pass
    POST /forge/economic/discover                                           -> manually trigger evidence-gated opportunity discovery
    GET  /forge/economic/patterns/{id}/corroboration                        -> source diversity for one pattern
    GET  /forge/scenarios                                                    -> Phase 1 2036 Scenario Engine overview (secondary domain)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models
from app.config import settings
from app.security import require_owner_api_key
from app.services import (
    reality_checker,
    reality_memory,
    experiment_runner,
    source_manager,
    knowledge_miner,
    memory_layer,
    ai_engine,
    world_model,
    goal_engine,
    causal_engine,
    strategy_engine,
    money_engine,
    execution_engine,
    autonomy_engine,
    opportunity_engine,
    economic_intelligence,
    scenario_engine,
    approval_outcome_bridge,
)

router = APIRouter(prefix="/forge", tags=["forge"])


def _require_legacy_intelligence() -> None:
    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        raise HTTPException(status_code=503, detail="Legacy intelligence is disabled.")


@router.post("/cycle", response_model=schemas.ForgeCycleSummary)
def run_cycle(data_scope: str = "REAL", db: Session = Depends(get_db)):
    """Run one full Forge intelligence cycle: refresh patterns, form/
    update beliefs, reality-check existing beliefs, and generate new
    research questions + tasks from any weak spots found."""
    _require_legacy_intelligence()
    from app.services import forge_loop

    return forge_loop.run_cycle(db, data_scope=data_scope)


@router.get("/questions", response_model=list[schemas.ResearchQuestionOut])
def get_questions(request: Request, status: Optional[str] = None, db: Session = Depends(get_db)):
    """What Forge currently wants to learn, highest priority first.
    Filter with ?status=open|planned|closed.
    Owner-only: internal research objectives."""
    require_owner_api_key(request)
    query = db.query(models.ResearchQuestion)
    if status:
        query = query.filter(models.ResearchQuestion.status == status)
    return query.order_by(models.ResearchQuestion.priority_score.desc()).all()


@router.get("/tasks", response_model=list[schemas.ResearchTaskOut])
def get_tasks(request: Request, db: Session = Depends(get_db)):
    """Research tasks planned from open questions — not yet executed
    by any collector in v0.1.
    Owner-only: internal task details."""
    require_owner_api_key(request)
    return db.query(models.ResearchTask).order_by(models.ResearchTask.created_at.desc()).all()


@router.get("/tasks/{task_id}/history", response_model=list[schemas.ResearchTaskEventOut])
def get_task_history(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.ResearchTask).filter(models.ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return (
        db.query(models.ResearchTaskEvent)
        .filter(models.ResearchTaskEvent.task_id == task_id)
        .order_by(models.ResearchTaskEvent.created_at.asc(), models.ResearchTaskEvent.id.asc())
        .all()
    )


@router.post("/tasks/{task_id}/retry", response_model=schemas.ResearchTaskOut)
def retry_research_task(task_id: int, db: Session = Depends(get_db)):
    from app.services import research_task_engine

    task = db.query(models.ResearchTask).filter(models.ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return research_task_engine.retry_task(db, task)


@router.get("/beliefs", response_model=list[schemas.BeliefOut])
def get_beliefs(db: Session = Depends(get_db)):
    """Current beliefs, highest confidence first."""
    from app.services.belief_engine import is_presentable_belief
    rows = (
        db.query(models.Belief)
        .filter(models.Belief.merged_into_id.is_(None))
        .order_by(models.Belief.confidence_score.desc())
        .all()
    )
    return [row for row in rows if is_presentable_belief(row)]


_UNKNOWN_ROW_RE = re.compile(r"row (D\d+)", re.IGNORECASE)


def _unknown_from_claim(row: models.Claim) -> schemas.UnknownOut:
    provenance = row.provenance or ""
    match = _UNKNOWN_ROW_RE.search(provenance)
    row_id = match.group(1).upper() if match else f"C{row.id}"
    cheapest_test = ""
    if "Cheapest test:" in provenance:
        cheapest_test = provenance.split("Cheapest test:", 1)[1].strip()
    return schemas.UnknownOut(
        id=row.id,
        row_id=row_id,
        question=row.statement,
        epistemic_state=row.epistemic_state,
        cheapest_test=cheapest_test,
        provenance=provenance or None,
    )


@router.get("/unknowns", response_model=list[schemas.UnknownOut])
def get_unknowns(db: Session = Depends(get_db)):
    """Public projection of the discovery unknowns, parsed from stored
    Claim primitives. Every item carries its truth label
    (epistemic_state) and its source (provenance) — the page displays
    this and nothing hand-written.

    Not gated by the legacy-intelligence flag: this is the live
    discovery pipeline (rounds -> map -> importer -> Claim), not the
    retired pattern/belief/curiosity loop."""
    rows = (
        db.query(models.Claim)
        .filter(models.Claim.provenance.like("%UNKNOWN_MAP.md%"))
        .order_by(models.Claim.id.asc())
        .all()
    )
    return [_unknown_from_claim(row) for row in rows]


@router.post("/beliefs/{belief_id}/check", response_model=schemas.BeliefCheckResponse)
def check_belief(belief_id: int, db: Session = Depends(get_db)):
    """Re-score one belief against the current signal pool right now,
    without waiting for the next full cycle."""
    belief = db.query(models.Belief).filter(models.Belief.id == belief_id).first()
    if not belief:
        raise HTTPException(status_code=404, detail="Belief not found")
    return reality_checker.check_belief(db, belief)


@router.post("/beliefs/{belief_id}/experiments", response_model=schemas.BeliefExperimentOut)
def create_belief_experiment(
    belief_id: int, payload: schemas.BeliefExperimentCreate, db: Session = Depends(get_db)
):
    """Plan a real-world test of a belief (e.g. build an MVP and
    measure the result)."""
    belief = db.query(models.Belief).filter(models.Belief.id == belief_id).first()
    if not belief:
        raise HTTPException(status_code=404, detail="Belief not found")
    return experiment_runner.ExperimentRunner(db).create_experiment(
        belief_id, payload.hypothesis, payload.method
    )


@router.post("/experiments/{experiment_id}/result", response_model=schemas.BeliefExperimentOut)
def record_experiment_result(
    experiment_id: int, payload: schemas.BeliefExperimentResult, db: Session = Depends(get_db)
):
    """Record what actually happened and push the resulting confidence
    change into the linked belief."""
    try:
        experiment = experiment_runner.ExperimentRunner(db).record_result(
            experiment_id, payload.result, payload.confidence_change
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


@router.get("/experiments", response_model=list[schemas.BeliefExperimentOut])
def list_experiments(belief_id: Optional[int] = None, db: Session = Depends(get_db)):
    return experiment_runner.ExperimentRunner(db).list_experiments(belief_id=belief_id)


@router.get("/sources", response_model=list[schemas.SourceOut])
def get_sources(db: Session = Depends(get_db)):
    """Tracked reliability of each observation source."""
    return source_manager.list_sources(db)


@router.get("/predictions", response_model=list[schemas.PredictionOut])
def get_predictions(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Predictions Forge has made from confident beliefs. Filter with
    ?status=pending|confirmed|failed."""
    return reality_memory.list_predictions(db, status=status)


@router.get("/evidence", response_model=list[schemas.EvidenceOut])
def get_evidence(request: Request, belief_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Evidence Reality Memory has persisted, optionally filtered to
    one belief.
    Owner-only: internal evidence metadata."""
    require_owner_api_key(request)
    return reality_memory.list_evidence(db, belief_id=belief_id)


@router.post("/knowledge/mine", response_model=schemas.KnowledgeMineResponse)
def mine_knowledge(request: Request, payload: schemas.KnowledgeMineRequest, db: Session = Depends(get_db)):
    """Knowledge Mining Engine: extract strategy/behavior insights from
    a long piece of text (a book excerpt, paper, story, etc.) and store
    each as a Signal — they flow through the normal Observer -> Pattern
    -> Belief pipeline from there, exactly like any other signal.

    Owner-only: this writes arbitrary Signal rows into the DB."""
    require_owner_api_key(request)
    signal_ids = knowledge_miner.mine_document(db, payload.content, source_label=payload.source_label)
    return schemas.KnowledgeMineResponse(
        source_label=payload.source_label,
        insights_found=len(signal_ids),
        signal_ids=signal_ids,
    )


@router.post("/tasks/{task_id}/run", response_model=schemas.TaskRunResult)
def run_task(task_id: int, db: Session = Depends(get_db)):
    """Execute one planned research task through its matching collector
    right now (rather than waiting for the Background Forge Worker).
    An uncleared source fails the task and does not collect. A cleared
    web task may open that page. Network errors mark the task failed
    rather than raising."""
    _require_legacy_intelligence()
    from app.services import collector_runner

    task = db.query(models.ResearchTask).filter(models.ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    return collector_runner.execute_task(db, task)


@router.post("/tasks/run-pending", response_model=list[schemas.TaskRunResult])
def run_pending_tasks(limit: int = 5, db: Session = Depends(get_db)):
    """Execute a batch of currently-planned research tasks right now."""
    _require_legacy_intelligence()
    from app.services import collector_runner

    return collector_runner.run_pending_tasks(db, limit=limit)


@router.post("/collect", response_model=list[schemas.DefaultCollectionResult])
def collect_default(db: Session = Depends(get_db)):
    """Record that the standing Reddit, GitHub, RSS, and arXiv feeds
    are skipped. None is cleared in docs/PUBLIC_SOURCES.md, so this
    route does not open those requests."""
    _require_legacy_intelligence()
    from app.services import collector_runner

    return collector_runner.run_default_collection(db)


@router.get("/knowledge", response_model=list[schemas.KnowledgeSearchResult])
def search_knowledge(request: Request, query: str, top_k: int = 5, source_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Semantic search over Forge's permanent Knowledge memory (synced
    from Beliefs/Patterns). This is the same retrieval mechanism
    POST /forge/ask uses internally, exposed directly for inspection.
    Owner-only: this reads the owner's internal belief/pattern memory."""
    require_owner_api_key(request)
    matches = memory_layer.search_knowledge(db, query, top_k=top_k, source_type=source_type)
    return [
        schemas.KnowledgeSearchResult(knowledge=knowledge, similarity=round(similarity, 4))
        for knowledge, similarity in matches
    ]


@router.get("/knowledge/list", response_model=list[schemas.KnowledgeOut])
def list_knowledge(request: Request, source_type: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    """Browse Knowledge entries without a search query, most recently
    updated first. Owner-only: internal memory."""
    require_owner_api_key(request)
    return memory_layer.list_knowledge(db, source_type=source_type, limit=limit)


@router.post("/ask", response_model=schemas.AskResponse)
def ask_forge(request: Request, payload: schemas.AskRequest, db: Session = Depends(get_db)):
    """
    Ask Forge a question. Forge is not a chatbot — it retrieves
    relevant memories from its own Knowledge base FIRST (beliefs and
    patterns it has actually formed and evidence-linked), then answers
    grounded in only that, via whichever AI provider is configured
    (free mock, free local Ollama, or optional paid OpenAI). If nothing
    relevant exists yet, it says so rather than guessing.

    Owner-only: an unauthenticated caller could trigger AI provider
    calls (paid OpenAI path, or local Ollama compute) at the owner's
    expense, and read internal memory through the answers."""
    require_owner_api_key(request)
    result = ai_engine.answer_question(payload.question, db)
    matches = memory_layer.search_knowledge(db, payload.question, top_k=5)
    memories_used = [knowledge for knowledge, _similarity in matches]
    return schemas.AskResponse(question=payload.question, answer=result["answer"], memories_used=memories_used)


@router.get("/world/beliefs/{belief_id}", response_model=schemas.BeliefGraph)
def get_belief_graph(belief_id: int, db: Session = Depends(get_db)):
    """
    The Temporal, Goal-Aware, Causal World Model view of one belief:
    which pattern caused it, which opportunities and goals that
    pattern connects to (so Forge can answer not just "where did this
    come from" but "why does it matter"), supporting and contradicting
    evidence, the sources that produced it and their current
    reliability, when it was last tested against reality, similar
    beliefs (via the Memory Layer's embeddings), every real-world
    experiment run against it, its full confidence-change history
    (with reason + evidence for each change), its stability score +
    trend (is this settling into stable knowledge or still swinging?),
    and what Forge has actually learned from testing real actions
    tied to it (related_causal_knowledge / successful_actions /
    failed_actions). This is a read-only synthesis over existing
    tables, not a new store of facts.
    """
    graph = world_model.get_belief_graph(db, belief_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Belief not found")
    return graph


@router.post("/goals", response_model=schemas.GoalOut)
def create_goal(payload: schemas.GoalCreate, db: Session = Depends(get_db)):
    """Create a Goal — something Forge is currently trying to make
    progress toward. Optional and additive: Forge works exactly as
    before if no goals ever exist."""
    return goal_engine.GoalEngine(db).create_goal(
        payload.statement, target_metric=payload.target_metric, priority=payload.priority
    )


@router.get("/goals", response_model=list[schemas.GoalOut])
def list_goals(status: Optional[str] = None, db: Session = Depends(get_db)):
    """List goals, highest priority first. Filter with ?status=active|paused|achieved|abandoned."""
    return goal_engine.GoalEngine(db).list_goals(status=status)


@router.patch("/goals/{goal_id}", response_model=schemas.GoalOut)
def update_goal(goal_id: int, payload: schemas.GoalUpdate, db: Session = Depends(get_db)):
    """Update a goal's status and/or priority."""
    engine = goal_engine.GoalEngine(db)
    goal = engine.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return engine.update_goal(goal, status=payload.status, priority=payload.priority)


@router.post("/goals/{goal_id}/opportunities/{opportunity_id}", response_model=schemas.OpportunityOut)
def link_opportunity_to_goal(goal_id: int, opportunity_id: int, db: Session = Depends(get_db)):
    """Link an existing Opportunity to the Goal it serves."""
    engine = goal_engine.GoalEngine(db)
    goal = engine.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return engine.link_opportunity(opportunity, goal)


@router.get("/causal-knowledge", response_model=list[schemas.CausalKnowledgeOut])
def get_causal_knowledge(
    belief_id: Optional[int] = None, goal_id: Optional[int] = None, db: Session = Depends(get_db)
):
    """
    Browse Forge's causal knowledge — structured condition/action/
    outcome facts built automatically from completed BeliefExperiments
    (see causal_engine.py). Highest confidence first. Filter with
    ?belief_id= or ?goal_id=.
    """
    return causal_engine.list_causal_knowledge(db, belief_id=belief_id, goal_id=goal_id)


@router.post("/goals/{goal_id}/strategies", response_model=list[schemas.StrategyOut])
def generate_strategies(goal_id: int, db: Session = Depends(get_db)):
    """
    Generate (or refresh) candidate strategies for one Goal, grounded
    entirely in Forge's own beliefs and causal knowledge — never
    invented from general model knowledge (see strategy_engine.py).
    This DOES write: existing candidates are never overwritten in
    place — if the picture genuinely changed, the old candidate is
    marked superseded and a new one is created; otherwise the existing
    candidate is returned unchanged. Strategy Engine only proposes; it
    never executes anything.
    """
    goal = goal_engine.GoalEngine(db).get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return strategy_engine.generate_strategies(db, goal)


@router.get("/goals/{goal_id}/strategies", response_model=list[schemas.StrategyOut])
def get_strategies_for_goal(
    goal_id: int, status: Optional[str] = "candidate", db: Session = Depends(get_db)
):
    """List strategies for one goal, highest confidence first. Defaults
    to only current candidates (?status=candidate); pass
    ?status=superseded to see prior candidates this goal has had, or
    omit status entirely for both."""
    return strategy_engine.list_strategies(db, goal_id=goal_id, status=status)


@router.get("/strategies/compare", response_model=schemas.StrategyCompareResponse)
def compare_strategies(a: int, b: int, db: Session = Depends(get_db)):
    """
    Compare two strategies using their frozen, already-computed scores
    — "Strategy A scores higher because..." made concrete, from the
    underlying numerical factors rather than a fresh judgment call.
    """
    result = strategy_engine.compare_strategies(db, a, b)
    if not result:
        raise HTTPException(status_code=404, detail="One or both strategies not found")
    return result


@router.get("/world/goals/{goal_id}", response_model=schemas.GoalGraph)
def get_goal_graph(goal_id: int, db: Session = Depends(get_db)):
    """
    The Strategic (goal-scoped) World Model view: every opportunity
    linked to this goal (with its live money_score), every belief and
    piece of causal knowledge relevant to it, and every candidate
    strategy generated so far. Read-only — does not generate new
    strategies (use POST /forge/goals/{id}/strategies for that).
    """
    graph = world_model.get_goal_graph(db, goal_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Goal not found")
    return graph


@router.get(
    "/money/opportunities",
    response_model=list[schemas.RankedOpportunity],
    description=(
        "EXPLICIT EXPLOITATION LANE: rank commercial opportunities by money "
        "evidence; this is not Hami's global unknown/experiment selector."
    ),
)
def get_ranked_opportunities(request: Request, goal_id: Optional[int] = None, limit: int = 10, db: Session = Depends(get_db)):
    """
    Every opportunity, scored live by money_score and ranked highest
    first — never a fabricated number, see money_engine.py's module
    docstring. EXPLOITATION LANE only, not a global experiment selector.
    Filter with ?goal_id=. Owner-only: this exposes the
    owner's internal price projections and revenue estimates.
    """
    require_owner_api_key(request)
    ranked = money_engine.rank_opportunities(db, goal_id=goal_id, limit=limit)
    return [
        schemas.RankedOpportunity(
            opportunity=item["opportunity"], money_score=item["money_score"], expected_value=item["expected_value"]
        )
        for item in ranked
    ]


@router.get("/money/opportunities/{opportunity_id}", response_model=schemas.OpportunityMoneyGraph)
def get_opportunity_money_graph(opportunity_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Full monetization view of one opportunity: live money_score with
    the complete numerical breakdown, every revenue experiment ever
    recorded against it (immutable history), total real revenue
    recorded, and any strategies sharing its goal. Owner-only.
    """
    require_owner_api_key(request)
    graph = world_model.get_opportunity_money_graph(db, opportunity_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return graph


@router.get(
    "/money/recommend",
    response_model=schemas.MoneyRecommendation,
    description=(
        "EXPLICIT EXPLOITATION LANE: recommend a revenue follow-through "
        "among commercial opportunities; not global unknown selection."
    ),
)
def get_money_recommendation(request: Request, db: Session = Depends(get_db)):
    """
    "What should I pursue today to make money?" — the single highest-
    money_score opportunity across everything Forge knows, with a
    plain-text explanation of why and a concrete next step. Both are
    rule-based, not an LLM judgment call. Owner-only.
    """
    require_owner_api_key(request)
    recommendation = money_engine.recommend_next_action(db)
    if not recommendation:
        raise HTTPException(status_code=404, detail="No opportunities exist yet")
    return recommendation


@router.post("/opportunities/{opportunity_id}/revenue-experiments", response_model=schemas.ExperimentOut)
def create_revenue_experiment(
    opportunity_id: int, payload: schemas.RevenueExperimentCreate, request: Request, db: Session = Depends(get_db)
):
    """Plan a real-world revenue test against an opportunity — created
    as pending (result=None) until POST .../result completes it."""
    require_owner_api_key(request)
    experiment = money_engine.record_revenue_experiment(
        db, opportunity_id, payload.hypothesis, payload.action, expected_result=payload.expected_result
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return experiment


@router.post("/revenue-experiments/{experiment_id}/result", response_model=schemas.ExperimentOut)
def record_revenue_experiment_result(
    experiment_id: int, payload: schemas.RevenueExperimentResult, request: Request, db: Session = Depends(get_db)
):
    """
    Record what actually happened. Immutable once completed — calling
    this again on an already-completed experiment raises (via the
    ValueError handler) on conflicting data and returns the unchanged
    row on identical data; plan a new revenue experiment for a
    genuinely new test instead.
    """
    require_owner_api_key(request)
    experiment = money_engine.record_revenue_result(
        db, experiment_id, payload.result, revenue=payload.revenue, conversions=payload.conversions, data_scope=payload.data_scope
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Revenue experiment not found")
    return experiment


@router.get("/money/opportunities/{opportunity_id}/evidence", response_model=schemas.EvidenceStatus)
def get_opportunity_evidence_status(opportunity_id: int, request: Request, db: Session = Depends(get_db)):
    """
    "Prediction ≠ Revenue, Belief ≠ Customer, Interest ≠ Payment" made
    concrete: every money-relevant field on this opportunity, labeled
    "observed" | "inferred" | "estimated" | "unknown" — never letting a
    populated number silently imply more certainty than it has earned.
    Owner-only.
    """
    require_owner_api_key(request)
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return money_engine.classify_evidence(opportunity)


@router.get(
    "/money/opportunities/owner-ranked",
    response_model=list[schemas.OwnerRankedOpportunity],
    description=(
        "EXPLICIT EXPLOITATION LANE: commercial ranking by speed to first "
        "revenue; not Hami's global unknown/experiment selector."
    ),
)
def get_owner_ranked_opportunities(request: Request, limit: int = 10, db: Session = Depends(get_db)):
    """
    Owner-first ranking: explicitly rewards speed to first revenue over
    theoretical size — a $500 opportunity validated this week can
    outrank a hypothetical $10M idea needing six months. Distinct from
    GET /forge/money/opportunities, which ranks by pure money_score.
    Owner-only.
    """
    require_owner_api_key(request)
    ranked = money_engine.rank_opportunities_for_owner(db, limit=limit)
    return [
        schemas.OwnerRankedOpportunity(
            opportunity=item["opportunity"],
            money_score=item["money_score"],
            expected_value=item["expected_value"],
            speed_score=item["speed_score"],
            owner_score=item["owner_score"],
        )
        for item in ranked
    ]


@router.get("/money/dashboard", response_model=schemas.MoneyDashboard)
def get_money_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    One consolidated read for the owner: best opportunities (both
    ranking modes), fastest path to revenue, highest 30-day estimate,
    highest confidence, what needs validation, active/completed
    revenue experiments, total real revenue recorded, conversion rate,
    and which offers won vs. failed.
    """
    require_owner_api_key(request)
    dashboard = money_engine.get_money_dashboard(db)

    def to_ranked(items):
        return [
            schemas.RankedOpportunity(
                opportunity=item["opportunity"], money_score=item["money_score"], expected_value=item["expected_value"]
            )
            for item in items
        ]

    return schemas.MoneyDashboard(
        best_opportunities=to_ranked(dashboard["best_opportunities"]),
        owner_priority_opportunities=[
            schemas.OwnerRankedOpportunity(
                opportunity=item["opportunity"],
                money_score=item["money_score"],
                expected_value=item["expected_value"],
                speed_score=item["speed_score"],
                owner_score=item["owner_score"],
            )
            for item in dashboard["owner_priority_opportunities"]
        ],
        fastest_to_revenue=to_ranked(dashboard["fastest_to_revenue"]),
        highest_30d_estimate=to_ranked(dashboard["highest_30d_estimate"]),
        highest_confidence=to_ranked(dashboard["highest_confidence"]),
        needing_validation=to_ranked(dashboard["needing_validation"]),
        active_experiments=dashboard["active_experiments"],
        completed_experiments_count=dashboard["completed_experiments_count"],
        total_revenue_recorded=dashboard["total_revenue_recorded"],
        conversion_rate=dashboard["conversion_rate"],
        winning_experiments=dashboard["winning_experiments"],
        failed_experiments=dashboard["failed_experiments"],
    )


@router.get("/revenue-sources", response_model=list[schemas.RevenueSourceOut])
def get_revenue_sources(db: Session = Depends(get_db)):
    """
    Revenue-source rows stored in this database. A percentage is present
    only when a primary citation was stored with it. Startup does not
    add platform fee figures.
    """
    return money_engine.list_revenue_sources(db)


@router.get("/money/opportunities/{opportunity_id}/suggested-sources", response_model=list[schemas.RevenueSourceOut])
def get_suggested_revenue_sources(opportunity_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Candidate RevenueSources for this opportunity, based on its
    already-inferred monetization_model — a SUGGESTION only. Nothing
    is linked automatically; use POST .../revenue-source to confirm one.
    Owner-only.
    """
    require_owner_api_key(request)
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return money_engine.suggest_revenue_sources(db, opportunity)


@router.post("/money/opportunities/{opportunity_id}/revenue-source", response_model=schemas.OpportunityOut)
def set_opportunity_revenue_source(
    opportunity_id: int, payload: schemas.LinkRevenueSourceRequest, db: Session = Depends(get_db)
):
    """
    Explicitly ground an opportunity in a real, known revenue source.
    This is the only way an opportunity ever gets linked to one —
    never automatic, even when a suggestion is obvious.
    """
    opportunity = money_engine.link_revenue_source(db, opportunity_id, payload.revenue_source_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity or revenue source not found")
    return opportunity


@router.post("/execution/actions", response_model=schemas.ExperimentOut)
def create_execution_action(payload: schemas.ExecutionActionCreate, db: Session = Depends(get_db)):
    """
    Create a concrete, trackable executable action against an
    opportunity — not merely advice. requires_owner_approval and
    execution_mode are derived automatically from action_type; actions
    involving spending or commitment (paid_pilot, service_delivery)
    cannot be started until POST .../approve is called explicitly.
    """
    action = execution_engine.create_action(
        db,
        payload.opportunity_id,
        payload.action_type,
        payload.description,
        strategy_id=payload.strategy_id,
        required_inputs=payload.required_inputs,
        expected_result=payload.expected_result,
        estimated_cost=payload.estimated_cost,
    )
    if not action:
        raise HTTPException(
            status_code=400,
            detail="Opportunity/strategy not found, or action_type not recognized",
        )
    return action


@router.get("/execution/actions", response_model=list[schemas.ExperimentOut])
def list_execution_actions(
    request: Request,
    opportunity_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """List execution actions, optionally filtered to one opportunity."""
    require_owner_api_key(request)
    query = db.query(models.Experiment).filter(models.Experiment.action_type.isnot(None))
    if opportunity_id is not None:
        query = query.filter(models.Experiment.opportunity_id == opportunity_id)
    return query.order_by(models.Experiment.created_at.desc()).all()


@router.get("/execution/actions/blocked", response_model=list[schemas.ExperimentOut])
def list_blocked_actions(request: Request, db: Session = Depends(get_db)):
    """Every action Forge proposed that policy blocked outright."""
    require_owner_api_key(request)
    return (
        db.query(models.Experiment)
        .filter(models.Experiment.status == "blocked")
        .order_by(models.Experiment.created_at.desc())
        .all()
    )


@router.get("/execution/actions/{action_id}", response_model=schemas.ExperimentOut)
def get_execution_action(action_id: int, request: Request, db: Session = Depends(get_db)):
    """One execution action's full current state."""
    require_owner_api_key(request)
    action = db.query(models.Experiment).filter(models.Experiment.id == action_id).first()
    if not action or action.action_type is None:
        raise HTTPException(status_code=404, detail="Execution action not found")
    return action


@router.post("/execution/actions/{action_id}/approve", response_model=schemas.ExperimentOut)
def approve_execution_action(action_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Explicit owner approval — the only way an approval-required action
    (spending or commitment involved) can ever move to 'ready'. No
    automatic approval path exists anywhere in this codebase.
    """
    require_owner_api_key(request)
    action = execution_engine.approve_action(db, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Execution action not found")
    return action


@router.post("/execution/actions/{action_id}/start", response_model=schemas.ExperimentOut)
def start_execution_action(action_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Mark an action as actually being carried out. Refuses (404) if an
    approval-required action hasn't been approved yet — call
    POST .../approve first.
    """
    require_owner_api_key(request)
    action = execution_engine.start_action(db, action_id)
    if not action:
        raise HTTPException(
            status_code=404,
            detail="Execution action not found, or it requires owner approval first",
        )
    return action


@router.post("/execution/actions/{action_id}/result", response_model=schemas.ExperimentOut)
def record_execution_action_result(
    action_id: int, payload: schemas.ExecutionActionResult, request: Request, db: Session = Depends(get_db)
):
    """
    Record what actually happened. Delegates the confidence-update
    math to money_engine.py (not duplicated here). Immutable once
    completed — calling this again on an already-completed action
    returns it unchanged rather than overwriting its result.

    A require_approval action cannot attach revenue here. Its result
    is the human outcome, and money is a separate verified payment.
    """
    require_owner_api_key(request)
    existing = db.get(models.Experiment, action_id)
    if existing is not None and existing.policy_decision == "require_approval":
        if payload.revenue is not None or payload.conversions is not None or payload.costs is not None:
            raise HTTPException(
                status_code=409,
                detail="Revenue is recorded only from verified payment evidence",
            )
        if payload.data_scope != existing.data_scope:
            raise HTTPException(status_code=409, detail="Result scope must match the action")
        try:
            approval_outcome_bridge.record_human_result(db, action_id, payload.result)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return db.get(models.Experiment, action_id)

    action = execution_engine.record_action_result(
        db, action_id, payload.result, revenue=payload.revenue, conversions=payload.conversions, costs=payload.costs, data_scope=payload.data_scope
    )
    if not action:
        raise HTTPException(status_code=404, detail="Execution action not found")
    return action


@router.get("/execution/actions/{action_id}/package", response_model=schemas.ActionPackageOut)
def get_execution_action_package(
    action_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Evidence already stored for a require_approval action. Writes nothing."""
    require_owner_api_key(request)
    package = approval_outcome_bridge.build_action_package(db, action_id)
    if package is None:
        raise HTTPException(status_code=404, detail="No require_approval action")
    return package


@router.post("/execution/actions/{action_id}/human-result", response_model=schemas.ActionPackageOut)
def record_execution_human_result(
    action_id: int, payload: schemas.HumanResultIn, request: Request, db: Session = Depends(get_db)
):
    """Record the human outcome. Revenue stays empty."""
    require_owner_api_key(request)
    try:
        return approval_outcome_bridge.record_human_result(db, action_id, payload.result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/execution/actions/{action_id}/verified-revenue", response_model=schemas.ActionPackageOut)
def record_execution_verified_revenue(
    action_id: int, payload: schemas.VerifiedRevenueIn, request: Request, db: Session = Depends(get_db)
):
    """Record revenue only after a human outcome and a verified payment reference."""
    require_owner_api_key(request)
    try:
        approval_outcome_bridge.record_verified_revenue_evidence(
            db,
            action_id,
            amount=payload.amount,
            currency=payload.currency,
            source=payload.source,
            reference=payload.reference,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    package = approval_outcome_bridge.build_action_package(db, action_id)
    if package is None:
        raise HTTPException(status_code=404, detail="No require_approval action")
    return package


@router.get("/execution/rank", response_model=list[schemas.RankedAction])
def get_ranked_actions(limit: int = 10, db: Session = Depends(get_db)):
    """
    Every not-yet-completed execution action, scored and ranked by the
    owner's own formula: economic_potential x confidence x
    goal_relevance x evidence_quality / execution_cost_time.
    """
    ranked = execution_engine.rank_pending_actions(db, limit=limit)
    return [
        schemas.RankedAction(
            action=item["action"],
            action_score=item["action_score"],
            factors=schemas.ActionScoreFactors(**item["factors"]),
            stage=item["stage"],
        )
        for item in ranked
        if item["factors"]
    ]


@router.get("/execution/recommend", response_model=schemas.ExecutionRecommendation)
def get_execution_recommendation(db: Session = Depends(get_db)):
    """
    "What should I do right now to make money?" — from actual ranked
    execution actions, not a fresh guess. Falls back to an
    opportunity-level recommendation (still real data) if no execution
    actions exist yet.
    """
    recommendation = execution_engine.recommend_next_money_action(db)
    if not recommendation:
        raise HTTPException(status_code=404, detail="No opportunities or actions exist yet")
    return schemas.ExecutionRecommendation(
        action=recommendation["action"],
        action_score=recommendation["action_score"],
        factors=schemas.ActionScoreFactors(**recommendation["factors"]) if recommendation["factors"] else None,
        stage=recommendation["stage"],
        reasoning=recommendation["reasoning"],
        next_step=recommendation["next_step"],
    )


@router.get("/autonomy/policy", response_model=schemas.AutonomyPolicyOut)
def get_autonomy_policy(db: Session = Depends(get_db)):
    """
    The owner's current operating boundary — what Forge may do
    autonomously vs. what requires approval. Seeded conservatively by
    default (zero autonomous spend, only the free/low-risk action
    types allowed) — see autonomy_engine.py.
    """
    policy = autonomy_engine.get_active_policy(db)
    if not policy:
        raise HTTPException(status_code=404, detail="No active autonomy policy configured")
    return policy


@router.patch("/autonomy/policy", response_model=schemas.AutonomyPolicyOut)
def update_autonomy_policy(payload: schemas.AutonomyPolicyUpdate, db: Session = Depends(get_db)):
    """
    Adjust the owner's operating boundary. Only provided fields
    change; omitted fields keep their current value. This is the one
    and only way the boundary widens — nothing in the backend can
    grant itself more autonomy than the owner has configured here.
    """
    policy = autonomy_engine.get_active_policy(db)
    if not policy:
        raise HTTPException(status_code=404, detail="No active autonomy policy configured")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    policy.updated_at = autonomy_engine.utcnow()
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/autonomy/evaluate", response_model=schemas.PolicyEvaluationOut)
def preview_policy_evaluation(
    opportunity_id: int, action_type: str, estimated_cost: Optional[float] = None, db: Session = Depends(get_db)
):
    """
    Preview what the policy engine would decide for a candidate action
    WITHOUT creating it — "why did/would Forge choose this" made
    inspectable before committing to anything.
    """
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return autonomy_engine.evaluate_action(db, opportunity, action_type, estimated_cost)


@router.get("/money/revenue-breakdown", response_model=schemas.RevenueBreakdown)
def get_revenue_breakdown(request: Request, db: Session = Depends(get_db)):
    """
    POTENTIAL (the owner's own stated projections — estimates, never
    facts) vs. EXPECTED (probability-weighted, from real evidence) vs.
    REALIZED (actual recorded revenue) — never displayed as one
    conflated number. Owner-only.
    """
    require_owner_api_key(request)
    return execution_engine.get_revenue_breakdown(db)


@router.get("/strategies/{strategy_id}/performance", response_model=schemas.StrategyPerformanceOut)
def get_strategy_performance(strategy_id: int, db: Session = Depends(get_db)):
    """
    Real, recorded track record for one strategy — attempts,
    successes, revenue, cost — computed only from completed
    Experiments linked to it. All-zero/unknown fields if nothing has
    completed yet, never an invented figure.
    """
    strategy = db.query(models.Strategy).filter(models.Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return execution_engine.get_strategy_performance(db, strategy_id)


@router.post("/autonomy/run-cycle", response_model=schemas.AutonomousCycleSummary)
def run_autonomy_cycle_now(db: Session = Depends(get_db)):
    """
    Manually trigger one pass of the autonomous action-proposal loop
    (the same one worker.py runs on every Forge cycle) — useful for
    testing a policy change without waiting for the next scheduled
    cycle. AUTONOMOUS DECISION only: this proposes and evaluates
    actions against policy, it never starts or executes any of them.
    """
    return execution_engine.run_autonomous_action_cycle(db)


@router.post("/economic/discover", response_model=schemas.EconomicDiscoverySummary)
def run_economic_discovery_now(request: Request, db: Session = Depends(get_db)):
    """
    Manually trigger one pass of autonomous, evidence-gated opportunity
    discovery (the same one worker.py runs on every Forge cycle) — the
    v1.8 fix for patterns accumulating with zero opportunities ever
    emerging. Reviews every Pattern with no Opportunity yet against
    real economic evidence; only creates one where the evidence clears
    the bar (see economic_intelligence.py / opportunity_engine.py).

    OWNER-ONLY: this writes Opportunity rows to the database.
    """
    require_owner_api_key(request)
    return opportunity_engine.run_autonomous_opportunity_discovery(db)


@router.get("/economic/patterns/{pattern_id}/corroboration", response_model=schemas.CorroborationOut)
def get_pattern_corroboration(pattern_id: int, db: Session = Depends(get_db)):
    """
    Source diversity for one pattern's supporting signals — how many
    genuinely independent sources back it, vs. how many are duplicates/
    syndication of the same underlying report. Computed live, not
    stored, from existing Pattern/Signal data (v1.4's Signal.source and
    Signal.is_duplicate_of).
    """
    pattern = db.query(models.Pattern).filter(models.Pattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return economic_intelligence.compute_corroboration(db, pattern)


@router.get("/scenarios", response_model=schemas.ScenarioOverview)
def get_scenario_overview(request: Request, db: Session = Depends(get_db)):
    """
    Phase 1 of the 2036 Civilization Scenario Engine (v1.9) — a
    SECONDARY, parallel domain to Revenue Intelligence. Returns every
    Scenario (6 mutually exclusive high-level futures, evidence-first:
    probability is NULL/"insufficient evidence" until real evidence
    differentiates them), every tracked Forecaster, and every
    ScenarioPrediction (both forecaster-attributed claims and Forge's
    own tracked indicators) with its evidence count.

    Owner-only: this exposes the full internal scenario/forecaster/
    prediction ledger and evidence counts. No frontend/script consumer
    reads it (verified repo-wide, 2026-10-05).

    Nothing here is asserted as true — see each ScenarioPrediction's
    status ("open" until resolved), probability/confidence (separate
    numbers, both nullable), and interpretation_note (explicit where
    Forge's claim text is a paraphrase rather than a verbatim quote).
    """
    require_owner_api_key(request)
    overview = scenario_engine.get_scenario_overview(db)
    return schemas.ScenarioOverview(
        scenarios=overview["scenarios"],
        forecasters=overview["forecasters"],
        predictions=[
            schemas.ScenarioPredictionWithEvidence(prediction=item["prediction"], evidence_count=item["evidence_count"])
            for item in overview["predictions"]
        ],
    )


# ---------- Decisions & Learning (restored) ----------

@router.post("/decisions")
def create_decision(
    request: Request,
    title: str,
    rationale: str,
    opportunity_id: Optional[int] = None,
    expected_outcome: Optional[str] = None,
    db: Session = Depends(get_db),
):
    require_owner_api_key(request)
    from app.services import decision_engine
    d = decision_engine.propose_decision(
        db,
        title=title,
        rationale=rationale,
        opportunity_id=opportunity_id,
        expected_outcome=expected_outcome,
    )
    return {
        "id": d.id,
        "title": d.title,
        "rationale": d.rationale,
        "status": d.status,
        "expected_cost": d.expected_cost,  # ESTIMATE
        "expected_value": d.expected_value,  # ESTIMATE
    }


@router.get("/decisions")
def list_decisions(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    from app.services import decision_engine
    rows = decision_engine.list_decisions(db, limit=limit)
    return [
        {
            "id": d.id,
            "title": d.title,
            "rationale": d.rationale[:300],
            "status": d.status,
            "opportunity_id": d.opportunity_id,
            "confidence_at_decision": d.confidence_at_decision,
            "created_at": d.created_at,
        }
        for d in rows
    ]


@router.post("/decisions/{decision_id}/accept")
def accept_decision(decision_id: int, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    from app.services import decision_engine
    d = decision_engine.accept_decision(db, decision_id)
    if not d:
        raise HTTPException(404, "Decision not found")
    return {"id": d.id, "status": d.status, "decided_at": d.decided_at}


@router.post("/learning/from-experiment")
def learning_from_experiment(
    experiment_id: int,
    prediction: str,
    actual: str,
    lesson: str,
    prediction_error: Optional[float] = None,
    error_type: Optional[str] = None,
    confidence_delta: Optional[float] = None,
    data_scope: str = "REAL",
    db: Session = Depends(get_db),
):
    from app.services import learning_engine
    exp = db.get(models.Experiment, experiment_id)
    if not exp or exp.status != "completed" or not db.query(models.Outcome).filter_by(experiment_id=experiment_id, data_scope=data_scope).first():
        raise HTTPException(422, "Record an actual outcome through the canonical outcome endpoint before adding learning")
    event = learning_engine.record_learning_from_experiment(
        db,
        experiment_id,
        prediction=prediction,
        actual=actual,
        lesson=lesson,
        prediction_error=prediction_error,
        error_type=error_type,
        confidence_delta=confidence_delta,
        data_scope=data_scope,
    )
    return {
        "id": event.id,
        "prediction": event.prediction,
        "actual": event.actual,
        "lesson": event.lesson,
        "error_type": event.error_type,
        "belief_update_applied": event.belief_update_applied,
    }


@router.get("/learning")
def list_learning(limit: int = 50, db: Session = Depends(get_db)):
    from app.services import learning_engine
    rows = learning_engine.list_learning_events(db, limit=limit)
    return [
        {
            "id": e.id,
            "prediction": e.prediction[:200],
            "actual": e.actual[:200],
            "lesson": e.lesson[:300],
            "error_type": e.error_type,
            "belief_update_applied": e.belief_update_applied,
            "confidence_delta": e.confidence_delta,
            "created_at": e.created_at,
        }
        for e in rows
    ]


@router.post("/actions")
def create_action(
    objective: str,
    action_type: str = "manual_note",
    decision_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    parameters: Optional[str] = None,
    db: Session = Depends(get_db),
):
    import json
    from app.services import action_engine
    if action_type == "forge_bot_response":
        raise HTTPException(
            403,
            "Create Forge Bot response ACTIONs through the owner-only Forge Bot route.",
        )
    parsed = None
    if parameters:
        try:
            parsed = json.loads(parameters)
        except json.JSONDecodeError:
            raise HTTPException(422, "parameters must be a JSON object")
        if not isinstance(parsed, dict):
            raise HTTPException(422, "parameters must be a JSON object")
    a = action_engine.propose_action(
        db,
        objective=objective,
        action_type=action_type,
        decision_id=decision_id,
        opportunity_id=opportunity_id,
        parameters=parsed,
    )
    return {
        "id": a.id,
        "status": a.status,
        "policy_result": a.policy_result,
        "policy_reason": a.policy_reason,
        "verification_state": a.verification_state,
        "adapter_name": a.adapter_name,
    }


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: int, request: Request, db: Session = Depends(get_db)):
    action = db.get(models.Action, action_id)
    if action and action.action_type == "forge_bot_response":
        from app.api.forge_bot import _require_owner_key

        _require_owner_key(request)
    from app.services import action_engine
    a = action_engine.approve_action(db, action_id)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"id": a.id, "status": a.status, "approved_at": a.approved_at}


@router.post("/actions/{action_id}/execute")
def execute_action(action_id: int, request: Request, db: Session = Depends(get_db)):
    action = db.get(models.Action, action_id)
    if action and action.action_type == "forge_bot_response":
        from app.api.forge_bot import _require_owner_key

        _require_owner_key(request)
    from app.services import action_engine
    a = action_engine.start_and_execute_action(db, action_id)
    if not a:
        raise HTTPException(404, "Action not found")
    return {
        "id": a.id,
        "status": a.status,
        "execution_result": a.execution_result,
        "execution_error": a.execution_error,
        "verification_state": a.verification_state,
        "note": "Execution success is not business outcome. Record Outcome separately.",
    }


@router.get("/actions")
def list_actions(limit: int = 50, db: Session = Depends(get_db)):
    from app.services import action_engine
    rows = action_engine.list_actions(db, limit=limit)
    return [
        {
            "id": a.id,
            "objective": a.objective[:200],
            "action_type": a.action_type,
            "status": a.status,
            "policy_result": a.policy_result,
            "decision_id": a.decision_id,
            "verification_state": a.verification_state,
        }
        for a in rows
    ]


@router.post("/outcomes")
def create_outcome(
    outcome_type: str,
    action_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    product_id: Optional[int] = None,
    actual_value: Optional[float] = None,
    unit: Optional[str] = None,
    qualitative_result: Optional[str] = None,
    success: Optional[bool] = None,
    notes: Optional[str] = None,
    source: str = "manual",
    data_scope: str = "REAL",
    idempotency_key: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from app.services import action_engine
    o = action_engine.record_outcome(
        db,
        outcome_type=outcome_type,
        action_id=action_id,
        experiment_id=experiment_id,
        product_id=product_id,
        actual_value=actual_value,
        unit=unit,
        qualitative_result=qualitative_result,
        source=source,
        success=success,
        notes=notes,
        data_scope=data_scope,
        idempotency_key=idempotency_key,
    )
    return {
        "id": o.id,
        "outcome_type": o.outcome_type,
        "actual_value": o.actual_value,  # ACTUAL
        "unit": o.unit,
        "success": o.success,
        "verification_state": o.verification_state,
        "data_scope": o.data_scope,
        "label": "SANDBOX/TEST ACTUAL" if o.data_scope == "SANDBOX" else "REAL ACTUAL",
    }


@router.get("/outcomes")
def list_outcomes(limit: int = 50, db: Session = Depends(get_db)):
    from app.services import action_engine
    rows = action_engine.list_outcomes(db, limit=limit)
    return [
        {
            "id": o.id,
            "outcome_type": o.outcome_type,
            "actual_value": o.actual_value,
            "unit": o.unit,
            "qualitative_result": (o.qualitative_result or "")[:200],
            "success": o.success,
            "action_id": o.action_id,
            "data_scope": o.data_scope,
            "label": "SANDBOX/TEST ACTUAL" if o.data_scope == "SANDBOX" else "REAL ACTUAL",
        }
        for o in rows
    ]


@router.get("/cycles")
def list_cycles(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(models.CycleRun)
        .order_by(models.CycleRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": c.id,
            "started_at": c.started_at,
            "ended_at": c.ended_at,
            "duration_ms": c.duration_ms,
            "status": c.status,
            "error": c.error,
        }
        for c in rows
    ]


@router.get("/runtime")
def get_runtime(db: Session = Depends(get_db)):
    """Real system window: counts + last cycle + worker task state from the live DB.
    No fabricated activity — only what is actually stored.
    """
    from sqlalchemy import func
    from app.services import truth_audit

    truth_audit.reconcile_stale_cycles(db)
    truth = truth_audit.snapshot(db)

    def count(model):
        try:
            return db.query(func.count()).select_from(model).scalar() or 0
        except Exception:
            return None

    signals = count(models.Signal)
    evidence = count(models.Evidence)
    research_tasks = count(models.ResearchTask)
    claims = count(models.Claim) if hasattr(models, "Claim") else 0
    opportunities = count(models.Opportunity)
    decisions = count(models.Decision) if hasattr(models, "Decision") else 0
    experiments = count(models.Experiment)
    outcomes = count(models.Outcome) if hasattr(models, "Outcome") else 0
    learning_events = count(models.LearningEvent) if hasattr(models, "LearningEvent") else 0
    patterns = count(models.Pattern)
    beliefs = count(models.Belief)

    last_cycle = (
        db.query(models.CycleRun)
        .order_by(models.CycleRun.started_at.desc())
        .first()
    )
    last_completed = (
        db.query(models.CycleRun)
        .filter(models.CycleRun.status == "COMPLETED")
        .order_by(models.CycleRun.ended_at.desc())
        .first()
    )
    running = (
        db.query(func.count())
        .select_from(models.CycleRun)
        .filter(models.CycleRun.status == "RUNNING")
        .scalar()
        or 0
    )

    queued = (
        db.query(func.count())
        .select_from(models.WorkerTask)
        .filter(models.WorkerTask.status == "queued")
        .scalar()
        or 0
    )
    last_task = (
        db.query(models.WorkerTask)
        .order_by(models.WorkerTask.updated_at.desc())
        .first()
    )

    # Honest stage: only mark stages that have real records
    stages = []
    if signals and signals > 0:
        stages.append({"name": "WORLD / DISCOVER", "state": "has_data", "count": signals})
    if evidence and evidence > 0:
        stages.append({"name": "EVIDENCE", "state": "has_data", "count": evidence})
    if patterns and patterns > 0:
        stages.append({"name": "DETECT", "state": "has_data", "count": patterns})
    if opportunities and opportunities > 0:
        stages.append({"name": "OPPORTUNITY", "state": "has_data", "count": opportunities})
    if claims and claims > 0:
        stages.append({"name": "VERIFY / CLAIMS", "state": "has_data", "count": claims})
    if decisions and decisions > 0:
        stages.append({"name": "DECISION", "state": "has_data", "count": decisions})
    if experiments and experiments > 0:
        stages.append({"name": "EXPERIMENT", "state": "has_data", "count": experiments})
    if outcomes and outcomes > 0:
        stages.append({"name": "MEASURE", "state": "has_data", "count": outcomes})
    if learning_events and learning_events > 0:
        stages.append({"name": "LEARN", "state": "has_data", "count": learning_events})

    active_stage = None
    if last_task and last_task.status in ("queued", "running"):
        active_stage = f"{last_task.worker_type}/{last_task.task_name}"
    elif running > 0:
        active_stage = "cycle_running"
    else:
        active_stage = "IDLE — waiting for next scheduled cycle"

    return {
        "signals": signals,
        "evidence": evidence,
        "research_tasks": research_tasks,
        "claims": claims,
        "opportunities": opportunities,
        "decisions": decisions,
        "experiments": experiments,
        "outcomes": outcomes,
        "learning_events": learning_events,
        "patterns": patterns,
        "beliefs": beliefs,
        "worker": {
            "queued_tasks": queued,
            "last_task": {
                "id": last_task.id if last_task else None,
                "worker_type": last_task.worker_type if last_task else None,
                "task_name": last_task.task_name if last_task else None,
                "status": last_task.status if last_task else None,
                "updated_at": last_task.updated_at.isoformat() if last_task and last_task.updated_at else None,
                "error": (last_task.error or None) if last_task else None,
            } if last_task else None,
        },
        "cycles": {
            "running_count": running,
            "last": {
                "id": last_cycle.id if last_cycle else None,
                "status": last_cycle.status if last_cycle else None,
                "started_at": last_cycle.started_at.isoformat() if last_cycle and last_cycle.started_at else None,
                "ended_at": last_cycle.ended_at.isoformat() if last_cycle and last_cycle.ended_at else None,
                "error": last_cycle.error if last_cycle else None,
            } if last_cycle else None,
            "last_completed": {
                "id": last_completed.id if last_completed else None,
                "started_at": last_completed.started_at.isoformat() if last_completed and last_completed.started_at else None,
                "ended_at": last_completed.ended_at.isoformat() if last_completed and last_completed.ended_at else None,
                "duration_ms": last_completed.duration_ms if last_completed else None,
            } if last_completed else None,
        },
        "loop_stages_with_data": stages,
        "active_stage": active_stage,
        "truth": truth,
    }


def _connection_note(db: Session, row: models.NetworkConnection, kind: str) -> str | None:
    query = db.query(models.Outcome)
    if kind == "response":
        query = query.filter(
            models.Outcome.notes.like(f"idempotency:network-connection:{row.id}:response:%")
        ).order_by(models.Outcome.id.desc())
    else:
        query = query.filter(models.Outcome.notes == f"idempotency:network-connection:{row.id}:{kind}")
    outcome = query.first()
    return outcome.qualitative_result if outcome else None


def _latest_connection_response(db: Session, row: models.NetworkConnection) -> str | None:
    return _connection_note(db, row, "response")


def _seconds_to_recorded_payment(db: Session, row: models.NetworkConnection) -> int | None:
    outcome = (
        db.query(models.Outcome)
        .filter(models.Outcome.notes == f"idempotency:network-connection:{row.id}:paid")
        .first()
    )
    if outcome is None or outcome.observed_at is None or row.created_at is None:
        return None
    return int((outcome.observed_at - row.created_at).total_seconds())


@router.get("/connections")
def list_network_connections(request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    from app.services import network_connections
    from app.services.network_substrate_adapter import relation_read_model

    rows = db.query(models.NetworkConnection).order_by(models.NetworkConnection.id.desc()).limit(100).all()
    result = []
    for row in rows:
        result.append({
            "id": row.id,
            **relation_read_model(db, row),
            "left_kind": row.left_kind,
            "left_id": row.left_id,
            "right_kind": row.right_kind,
            "right_id": row.right_id,
            "state": row.state,
            "reason": row.reason,
            "context": row.context,
            "uncertainty": row.uncertainty,
            "provenance": row.provenance,
            "valid_from": row.valid_from,
            "valid_until": row.valid_until,
            "observed_at": row.observed_at,
            "evidence_ids": [
                evidence.id
                for evidence in network_connections.evidence_for_connection(db, row.id)
            ],
            "evidence_reference": row.evidence_reference,
            "constraints": row.constraints,
            "unknown": row.unknown,
            "agreement_gap": row.agreement_gap,
            "public_visible": row.public_visible,
            "seconds_to_recorded_payment": _seconds_to_recorded_payment(db, row),
            "latest_response": _latest_connection_response(db, row),
            "latest_fulfillment": _connection_note(db, row, "fulfilled"),
        })
    return result


@router.post("/connections/scan")
def scan_network_connections(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    from app.services import network_connections
    rows = network_connections.scan_candidates(db, limit=limit)
    return [{"id": row.id, "state": row.state, "public_visible": row.public_visible} for row in rows]


@router.post("/connections/{connection_id}/advance")
def advance_network_connection(
    request: Request,
    connection_id: int,
    next_state: str,
    amount_npr: Optional[int] = None,
    evidence_reference: Optional[str] = None,
    constraints: Optional[str] = None,
    note: Optional[str] = None,
    db: Session = Depends(get_db),
):
    require_owner_api_key(request)
    from app.services import action_engine, network_connections
    row = db.query(models.NetworkConnection).filter_by(id=connection_id).first()
    if row is None:
        raise HTTPException(404, "connection not found")
    if not network_connections.can_advance(row.state, next_state):
        raise HTTPException(409, f"cannot move from {row.state} to {next_state}")
    if next_state == "evidenced":
        ref = (evidence_reference or "").strip()
        stored = (
            db.query(models.Signal)
            .filter(models.Signal.canonical_url == ref, models.Signal.source_type == "external")
            .first()
        )
        if stored is None:
            raise HTTPException(409, "a proposal requires evidence already stored from an external source")
        from app.api.public import evidence_freshness
        if evidence_freshness(stored.retrieved_at) == "stale":
            raise HTTPException(409, "stored evidence is stale")
        row.evidence_reference = ref
    if next_state == "viable":
        import json
        keys = ("landed_cost", "margin", "buyer", "route")
        supplied = {}
        if constraints:
            try:
                supplied = json.loads(constraints)
            except json.JSONDecodeError:
                raise HTTPException(422, "constraints must be a JSON object")
            if not isinstance(supplied, dict):
                raise HTTPException(422, "constraints must be a JSON object")
        evidence_text = ""
        if row.evidence_reference:
            stored = (
                db.query(models.Signal)
                .filter(models.Signal.canonical_url == row.evidence_reference, models.Signal.source_type == "external")
                .first()
            )
            evidence_text = f"{stored.title or ''} {stored.content or ''}" if stored else ""
        checked = {}
        for key in keys:
            value = supplied.get(key)
            if value in (None, ""):
                checked[key] = None
                continue
            quote = str(value).strip()
            if quote.lower() not in evidence_text.lower():
                raise HTTPException(409, f"{key} is not in the stored evidence")
            checked[key] = quote
        row.constraints = json.dumps(checked)
    if next_state == "fulfilled" and not (note or "").strip():
        raise HTTPException(422, "fulfillment requires a note of what was done")
    if next_state == "paid" and (amount_npr is None or amount_npr < 0):
        raise HTTPException(422, "moving to paid requires the amount that changed hands")
    if next_state == "accepted" and row.left_kind == "domain_record":
        from app.api.public import terms_complete
        need = db.query(models.DomainRecord).filter_by(id=row.left_id).first()
        if need is None or not terms_complete(need.terms):
            raise HTTPException(409, "accepted work requires a complete economic contract")
    row.state = next_state
    db.commit()
    paid = next_state == "paid"
    action_engine.record_domain_event(
        db,
        idempotency_key=f"network-connection:{row.id}:{next_state}",
        source="network_connection",
        success=False if next_state == "failed" else (True if paid else None),
        actual_value=float(amount_npr) if paid else None,
        unit="NPR" if paid else None,
        qualitative_result=(
            f"Connection {row.id} from {row.left_kind}:{row.left_id} to {row.right_kind}:{row.right_id} "
            f"is now {next_state}. "
            + (
                f"Amount recorded: {amount_npr} NPR. Not yet confirmed by the other side."
                if paid
                else (
                    f"Work recorded: {(note or '').strip()}. This is not a payment."
                    if next_state == "fulfilled"
                    else "This state is not a later state."
                )
            )
        ),
    )
    return {"id": row.id, "state": row.state, "public_visible": row.public_visible, "payment": "reported" if paid else None}


@router.post("/connections/{connection_id}/confirm-payment")
def confirm_network_payment(request: Request, connection_id: int, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    row = db.query(models.NetworkConnection).filter_by(id=connection_id).first()
    if row is None or row.state != "paid":
        raise HTTPException(409, "only a recorded paid connection can be confirmed")
    outcome = (
        db.query(models.Outcome)
        .filter(models.Outcome.notes == f"idempotency:network-connection:{row.id}:paid")
        .first()
    )
    if outcome is None or outcome.actual_value is None:
        raise HTTPException(409, "no recorded amount to confirm")
    if outcome.verification_state != "REPORTED":
        raise HTTPException(409, "only a reported payment can be verified")
    outcome.verification_state = "VERIFIED"
    db.commit()
    return {"id": row.id, "state": row.state, "amount_npr": outcome.actual_value, "payment": "verified"}


def _paid_outcome(db: Session, connection_id: int) -> models.Outcome | None:
    return (
        db.query(models.Outcome)
        .filter(models.Outcome.notes == f"idempotency:network-connection:{connection_id}:paid")
        .first()
    )


def _payment_lesson(db: Session, connection_id: int, prediction: str, actual: str, lesson: str) -> None:
    db.add(models.LearningEvent(
        prediction=prediction,
        actual=actual,
        lesson=lesson,
        error_type="qualitative_miss",
        data_scope="REAL",
        belief_update_applied=False,
    ))
    db.commit()


@router.post("/connections/{connection_id}/dispute-payment")
def dispute_network_payment(request: Request, connection_id: int, note: str, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    row = db.query(models.NetworkConnection).filter_by(id=connection_id).first()
    outcome = _paid_outcome(db, connection_id)
    if row is None or row.state != "paid" or outcome is None:
        raise HTTPException(409, "only a recorded payment can be disputed")
    if outcome.verification_state not in {"REPORTED", "VERIFIED"}:
        raise HTTPException(409, "this payment is already disputed or settled")
    if not note.strip():
        raise HTTPException(422, "a dispute needs a note")
    outcome.verification_state = "DISPUTED"
    _payment_lesson(
        db,
        connection_id,
        prediction="The recorded payment would stand.",
        actual=f"Disputed. No winner is recorded. Note: {note.strip()}",
        lesson="A recorded payment was disputed. The amount is not settled.",
    )
    return {"id": row.id, "payment": "disputed", "winner": None}


@router.post("/connections/{connection_id}/settle-payment")
def settle_network_payment(request: Request, connection_id: int, note: str, amount_npr: int, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    row = db.query(models.NetworkConnection).filter_by(id=connection_id).first()
    outcome = _paid_outcome(db, connection_id)
    if row is None or outcome is None or outcome.verification_state != "DISPUTED":
        raise HTTPException(409, "only a disputed payment can be settled")
    if amount_npr < 0 or not note.strip():
        raise HTTPException(422, "settlement needs the stated amount and a note")
    outcome.verification_state = "SETTLED"
    outcome.actual_value = float(amount_npr)
    outcome.qualitative_result = (
        f"{outcome.qualitative_result} Settled amount recorded: {amount_npr} NPR. Note: {note.strip()}"
    )
    _payment_lesson(
        db,
        connection_id,
        prediction="The dispute had no recorded resolution.",
        actual=f"Settled at {amount_npr} NPR. Note: {note.strip()}",
        lesson="The parties recorded a settlement. This is not a guess about who was right.",
    )
    return {"id": row.id, "payment": "settled", "amount_npr": amount_npr, "winner": None}


@router.post("/connections/{connection_id}/response")
def record_connection_response(request: Request, connection_id: int, note: str, db: Session = Depends(get_db)):
    """A reply is a recorded response. It does not accept, fulfill, or pay."""
    require_owner_api_key(request)
    from app.services import network_connections
    row = db.query(models.NetworkConnection).filter_by(id=connection_id).first()
    if row is None:
        raise HTTPException(404, "connection not found")
    if row.state not in {"proposed", "authorized", "contacted"}:
        raise HTTPException(409, "a response is only recorded before acceptance")
    try:
        network_connections.record_response(db, row, note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"id": row.id, "state": row.state, "accepted": False}


@router.post("/connections/{connection_id}/publish")
def publish_network_connection(request: Request, connection_id: int, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    from app.services import network_connections
    row = db.query(models.NetworkConnection).filter_by(id=connection_id).first()
    if row is None:
        raise HTTPException(404, "connection not found")
    if row.state not in network_connections.PUBLISHABLE:
        raise HTTPException(409, "a candidate or proposal is not publishable")
    row.public_visible = True
    db.commit()
    return {"id": row.id, "state": row.state, "public_visible": True}
