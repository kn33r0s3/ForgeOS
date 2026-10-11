import { useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
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
  // JSON string of {stages, stage_errors} for scheduled intelligence runs;
  // null for older rows that predate per-stage persistence.
  summary: string | null;
};

type RuntimeWindow = {
  signals: number | null;
  evidence: number | null;
  research_tasks: number | null;
  opportunities: number | null;
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
  status: string;
  source: string | null;
  updated_at: string | null;
};

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
  if (cycle.summary) {
    try {
      const parsed: unknown = JSON.parse(cycle.summary);
      if (typeof parsed === "object" && parsed !== null && "stages" in parsed) {
        const raw = (parsed as { stages: unknown }).stages;
        if (typeof raw === "object" && raw !== null) {
          stages = raw as Record<string, { status?: string }>;
        }
      }
    } catch {
      stages = null;
    }
  }
  const stateColor =
    cycle.status === "COMPLETED"
      ? "border-success/70"
      : cycle.status === "FAILED"
        ? "border-danger/70"
        : "border-warning/70";
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
        <p className="mt-1 break-words text-sm text-danger">{cycle.error}</p>
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

  async function refresh(ownerKey = key) {
    const [readiness, leads] = await Promise.all([
      ownerFetch<Readiness>("owner/readiness", ownerKey),
      ownerFetch<Lead[]>("owner/leads", ownerKey),
    ]);
    setConsoleState({ readiness, leads });
    if (selected) {
      const updated = leads.find((lead) => lead.reference === selected.reference);
      if (!updated) setSelected(null);
    }
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

  async function unlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await refresh(key);
    } catch (cause) {
      setConsoleState(null);
      setError(cause instanceof Error ? cause.message : "Owner access is unavailable.");
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
    setKey("");
    setConsoleState(null);
    setSelected(null);
    setIntel(null);
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

  return (
    <main className="flex-1">
      <Container className="py-8 sm:py-12">
        <div className="mx-auto max-w-5xl">
          <p className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Owner tools · key-protected data
          </p>
          <h1 className="mt-2 text-title">Owner console</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
            This noindex page is publicly reachable but not linked from the
            public site. It loads no owner records until you enter the key.
            Your key stays in this page’s memory and is sent only in the
            X-API-Key request header; the API protects owner data and actions.
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
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-extrabold">Readiness</h2>
                <div className="flex flex-wrap gap-2">
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

              <section className="mt-8">
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

              <section className="mt-10 border-t-2 border-line pt-5" aria-label="Intelligence">
                <h2 className="text-xl font-extrabold">Intelligence</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  What Hami&apos;s engines actually did — last runs, per-stage
                  results, research state, and source clearance. UNKNOWN means
                  not instrumented, not zero. Nothing here is inferred from
                  imports or tests; every number comes from a persisted record.
                </p>
                {intel === null ? (
                  <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">
                    Intelligence data unavailable — the console could not load it.
                  </p>
                ) : (
                  <div className="mt-4 grid gap-6">
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
                            intel.runtime.cycles.running_count > 0 ? "amber" : "green",
                            "Cycles running",
                            `${intel.runtime.cycles.running_count}`,
                            intel.runtime.cycles.last
                              ? `Last run #${intel.runtime.cycles.last.id} — ${intel.runtime.cycles.last.status}`
                              : "No cycle recorded yet.",
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
                            <p className="mt-1 text-sm text-muted">UNKNOWN</p>
                          ) : intel.tasks.length === 0 ? (
                            <p className="mt-1 text-sm text-muted">None recorded.</p>
                          ) : (
                            <dl className="mt-2 grid gap-1 text-sm">
                              {(["open", "running", "completed", "failed"] as const).map((s) => {
                                const n = intel.tasks!.filter((t) => t.status === s).length;
                                return (
                                  <div key={s} className="flex justify-between">
                                    <dt className="text-muted">{s}</dt>
                                    <dd className="font-bold">{n}</dd>
                                  </div>
                                );
                              })}
                            </dl>
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

              <section className="mt-10 border-t-2 border-line pt-5" aria-label="ForgeBot">
                <h2 className="text-xl font-extrabold">ForgeBot</h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  The operator's console. Key-protected like everything else
                  here — the gate, the angle guard, and the ripeness queue run
                  the real engine code.
                </p>
                <div className="mt-4">
                  <ForgeConsoleWidgets />
                </div>
              </section>

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
          )}

          {error ? <p role="alert" className="mt-5 rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}
          {notice ? <p role="status" className="mt-5 rounded-card border-2 border-success/70 bg-success/10 p-4 text-sm">{notice}</p> : null}

          <section className="mt-10 max-w-3xl border-t-2 border-line pt-5">
            <h2 className="text-lg font-extrabold">A short daily routine</h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-muted">
              <li>Check database, schema, maintenance heartbeat, and the owner-email queue.</li>
              <li>Review new inquiries and reply only through a channel the owner has authorized.</li>
              <li>Record a booking only with evidence, then record completion only with an outcome note.</li>
              <li>Erase contact details when requested; rotate keys through the approved secret manager.</li>
              <li>Keep intake closed and LIVE off until every activation-runbook check passes.</li>
            </ol>
          </section>
        </div>
      </Container>
    </main>
  );
}
