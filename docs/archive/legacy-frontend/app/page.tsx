"use client";

import { useEffect, useState } from "react";
import { api, Stats, ObserverStats, MoneyDashboard, ExecutionRecommendation, Signal, ExecutionAction, ForgeApiError, AutonomyPolicy, RevenueBreakdown, ForgeRuntime } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import StatusPill from "@/components/StatusPill";
import { QueryState } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";

type ActivityItem = { time: string; text: string; kind: "signal" | "execution" | "revenue" };
const loopStages = ["OBSERVE", "VERIFY", "UNDERSTAND", "DECIDE", "ACT", "MEASURE", "LEARN"];

function deriveSystemStatus(connection: QueryState, dashboard: MoneyDashboard | null, runtime: ForgeRuntime | null) {
  if (connection === "offline") return { label: "OFFLINE", tone: "text-forge-danger" };
  if (connection === "loading") return { label: "CONNECTING", tone: "text-neutral-400" };
  if (connection === "error" && !runtime && !dashboard) return { label: "DEGRADED", tone: "text-forge-warn" };
  if (runtime?.cycles?.running_count && runtime.cycles.running_count > 0) return { label: "CYCLE RUNNING", tone: "text-forge-accent2" };
  if (dashboard?.active_experiments?.some((action) => action.started_at && !action.completed_at)) return { label: "EXECUTING", tone: "text-forge-revenue" };
  if (runtime?.worker?.queued_tasks && runtime.worker.queued_tasks > 0) return { label: "QUEUED WORK", tone: "text-forge-accent2" };
  if (runtime?.active_stage?.startsWith("IDLE")) return { label: "IDLE", tone: "text-neutral-400" };
  return { label: "OBSERVING", tone: "text-forge-revenue" };
}

function buildActivityFeed(signals: Signal[], actions: ExecutionAction[]): ActivityItem[] {
  const items: ActivityItem[] = [];
  signals.slice(0, 8).forEach((s) => items.push({ time: s.timestamp, kind: "signal", text: s.quality_score != null && s.quality_score < 40 ? `Signal held below the quality floor (${Math.round(s.quality_score)}/100)` : `Signal observed — “${s.content.slice(0, 70)}${s.content.length > 70 ? "…" : ""}”` }));
  actions.slice(0, 8).forEach((a) => items.push({ time: a.completed_at || a.started_at || a.created_at, kind: a.completed_at && a.revenue && a.revenue > 0 ? "revenue" : "execution", text: a.completed_at ? (a.revenue != null ? `Action completed — $${a.revenue.toFixed(2)} recorded` : "Action completed — outcome not measured") : a.started_at ? `Action started — ${a.action_type || a.action}` : `Action proposed — ${a.action_type || a.action}` }));
  return items.sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()).slice(0, 10);
}

export default function ForgeCorePage() {
  const [connection, setConnection] = useState<QueryState>("loading");
  const [stats, setStats] = useState<Stats | null>(null);
  const [observerStats, setObserverStats] = useState<ObserverStats | null>(null);
  const [dashboard, setDashboard] = useState<MoneyDashboard | null>(null);
  const [recommendation, setRecommendation] = useState<ExecutionRecommendation | null>(null);
  const [beliefCount, setBeliefCount] = useState<number | null>(null);
  const [strategyCount, setStrategyCount] = useState<number | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [policy, setPolicy] = useState<AutonomyPolicy | null>(null);
  const [revenueBreakdown, setRevenueBreakdown] = useState<RevenueBreakdown | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<number | null>(null);
  const [blockedCount, setBlockedCount] = useState<number | null>(null);
  const [actionsToday, setActionsToday] = useState<number | null>(null);
  const [runtime, setRuntime] = useState<ForgeRuntime | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  function load(isRefresh = false) {
    if (!isRefresh) setConnection("loading");
    Promise.allSettled([api.getStats(), api.getObserverStats(), api.getMoneyDashboard(), api.getExecutionRecommendation(), api.getBeliefs(), api.getImportantSignals(8, 0), api.getExecutionActions(), api.getGoals(), api.getAutonomyPolicy(), api.getRevenueBreakdown(), api.getBlockedActions(), api.getRuntime()]).then(async (results) => {
      const [s, obs, dash, rec, beliefs, signals, actions, goals, pol, rev, blocked, rt] = results;
      if (s.status === "fulfilled") setStats(s.value); if (obs.status === "fulfilled") setObserverStats(obs.value); if (dash.status === "fulfilled") setDashboard(dash.value); if (rec.status === "fulfilled") setRecommendation(rec.value); if (beliefs.status === "fulfilled") setBeliefCount(beliefs.value.length); if (rt.status === "fulfilled") setRuntime(rt.value); if (pol.status === "fulfilled") setPolicy(pol.value); if (rev.status === "fulfilled") setRevenueBreakdown(rev.value); if (blocked.status === "fulfilled") setBlockedCount(blocked.value.length);
      if (signals.status === "fulfilled") setActivity(buildActivityFeed(signals.value, actions.status === "fulfilled" ? actions.value : []));
      if (actions.status === "fulfilled") { const today = new Date().toDateString(); setActionsToday(actions.value.filter((a) => new Date(a.created_at).toDateString() === today).length); setPendingApprovals(actions.value.filter((a) => a.requires_owner_approval && !a.approved_at && a.status !== "blocked").length); }
      if (goals.status === "fulfilled") { const counts = await Promise.allSettled(goals.value.map((g) => api.getStrategiesForGoal(g.id))); setStrategyCount(counts.reduce((sum, c) => sum + (c.status === "fulfilled" ? c.value.length : 0), 0)); }
      const anyOffline = results.some((r) => r.status === "rejected" && r.reason instanceof ForgeApiError && r.reason.status === 0); const anyFailed = results.some((r) => r.status === "rejected"); const anyData = [s, obs, dash, rt].some((r) => r.status === "fulfilled");
      if (anyOffline && !anyData) { setConnection("offline"); setErrorDetail("Could not reach the Forge backend."); } else if (anyFailed) { setConnection("error"); const first = results.find((r) => r.status === "rejected") as PromiseRejectedResult; setErrorDetail(first?.reason?.message || "Some Forge data could not be loaded."); } else { setConnection("ready"); setErrorDetail(null); }
      setLastUpdated(new Date().toISOString()); setInitialLoadDone(true);
    });
  }

  useEffect(() => { load(); const id = setInterval(() => load(true), 30000); return () => clearInterval(id); }, []);
  const status = deriveSystemStatus(connection, dashboard, runtime);
  if (connection === "loading" && !initialLoadDone) return <QueryStateView state="loading" />;
  if (connection === "offline" && !initialLoadDone) return <QueryStateView state="offline" error={errorDetail} onRetry={() => load()} />;

  const actualRevenue = runtime?.truth?.epistemic_labels?.actual_revenue ?? dashboard?.total_revenue_recorded ?? 0;
  const opportunityCount = runtime?.opportunities ?? stats?.total_opportunities ?? dashboard?.best_opportunities?.length ?? 0;

  return <div className="space-y-8 pb-10 animate-fade-up">
    <header className="hero-grid rounded-3xl border border-white/[0.08] bg-white/[0.035] px-6 py-8 md:px-10 md:py-11">
      <div className="max-w-3xl"><div className="eyebrow mb-4"><span className="live-dot" /> Hami intelligence / current cycle</div><h1 className="text-4xl font-semibold tracking-[-0.04em] text-white md:text-6xl">See what matters.<br /><span className="text-gradient">Act only on what is real.</span></h1><p className="mt-5 max-w-2xl text-base leading-7 text-neutral-400 md:text-lg">Hami observes signals, verifies evidence, and turns uncertainty into measured action — with the truth status of every claim kept visible.</p></div>
      <div className="mt-8 flex flex-wrap items-center gap-3 md:mt-10"><CommandButton label="Run Forge Cycle" onClick={async () => { await api.runForgeCycle(); load(true); }} primary /><CommandButton label="Run Autonomy Cycle" onClick={async () => { await api.runAutonomyCycleNow(); load(true); }} /><button onClick={() => load(true)} className="text-sm text-neutral-400 transition hover:text-white">Refresh data ↗</button></div>
      <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-white/[0.08] pt-5 text-xs text-neutral-500"><StatusPill label={status.label} /><span>{runtime?.active_stage || "Waiting for current stage"}</span><span className="hidden text-neutral-700 sm:inline">•</span><span>{lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Awaiting first update"}</span>{connection === "error" && <span className="text-forge-warn">Some data unavailable — retry when ready.</span>}</div>
    </header>

    <section><div className="section-intro"><div><p className="eyebrow">The Forge loop</p><h2 className="section-title">From signal to learning</h2></div><p className="section-note">A plain-language view of what the system is doing now.</p></div><div className="loop-track">{loopStages.map((stage, i) => <div className={`loop-step ${i === 0 ? "is-current" : ""}`} key={stage}><span>{String(i + 1).padStart(2, "0")}</span><strong>{stage}</strong>{i < loopStages.length - 1 && <i>→</i>}</div>)}</div></section>

    <section className="grid gap-4 md:grid-cols-4"><RealityCard label="Signals observed" value={runtime?.signals ?? stats?.total_signals ?? observerStats?.total_observations ?? "—"} status="OBSERVED" /><RealityCard label="Opportunities" value={opportunityCount} status={opportunityCount ? "INFERRED" : "NONE VERIFIED"} /><RealityCard label="Validation plans" value={runtime?.experiments ?? stats?.total_experiments ?? "—"} status="PLANNED / TRACEABLE" /><RealityCard label="Actual revenue" value={`$${actualRevenue.toFixed(2)}`} status="ACTUAL" accent /></section>

    <section className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]"><GlassPanel className="p-6 md:p-8"><div className="section-intro mb-7"><div><p className="eyebrow">Truth audit</p><h2 className="section-title">What is known right now</h2></div><span className="truth-chip">No invented certainty</span></div>{runtime?.truth ? <><div className="grid grid-cols-2 gap-x-5 gap-y-6 sm:grid-cols-4">{[["Raw signals", runtime.truth.epistemic_labels.raw_signals], ["Inferred patterns", runtime.truth.epistemic_labels.inferred_patterns], ["Opportunity hypotheses", runtime.truth.epistemic_labels.opportunity_hypotheses], ["Human validated", runtime.truth.epistemic_labels.human_validated_problems], ["Real outcomes", runtime.truth.epistemic_labels.actual_outcomes], ["Canonical evidence", runtime.truth.provenance.evidence_with_provenance], ["Pending actions", runtime.truth.operations.pending_actions], ["Failed cycles", runtime.truth.operations.failed_cycles]].map(([label, value]) => <Metric key={String(label)} label={String(label)} value={value as number} />)}</div><p className="mt-7 max-w-2xl border-t border-white/[0.07] pt-5 text-sm leading-6 text-neutral-500">Observed data is not the same as validation. Patterns and opportunities remain hypotheses until evidence or a real person confirms them.</p></> : <EmptyState title="Truth audit is unavailable" body="Hami is connected, but the audit summary did not load." />}</GlassPanel><GlassPanel className="p-6 md:p-8"><p className="eyebrow">Economic reality</p><h2 className="section-title mt-2">Revenue, without the spin</h2><div className="mt-8"><p className="text-5xl font-semibold tracking-[-0.05em] text-forge-revenue">${actualRevenue.toFixed(2)}</p><p className="mt-2 text-sm text-neutral-400">Actual revenue recorded</p></div>{revenueBreakdown && <div className="mt-8 space-y-4 border-t border-white/[0.07] pt-5"><MoneyLine label="Potential (estimated, 30d)" value={revenueBreakdown.potential_30d} /><MoneyLine label="Expected (evidence-weighted)" value={revenueBreakdown.expected} /><MoneyLine label="Realized (verified)" value={revenueBreakdown.realized} actual /></div>}<p className="mt-7 text-xs leading-5 text-neutral-500">Estimated opportunity value is not revenue. Only realized, verified results appear in the actual figure.</p></GlassPanel></section>

    <section className="grid gap-5 lg:grid-cols-[1fr_1fr]"><GlassPanel className="p-6 md:p-8"><p className="eyebrow">Decision</p><h2 className="section-title mt-2">What Hami recommends next</h2>{recommendation?.action ? <div className="mt-7"><span className="truth-chip">{recommendation.stage.toUpperCase()}</span><h3 className="mt-4 text-xl font-medium text-white">{recommendation.next_step}</h3><p className="mt-3 text-sm leading-6 text-neutral-400">{recommendation.reasoning}</p><div className="mt-6 flex gap-8"><Metric label="Action score" value={Math.round(recommendation.action_score)} /><Metric label="Confidence" value={`${Math.round(recommendation.factors?.confidence ?? 0)}%`} /></div></div> : <EmptyState title="No decision formed yet" body="Hami has not found a verified opportunity requiring a next action." />}</GlassPanel><GlassPanel className="p-6 md:p-8"><div className="section-intro"><div><p className="eyebrow">Recent trace</p><h2 className="section-title">What happened</h2></div><span className="text-xs text-neutral-500">last 10 events</span></div>{activity.length ? <ul className="mt-6 divide-y divide-white/[0.07]">{activity.map((item, i) => <li key={i} className="flex gap-3 py-3 text-sm"><span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${item.kind === "revenue" ? "bg-forge-revenue" : item.kind === "execution" ? "bg-forge-accent" : "bg-forge-accent2"}`} /><span className="leading-5 text-neutral-300">{item.text}<small className="ml-2 text-xs text-neutral-600">{new Date(item.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small></span></li>)}</ul> : <EmptyState title="No recent activity" body="Nothing has been recorded in this cycle yet." />}</GlassPanel></section>

    <GlassPanel className="p-6 md:p-8"><div className="section-intro"><div><p className="eyebrow">Guardrails</p><h2 className="section-title">Autonomy, with you in command</h2></div><span className="truth-chip">Policy enforced</span></div>{policy ? <div className="mt-7 grid gap-6 sm:grid-cols-4"><Metric label="Needs your approval" value={pendingApprovals ?? "—"} /><Metric label="Actions today" value={`${actionsToday ?? "—"} / ${policy.max_daily_actions}`} /><Metric label="Blocked by policy" value={blockedCount ?? "—"} /><Metric label="Beliefs / strategies" value={`${beliefCount ?? "—"} / ${strategyCount ?? "—"}`} /></div> : <EmptyState title="No autonomy policy configured" body="Hami will not assume permission to act without an explicit policy." />}</GlassPanel>
  </div>;
}

function RealityCard({ label, value, status, accent = false }: { label: string; value: number | string; status: string; accent?: boolean }) { return <div className="reality-card"><p className="eyebrow">{label}</p><p className={`mt-5 text-3xl font-semibold tracking-[-0.04em] ${accent ? "text-forge-revenue" : "text-white"}`}>{value}</p><p className="mt-2 text-[10px] font-semibold tracking-[0.16em] text-neutral-600">{status}</p></div>; }
function Metric({ label, value }: { label: string; value: number | string }) { return <div><p className="text-2xl font-semibold tabular text-white">{value}</p><p className="mt-1 text-xs text-neutral-500">{label}</p></div>; }
function MoneyLine({ label, value, actual = false }: { label: string; value: number; actual?: boolean }) { return <div className="flex items-center justify-between gap-4 text-sm"><span className="text-neutral-500">{label}</span><span className={actual ? "text-forge-revenue" : "text-neutral-300"}>${value.toFixed(2)}</span></div>; }
function EmptyState({ title, body }: { title: string; body: string }) { return <div className="empty-state mt-6"><p className="font-medium text-neutral-300">{title}</p><p className="mt-2 text-sm leading-6 text-neutral-500">{body}</p></div>; }
function CommandButton({ label, onClick, primary = false }: { label: string; onClick: () => Promise<void>; primary?: boolean }) { const [busy, setBusy] = useState(false); return <button disabled={busy} onClick={async () => { setBusy(true); try { await onClick(); } finally { setBusy(false); } }} className={`rounded-full px-5 py-2.5 text-sm font-medium transition ${primary ? "bg-white text-black hover:bg-forge-accent2" : "border border-white/[0.12] bg-white/[0.04] text-neutral-200 hover:border-white/[0.25] hover:bg-white/[0.08]"}`}>{busy ? "Working…" : label}</button>; }
