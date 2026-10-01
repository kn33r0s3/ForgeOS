/**
 * Thin typed client for the Forge backend API.
 * One place to change if the backend URL, auth, or error handling
 * ever changes. Every type here mirrors a real backend Pydantic
 * schema (backend/app/schemas.py) — nothing is invented on the
 * frontend side; unavailable fields stay optional/null and are
 * rendered as "unknown", never guessed.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "/api";

const API_TIMEOUT_MS = 10_000;

export type DataScope = "REAL" | "SANDBOX";
let sessionApiKey = "";
export function setSessionApiKey(value: string) { sessionApiKey = value; }
export function clearSessionApiKey() { sessionApiKey = ""; }

function withScope(path: string, scope: DataScope, limit?: number): string {
  const params = new URLSearchParams({ data_scope: scope });
  if (limit !== undefined) params.set("limit", String(limit));
  return `${path}?${params.toString()}`;
}

// ---------- Core signal/pattern/observer types ----------

export interface Signal {
  id: number;
  source: string;
  content: string;
  category: string | null;
  timestamp: string;
  signal_type: string | null; // "problem" | "demand" | "observation"
  importance_score: number;
  processed: boolean;
  tags: string | null;
  reliability_score?: number;
  freshness_score?: number;
  quality_score?: number | null; // v1.4 — null for signals observed before quality scoring existed
  quality_flags?: string | null;
  is_duplicate_of?: number | null;
}

export interface ObserverStats {
  total_observations: number;
  high_importance_count: number;
  average_importance: number;
  low_quality_count?: number; // v1.4
  quality_flag_breakdown?: Record<string, number>; // v1.8 — why signals are held back, not just how many
}

export interface Pattern {
  id: number;
  title: string;
  description: string;
  frequency: number;
  confidence_score: number;
  created_at: string;
}

// ---------- Belief / Curiosity / Reality layer ----------

export interface Belief {
  id: number;
  statement: string;
  pattern_id?: number | null;
  supporting_signal_ids: string | null;
  confidence_score: number;
  created_at: string;
  last_updated: string;
}

export interface Goal {
  id: number;
  statement: string;
  target_metric: string | null;
  status: string;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface Strategy {
  id: number;
  goal_id: number;
  title: string;
  description: string;
  rationale: string;
  expected_outcome: string | null;
  confidence: number;
  estimated_impact: number;
  uncertainty: number;
  status: string; // "candidate" | "superseded"
  supporting_belief_ids: string | null;
  supporting_causal_knowledge_ids: string | null;
  supporting_experiment_ids: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConfidenceEvent {
  id: number;
  belief_id: number;
  previous_confidence: number;
  new_confidence: number;
  delta: number;
  reason: string | null;
  evidence_signal_ids: string | null;
  experiment_id: number | null;
  created_at: string;
}

export interface RelatedBelief {
  belief_id: number;
  statement: string;
  confidence_score: number;
  similarity: number;
}

export interface Evidence {
  id: number;
  belief_id: number;
  signal_id: number | null;
  source: string | null;
  content: string;
  direction: string; // "supports" | "contradicts"
  created_at: string;
}

export interface BeliefGraph {
  belief: Belief;
  originating_pattern: Pattern | null;
  related_opportunities: Opportunity[];
  related_goals: Goal[];
  goal_relevance_score: number;
  stability_score: number;
  confidence_trend: string; // "increasing" | "decreasing" | "stable"
  related_causal_knowledge: unknown[];
  successful_actions: unknown[];
  failed_actions: unknown[];
  last_verification: string | null;
  supporting_evidence: Evidence[];
  contradicting_evidence: Evidence[];
  origin_sources: string[];
  source_reliability: Record<string, number>;
  related_beliefs: RelatedBelief[];
  experiments: unknown[];
  predictions: unknown[];
  confidence_changes: ConfidenceEvent[];
}

export interface ResearchQuestion {
  id: number;
  question: string;
  priority_score: number;
  status: string;
  source_pattern_id: number | null;
  source_belief_id: number | null;
  created_at: string;
}

export interface ResearchTask {
  id: number;
  question_id: number;
  source: string;
  query: string;
  status: string;
  created_at: string;
}

export interface ForgeOutcome {
  id: number;
  outcome_type: string;
  actual_value: number | null;
  unit: string | null;
  qualitative_result: string;
  success: boolean | null;
  action_id: number | null;
  data_scope: DataScope;
  label: string;
}

export interface LearningEvent {
  id: number;
  prediction: string;
  actual: string;
  lesson: string;
  error_type: string | null;
  belief_update_applied: boolean;
  confidence_delta: number | null;
  created_at: string;
}

export interface CycleRun {
  id: number;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  status: string;
  error: string | null;
}

export interface ForgeCycleSummary {
  signals_processed: number;
  patterns_found: number;
  beliefs_updated: number;
  predictions_created: number;
  predictions_resolved: number;
  questions_created: number;
  research_tasks_created: number;
  opportunities_classified?: number; // v1.2 money cycle integration
  opportunities_needing_validation?: number;
}

// ---------- Forge Memory Layer ----------

export interface Knowledge {
  id: number;
  title: string;
  content: string;
  category: string | null;
  source_type: string;
  source_id: number;
  confidence_score: number;
  embedding_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  memories_used: Knowledge[];
}

// ---------- Opportunity (extended through v1.2) ----------

export interface Opportunity {
  id: number;
  pattern_id: number | null;
  goal_id?: number | null;
  problem: string;
  target_customer: string;
  solution: string;
  business_model: string;
  pricing_idea: string | null;
  market_analysis: string | null;
  mvp_plan: string | null;
  validation_plan: string | null;
  difficulty: string | null;
  score: number;
  created_at: string;

  // Money Engine fields (v1.1)
  customer_segment?: string | null;
  economic_consequence?: string | null;
  offer?: string | null;
  acquisition_path?: string | null;
  estimated_price?: number | null;
  estimated_revenue?: number | null;
  problem_evidence_signal_ids?: string | null;
  willingness_evidence_ids?: string | null;
  market_confidence: number;
  revenue_confidence: number;
  implementation_difficulty?: number | null;
  acquisition_difficulty?: number | null;
  uncertainty: number;
  competition_evidence?: string | null;
  expected_value: number | null;
  status: string;
  owner_priority: number;
  updated_at?: string | null;

  // Money Engine fields (v1.2)
  monetization_model?: string | null;
  time_to_first_revenue_days?: number | null;
  estimated_revenue_30d?: number | null;
  estimated_revenue_90d?: number | null;
  estimated_effort_hours?: number | null;
  estimated_startup_cost?: number | null;
  revenue_source_id?: number | null;

  // Economic Intelligence fields (v1.8)
  economic_evidence_summary?: string | null;
}

export interface RankedOpportunity {
  opportunity: Opportunity;
  money_score: number;
  expected_value: number | null;
}

export interface OwnerRankedOpportunity {
  opportunity: Opportunity;
  money_score: number;
  expected_value: number | null;
  speed_score: number;
  owner_score: number;
}

export interface MoneyRecommendation {
  opportunity: Opportunity;
  money_score: number;
  expected_value: number | null;
  reasoning: string;
  next_step: string;
}

export interface MoneyScoreBreakdown {
  money_score: number;
  expected_value: number | null;
  revenue_source_grounded: boolean;
  problem_evidence: number;
  willingness_evidence: number;
  market_confidence: number;
  revenue_confidence: number;
  ease_implementation: number;
  ease_acquisition: number;
  goal_priority: number;
  owner_priority: number;
  uncertainty: number;
}

export interface EvidenceStatusItem {
  status: "observed" | "inferred" | "estimated" | "unknown";
  value: string | number | null;
}

export interface EvidenceStatus {
  problem_existence: EvidenceStatusItem;
  willingness_to_pay: EvidenceStatusItem;
  revenue_source: EvidenceStatusItem;
  estimated_revenue: EvidenceStatusItem;
  estimated_price: EvidenceStatusItem;
  revenue_confidence: EvidenceStatusItem;
  market_confidence: EvidenceStatusItem;
  estimated_revenue_30d: EvidenceStatusItem;
  estimated_revenue_90d: EvidenceStatusItem;
  time_to_first_revenue_days: EvidenceStatusItem;
  estimated_effort_hours: EvidenceStatusItem;
  estimated_startup_cost: EvidenceStatusItem;
}

// ---------- Execution (Experiment, extended through v1.5) ----------

export interface ExecutionAction {
  data_scope?: DataScope;
  id: number;
  opportunity_id: number | null;
  action: string;
  result: string | null;
  lesson: string | null;
  created_at: string;

  // Revenue Experiment fields (v1.1)
  hypothesis: string | null;
  expected_result: string | null;
  revenue: number | null;
  conversions: number | null;
  confidence_change: number | null;

  // Execution lifecycle fields (v1.5)
  strategy_id: number | null;
  action_type: string | null;
  status: string; // "planned" | "ready" | "in_progress" | "completed" | "abandoned"
  execution_mode: string | null; // "executable_locally" | "requires_owner_action" | "requires_external_integration"
  requires_owner_approval: boolean;
  approved_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  costs: number | null;
  required_inputs: string | null;

  // Autonomy Policy fields (v1.7)
  estimated_cost: number | null;
  risk_score: number | null;
  policy_decision: string | null; // "allow" | "require_approval" | "block"
  policy_reason: string | null;
  attempt_number: number;
}

export interface ActionEvidenceCite {
  signal_id: number;
  source: string | null;
  text: string | null;
}

export interface ActionPackage {
  action_id: number;
  opportunity_id: number | null;
  action_type: string | null;
  status: string;
  policy_decision: string | null;
  requires_owner_approval: boolean;
  approved: boolean;
  execution_allowed: boolean;
  problem: string | null;
  proposed_action: string;
  evidence: ActionEvidenceCite[];
  result: string | null;
  revenue: number | null;
}

// ---------- Autonomy Policy Engine (v1.7) ----------

export interface AutonomyPolicy {
  id: number;
  name: string;
  active: boolean;
  max_experiment_spend: number | null; // null = no autonomous spending permitted at all
  max_concurrent_experiments: number;
  max_daily_actions: number;
  max_retries: number;
  min_confidence_required: number;
  max_risk_threshold: number;
  allowed_action_types: string | null;
  created_at: string;
  updated_at: string;
}

export interface PolicyEvaluation {
  decision: "allow" | "require_approval" | "block";
  reasons: string[];
  risk_score: number;
  attempt_number: number;
}

export interface RevenueBreakdown {
  potential_30d: number;
  potential_90d: number;
  expected: number;
  realized: number;
}

export interface StrategyPerformance {
  strategy_id: number;
  attempts: number;
  successes: number;
  success_rate: number | null;
  total_revenue: number;
  total_cost: number | null;
  net_profit: number | null;
}

export interface AutonomousCycleSummary {
  proposed: number;
  allowed: number;
  blocked: number;
  require_approval: number;
  reason?: string | null;
}

export interface ActionScoreFactors {
  economic_potential: number;
  confidence: number;
  goal_relevance: number;
  evidence_quality: number;
  execution_cost_time_burden: number;
}

export interface RankedAction {
  action: ExecutionAction;
  action_score: number;
  factors: ActionScoreFactors;
  stage: "planned" | "attempted" | "completed" | "verified";
}

export interface ExecutionRecommendation {
  action: ExecutionAction | null;
  action_score: number;
  factors: ActionScoreFactors | null;
  stage: string; // "predicted" if no action exists yet, else the real stage
  reasoning: string;
  next_step: string;
}

export interface OpportunityMoneyGraph {
  opportunity: Opportunity;
  money_score: number;
  expected_value: number | null;
  score_breakdown: MoneyScoreBreakdown;
  revenue_experiments: ExecutionAction[];
  total_revenue_recorded: number;
  related_strategies: Strategy[];
}

export interface GoalGraph {
  goal: Goal;
  opportunities: RankedOpportunity[];
  relevant_beliefs: Belief[];
  relevant_causal_knowledge: unknown[];
  candidate_strategies: Strategy[];
}

export interface MoneyDashboard {
  best_opportunities: RankedOpportunity[];
  owner_priority_opportunities: OwnerRankedOpportunity[];
  fastest_to_revenue: RankedOpportunity[];
  highest_30d_estimate: RankedOpportunity[];
  highest_confidence: RankedOpportunity[];
  needing_validation: RankedOpportunity[];
  active_experiments: ExecutionAction[];
  completed_experiments_count: number;
  total_revenue_recorded: number;
  conversion_rate: number | null;
  winning_experiments: ExecutionAction[];
  failed_experiments: ExecutionAction[];
}

export interface RevenueSource {
  id: number;
  name: string;
  source_type: string;
  payout_structure: string;
  payout_share_percent_min: number | null;
  payout_share_percent_max: number | null;
  minimum_payout: number | null;
  payment_frequency: string | null;
  requires_approval: boolean;
  source_citation: string | null;
  data_as_of: string | null;
  created_at: string;
  updated_at: string;
}

// ---------- Analyze / stats ----------

export interface Stats {
  total_signals: number;
  total_patterns: number;
  total_opportunities: number;
  total_experiments: number;
}

export interface AnalyzeResponse {
  opportunity_id?: number | null;
  problem: string;
  target_customer: string;
  market_analysis: string;
  solution: string;
  business_model: string;
  pricing_idea: string;
  mvp_plan: string;
  validation_plan: string;
  difficulty: string;
  score: number;
  signal_id?: number | null;
  observation_status?: string;
  evidence_quality?: string;
  unknowns?: string[];
  recommended_next_experiment?: string | null;
  decision_id?: number | null;
  knowledge_labels?: Record<string, string>;
  research_question_id?: number | null;
  research_task_ids?: number[];
  research_status?: string;
  research_status_url?: string | null;
  evidence_count?: number;
  findings_summary?: string | null;
  research_plan?: ResearchPlan;
  research_sources?: ResearchEvidenceSource[];
}

export interface AnalyzeProgressResponse {
  research_question_id: number;
  phase: string;
  research_status: string;
  evidence_count: number;
  tasks: {
    id: number;
    source: string;
    status: string;
    current_step?: string | null;
    attempts: number;
    evidence_count: number;
    updated_at: string;
    started_at?: string | null;
    completed_at?: string | null;
  }[];
  research_plan: Record<string, unknown>;
  research_sources: Record<string, unknown>[];
}

export interface ResearchPlan {
  question_id: number;
  question: string;
  status: string;
  subquestions: string[];
  requirements: ResearchRequirement[];
  assumptions: string[];
  unknowns: string[];
  candidate_sources: ResearchCandidateSource[];
  stopping_conditions: string[];
  known_observations: ResearchObservation[];
  unresolved_requirements?: string[];
  terminal_reason?: string | null;
  contradictions?: Array<{ evidence_id: number; claim_id: number | null }>;
  budget?: { max_tasks: number; tasks_created: number; remaining_tasks: number };
}

export interface ResearchRequirement {
  id: string;
  question: string;
  evidence_kind: string;
  can_resolve_claim: boolean;
  status: string;
  terminal_reason: string | null;
  capable_sources: Array<{
    source: string;
    registry_id: string;
    endpoint: string;
    operation: string;
    allowed_fields: string[];
    provenance_requirements: string[];
  }>;
  evidence_ids: number[];
  task_ids: number[];
}

export interface ResearchCandidateSource {
  source: string;
  available: boolean;
  registry_id?: string;
  endpoint?: string;
  operation?: string;
  allowed_fields?: string[];
  supports_requirements?: string[];
  valid_through?: string;
  rate_limit_seconds?: number;
  rank?: number;
  rationale?: string;
  reason?: string;
  scope?: string;
}

export interface ResearchObservation {
  signal_id: number;
  evidence_id: number;
  source: string;
  title: string | null;
  url: string;
  published_at: string | null;
  retrieved_at: string | null;
  matched_term_fraction: number;
  epistemic_status: string;
  matching_is_not_semantic_relevance?: boolean;
}

export interface ResearchEvidenceSource {
  signal_id: number;
  evidence_id: number;
  title: string | null;
  url: string | null;
  external_id: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  source: string;
  assessment?: {
    assessment_state: string;
    provenance: {
      present: boolean;
      source_registry_id: string | null;
      retrieval_timestamp: string | null;
      publication_timestamp: string | null;
      canonical_url: string | null;
      source_identity: string | null;
    };
    keyword_overlap: {
      method: string;
      query_term_count: number;
      matched_terms: string[];
      unmatched_terms: string[];
    };
    publication_age_days: number | null;
    freshness_basis: string;
    source_record: string;
    source_reliability: string;
    semantic_relevance: string;
    contradictions: string;
    claim_support: string;
  };
}

// ---------- request plumbing ----------

export class ForgeApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ForgeApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: init?.signal || controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(sessionApiKey ? { "X-API-Key": sessionApiKey } : {}),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ForgeApiError(0, "Request timed out while reading Forge memory.");
    }
    // Network-level failure (backend not running, offline) — distinct
    // from an HTTP error status, so callers can show OFFLINE rather
    // than a generic error.
    throw new ForgeApiError(0, "offline");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ForgeApiError(res.status, text || res.statusText);
  }
  return res.json() as Promise<T>;
}


export interface ForgeRuntime {
  signals: number | null;
  evidence: number | null;
  research_tasks: number | null;
  claims: number | null;
  opportunities: number | null;
  decisions: number | null;
  experiments: number | null;
  outcomes: number | null;
  learning_events: number | null;
  patterns: number | null;
  beliefs: number | null;
  worker: {
    queued_tasks: number;
    last_task: {
      id: number | null;
      worker_type: string | null;
      task_name: string | null;
      status: string | null;
      updated_at: string | null;
      error: string | null;
    } | null;
  };
  cycles: {
    running_count: number;
    last: {
      id: number | null;
      status: string | null;
      started_at: string | null;
      ended_at: string | null;
      error: string | null;
    } | null;
    last_completed: {
      id: number | null;
      started_at: string | null;
      ended_at: string | null;
      duration_ms: number | null;
    } | null;
  };
  loop_stages_with_data: { name: string; state: string; count: number }[];
  active_stage: string;
  truth?: {
    epistemic_labels: {
      raw_signals: number;
      historical_or_observed_signals: number;
      currently_collected_signals: number;
      duplicate_signals: number;
      inferred_patterns: number;
      opportunity_hypotheses: number;
      verified_claims: number;
      human_validated_problems: number;
      real_experiments: number;
      actual_outcomes: number;
      reality_learning_events: number;
      actual_revenue: number;
    };
    provenance: {
      signal_sources: Record<string, number>;
      collection_status: Record<string, number>;
      canonical_signals: number;
      evidence_with_provenance: number;
      evidence_without_provenance: number;
    };
    signal_quality: {
      canonical_distribution: { score: number | null; count: number }[];
      canonical_average: number | null;
    };
    operations: {
      completed_cycles: number;
      failed_cycles: number;
      running_cycles: number;
      pending_actions: number;
      queued_tasks: number;
      outbox_queued: number;
      outbox_failed: number;
    };
    interpretation: {
      signals_are_raw_observations: boolean;
      evidence_is_not_verified_truth: boolean;
      opportunities_are_hypotheses_until_human_validated: boolean;
      actual_revenue_is_real_scope_only: boolean;
    };
  };
}

// ---------- Product / Distribution / Customer workflow (v2) ----------
// Mirrors backend/app/schemas.py. All revenue/customer values are
// evidence-gated: they can only come from real ACTUAL_* outcomes, never
// fabricated. The frontend renders them as-is; it never guesses.

export interface Product {
  data_scope?: DataScope;
  id: number;
  opportunity_id: number | null;
  goal_id: number | null;
  name: string;
  offer: string;
  target_customer: string | null;
  pricing: string | null;
  mvp_scope: string | null;
  status: string; // concept | validating | launched | iterating | retired
  launch_state: string | null; // not_launched | piloting | public
  created_at: string;
  updated_at: string;
  retired_at: string | null;
  retirement_reason: string | null;
  hypothesis: string | null;
  actual_customers: number;
  actual_revenue: number;
  actual_cost: number;
  offer_brief?: Record<string, unknown> | null;
  approval_status?: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "NEEDS_EDIT" | string;
  approval_note?: string | null;
  approved_at?: string | null;
}

export interface ProductSummary extends Product {
  channel_count: number;
  lead_count: number;
  paid_customer_count: number;
}

export interface Channel {
  data_scope?: DataScope;
  id: number;
  product_id: number | null;
  opportunity_id: number | null;
  channel_type: string;
  name: string;
  description: string | null;
  status: string; // planned | active | paused | retired
  action_id: number | null;
  created_at: string;
  updated_at: string;
  outreach_count: number;
  response_count: number;
  conversion_count: number;
}

export interface CustomerEvent {
  data_scope?: DataScope;
  id: number;
  product_id: number | null;
  channel_id: number | null;
  opportunity_id: number | null;
  contact_name: string | null;
  contact_identifier: string | null;
  segment: string | null;
  stage: string; // lead | contacted | interested | paid_customer | churned
  event_type: string | null;
  notes: string | null;
  action_id: number | null;
  outcome_id: number | null;
  occurred_at: string;
  created_at: string;
}

export interface FlowOpportunity {
  id: number; problem: string; target_customer: string; score: number; status: string;
  market_confidence: number; revenue_confidence: number; uncertainty: number;
  economic_evidence_summary: string | null; problem_evidence_signal_ids: string | null;
  value_hypothesis: string; offer_hypothesis: string;
}
export interface FlowOutcome { id?: number; actual?: string | null; success?: boolean | null; conversions?: number | null; contacts?: Record<string, unknown>[] | null; [key: string]: unknown; }
export interface FlowState {
  status: string; opportunity_id: number; opportunity: FlowOpportunity;
  data_scope?: DataScope;
  decision: {id: number | null; title?: string | null; rationale?: string | null; status?: string | null};
  experiment: { id: number | null; hypothesis: string | null; expected_result: string | null; status: string | null; policy_decision: string | null; requires_owner_approval: boolean; stage: string; required_inputs: string[]; result: string | null; data_scope: string | null; revenue: number | null; conversions: number | null };
  outcomes_count: number; outcomes?: FlowOutcome[]; learning_events?: unknown[]; lessons?: unknown[]; channels?: Channel[]; customer_events?: CustomerEvent[]; products: ProductSummary[]; lessons_recalled: number;
}
export interface NextDecisionResponse {
  id?: number;
  title?: string | null;
  rationale?: string | null;
  status?: string | null;
  expected_outcome?: string | null;
  expected_cost?: number | null;
  data_scope?: DataScope;
  [key: string]: unknown;
}
export interface FlowResponse { flow: FlowState[]; pipeline: Record<string, unknown>; data_scope?: DataScope; }

export interface ProductPipeline {
  products: ProductSummary[];
  channels: Channel[];
  customer_events: CustomerEvent[];
  total_products: number;
  launched_products: number;
  total_outreach: number;
  total_leads: number;
  total_paid_customers: number;
  realized_revenue: number;
}

export interface ProductCreate {
  opportunity_id?: number | null;
  goal_id?: number | null;
  name: string;
  offer: string;
  target_customer?: string | null;
  pricing?: string | null;
  mvp_scope?: string | null;
  hypothesis?: string | null;
  launch_state?: string | null;
}

export interface ProductUpdate {
  name?: string | null;
  offer?: string | null;
  target_customer?: string | null;
  pricing?: string | null;
  mvp_scope?: string | null;
  hypothesis?: string | null;
  status?: string | null;
  launch_state?: string | null;
  retirement_reason?: string | null;
}

export interface OfferDraftCreate {
  problem: string;
  target_customer?: string | null;
}

export interface OfferApprovalUpdate {
  status: "APPROVED" | "REJECTED" | "NEEDS_EDIT";
  note?: string | null;
}

export interface ChannelCreate {
  product_id?: number | null;
  opportunity_id?: number | null;
  channel_type: string;
  name: string;
  description?: string | null;
  status?: string | null;
  action_id?: number | null;
}

export interface ChannelUpdate {
  status?: string | null;
  name?: string | null;
  description?: string | null;
}

export interface CustomerEventCreate {
  product_id?: number | null;
  channel_id?: number | null;
  opportunity_id?: number | null;
  contact_name?: string | null;
  contact_identifier?: string | null;
  segment?: string | null;
  stage?: string | null;
  event_type?: string | null;
  notes?: string | null;
  action_id?: number | null;
  outcome_id?: number | null;
}

export interface EarningOffer {
  id: number;
  pathway: string;
  title: string;
  skill: string;
  customer: string;
  price_npr: number | null;
  age_band: "14_17" | "18_plus";
  status: "draft" | "customer_confirmed" | "paid" | "failed" | "abandoned";
  next_actions: { text: string; completed: boolean }[];
  outcome_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface RepairWorkItem {
  id: number;
  customer_id: number;
  asset_label: string;
  reported_problem: string;
  status: string;
  data_scope: DataScope;
  opportunity_id: number | null;
  decision_id: number | null;
  experiment_id: number | null;
  action_id: number | null;
  product_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface RepairCustomer { id: number; name: string; contact_identifier: string | null; consent_state: string; data_scope: DataScope; created_at: string; }
export interface RepairEvent { id: number; work_item_id: number; actor: string; event_type: string; previous_state: string | null; next_state: string; reason: string | null; evidence_ids: string | null; metadata_json: Record<string, unknown> | null; idempotency_key: string | null; created_at: string; }
export interface RepairCommunication { id: number; work_item_id: number; channel: string; body: string; status: string; customer_response: string | null; action_id: number | null; integration_delivery_id: number | null; created_at: string; updated_at: string; }
export interface RepairEvidence { id: number; content: string | null; source: string | null; provenance: string | null; created_at: string; }
export interface RepairWorkItemDetail { work_item: RepairWorkItem; customer: RepairCustomer; events: RepairEvent[]; communications: RepairCommunication[]; evidence: RepairEvidence[]; decision: Record<string, unknown> | null; experiment: Record<string, unknown> | null; outcomes: Record<string, unknown>[]; learning_events: Record<string, unknown>[]; }

export const api = {
  getStats: () => request<Stats>("/stats"),
  listEarningOffers: (workspaceKey: string) =>
    request<EarningOffer[]>(`/earn/offers?workspace_key=${encodeURIComponent(workspaceKey)}`),
  createEarningOffer: (payload: {
    workspace_key: string;
    pathway: string;
    title: string;
    skill: string;
    customer: string;
    price_npr: number | null;
    age_band: "14_17" | "18_plus";
    next_actions?: { text: string; completed: boolean }[];
  }) => request<EarningOffer>("/earn/offers", { method: "POST", body: JSON.stringify(payload) }),
  updateEarningOfferStatus: (id: number, workspaceKey: string, status: EarningOffer["status"], outcomeNote?: string) =>
    request<EarningOffer>(`/earn/offers/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ workspace_key: workspaceKey, status, outcome_note: outcomeNote || null }),
    }),
  updateEarningOfferChecklist: (id: number, workspaceKey: string, nextActions: EarningOffer["next_actions"]) =>
    request<EarningOffer>(`/earn/offers/${id}/checklist`, {
      method: "PUT",
      body: JSON.stringify({ workspace_key: workspaceKey, next_actions: nextActions }),
    }),
  getRuntime: () => request<ForgeRuntime>("/forge/runtime"),
  getSignals: () => request<Signal[]>("/signals"),
  getEvidence: () => request<Evidence[]>("/forge/evidence"),
  getClaims: (limit = 50) => request<Record<string, unknown>[]>(`/world/claims?limit=${limit}`),
  createSignal: (content: string, source = "manual", category?: string) =>
    request<Signal>("/signals", {
      method: "POST",
      body: JSON.stringify({ content, source, category }),
    }),
  getPatterns: () => request<Pattern[]>("/patterns"),
  runPatterns: () =>
    request<{ patterns_found: number; patterns: Pattern[] }>("/patterns/run", {
      method: "POST",
    }),
  getOpportunities: () => request<Opportunity[]>("/opportunities"),
  analyze: (idea: string) =>
    request<AnalyzeResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify({ idea }),
    }),
  getAnalyzeProgress: (researchStatusUrl: string, signal?: AbortSignal) =>
    request<AnalyzeProgressResponse>(researchStatusUrl, { signal }),

  // Observer Engine
  observe: (content: string, source = "manual") =>
    request<Signal>("/observer/observe", {
      method: "POST",
      body: JSON.stringify({ content, source }),
    }),
  getImportantSignals: (limit = 5, minImportance = 0) =>
    request<Signal[]>(
      `/observer/signals?limit=${limit}&min_importance=${minImportance}`
    ),
  getObserverStats: () => request<ObserverStats>("/observer/stats"),

  // Forge intelligence layer
  runForgeCycle: () =>
    request<ForgeCycleSummary>("/forge/cycle", { method: "POST" }),
  getQuestions: (status?: string) =>
    request<ResearchQuestion[]>(
      `/forge/questions${status ? `?status=${status}` : ""}`
    ),
  getTasks: () => request<ResearchTask[]>("/forge/tasks"),
  getOutcomes: (limit = 50) => request<ForgeOutcome[]>(`/forge/outcomes?limit=${limit}`),
  getLearning: (limit = 50) => request<LearningEvent[]>(`/forge/learning?limit=${limit}`),
  getCycles: (limit = 20) => request<CycleRun[]>(`/forge/cycles?limit=${limit}`),
  getBeliefs: () => request<Belief[]>("/forge/beliefs"),
  getBeliefGraph: (id: number) => request<BeliefGraph>(`/forge/world/beliefs/${id}`),
  askForge: (question: string) =>
    request<AskResponse>("/forge/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  // Goals / Strategy Engine (v1.0)
  getGoals: () => request<Goal[]>("/forge/goals"),
  createGoal: (statement: string, target_metric?: string, priority = 50) =>
    request<Goal>("/forge/goals", {
      method: "POST",
      body: JSON.stringify({ statement, target_metric, priority }),
    }),
  getGoalGraph: (id: number) => request<GoalGraph>(`/forge/world/goals/${id}`),
  getStrategiesForGoal: (goalId: number, status?: string) =>
    request<Strategy[]>(
      `/forge/goals/${goalId}/strategies${status ? `?status=${status}` : ""}`
    ),
  generateStrategies: (goalId: number) =>
    request<Strategy[]>(`/forge/goals/${goalId}/strategies`, { method: "POST" }),

  // Money Engine (v1.1-v1.3)
  getRankedOpportunities: (limit = 5, goalId?: number) =>
    request<RankedOpportunity[]>(
      `/forge/money/opportunities?limit=${limit}${goalId ? `&goal_id=${goalId}` : ""}`
    ),
  getOwnerRankedOpportunities: (limit = 10) =>
    request<OwnerRankedOpportunity[]>(`/forge/money/opportunities/owner-ranked?limit=${limit}`),
  getOpportunityMoneyGraph: (id: number) =>
    request<OpportunityMoneyGraph>(`/forge/money/opportunities/${id}`),
  getOpportunityEvidence: (id: number) =>
    request<EvidenceStatus>(`/forge/money/opportunities/${id}/evidence`),
  getMoneyRecommendation: () => request<MoneyRecommendation>("/forge/money/recommend"),
  getMoneyDashboard: () => request<MoneyDashboard>("/forge/money/dashboard"),
  getRevenueSources: () => request<RevenueSource[]>("/forge/revenue-sources"),
  getSuggestedRevenueSources: (opportunityId: number) =>
    request<RevenueSource[]>(`/forge/money/opportunities/${opportunityId}/suggested-sources`),
  linkRevenueSource: (opportunityId: number, revenueSourceId: number) =>
    request<Opportunity>(`/forge/money/opportunities/${opportunityId}/revenue-source`, {
      method: "POST",
      body: JSON.stringify({ revenue_source_id: revenueSourceId }),
    }),

  // Money Execution Engine (v1.5)
  createExecutionAction: (payload: {
    opportunity_id: number;
    action_type: string;
    description: string;
    strategy_id?: number;
    required_inputs?: string;
    expected_result?: string;
  }) =>
    request<ExecutionAction>("/forge/execution/actions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getExecutionActions: (opportunityId?: number) =>
    request<ExecutionAction[]>(
      `/forge/execution/actions${opportunityId ? `?opportunity_id=${opportunityId}` : ""}`
    ),
  getExecutionAction: (id: number) => request<ExecutionAction>(`/forge/execution/actions/${id}`),
  getActionPackage: (id: number) => request<ActionPackage>(`/forge/execution/actions/${id}/package`),
  approveExecutionAction: (id: number) =>
    request<ExecutionAction>(`/forge/execution/actions/${id}/approve`, { method: "POST" }),
  startExecutionAction: (id: number) =>
    request<ExecutionAction>(`/forge/execution/actions/${id}/start`, { method: "POST" }),
  recordExecutionResult: (
    id: number,
    payload: { result: string; revenue?: number; conversions?: number; costs?: number }
  ) =>
    request<ExecutionAction>(`/forge/execution/actions/${id}/result`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recordHumanResult: (id: number, result: string) =>
    request<ActionPackage>(`/forge/execution/actions/${id}/human-result`, {
      method: "POST",
      body: JSON.stringify({ result }),
    }),
  recordVerifiedRevenue: (
    id: number,
    payload: { amount: number; currency: string; source: string; reference: string }
  ) =>
    request<ActionPackage>(`/forge/execution/actions/${id}/verified-revenue`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRankedActions: (limit = 10) => request<RankedAction[]>(`/forge/execution/rank?limit=${limit}`),
  getExecutionRecommendation: () => request<ExecutionRecommendation>("/forge/execution/recommend"),

  // Autonomy Policy Engine (v1.7)
  getAutonomyPolicy: () => request<AutonomyPolicy>("/forge/autonomy/policy"),
  updateAutonomyPolicy: (payload: Partial<Omit<AutonomyPolicy, "id" | "name" | "active" | "created_at" | "updated_at">>) =>
    request<AutonomyPolicy>("/forge/autonomy/policy", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  previewPolicyEvaluation: (opportunityId: number, actionType: string, estimatedCost?: number) =>
    request<PolicyEvaluation>(
      `/forge/autonomy/evaluate?opportunity_id=${opportunityId}&action_type=${actionType}` +
        (estimatedCost !== undefined ? `&estimated_cost=${estimatedCost}` : "")
    ),
  getBlockedActions: () => request<ExecutionAction[]>("/forge/execution/actions/blocked"),
  getRevenueBreakdown: () => request<RevenueBreakdown>("/forge/money/revenue-breakdown"),
  getStrategyPerformance: (strategyId: number) =>
    request<StrategyPerformance>(`/forge/strategies/${strategyId}/performance`),
  runAutonomyCycleNow: () =>
    request<AutonomousCycleSummary>("/forge/autonomy/run-cycle", { method: "POST" }),

  // Economic Intelligence (v1.8)
  runEconomicDiscoveryNow: () =>
    request<{ patterns_reviewed: number; opportunities_created: number; patterns_without_sufficient_evidence: number }>(
      "/forge/economic/discover",
      { method: "POST" }
    ),
  getPatternCorroboration: (patternId: number) =>
    request<{ unique_sources: number; independent_observations: number; corroboration_count: number }>(
      `/forge/economic/patterns/${patternId}/corroboration`
    ),

  // Canonical opportunity -> decision -> experiment -> outcome -> product flow
  getFlow: (limit = 10, scope: DataScope = "REAL") => request<FlowResponse>(withScope("/orchestrate/flow", scope, limit)),
  getOpportunityFlow: (id: number, scope: DataScope = "REAL") => request<FlowState>(withScope(`/orchestrate/flow/${id}`, scope)),
  advanceFlow: (id: number, scope: DataScope = "REAL") => request<FlowState>(withScope(`/orchestrate/${id}/advance`, scope), { method: "POST" }),
  approveFlow: (id: number, scope: DataScope = "REAL") => request<FlowState>(withScope(`/orchestrate/${id}/approve`, scope), { method: "POST" }),
  executeFlow: (id: number, scope: DataScope = "REAL") => request<FlowState>(withScope(`/orchestrate/${id}/execute`, scope), { method: "POST" }),
  rejectFlow: (id: number, scope: DataScope = "REAL") => request<FlowState>(withScope(`/orchestrate/${id}/reject`, scope), { method: "POST" }),
  // Outcome scope is authoritative in the JSON body. The backend endpoint does
  // not accept a data_scope query parameter, so keep this call body-only.
  recordFlowOutcome: (id: number, body: FlowOutcome, scope: DataScope = "REAL") => request<FlowState>(`/orchestrate/${id}/outcome`, { method: "POST", body: JSON.stringify({ ...body, data_scope: scope }) }),
  createFlowProduct: (id: number, body: Partial<ProductCreate>, scope: DataScope = "REAL") => request<{status: string; reason?: string; product_id?: number; product?: ProductSummary}>(withScope(`/orchestrate/${id}/product`, scope), { method: "POST", body: JSON.stringify({ ...body, data_scope: scope }) }),
  getNextDecision: (id: number, scope: DataScope = "REAL") => request<NextDecisionResponse>(withScope(`/orchestrate/${id}/next-decision`, scope), { method: "POST" }),

  // Product / Distribution / Customer workflow (v2)
  getProductPipeline: (scope: DataScope = "REAL") => request<ProductPipeline>(withScope("/products/pipeline", scope)),
  listProducts: (scope: DataScope = "REAL") => request<ProductSummary[]>(withScope("/products", scope)),
  createProduct: (payload: Partial<ProductCreate>, scope: DataScope = "REAL") =>
    request<Product>("/products", { method: "POST", body: JSON.stringify({ ...payload, data_scope: scope }) }),
  createOfferDraft: (payload: OfferDraftCreate, scope: DataScope = "REAL") =>
    request<Product>("/products/offer-drafts", { method: "POST", body: JSON.stringify({ ...payload, data_scope: scope }) }),
  updateOfferApproval: (id: number, payload: OfferApprovalUpdate) =>
    request<Product>(`/products/${id}/offer-approval`, { method: "POST", body: JSON.stringify(payload) }),
  updateProduct: (id: number, payload: Partial<ProductUpdate>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listChannels: () => request<Channel[]>("/products/channels"),
  addChannel: (productId: number, payload: Partial<ChannelCreate>, scope: DataScope = "REAL") =>
    request<Channel>(`/products/${productId}/channels`, { method: "POST", body: JSON.stringify({ ...payload, data_scope: scope, product_id: productId }) }),
  updateChannel: (id: number, payload: Partial<ChannelUpdate>) =>
    request<Channel>(`/products/channels/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listCustomers: () => request<CustomerEvent[]>("/products/customers"),
  addCustomerEvent: (payload: Partial<CustomerEventCreate>, scope: DataScope = "REAL") =>
    request<CustomerEvent>("/products/customers", { method: "POST", body: JSON.stringify({ ...payload, data_scope: scope }) }),
  addChannelCustomer: (channelId: number, payload: Partial<CustomerEventCreate>, scope: DataScope = "REAL") =>
    request<CustomerEvent>(`/products/channels/${channelId}/customers`, {
      method: "POST",
      body: JSON.stringify({ ...payload, data_scope: scope, channel_id: channelId }),
    }),
  recordProductOutcome: (productId: number, actualValue: number, scope: DataScope = "REAL", idempotencyKey?: string, source = "manual", description?: string) => {
    const key = idempotencyKey || `forgeos-revenue-${scope.toLowerCase()}-${productId}-${crypto.randomUUID()}`;
    const params = new URLSearchParams({ outcome_type: "ACTUAL_REVENUE", product_id: String(productId), actual_value: String(actualValue), unit: "USD", source, data_scope: scope, idempotency_key: key });
    if (description) params.set("qualitative_result", description);
    return request<{ id: number; outcome_type: string; actual_value: number; data_scope: DataScope; label: string }>(`/forge/outcomes?${params.toString()}`, { method: "POST" });
  },
  // Repair-shop vertical slice
  listRepairWorkItems: (scope: DataScope = "SANDBOX") => request<RepairWorkItem[]>(`/repair-shop/work-items?data_scope=${scope}`),
  getRepairWorkItem: (id: number) => request<RepairWorkItemDetail>(`/repair-shop/work-items/${id}`),
  createRepairWorkItem: (payload: { customer_name: string; contact_identifier?: string; consent_state: string; asset_label: string; reported_problem: string; data_scope: DataScope; actor?: string; idempotency_key?: string }) => request<RepairWorkItem>("/repair-shop/work-items", { method: "POST", body: JSON.stringify(payload) }),
  attachRepairEvidence: (id: number, payload: { content: string; source?: string; actor?: string; idempotency_key?: string }) => request<RepairEvidence>(`/repair-shop/work-items/${id}/evidence`, { method: "POST", body: JSON.stringify(payload) }),
  createRepairTriage: (id: number, payload: { rationale: string; expected_outcome: string; confidence: number; actor?: string; idempotency_key?: string }) => request<Record<string, unknown>>(`/repair-shop/work-items/${id}/triage`, { method: "POST", body: JSON.stringify(payload) }),
  proposeRepairStatus: (id: number, body: string) => request<RepairCommunication>(`/repair-shop/work-items/${id}/communications`, { method: "POST", body: JSON.stringify({ body }) }),
  approveRepairStatus: (id: number) => request<RepairCommunication>(`/repair-shop/communications/${id}/approve`, { method: "POST", body: JSON.stringify({ data_scope: "SANDBOX" }) }),
  recordRepairResponse: (id: number, accepted: boolean, response: string) => request<RepairCommunication>(`/repair-shop/communications/${id}/response`, { method: "POST", body: JSON.stringify({ accepted, response }) }),
  recordRepairPayment: (id: number, payload: { amount: number; unit: string; provider: string; provider_reference: string; data_scope: DataScope; idempotency_key?: string }) => request<Record<string, unknown>>(`/repair-shop/work-items/${id}/payment`, { method: "POST", body: JSON.stringify(payload) }),
  recordRepairOutcome: (id: number, payload: { actual: string; success?: boolean; source?: string }) => request<Record<string, unknown>>(`/repair-shop/work-items/${id}/outcome`, { method: "POST", body: JSON.stringify(payload) }),
  listNetworkConnections: () => request<NetworkConnectionRow[]>("/forge/connections"),
  scanNetworkConnections: (limit = 50) =>
    request<{ id: number; state: string; public_visible: boolean }[]>(`/forge/connections/scan?limit=${limit}`, { method: "POST" }),
  advanceNetworkConnection: (id: number, nextState: string, options?: { amountNpr?: number; evidenceReference?: string }) => {
    const params = new URLSearchParams({ next_state: nextState });
    if (options?.amountNpr !== undefined) params.set("amount_npr", String(options.amountNpr));
    if (options?.evidenceReference) params.set("evidence_reference", options.evidenceReference);
    return request<{ id: number; state: string; public_visible: boolean; payment?: string }>(`/forge/connections/${id}/advance?${params.toString()}`, { method: "POST" });
  },
  recordNetworkResponse: (id: number, note: string) =>
    request<{ id: number; state: string; accepted: boolean }>(`/forge/connections/${id}/response?note=${encodeURIComponent(note)}`, { method: "POST" }),
  publishNetworkConnection: (id: number) =>
    request<{ id: number; state: string; public_visible: boolean }>(`/forge/connections/${id}/publish`, { method: "POST" }),
  confirmNetworkPayment: (id: number) =>
    request<{ id: number; state: string; amount_npr: number; payment: string }>(`/forge/connections/${id}/confirm-payment`, { method: "POST" }),
};

/**
 * Client-side mirror of execution_engine.get_action_stage() — the raw
 * ExperimentOut returned by list/get endpoints doesn't carry a `stage`
 * field (only the ranked/recommend endpoints compute it server-side),
 * so this derives the same classification from the same real fields
 * rather than guessing.
 */
export interface NetworkConnectionRow {
  id: number;
  left_kind: string;
  left_id: number;
  right_kind: string;
  right_id: number;
  state: string;
  reason: string;
  evidence_reference?: string | null;
  constraints?: string | null;
  unknown?: string | null;
  agreement_gap: string;
  public_visible: boolean;
  seconds_to_recorded_payment?: number | null;
  latest_response?: string | null;
}

export function actionStage(
  action: ExecutionAction
): "blocked" | "planned" | "attempted" | "completed" | "verified" {
  if (action.status === "blocked") return "blocked";
  if (action.completed_at) {
    return action.revenue !== null && action.costs !== null ? "verified" : "completed";
  }
  if (action.started_at) return "attempted";
  return "planned";
}

export function computeProfit(action: ExecutionAction): number | null {
  if (action.revenue === null || action.costs === null) return null;
  return Math.round((action.revenue - action.costs) * 100) / 100;
}
