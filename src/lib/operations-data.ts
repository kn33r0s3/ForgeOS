import { cachedRead, type CacheScope } from "./api-cache.ts";

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

export interface PublicRuntimeSummary {
  active_stage: string;
  pending_actions: number;
  queued_tasks: number;
  running_cycles: number;
  human_validated_problems: number;
  last_completed_at: string | null;
}

async function fetchApiJson<T>(path: string, ownerKey?: string): Promise<T> {
  const response = await fetch(path, {
    headers: {
      Accept: "application/json",
      ...(ownerKey ? { "X-API-Key": ownerKey } : {}),
    },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/**
 * Public pages receive aggregate counts only. Detailed worker/task/action fields
 * stay on the owner-key-protected `/api/forge/runtime` endpoint.
 */
export function loadPublicRuntimeSummary(scope?: CacheScope) {
  return cachedRead(
    "/api/public/runtime-summary",
    () => fetchApiJson<PublicRuntimeSummary>("/api/public/runtime-summary"),
    scope,
  );
}

export function loadMoneyDashboard(ownerKey: string, scope?: CacheScope) {
  return cachedRead(
    "/api/forge/money/dashboard",
    () => fetchApiJson<MoneyDashboard>("/api/forge/money/dashboard", ownerKey),
    scope,
  );
}

export function loadExecutionActions(ownerKey: string, scope?: CacheScope) {
  return cachedRead(
    "/api/forge/execution/actions",
    () => fetchApiJson<ActionRecord[]>("/api/forge/execution/actions", ownerKey),
    scope,
  );
}
