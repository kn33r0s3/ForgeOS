"use client";

import { api, MoneyDashboard, RankedOpportunity, ExecutionAction } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import { useForgeQuery } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";

export default function RevenuePage() {
  const { state, data, error, reload } = useForgeQuery<MoneyDashboard>(
    () => api.getMoneyDashboard(),
    (d) => d.best_opportunities.length === 0 && d.active_experiments.length === 0
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">REVENUE INTELLIGENCE</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Real recorded revenue only. Predicted and expected figures are labeled separately from
          verified ones.
        </p>
      </div>

      {state !== "ready" && (
        <QueryStateView state={state} error={error} onRetry={reload} />
      )}

      {state === "ready" && data && (
        <div className="space-y-6">
          <GlassPanel glow className="p-8">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <RevenueHero
                label="Total Revenue (verified)"
                value={`$${data.total_revenue_recorded.toFixed(2)}`}
                accent
              />
              <RevenueHero
                label="Conversion Rate"
                value={data.conversion_rate !== null ? `${data.conversion_rate.toFixed(0)}%` : "unknown"}
              />
              <RevenueHero label="Experiments Completed" value={String(data.completed_experiments_count)} />
              <RevenueHero label="Active Experiments" value={String(data.active_experiments.length)} />
            </div>
          </GlassPanel>

          <div className="grid md:grid-cols-2 gap-4">
            <RankedList title="Fastest To Revenue" items={data.fastest_to_revenue} metric="speed" />
            <RankedList title="Highest 30-Day Estimate" items={data.highest_30d_estimate} metric="30d" />
            <RankedList title="Highest Confidence" items={data.highest_confidence} metric="confidence" />
            <RankedList title="Needing Validation" items={data.needing_validation} metric="score" />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <ExperimentList title="Winning Experiments" items={data.winning_experiments} tone="revenue" />
            <ExperimentList title="Failed Experiments" items={data.failed_experiments} tone="danger" />
          </div>
        </div>
      )}
    </div>
  );
}

function RevenueHero({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <p className={`text-3xl font-bold tabular ${accent ? "text-forge-revenue" : "text-neutral-100"}`}>
        {value}
      </p>
      <p className="text-[10px] text-neutral-500 uppercase tracking-wide mt-1">{label}</p>
    </div>
  );
}

function RankedList({
  title,
  items,
  metric,
}: {
  title: string;
  items: RankedOpportunity[];
  metric: "speed" | "30d" | "confidence" | "score";
}) {
  return (
    <GlassPanel className="p-4">
      <p className="text-xs uppercase tracking-widest text-neutral-500 mb-3">{title}</p>
      {items.length === 0 ? (
        <p className="text-sm text-neutral-600">No data yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 5).map((item) => (
            <li key={item.opportunity.id} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-neutral-300 truncate">{item.opportunity.problem}</span>
              <span className="text-forge-accent2 tabular shrink-0">
                {metric === "speed" &&
                  (item.opportunity.time_to_first_revenue_days !== null &&
                  item.opportunity.time_to_first_revenue_days !== undefined
                    ? `${item.opportunity.time_to_first_revenue_days}d`
                    : "?")}
                {metric === "30d" &&
                  (item.opportunity.estimated_revenue_30d !== null &&
                  item.opportunity.estimated_revenue_30d !== undefined
                    ? `$${item.opportunity.estimated_revenue_30d.toFixed(0)}`
                    : "?")}
                {metric === "confidence" && `${Math.round(item.opportunity.revenue_confidence)}%`}
                {metric === "score" && item.money_score.toFixed(0)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </GlassPanel>
  );
}

function ExperimentList({
  title,
  items,
  tone,
}: {
  title: string;
  items: ExecutionAction[];
  tone: "revenue" | "danger";
}) {
  return (
    <GlassPanel className="p-4">
      <p className="text-xs uppercase tracking-widest text-neutral-500 mb-3">{title}</p>
      {items.length === 0 ? (
        <p className="text-sm text-neutral-600">None recorded.</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 6).map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-neutral-300 truncate">{a.action}</span>
              <span className={`tabular shrink-0 ${tone === "revenue" ? "text-forge-revenue" : "text-forge-danger"}`}>
                {a.revenue !== null ? `$${a.revenue.toFixed(2)}` : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </GlassPanel>
  );
}
