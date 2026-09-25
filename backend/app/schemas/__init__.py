"""
Pydantic schemas — request/response contracts for the API.

Kept separate from models.py (DB layer) on purpose: this is the
boundary that will stay stable even if the database changes shape,
and it's what the frontend and any future client (mobile, SaaS API
consumers) code against.
"""

from datetime import datetime
from typing import Literal, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------- Signal ----------

class SignalCreate(BaseModel):
    content: str = Field(..., min_length=1, description="The raw observed text")
    source: str = Field(default="manual")
    category: Optional[str] = None


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    content: str
    category: Optional[str]
    timestamp: datetime

    # --- Observer Engine fields ---
    signal_type: Optional[str] = None  # "problem" | "demand" | "observation"
    importance_score: float = 0.0
    processed: bool = False
    tags: Optional[str] = None  # comma-separated, e.g. "restaurant,customer support"

    # --- Source Collector Framework fields ---
    reliability_score: float = 50.0
    freshness_score: float = 100.0

    # --- Signal Quality Engine fields (v1.4) ---
    quality_score: Optional[float] = None
    quality_flags: Optional[str] = None
    is_duplicate_of: Optional[int] = None


# ---------- Pattern ----------

class PatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    frequency: int
    confidence_score: float
    created_at: datetime


# ---------- Opportunity ----------

class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pattern_id: Optional[int]
    goal_id: Optional[int] = None
    problem: str
    target_customer: str
    solution: str
    business_model: str
    pricing_idea: Optional[str]
    market_analysis: Optional[str]
    mvp_plan: Optional[str]
    validation_plan: Optional[str]
    difficulty: Optional[str]
    score: float
    created_at: datetime

    # --- Money Engine fields (v1.1) ---
    customer_segment: Optional[str] = None
    economic_consequence: Optional[str] = None
    offer: Optional[str] = None
    acquisition_path: Optional[str] = None
    estimated_price: Optional[float] = None
    estimated_revenue: Optional[float] = None
    problem_evidence_signal_ids: Optional[str] = None
    willingness_evidence_ids: Optional[str] = None
    market_confidence: float = 0.0
    revenue_confidence: float = 0.0
    implementation_difficulty: Optional[float] = None
    acquisition_difficulty: Optional[float] = None
    uncertainty: float = 100.0
    competition_evidence: Optional[str] = None
    expected_value: Optional[float] = None
    status: str = "identified"
    owner_priority: float = 50.0
    updated_at: Optional[datetime] = None

    # --- Money Engine fields (v1.2) ---
    monetization_model: Optional[str] = None
    time_to_first_revenue_days: Optional[float] = None
    estimated_revenue_30d: Optional[float] = None
    estimated_revenue_90d: Optional[float] = None
    estimated_effort_hours: Optional[float] = None
    estimated_startup_cost: Optional[float] = None
    revenue_source_id: Optional[int] = None
    economic_evidence_summary: Optional[str] = None


# ---------- Experiment ----------

class ExperimentCreate(BaseModel):
    opportunity_id: int
    action: str
    result: Optional[str] = None
    lesson: Optional[str] = None


class ExperimentOut(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "REAL"
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: Optional[int] = None
    action: str
    result: Optional[str]
    lesson: Optional[str]
    created_at: datetime

    # --- Revenue Experiment fields (v1.1) ---
    hypothesis: Optional[str] = None
    expected_result: Optional[str] = None
    revenue: Optional[float] = None
    conversions: Optional[int] = None
    confidence_change: Optional[float] = None

    # --- Execution lifecycle fields (v1.5) ---
    strategy_id: Optional[int] = None
    action_type: Optional[str] = None
    status: str = "planned"
    execution_mode: Optional[str] = None
    requires_owner_approval: bool = False
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    costs: Optional[float] = None
    required_inputs: Optional[str] = None

    # --- Autonomy Policy fields (v1.7) ---
    estimated_cost: Optional[float] = None
    risk_score: Optional[float] = None
    policy_decision: Optional[str] = None
    policy_reason: Optional[str] = None
    attempt_number: int = 1


# ---------- Analyze ----------

class AnalyzeRequest(BaseModel):
    idea: str = Field(..., min_length=3, description="Free-text business idea or problem description")

    @field_validator("idea")
    @classmethod
    def validate_idea(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("idea must not be empty")
        if len(cleaned) < 3:
            raise ValueError("idea must be at least 3 characters long")
        return cleaned


class AnalyzeResponse(BaseModel):
    opportunity_id: Optional[int] = None
    problem: str
    target_customer: str
    market_analysis: str
    solution: str
    business_model: str
    pricing_idea: str
    mvp_plan: str
    validation_plan: str
    difficulty: str
    score: float
    # Structured intelligence (not just scores)
    signal_id: Optional[int] = None
    observation_status: str = "OBSERVED_AS_USER_REPORT"
    evidence_quality: str = "LIMITED"  # LIMITED | MODERATE | STRONG
    unknowns: List[str] = []
    recommended_next_experiment: Optional[str] = None
    decision_id: Optional[int] = None
    knowledge_labels: dict = {}  # e.g. {"score": "HEURISTIC", "pricing": "ESTIMATED"}
    research_question_id: Optional[int] = None
    research_task_ids: List[int] = []
    research_status: str = "research_started"
    evidence_count: int = 0
    findings_summary: Optional[str] = None


# ---------- Pattern-run (pattern engine trigger) ----------

class PatternRunResponse(BaseModel):
    patterns_found: int
    patterns: List[PatternOut]


# ---------- Dashboard stats ----------

class StatsOut(BaseModel):
    total_signals: int
    total_patterns: int
    total_opportunities: int
    total_experiments: int


# ---------- Observer Engine ----------

class ObserveRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Raw observed text, from any source")
    source: str = Field(default="manual", description='e.g. "manual", "reddit", "github", "web"')


class ObserverStatsOut(BaseModel):
    total_observations: int
    high_importance_count: int  # signals scored >= 70
    average_importance: float
    low_quality_count: int = 0  # v1.4 — signals below the pattern-inclusion quality floor
    quality_flag_breakdown: dict[str, int] = {}  # v1.8 — why signals are held back, not just how many

    # Additive Phase 1 stats fields
    signals_total: Optional[int] = None
    signals_external_with_url: Optional[int] = None
    signals_seed: Optional[int] = None
    signals_manual: Optional[int] = None
    signals_synthetic: Optional[int] = None
    opportunities_active: Optional[int] = None
    opportunities_duplicate_archived: Optional[int] = None
    outcomes_real: Optional[int] = None
    verified_revenue: Optional[float] = None


# ---------- Belief / Curiosity / Reality layer ----------

class BeliefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    statement: str
    pattern_id: Optional[int] = None
    supporting_signal_ids: Optional[str]
    confidence_score: float
    created_at: datetime
    last_updated: datetime


class BeliefCheckResponse(BaseModel):
    belief: str
    evidence_found: List[dict]
    confidence_change: float


class ResearchQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    priority_score: float
    status: str
    source_pattern_id: Optional[int]
    source_belief_id: Optional[int]
    source_claim_id: Optional[int] = None
    created_at: datetime


class ResearchTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    claim_id: Optional[int] = None
    source: str
    query: str
    status: str
    objective: Optional[str] = None
    plan: Optional[list[dict]] = None
    tools_used: Optional[list[str]] = None
    evidence_ids: Optional[str] = None
    claims: Optional[list[dict]] = None
    judgments: Optional[list[dict]] = None
    contradictions: Optional[list[dict]] = None
    remaining_questions: Optional[list[str]] = None
    results: Optional[dict] = None
    errors: Optional[list[dict]] = None
    current_step: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ResearchTaskEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    event_type: str
    step_name: Optional[str]
    details: Optional[dict]
    created_at: datetime


class BeliefExperimentCreate(BaseModel):
    hypothesis: str = Field(..., min_length=1)
    method: str = Field(..., min_length=1)


class BeliefExperimentResult(BaseModel):
    result: str = Field(..., min_length=1)
    confidence_change: float = Field(..., ge=-100, le=100)


class BeliefExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    belief_id: int
    hypothesis: str
    method: str
    result: Optional[str]
    confidence_change: Optional[float]
    status: str
    created_at: datetime


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: Optional[str]
    reliability_score: float
    last_checked: Optional[datetime]
    lifespan: Optional[str]


class ForgeCycleSummary(BaseModel):
    signals_processed: int
    source_addresses_restored: int = 0
    claims_linked: List[int] = Field(default_factory=list)
    network_connection_ids: List[int] = Field(default_factory=list)
    patterns_found: int
    beliefs_updated: int
    predictions_created: int
    predictions_resolved: int
    questions_created: int
    research_tasks_created: int
    patterns_reviewed_for_opportunities: int = 0
    opportunities_discovered: int = 0
    patterns_without_sufficient_evidence: int = 0
    opportunities_classified: int
    opportunities_needing_validation: int
    actions_proposed: int = 0
    actions_allowed: int = 0
    actions_requiring_approval: int = 0
    actions_blocked: int = 0
    scenario: dict = {"status": "not_run"}  # SECONDARY, additive sub-result — never overwrites the fields above it; {"status": "completed"|"failed", "reason"?, "signals_reviewed", "signals_classified"}
    lessons_memory: Optional[dict] = None  # v2.10 — durable lesson consolidation + recall snapshot for this cycle
    orchestration: Optional[dict] = None  # v2.11 — canonical E2E flow advancement + honest pipeline snapshot


# ---------- Reality Memory ----------

class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    belief_id: Optional[int]
    signal_id: Optional[int]
    source: Optional[str]
    content: str
    direction: str
    canonical_url: Optional[str] = None
    external_id: Optional[str] = None
    title: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    content_fingerprint: Optional[str] = None
    provenance: Optional[str] = None
    created_at: datetime


class ClaimCreate(BaseModel):
    statement: str = Field(..., min_length=1)
    epistemic_state: str = "observed"
    evidence_id: Optional[int] = None
    relation_type: str = "supports"
    decision_id: Optional[int] = None
    experiment_id: Optional[int] = None
    outcome_id: Optional[int] = None


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    statement: str
    normalized_statement: str
    epistemic_state: str
    confidence: Optional[float]
    opportunity_id: Optional[int]
    decision_id: Optional[int]
    experiment_id: Optional[int]
    outcome_id: Optional[int]
    provenance: Optional[str]
    created_at: datetime
    updated_at: datetime


class EvidenceRelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    claim_id: Optional[int]
    opportunity_id: Optional[int]
    decision_id: Optional[int]
    experiment_id: Optional[int]
    outcome_id: Optional[int]
    relation_type: str
    relation_key: str
    created_at: datetime


class JudgeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    evidence_ids: List[int] = Field(default_factory=list)
    claim_id: Optional[int] = None


class JudgmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    judge_name: str
    provider: str
    model: str
    question: str
    conclusion: Optional[str]
    reasoning_summary: Optional[str]
    conclusion_label: Optional[str]
    evidence_ids: str
    uncertainty: Optional[str]
    confidence: Optional[float]
    status: str
    error: Optional[str]
    created_at: datetime


class JudgmentComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    judgment_ids: list[int]
    evidence_ids: str
    outcome: str
    summary: str
    disagreement_points: Optional[list[dict]]
    missing_evidence: Optional[list]
    contradictory_claims: Optional[list]
    unsupported_conclusions: Optional[list]
    follow_up_question_id: Optional[int]
    comparison_key: str
    created_at: datetime


class OpportunityEvidenceGraph(BaseModel):
    opportunity: OpportunityOut
    claims: List[ClaimOut]
    evidence: List[EvidenceOut]
    relationships: List[EvidenceRelationshipOut]
    judgments: List[JudgmentOut] = []
    comparisons: List[JudgmentComparisonOut] = []
    why: List[dict]


class JudgmentRunOut(BaseModel):
    judgments: List[JudgmentOut]
    comparison: JudgmentComparisonOut


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    belief_id: int
    statement: str
    status: str
    confidence_before: float
    confidence_after: Optional[float]
    created_at: datetime
    resolved_at: Optional[datetime]


# ---------- Knowledge Mining Engine ----------

class KnowledgeMineRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Long-form text: a book excerpt, paper, story, etc.")
    source_label: str = Field(default="book", description='e.g. "book", "paper", or a custom label')


class KnowledgeMineResponse(BaseModel):
    source_label: str
    insights_found: int
    signal_ids: List[int]


# ---------- Research task execution ----------

class TaskRunResult(BaseModel):
    task_id: int
    status: str
    signals_created: Optional[int] = None
    reason: Optional[str] = None


class DefaultCollectionResult(BaseModel):
    source: str
    status: str
    signals_created: Optional[int] = None
    reason: Optional[str] = None


# ---------- Forge Memory Layer ----------

class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    category: Optional[str]
    source_type: str
    source_id: int
    confidence_score: float
    embedding_model: Optional[str]
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchResult(BaseModel):
    knowledge: KnowledgeOut
    similarity: float


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="A question for Forge to answer from its own accumulated knowledge")


class AskResponse(BaseModel):
    question: str
    answer: str
    memories_used: List[KnowledgeOut]


# ---------- Goal Engine ----------

class GoalCreate(BaseModel):
    statement: str = Field(..., min_length=1, description="What Forge is trying to make progress toward")
    target_metric: Optional[str] = Field(default=None, description='Optional measurable target, e.g. "$1,000 MRR"')
    priority: float = Field(default=50.0, ge=0, le=100)


class GoalUpdate(BaseModel):
    status: Optional[str] = Field(default=None, description='"active" | "paused" | "achieved" | "abandoned"')
    priority: Optional[float] = Field(default=None, ge=0, le=100)


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    statement: str
    target_metric: Optional[str]
    status: str
    priority: float
    created_at: datetime
    updated_at: datetime


# ---------- Confidence history ----------

class ConfidenceEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    belief_id: int
    previous_confidence: float
    new_confidence: float
    delta: float
    reason: Optional[str] = None
    evidence_signal_ids: Optional[str] = None
    experiment_id: Optional[int] = None
    created_at: datetime


# ---------- Causal Knowledge Engine ----------

class CausalKnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    condition: str
    action: str
    expected_outcome: Optional[str]
    actual_outcome: Optional[str]
    confidence: float
    belief_id: Optional[int]
    goal_id: Optional[int]
    supporting_experiment_ids: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------- World Model ----------

class RelatedBelief(BaseModel):
    belief_id: int
    statement: str
    confidence_score: float
    similarity: float


class BeliefGraph(BaseModel):
    belief: BeliefOut
    originating_pattern: Optional[PatternOut]
    related_opportunities: List[OpportunityOut]
    related_goals: List[GoalOut]
    goal_relevance_score: float
    stability_score: float
    confidence_trend: str
    related_causal_knowledge: List[CausalKnowledgeOut]
    successful_actions: List[CausalKnowledgeOut]
    failed_actions: List[CausalKnowledgeOut]
    last_verification: Optional[datetime]
    supporting_evidence: List[EvidenceOut]
    contradicting_evidence: List[EvidenceOut]
    origin_sources: List[str]
    source_reliability: dict[str, float]
    related_beliefs: List[RelatedBelief]
    experiments: List[BeliefExperimentOut]
    predictions: List[PredictionOut]
    confidence_changes: List[ConfidenceEventOut]


# ---------- Strategy Engine (v1.0) ----------

class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    title: str
    description: str
    rationale: str
    expected_outcome: Optional[str]
    confidence: float
    estimated_impact: float
    uncertainty: float
    status: str
    supporting_belief_ids: Optional[str]
    supporting_causal_knowledge_ids: Optional[str]
    supporting_experiment_ids: Optional[str]
    created_at: datetime
    updated_at: datetime


class StrategyCompareResponse(BaseModel):
    strategy_a: StrategyOut
    strategy_b: StrategyOut
    higher_scoring: int
    score_difference: float
    explanation: str


# ---------- Money Engine (v1.1) ----------

class RevenueExperimentCreate(BaseModel):
    opportunity_id: int
    hypothesis: str = Field(..., min_length=1, description="What is being tested, e.g. a price or offer")
    action: str = Field(..., min_length=1, description="What was actually done, e.g. 'contacted 20 restaurants with a $99/mo offer'")
    expected_result: Optional[str] = None


class RevenueExperimentResult(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "REAL"
    result: str = Field(..., min_length=1)
    revenue: Optional[float] = Field(default=None, description="Actual $ recorded from this test — never a guess")
    conversions: Optional[int] = Field(default=None, description="e.g. how many of N prospects said yes")


class MoneyScoreBreakdown(BaseModel):
    money_score: float
    expected_value: Optional[float]
    revenue_source_grounded: bool = False
    problem_evidence: float
    willingness_evidence: float
    market_confidence: float
    revenue_confidence: float
    ease_implementation: float
    ease_acquisition: float
    goal_priority: float
    owner_priority: float
    uncertainty: float


class RankedOpportunity(BaseModel):
    opportunity: OpportunityOut
    money_score: float
    expected_value: Optional[float]


class OpportunityMoneyGraph(BaseModel):
    opportunity: OpportunityOut
    money_score: float
    expected_value: Optional[float]
    score_breakdown: MoneyScoreBreakdown
    revenue_experiments: List[ExperimentOut]
    total_revenue_recorded: float
    related_strategies: List[StrategyOut]


class MoneyRecommendation(BaseModel):
    opportunity: OpportunityOut
    money_score: float
    expected_value: Optional[float]
    reasoning: str
    next_step: str


# ---------- Revenue Sources (v1.3) ----------

class RevenueSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    payout_structure: str
    payout_share_percent_min: Optional[float]
    payout_share_percent_max: Optional[float]
    minimum_payout: Optional[float]
    payment_frequency: Optional[str]
    requires_approval: bool
    source_citation: Optional[str]
    data_as_of: Optional[str]
    created_at: datetime
    updated_at: datetime


class LinkRevenueSourceRequest(BaseModel):
    revenue_source_id: int


class GoalGraph(BaseModel):
    goal: GoalOut
    opportunities: List[RankedOpportunity]
    relevant_beliefs: List[BeliefOut]
    relevant_causal_knowledge: List[CausalKnowledgeOut]
    candidate_strategies: List[StrategyOut]


# ---------- Money Engine, v1.2 ----------

class EvidenceStatusItem(BaseModel):
    status: str  # "observed" | "inferred" | "estimated" | "unknown"
    value: Optional[Union[str, float, int]] = None


class EvidenceStatus(BaseModel):
    problem_existence: EvidenceStatusItem
    willingness_to_pay: EvidenceStatusItem
    revenue_source: EvidenceStatusItem
    estimated_revenue: EvidenceStatusItem
    estimated_price: EvidenceStatusItem
    revenue_confidence: EvidenceStatusItem
    market_confidence: EvidenceStatusItem
    estimated_revenue_30d: EvidenceStatusItem
    estimated_revenue_90d: EvidenceStatusItem
    time_to_first_revenue_days: EvidenceStatusItem
    estimated_effort_hours: EvidenceStatusItem
    estimated_startup_cost: EvidenceStatusItem


class OwnerRankedOpportunity(BaseModel):
    opportunity: OpportunityOut
    money_score: float
    expected_value: Optional[float]
    speed_score: float
    owner_score: float


class MoneyDashboard(BaseModel):
    best_opportunities: List[RankedOpportunity]
    owner_priority_opportunities: List[OwnerRankedOpportunity]
    fastest_to_revenue: List[RankedOpportunity]
    highest_30d_estimate: List[RankedOpportunity]
    highest_confidence: List[RankedOpportunity]
    needing_validation: List[RankedOpportunity]
    active_experiments: List[ExperimentOut]
    completed_experiments_count: int
    total_revenue_recorded: float
    conversion_rate: Optional[float]
    winning_experiments: List[ExperimentOut]
    failed_experiments: List[ExperimentOut]


# ---------- Money Execution Engine (v1.5) ----------

class ExecutionActionCreate(BaseModel):
    opportunity_id: int
    action_type: str = Field(..., description="One of: customer_interview, outreach, offer, paid_pilot, service_delivery, revenue_experiment, follow_up, validate_pricing, build_mvp")
    description: str = Field(..., min_length=1, description="The concrete action, e.g. 'Contact 20 qualified prospects with the $99/mo offer'")
    strategy_id: Optional[int] = None
    required_inputs: Optional[str] = None
    expected_result: Optional[str] = None
    estimated_cost: Optional[float] = Field(default=None, description="Stated estimate for policy evaluation — never treated as a fact, distinct from real recorded costs")


class ExecutionActionResult(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "REAL"
    result: str = Field(..., min_length=1)
    revenue: Optional[float] = Field(default=None, description="Actual $ recorded — never a guess")
    conversions: Optional[int] = None
    costs: Optional[float] = Field(default=None, description="Actual $ spent — never a guess")


class ActionEvidenceCite(BaseModel):
    signal_id: int
    source: Optional[str] = None
    text: Optional[str] = None


class ActionPackageOut(BaseModel):
    action_id: int
    opportunity_id: Optional[int] = None
    action_type: Optional[str] = None
    status: str
    policy_decision: Optional[str] = None
    requires_owner_approval: bool
    approved: bool
    execution_allowed: bool
    problem: Optional[str] = None
    proposed_action: str
    evidence: List[ActionEvidenceCite]
    result: Optional[str] = None
    revenue: Optional[float] = None


class HumanResultIn(BaseModel):
    result: str = Field(..., min_length=1)


class VerifiedRevenueIn(BaseModel):
    amount: float = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    source: str = Field(..., min_length=1)
    reference: str = Field(..., min_length=1)
    notes: Optional[str] = None


class ExperimentActionRead(BaseModel):
    id: int
    experiment_id: int
    action_type: str
    objective: str
    status: str
    policy_result: Optional[str] = None
    policy_reason: Optional[str] = None
    proposed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_result: Optional[str] = None
    execution_error: Optional[str] = None
    verification_state: str
    adapter_name: Optional[str] = None


class ExperimentActionOutcomeCreate(BaseModel):
    actual: str = Field(..., min_length=1)
    success: Optional[bool] = None
    source: str = "manual"
    actual_value: Optional[float] = None
    unit: Optional[str] = None
    lesson: Optional[str] = None


class ActionScoreFactors(BaseModel):
    economic_potential: float
    confidence: float
    goal_relevance: float
    evidence_quality: float
    execution_cost_time_burden: float


class RankedAction(BaseModel):
    action: ExperimentOut
    action_score: float
    factors: ActionScoreFactors
    stage: str  # "planned" | "attempted" | "completed" | "verified"


class ExecutionRecommendation(BaseModel):
    action: Optional[ExperimentOut]
    action_score: float
    factors: Optional[ActionScoreFactors]
    stage: str  # "predicted" if no action exists yet, else the action's real stage
    reasoning: str
    next_step: str


# ---------- Autonomy Policy Engine (v1.7) ----------

class AutonomyPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    active: bool
    max_experiment_spend: Optional[float]
    max_concurrent_experiments: int
    max_daily_actions: int
    max_retries: int
    min_confidence_required: float
    max_risk_threshold: float
    allowed_action_types: Optional[str]
    created_at: datetime
    updated_at: datetime


class AutonomyPolicyUpdate(BaseModel):
    max_experiment_spend: Optional[float] = None
    max_concurrent_experiments: Optional[int] = None
    max_daily_actions: Optional[int] = None
    max_retries: Optional[int] = None
    min_confidence_required: Optional[float] = None
    max_risk_threshold: Optional[float] = None
    allowed_action_types: Optional[str] = Field(
        default=None, description="Comma-separated action types, e.g. 'customer_interview,validate_pricing'"
    )


class PolicyEvaluationOut(BaseModel):
    decision: str  # "allow" | "require_approval" | "block"
    reasons: List[str]
    risk_score: float
    attempt_number: int


class RevenueBreakdown(BaseModel):
    potential_30d: float
    potential_90d: float
    expected: float
    realized: float


class StrategyPerformanceOut(BaseModel):
    strategy_id: int
    attempts: int
    successes: int
    success_rate: Optional[float]
    total_revenue: float
    total_cost: Optional[float]
    net_profit: Optional[float]


class AutonomousCycleSummary(BaseModel):
    proposed: int
    allowed: int
    blocked: int
    require_approval: int
    reason: Optional[str] = None


# ---------- Economic Intelligence (v1.8) ----------

class EconomicDiscoverySummary(BaseModel):
    patterns_reviewed: int
    opportunities_created: int
    patterns_without_sufficient_evidence: int


class CorroborationOut(BaseModel):
    unique_sources: int
    independent_observations: int
    corroboration_count: int


# ---------- Scenario Engine (v1.9) — secondary domain ----------

class ForecasterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    track_record_accuracy: Optional[float]  # None = insufficient evidence
    created_at: datetime


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str
    probability: Optional[float]  # None = insufficient evidence
    probability_basis: str
    created_at: datetime
    updated_at: datetime


class ScenarioPredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    forecaster_id: Optional[int]
    scenario_id: Optional[int]
    domain: Optional[str]
    claim: str
    original_quote: Optional[str]
    interpretation_note: Optional[str]
    target_date: Optional[str]
    probability: Optional[float]  # Forge's own estimate — None = insufficient evidence
    confidence: Optional[float]  # confidence the EVIDENCE supports the forecast — None = insufficient evidence
    reasoning: Optional[str]
    source_url: Optional[str]
    source_name: Optional[str]
    source_date: Optional[str]
    status: str
    outcome: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ScenarioPredictionWithEvidence(BaseModel):
    prediction: ScenarioPredictionOut
    evidence_count: int


class ScenarioOverview(BaseModel):
    scenarios: List[ScenarioOut]
    forecasters: List[ForecasterOut]
    predictions: List[ScenarioPredictionWithEvidence]

class WorkerTaskBase(BaseModel):
    worker_type: str
    task_name: str
    priority: int = 0
    inputs: Optional[dict] = None

class WorkerTaskCreate(WorkerTaskBase):
    pass

class WorkerTaskOut(WorkerTaskBase):
    id: int
    status: str
    outputs: Optional[dict] = None
    evidence: Optional[dict] = None
    dependencies: Optional[dict] = None
    worker_id: Optional[str] = None
    role: Optional[str] = None
    error: Optional[str] = None
    attempts: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    next_run_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Product / Distribution / Customer workflows (commercial readiness v2)
# All metrics are evidence-gated: revenue & customer counts only ever come
# from real Outcome rows (ACTUAL_*), never fabricated by the system.
# ---------------------------------------------------------------------------

class PublicProviderOut(BaseModel):
    id: int
    name: str
    business_name: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    country: str = "Nepal"
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    verification_status: str = "unverified"
    is_active: bool = True
    public_visible: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicServiceListingOut(BaseModel):
    id: int
    provider_id: int
    title: str
    description: str
    category: Optional[str] = None
    location: Optional[str] = None
    price_from: Optional[str] = None
    currency: str = "NPR"
    availability_status: str = "pending"
    is_active: bool = True
    public_visible: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicDiscoveryOut(BaseModel):
    """A collected observation. Not a verified fact and not a price Forge set."""

    id: int
    source: str
    title: Optional[str] = None
    excerpt: str
    canonical_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    epistemic_state: str = "observation"
    freshness: str = "unknown"


class PublicFeedRelation(BaseModel):
    entity_type: str
    entity_id: int
    relation: str


class PublicFeedItem(BaseModel):
    """A public projection of one canonical Forge record, never a copied entity."""

    id: str
    kind: str
    category: Optional[str] = None
    entity_type: str
    entity_id: int
    title: str
    summary: str
    occurred_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    epistemic_state: str
    source: Optional[str] = None
    source_url: Optional[str] = None
    relations: list[PublicFeedRelation] = Field(default_factory=list)


class PublicMatchCandidate(BaseModel):
    kind: str
    id: int
    name: str
    where: Optional[str] = None
    stated_price: Optional[str] = None
    stated_availability: Optional[str] = None
    reasons: list[str]
    unknowns: list[str]
    connection_id: Optional[int] = None
    latest_response: Optional[str] = None


class PublicMatchOut(BaseModel):
    need_id: int
    need_kind: str
    need_title: str
    need_city: Optional[str] = None
    candidates: list[PublicMatchCandidate]
    unknowns: list[str]


class DomainRecordCreate(BaseModel):
    kind: Literal["job", "offer", "trade"]
    title: str = Field(..., min_length=1, max_length=160)
    detail: str = Field(..., min_length=1)
    city: Optional[str] = None
    stated_price: Optional[str] = None
    terms: Optional[dict] = None


class DomainRecordOut(BaseModel):
    id: int
    kind: str
    title: str
    detail: str
    city: Optional[str] = None
    stated_price: Optional[str] = None
    status: str
    terms_complete: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DomainRecordCreated(DomainRecordOut):
    close_token: str


class PublicConnectionOut(BaseModel):
    id: int
    left_kind: str
    left_id: int
    right_kind: str
    right_id: int
    state: str
    reason: str
    known: Optional[str] = None
    unknown: Optional[str] = None
    agreement_gap: str
    forge_role: str = "introducer"
    owns_either_side: bool = False
    latest_response: Optional[str] = None
    latest_fulfillment: Optional[str] = None


class PublicConnectionResponseCreate(BaseModel):
    close_token: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)


class RecordedPaymentOut(BaseModel):
    connection_id: int
    amount: float
    unit: str
    verification: str


class PublicTrustOut(BaseModel):
    subject_kind: str
    subject_id: int
    recorded_requests: int
    reported_payments: list[RecordedPaymentOut]
    verified_payments: list[RecordedPaymentOut]
    disputed_payments: list[RecordedPaymentOut] = []
    settled_payments: list[RecordedPaymentOut] = []
    disputes: int
    unknowns: list[str]


class PublicAlertOut(BaseModel):
    id: int
    source: str
    text: str
    created_at: Optional[datetime] = None


class PublicRevenueMinerOut(BaseModel):
    paid_offers_recorded: int
    repeatability_reviews: int
    ownership_reviews: int
    note: str


class DomainDisputeCreate(BaseModel):
    close_token: str = Field(..., min_length=1)
    note: str = Field(..., min_length=3)


class DomainRecordEventsOut(BaseModel):
    record_id: int
    payments: list[str]
    disputes: list[str]
    completions: int
    unknowns: list[str]


class DomainRecordClose(BaseModel):
    close_token: str = Field(..., min_length=1)
    result: Literal["completed", "withdrawn", "paid"]
    note: str = Field(..., min_length=3)
    amount_npr: Optional[int] = None


class BookingRequestCreate(BaseModel):
    provider_id: int
    service_listing_id: Optional[int] = None
    requester_name: str = Field(..., min_length=1)
    requester_phone: Optional[str] = None
    requester_email: Optional[str] = None
    requested_service: str = Field(..., min_length=1)
    requested_date: Optional[str] = None
    requested_time: Optional[str] = None
    notes: Optional[str] = None


class BookingRequestOut(BaseModel):
    id: int
    provider_id: int
    service_listing_id: Optional[int]
    requester_name: str
    requester_phone: Optional[str]
    requester_email: Optional[str]
    requested_service: str
    requested_date: Optional[str]
    requested_time: Optional[str]
    notes: Optional[str]
    status: str = "pending"
    provider_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class BookingRequestStatusOut(BaseModel):
    id: int
    provider_id: int
    provider_name: Optional[str] = None
    service_listing_id: Optional[int] = None
    requested_service: str
    requested_date: Optional[str] = None
    requested_time: Optional[str] = None
    status: str = "pending"
    provider_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "REAL"
    opportunity_id: Optional[int] = None
    goal_id: Optional[int] = None
    name: str = Field(..., min_length=1, description="Concrete offer name")
    offer: str = Field(..., min_length=1, description="What is actually being sold/delivered, in plain words")
    target_customer: Optional[str] = None
    pricing: Optional[str] = None
    mvp_scope: Optional[str] = None
    hypothesis: Optional[str] = None
    launch_state: Optional[str] = Field(default="not_launched")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    offer: Optional[str] = None
    target_customer: Optional[str] = None
    pricing: Optional[str] = None
    mvp_scope: Optional[str] = None
    hypothesis: Optional[str] = None
    status: Optional[str] = Field(default=None, description="concept|validating|launched|iterating|retired")
    launch_state: Optional[str] = None
    retirement_reason: Optional[str] = None


class ProductOut(BaseModel):
    id: int
    opportunity_id: Optional[int]
    goal_id: Optional[int]
    name: str
    offer: str
    target_customer: Optional[str]
    pricing: Optional[str]
    mvp_scope: Optional[str]
    status: str
    launch_state: Optional[str]
    created_at: datetime
    updated_at: datetime
    retired_at: Optional[datetime]
    retirement_reason: Optional[str]
    hypothesis: Optional[str]
    actual_customers: int
    actual_revenue: float
    actual_cost: float
    data_scope: str = "REAL"

    model_config = ConfigDict(from_attributes=True)


class ProductSummary(ProductOut):
    """Product + honest distribution rollup."""
    channel_count: int = 0
    lead_count: int = 0
    paid_customer_count: int = 0


class ChannelCreate(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "REAL"
    product_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    channel_type: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    status: Optional[str] = "planned"
    action_id: Optional[int] = None


class ChannelUpdate(BaseModel):
    status: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class ChannelOut(BaseModel):
    id: int
    product_id: Optional[int]
    opportunity_id: Optional[int]
    channel_type: str
    name: str
    description: Optional[str]
    status: str
    action_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    outreach_count: int
    response_count: int
    conversion_count: int
    data_scope: str = "REAL"

    model_config = ConfigDict(from_attributes=True)


class CustomerEventCreate(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "REAL"
    product_id: Optional[int] = None
    channel_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_identifier: Optional[str] = None
    segment: Optional[str] = None
    stage: str = "lead"
    event_type: Optional[str] = None
    notes: Optional[str] = None
    action_id: Optional[int] = None
    outcome_id: Optional[int] = None


class CustomerEventOut(BaseModel):
    id: int
    product_id: Optional[int]
    channel_id: Optional[int]
    opportunity_id: Optional[int]
    contact_name: Optional[str]
    contact_identifier: Optional[str]
    segment: Optional[str]
    stage: str
    event_type: Optional[str]
    notes: Optional[str]
    action_id: Optional[int]
    outcome_id: Optional[int]
    occurred_at: datetime
    created_at: datetime
    data_scope: str = "REAL"

    model_config = ConfigDict(from_attributes=True)


class ProductPipeline(BaseModel):
    """Honest snapshot of the build->distribute->measure pipeline."""
    products: List[ProductSummary]
    channels: List[ChannelOut]
    customer_events: List[CustomerEventOut]
    total_products: int
    launched_products: int
    total_outreach: int  # sum of real outreach_counts (from outcomes)
    total_leads: int
    total_paid_customers: int
    realized_revenue: float  # REAL ACTUAL_REVENUE outcomes only
    sandbox_revenue: float = 0.0  # TEST/SANDBOX only; never business traction
    sandbox_products: int = 0


# ---------------------------------------------------------------------------
# Lessons Memory (v2.10)
# Durable, consolidated lessons distilled from real LearningEvents. Recall
# surfaces them when reasoning about an opportunity/decision. Never fabricated.
# ---------------------------------------------------------------------------

class LessonOut(BaseModel):
    id: int
    theme_key: str
    title: str
    summary: str
    opportunity_id: Optional[int]
    belief_id: Optional[int]
    product_id: Optional[int]
    error_type: Optional[str]
    prediction_error_avg: float
    hit_count: int
    source_learning_event_ids: Optional[str]
    first_seen: datetime
    last_seen: datetime
    active: bool
    created_at: datetime
    updated_at: datetime
    data_scope: str = "REAL"

    model_config = ConfigDict(from_attributes=True)


class LessonRecallOut(BaseModel):
    recalled_lessons: List[LessonOut]
    notes: List[str]


# ---------- Repair-shop vertical slice ----------

class RepairScope(BaseModel):
    data_scope: Literal["REAL", "SANDBOX"] = "SANDBOX"


class RepairWorkItemCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200)
    contact_identifier: Optional[str] = Field(default=None, max_length=300)
    consent_state: str = Field(default="NOT_REQUIRED", max_length=40)
    asset_label: str = Field(..., min_length=1, max_length=200)
    reported_problem: str = Field(..., min_length=1, max_length=5000)
    data_scope: Literal["REAL", "SANDBOX"] = "SANDBOX"
    actor: str = Field(default="operator", min_length=1, max_length=120)
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=160)


class RepairEvidenceCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    source: str = Field(default="manual", min_length=1, max_length=120)
    actor: str = Field(default="operator", min_length=1, max_length=120)
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=160)


class RepairTriageCreate(BaseModel):
    rationale: str = Field(..., min_length=1, max_length=5000)
    expected_outcome: str = Field(..., min_length=1, max_length=5000)
    confidence: float = Field(..., ge=0, le=100)
    actor: str = Field(default="operator", min_length=1, max_length=120)
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=160)


class CustomerStatusCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    actor: str = Field(default="operator", min_length=1, max_length=120)


class CustomerResponseCreate(BaseModel):
    accepted: bool
    response: str = Field(..., min_length=1, max_length=5000)
    actor: str = Field(default="operator", min_length=1, max_length=120)


class RepairPaymentCreate(BaseModel):
    amount: float = Field(..., gt=0, le=100_000_000)
    unit: str = Field(default="NPR", min_length=1, max_length=12)
    provider: str = Field(..., min_length=1, max_length=120)
    provider_reference: str = Field(..., min_length=1, max_length=300)
    data_scope: Literal["REAL", "SANDBOX"] = "SANDBOX"
    actor: str = Field(default="operator", min_length=1, max_length=120)
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=160)


class RepairOutcomeCreate(BaseModel):
    actual: str = Field(..., min_length=1, max_length=10000)
    success: Optional[bool] = None
    source: str = Field(default="manual", min_length=1, max_length=120)
    actor: str = Field(default="operator", min_length=1, max_length=120)


class RepairWorkItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    asset_label: str
    reported_problem: str
    status: str
    data_scope: Literal["REAL", "SANDBOX"]
    opportunity_id: Optional[int]
    decision_id: Optional[int]
    experiment_id: Optional[int]
    action_id: Optional[int]
    product_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class RepairCustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact_identifier: Optional[str]
    consent_state: str
    data_scope: Literal["REAL", "SANDBOX"]
    created_at: datetime


class RepairEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_item_id: int
    actor: str
    event_type: str
    previous_state: Optional[str]
    next_state: str
    reason: Optional[str]
    evidence_ids: Optional[str]
    metadata_json: Optional[dict]
    idempotency_key: Optional[str]
    created_at: datetime


class RepairCommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_item_id: int
    channel: str
    body: str
    status: str
    customer_response: Optional[str]
    action_id: Optional[int]
    integration_delivery_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class RepairWorkItemDetail(BaseModel):
    work_item: RepairWorkItemOut
    customer: RepairCustomerOut
    events: List[RepairEventOut]
    communications: List[RepairCommunicationOut]
    evidence: List[EvidenceOut]
    decision: Optional[dict] = None
    experiment: Optional[dict] = None
    outcomes: List[dict] = []
    learning_events: List[dict] = []

from .experiment import ExperimentProposalCreate, ExperimentAuthorize, ExperimentOutcomeCreate, ExperimentRead
