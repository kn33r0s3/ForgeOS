import { cachedRead, type CacheScope } from "./api-cache";

export interface OpportunityRecord {
  id: number;
  problem: string;
  target_customer: string;
  solution: string;
  business_model: string;
  pricing_idea?: string | null;
  score: number;
  difficulty?: string | null;
  customer_segment?: string | null;
  status?: string;
}

export interface RankedOpportunity {
  opportunity: OpportunityRecord;
  money_score: number;
  expected_value: number | null;
}

export interface ActionRecord {
  data_scope?: "REAL" | "SANDBOX";
  id: number;
  action: string;
  action_type?: string | null;
  status: string;
  requires_owner_approval?: boolean;
  policy_decision?: string | null;
  policy_reason?: string | null;
  approved_at?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface MoneyDashboard {
  best_opportunities: RankedOpportunity[];
  active_experiments: ActionRecord[];
  completed_experiments_count: number;
  total_revenue_recorded: number;
  conversion_rate: number | null;
  winning_experiments: ActionRecord[];
  failed_experiments: ActionRecord[];
}

export interface RuntimeSnapshot {
  signals: number | null;
  evidence: number | null;
  research_tasks: number | null;
  opportunities: number | null;
  outcomes: number | null;
  active_stage: string;
  worker: {
    queued_tasks: number;
    last_task: {
      worker_type: string | null;
      task_name: string | null;
      status: string | null;
      updated_at: string | null;
      error: string | null;
    } | null;
  };
  cycles: {
    running_count: number;
    last_completed: {
      id: number | null;
      started_at: string | null;
      ended_at: string | null;
      duration_ms: number | null;
    } | null;
  };
  truth?: {
    epistemic_labels: {
      currently_collected_signals: number;
      opportunity_hypotheses: number;
      human_validated_problems: number;
      actual_outcomes: number;
      actual_revenue: number;
    };
    operations: {
      pending_actions: number;
      queued_tasks: number;
      running_cycles: number;
    };
  };
}

async function fetchApiJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/**
 * Engine reads are cached for a few seconds because several pages ask for the
 * same snapshot (home, opportunities, actions each show part of
 * `/api/forge/runtime`). Callers that must reflect a just-performed action pass
 * `{ fresh: true }`.
 *
 * Errors are deliberately not cached: `fetchApiJson` throws on a bad response,
 * so a failure stays a live signal for the next caller and for "Retry".
 */
export function loadRuntimeSnapshot(scope?: CacheScope) {
  return cachedRead("/api/forge/runtime", () => fetchApiJson<RuntimeSnapshot>("/api/forge/runtime"), scope);
}

export function loadMoneyDashboard(scope?: CacheScope) {
  return cachedRead(
    "/api/forge/money/dashboard",
    () => fetchApiJson<MoneyDashboard>("/api/forge/money/dashboard"),
    scope,
  );
}

export function loadExecutionActions(scope?: CacheScope) {
  return cachedRead(
    "/api/forge/execution/actions",
    () => fetchApiJson<ActionRecord[]>("/api/forge/execution/actions"),
    scope,
  );
}
