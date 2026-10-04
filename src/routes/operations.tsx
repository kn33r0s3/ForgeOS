import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useState } from "react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, MetricTile, SkeletonCards, Skeleton } from "@/components/ui/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RefreshCw, Play, Shield, CheckCircle, AlertTriangle, Activity, TrendingUp, Layers, WifiOff, Lightbulb, Wallet, FlaskConical, X } from "lucide-react";
import {
  loadExecutionActions,
  loadMoneyDashboard,
  type ActionRecord as ActionItem,
  type MoneyDashboard,
} from "@/lib/operations-data";

export const Route = createFileRoute("/operations")({
  component: OperationsPage,
  head: () => ({ meta: [{ title: "Operations — Hami" }] }),
});

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function OperationsPage() {
  const [ownerKey, setOwnerKey] = useState("");
  const [dashboard, setDashboard] = useState<MoneyDashboard | null>(null);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Change 4: Backend health state ──────────────────────────────────────
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  // Explicit cycle execution state
  const [runningCycle, setRunningCycle] = useState(false);
  const [cycleMsg, setCycleMsg] = useState<string | null>(null);

  // ── Change 4: Read-only health probe (uses /health — zero side-effects) ─
  async function checkBackendHealth(): Promise<boolean> {
    try {
      const res = await fetch("/api/health", { signal: AbortSignal.timeout(4000) });
      return res.ok;
    } catch {
      return false;
    }
  }

  // Read-only data loader (never auto-triggers cycles). This surface shows
  // pending approvals, so every read bypasses the short read cache: an action
  // approved moments ago must never be hidden behind a stale snapshot.
  const loadOperatingData = useCallback(async (apiKey: string) => {
    setLoading(true);
    setError(null);
    setDashboard(null);
    setActions([]);

    // Health probe first — distinguishes "backend offline" from "API error"
    const online = await checkBackendHealth();
    setBackendOnline(online);

    if (!online) {
      setError("Hami engine offline");
      setLoading(false);
      return;
    }

    try {
      const [dashData, actData] = await Promise.all([
        loadMoneyDashboard(apiKey, { fresh: true }),
        loadExecutionActions(apiKey, { fresh: true }),
      ]);

      setDashboard(dashData);
      setActions(actData);
    } catch (err: unknown) {
      const message = errorMessage(err, "Unable to query Hami data endpoints");
      setError(message.includes("HTTP 401") || message.includes("HTTP 403")
        ? "Owner only: this operational data requires the owner API key."
        : message);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Change 2: Explicit user action with confirmation ─────────────────────
  async function handleRunCycle() {
    const confirmed = window.confirm(
      "Run Hami Intelligence Cycle?\n\n" +
      "This operation writes to multiple Hami database tables " +
      "(cycle_runs, patterns, beliefs, research_tasks, predictions, opportunities, and more).\n\n" +
      "It does NOT execute any actions or spend money. " +
      "Proceed only when you want to advance the intelligence cycle."
    );
    if (!confirmed) return;

    setRunningCycle(true);
    setCycleMsg(null);
    try {
      const res = await fetch("/api/forge/cycle", {
        method: "POST",
        headers: { "X-API-Key": ownerKey },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCycleMsg(`Cycle complete. Status: ${data.status || "status not recorded"} · Cycle ID: ${data.cycle_id ?? "—"}`);
      await loadOperatingData(ownerKey);
    } catch (err: unknown) {
      setCycleMsg(`Cycle error: ${errorMessage(err, "Unexpected error")}`);
    } finally {
      setRunningCycle(false);
    }
  }

  // ── Change 2: Explicit user action with confirmation ─────────────────────
  async function handleRunDiscovery() {
    const confirmed = window.confirm(
      "Run Economic Discovery Scan?\n\n" +
      "This operation writes to the Hami opportunities table. " +
      "It evaluates patterns and strong signals against the economic evidence gate " +
      "and creates new Opportunity records where the bar is met.\n\n" +
      "It does NOT contact customers or spend money. " +
      "Proceed only when you want to run autonomous opportunity discovery."
    );
    if (!confirmed) return;

    setRunningCycle(true);
    setCycleMsg(null);
    try {
      const res = await fetch("/api/forge/economic/discover", {
        method: "POST",
        headers: { "X-API-Key": ownerKey },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCycleMsg(
        `Discovery complete: reviewed ${data.patterns_reviewed ?? "?"} pattern(s), ` +
        `created ${(data.opportunities_created ?? 0) + (data.single_signal_opportunities_created ?? 0)} new evidence-backed opportunity(ies).`
      );
      await loadOperatingData(ownerKey);
    } catch (err: unknown) {
      setCycleMsg(`Discovery error: ${errorMessage(err, "Unexpected error")}`);
    } finally {
      setRunningCycle(false);
    }
  }

  // ── Change 3: Null-safe approval handler ─────────────────────────────────
  async function handleApproveAction(id: number) {
    try {
      const res = await fetch(`/api/forge/execution/actions/${id}/approve`, {
        method: "POST",
        headers: { "X-API-Key": ownerKey },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      // Backend returns null when the action is blocked (policy_decision = BLOCKED)
      const body = await res.json();
      if (body === null) {
        alert(
          `Approval not applied for Action #${id}.\n\n` +
          "The Hami policy engine returned null, which means this action is currently " +
          "blocked by the autonomy policy. Review the policy_reason shown below the action."
        );
        return;
      }

      // Approval recorded — reload to reflect updated approved_at timestamp
      await loadOperatingData(ownerKey);
    } catch (err: unknown) {
      alert(`Approval error: ${errorMessage(err, "Unexpected error")}`);
    }
  }

  return (
    <main>
      <PageHeader
        eyebrow={
          <>
            <span className="live-dot live-dot-warning" aria-hidden="true" />
            Hami · Internal engine
          </>
        }
        title={
          <>
            Operating dashboard
            <span className="mt-2 block text-[0.55em] leading-tight text-muted">
              Evidence, opportunities &amp; proposed actions.
            </span>
          </>
        }
        lede="Hami operating window. It shows stored evidence, recorded opportunities, and actions that still need approval. A missing amount stays unknown. Figures come from the existing system data."
        aside={dashboard ? (
          <>
            <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">Manual controls</p>
            <p className="mt-2 text-xs leading-5 text-muted">
              Nothing runs on page load. Each run is started here, by you.
            </p>
            {/* Explicit User Mutation Controls (Never automatic on page load) */}
            <div className="mt-4 grid gap-2">
              <Button
                onClick={handleRunCycle}
                disabled={runningCycle || backendOnline === false}
                variant="primary"
                className="w-full gap-2"
              >
                <Play className={`size-4 ${runningCycle ? "animate-spin" : ""}`} />
                {runningCycle ? "Running Cycle..." : "Run Hami Cycle"}
              </Button>
              <Button
                onClick={handleRunDiscovery}
                disabled={runningCycle || backendOnline === false}
                variant="secondary"
                className="w-full gap-2"
              >
                <RefreshCw className={`size-4 ${runningCycle ? "animate-spin" : ""}`} />
                Run Discovery Scan
              </Button>
            </div>
          </>
        ) : null}
      >
        {cycleMsg && (
          <div
            role="status"
            className="fade-in mt-6 flex items-start justify-between gap-4 rounded-card border border-warning/35 bg-warning/10 p-4 font-mono text-sm text-warning"
          >
            <span>{cycleMsg}</span>
            <button
              type="button"
              onClick={() => setCycleMsg(null)}
              className="btn-ghost inline-flex min-h-8 shrink-0 items-center gap-1 rounded-card px-2 text-xs text-ink hover:text-accent focus-visible:text-accent"
            >
              <X className="size-3.5" aria-hidden="true" /> Dismiss
            </button>
          </div>
        )}
      </PageHeader>

      <section className="border-b border-line py-5">
        <Container>
          <form
            aria-label="Owner access"
            onSubmit={(event) => {
              event.preventDefault();
              void loadOperatingData(ownerKey);
            }}
            className="card grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
          >
            <label htmlFor="operations-owner-key" className="grid gap-1.5 text-sm font-bold text-ink">
              Owner API key
              <Input
                id="operations-owner-key"
                type="password"
                value={ownerKey}
                onChange={(event) => {
                  setOwnerKey(event.currentTarget.value);
                  setDashboard(null);
                  setActions([]);
                  setError(null);
                  setBackendOnline(null);
                }}
                autoComplete="off"
                spellCheck={false}
                required
              />
            </label>
            <Button type="submit" disabled={loading || !ownerKey.trim()} className="gap-2">
              <Shield className="size-4" aria-hidden="true" />
              {loading ? "Checking key…" : dashboard ? "Refresh dashboard" : "Load dashboard"}
            </Button>
          </form>
        </Container>
      </section>

      {/* Main Dashboard Content */}
      <section className="py-12 lg:py-16">
        <Container>
          {loading ? (
            <div role="status" aria-live="polite" className="space-y-10">
              <span className="sr-only">Connecting to Hami backend engine...</span>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {Array.from({ length: 4 }, (_, index) => (
                  <div key={index} className="card p-5" aria-hidden="true">
                    <Skeleton className="h-3 w-24" />
                    <Skeleton className="mt-4 h-8 w-20" />
                    <Skeleton className="mt-3 h-3 w-32" />
                  </div>
                ))}
              </div>
              <SkeletonCards count={2} label="Loading opportunities" className="grid gap-3 sm:grid-cols-2" />
              <SkeletonCards count={2} label="Loading proposed actions" className="space-y-3" />
            </div>
          ) : backendOnline === false ? (
            /* ── Change 4: Distinct offline banner ─────────────────────────── */
            <div role="alert" className="fade-in mx-auto max-w-2xl rounded-card border border-danger/35 bg-danger/5 p-8 text-center">
              <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-danger/10 text-danger">
                <WifiOff className="size-6" aria-hidden="true" />
              </div>
              <h2 className="mt-4 font-display text-3xl tracking-tight text-ink">Hami Engine Offline</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted">
                The local Hami backend (FastAPI, port 8000) is not responding. Economic data
                cannot be shown — displaying empty state here would misrepresent the actual system
                as having zero opportunities, which is not the same as an offline backend.
              </p>
              <p className="mx-auto mt-4 max-w-md rounded-card border border-line bg-paper/70 p-3 text-left font-mono text-xs leading-6 text-dim">
                Start the backend: <span className="text-accent">./run_forgeos.sh</span> (legacy command name)
                <br />
                or: <span className="text-accent">cd backend &amp;&amp; uvicorn app.main:app --port 8000</span>
              </p>
              <Button onClick={() => void loadOperatingData(ownerKey)} variant="secondary" size="sm" className="mt-5 gap-2">
                <RefreshCw className="size-4" /> Retry Connection
              </Button>
            </div>
          ) : error ? (
            <div role="alert" className="fade-in mx-auto max-w-2xl rounded-card border border-warning/35 bg-warning/5 p-8 text-center">
              <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-warning/10 text-warning">
                <AlertTriangle className="size-6" aria-hidden="true" />
              </div>
              <h2 className="mt-4 font-display text-3xl tracking-tight text-ink">Data Load Error</h2>
              <p className="mx-auto mt-3 max-w-md text-sm text-muted">
                Hami backend is reachable but returned an error: {error}
              </p>
              <Button onClick={() => void loadOperatingData(ownerKey)} variant="secondary" size="sm" className="mt-5 gap-2">
                <RefreshCw className="size-4" /> Retry
              </Button>
            </div>
          ) : dashboard ? (
            <div className="space-y-16">
              {/* 1. System Status & Economic State Overview */}
              <section aria-labelledby="ops-state">
                <SectionTitle id="ops-state" index="01" icon={Activity} title="System & economic state" />
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <MetricTile
                    index={0}
                    icon={Wallet}
                    tone="accent"
                    label="Verified revenue"
                    value={`NPR ${dashboard.total_revenue_recorded.toFixed(2)}`}
                    note="Bank/wallet verified payout only"
                  />
                  {/* ── Change 5: truthful sub-label ── */}
                  <MetricTile
                    index={1}
                    icon={Lightbulb}
                    label="Evidence-gated hypotheses"
                    value={dashboard.best_opportunities.length}
                    note="Opportunities scored by evidence — current money scores may be 0"
                  />
                  {/* ── Change 1 + 5: "queued" → "proposed, pending owner approval" ── */}
                  <MetricTile
                    index={2}
                    icon={Shield}
                    label="Proposed actions"
                    value={actions.length}
                    note="All require owner approval before any execution"
                  />
                  <MetricTile
                    index={3}
                    icon={FlaskConical}
                    label="Completed experiments"
                    value={dashboard.completed_experiments_count}
                    note="Measured validation tests"
                  />
                </div>
              </section>

              {/* 2. Opportunities Section */}
              <section aria-labelledby="ops-opps">
                <SectionTitle
                  id="ops-opps"
                  index="02"
                  icon={TrendingUp}
                  title="Ranked opportunities"
                  meta="Ordered by Money Score · Evidence-gated hypotheses"
                />
                {dashboard.best_opportunities.length === 0 ? (
                  <EmptyState
                    icon={Lightbulb}
                    headingLevel="h3"
                    title="No cleared opportunities"
                    body={'No opportunities currently cleared by the evidence engine. Click "Run Discovery Scan" to evaluate signals.'}
                  />
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {dashboard.best_opportunities.slice(0, 4).map((item, index) => {
                      const opp = item.opportunity;
                      return (
                        <article
                          key={opp.id}
                          className="card card-interactive reveal flex flex-col justify-between gap-4 p-5"
                          style={{ "--i": index } as React.CSSProperties}
                        >
                          <div>
                            <div className="flex items-start justify-between gap-3">
                              <span className="text-micro font-extrabold uppercase tracking-[0.08em] text-accent">
                                Opp #{opp.id} · {opp.customer_segment || opp.target_customer || "Customer not recorded"}
                              </span>
                              <span className="status-pill status-pill-accent shrink-0">Score {opp.score.toFixed(1)}</span>
                            </div>
                            <h3 className="mt-3 line-clamp-2 font-display text-xl leading-snug tracking-tight text-ink">
                              {opp.problem}
                            </h3>
                            {opp.solution ? (
                              <p className="mt-2 line-clamp-2 text-sm text-muted">{opp.solution}</p>
                            ) : null}
                          </div>
                          <dl className="grid grid-cols-3 gap-3 border-t border-line pt-3 text-micro font-extrabold uppercase tracking-[0.06em] text-dim">
                            <div>
                              <dt>Model</dt>
                              <dd className="mt-1 normal-case tracking-normal text-muted">{opp.business_model || "Model not recorded"}</dd>
                            </div>
                            <div>
                              <dt>Difficulty</dt>
                              <dd className="mt-1 normal-case tracking-normal text-muted">{opp.difficulty || "Difficulty not recorded"}</dd>
                            </div>
                            {/* ── Change 5: show money_score honestly even when 0 ── */}
                            <div>
                              <dt>Money score</dt>
                              <dd className="mt-1 normal-case tracking-normal text-muted">
                                {item.money_score.toFixed(2)}
                                {item.money_score === 0 && (
                                  <span className="block text-dim">(pending revenue validation)</span>
                                )}
                              </dd>
                            </div>
                          </dl>
                        </article>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* 3. Proposed Actions & Approval Queue — Change 1 */}
              <section aria-labelledby="ops-actions">
                <SectionTitle
                  id="ops-actions"
                  index="03"
                  icon={Shield}
                  title="Proposed actions & approval queue"
                  meta="Requires Owner Approval · None auto-executed"
                />
                {/* ── Change 1 + 5: truthful description of actual state ── */}
                <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
                  These are Hami-proposed validation actions (e.g. customer interviews). They are in{" "}
                  <span className="font-mono text-accent">planned</span> status with{" "}
                  <span className="font-mono text-accent">requires_owner_approval = true</span>.
                  None have been executed. Approving marks the record; it does not trigger automatic execution.
                </p>

                {actions.length === 0 ? (
                  <EmptyState icon={Shield} headingLevel="h3" title="Queue is clear" body="No proposed actions in the queue." />
                ) : (
                  <ol className="grid gap-3">
                    {actions.map((act, index) => (
                      <li
                        key={act.id}
                        className="card card-interactive reveal flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"
                        style={{ "--i": index } as React.CSSProperties}
                      >
                        <div className="min-w-0 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-micro font-extrabold uppercase tracking-[0.08em] text-accent">
                              Proposal #{act.id} · {act.action_type || "Action type not recorded"}
                            </span>
                            <span
                              className={`status-pill ${
                                act.status === "completed"
                                  ? "status-pill-success"
                                  : act.approved_at
                                  ? "status-pill-accent"
                                  : "status-pill-warning"
                              }`}
                            >
                              {/* ── Change 5: never show completed unless backend says so ── */}
                              {act.status === "completed"
                                ? "completed"
                                : act.approved_at
                                ? "approved (not yet executed)"
                                : act.status}
                            </span>
                          </div>
                          <p className="text-base font-semibold text-ink">{act.action}</p>
                          {act.policy_reason && (
                            <p className="text-xs leading-5 text-dim">Policy: {act.policy_reason}</p>
                          )}
                          {act.approved_at && (
                            <p className="text-xs text-dim">
                              Approved at: {new Date(act.approved_at).toLocaleString()} — awaiting manual execution
                            </p>
                          )}
                        </div>

                        {/* Only show Approve button when truly unapproved and not completed */}
                        {act.requires_owner_approval && act.status !== "completed" && !act.approved_at && (
                          <Button onClick={() => handleApproveAction(act.id)} size="sm" variant="warning" className="gap-1.5 self-start sm:self-auto">
                            <CheckCircle className="size-4" /> Approve Proposal
                          </Button>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              {/* 4. Honest Learning & Measured Outcomes Section */}
              <section aria-labelledby="ops-outcomes">
                <SectionTitle id="ops-outcomes" index="04" icon={Layers} title="Measured outcomes & learning" />
                {dashboard.completed_experiments_count === 0 ? (
                  <EmptyState
                    icon={Layers}
                    headingLevel="h3"
                    title="Outcomes Currently Empty"
                    body="No customer validation experiments have completed yet. As approved proposals are manually executed and real outcomes are recorded into Hami, results will appear here."
                  />
                ) : (
                  <div className="card p-6 text-sm text-ink">
                    {dashboard.winning_experiments.length} winning validation test(s) recorded.
                  </div>
                )}
              </section>
            </div>
          ) : null}
        </Container>
      </section>
    </main>
  );
}

function SectionTitle({
  id,
  index,
  icon: Icon,
  title,
  meta,
}: {
  id: string;
  index: string;
  icon: typeof Activity;
  title: string;
  meta?: string;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-line pb-4">
      <h2 id={id} className="flex items-center gap-3 font-display text-3xl tracking-tight text-ink">
        <span className="font-mono text-micro tracking-[0.14em] text-accent">{index}</span>
        <Icon className="size-5 text-accent" aria-hidden="true" />
        {title}
      </h2>
      {meta ? <span className="text-micro font-extrabold uppercase tracking-[0.1em] text-dim">{meta}</span> : null}
    </div>
  );
}
