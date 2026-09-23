import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { Button } from "@/components/ui/button";
import { RefreshCw, Play, Shield, CheckCircle, AlertTriangle, Activity, TrendingUp, Layers, WifiOff } from "lucide-react";

export const Route = createFileRoute("/operations")({
  component: OperationsPage,
  head: () => ({ meta: [{ title: "Operations — Sanip Ops" }] }),
});

interface OpportunityItem {
  id: number;
  problem: string;
  target_customer: string;
  solution: string;
  business_model: string;
  pricing_idea?: string;
  score: number;
  difficulty?: string;
  customer_segment?: string;
}

interface RankedOpportunity {
  opportunity: OpportunityItem;
  money_score: number;
  expected_value: number | null;
}

interface ActionItem {
  id: number;
  action: string;
  action_type?: string;
  status: string;
  requires_owner_approval?: boolean;
  policy_decision?: string;
  policy_reason?: string;
  approved_at?: string | null;
  created_at?: string;
}

interface MoneyDashboard {
  best_opportunities: RankedOpportunity[];
  active_experiments: ActionItem[];
  completed_experiments_count: number;
  total_revenue_recorded: number;
  conversion_rate: number | null;
  winning_experiments: any[];
  failed_experiments: any[];
}

function OperationsPage() {
  const [dashboard, setDashboard] = useState<MoneyDashboard | null>(null);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
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

  // Read-only data loader (never auto-triggers cycles)
  async function loadOperatingData() {
    setLoading(true);
    setError(null);

    // Health probe first — distinguishes "backend offline" from "API error"
    const online = await checkBackendHealth();
    setBackendOnline(online);

    if (!online) {
      setError("ForgeOS engine offline");
      setLoading(false);
      return;
    }

    try {
      const [dashRes, actRes] = await Promise.all([
        fetch("/api/forge/money/dashboard"),
        fetch("/api/forge/execution/actions"),
      ]);

      if (!dashRes.ok) throw new Error(`Dashboard API HTTP ${dashRes.status}`);
      if (!actRes.ok) throw new Error(`Actions API HTTP ${actRes.status}`);

      const dashData = await dashRes.json();
      const actData = await actRes.json();

      setDashboard(dashData);
      setActions(actData);
    } catch (err: any) {
      setError(err.message || "Unable to query ForgeOS data endpoints");
    } finally {
      setLoading(false);
    }
  }

  // ── Change 2: Explicit user action with confirmation ─────────────────────
  async function handleRunCycle() {
    const confirmed = window.confirm(
      "Run Forge Intelligence Cycle?\n\n" +
      "This operation writes to multiple ForgeOS database tables " +
      "(cycle_runs, patterns, beliefs, research_tasks, predictions, opportunities, and more).\n\n" +
      "It does NOT execute any actions or spend money. " +
      "Proceed only when you want to advance the intelligence cycle."
    );
    if (!confirmed) return;

    setRunningCycle(true);
    setCycleMsg(null);
    try {
      const res = await fetch("/api/forge/cycle", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCycleMsg(`Cycle complete. Status: ${data.status || "COMPLETED"} · Cycle ID: ${data.cycle_id ?? "—"}`);
      await loadOperatingData();
    } catch (err: any) {
      setCycleMsg(`Cycle error: ${err.message}`);
    } finally {
      setRunningCycle(false);
    }
  }

  // ── Change 2: Explicit user action with confirmation ─────────────────────
  async function handleRunDiscovery() {
    const confirmed = window.confirm(
      "Run Economic Discovery Scan?\n\n" +
      "This operation writes to the ForgeOS opportunities table. " +
      "It evaluates patterns and strong signals against the economic evidence gate " +
      "and creates new Opportunity records where the bar is met.\n\n" +
      "It does NOT contact customers or spend money. " +
      "Proceed only when you want to run autonomous opportunity discovery."
    );
    if (!confirmed) return;

    setRunningCycle(true);
    setCycleMsg(null);
    try {
      const res = await fetch("/api/forge/economic/discover", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCycleMsg(
        `Discovery complete: reviewed ${data.patterns_reviewed ?? "?"} pattern(s), ` +
        `created ${(data.opportunities_created ?? 0) + (data.single_signal_opportunities_created ?? 0)} new evidence-backed opportunity(ies).`
      );
      await loadOperatingData();
    } catch (err: any) {
      setCycleMsg(`Discovery error: ${err.message}`);
    } finally {
      setRunningCycle(false);
    }
  }

  // ── Change 3: Null-safe approval handler ─────────────────────────────────
  async function handleApproveAction(id: number) {
    try {
      const res = await fetch(`/api/forge/execution/actions/${id}/approve`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      // Backend returns null when the action is blocked (policy_decision = BLOCKED)
      const body = await res.json();
      if (body === null) {
        alert(
          `Approval not applied for Action #${id}.\n\n` +
          "The ForgeOS policy engine returned null, which means this action is currently " +
          "blocked by the autonomy policy. Review the policy_reason shown below the action."
        );
        return;
      }

      // Approval recorded — reload to reflect updated approved_at timestamp
      await loadOperatingData();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    }
  }

  useEffect(() => {
    loadOperatingData();
  }, []);

  return (
    <main>
      {/* Header & Controls Section */}
      <section className="border-b border-line py-12 lg:py-16">
        <Container>
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <Eyebrow tone="amber">
                <span className="size-1.5 rounded-full bg-amber shadow-[0_0_0_4px_var(--color-amber-dim)]" />
                Sanip Operations · Internal Engine
              </Eyebrow>
              <h1 className="font-display text-title tracking-tight text-fg">
                Operating Dashboard
                <br />
                <span className="text-muted">Evidence, opportunities &amp; proposed actions.</span>
              </h1>
              <p className="mt-4 max-w-2xl text-lede text-muted">
                Sanip Ops internal operating window. Exposes real evidence, scored opportunities,
                policy-governed approval queues, and verified economic results.
                All figures are drawn directly from the ForgeOS database — no fabricated data.
              </p>
            </div>

            {/* Explicit User Mutation Controls (Never automatic on page load) */}
            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={handleRunCycle}
                disabled={runningCycle || backendOnline === false}
                variant="amber"
                size="sm"
                className="gap-2"
              >
                <Play className={`size-4 ${runningCycle ? "animate-spin" : ""}`} />
                {runningCycle ? "Running Cycle..." : "Run Forge Cycle"}
              </Button>
              <Button
                onClick={handleRunDiscovery}
                disabled={runningCycle || backendOnline === false}
                variant="secondary"
                size="sm"
                className="gap-2"
              >
                <RefreshCw className={`size-4 ${runningCycle ? "animate-spin" : ""}`} />
                Run Discovery Scan
              </Button>
            </div>
          </div>

          {cycleMsg && (
            <div className="mt-6 rounded-lg border border-amber/30 bg-amber/10 p-4 font-mono text-sm text-amber flex items-center justify-between">
              <span>{cycleMsg}</span>
              <button onClick={() => setCycleMsg(null)} className="text-xs underline hover:text-fg">
                Dismiss
              </button>
            </div>
          )}
        </Container>
      </section>

      {/* Main Dashboard Content */}
      <section className="py-12 lg:py-16">
        <Container>
          {loading ? (
            <div className="flex items-center justify-center py-20 text-muted">
              <RefreshCw className="size-6 animate-spin mr-3 text-cyan" />
              Connecting to ForgeOS backend engine...
            </div>
          ) : backendOnline === false ? (
            /* ── Change 4: Distinct offline banner ─────────────────────────── */
            <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-8 text-center space-y-4">
              <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-red-500/10 text-red-400">
                <WifiOff className="size-6" />
              </div>
              <h2 className="font-display text-lg font-semibold text-fg">ForgeOS Engine Offline</h2>
              <p className="max-w-md mx-auto text-sm text-muted">
                The local ForgeOS backend (FastAPI, port 8000) is not responding. Economic data
                cannot be shown — displaying empty state here would misrepresent the actual system
                as having zero opportunities, which is not the same as an offline backend.
              </p>
              <p className="max-w-md mx-auto text-xs text-dim font-mono">
                Start the backend: <span className="text-cyan">./run_forgeos.sh</span>
                <br />
                or: <span className="text-cyan">cd backend &amp;&amp; uvicorn app.main:app --port 8000</span>
              </p>
              <Button onClick={loadOperatingData} variant="secondary" size="sm" className="gap-2">
                <RefreshCw className="size-4" /> Retry Connection
              </Button>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-line bg-surface p-8 text-center space-y-4">
              <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-amber/10 text-amber">
                <AlertTriangle className="size-6" />
              </div>
              <h2 className="font-display text-lg font-semibold text-fg">Data Load Error</h2>
              <p className="max-w-md mx-auto text-sm text-muted">
                ForgeOS backend is reachable but returned an error: {error}
              </p>
              <Button onClick={loadOperatingData} variant="secondary" size="sm" className="gap-2">
                <RefreshCw className="size-4" /> Retry
              </Button>
            </div>
          ) : dashboard ? (
            <div className="space-y-12">
              {/* 1. System Status & Economic State Overview */}
              <div>
                <h2 className="font-display text-lg font-semibold text-fg mb-4 flex items-center gap-2">
                  <Activity className="size-5 text-cyan" /> 1. System &amp; Economic State
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-xl border border-line bg-surface p-5">
                    <span className="font-mono text-micro uppercase text-dim block mb-1">Verified Revenue</span>
                    <span className="font-display text-2xl font-semibold text-fg">
                      NPR {dashboard.total_revenue_recorded.toFixed(2)}
                    </span>
                    <p className="mt-1 text-xs text-muted">Bank/wallet verified payout only</p>
                  </div>

                  <div className="rounded-xl border border-line bg-surface p-5">
                    <span className="font-mono text-micro uppercase text-dim block mb-1">Evidence-Gated Hypotheses</span>
                    <span className="font-display text-2xl font-semibold text-amber">
                      {dashboard.best_opportunities.length}
                    </span>
                    {/* ── Change 5: truthful sub-label ── */}
                    <p className="mt-1 text-xs text-muted">
                      Opportunities scored by evidence — current money scores may be 0
                    </p>
                  </div>

                  <div className="rounded-xl border border-line bg-surface p-5">
                    <span className="font-mono text-micro uppercase text-dim block mb-1">Proposed Actions</span>
                    <span className="font-display text-2xl font-semibold text-cyan">
                      {actions.length}
                    </span>
                    {/* ── Change 1 + 5: "queued" → "proposed, pending owner approval" ── */}
                    <p className="mt-1 text-xs text-muted">All require owner approval before any execution</p>
                  </div>

                  <div className="rounded-xl border border-line bg-surface p-5">
                    <span className="font-mono text-micro uppercase text-dim block mb-1">Completed Experiments</span>
                    <span className="font-display text-2xl font-semibold text-fg">
                      {dashboard.completed_experiments_count}
                    </span>
                    <p className="mt-1 text-xs text-muted">Measured validation tests</p>
                  </div>
                </div>
              </div>

              {/* 2. Opportunities Section */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-display text-lg font-semibold text-fg flex items-center gap-2">
                    <TrendingUp className="size-5 text-amber" /> 2. Ranked Opportunities
                  </h2>
                  <span className="font-mono text-micro uppercase text-dim">
                    Ordered by Money Score · Evidence-gated hypotheses
                  </span>
                </div>

                {dashboard.best_opportunities.length === 0 ? (
                  <div className="rounded-xl border border-line bg-surface p-6 text-center text-sm text-muted">
                    No opportunities currently cleared by the evidence engine. Click "Run Discovery Scan" to evaluate signals.
                  </div>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {dashboard.best_opportunities.slice(0, 4).map((item) => {
                      const opp = item.opportunity;
                      return (
                        <div key={opp.id} className="flex flex-col justify-between rounded-xl border border-line bg-surface p-5 space-y-3">
                          <div className="space-y-1.5">
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-micro uppercase text-cyan">
                                Opp #{opp.id} · {opp.customer_segment || opp.target_customer || "General"}
                              </span>
                              <span className="font-mono text-micro rounded-full border border-amber/30 bg-amber/10 px-2 py-0.5 text-amber">
                                Score: {opp.score.toFixed(1)}
                              </span>
                            </div>
                            <h3 className="font-display font-semibold text-fg text-base line-clamp-2">
                              {opp.problem}
                            </h3>
                            <p className="text-xs text-muted line-clamp-2">
                              {opp.solution}
                            </p>
                          </div>
                          <div className="border-t border-line pt-3 flex items-center justify-between text-xs text-dim font-mono">
                            <span>Model: {opp.business_model || "SaaS"}</span>
                            <span>Diff: {opp.difficulty || "medium"}</span>
                          </div>
                          {/* ── Change 5: show money_score honestly even when 0 ── */}
                          <div className="text-xs text-dim font-mono">
                            Money Score: {item.money_score.toFixed(2)}
                            {item.money_score === 0 && (
                              <span className="ml-2 text-dim opacity-70">(pending revenue validation)</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* 3. Proposed Actions & Approval Queue — Change 1 */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-display text-lg font-semibold text-fg flex items-center gap-2">
                    {/* ── Change 1: renamed heading ── */}
                    <Shield className="size-5 text-cyan" /> 3. Proposed Actions &amp; Approval Queue
                  </h2>
                  <span className="font-mono text-micro uppercase text-dim">
                    Requires Owner Approval · None auto-executed
                  </span>
                </div>

                {/* ── Change 1 + 5: truthful description of actual state ── */}
                <p className="mb-4 text-xs text-dim">
                  These are ForgeOS-proposed validation actions (e.g. customer interviews). They are in{" "}
                  <span className="text-amber font-mono">planned</span> status with{" "}
                  <span className="text-amber font-mono">requires_owner_approval = true</span>.
                  None have been executed. Approving marks the record; it does not trigger automatic execution.
                </p>

                {actions.length === 0 ? (
                  <div className="rounded-xl border border-line bg-surface p-6 text-center text-sm text-muted">
                    No proposed actions in the queue.
                  </div>
                ) : (
                  <div className="grid gap-3">
                    {actions.map((act) => (
                      <div key={act.id} className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-micro uppercase text-cyan">
                              Proposal #{act.id} · {act.action_type || "Validation"}
                            </span>
                            <span className={`rounded-full border px-2 py-0.5 font-mono text-micro ${
                              act.status === "completed"
                                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                                : act.approved_at
                                ? "border-cyan/30 bg-cyan/10 text-cyan"
                                : "border-amber/30 bg-amber/10 text-amber"
                            }`}>
                              {/* ── Change 5: never show completed unless backend says so ── */}
                              {act.status === "completed"
                                ? "completed"
                                : act.approved_at
                                ? "approved (not yet executed)"
                                : act.status}
                            </span>
                          </div>
                          <p className="font-display text-sm font-semibold text-fg">{act.action}</p>
                          {act.policy_reason && (
                            <p className="text-xs text-dim">Policy: {act.policy_reason}</p>
                          )}
                          {act.approved_at && (
                            <p className="text-xs text-dim">
                              Approved at: {new Date(act.approved_at).toLocaleString()} — awaiting manual execution
                            </p>
                          )}
                        </div>

                        {/* Only show Approve button when truly unapproved and not completed */}
                        {act.requires_owner_approval && act.status !== "completed" && !act.approved_at && (
                          <Button onClick={() => handleApproveAction(act.id)} size="sm" variant="amber" className="gap-1.5 self-start sm:self-auto">
                            <CheckCircle className="size-4" /> Approve Proposal
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 4. Honest Learning & Measured Outcomes Section */}
              <div>
                <h2 className="font-display text-lg font-semibold text-fg mb-4 flex items-center gap-2">
                  <Layers className="size-5 text-muted" /> 4. Measured Outcomes &amp; Learning
                </h2>
                <div className="rounded-xl border border-line bg-surface p-6 text-center">
                  {dashboard.completed_experiments_count === 0 ? (
                    <div className="space-y-2 text-muted">
                      <p className="text-sm font-medium text-fg">Outcomes Currently Empty</p>
                      <p className="max-w-md mx-auto text-xs">
                        No customer validation experiments have completed yet. As approved proposals are
                        manually executed and real outcomes are recorded into ForgeOS, results will appear here.
                      </p>
                    </div>
                  ) : (
                    <div className="text-sm text-fg">
                      {dashboard.winning_experiments.length} winning validation test(s) recorded.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </Container>
      </section>
    </main>
  );
}
