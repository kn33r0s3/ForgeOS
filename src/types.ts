export interface Signal {
  id: number;
  source: string;
  content: string;
  category: string | null;
  timestamp: string;
  signal_type: string | null;
  importance_score: number;
  processed: boolean;
  tags: string | null;
  reliability_score: number;
  freshness_score: number;
  quality_score: number | null;
  quality_flags: string | null;
  is_duplicate_of: number | null;
}

export interface Opportunity {
  id: number;
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
  market_confidence: number;
  revenue_confidence: number;
  estimated_revenue: number | null;
  estimated_revenue_30d: number | null;
  estimated_revenue_90d: number | null;
  estimated_startup_cost: number | null;
  status: string;
}

export interface Belief {
  id: number;
  statement: string;
  pattern_id: number | null;
  supporting_signal_ids: string | null;
  confidence_score: number;
  created_at: string;
  last_updated: string;
}

export interface Decision {
  id: number;
  title: string;
  rationale: string;
  status: string;
  opportunity_id: number | null;
  confidence_at_decision: number | null;
  created_at: string;
}

export interface ExecutionAction {
  id: number;
  action: string;
  action_type: string;
  status: string;
  policy_decision: string | null;
  policy_reason: string | null;
  requires_owner_approval: boolean;
  data_scope: string;
  created_at: string;
}

export interface Outcome {
  id: number;
  outcome_type: string;
  actual_value: number | null;
  unit: string | null;
  qualitative_result: string;
  success: boolean | null;
  action_id: number | null;
  data_scope: string;
  label: string;
}

export interface WorkerTask {
  id: number;
  worker_type: string;
  task_name: string;
  priority: number;
  inputs: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SystemStats {
  total_signals: number;
  total_patterns: number;
  total_opportunities: number;
  total_experiments: number;
}

export interface ObserverStats {
  total_observations: number;
  high_importance_count: number;
  average_importance: number;
  low_quality_count: number;
  signals_total: number | null;
  outcomes_real: number | null;
  verified_revenue: number | null;
}

export interface Cycle {
  id: number;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  status: string;
  error: string | null;
}

export interface ApiHealth {
  status: string;
  database: {
    available: boolean;
    durability: string;
    error: string | null;
  };
  readiness: {
    ready: boolean;
    blockers: string[];
  };
}

export interface ForgeDashboardData {
  health: ApiHealth;
  stats: SystemStats;
  observerStats: ObserverStats;
  signals: Signal[];
  recentSignals: Signal[];
  opportunities: Opportunity[];
  beliefs: Belief[];
  decisions: Decision[];
  actions: ExecutionAction[];
  outcomes: Outcome[];
  workers: WorkerTask[];
  cycles: Cycle[];
}
