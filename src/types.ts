export interface Signal {
  id: number;
  source: string;
  content: string;
  category: string;
  timestamp: string;
  signal_type: 'demand' | 'supply' | 'regulatory' | 'market_gap';
  importance_score: number;
  processed: boolean;
  tags: string[];
  reliability_score: number;
  freshness_score: number;
  quality_score: number;
  quality_flags?: string;
  is_duplicate_of?: number | null;
}

export interface ActionChecklistItem {
  task: string;
  done: boolean;
  notes?: string;
}

export interface Opportunity {
  id: number;
  title: string;
  description: string;
  confidence_score: number;
  estimated_revenue: number | null;
  estimated_cost: number | null;
  source_pattern_ids: number[];
  evidence_signal_ids: number[];
  created_at: string;
  status: 'draft' | 'customer_confirmed' | 'in_progress' | 'paid' | 'no_sale' | 'abandoned';
  target_customer?: string | null;
  business_model?: string | null;
  action_checklist: ActionChecklistItem[];
  honest_outcome_notes?: string;
}

export interface Belief {
  id: number;
  statement: string;
  confidence_score: number;
  sources: string[];
  supporting_evidence: number;
  contradicting_evidence: number;
  created_at: string;
  updated_at: string;
}

export interface Decision {
  id: number;
  opportunity_id: number;
  action: string;
  justification: string;
  risk_level: 'low' | 'medium' | 'high';
  standing_authorization: boolean;
  status: 'recommended' | 'approved' | 'executed' | 'declined';
  created_at: string;
}

export interface Execution {
  id: number;
  decision_id: number;
  outcome: string;
  actual_cost: number;
  revenue_generated: number;
  honest_notes: string;
  status: 'completed' | 'failed' | 'in_progress';
  executed_at: string;
}

export interface WorkerTask {
  id: number;
  worker_type: string;
  task_name: string;
  priority: number;
  inputs: Record<string, any>;
  status: 'completed' | 'running' | 'queued' | 'idle';
  cycle_id: number;
  updated_at: string;
}

export interface SystemStats {
  signals_count: number;
  opportunities_count: number;
  beliefs_count: number;
  decisions_count: number;
  executions_count: number;
  workers_count: number;
  experiments_count: number;
  real_revenue: number;
  real_customers: number;
  owner_interventions_per_real_transaction: string;
  latest_cycle_id: number;
  pipeline_health: string;
}
