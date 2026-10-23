import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { BrandMark } from "@/components/layout/brand-mark";
import { ForgeConsoleWidgets } from "@/components/forge/forge-console";
import { OperatingV4 } from "@/components/owner/operating-v4";
import { ScoutQueue } from "@/components/owner/scout-queue";
import { PurchaseJourney } from "@/components/owner/purchase-journey";

type LeadStage = "REQUESTED" | "REPLIED" | "BOOKED" | "COMPLETED";
type Readiness = {
  database_ok: boolean;
  migrations_ok: boolean;
  smtp_configured: boolean;
  hmac_key_configured: boolean;
  intake_enabled: boolean;
  live_enabled: boolean;
  last_maintenance_at: string | null;
  last_maintenance_age_seconds: number | null;
  last_test_email_at: string | null;
  last_test_email_result: string;
  oldest_unsent_or_failed_owner_email_at: string | null;
  deployed_commit: string | null;
  lead_counts_by_stage: Record<LeadStage, number>;
  lead_counts_by_evidence_class: Record<"REAL" | "TEST", number>;
  new_leads_last_24h: number;
};
type Lead = {
  reference: string;
  received_at: string | null;
  stage: LeadStage;
  evidence_class: "REAL" | "TEST";
  channel: "email" | "phone";
  destination: string | null;
  course: string | null;
};
type LeadDetail = Lead & {
  email: string | null;
  phone: string | null;
  timeline: string | null;
  budget_minimum: number | null;
  budget_maximum: number | null;
  consent_at: string | null;
  history: Array<{
    event: string;
    at: string | null;
    previous_state: string | null;
    state: string | null;
    evidence_reference: string | null;
    outcome_note: string | null;
  }>;
};
type OwnerConsoleState = {
  readiness: Readiness;
  leads: Lead[];
};

export const Route = createFileRoute("/owner")({
  component: OwnerConsolePage,
  head: () => ({
    meta: [
      { title: "Owner console — Hami" },
      { name: "robots", content: "noindex, nofollow, noarchive" },
    ],
  }),
});

async function ownerProjectionFetch<T>(path: string, ownerKey: string): Promise<T> {
  const response = await fetch(path, { headers: { "X-API-Key": ownerKey } });
  if (response.status === 401) {
    throw new Error("Owner authentication failed. Check the key and try again.");
  }
  if (!response.ok) {
    throw new Error(`Owner projection request failed (${response.status}) at ${path}.`);
  }
  return (await response.json()) as T;
}

async function ownerFetch<T>(
  path: string,
  key: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/forge-bot/${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
      "X-API-Key": key,
    },
  });
  if (response.status === 401) {
    throw new Error("Owner authentication failed. Check the key and try again.");
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `The owner request failed (${response.status}).`;
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// Same key-gated pattern as ownerFetch, but against the /api/forge/* owner
// router (runtime window, cycle history, research loop, source clearance).
// Returns null on 404 so the console degrades to UNKNOWN when the backend
// predates an endpoint instead of failing the whole section.
async function forgeFetch<T>(
  path: string,
  key: string,
  init: RequestInit = {},
): Promise<T | null> {
  const response = await fetch(`/api/forge/${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
      "X-API-Key": key,
    },
  });
  if (response.status === 401) {
    throw new Error("Owner authentication failed. Check the key and try again.");
  }
  if (response.status === 404) return null;
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `The owner request failed (${response.status}).`;
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

type CycleSummary = {
  id: number;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  status: string;
  error: string | null;
  // JSON string of {stages, stage_errors, stage_partials} for scheduled intelligence runs;
  // null for older rows that predate per-stage persistence.
  summary: string | null;
};

type CycleEffectSummary = {
  status?: string;
  counts?: Record<string, number>;
  source_observations?: string[];
  internal_work?: string[];
  next_owner_attention?: string;
  reality_boundary?: string;
};

type RuntimeWindow = {
  signals: number | null;
  evidence: number | null;
  research_tasks: number | null;
  opportunities: number | null;
  truth?: {
    operations?: {
      completed_cycles: number;
      partial_cycles?: number;
      failed_cycles: number;
      running_cycles: number;
    };
  };
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
    last: {
      id: number | null;
      status: string | null;
      started_at: string | null;
      ended_at: string | null;
      error: string | null;
    } | null;
  };
};

type ResearchQuestionRow = {
  id: number;
  question: string;
  status: string;
  priority_score: number;
};

type ResearchTaskRow = {
  id: number;
  question_id: number;
  status: string;
  source: string | null;
  query: string;
  objective: string | null;
  current_step: string | null;
  attempts: number;
  max_attempts: number;
  evidence_ids: string | null;
  updated_at: string | null;
  created_at: string;
};

type ResearchTaskEventRow = {
  id: number;
  task_id: number;
  event_type: string;
  step_name: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

type TaskHistoryState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "error"; message: string }
  | { status: "loaded"; events: ResearchTaskEventRow[] };

const TASK_STATUS_ORDER = [
  "planned",
  "queued",
  "open",
  "running",
  "deferred",
  "blocked",
  "completed",
  "failed",
] as const;

function summarizeTaskEventDetails(details: Record<string, unknown> | null): string {
  if (!details) return "";
  const allowedKeys = [
    "status",
    "reason",
    "attempt",
    "next_attempt",
    "step",
    "signals_created",
    "tasks_deferred",
    "evidence_ids",
  ] as const;
  const parts: string[] = [];
  for (const key of allowedKeys) {
    const value = details[key];
    if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") {
      continue;
    }
    const text = String(value).replace(/\s+/g, " ").trim();
    if (!text) continue;
    const clipped = text.length > 100 ? `${text.slice(0, 100)}…` : text;
    parts.push(`${key.replace(/_/g, " ")}: ${clipped}`);
    if (parts.length >= 3) break;
  }
  if (Object.prototype.hasOwnProperty.call(details, "error")) parts.push("error details withheld");
  return parts.join(" · ").slice(0, 300);
}

type ClearanceEntry = {
  display_name: string;
  collector: string;
  url: string;
  valid_through: string;
  days_until_expiry: number;
  clearance_state: "valid" | "expiring_soon" | "expired";
  collector_cleared_now: boolean;
  allowed_operation: string;
};

type IntelligenceState = {
  runtime: RuntimeWindow | null;
  cycles: CycleSummary[] | null;
  questions: ResearchQuestionRow[] | null;
  tasks: ResearchTaskRow[] | null;
  clearance: { as_of: string; sources: ClearanceEntry[] } | null;
};

type GlobalFrontierItem = {
  frontier_id: string;
  record_type: string;
  lane: string;
  kind: string;
  title: string;
  status: string;
  epistemic_state?: string | null;
  next_step: string;
  source_refs: Array<{ kind: string; id: number }>;
  unknown_id?: string;
  recorded_cheapest_test?: string | null;
  domain_hint?: string | null;
  research_source?: string;
  attempts?: number;
  max_attempts?: number;
  success?: boolean | null;
  data_scope?: string;
  source_kind?: string;
  relation_id?: number;
  relation_type?: string;
  from_entity?: { id: number; type: string; name: string };
  to_entity?: { id: number; type: string; name: string };
  domain_hints?: { from: string | null; to: string | null };
  strength?: number | null;
  path_entities?: Array<{ id: number; type: string; name: string }>;
  path_relations?: Array<{ id: number; type: string; state: string }>;
};

type GlobalFrontierView = {
  read_only: boolean;
  selection_method: string;
  limit: number;
  candidate_count_scanned: number;
  lane_counts_scanned: Record<string, number>;
  source_counts_scanned: Record<string, number>;
  scan_limited_sources: string[];
  truncated: boolean;
  items: GlobalFrontierItem[];
  boundary: string;
};

type ProductSummaryView = {
  id: number;
  opportunity_id: number | null;
  name: string;
  offer: string;
  pricing: string | null;
  status: string;
  launch_state: string | null;
  approval_status: string;
  approval_note?: string | null;
  approved_at?: string | null;
  has_offer_brief: boolean;
  data_scope: string;
  lead_count: number;
  paid_customer_count: number;
  actual_customers: number;
  actual_revenue: number;
  actual_revenue_by_currency?: { USD?: number; NPR?: number } | null;
};

type CommercialState = {
  products: ProductSummaryView[] | null;
  error: string | null;
};

type ChannelSummaryView = {
  id: number;
  product_id: number | null;
  opportunity_id: number | null;
  channel_type: string;
  name: string;
  description: string | null;
  status: string;
  outreach_count: number;
  response_count: number;
  conversion_count: number;
  data_scope: "REAL" | "SANDBOX";
};

type PaymentFulfillmentIntentView = {
  id: number;
  product_id: number;
  product_name: string;
  provider: "esewa" | "khalti";
  status: "VERIFIED";
  amount_paisa: number;
  amount_npr: string;
  currency: "NPR";
  provider_reference: string | null;
  created_at: string | null;
  outcome_id: number | null;
};

type PaymentConfigurationView = {
  scope: "configuration_only";
  provider_connectivity_checked: false;
  transaction_state_checked: false;
  providers: {
    esewa: {
      merchant_code_configured: boolean;
      signing_secret_configured: boolean;
      required_credentials_present: boolean;
    };
    khalti: {
      secret_key_configured: boolean;
      required_credentials_present: boolean;
    };
  };
  not_established: string[];
};

type OrchestratorPipelineView = {
  signals: number;
  opportunities: number;
  decisions_accepted: number;
  validation_experiments: number;
  experiments_completed: number;
  outcomes: number;
  learning_events: number;
  lessons: number;
  products: number;
  distribution_channels: number;
  customer_events: number;
  actions_awaiting_approval: number;
  actual_revenue: number;
  actual_revenue_by_currency?: { USD?: number; NPR?: number } | null;
  real_customers: number;
  products_with_revenue: number;
  sandbox: {
    actual_revenue: number;
    actual_revenue_by_currency?: { USD?: number; NPR?: number } | null;
    outcomes: number;
    products: number;
    label: string;
  };
};

type OrchestratorOpportunityView = {
  opportunity_id: number;
  problem: string | null;
  target_customer_hypothesis: string;
  opportunity_status: string;
  score: number | null;
  decision_status: string;
  validation_status: string;
  validation_experiment_id: number | null;
  requires_owner_approval: boolean | null;
  product_count: number;
  distribution_channel_count: number;
  data_scope: "REAL" | "SANDBOX";
};

type OrchestratorOverviewView = {
  data_scope: "REAL" | "SANDBOX";
  flow: OrchestratorOpportunityView[];
  pipeline: OrchestratorPipelineView;
};

type OrchestratorFlowDetailView = {
  data_scope: "REAL" | "SANDBOX";
  opportunity_id: number;
  opportunity: { id: number; problem: string; target_customer: string | null; score: number | null; status: string; market_confidence: number; revenue_confidence: number; uncertainty: number; economic_evidence_summary: string | null; value_hypothesis: string; offer_hypothesis: string };
  decision: { id: number | null; title: string | null; rationale: string | null; status: string | null; recalled_lessons: string[] };
  experiment: { id: number | null; hypothesis: string | null; expected_result: string | null; status: string | null; policy_decision: string | null; requires_owner_approval: boolean; stage: string; required_inputs: string[]; result: string | null; data_scope: string | null; revenue: number | null; conversions: number | null };
  outcomes_count: number;
  outcomes: Array<{
    id: number;
    outcome_type: string;
    source_kind: string;
    verification_state: string;
  }>;
  products: Array<{ id: number; name: string; status: string; launch_state?: string | null }>;
};

type RespondentStage = "lead" | "contacted" | "interested";

function parseOutcomeRespondents(raw: string): {
  contacts: Array<{ identifier: string; stage: RespondentStage; event_type: string; notes: string }>;
  conversions: number;
} {
  const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean);
  if (lines.length === 0) throw new Error("Add at least one actual interview respondent.");
  const seen = new Set<string>();
  const contacts: Array<{ identifier: string; stage: RespondentStage; event_type: string; notes: string }> = [];
  let conversions = 0;
  const stages = new Set<RespondentStage>(["lead", "contacted", "interested"]);
  for (const [index, line] of lines.entries()) {
    const parts = line.split("|").map((part) => part.trim());
    if (parts.length !== 4) throw new Error("Respondent line " + (index + 1) + " must use: pseudonymous-id | stage | confirmed/not confirmed | short note.");
    const [identifier = "", rawStage = "", rawConfirmation = "", note = ""] = parts;
    const stage = rawStage as RespondentStage;
    if (!identifier || !stages.has(stage) || !note) throw new Error("Respondent line " + (index + 1) + " has a missing ID/note or invalid stage.");
    if (!["confirmed", "not confirmed"].includes(rawConfirmation)) throw new Error("Respondent line " + (index + 1) + " must say exactly confirmed or not confirmed.");
    const normalizedId = identifier.toLowerCase();
    if (seen.has(normalizedId)) throw new Error("Duplicate respondent ID: " + identifier + ".");
    seen.add(normalizedId);
    const confirmed = rawConfirmation === "confirmed";
    if (stage === "interested" && !confirmed) throw new Error("Respondent " + identifier + ": interested stage requires problem confirmation.");
    if (stage === "interested") conversions += 1;
    contacts.push({ identifier, stage, event_type: "response", notes: (confirmed ? "confirmed: " : "not confirmed: ") + note });
  }
  return { contacts, conversions };
}

async function ownerCommandFetch<T>(path: string, ownerKey: string, body?: Record<string, unknown>): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "X-API-Key": ownerKey, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
      ? payload.detail
      : "Owner action failed (" + response.status + ") at " + path + ".";
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

async function ownerProductRequest<T>(path: string, method: "POST" | "PATCH", ownerKey: string, body?: Record<string, unknown>): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "X-API-Key": ownerKey, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
      ? payload.detail
      : "Product action failed (" + response.status + ") at " + path + ".";
    throw new Error(detail);
  }
  return (await response.json()) as T;
}
function formatUsd(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "UNKNOWN";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNpr(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "UNKNOWN";
  return new Intl.NumberFormat("en-NP", {
    style: "currency",
    currency: "NPR",
    maximumFractionDigits: 2,
  }).format(value);
}

function displayTime(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}

function signalFor(
  state: "green" | "amber" | "red",
  title: string,
  value: string,
  nextStep: string,
) {
  const colors = {
    green: "border-success/70 bg-success/10",
    amber: "border-warning/70 bg-warning/10",
    red: "border-danger/70 bg-danger/10",
  } as const;
  // Called as a plain function (not a component or list), so no key is needed.
  return (
    <article className={`rounded-card border-2 p-4 ${colors[state]}`}>
      <h3 className="font-extrabold">{title}</h3>
      <p className="mt-1 break-words text-sm font-semibold">{value}</p>
      <p className="mt-2 text-sm leading-5 text-muted">Next: {nextStep}</p>
    </article>
  );
}

// One recorded cycle run with its per-stage breakdown. The summary is a JSON
// string of {stages, stage_errors} written by the scheduled intelligence
// endpoint; older forge_loop rows carry a different shape or none at all.
// Anything unparseable renders as UNKNOWN, never as green.
function CycleCard({ cycle }: { cycle: CycleSummary }) {
  let stages: Record<string, { status?: string }> | null = null;
  let effect: CycleEffectSummary | null = null;
  if (cycle.summary) {
    try {
      const parsed: unknown = JSON.parse(cycle.summary);
      if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
        const root = parsed as Record<string, unknown>;
        if (typeof root.stages === "object" && root.stages !== null && !Array.isArray(root.stages)) {
          const stageMap: Record<string, { status?: string }> = {};
          for (const [name, value] of Object.entries(root.stages as Record<string, unknown>)) {
            if (name === "cycle_effect") continue;
            const rawStatus =
              typeof value === "object" && value !== null && "status" in value
                ? (value as { status?: unknown }).status
                : undefined;
            stageMap[name] = {
              status: typeof rawStatus === "string" ? rawStatus : "unknown",
            };
          }
          stages = stageMap;
        }

        const rawStages = root.stages;
        const rawEffect =
          typeof rawStages === "object" && rawStages !== null && !Array.isArray(rawStages)
            ? (rawStages as Record<string, unknown>).cycle_effect
            : undefined;
        if (typeof rawEffect === "object" && rawEffect !== null && !Array.isArray(rawEffect)) {
          const raw = rawEffect as Record<string, unknown>;
          const counts: Record<string, number> = {};
          if (typeof raw.counts === "object" && raw.counts !== null && !Array.isArray(raw.counts)) {
            for (const [name, count] of Object.entries(raw.counts as Record<string, unknown>)) {
              if (typeof count === "number" && Number.isFinite(count) && count >= 0) {
                counts[name] = count;
              }
            }
          }
          effect = {
            status: typeof raw.status === "string" ? raw.status : "unknown",
            counts,
            source_observations: Array.isArray(raw.source_observations)
              ? raw.source_observations.filter((item): item is string => typeof item === "string")
              : [],
            internal_work: Array.isArray(raw.internal_work)
              ? raw.internal_work.filter((item): item is string => typeof item === "string")
              : [],
            next_owner_attention: typeof raw.next_owner_attention === "string"
              ? raw.next_owner_attention
              : undefined,
            reality_boundary: typeof raw.reality_boundary === "string"
              ? raw.reality_boundary
              : undefined,
          };
        }
      }
    } catch {
      stages = null;
      effect = null;
    }
  }
  const stateColor =
    cycle.status === "COMPLETED"
      ? "border-success/70"
      : cycle.status === "FAILED"
        ? "border-danger/70"
        : "border-warning/70";
  const noteColor =
    cycle.status === "PARTIAL"
      ? "text-warning"
      : cycle.status === "FAILED"
        ? "text-danger"
        : "text-muted";
  const effectColor =
    effect?.status === "source_data_collected"
      ? "text-success"
      : effect?.status === "internal_work_only" || effect?.status === "no_new_effect"
        ? "text-warning"
        : "text-muted";
  const humanize = (value: string) => value.replace(/_/g, " ");
  const visibleCounts = Object.entries(effect?.counts ?? {}).filter(([, count]) => count > 0);

  return (
    <article className={`rounded-card border-2 ${stateColor} bg-card p-4`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-extrabold">
          Run #{cycle.id} · {cycle.status}
        </p>
        <p className="text-sm text-muted">
          {displayTime(cycle.started_at)}
          {cycle.duration_ms != null ? ` · ${Math.round(cycle.duration_ms / 1000)}s` : ""}
        </p>
      </div>
      {cycle.error ? (
        <p className={`mt-1 break-words text-sm ${noteColor}`}>{cycle.error}</p>
      ) : null}

      {effect ? (
        <section className="mt-3 rounded-card border border-line bg-surface p-3" aria-label="Cycle effect">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-bold">Cycle effect</p>
            <p className={`text-sm font-extrabold capitalize ${effectColor}`}>
              {humanize(effect.status || "unknown")}
            </p>
          </div>
          {visibleCounts.length ? (
            <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
              {visibleCounts.map(([name, count]) => (
                <div key={name} className="flex justify-between gap-2">
                  <dt className="break-words text-muted">{humanize(name)}</dt>
                  <dd className="font-bold tabular-nums">{count}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-2 text-sm text-muted">No positive effect counts recorded.</p>
          )}
          {effect.next_owner_attention ? (
            <p className="mt-3 text-sm">
              <span className="font-bold">Next owner attention: </span>
              {humanize(effect.next_owner_attention)}
            </p>
          ) : null}
          {effect.reality_boundary ? (
            <p className="mt-2 text-xs leading-5 text-muted">{effect.reality_boundary}</p>
          ) : null}
        </section>
      ) : null}

      {stages ? (
        <dl className="mt-3 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
          {Object.entries(stages).map(([name, info]) => {
            const st = typeof info?.status === "string" ? info.status : "unknown";
            const dot =
              st === "ok"
                ? "text-success"
                : st === "error"
                  ? "text-danger"
                  : st === "partial" || st === "skipped"
                    ? "text-warning"
                    : "text-muted";
            return (
              <div key={name} className="flex justify-between gap-2">
                <dt className="break-all text-muted">{name}</dt>
                <dd className={`font-bold ${dot}`}>{st}</dd>
              </div>
            );
          })}
        </dl>
      ) : (
        <p className="mt-2 text-sm text-muted">
          Per-stage breakdown UNKNOWN — this run predates stage persistence.
        </p>
      )}
    </article>
  );
}

function PaymentFulfillmentQueue({ apiKey }: { apiKey: string }) {
  const [items, setItems] = useState<PaymentFulfillmentIntentView[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let current = true;
    if (!apiKey) {
      setItems(null);
      return () => { current = false; };
    }
    setLoading(true);
    setError("");
    ownerProjectionFetch<PaymentFulfillmentIntentView[]>("/api/payments/owner/fulfillment-queue", apiKey)
      .then((payload) => { if (current) setItems(Array.isArray(payload) ? payload : []); })
      .catch((cause) => {
        if (current) {
          setItems(null);
          setError(cause instanceof Error ? cause.message : "Payment fulfillment queue is unavailable.");
        }
      })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [apiKey, refresh]);

  async function confirmFulfillment(item: PaymentFulfillmentIntentView) {
    const confirmed = window.confirm(
      "Confirm that the purchased offer was actually delivered or fulfilled? This records verified REAL NPR revenue and a paid-customer event. Do not confirm merely because the provider reports payment.",
    );
    if (!confirmed) return;
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      await ownerCommandFetch(
        "/api/payments/owner/intents/" + item.id + "/fulfill",
        apiKey,
        { confirmed: true },
      );
      setNotice("Fulfillment confirmed for payment #" + item.id + ". The verified outcome and paid-customer event are now linked.");
      setRefresh((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Fulfillment could not be recorded.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="mt-6 rounded-card border-2 border-line p-4" aria-label="Payments awaiting fulfillment">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-extrabold">Provider-verified payments awaiting fulfillment</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
            A provider callback alone is not realized revenue. Confirm only after the promised service or deliverable was actually fulfilled.
          </p>
        </div>
        <button
          type="button"
          disabled={loading || busyId !== null}
          onClick={() => setRefresh((value) => value + 1)}
          className="min-h-10 rounded-card border border-line px-3 py-2 text-sm font-bold disabled:opacity-60"
        >
          Refresh
        </button>
      </div>
      {error ? <p role="alert" className="mt-3 rounded-card border border-danger/60 p-3 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="mt-3 rounded-card border border-line p-3 text-sm">{notice}</p> : null}
      {items === null ? (
        <p className="mt-3 text-sm text-muted">{loading ? "Loading owner-protected payment intents…" : "Payment fulfillment data is unavailable."}</p>
      ) : items.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No provider-verified payments currently await fulfillment. Pending or unverified transactions do not appear here.</p>
      ) : (
        <ul className="mt-4 grid gap-3">
          {items.map((item) => (
            <li key={item.id} className="rounded-card border border-line bg-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h4 className="font-extrabold">{item.product_name}</h4>
                  <p className="mt-1 text-sm text-muted">
                    Payment #{item.id} · {item.provider === "esewa" ? "eSewa" : "Khalti"} · provider status VERIFIED
                  </p>
                  {item.provider_reference ? <p className="mt-1 break-all text-xs text-muted">Provider reference: {item.provider_reference}</p> : null}
                  <p className="mt-2 font-display text-xl font-extrabold">NPR {item.amount_npr}</p>
                </div>
                <button
                  type="button"
                  disabled={busyId !== null || loading}
                  onClick={() => void confirmFulfillment(item)}
                  className="min-h-11 rounded-card border-2 border-accent px-4 py-2 text-sm font-bold text-accent disabled:opacity-60"
                >
                  {busyId === item.id ? "Recording fulfillment…" : "Confirm fulfilled"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


type OwnerControlStatusView = {
  safe_mode_enabled: boolean;
  safe_mode_reason: string | null;
  last_owner_contact_at_utc: string | null;
  owner_contact_stale: boolean | null;
  customer_sending_effective: "ON" | "OFF";
  active_stage: string;
  telegram_control_configured: boolean;
  telegram_digest_enabled: boolean;
  sms_digest_enabled: boolean;
  intake_enabled: boolean;
  public_checkout_enabled: boolean;
  note: string;
};

type OwnerControlAskView = {
  ask_ref: string;
  decision_ref: string;
  action_type: string;
  action_id: number | null;
  question: string;
  options: Array<{ key: string; label: string }>;
  high_impact: boolean;
  status: string;
  notification_status: string;
  code_expires_at_utc: string | null;
  expires_at_utc: string | null;
  answer_option: string | null;
};

async function ownerControlRequest<T>(
  path: string,
  ownerKey: string,
  method = "GET",
  body?: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      "X-API-Key": ownerKey,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Owner control request failed (" + response.status + ").";
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function OwnerControlPanel({ apiKey }: { apiKey: string }) {
  const [status, setStatus] = useState<OwnerControlStatusView | null>(null);
  const [asks, setAsks] = useState<OwnerControlAskView[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyAsk, setBusyAsk] = useState<string | null>(null);
  const [codes, setCodes] = useState<Record<string, string>>({});
  const [choices, setChoices] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    if (!apiKey.trim()) return;
    setLoading(true);
    setLoadError("");
    try {
      const [nextStatus, nextAsks] = await Promise.all([
        ownerControlRequest<OwnerControlStatusView>("/api/owner-control/status", apiKey),
        ownerControlRequest<OwnerControlAskView[]>("/api/owner-control/asks", apiKey),
      ]);
      if (!nextStatus || typeof nextStatus.safe_mode_enabled !== "boolean" || !Array.isArray(nextAsks)) {
        throw new Error("Owner control returned an unexpected response.");
      }
      setStatus(nextStatus);
      setAsks(nextAsks);
    } catch (cause) {
      setStatus(null);
      setAsks(null);
      setLoadError(cause instanceof Error ? cause.message : "Owner safety status is unavailable.");
    } finally {
      setLoading(false);
    }
  }, [apiKey]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submitAnswer(ask: OwnerControlAskView) {
    const code = (codes[ask.ask_ref] ?? "").trim();
    const option = (choices[ask.ask_ref] ?? "").trim();
    if (!code || !option) {
      setActionError("Enter the one-time code and choose an option before submitting.");
      return;
    }
    setBusyAsk(ask.ask_ref);
    setActionError("");
    setNotice("");
    try {
      const result = await ownerControlRequest<{
        status: string;
        ask_ref: string;
        option: string;
        safe_mode_enabled: boolean;
        action_executed: boolean;
      }>("/api/owner-control/asks/" + encodeURIComponent(ask.ask_ref) + "/answer", apiKey, "POST", {
        code,
        option,
      });
      setCodes((current) => ({ ...current, [ask.ask_ref]: "" }));
      setNotice(
        "Recorded " + result.option + " for " + result.ask_ref +
        (result.action_executed ? ". The API reports an execution; inspect the Action record." : ". No Action was executed automatically."),
      );
      await refresh();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "The decision could not be recorded.");
    } finally {
      setBusyAsk(null);
    }
  }

  async function requestResume() {
    setBusyAsk("resume");
    setActionError("");
    setNotice("");
    try {
      const result = await ownerControlRequest<{ ask_ref: string; high_impact: boolean; status: string }>(
        "/api/owner-control/resume/request", apiKey, "POST",
      );
      setNotice(
        "Resume review " + result.ask_ref + " was created. Enter its one-time code here after it arrives in the private Telegram chat. Clearing safe mode alone does not enable customer sending or other flags.",
      );
      await refresh();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Resume review could not be requested.");
    } finally {
      setBusyAsk(null);
    }
  }

  if (!apiKey.trim()) return null;

  return (
    <section aria-label="Owner safety and decisions" className="mt-6 rounded-2xl border-2 border-line bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-accent">Owner control</p>
          <h2 className="mt-1 text-xl font-extrabold">Safety state &amp; pending decisions</h2>
          <p className="mt-1 max-w-3xl text-sm leading-5 text-muted">
            The persistent safety gate and one-time ASK approvals. Configuration is not delivery proof; this panel never executes an Action itself.
          </p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading} className="min-h-10 rounded-card border border-line px-3 py-2 text-sm font-bold disabled:opacity-60">
          {loading ? "Refreshing…" : "Refresh safety"}
        </button>
      </div>

      {loadError ? <p role="alert" className="mt-4 rounded-card border border-danger/70 bg-danger/10 p-3 text-sm">{loadError}</p> : null}
      {!status ? (
        <p className="mt-4 rounded-card border border-line p-3 text-sm text-muted">
          Safety state is not verified yet. Refresh after owner authentication; an unavailable read must not be interpreted as safe or live.
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <article className={"rounded-xl border-2 p-3 " + (status.safe_mode_enabled ? "border-danger/70 bg-danger/10" : "border-line bg-background")}>
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Persistent safe mode</p>
              <p className="mt-1 text-xl font-extrabold">{status.safe_mode_enabled ? "ON" : "OFF"}</p>
              <p className="mt-1 break-words text-xs leading-5 text-muted">Reason: {status.safe_mode_reason ?? "not recorded"}</p>
            </article>
            <article className="rounded-xl border-2 border-line bg-background p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Generic customer sending</p>
              <p className="mt-1 text-xl font-extrabold">{status.customer_sending_effective}</p>
              <p className="mt-1 text-xs leading-5 text-muted">Email/SMS delivery gate only; does not describe every possible integration.</p>
            </article>
            <article className="rounded-xl border-2 border-line bg-background p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Last owner contact</p>
              <p className="mt-1 text-sm font-bold">{displayTime(status.last_owner_contact_at_utc)}</p>
              <p className="mt-1 text-xs leading-5 text-muted">{status.owner_contact_stale === null ? "Freshness UNKNOWN" : status.owner_contact_stale ? "Stale — safe mode should stay on" : "Within the 7-day window"}</p>
            </article>
            <article className="rounded-xl border-2 border-line bg-background p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Telegram control</p>
              <p className="mt-1 text-lg font-extrabold">{status.telegram_control_configured ? "Configured" : "OFF / incomplete"}</p>
              <p className="mt-1 text-xs leading-5 text-muted">Secrets and owner IDs are never shown. Configured does not mean a handset received a message.</p>
            </article>
            <article className="rounded-xl border-2 border-line bg-background p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Digest delivery</p>
              <p className="mt-1 text-sm font-bold">Telegram {status.telegram_digest_enabled ? "enabled by configuration" : "OFF"} · SMS {status.sms_digest_enabled ? "enabled by configuration" : "OFF"}</p>
              <p className="mt-1 text-xs leading-5 text-muted">No delivery is asserted by this setting alone.</p>
            </article>
            <article className="rounded-xl border-2 border-line bg-background p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Other public gates</p>
              <p className="mt-1 text-sm font-bold">Intake {status.intake_enabled ? "ON" : "OFF"} · Checkout {status.public_checkout_enabled ? "ON" : "OFF"}</p>
              <p className="mt-1 text-xs leading-5 text-muted">Active stage: {status.active_stage}</p>
            </article>
          </div>
          {status.owner_contact_stale ? (
            <p role="status" className="mt-3 rounded-card border border-warning/70 bg-warning/10 p-3 text-sm">
              Owner contact is at least seven days old or has not yet been recorded. The safety gate remains active until the state is reviewed.
            </p>
          ) : null}
          {status.safe_mode_enabled && status.telegram_control_configured ? (
            <div className="mt-4">
              <button type="button" onClick={() => void requestResume()} disabled={busyAsk !== null} className="min-h-11 rounded-card border-2 border-accent px-4 py-2 text-sm font-bold text-accent disabled:opacity-60">
                {busyAsk === "resume" ? "Creating request…" : "Request safe-mode review"}
              </button>
              <p className="mt-1 text-xs leading-5 text-muted">This sends a high-impact ASK to the configured private Telegram chat. Resuming requires this authenticated console and the one-time code; it does not turn other flags on.</p>
            </div>
          ) : null}
        </>
      )}

      {notice ? <p role="status" className="mt-4 rounded-card border border-success/70 bg-success/10 p-3 text-sm">{notice}</p> : null}
      {actionError ? <p role="alert" className="mt-4 rounded-card border border-danger/70 bg-danger/10 p-3 text-sm">{actionError}</p> : null}

      <div className="mt-5 border-t border-line pt-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="font-extrabold">Owner decision requests</h3>
            <p className="mt-1 text-sm leading-5 text-muted">One-time codes are entered here only for console approvals. High-impact decisions cannot be approved in Telegram alone.</p>
          </div>
          <span className="rounded-full border border-line px-3 py-1 text-xs font-semibold">{asks ? asks.filter((ask) => ask.status === "OPEN").length : "UNKNOWN"} open</span>
        </div>
        {asks === null ? (
          <p className="mt-3 text-sm text-muted">Decision queue unavailable; it is not assumed to be empty.</p>
        ) : asks.length === 0 ? (
          <p className="mt-3 rounded-card border border-line p-3 text-sm text-muted">No recent decision requests are recorded.</p>
        ) : (
          <ul className="mt-3 grid gap-3">
            {asks.map((ask) => (
              <li key={ask.ask_ref} className="rounded-xl border-2 border-line p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h4 className="font-bold">{ask.question}</h4>
                    <p className="mt-1 text-xs text-muted">{ask.ask_ref} · {ask.decision_ref} · {ask.action_type}</p>
                  </div>
                  <span className="rounded-full border border-line px-2 py-1 text-xs font-bold">{ask.high_impact ? "HIGH IMPACT" : "ROUTINE"} · {ask.status}</span>
                </div>
                {ask.status === "OPEN" ? (
                  <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); void submitAnswer(ask); }}>
                    <label className="grid gap-1 text-sm font-semibold">
                      One-time code
                      <input type="password" autoComplete="off" spellCheck={false} value={codes[ask.ask_ref] ?? ""} onChange={(event) => setCodes((current) => ({ ...current, [ask.ask_ref]: event.target.value }))} className="min-h-11 min-w-0 rounded-card border-2 border-line bg-background px-3 text-base" required />
                    </label>
                    <label className="grid gap-1 text-sm font-semibold">
                      Decision
                      <select value={choices[ask.ask_ref] ?? ""} onChange={(event) => setChoices((current) => ({ ...current, [ask.ask_ref]: event.target.value }))} className="min-h-11 min-w-0 rounded-card border-2 border-line bg-background px-3 text-base" required>
                        <option value="" disabled>Select an option</option>
                        {ask.options.map((option) => <option key={option.key} value={option.key}>{option.key} — {option.label}</option>)}
                      </select>
                    </label>
                    <div className="sm:col-span-2">
                      <button type="submit" disabled={busyAsk !== null || !(codes[ask.ask_ref] ?? "").trim() || !(choices[ask.ask_ref] ?? "").trim()} className="min-h-11 rounded-card border-2 border-accent px-4 py-2 text-sm font-bold text-accent disabled:opacity-60">
                        {busyAsk === ask.ask_ref ? "Recording decision…" : "Record decision — no automatic execution"}
                      </button>
                      {ask.high_impact ? <p className="mt-2 text-xs leading-5 text-muted">High-impact: this authenticated owner console and the unexpired code are both required.</p> : <p className="mt-2 text-xs leading-5 text-muted">A routine decision can alternatively be submitted to Telegram as a new, unforwarded message. This form never runs an Action.</p>}
                    </div>
                  </form>
                ) : (
                  <p className="mt-2 text-sm text-muted">Status: {ask.status}{ask.answer_option ? " · recorded option: " + ask.answer_option : ""}{ask.notification_status ? " · notification: " + ask.notification_status : ""}</p>
                )}
                <p className="mt-2 text-xs text-muted">Code expires: {displayTime(ask.code_expires_at_utc)} · Request expires: {displayTime(ask.expires_at_utc)}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function OwnerConsolePage() {
  const [key, setKey] = useState("");
  const [consoleState, setConsoleState] = useState<OwnerConsoleState | null>(null);
  const [selected, setSelected] = useState<LeadDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [evidenceReference, setEvidenceReference] = useState("");
  const [outcomeNote, setOutcomeNote] = useState("");
  const [intel, setIntel] = useState<IntelligenceState | null>(null);
  const [globalFrontier, setGlobalFrontier] = useState<GlobalFrontierView | null>(null);
  const [globalFrontierError, setGlobalFrontierError] = useState<string | null>(null);
  const [globalFrontierLoading, setGlobalFrontierLoading] = useState(false);
  const [expandedTaskId, setExpandedTaskId] = useState<number | null>(null);
  const [taskHistoryById, setTaskHistoryById] = useState<Record<number, TaskHistoryState>>({});
  const taskHistoryRequestId = useRef(0);
  const [commercial, setCommercial] = useState<CommercialState>({
    products: null,
    error: null,
  });
  const [orchestrationOverview, setOrchestrationOverview] = useState<OrchestratorOverviewView | null>(null);
  const [orchestrationError, setOrchestrationError] = useState<string | null>(null);
  const [channels, setChannels] = useState<ChannelSummaryView[] | null>(null);
  const [channelsError, setChannelsError] = useState<string | null>(null);
  const [paymentConfiguration, setPaymentConfiguration] = useState<PaymentConfigurationView | null>(null);
  const [paymentConfigurationError, setPaymentConfigurationError] = useState<string | null>(null);
  const [productPricingDrafts, setProductPricingDrafts] = useState<Record<number, string>>({});
  const [productLifecycleBusyId, setProductLifecycleBusyId] = useState<number | null>(null);
  const [productLifecycleError, setProductLifecycleError] = useState("");
  const [productLifecycleNotice, setProductLifecycleNotice] = useState("");
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<number | null>(null);
  const [orchestratorDetail, setOrchestratorDetail] = useState<OrchestratorFlowDetailView | null>(null);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [pipelineError, setPipelineError] = useState("");
  const [pipelineNotice, setPipelineNotice] = useState("");
  const [outcomeActual, setOutcomeActual] = useState("");
  const [outcomeSuccess, setOutcomeSuccess] = useState<"unknown" | "yes" | "no">("unknown");
  const [outcomeRespondents, setOutcomeRespondents] = useState("");

  const cycleOperations = intel?.runtime?.truth?.operations;

  async function refresh(ownerKey = key) {
    taskHistoryRequestId.current += 1;
    setExpandedTaskId(null);
    setTaskHistoryById({});
    const [readiness, leads] = await Promise.all([
      ownerFetch<Readiness>("owner/readiness", ownerKey),
      ownerFetch<Lead[]>("owner/leads", ownerKey),
    ]);
    setConsoleState({ readiness, leads });

    // Read only the product summary endpoint. The consolidated pipeline also
    // returns customer-event contact data, which this visibility panel does
    // not need and therefore must not fetch into browser memory.
    try {
      const response = await fetch("/api/products", {
        headers: { "X-API-Key": ownerKey },
      });
      if (response.status === 401) {
        throw new Error("Owner authentication failed. Check the key and try again.");
      }
      if (!response.ok) {
        throw new Error(`Product visibility request failed (${response.status}).`);
      }
      const payload: unknown = await response.json();
      if (!Array.isArray(payload)) {
        throw new Error("Product visibility returned an unexpected response.");
      }
      setCommercial({ products: payload as ProductSummaryView[], error: null });
    } catch (cause) {
      setCommercial({
        products: null,
        error: cause instanceof Error ? cause.message : "Product visibility is unavailable.",
      });
    }

    // Read a PII-free view of the canonical orchestrator; do not load customer-event rows.
    try {
      const payload = await ownerProjectionFetch<OrchestratorOverviewView>(
        "/api/orchestrate/overview?limit=25&data_scope=REAL",
        ownerKey,
      );
      if (!payload || !Array.isArray(payload.flow) || !payload.pipeline) {
        throw new Error("Orchestrator overview returned an unexpected response.");
      }
      setOrchestrationOverview(payload);
      setOrchestrationError(null);
    } catch (cause) {
      setOrchestrationOverview(null);
      setOrchestrationError(cause instanceof Error ? cause.message : "Orchestrator overview is unavailable.");
    }

    // Channel rollups are safe to display; do not fetch /products/pipeline because it includes contact records.
    try {
      const payload = await ownerProjectionFetch<unknown>("/api/products/channels", ownerKey);
      if (!Array.isArray(payload)) {
        throw new Error("Distribution channel visibility returned an unexpected response.");
      }
      setChannels(payload as ChannelSummaryView[]);
      setChannelsError(null);
    } catch (cause) {
      setChannels(null);
      setChannelsError(cause instanceof Error ? cause.message : "Distribution channel visibility is unavailable.");
    }

    // Configuration-only status does not contact eSewa/Khalti or assert a successful payment.
    try {
      const payload = await ownerProjectionFetch<PaymentConfigurationView>("/api/payments/status", ownerKey);
      if (!payload || payload.scope !== "configuration_only" || !payload.providers) {
        throw new Error("Payment configuration returned an unexpected response.");
      }
      setPaymentConfiguration(payload);
      setPaymentConfigurationError(null);
    } catch (cause) {
      setPaymentConfiguration(null);
      setPaymentConfigurationError(cause instanceof Error ? cause.message : "Payment configuration is unavailable.");
    }

    if (selected) {
      const updated = leads.find((lead) => lead.reference === selected.reference);
      if (!updated) setSelected(null);
    }
    // Load this projection independently: an unavailable intelligence/cycle endpoint
    // must not hide the frontier or convert a failed read into an empty world.
    await refreshGlobalFrontier(ownerKey);

    // Intelligence section: best-effort loads against /api/forge/*. A 404
    // (backend predates the endpoint) yields null -> UNKNOWN in the UI.
    // A 401 propagates like the rest of the console.
    try {
      const [runtime, cycles, questions, tasks, clearance] = await Promise.all([
        forgeFetch<RuntimeWindow>("runtime", ownerKey),
        forgeFetch<CycleSummary[]>("cycles?limit=5", ownerKey),
        forgeFetch<ResearchQuestionRow[]>("questions?status=open", ownerKey),
        forgeFetch<ResearchTaskRow[]>("tasks", ownerKey),
        forgeFetch<{ as_of: string; sources: ClearanceEntry[] }>("clearance", ownerKey),
      ]);
      setIntel({ runtime, cycles, questions, tasks, clearance });
    } catch (cause) {
      // Intelligence is additive; a failure here must not hide readiness/leads.
      setIntel(null);
      throw cause;
    }

  }

  async function refreshGlobalFrontier(ownerKey = key) {
    setGlobalFrontierLoading(true);
    try {
      const payload = await ownerProjectionFetch<GlobalFrontierView>(
        "/api/forge/substrate/discovery/frontier?limit=40",
        ownerKey,
      );
      if (!payload || !Array.isArray(payload.items) || typeof payload.candidate_count_scanned !== "number") {
        throw new Error("Global frontier returned an unexpected response.");
      }
      setGlobalFrontier(payload);
      setGlobalFrontierError(null);
    } catch (cause) {
      setGlobalFrontier(null);
      setGlobalFrontierError(cause instanceof Error ? cause.message : "Global frontier is unavailable.");
    } finally {
      setGlobalFrontierLoading(false);
    }
  }

  async function toggleTaskHistory(taskId: number) {
    if (expandedTaskId === taskId) {
      taskHistoryRequestId.current += 1;
      setExpandedTaskId(null);
      return;
    }

    const requestId = ++taskHistoryRequestId.current;
    setExpandedTaskId(taskId);
    setTaskHistoryById((current) => ({
      ...current,
      [taskId]: { status: "loading" },
    }));

    try {
      const events = await forgeFetch<ResearchTaskEventRow[]>(`tasks/${taskId}/history`, key);
      if (requestId !== taskHistoryRequestId.current) return;
      if (events === null) {
        setTaskHistoryById((current) => ({
          ...current,
          [taskId]: { status: "unavailable" },
        }));
        return;
      }
      if (!Array.isArray(events)) {
        setTaskHistoryById((current) => ({
          ...current,
          [taskId]: { status: "error", message: "The history response was not a list." },
        }));
        return;
      }
      setTaskHistoryById((current) => ({
        ...current,
        [taskId]: { status: "loaded", events },
      }));
    } catch (cause) {
      if (requestId !== taskHistoryRequestId.current) return;
      setTaskHistoryById((current) => ({
        ...current,
        [taskId]: {
          status: "error",
          message: cause instanceof Error ? cause.message : "Task history could not be loaded.",
        },
      }));
    }
  }

  async function unlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await refresh(key);
    } catch (cause) {
      setConsoleState(null);
      setCommercial({ products: null, error: null });
      setOrchestrationOverview(null);
      setOrchestrationError(null);
      setChannels(null);
      setChannelsError(null);
      setPaymentConfiguration(null);
      setPaymentConfigurationError(null);
      setError(cause instanceof Error ? cause.message : "Owner access is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  async function refreshWorkbench() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await refresh(key);
      setNotice("Read-only refresh finished. Check each section for UNKNOWN or unavailable-source labels.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The owner snapshot could not be refreshed.");
    } finally {
      setBusy(false);
    }
  }

  async function loadLead(reference: string) {
    setError("");
    try {
      setSelected(await ownerFetch<LeadDetail>(`owner/leads/${encodeURIComponent(reference)}`, key));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The inquiry could not be loaded.");
    }
  }

  async function runProductLifecycleAction(product: ProductSummaryView, action: "prepare" | "approve" | "publish" | "pause") {
    if (productLifecycleBusyId !== null) return;
    if (action === "approve" && !window.confirm("Approve the prepared offer brief and exact one-time NPR price? This approves the offer for launch review; it does not publish it or collect money.")) return;
    if (action === "publish" && !window.confirm("Publish this product offer publicly? The API will re-check verified demand, approval, and the exact NPR price. This action does not initiate a payment.")) return;
    if (action === "pause" && !window.confirm("Pause the public offer? Its public approval will be removed.")) return;
    setProductLifecycleBusyId(product.id);
    setProductLifecycleError("");
    setProductLifecycleNotice("");
    try {
      if (action === "prepare") {
        const draftPrice = productPricingDrafts[product.id] ?? product.pricing ?? "";
        if (draftPrice !== (product.pricing ?? "")) {
          await ownerProductRequest("/api/products/" + product.id, "PATCH", key, { pricing: draftPrice });
        }
        await ownerProductRequest("/api/products/" + product.id + "/prepare-offer-review", "POST", key);
        setProductLifecycleNotice("Review brief prepared on Product #" + product.id + ". No duplicate product was created; it is pending owner approval.");
      } else if (action === "approve") {
        await ownerProductRequest("/api/products/" + product.id + "/offer-approval", "POST", key, { status: "APPROVED", note: "Explicit owner approval through the private /owner console." });
        setProductLifecycleNotice("Offer terms approved. Publication still requires verified demand and the exact one-time NPR contract.");
      } else if (action === "publish") {
        await ownerProductRequest("/api/products/" + product.id, "PATCH", key, { status: "launched", launch_state: "public" });
        setProductLifecycleNotice("Product offer published. This does not mean a payment occurred or revenue was collected.");
      } else {
        await ownerProductRequest("/api/products/" + product.id + "/offer-approval", "POST", key, { status: "NEEDS_EDIT", note: "Owner paused the offer from the private /owner console." });
        setProductLifecycleNotice("Offer paused; its approval must be reviewed again before republication.");
      }
      const products = await ownerProjectionFetch<ProductSummaryView[]>("/api/products", key);
      setCommercial({ products, error: null });
      setProductPricingDrafts((previous) => { const next = { ...previous }; delete next[product.id]; return next; });
    } catch (cause) {
      setProductLifecycleError(cause instanceof Error ? cause.message : "Product lifecycle action failed.");
    } finally {
      setProductLifecycleBusyId(null);
    }
  }
  async function openOpportunityPipeline(opportunityId: number) {
    setPipelineBusy(true);
    setPipelineError("");
    setPipelineNotice("");
    setSelectedOpportunityId(opportunityId);
    setOrchestratorDetail(null);
    try {
      const detail = await ownerProjectionFetch<OrchestratorFlowDetailView>(
        "/api/orchestrate/flow/" + opportunityId + "?data_scope=REAL",
        key,
      );
      setOrchestratorDetail(detail);
      setOutcomeActual("");
      setOutcomeSuccess("unknown");
      setOutcomeRespondents("");
    } catch (cause) {
      setPipelineError(cause instanceof Error ? cause.message : "The opportunity detail could not be loaded.");
    } finally {
      setPipelineBusy(false);
    }
  }

  async function runPipelineAction(
    action: "advance" | "approve" | "execute" | "reject" | "outcome" | "product" | "next-decision",
    body?: Record<string, unknown>,
    confirmation?: string,
    successMessage = "Pipeline action recorded.",
  ) {
    if (selectedOpportunityId === null) return;
    if (confirmation && !window.confirm(confirmation)) return;
    setPipelineBusy(true);
    setPipelineError("");
    setPipelineNotice("");
    const id = selectedOpportunityId;
    const path = action === "advance"
      ? "/api/orchestrate/" + id + "/advance?data_scope=REAL&x_interviews=10&y_confirm=5&z_willing=3"
      : "/api/orchestrate/" + id + "/" + action + "?data_scope=REAL";
    let message = successMessage;
    try {
      const result = await ownerCommandFetch<Record<string, unknown>>(path, key, body);
      if (action === "product") {
        if (result.status === "not_validated") {
          message = "Product gate not met: " + (typeof result.reason === "string" ? result.reason : "the recorded evidence does not meet the demand threshold.");
        } else if (result.status === "created") {
          message = "Product record #" + String(result.product_id ?? "UNKNOWN") + " created from validated demand. This does not launch it, initiate checkout, or record revenue.";
        } else if (result.status === "exists") {
          message = "A product record already exists for this opportunity (#" + String(result.product_id ?? "UNKNOWN") + ").";
        }
      }
      if (action === "outcome") {
        setOutcomeActual("");
        setOutcomeSuccess("unknown");
        setOutcomeRespondents("");
      }
      setPipelineNotice(message);
    } catch (cause) {
      setPipelineError(cause instanceof Error ? cause.message : "The pipeline action failed.");
      setPipelineBusy(false);
      return;
    }

    const refreshWarnings: string[] = [];
    try {
      const overview = await ownerProjectionFetch<OrchestratorOverviewView>(
        "/api/orchestrate/overview?limit=25&data_scope=REAL", key,
      );
      setOrchestrationOverview(overview);
      setOrchestrationError(null);
    } catch (cause) {
      refreshWarnings.push("opportunity summary could not refresh");
      setOrchestrationError(cause instanceof Error ? cause.message : "Orchestrator overview is unavailable.");
    }
    try {
      const products = await ownerProjectionFetch<ProductSummaryView[]>("/api/products", key);
      setCommercial({ products, error: null });
    } catch (cause) {
      refreshWarnings.push("product summary could not refresh");
      setCommercial({ products: null, error: cause instanceof Error ? cause.message : "Product visibility is unavailable." });
    }
    try {
      const refreshedChannels = await ownerProjectionFetch<ChannelSummaryView[]>("/api/products/channels", key);
      setChannels(refreshedChannels);
      setChannelsError(null);
    } catch (cause) {
      refreshWarnings.push("distribution summary could not refresh");
      setChannelsError(cause instanceof Error ? cause.message : "Distribution channel visibility is unavailable.");
    }
    try {
      const detail = await ownerProjectionFetch<OrchestratorFlowDetailView>(
        "/api/orchestrate/flow/" + id + "?data_scope=REAL", key,
      );
      setOrchestratorDetail(detail);
    } catch (cause) {
      refreshWarnings.push("opportunity detail could not refresh");
      setPipelineError(cause instanceof Error ? cause.message : "Opportunity detail is unavailable.");
    }
    if (refreshWarnings.length) setPipelineNotice(message + " Refresh warning: " + refreshWarnings.join(", ") + ".");
    setPipelineBusy(false);
  }

  async function submitPipelineOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedOpportunityId === null) return;
    if (!outcomeActual.trim()) {
      setPipelineError("Enter the outcome you personally recorded before saving.");
      return;
    }
    try {
      const respondents = parseOutcomeRespondents(outcomeRespondents);
      await runPipelineAction(
        "outcome",
        {
          actual: outcomeActual.trim(),
          ...(outcomeSuccess === "yes" ? { success: true } : outcomeSuccess === "no" ? { success: false } : {}),
          source: "owner_recorded_interview",
          conversions: respondents.conversions,
          contacts: respondents.contacts,
          data_scope: "REAL",
        },
        undefined,
        "Owner-reported outcome saved as MOCK/REPORTED; it is not verified REAL evidence, payment, or revenue, and does not unlock the product gate by itself.",
      );
    } catch (cause) {
      setPipelineError(cause instanceof Error ? cause.message : "The respondent notes could not be validated.");
    }
  }

  async function runAction(
    path: string,
    body?: Record<string, string>,
    method = "POST",
    successMessage = "Inquiry updated.",
  ) {
    if (!selected) return;
    const reference = selected.reference;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await ownerFetch(
        `owner/leads/${encodeURIComponent(reference)}${path}`,
        key,
        { method, ...(body ? { body: JSON.stringify(body) } : {}) },
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The inquiry could not be updated.");
      setBusy(false);
      return;
    }
    // The milestone is recorded at this point: server-side transitions are
    // stage-guarded (409 on mismatch), so retrying this step is safe. From
    // here on, a failure only means the view could not refresh — it never
    // means the record failed, and the message must not say so.
    try {
      await refresh();
      if (method === "DELETE") {
        setSelected(null);
      } else {
        await loadLead(reference);
      }
      setEvidenceReference("");
      setOutcomeNote("");
      setNotice(successMessage);
    } catch {
      setNotice(
        `${successMessage} The console could not refresh — reload to see the latest state.`,
      );
    } finally {
      setBusy(false);
    }
  }

  async function sendTestEmail() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await ownerFetch<{ status: string }>(
        "owner-notification/test-send",
        key,
        { method: "POST" },
      );
      await refresh();
      setNotice(
        result.status === "sent"
          ? "The one-shot test message was accepted by the configured mail server."
          : "The one-shot test message was not accepted. Check the mail configuration and delivery queue.",
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The test message could not be sent.");
    } finally {
      setBusy(false);
    }
  }

  function lockConsole() {
    taskHistoryRequestId.current += 1;
    setExpandedTaskId(null);
    setTaskHistoryById({});
    setKey("");
    setConsoleState(null);
    setSelected(null);
    setIntel(null);
    setCommercial({ products: null, error: null });
    setOrchestrationOverview(null);
    setOrchestrationError(null);
    setChannels(null);
    setChannelsError(null);
    setPaymentConfiguration(null);
    setPaymentConfigurationError(null);
    setSelectedOpportunityId(null);
    setOrchestratorDetail(null);
    setPipelineBusy(false);
    setPipelineError("");
    setPipelineNotice("");
    setOutcomeActual("");
    setOutcomeSuccess("unknown");
    setOutcomeRespondents("");
    setNotice("");
    setError("");
  }

  const readiness = consoleState?.readiness;
  const heartbeatState: "green" | "amber" | "red" =
    readiness?.last_maintenance_age_seconds == null
      ? "amber"
      : readiness.last_maintenance_age_seconds > 26 * 60 * 60
        ? "red"
        : readiness.last_maintenance_age_seconds > 24 * 60 * 60
          ? "amber"
          : "green";
  const emailQueueState: "green" | "amber" | "red" =
    !readiness?.oldest_unsent_or_failed_owner_email_at
      ? "green"
      : Date.now() -
          new Date(readiness.oldest_unsent_or_failed_owner_email_at).getTime() >
        24 * 60 * 60 * 1000
        ? "red"
        : "amber";
  const realProducts = (commercial.products ?? []).filter((p) => p.data_scope === "REAL");
  const sandboxProducts = (commercial.products ?? []).filter((p) => p.data_scope === "SANDBOX");
  const launchedProducts = realProducts.filter(
    (p) =>
      ["launched", "iterating"].includes(p.status) &&
      ["piloting", "public"].includes(p.launch_state ?? ""),
  ).length;
  const realLeads = realProducts.reduce((sum, p) => sum + p.lead_count, 0);
  const recordedRealCustomers = realProducts.reduce((sum, p) => sum + p.actual_customers, 0);
  const recordedRealRevenue = realProducts.reduce((sum, p) => sum + p.actual_revenue, 0);
  const recordedRealNprRevenue = realProducts.every((p) => typeof p.actual_revenue_by_currency?.NPR === "number" && Number.isFinite(p.actual_revenue_by_currency?.NPR))
    ? realProducts.reduce((sum, p) => sum + (p.actual_revenue_by_currency?.NPR ?? 0), 0)
    : undefined;
  const recordedSandboxRevenue = sandboxProducts.reduce((sum, p) => sum + p.actual_revenue, 0);
  const recordedSandboxNprRevenue = sandboxProducts.every((p) => typeof p.actual_revenue_by_currency?.NPR === "number" && Number.isFinite(p.actual_revenue_by_currency?.NPR))
    ? sandboxProducts.reduce((sum, p) => sum + (p.actual_revenue_by_currency?.NPR ?? 0), 0)
    : undefined;

  return (
    <main className="flex-1">
      <Container className="py-8 sm:py-12">
        <div className="mx-auto max-w-5xl">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
            <BrandMark tone="light" />
            <span className="inline-flex min-h-10 items-center gap-2 rounded-full border border-line px-3 py-2 text-xs font-semibold text-muted">
              <span className="size-2 rounded-full bg-success" aria-hidden="true" />
              Private owner workspace
            </span>
          </div>
          <p className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Owner tools · key-protected data
          </p>
          <h1 className="mt-2 text-title">Your Hami workspace</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
            This is your private place to see what Hami knows and talk with ForgeBot.
            You do not need to manage the technical details. Enter your owner key to begin;
            it stays in this page session and is never shown back to you.
          </p>

          {!consoleState || !readiness ? (
            <form onSubmit={unlock} className="mt-6 grid max-w-xl gap-3 rounded-card border-2 border-line bg-card p-5">
              <label htmlFor="owner-key" className="font-bold">Owner key</label>
              <input
                id="owner-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={key}
                onChange={(event) => setKey(event.target.value)}
                className="min-h-12 min-w-0 rounded-card border-2 border-line bg-black px-3 text-base text-ink"
                required
              />
              <button type="submit" disabled={busy} className="min-h-12 rounded-card border-2 border-accent bg-accent px-4 font-extrabold text-black disabled:opacity-60">
                {busy ? "Checking access…" : "Open owner console"}
              </button>
            </form>
          ) : (
            <div className="mt-6">
              <section aria-label="Welcome to Hami" className="mb-5 rounded-2xl border border-line bg-card p-5 sm:p-7">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-accent">Your private workspace</p>
                <h2 className="mt-2 max-w-2xl text-2xl font-extrabold leading-tight sm:text-3xl">Let's work through Hami together.</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
                  Start by asking ForgeBot a question in your own words. It can explain what Hami has recorded,
                  what is still unclear, and what would be useful to investigate next. You can ignore the technical tools unless you need them.
                </p>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-line bg-background p-4">
                    <p className="text-sm font-semibold text-muted">New inquiry records · last 24 hours</p>
                    <p className="mt-1 text-3xl font-extrabold tabular-nums">{readiness.new_leads_last_24h}</p>
                    <p className="mt-1 text-xs leading-5 text-muted">These are stored inquiry records, not confirmed customers or sales.</p>
                  </div>
                  <div className="rounded-xl border border-line bg-background p-4">
                    <p className="text-sm font-semibold text-muted">Can someone submit a request right now?</p>
                    <p className="mt-1 text-xl font-extrabold">{readiness.intake_enabled ? "Requests are enabled" : "Public requests are closed"}</p>
                    <p className="mt-1 text-xs leading-5 text-muted">This reflects the current setting; it does not claim a request was received.</p>
                  </div>
                </div>
              </section>

              <OwnerControlPanel apiKey={key} />

              <section id="forgebot-workspace" className="scroll-mt-24" aria-label="Talk to ForgeBot">
                <ForgeConsoleWidgets apiKey={key} />
              </section>

              <details id="more-owner-tools" className="mt-8 rounded-2xl border border-line bg-card p-4 sm:p-5">
                <summary className="cursor-pointer list-none">
                  <span className="flex flex-wrap items-center justify-between gap-3">
                    <span>
                      <span className="block text-base font-extrabold">More owner tools</span>
                      <span className="mt-1 block text-sm font-normal text-muted">Research, requests, products, payments and technical status. Optional — you can leave this closed.</span>
                    </span>
                    <span className="rounded-full border border-line px-3 py-2 text-sm font-semibold">Open tools</span>
                  </span>
                </summary>
                <div className="mt-5">
              <nav aria-label="More owner tools" className="mb-5 flex flex-wrap gap-2 rounded-card border border-line bg-background p-3">
                <a href="#hami-frontier" className="inline-flex min-h-10 items-center rounded-card border border-line px-3 text-sm font-semibold">Research and discoveries</a>
                <a href="#hami-intelligence" className="inline-flex min-h-10 items-center rounded-card border border-line px-3 text-sm font-semibold">Hami activity</a>
                <a href="#owner-inquiries" className="inline-flex min-h-10 items-center rounded-card border border-line px-3 text-sm font-semibold">Requests</a>
                <a href="#owner-products-payments" className="inline-flex min-h-10 items-center rounded-card border border-line px-3 text-sm font-semibold">Products &amp; payments</a>
                <button type="button" onClick={() => void refreshWorkbench()} disabled={busy} className="inline-flex min-h-10 items-center rounded-card border border-line px-3 text-sm font-semibold disabled:opacity-50">
                  {busy ? "Refreshing…" : "Refresh status"}
                </button>
              </nav>

              <section aria-label="Current Hami snapshot" className="mb-8 rounded-card border-2 border-accent/50 bg-card p-4 sm:p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-extrabold">Current Hami snapshot</h2>
                    <p className="mt-1 max-w-3xl text-sm leading-5 text-muted">
                      Read-only values returned by existing owner APIs. Missing data stays UNKNOWN or unavailable; it is not converted to zero.
                    </p>
                  </div>
                  <span className="rounded-full border border-line px-3 py-1 text-xs font-semibold text-muted">Live read · no actions executed</span>
                </div>
                <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <div className="min-w-0 rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">Inquiry records created · last 24 hours</dt>
                    <dd className="mt-1 text-2xl font-extrabold">{readiness.new_leads_last_24h}</dd>
                    <p className="mt-1 text-xs leading-5 text-muted">Records only; not confirmed people, conversions, or recovered sales.</p>
                  </div>
                  <div className="min-w-0 rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">Stored inquiry evidence classes</dt>
                    <dd className="mt-1 text-2xl font-extrabold">REAL {readiness.lead_counts_by_evidence_class.REAL} · TEST {readiness.lead_counts_by_evidence_class.TEST}</dd>
                    <p className="mt-1 text-xs leading-5 text-muted">Stored labels, not independent proof that a transaction occurred.</p>
                  </div>
                  <div className="min-w-0 rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">Intake / LIVE flags</dt>
                    <dd className="mt-1 text-lg font-extrabold">Intake {readiness.intake_enabled ? "ON" : "OFF"} · LIVE {readiness.live_enabled ? "ON" : "OFF"}</dd>
                    <p className="mt-1 text-xs leading-5 text-muted">Configuration flags only; they do not prove a message was sent.</p>
                  </div>
                  <div className="min-w-0 rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">Recorded open research questions</dt>
                    <dd className="mt-1 text-2xl font-extrabold">{intel === null || intel.questions === null ? "UNKNOWN" : intel.questions.length}</dd>
                    <p className="mt-1 text-xs leading-5 text-muted">Current owner-only question endpoint; not an exhaustive map of reality.</p>
                  </div>
                  <div className="min-w-0 rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">Last recorded intelligence cycle</dt>
                    <dd className="mt-1 break-words text-sm font-extrabold">
                      {intel === null || intel.runtime === null
                        ? "UNKNOWN"
                        : intel.runtime.cycles.last
                          ? (intel.runtime.cycles.last.status || "STATUS UNKNOWN") + " · " + displayTime(intel.runtime.cycles.last.started_at)
                          : "No cycle recorded"}
                    </dd>
                    <p className="mt-1 text-xs leading-5 text-muted">A stored cycle does not prove a real-world action or outcome occurred.</p>
                  </div>
                  <div className="min-w-0 rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">Recorded-work frontier scan</dt>
                    <dd className="mt-1 break-words text-sm font-extrabold">
                      {globalFrontierLoading
                        ? "Refreshing…"
                        : globalFrontier
                          ? globalFrontier.items.length + " returned · " + globalFrontier.candidate_count_scanned + " scanned" + (globalFrontier.truncated ? " · truncated" : "")
                          : "UNKNOWN"}
                    </dd>
                    <p className="mt-1 text-xs leading-5 text-muted">Bounded scan of existing records, not all possible value in reality.</p>
                  </div>
                </dl>
              </section>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-extrabold">Readiness</h2>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to="/operations"
                    className="inline-flex min-h-11 items-center rounded-card border-2 border-line px-4 text-sm font-bold hover:border-accent"
                  >
                    Open operating dashboard
                  </Link>
                  <button type="button" onClick={sendTestEmail} disabled={busy} className="min-h-11 rounded-card border-2 border-accent px-4 font-bold text-accent disabled:opacity-60">
                    Send one-shot test email
                  </button>
                  <button type="button" onClick={lockConsole} className="min-h-11 rounded-card border-2 border-line px-4 font-bold">
                    Lock console
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {signalFor(
                  readiness.database_ok && readiness.migrations_ok ? "green" : "red",
                  "Database and schema",
                  readiness.database_ok && readiness.migrations_ok ? "Available and current" : "Unavailable or not current",
                  readiness.database_ok && readiness.migrations_ok ? "No action needed." : "Restore the database connection and apply the application schema.",
                )}
                {signalFor(
                  readiness.smtp_configured ? "green" : "amber",
                  "Owner email",
                  readiness.smtp_configured ? "SMTP is configured" : "SMTP is not configured",
                  readiness.smtp_configured ? "Send a test and confirm it arrives." : "Configure the approved mail provider before relying on email alerts.",
                )}
                {signalFor(
                  readiness.hmac_key_configured ? "green" : "red",
                  "Privacy key",
                  readiness.hmac_key_configured ? "Configured" : "Missing or too short",
                  readiness.hmac_key_configured ? "Keep the key stable and rotate it deliberately." : "Configure a stable server-side HMAC key.",
                )}
                {signalFor(
                  readiness.intake_enabled || readiness.live_enabled ? "red" : "amber",
                  "Activation flags",
                  `Intake flag ${readiness.intake_enabled ? "on" : "off"} · LIVE ${readiness.live_enabled ? "on" : "off"}`,
                  readiness.intake_enabled || readiness.live_enabled ? "Close both flags until the readiness checklist is approved." : "Keep both closed until every runbook check passes and the exact activation phrase is given.",
                )}
                {signalFor(
                  heartbeatState,
                  "Daily maintenance",
                  `${displayTime(readiness.last_maintenance_at)}${readiness.last_maintenance_age_seconds == null ? "" : ` · ${Math.floor(readiness.last_maintenance_age_seconds / 3600)}h old`}`,
                  heartbeatState === "green" ? "No action needed." : "Check the scheduled maintenance run and restore it before activation.",
                )}
                {signalFor(
                  emailQueueState,
                  "Owner email queue",
                  readiness.oldest_unsent_or_failed_owner_email_at
                    ? `Oldest pending/failed: ${displayTime(readiness.oldest_unsent_or_failed_owner_email_at)}`
                    : "No pending or failed owner email",
                  emailQueueState === "green"
                    ? "No action needed."
                    : "Check SMTP settings; queued owner notices retry when the scheduled digest runs. Permanent failures need correction.",
                )}
                {signalFor(
                  readiness.last_test_email_result === "ACCEPTED_BY_SMTP" ? "green" : "amber",
                  "Last test email",
                  `${readiness.last_test_email_result} · ${displayTime(readiness.last_test_email_at)}`,
                  readiness.last_test_email_result === "ACCEPTED_BY_SMTP" ? "Confirm receipt in the mailbox." : "Send the one-shot test and confirm receipt.",
                )}
                {signalFor(
                  readiness.deployed_commit ? "green" : "amber",
                  "Deployed revision",
                  readiness.deployed_commit ?? "Not reported",
                  readiness.deployed_commit ? "Compare it with origin/main before activation." : "Check deployment metadata and verify it matches origin/main.",
                )}
              </div>

              <section className="mt-8 rounded-card border-2 border-line bg-card p-4 sm:p-5">
                <h2 className="text-lg font-extrabold">Lead counts</h2>
                <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {(Object.entries(readiness.lead_counts_by_stage) as Array<[LeadStage, number]>).map(([stage, count]) => (
                    <div key={stage} className="rounded-card border border-line p-3">
                      <dt className="text-xs font-bold uppercase tracking-wide text-muted">{stage}</dt>
                      <dd className="mt-1 text-2xl font-extrabold">{count}</dd>
                    </div>
                  ))}
                  {(Object.entries(readiness.lead_counts_by_evidence_class) as Array<["REAL" | "TEST", number]>).map(([evidenceClass, count]) => (
                    <div key={evidenceClass} className="rounded-card border border-line p-3">
                      <dt className="text-xs font-bold uppercase tracking-wide text-muted">{evidenceClass}</dt>
                      <dd className="mt-1 text-2xl font-extrabold">{count}</dd>
                    </div>
                  ))}
                  <div className="rounded-card border border-line p-3">
                    <dt className="text-xs font-bold uppercase tracking-wide text-muted">New in 24 hours</dt>
                    <dd className="mt-1 text-2xl font-extrabold">{readiness.new_leads_last_24h}</dd>
                  </div>
                </dl>
              </section>

              <section id="owner-inquiries" className="mt-8 scroll-mt-24">
                <h2 className="text-lg font-extrabold">Inquiries</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
                  These controls record owner-reported milestones only. They do
                  not send a reply, create a booking, or record payment or revenue.
                </p>
                {consoleState.leads.length === 0 ? (
                  <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">No active inquiries.</p>
                ) : (
                  <ul className="mt-3 grid gap-3">
                    {consoleState.leads.map((lead) => (
                      <li key={lead.reference} className="min-w-0 rounded-card border-2 border-line bg-card p-4">
                        <button
                          type="button"
                          onClick={() => void loadLead(lead.reference)}
                          className="min-h-10 break-all text-left font-extrabold text-accent underline underline-offset-4"
                        >
                          {lead.reference}
                        </button>
                        <dl className="mt-2 grid min-w-0 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
                          <div><dt className="inline text-muted">Received: </dt><dd className="inline break-words">{displayTime(lead.received_at)}</dd></div>
                          <div><dt className="inline text-muted">Stage: </dt><dd className="inline">{lead.stage}</dd></div>
                          <div><dt className="inline text-muted">Evidence: </dt><dd className="inline">{lead.evidence_class}</dd></div>
                          <div><dt className="inline text-muted">Channel: </dt><dd className="inline">{lead.channel}</dd></div>
                          <div><dt className="inline text-muted">Destination: </dt><dd className="inline break-words">{lead.destination || "Not stated"}</dd></div>
                          <div><dt className="inline text-muted">Course: </dt><dd className="inline break-words">{lead.course || "Not stated"}</dd></div>
                        </dl>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {selected ? (
                <section className="mt-6 min-w-0 rounded-card border-2 border-accent/70 bg-card p-4 sm:p-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs uppercase tracking-wide text-accent">Owner-only contact view</p>
                      <h2 className="mt-1 break-all text-xl font-extrabold">{selected.reference}</h2>
                    </div>
                    <button type="button" onClick={() => setSelected(null)} className="min-h-10 rounded-card border border-line px-3 font-bold">Close details</button>
                  </div>
                  <dl className="mt-4 grid min-w-0 gap-x-5 gap-y-2 text-sm sm:grid-cols-2">
                    <div><dt className="text-muted">Email</dt><dd className="break-all">{selected.email || "Not provided"}</dd></div>
                    <div><dt className="text-muted">Phone</dt><dd className="break-all">{selected.phone || "Not provided"}</dd></div>
                    <div><dt className="text-muted">Timeline</dt><dd className="break-words">{selected.timeline || "Not stated"}</dd></div>
                    <div><dt className="text-muted">Budget range</dt><dd>{selected.budget_minimum ?? "Not stated"} – {selected.budget_maximum ?? "Not stated"}</dd></div>
                    <div><dt className="text-muted">Consent recorded</dt><dd>{displayTime(selected.consent_at)}</dd></div>
                  </dl>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {selected.stage === "REQUESTED" ? (
                      <button type="button" disabled={busy} onClick={() => void runAction("/replied", undefined, "POST", "Reply recorded.")} className="min-h-11 rounded-card border-2 border-accent px-4 font-bold text-accent disabled:opacity-60">
                        Mark replied
                      </button>
                    ) : null}
                    {selected.stage === "REPLIED" ? (
                      <form onSubmit={(event) => { event.preventDefault(); void runAction("/booked", { evidence_reference: evidenceReference }, "POST", "Booking recorded."); }} className="grid w-full gap-2 sm:max-w-lg sm:grid-cols-[1fr_auto]">
                        <label className="grid gap-1 text-sm font-semibold" htmlFor="booking-evidence">
                          Booking evidence reference
                          <input id="booking-evidence" value={evidenceReference} onChange={(event) => setEvidenceReference(event.target.value)} maxLength={100} minLength={2} required className="min-h-11 min-w-0 rounded-card border-2 border-line bg-black px-3 text-ink" />
                        </label>
                        <button type="submit" disabled={busy} className="min-h-11 self-end rounded-card border-2 border-accent px-4 font-bold text-accent disabled:opacity-60">Mark booked</button>
                      </form>
                    ) : null}
                    {selected.stage === "BOOKED" ? (
                      <form onSubmit={(event) => { event.preventDefault(); void runAction("/completed", { outcome_note: outcomeNote }, "POST", "Completion recorded."); }} className="grid w-full gap-2 sm:max-w-lg sm:grid-cols-[1fr_auto]">
                        <label className="grid gap-1 text-sm font-semibold" htmlFor="outcome-note">
                          Short outcome note
                          <textarea id="outcome-note" value={outcomeNote} onChange={(event) => setOutcomeNote(event.target.value)} maxLength={240} minLength={2} required rows={2} className="min-h-11 min-w-0 rounded-card border-2 border-line bg-black px-3 py-2 text-ink" />
                        </label>
                        <button type="submit" disabled={busy} className="min-h-11 self-end rounded-card border-2 border-accent px-4 font-bold text-accent disabled:opacity-60">Mark completed</button>
                      </form>
                    ) : null}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm("Erase this inquiry and its contact details now? A non-contact erasure event will remain.")) {
                          void runAction("", undefined, "DELETE", "Inquiry erased; the non-contact erasure event remains.");
                        }
                      }}
                      className="min-h-11 rounded-card border-2 border-danger px-4 font-bold text-danger disabled:opacity-60"
                    >
                      Erase contact now
                    </button>
                  </div>
                  {selected.history.length ? (
                    <ol className="mt-6 grid gap-2 border-t border-line pt-4 text-sm">
                      {selected.history.map((entry, index) => (
                        <li key={`${entry.event}-${entry.at}-${index}`} className="break-words">
                          <span className="font-bold">{entry.state || entry.event}</span>
                          <span className="text-muted"> · {displayTime(entry.at)}</span>
                          {entry.evidence_reference ? <p>Evidence reference: {entry.evidence_reference}</p> : null}
                          {entry.outcome_note ? <p>Outcome note: {entry.outcome_note}</p> : null}
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </section>
              ) : null}

              <section id="hami-intelligence" className="mt-10 scroll-mt-24 border-t-2 border-line pt-5" aria-label="Intelligence">
                <h2 className="text-xl font-extrabold">Orchestrator &amp; intelligence</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  What Hami&apos;s engines actually did — last runs, per-stage
                  results, research state, and source clearance. UNKNOWN means
                  not instrumented, not zero. Nothing here is inferred from
                  imports or tests; every number comes from a persisted record.
                </p>
                <section id="hami-frontier" aria-label="Global value frontier" className="scroll-mt-24 rounded-card border-2 border-line bg-card p-4 sm:p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-extrabold">Global value frontier</h3>
                      <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                        Recorded discoveries, unknown-map entries, research, capability gaps, and failed or disputed outcomes across distinct lanes — independent of the commercial Bet selector.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => { void refreshGlobalFrontier(key); }}
                      disabled={globalFrontierLoading}
                      className="min-h-10 rounded-card border-2 border-line px-3 text-sm font-bold disabled:opacity-60"
                    >
                      {globalFrontierLoading ? "Refreshing…" : "Refresh frontier"}
                    </button>
                  </div>
                  {globalFrontierError ? (
                    <p role="alert" className="mt-3 rounded-card border border-line p-3 text-sm text-muted">
                      Frontier unavailable — {globalFrontierError}. This is not an empty-world result.
                    </p>
                  ) : globalFrontier === null ? (
                    <p className="mt-3 rounded-card border border-line p-3 text-sm text-muted">
                      Frontier has not been loaded yet.
                    </p>
                  ) : (
                    <>
                      <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-card border border-line p-3">
                          <p className="text-xs font-bold uppercase tracking-wide text-muted">Recorded items scanned</p>
                          <p className="mt-1 text-2xl font-extrabold">{globalFrontier.candidate_count_scanned}</p>
                        </div>
                        <div className="rounded-card border border-line p-3">
                          <p className="text-xs font-bold uppercase tracking-wide text-muted">Distinct lanes</p>
                          <p className="mt-1 text-2xl font-extrabold">{Object.keys(globalFrontier.lane_counts_scanned).length}</p>
                        </div>
                        <div className="rounded-card border border-line p-3">
                          <p className="text-xs font-bold uppercase tracking-wide text-muted">Returned for review</p>
                          <p className="mt-1 text-2xl font-extrabold">{globalFrontier.items.length}</p>
                        </div>
                      </div>
                      {globalFrontier.scan_limited_sources.length ? (
                        <p className="mt-3 text-sm text-muted">
                          Bounded scan limit reached for: {globalFrontier.scan_limited_sources.join(", ")}. The frontier is incomplete and needs further review.
                        </p>
                      ) : null}
                      <div className="mt-4 grid gap-3 lg:grid-cols-2">
                        {globalFrontier.items.slice(0, 16).map((item) => (
                          <article key={item.frontier_id} className="min-w-0 rounded-card border border-line p-4">
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="rounded border border-line px-2 py-1 font-mono">{item.record_type.replace(/_/g, " ")}</span>
                              <span className="text-muted">{item.kind.replace(/_/g, " ")}</span>
                              <span className="text-muted">· {item.status}</span>
                              {item.success === false ? <span className="text-muted">· reported failure</span> : null}
                              {item.unknown_id ? <span className="font-mono text-muted">{item.unknown_id}</span> : null}
                            </div>
                            <h4 className="mt-2 break-words font-bold">{item.title}</h4>
                            {item.record_type === "recorded_connection" && item.from_entity && item.to_entity ? (
                              <div className="mt-2 rounded-card border border-line bg-card p-3 text-sm">
                                <p className="font-semibold">Recorded endpoints</p>
                                <p className="mt-1 break-words">{item.from_entity.name} <span className="text-muted">({item.from_entity.type} #{item.from_entity.id})</span></p>
                                <p className="text-muted">connects to</p>
                                <p className="break-words">{item.to_entity.name} <span className="text-muted">({item.to_entity.type} #{item.to_entity.id})</span></p>
                                {item.domain_hints?.from || item.domain_hints?.to ? (
                                  <p className="mt-2 text-xs text-muted">Recorded domains: {item.domain_hints.from || "not recorded"} → {item.domain_hints.to || "not recorded"}</p>
                                ) : null}
                                {typeof item.strength === "number" ? <p className="mt-1 text-xs text-muted">Recorded strength: {item.strength}</p> : null}
                              </div>
                            ) : null}
                            {item.record_type === "possibility_path" && item.path_entities && item.path_relations ? (
                              <div className="mt-2 rounded-card border border-line bg-card p-3 text-sm">
                                <p className="font-semibold">Composed from recorded links</p>
                                <ol className="mt-2 space-y-2">
                                  {item.path_entities.map((entity, index) => (
                                    <li key={entity.id} className="break-words">
                                      <span className="font-semibold">{entity.name}</span>
                                      <span className="text-xs text-muted"> · {entity.type} #{entity.id}</span>
                                      {index < item.path_relations!.length ? (
                                        <p className="text-xs text-muted">— {item.path_relations![index].type} ({item.path_relations![index].state}) →</p>
                                      ) : null}
                                    </li>
                                  ))}
                                </ol>
                                <p className="mt-2 text-xs text-muted">Hypothesis only. The links exist in records; usefulness of the combined path is untested.</p>
                              </div>
                            ) : null}
                            {item.domain_hint ? <p className="mt-1 text-sm text-muted">Recorded domain: {item.domain_hint}</p> : null}
                            {item.recorded_cheapest_test ? (
                              <p className="mt-2 break-words text-sm"><span className="font-bold">Recorded test:</span> {item.recorded_cheapest_test}</p>
                            ) : null}
                            <p className="mt-2 break-words text-sm text-muted">{item.next_step}</p>
                            <p className="mt-2 text-xs text-muted">
                              Source records: {item.source_refs.length ? item.source_refs.map((ref) => `${ref.kind} #${ref.id}`).join(", ") : "Not linked in this projection"}
                              {item.epistemic_state ? ` · ${item.epistemic_state}` : ""}
                              {item.data_scope ? ` · scope ${item.data_scope}` : ""}
                              {item.source_kind ? ` · provenance ${item.source_kind}` : ""}
                            </p>
                          </article>
                        ))}
                      </div>
                      {globalFrontier.items.length > 16 || globalFrontier.truncated ? (
                        <p className="mt-3 text-sm text-muted">
                          Showing at most 16 returned records. Additional recorded work exists or one or more source scans reached its bound.
                        </p>
                      ) : null}
                      <p className="mt-3 border-t border-line pt-3 text-xs leading-5 text-muted">
                        Read-only projection; not a measure of total world value, not proof that a hypothesis is true, and not authorization to run a test or action. This view does not trigger discovery or create work.
                      </p>
                    </>
                  )}
                </section>
                {intel === null ? (
                  <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">
                    Intelligence data unavailable — the console could not load it.
                  </p>
                ) : (
                  <div className="mt-4 grid gap-6">
                    
                    {/* Canonical orchestrator: persisted stage state only, no customer/contact details. */}
                    <div>
                      <h3 className="font-extrabold">Canonical orchestration path</h3>
                      <p className="mt-1 text-sm text-muted">
                        Opportunity → owner-reviewed decision → human validation → product → distribution → verified outcome.
                        Counts come from persisted records; this panel never advances or approves work.
                      </p>
                      {orchestrationOverview === null ? (
                        <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
                          {orchestrationError ?? "Orchestrator status UNKNOWN — refresh the owner console to load the read-only projection."}
                        </p>
                      ) : (
                        <>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            {([
                              ["Opportunities", orchestrationOverview.pipeline.opportunities],
                              ["Accepted decisions", orchestrationOverview.pipeline.decisions_accepted],
                              ["Validation experiments", orchestrationOverview.pipeline.validation_experiments],
                              ["Completed experiments", orchestrationOverview.pipeline.experiments_completed],
                              ["Verified REAL outcomes", orchestrationOverview.pipeline.outcomes],
                              ["REAL products", orchestrationOverview.pipeline.products],
                              ["REAL distribution channels", orchestrationOverview.pipeline.distribution_channels],
                              ["Actions awaiting approval", orchestrationOverview.pipeline.actions_awaiting_approval],
                            ] as const).map(([label, value]) => (
                              <div key={label} className="rounded-card border-2 border-line bg-card p-3">
                                <p className="text-sm text-muted">{label}</p>
                                <p className="mt-1 text-xl font-extrabold tabular-nums">{value}</p>
                              </div>
                            ))}
                          </div>
                          <div className="mt-3 rounded-card border-2 border-line bg-card p-4">
                            <p className="text-sm text-muted">Verified REAL outcome revenue · USD</p>
                            <p className="mt-1 text-2xl font-extrabold tabular-nums">{formatUsd(orchestrationOverview.pipeline.actual_revenue)}</p>
                            <p className="mt-2 text-sm text-muted">Verified REAL outcome revenue · NPR</p>
                            <p className="mt-1 text-xl font-extrabold tabular-nums">{formatNpr(orchestrationOverview.pipeline.actual_revenue_by_currency?.NPR)}</p>
                            <p className="mt-2 text-xs text-muted">
                              SANDBOX remains separate: USD {formatUsd(orchestrationOverview.pipeline.sandbox.actual_revenue)} · NPR {formatNpr(orchestrationOverview.pipeline.sandbox.actual_revenue_by_currency?.NPR)} · {orchestrationOverview.pipeline.sandbox.products} sandbox products; not business traction.
                            </p>
                          </div>
                          <div className="mt-5" id="pipeline">
                            <h4 className="font-bold">Opportunity pipeline</h4>
                            <p className="mt-1 text-sm text-muted">
                              Ranked REAL-scope opportunities (up to 25). Select one to inspect its validation plan and record work you actually performed.
                              Nothing here contacts a prospect or treats willingness-to-pay as collected money.
                            </p>
                            {orchestrationOverview.flow.length === 0 ? (
                              <p className="mt-2 text-sm text-muted">No opportunity rows are currently returned by the selected REAL-scope view.</p>
                            ) : (
                              <ul className="mt-2 grid gap-3">
                                {orchestrationOverview.flow.map((item) => (
                                  <li key={item.opportunity_id} className="rounded-card border-2 border-line bg-card p-4">
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                      <p className="font-bold">Opportunity #{item.opportunity_id}</p>
                                      <span className="rounded border border-line px-2 py-1 text-xs font-bold">{item.opportunity_status}</span>
                                    </div>
                                    <p className="mt-2 text-sm">{item.problem || "Problem not recorded"}</p>
                                    <p className="mt-1 text-sm text-muted">Target-customer hypothesis: {item.target_customer_hypothesis}</p>
                                    <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                                      <div><dt className="text-muted">Decision</dt><dd className="font-bold">{item.decision_status}</dd></div>
                                      <div><dt className="text-muted">Validation</dt><dd className="font-bold">{item.validation_status}</dd></div>
                                      <div><dt className="text-muted">Products</dt><dd className="font-bold">{item.product_count}</dd></div>
                                      <div><dt className="text-muted">Distribution channels</dt><dd className="font-bold">{item.distribution_channel_count}</dd></div>
                                    </dl>
                                    <div className="mt-3 flex flex-wrap items-center gap-2">
                                      <button type="button" disabled={pipelineBusy} onClick={() => void openOpportunityPipeline(item.opportunity_id)} className="min-h-10 rounded-card border-2 border-accent px-3 py-2 text-sm font-bold text-accent disabled:opacity-60">
                                        {selectedOpportunityId === item.opportunity_id ? "Refresh pipeline detail" : "Open pipeline"}
                                      </button>
                                      {item.requires_owner_approval ? <span className="text-xs text-muted">Owner approval required</span> : null}
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            )}
                            {selectedOpportunityId !== null ? (
                              <section className="mt-5 rounded-card border-2 border-accent/70 bg-card p-4 sm:p-6" aria-label="Selected opportunity validation">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <p className="font-mono text-xs uppercase tracking-wide text-accent">Owner-only validation record</p>
                                    <h4 className="mt-1 text-lg font-extrabold">Opportunity #{selectedOpportunityId}</h4>
                                  </div>
                                  <button type="button" onClick={() => { setSelectedOpportunityId(null); setOrchestratorDetail(null); setPipelineError(""); setPipelineNotice(""); }} className="min-h-10 rounded-card border border-line px-3 text-sm font-bold">Close detail</button>
                                </div>
                                {pipelineError ? <p role="alert" className="mt-3 rounded-card border border-danger/70 p-3 text-sm">{pipelineError}</p> : null}
                                {pipelineNotice ? <p role="status" className="mt-3 rounded-card border border-line p-3 text-sm">{pipelineNotice}</p> : null}
                                {orchestratorDetail === null ? (
                                  <p className="mt-3 text-sm text-muted">{pipelineBusy ? "Loading the canonical opportunity record…" : "Opportunity detail is unavailable."}</p>
                                ) : (
                                  <>
                                    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                                      <div><dt className="text-muted">Target customer</dt><dd>{orchestratorDetail.opportunity.target_customer || "Not specified"}</dd></div>
                                      <div><dt className="text-muted">Current decision</dt><dd>{orchestratorDetail.decision.status || "Not started"}{orchestratorDetail.decision.title ? " · " + orchestratorDetail.decision.title : ""}</dd></div>
                                      <div><dt className="text-muted">Validation task</dt><dd>{orchestratorDetail.experiment.status || "Not prepared"} · {orchestratorDetail.experiment.stage}</dd></div>
                                      <div><dt className="text-muted">Demand evidence</dt><dd>{orchestratorDetail.outcomes_count} recorded outcome(s); {orchestratorDetail.products.length} product record(s)</dd></div>
                                    </dl>
                                    <div className="mt-4 rounded-card border border-line p-3">
                                      <h5 className="font-bold">Outcome provenance</h5>
                                      {orchestratorDetail.outcomes.length ? (
                                        <ul className="mt-2 grid gap-2 text-sm">
                                          {orchestratorDetail.outcomes.map((outcome) => (
                                            <li key={outcome.id} className="flex flex-wrap items-start justify-between gap-2 border-b border-line/60 pb-2 last:border-0">
                                              <span>Outcome #{outcome.id} · {outcome.outcome_type}</span>
                                              <span className="font-mono text-xs">{outcome.source_kind}/{outcome.verification_state}</span>
                                            </li>
                                          ))}
                                        </ul>
                                      ) : <p className="mt-2 text-sm text-muted">No outcome records yet.</p>}
                                      <p className="mt-3 text-xs leading-5 text-muted">
                                        Owner-entered interview notes are stored as MOCK/REPORTED. REAL scope alone is not proof: only separately qualifying REAL/VERIFIED evidence counts toward the product demand gate. A paid-customer record requires a separate verified ACTUAL_REVENUE outcome.
                                      </p>
                                    </div>
                                    {orchestratorDetail.opportunity.economic_evidence_summary ? <p className="mt-3 text-sm">{orchestratorDetail.opportunity.economic_evidence_summary}</p> : null}
                                    {orchestratorDetail.experiment.hypothesis ? (
                                      <div className="mt-4 rounded-card border border-line p-3">
                                        <p className="font-bold">Validation hypothesis</p>
                                        <p className="mt-1 text-sm">{orchestratorDetail.experiment.hypothesis}</p>
                                        {orchestratorDetail.experiment.expected_result ? <p className="mt-2 text-sm text-muted">{orchestratorDetail.experiment.expected_result}</p> : null}
                                        {orchestratorDetail.experiment.required_inputs.length ? (
                                          <ul className="mt-2 list-disc pl-5 text-sm text-muted">
                                            {orchestratorDetail.experiment.required_inputs.map((input, index) => <li key={index}>{input}</li>)}
                                          </ul>
                                        ) : null}
                                        {orchestratorDetail.experiment.result ? <p className="mt-2 text-sm">Recorded result: {orchestratorDetail.experiment.result}</p> : null}
                                      </div>
                                    ) : null}
                                    <div className="mt-4 flex flex-wrap gap-2">
                                      {orchestratorDetail.experiment.id === null ? (
                                        <button type="button" disabled={pipelineBusy} onClick={() => void runPipelineAction("advance", undefined, "Prepare a human-run validation plan for this opportunity? This prepares records only; it will not contact anyone or spend money.", "Validation plan prepared; no external action was taken.")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">Prepare validation plan</button>
                                      ) : null}
                                      {orchestratorDetail.experiment.id !== null && orchestratorDetail.experiment.requires_owner_approval && orchestratorDetail.experiment.status === "planned" ? (
                                        <button type="button" disabled={pipelineBusy} onClick={() => void runPipelineAction("approve", undefined, "Approve this human-run validation task? This authorizes a human task, not automated outreach.", "Human-run validation task approved.")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">Approve task</button>
                                      ) : null}
                                      {orchestratorDetail.experiment.id !== null && (orchestratorDetail.experiment.status === "ready" || (orchestratorDetail.experiment.status === "planned" && !orchestratorDetail.experiment.requires_owner_approval)) ? (
                                        <button type="button" disabled={pipelineBusy} onClick={() => void runPipelineAction("execute", undefined, "Confirm that you have actually performed the human validation task. This only records the task as performed; it does not record an outcome.", "Human task marked performed; record the actual response next.")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">Record task performed</button>
                                      ) : null}
                                      {orchestratorDetail.experiment.id !== null && ["planned", "ready", "in_progress"].includes(orchestratorDetail.experiment.status || "") ? (
                                        <button type="button" disabled={pipelineBusy} onClick={() => void runPipelineAction("reject", undefined, "Reject and abandon this validation task? This is terminal for this task.", "Validation task rejected; no business outcome recorded.")} className="min-h-10 rounded-card border border-danger px-3 text-sm font-bold text-danger disabled:opacity-60">Reject task</button>
                                      ) : null}
                                      {orchestratorDetail.experiment.status === "completed" ? (
                                        <button type="button" disabled={pipelineBusy} onClick={() => void runPipelineAction("next-decision", undefined, "Create a new proposed decision based on this completed validation cycle?", "A new decision proposal was requested; it requires its own review.")} className="min-h-10 rounded-card border border-line px-3 text-sm font-bold disabled:opacity-60">Propose next decision</button>
                                      ) : null}
                                      {orchestratorDetail.experiment.status === "completed" && orchestratorDetail.products.length === 0 ? (
                                        <button type="button" disabled={pipelineBusy} onClick={() => void runPipelineAction("product", { data_scope: "REAL" }, "Check the existing demand gate (5 problem confirmations and 3 willing-to-pay respondents). This creates a product record only; it does not launch, charge, or record revenue.", "Product gate checked.")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">Make it a product</button>
                                      ) : null}
                                    </div>
                                    {orchestratorDetail.experiment.status === "in_progress" ? (
                                      <form onSubmit={(event) => void submitPipelineOutcome(event)} className="mt-5 grid gap-3 border-t border-line pt-4">
                                        <h5 className="font-bold">Record actual interview results</h5>
                                        <p className="text-sm text-muted">Record only work you personally performed or directly observed. Use one respondent per line: <code>id | stage | confirmed/not confirmed | short note</code>. This interview form accepts only lead, contacted, and interested; it cannot mark paid_customer or churned. Use pseudonymous IDs, not names, emails, or phone numbers. The existing write path saves owner-entered interview notes as MOCK/REPORTED, not verified REAL evidence. An interview or willingness-to-pay statement is not revenue; paid-customer status requires a separately verified ACTUAL_REVENUE outcome.</p>
                                        <label className="grid gap-1 text-sm font-semibold">
                                          What actually happened?
                                          <textarea value={outcomeActual} onChange={(event) => setOutcomeActual(event.target.value)} required minLength={2} maxLength={3000} rows={3} className="min-h-20 rounded-card border-2 border-line bg-black px-3 py-2 text-ink" placeholder="Summarize the real conversations and what was said." />
                                        </label>
                                        <label className="grid gap-1 text-sm font-semibold">
                                          Overall validation result
                                          <select value={outcomeSuccess} onChange={(event) => setOutcomeSuccess(event.target.value as "unknown" | "yes" | "no")} className="min-h-10 rounded-card border-2 border-line bg-black px-3 text-ink">
                                            <option value="unknown">Uncertain / mixed evidence</option>
                                            <option value="yes">Hypothesis supported by these interviews</option>
                                            <option value="no">Hypothesis not supported by these interviews</option>
                                          </select>
                                        </label>
                                        <label className="grid gap-1 text-sm font-semibold">
                                          Actual respondents (one per line)
                                          <textarea value={outcomeRespondents} onChange={(event) => setOutcomeRespondents(event.target.value)} required rows={5} className="min-h-28 rounded-card border-2 border-line bg-black px-3 py-2 font-mono text-xs text-ink" placeholder={`shop-01 | interested | confirmed | says they may pay NPR 4000/mo
shop-02 | lead | confirmed | confirmed delay problem; price unknown
shop-03 | lead | not confirmed | uses an existing alternative`} />
                                        </label>
                                        <button type="submit" disabled={pipelineBusy} className="min-h-11 justify-self-start rounded-card border-2 border-accent px-4 font-bold text-accent disabled:opacity-60">Save actual outcome</button>
                                      </form>
                                    ) : null}
                                    {orchestratorDetail.products.length > 0 ? (
                                      <div className="mt-5 border-t border-line pt-4">
                                        <h5 className="font-bold">Product records</h5>
                                        <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                                          {orchestratorDetail.products.map((product) => <li key={product.id} className="rounded-card border border-line p-3 text-sm"><strong>{product.name}</strong><p className="mt-1 text-muted">{product.status}{product.launch_state ? " · " + product.launch_state : ""}</p></li>)}
                                        </ul>
                                      </div>
                                    ) : null}
                                  </>
                                )}
                              </section>
                            ) : null}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Runtime window */}
                    <div>
                      <h3 className="font-extrabold">Engine state</h3>
                      {intel.runtime === null ? (
                        <p className="mt-2 text-sm text-muted">UNKNOWN — /forge/runtime not available.</p>
                      ) : (
                        <div className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          {signalFor(
                            intel.runtime.active_stage.startsWith("IDLE") ? "amber" : "green",
                            "Active stage",
                            intel.runtime.active_stage,
                            "Idle is normal — engines run on schedule or on demand.",
                          )}
                          {signalFor(
                            intel.runtime.worker.queued_tasks > 0 ? "amber" : "green",
                            "Worker queue",
                            `${intel.runtime.worker.queued_tasks} queued`,
                            intel.runtime.worker.last_task
                              ? `Last: ${intel.runtime.worker.last_task.worker_type}/${intel.runtime.worker.last_task.task_name} — ${intel.runtime.worker.last_task.status}`
                              : "No worker task recorded.",
                          )}
                          {signalFor(
                            !cycleOperations
                              ? "amber"
                              : cycleOperations.failed_cycles > 0
                                ? "red"
                                : cycleOperations.partial_cycles === undefined
                                  ? "amber"
                                  : cycleOperations.partial_cycles > 0 || cycleOperations.running_cycles > 0
                                    ? "amber"
                                    : "green",
                            "Cycle outcomes",
                            cycleOperations
                              ? `Completed ${cycleOperations.completed_cycles} · Partial ${cycleOperations.partial_cycles ?? "UNKNOWN"} · Failed ${cycleOperations.failed_cycles} · Running ${cycleOperations.running_cycles}`
                              : "UNKNOWN",
                            cycleOperations
                              ? "Partial means degraded work, not clean completion; counts come from persisted CycleRun records."
                              : "Cycle outcome counts unavailable; do not infer success.",
                          )}
                          {signalFor(
                            "green",
                            "Persisted totals",
                            `Signals ${intel.runtime.signals ?? "?"} · Evidence ${intel.runtime.evidence ?? "?"} · Tasks ${intel.runtime.research_tasks ?? "?"} · Opportunities ${intel.runtime.opportunities ?? "?"}`,
                            "Counts from live tables, not estimates.",
                          )}
                        </div>
                      )}
                    </div>

                    {/* Last intelligence run: per-stage results */}
                    <div>
                      <h3 className="font-extrabold">Last intelligence run</h3>
                      {intel.cycles === null ? (
                        <p className="mt-2 text-sm text-muted">UNKNOWN — /forge/cycles not available.</p>
                      ) : intel.cycles.length === 0 ? (
                        <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
                          No cycle recorded yet. Run one from /operations or wait for the schedule.
                        </p>
                      ) : (
                        <div className="mt-2 grid gap-3">
                          {intel.cycles.slice(0, 3).map((cycle) => (
                            <CycleCard key={cycle.id} cycle={cycle} />
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Research loop */}
                    <div>
                      <h3 className="font-extrabold">Research loop</h3>
                      <div className="mt-2 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-card border-2 border-line bg-card p-4">
                          <p className="font-bold">Open questions</p>
                          {intel.questions === null ? (
                            <p className="mt-1 text-sm text-muted">UNKNOWN</p>
                          ) : intel.questions.length === 0 ? (
                            <p className="mt-1 text-sm text-muted">None open.</p>
                          ) : (
                            <ul className="mt-2 grid gap-2 text-sm">
                              {intel.questions.slice(0, 5).map((q) => (
                                <li key={q.id} className="break-words">
                                  <span className="font-mono text-xs text-muted">#{q.id} · {q.priority_score.toFixed(0)}</span>{" "}
                                  {q.question.length > 140 ? `${q.question.slice(0, 140)}…` : q.question}
                                </li>
                              ))}
                              {intel.questions.length > 5 ? (
                                <li className="text-muted">+{intel.questions.length - 5} more</li>
                              ) : null}
                            </ul>
                          )}
                        </div>
                        <div className="rounded-card border-2 border-line bg-card p-4">
                          <p className="font-bold">Research tasks</p>
                          {intel.tasks === null ? (
                            <p className="mt-1 text-sm text-muted">UNKNOWN — task records unavailable.</p>
                          ) : intel.tasks.length === 0 ? (
                            <p className="mt-1 text-sm text-muted">None recorded.</p>
                          ) : (
                            <>
                              <dl className="mt-2 grid gap-1 text-sm">
                                {[...new Set(intel.tasks.map((task) => task.status))]
                                  .sort((left, right) => {
                                    const leftRank = TASK_STATUS_ORDER.indexOf(left as (typeof TASK_STATUS_ORDER)[number]);
                                    const rightRank = TASK_STATUS_ORDER.indexOf(right as (typeof TASK_STATUS_ORDER)[number]);
                                    if (leftRank === -1 && rightRank === -1) return left.localeCompare(right);
                                    if (leftRank === -1) return 1;
                                    if (rightRank === -1) return -1;
                                    return leftRank - rightRank;
                                  })
                                  .map((status) => {
                                    const count = intel.tasks!.filter((task) => task.status === status).length;
                                    return (
                                      <div key={status} className="flex justify-between">
                                        <dt className="text-muted">{status}</dt>
                                        <dd className="font-bold">{count}</dd>
                                      </div>
                                    );
                                  })}
                              </dl>
                              <div className="mt-3 grid gap-3">
                                {intel.tasks.slice(0, 5).map((task) => {
                                  const history = taskHistoryById[task.id];
                                  const title = (task.objective || task.query || "").trim();
                                  const isExpanded = expandedTaskId === task.id;
                                  return (
                                    <article key={task.id} className="rounded-card border border-line p-3">
                                      <div className="flex flex-wrap items-start justify-between gap-2">
                                        <div className="min-w-0">
                                          <p className="text-xs font-mono text-muted">
                                            Task #{task.id} · question #{task.question_id}
                                          </p>
                                          <p className="mt-1 break-words text-sm font-semibold">
                                            {title
                                              ? title.length > 140 ? `${title.slice(0, 140)}…` : title
                                              : "Task objective UNKNOWN"}
                                          </p>
                                          <p className="mt-1 break-words text-xs text-muted">
                                            {task.source || "Source UNKNOWN"} · {task.status}
                                          </p>
                                        </div>
                                        <button
                                          type="button"
                                          className="min-h-9 rounded-card border border-line px-3 py-1 text-xs font-semibold"
                                          aria-expanded={isExpanded}
                                          aria-controls={`task-history-${task.id}`}
                                          onClick={() => void toggleTaskHistory(task.id)}
                                        >
                                          {isExpanded ? "Hide history" : "View history"}
                                        </button>
                                      </div>
                                      <dl className="mt-2 grid gap-1 text-xs">
                                        <div className="flex flex-wrap justify-between gap-2">
                                          <dt className="text-muted">Current step</dt>
                                          <dd className="break-words text-right">{task.current_step || "UNKNOWN"}</dd>
                                        </div>
                                        <div className="flex flex-wrap justify-between gap-2">
                                          <dt className="text-muted">Attempts</dt>
                                          <dd>{task.attempts}/{task.max_attempts}</dd>
                                        </div>
                                        <div className="flex flex-wrap justify-between gap-2">
                                          <dt className="text-muted">Updated</dt>
                                          <dd>{task.updated_at ? new Date(task.updated_at).toLocaleString() : "UNKNOWN"}</dd>
                                        </div>
                                        <div className="flex flex-wrap justify-between gap-2">
                                          <dt className="text-muted">Evidence refs</dt>
                                          <dd className="max-w-full break-all text-right">
                                            {task.evidence_ids
                                              ? task.evidence_ids.length > 100 ? `${task.evidence_ids.slice(0, 100)}…` : task.evidence_ids
                                              : "UNKNOWN"}
                                          </dd>
                                        </div>
                                      </dl>
                                      {isExpanded ? (
                                        <div id={`task-history-${task.id}`} className="mt-3 border-t border-line pt-3">
                                          <p className="text-xs font-semibold">Recorded task events</p>
                                          {!history || history.status === "loading" ? (
                                            <p className="mt-2 text-xs text-muted">Loading owner-only history…</p>
                                          ) : history.status === "unavailable" ? (
                                            <p className="mt-2 text-xs text-muted">UNKNOWN — task history is not available on this backend.</p>
                                          ) : history.status === "error" ? (
                                            <p className="mt-2 break-words text-xs text-warning">{history.message}</p>
                                          ) : history.events.length === 0 ? (
                                            <p className="mt-2 text-xs text-muted">No events recorded.</p>
                                          ) : (
                                            <ol className="mt-2 grid gap-3">
                                              {[...history.events].slice(-6).reverse().map((event) => {
                                                const detail = summarizeTaskEventDetails(event.details);
                                                return (
                                                  <li key={event.id} className="border-l-2 border-line pl-3">
                                                    <p className="break-words text-xs font-semibold">
                                                      {event.event_type}{event.step_name ? ` · ${event.step_name}` : ""}
                                                    </p>
                                                    <p className="mt-1 text-xs text-muted">
                                                      {event.created_at ? new Date(event.created_at).toLocaleString() : "UNKNOWN"}
                                                    </p>
                                                    {detail ? (
                                                      <p className="mt-1 break-words text-xs text-muted">{detail}</p>
                                                    ) : null}
                                                  </li>
                                                );
                                              })}
                                            </ol>
                                          )}
                                        </div>
                                      ) : null}
                                    </article>
                                  );
                                })}
                              </div>
                              {intel.tasks.length > 5 ? (
                                <p className="mt-2 text-xs text-muted">Showing the 5 most recently created tasks of {intel.tasks.length}.</p>
                              ) : null}
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Source clearance */}
                    <div>
                      <h3 className="font-extrabold">Source clearance</h3>
                      <p className="mt-1 text-sm text-muted">
                        Legal/terms basis for collector eligibility. A task cannot run when its
                        source is absent here, expired, or not currently cleared.
                      </p>
                      {intel.clearance === null ? (
                        <p className="mt-2 text-sm text-muted">UNKNOWN — /forge/clearance not available on this backend.</p>
                      ) : (
                        <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                          {intel.clearance.sources.map((s) => (
                            <li
                              key={s.collector}
                              className={`rounded-card border-2 p-3 text-sm ${
                                s.clearance_state === "expired"
                                  ? "border-danger/70 bg-danger/10"
                                  : s.clearance_state === "expiring_soon"
                                    ? "border-warning/70 bg-warning/10"
                                    : "border-line bg-card"
                              }`}
                            >
                              <p className="font-bold">{s.display_name}</p>
                              <p className="text-muted">
                                {s.clearance_state === "expired"
                                  ? `EXPIRED ${Math.abs(s.days_until_expiry)}d ago`
                                  : s.clearance_state === "expiring_soon"
                                    ? `Expires in ${s.days_until_expiry}d`
                                    : `Valid through ${s.valid_through}`}
                                {" · "}
                                {s.collector_cleared_now ? "collector cleared" : "collector NOT cleared"}
                              </p>
                              <p className="mt-1 break-all text-xs text-muted">{s.url}</p>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </section>

              <section id="owner-products-payments" className="mt-10 scroll-mt-24 border-t-2 border-line pt-5" aria-label="Products and payments">
                <h2 className="text-xl font-extrabold">Products &amp; payments</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  Commercial visibility from the existing product ledger. Provider callbacks only
                  verify payment; the owner-only fulfillment action below records revenue after
                  the promised service has actually been delivered.
                </p>

                {commercial.products === null ? (
                  <p className="mt-3 rounded-card border-2 border-line bg-card p-4 text-sm text-muted">
                    {commercial.error ?? "Product figures UNKNOWN — refresh the owner console to load the existing product summary endpoint."}
                  </p>
                ) : (
                  <>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">REAL product records</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{realProducts.length}</p>
                      </div>
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">Launched / piloting</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{launchedProducts}</p>
                      </div>
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">REAL-source leads</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{realLeads}</p>
                      </div>
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">Recorded customers (verified ACTUAL outcomes)</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{recordedRealCustomers}</p>
                      </div>
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">Verified outcome revenue · USD</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{formatUsd(recordedRealRevenue)}</p>
                        <p className="mt-1 text-xs text-muted">Derived from verified REAL ACTUAL_REVENUE outcomes, not payment-provider configuration.</p>
                      </div>
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">Verified outcome revenue · NPR</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{formatNpr(recordedRealNprRevenue)}</p>
                        <p className="mt-1 text-xs text-muted">Separate from USD. Derived from verified REAL ACTUAL_REVENUE outcomes.</p>
                      </div>
                      <div className="rounded-card border-2 border-line bg-card p-4">
                        <p className="text-sm text-muted">SANDBOX records</p>
                        <p className="mt-1 text-2xl font-extrabold tabular-nums">{sandboxProducts.length}</p>
                        <p className="mt-2 text-sm">USD revenue: {formatUsd(recordedSandboxRevenue)}</p>
                        <p className="mt-1 text-sm">NPR revenue: {formatNpr(recordedSandboxNprRevenue)}</p>
                        <p className="mt-1 text-xs text-muted">Test data is not business traction.</p>
                      </div>
                    </div>

                    <div className="mt-6">
                      <h3 className="font-extrabold">Existing products</h3>
                      {productLifecycleError ? <p role="alert" className="mt-3 rounded-card border border-danger/70 p-3 text-sm">{productLifecycleError}</p> : null}
                      {productLifecycleNotice ? <p role="status" className="mt-3 rounded-card border border-line p-3 text-sm">{productLifecycleNotice}</p> : null}
                      {commercial.products.length === 0 ? (
                        <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
                          No product records returned by the owner-protected endpoint.
                        </p>
                      ) : (
                        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                          {commercial.products.map((product) => {
                            const pricingDraft = productPricingDrafts[product.id] ?? product.pricing ?? "";
                            const canPrepare = product.data_scope === "REAL"
                              && product.opportunity_id !== null
                              && product.launch_state !== "public"
                              && !["launched", "iterating"].includes(product.status)
                              && (product.approval_status !== "APPROVED" || !product.has_offer_brief || pricingDraft !== (product.pricing ?? ""));
                            return (
                              <li key={product.id} className="rounded-card border-2 border-line bg-card p-4">
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                  <h4 className="font-extrabold">{product.name}</h4>
                                  <span className="rounded border border-line px-2 py-1 text-xs font-bold">{product.data_scope}</span>
                                </div>
                                <p className="mt-2 text-sm text-muted">
                                  {product.status} · launch {product.launch_state ?? "UNKNOWN"} · approval {product.approval_status}
                                </p>
                                <p className="mt-2 text-sm">{product.offer}</p>
                                <p className="mt-1 text-sm text-muted">
                                  Leads {product.lead_count} · paid-customer records {product.paid_customer_count}
                                </p>
                                <p className="mt-1 text-sm">
                                  Verified outcome revenue · USD {formatUsd(product.actual_revenue)} · NPR {formatNpr(product.actual_revenue_by_currency?.NPR)} · actual customers {product.actual_customers}
                                </p>
                                {product.data_scope === "REAL" && product.opportunity_id !== null && product.launch_state !== "public" ? (
                                  <div className="mt-4 grid gap-2 border-t border-line pt-3">
                                    <label className="grid gap-1 text-sm font-semibold">
                                      Fixed offer price
                                      <input
                                        value={pricingDraft}
                                        onChange={(event) => setProductPricingDrafts((current) => ({ ...current, [product.id]: event.target.value }))}
                                        disabled={productLifecycleBusyId === product.id}
                                        className="min-h-10 rounded-card border-2 border-line bg-black px-3 text-ink"
                                        placeholder="NPR 5000 one-time"
                                      />
                                    </label>
                                    <p className="text-xs leading-5 text-muted">
                                      Public launch accepts only a fixed one-time NPR amount, e.g. “NPR 5000 one-time”. A price is not proof of willingness to pay.
                                    </p>
                                    {canPrepare ? (
                                      <button type="button" disabled={productLifecycleBusyId !== null} onClick={() => void runProductLifecycleAction(product, "prepare")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">
                                        {productLifecycleBusyId === product.id ? "Saving…" : "Save price & prepare review"}
                                      </button>
                                    ) : null}
                                    {product.has_offer_brief && product.approval_status === "PENDING_REVIEW" ? (
                                      <button type="button" disabled={productLifecycleBusyId !== null} onClick={() => void runProductLifecycleAction(product, "approve")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">Approve offer terms</button>
                                    ) : null}
                                    {product.approval_status === "APPROVED" && product.has_offer_brief && product.launch_state !== "public" ? (
                                      <button type="button" disabled={productLifecycleBusyId !== null} onClick={() => void runProductLifecycleAction(product, "publish")} className="min-h-10 rounded-card border-2 border-accent px-3 text-sm font-bold text-accent disabled:opacity-60">Publish offer</button>
                                    ) : null}
                                  </div>
                                ) : null}
                                {product.launch_state === "public" && product.approval_status === "APPROVED" ? (
                                  <button type="button" disabled={productLifecycleBusyId !== null} onClick={() => void runProductLifecycleAction(product, "pause")} className="mt-3 min-h-10 rounded-card border border-danger px-3 text-sm font-bold text-danger disabled:opacity-60">Pause public offer</button>
                                ) : null}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  </>
                )}

                <div className="mt-6">
                  <h3 className="font-extrabold">Distribution channels</h3>
                  <p className="mt-1 text-sm text-muted">
                    Existing channel rollups only. “Recorded events” is a ledger count, not a claim that outreach succeeded.
                  </p>
                  {channels === null ? (
                    <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
                      {channelsError ?? "Distribution channel state UNKNOWN — refresh the owner console."}
                    </p>
                  ) : channels.length === 0 ? (
                    <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
                      No distribution-channel records were returned for the owner view.
                    </p>
                  ) : (
                    <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                      {channels.map((channel) => {
                        const productName = commercial.products?.find((product) => product.id === channel.product_id)?.name;
                        const related = productName
                          ?? (channel.product_id !== null ? `Product #${channel.product_id}` : null)
                          ?? (channel.opportunity_id !== null ? `Opportunity #${channel.opportunity_id}` : "Unlinked record");
                        return (
                          <li key={channel.id} className="rounded-card border-2 border-line bg-card p-4">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <h4 className="font-bold">{channel.name}</h4>
                              <span className="rounded border border-line px-2 py-1 text-xs font-bold">{channel.data_scope}</span>
                            </div>
                            <p className="mt-1 text-sm text-muted">{related} · {channel.channel_type} · {channel.status}</p>
                            {channel.description ? <p className="mt-2 text-sm">{channel.description}</p> : null}
                            <p className="mt-3 text-sm">
                              Recorded events {channel.outreach_count} · responses {channel.response_count} · conversion-stage records {channel.conversion_count}
                            </p>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>

                <div className="mt-6">
                  <h3 className="font-extrabold">Payment integration visibility</h3>
                  {paymentConfiguration === null ? (
                    <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
                      {paymentConfigurationError ?? "Provider configuration UNKNOWN — refresh the owner console."}
                    </p>
                  ) : (
                    <>
                      <p className="mt-2 text-sm text-muted">
                        Configuration-only snapshot: no gateway request was made and no transaction was looked up.
                      </p>
                      <div className="mt-2 grid gap-3 sm:grid-cols-2">
                        <article className="rounded-card border-2 border-line bg-card p-4">
                          <p className="font-bold">eSewa</p>
                          <p className="mt-1 text-sm">
                            Required credentials: {paymentConfiguration.providers.esewa.required_credentials_present ? "present" : "incomplete"}
                          </p>
                          <p className="mt-1 text-sm text-muted">
                            Merchant code: {paymentConfiguration.providers.esewa.merchant_code_configured ? "configured" : "missing"} · signing secret: {paymentConfiguration.providers.esewa.signing_secret_configured ? "configured" : "missing"}
                          </p>
                        </article>
                        <article className="rounded-card border-2 border-line bg-card p-4">
                          <p className="font-bold">Khalti</p>
                          <p className="mt-1 text-sm">
                            Required credentials: {paymentConfiguration.providers.khalti.required_credentials_present ? "present" : "incomplete"}
                          </p>
                          <p className="mt-1 text-sm text-muted">
                            Secret key: {paymentConfiguration.providers.khalti.secret_key_configured ? "configured" : "missing"}
                          </p>
                        </article>
                      </div>
                    </>
                  )}
                  <p className="mt-3 text-sm text-muted">
                    Provider availability, merchant approval, transaction completion, settlement, and live collection remain NOT VERIFIED.
                    The configuration endpoint returns booleans only and never discloses credential values.
                  </p>
                </div>
              </section>

              <PaymentFulfillmentQueue apiKey={key} />

              <section className="mt-10 border-t-2 border-line pt-5" aria-label="Operating model v4">
                <h2 className="text-xl font-extrabold">Operating model v4</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  The kernel, the scoreboard, and the frozen frontier. Full text in{" "}
                  <code className="text-xs">docs/OPERATING_MODEL.md</code>.
                </p>
                <div className="mt-4">
                  <OperatingV4 apiKey={key} />
                </div>
              </section>

              <section className="mt-10 border-t-2 border-line pt-5" aria-label="Scout and outreach">
                <h2 className="text-xl font-extrabold">Scout &amp; outreach</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  Candidate sellers, draft messages, and your approval queue. Nothing here
                  sends anything — you send from your own account.
                </p>
                <div className="mt-4">
                  <ScoutQueue apiKey={key} />
                </div>
              </section>

              <section className="mt-10 border-t-2 border-line pt-5" aria-label="Buyer-side purchase journeys">
                <h2 className="text-xl font-extrabold">Buyer-side purchase journeys</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  Where is the sale decided? Record first-person purchase accounts —
                  consent-gated, your own words only, never anyone else's private messages.
                </p>
                <div className="mt-4">
                  <PurchaseJourney apiKey={key} />
                </div>
              </section>
                </div>
              </details>
            </div>
          )}

          {error ? <p role="alert" className="mt-5 rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}
          {notice ? <p role="status" className="mt-5 rounded-card border-2 border-success/70 bg-success/10 p-4 text-sm">{notice}</p> : null}

        </div>
      </Container>
    </main>
  );
}
