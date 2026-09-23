"use client";

import { useState } from "react";
import { api, Belief, BeliefGraph } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import ConfidenceBar from "@/components/ConfidenceBar";
import StatusPill from "@/components/StatusPill";
import { useForgeQuery } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";

export default function KnowledgePage() {
  const { state, data, error, reload } = useForgeQuery<Belief[]>(
    () => api.getBeliefs(),
    (d) => d.length === 0
  );
  const [selected, setSelected] = useState<number | null>(null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">FORGE KNOWLEDGE</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Every belief Forge holds, and why — real evidence and confidence history, never a
          generated-sounding explanation.
        </p>
      </div>

      {state !== "ready" && (
        <QueryStateView
          state={state}
          error={error}
          emptyLabel="No beliefs formed yet. Patterns become beliefs once enough signals support them."
          onRetry={reload}
        />
      )}

      {state === "ready" && data && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="space-y-2">
            {data.map((b) => (
              <button
                key={b.id}
                onClick={() => setSelected(b.id)}
                className={`w-full text-left glass-panel rounded-lg p-4 transition-colors ${
                  selected === b.id ? "glow-border" : "hover:border-forge-borderBright"
                }`}
              >
                <p className="text-sm text-neutral-200">{b.statement}</p>
                <div className="mt-2">
                  <ConfidenceBar label="Confidence" value={b.confidence_score} />
                </div>
              </button>
            ))}
          </div>
          <div>{selected !== null && <BeliefDetail beliefId={selected} />}</div>
        </div>
      )}
    </div>
  );
}

function BeliefDetail({ beliefId }: { beliefId: number }) {
  const { state, data, error, reload } = useForgeQuery<BeliefGraph>(
    () => api.getBeliefGraph(beliefId),
    () => false,
    [beliefId]
  );

  if (state !== "ready" || !data) {
    return <QueryStateView state={state} error={error} onRetry={reload} />;
  }

  const g = data;

  return (
    <GlassPanel glow className="p-5 sticky top-20 space-y-4">
      <div>
        <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-1">Forge Believes</p>
        <p className="text-base font-medium text-neutral-100">{g.belief.statement}</p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Metric label="Confidence" value={`${g.belief.confidence_score.toFixed(0)}%`} />
        <Metric label="Stability" value={`${g.stability_score.toFixed(0)}/100`} />
        <Metric label="Trend" value={g.confidence_trend} />
      </div>

      {g.originating_pattern && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-1">
            Originating Pattern
          </p>
          <p className="text-sm text-neutral-300">{g.originating_pattern.title}</p>
        </div>
      )}

      <div>
        <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-2">Why</p>
        <div className="grid grid-cols-2 gap-2 text-xs text-neutral-400">
          <span>Supporting evidence: {g.supporting_evidence.length}</span>
          <span>Contradicting evidence: {g.contradicting_evidence.length}</span>
          <span>Confidence history: {g.confidence_changes.length} events</span>
          <span>Related beliefs: {g.related_beliefs.length}</span>
        </div>
      </div>

      {g.confidence_changes.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-2">
            Confidence History
          </p>
          <ul className="space-y-1">
            {g.confidence_changes.slice(0, 6).map((c) => (
              <li key={c.id} className="flex justify-between text-xs text-neutral-400">
                <span>{c.reason || "update"}</span>
                <span className={c.delta >= 0 ? "text-forge-revenue" : "text-forge-danger"}>
                  {c.delta >= 0 ? "+" : ""}
                  {c.delta.toFixed(1)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {g.related_goals.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-2">Related Goals</p>
          <div className="flex flex-wrap gap-1.5">
            {g.related_goals.map((goal) => (
              <StatusPill key={goal.id} label={goal.status} />
            ))}
          </div>
        </div>
      )}
    </GlassPanel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm font-semibold text-neutral-100">{value}</p>
      <p className="text-[10px] text-neutral-500 uppercase">{label}</p>
    </div>
  );
}
