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

function OwnerConsolePage() {
  const [key, setKey] = useState("");
  const [consoleState, setConsoleState] = useState<OwnerConsoleState | null>(null);
  const [selected, setSelected] = useState<LeadDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [evidenceReference, setEvidenceReference] = useState("");
  const [outcomeNote, setOutcomeNote] = useState("");

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
                  emailQueueState === "green" ? "No action needed." : "Inspect and retry the oldest failed or unsent delivery.",
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
