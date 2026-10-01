"use client";

import { useEffect, useState } from "react";
import { api, RankedOpportunity, Strategy, ExecutionAction } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import ConfidenceBar from "@/components/ConfidenceBar";
import StatusPill from "@/components/StatusPill";
import { useForgeQuery } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";

export default function OpportunitiesPage() {
  const { state, data, error, reload } = useForgeQuery<RankedOpportunity[]>(
    () => api.getRankedOpportunities(25),
    (d) => d.length === 0
  );
  const [expanded, setExpanded] = useState<number | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryNote, setDiscoveryNote] = useState<string | null>(null);

  async function runDiscovery() {
    setDiscovering(true);
    setDiscoveryNote(null);
    try {
      const result = await api.runEconomicDiscoveryNow();
      setDiscoveryNote(
        `Reviewed ${result.patterns_reviewed} pattern(s): ${result.opportunities_created} cleared the economic-evidence bar, ` +
          `${result.patterns_without_sufficient_evidence} did not (stayed patterns, not opportunities).`
      );
      reload();
    } finally {
      setDiscovering(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">OPPORTUNITY HUNT</h1>
          <p className="text-sm text-neutral-500 mt-1">
            Every opportunity Forge has discovered, ranked by transparent money score. Created only
            when a pattern clears a real economic-evidence bar — a problem, an identifiable
            customer, and real pain/demand/monetary evidence — never from a keyword repeating alone.
          </p>
        </div>
        <button
          disabled={discovering}
          onClick={runDiscovery}
          className="text-xs px-3 py-2 rounded-md border border-forge-border hover:glow-border-blue text-neutral-300 disabled:opacity-50 whitespace-nowrap"
        >
          {discovering ? "Scanning…" : "Scan Patterns for Opportunities"}
        </button>
      </div>

      {discoveryNote && (
        <div className="text-xs text-neutral-400 glass-panel rounded-md px-3 py-2">{discoveryNote}</div>
      )}

      {state !== "ready" && (
        <QueryStateView
          state={state}
          error={error}
          emptyLabel="No opportunities detected yet. Observe signals and run a Forge cycle to begin the hunt."
          onRetry={reload}
        />
      )}

      {state === "ready" && data && (
        <div className="grid gap-4">
          {data.map((item) => (
            <OpportunityQuestCard
              key={item.opportunity.id}
              item={item}
              expanded={expanded === item.opportunity.id}
              onToggle={() =>
                setExpanded(expanded === item.opportunity.id ? null : item.opportunity.id)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function urgencyFromDays(days: number | null | undefined): { label: string; tone: string } {
  if (days === null || days === undefined) return { label: "UNKNOWN", tone: "text-neutral-500" };
  if (days <= 14) return { label: "HIGH", tone: "text-forge-danger" };
  if (days <= 45) return { label: "MEDIUM", tone: "text-forge-warn" };
  return { label: "LOW", tone: "text-neutral-400" };
}

function OpportunityQuestCard({
  item,
  expanded,
  onToggle,
}: {
  item: RankedOpportunity;
  expanded: boolean;
  onToggle: () => void;
}) {
  const o = item.opportunity;
  const urgency = urgencyFromDays(o.time_to_first_revenue_days);
  const [strategies, setStrategies] = useState<Strategy[] | null>(null);
  const [actions, setActions] = useState<ExecutionAction[] | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!expanded || strategies !== null) return;
    setLoadingDetail(true);
    Promise.allSettled([
      o.goal_id ? api.getStrategiesForGoal(o.goal_id) : Promise.resolve([]),
      api.getExecutionActions(o.id),
    ]).then(([s, a]) => {
      setStrategies(s.status === "fulfilled" ? s.value : []);
      setActions(a.status === "fulfilled" ? a.value : []);
      setLoadingDetail(false);
    });
  }, [expanded, o.goal_id, o.id, strategies]);

  return (
    <GlassPanel glow={item.money_score >= 70} className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-1">
            Opportunity Detected
          </p>
          <p className="text-base font-medium text-neutral-100 leading-snug">{o.problem}</p>
          <p className="text-xs text-neutral-500 mt-1">Target: {o.target_customer}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-3xl font-bold tabular text-forge-accent2">{item.money_score.toFixed(0)}</p>
          <p className="text-[10px] text-neutral-500 uppercase tracking-wide">Money Score</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
        <div>
          <p className="text-sm font-semibold tabular text-neutral-100">
            {Math.round(o.revenue_confidence)}%
          </p>
          <p className="text-[10px] text-neutral-500 uppercase">Confidence</p>
        </div>
        <div>
          <p className="text-sm font-semibold tabular text-neutral-100">
            {item.expected_value !== null ? `$${item.expected_value.toFixed(2)}` : "unknown"}
          </p>
          <p className="text-[10px] text-neutral-500 uppercase">Expected Value</p>
        </div>
        <div>
          <p className={`text-sm font-semibold ${urgency.tone}`}>{urgency.label}</p>
          <p className="text-[10px] text-neutral-500 uppercase">Urgency</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-neutral-100">
            {o.monetization_model || "unclassified"}
          </p>
          <p className="text-[10px] text-neutral-500 uppercase">Model</p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <ConfidenceBar label="Market Confidence" value={o.market_confidence} colorClass="bg-forge-accent2" />
        <ConfidenceBar label="Uncertainty" value={o.uncertainty} colorClass="bg-forge-warn" />
      </div>

      <div className="flex items-center gap-2 mt-4">
        <StatusPill label={o.status} />
        <button
          onClick={onToggle}
          className="ml-auto text-xs px-3 py-1.5 rounded-md border border-forge-border hover:glow-border text-neutral-300"
        >
          {expanded ? "COLLAPSE" : "INVESTIGATE"}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-forge-border space-y-4 animate-fade-up">
          {o.economic_evidence_summary && (
            <div>
              <p className="text-xs uppercase tracking-widest text-neutral-500 mb-2">
                Why Forge Believes This Matters
              </p>
              <p className="text-sm text-neutral-300 leading-relaxed">{o.economic_evidence_summary}</p>
            </div>
          )}
          <div>
            <p className="text-xs uppercase tracking-widest text-neutral-500 mb-2">Solution</p>
            <p className="text-sm text-neutral-300">{o.solution}</p>
          </div>
          {loadingDetail && <p className="text-xs text-neutral-500">Loading strategies and actions…</p>}
          {strategies && strategies.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-widest text-neutral-500 mb-2">
                Generated Strategy
              </p>
              {strategies.slice(0, 2).map((s) => (
                <div key={s.id} className="text-sm text-neutral-300 mb-2">
                  <span className="text-forge-accent2 font-medium">{s.title}</span> —{" "}
                  {s.confidence.toFixed(0)}% confidence
                </div>
              ))}
            </div>
          )}
          {actions && actions.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-widest text-neutral-500 mb-2">
                Execution Actions
              </p>
              {actions.slice(0, 3).map((a) => (
                <div key={a.id} className="flex items-center gap-2 text-sm text-neutral-300 mb-1">
                  <StatusPill label={a.status} />
                  <span>{a.action}</span>
                </div>
              ))}
            </div>
          )}
          {strategies && strategies.length === 0 && (
            <p className="text-xs text-neutral-500">
              No strategy generated yet for this opportunity's goal.
            </p>
          )}
        </div>
      )}
    </GlassPanel>
  );
}
