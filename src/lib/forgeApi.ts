import type {
  ApiHealth,
  Belief,
  Cycle,
  Decision,
  ExecutionAction,
  ForgeDashboardData,
  ObserverStats,
  Opportunity,
  Outcome,
  Signal,
  SystemStats,
  WorkerTask,
} from '../types';

type Guard<T> = (value: unknown) => value is T;
type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isNumber(value);
}

function isSignal(value: unknown): value is Signal {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.source)
    && isString(value.content)
    && isNullableString(value.category)
    && isString(value.timestamp)
    && isNullableString(value.signal_type)
    && isNumber(value.importance_score)
    && typeof value.processed === 'boolean'
    && isNullableString(value.tags)
    && isNumber(value.reliability_score)
    && isNumber(value.freshness_score)
    && isNullableNumber(value.quality_score)
    && isNullableString(value.quality_flags)
    && isNullableNumber(value.is_duplicate_of);
}

function isOpportunity(value: unknown): value is Opportunity {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.problem)
    && isString(value.target_customer)
    && isString(value.solution)
    && isString(value.business_model)
    && isNullableString(value.pricing_idea)
    && isNullableString(value.market_analysis)
    && isNullableString(value.mvp_plan)
    && isNullableString(value.validation_plan)
    && isNullableString(value.difficulty)
    && isNumber(value.score)
    && isString(value.created_at)
    && isNumber(value.market_confidence)
    && isNumber(value.revenue_confidence)
    && isNullableNumber(value.estimated_revenue)
    && isNullableNumber(value.estimated_revenue_30d)
    && isNullableNumber(value.estimated_revenue_90d)
    && isNullableNumber(value.estimated_startup_cost)
    && isString(value.status);
}

function isBelief(value: unknown): value is Belief {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.statement)
    && isNullableNumber(value.pattern_id)
    && isNullableString(value.supporting_signal_ids)
    && isNumber(value.confidence_score)
    && isString(value.created_at)
    && isString(value.last_updated);
}

function isDecision(value: unknown): value is Decision {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.title)
    && isString(value.rationale)
    && isString(value.status)
    && isNullableNumber(value.opportunity_id)
    && isNullableNumber(value.confidence_at_decision)
    && isString(value.created_at);
}

function isExecutionAction(value: unknown): value is ExecutionAction {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.action)
    && isString(value.action_type)
    && isString(value.status)
    && isNullableString(value.policy_decision)
    && isNullableString(value.policy_reason)
    && typeof value.requires_owner_approval === 'boolean'
    && isString(value.data_scope)
    && isString(value.created_at);
}

function isOutcome(value: unknown): value is Outcome {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.outcome_type)
    && isNullableNumber(value.actual_value)
    && isNullableString(value.unit)
    && isString(value.qualitative_result)
    && (value.success === null || typeof value.success === 'boolean')
    && isNullableNumber(value.action_id)
    && isString(value.data_scope)
    && isString(value.label);
}

function isWorkerTask(value: unknown): value is WorkerTask {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.worker_type)
    && isString(value.task_name)
    && isNumber(value.priority)
    && (value.inputs === null || isObject(value.inputs))
    && isString(value.status)
    && isString(value.created_at)
    && isString(value.updated_at);
}

function isSystemStats(value: unknown): value is SystemStats {
  return isObject(value)
    && isNumber(value.total_signals)
    && isNumber(value.total_patterns)
    && isNumber(value.total_opportunities)
    && isNumber(value.total_experiments);
}

function isObserverStats(value: unknown): value is ObserverStats {
  return isObject(value)
    && isNumber(value.total_observations)
    && isNumber(value.high_importance_count)
    && isNumber(value.average_importance)
    && isNumber(value.low_quality_count)
    && isNullableNumber(value.signals_total)
    && isNullableNumber(value.outcomes_real)
    && isNullableNumber(value.verified_revenue);
}

function isCycle(value: unknown): value is Cycle {
  return isObject(value)
    && isNumber(value.id)
    && isString(value.started_at)
    && isNullableString(value.ended_at)
    && isNullableNumber(value.duration_ms)
    && isString(value.status)
    && isNullableString(value.error);
}

function isApiHealth(value: unknown): value is ApiHealth {
  return isObject(value)
    && isString(value.status)
    && isObject(value.database)
    && typeof value.database.available === 'boolean'
    && isString(value.database.durability)
    && isNullableString(value.database.error)
    && isObject(value.readiness)
    && typeof value.readiness.ready === 'boolean'
    && Array.isArray(value.readiness.blockers)
    && value.readiness.blockers.every(isString);
}

export function parseTags(value: string | null): string[] {
  return value?.split(',').map((tag) => tag.trim()).filter(Boolean) ?? [];
}

export function apiErrorMessage(payload: unknown, status: number): string {
  if (isObject(payload) && typeof payload.detail === 'string') {
    return payload.detail;
  }
  return `API request failed (${status})`;
}

export async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...init?.headers,
    },
  });
  const body = await response.text();
  let payload: unknown;

  try {
    payload = JSON.parse(body);
  } catch {
    throw new Error(`Expected JSON from ${path}; received HTTP ${response.status}`);
  }

  if (!response.ok) {
    throw new Error(apiErrorMessage(payload, response.status));
  }
  return payload;
}

async function requestObject<T>(path: string, guard: Guard<T>, init?: RequestInit): Promise<T> {
  const payload = await requestJson(path, init);
  if (!guard(payload)) {
    throw new Error(`Unexpected response shape from ${path}`);
  }
  return payload;
}

async function requestList<T>(path: string, guard: Guard<T>): Promise<T[]> {
  const payload = await requestJson(path);
  if (!Array.isArray(payload) || !payload.every(guard)) {
    throw new Error(`Unexpected list response shape from ${path}`);
  }
  return payload;
}

export async function loadForgeDashboard(): Promise<ForgeDashboardData> {
  const [
    health,
    stats,
    observerStats,
    signals,
    recentSignals,
    opportunities,
    beliefs,
    decisions,
    actions,
    outcomes,
    workers,
    cycles,
  ] = await Promise.all([
    requestObject('/api/health', isApiHealth),
    requestObject('/api/stats', isSystemStats),
    requestObject('/api/observer/stats', isObserverStats),
    requestList('/api/signals?limit=200', isSignal),
    requestList('/api/observer/recent?limit=3', isSignal),
    requestList('/api/opportunities', isOpportunity),
    requestList('/api/forge/beliefs', isBelief),
    requestList('/api/forge/decisions', isDecision),
    requestList('/api/forge/execution/actions', isExecutionAction),
    requestList('/api/forge/outcomes', isOutcome),
    requestList('/api/workers', isWorkerTask),
    requestList('/api/forge/cycles?limit=20', isCycle),
  ]);

  return {
    health,
    stats,
    observerStats,
    signals,
    recentSignals,
    opportunities,
    beliefs,
    decisions,
    actions,
    outcomes,
    workers,
    cycles,
  };
}

export async function recordObservation(content: string, source: string): Promise<Signal> {
  return requestObject('/api/signals', isSignal, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, source }),
  });
}
