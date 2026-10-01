"use client";

import { useEffect, useState } from "react";
import { api, Goal, GoalGraph, BeliefGraph } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import ConfidenceBar from "@/components/ConfidenceBar";
import { useForgeQuery } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";

export default function WorldModelPage() {
  const { state, data: goals, error, reload } = useForgeQuery<Goal[]>(
    () => api.getGoals(),
    (d) => d.length === 0
  );
  const [selectedGoalId, setSelectedGoalId] = useState<number | null>(null);

  useEffect(() => {
    if (goals && goals.length > 0 && selectedGoalId === null) {
      setSelectedGoalId(goals[0].id);
    }
  }, [goals, selectedGoalId]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">FORGE WORLD</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Trace the full causal chain from a goal down to the evidence behind it.
        </p>
      </div>

      {state !== "ready" && (
        <QueryStateView
          state={state}
          error={error}
          emptyLabel="No goals defined yet. Create a Goal via the API to begin mapping the world."
          onRetry={reload}
        />
      )}

      {state === "ready" && goals && (
        <>
          <div className="flex flex-wrap gap-2">
            {goals.map((g) => (
              <button
                key={g.id}
                onClick={() => setSelectedGoalId(g.id)}
                className={`text-xs px-3 py-1.5 rounded-md border ${
                  selectedGoalId === g.id
                    ? "glow-border text-forge-accent2 border-forge-accent2/40"
                    : "border-forge-border text-neutral-400 hover:text-neutral-200"
                }`}
              >
                {g.statement.slice(0, 40)}
              </button>
            ))}
          </div>
          {selectedGoalId !== null && <GoalWorldView goalId={selectedGoalId} />}
        </>
      )}
    </div>
  );
}

function GoalWorldView({ goalId }: { goalId: number }) {
  const { state, data, error, reload } = useForgeQuery<GoalGraph>(
    () => api.getGoalGraph(goalId),
    () => false,
    [goalId]
  );

  if (state !== "ready" || !data) {
    return <QueryStateView state={state} error={error} onRetry={reload} />;
  }

  return (
    <div className="space-y-4">
      <WorldNode label="GOAL" tone="accent">
        <p className="text-sm text-neutral-200">{data.goal.statement}</p>
        <p className="text-xs text-neutral-500 mt-1">
          Priority {data.goal.priority.toFixed(0)}/100 · {data.goal.status}
        </p>
      </WorldNode>

      <Connector />

      <WorldNode label={`OPPORTUNITIES (${data.opportunities.length})`} tone="blue">
        {data.opportunities.length === 0 ? (
          <EmptyNote text="No opportunities linked to this goal yet." />
        ) : (
          <div className="space-y-2">
            {data.opportunities.map((o) => (
              <div key={o.opportunity.id} className="flex justify-between text-sm">
                <span className="text-neutral-300 truncate">{o.opportunity.problem}</span>
                <span className="text-forge-accent2 tabular shrink-0 ml-2">{o.money_score.toFixed(0)}</span>
              </div>
            ))}
          </div>
        )}
      </WorldNode>

      <Connector />

      <WorldNode label={`RELEVANT BELIEFS (${data.relevant_beliefs.length})`} tone="accent">
        {data.relevant_beliefs.length === 0 ? (
          <EmptyNote text="No beliefs connected to this goal yet." />
        ) : (
          <div className="space-y-3">
            {data.relevant_beliefs.map((b) => (
              <BeliefNode key={b.id} beliefId={b.id} statement={b.statement} confidence={b.confidence_score} />
            ))}
          </div>
        )}
      </WorldNode>

      <Connector />

      <WorldNode label={`CANDIDATE STRATEGIES (${data.candidate_strategies.length})`} tone="revenue">
        {data.candidate_strategies.length === 0 ? (
          <EmptyNote text="No strategies generated for this goal yet." />
        ) : (
          <div className="space-y-2">
            {data.candidate_strategies.map((s) => (
              <div key={s.id} className="text-sm">
                <p className="text-neutral-200">{s.title}</p>
                <ConfidenceBar label="Confidence" value={s.confidence} colorClass="bg-forge-revenue" />
              </div>
            ))}
          </div>
        )}
      </WorldNode>
    </div>
  );
}

function BeliefNode({ beliefId, statement, confidence }: { beliefId: number; statement: string; confidence: number }) {
  const [open, setOpen] = useState(false);
  const [graph, setGraph] = useState<BeliefGraph | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    if (!open && !graph) {
      setLoading(true);
      try {
        setGraph(await api.getBeliefGraph(beliefId));
      } finally {
        setLoading(false);
      }
    }
    setOpen((v) => !v);
  }

  return (
    <div className="border-l-2 border-forge-border pl-3">
      <button onClick={toggle} className="w-full text-left group">
        <p className="text-sm text-neutral-300 group-hover:text-neutral-100">{statement}</p>
        <p className="text-[10px] text-neutral-500 mt-0.5">
          {confidence.toFixed(0)}% confidence · click to inspect evidence
        </p>
      </button>
      {open && (
        <div className="mt-2 pl-2 border-l border-forge-border/60 text-xs text-neutral-400 space-y-1 animate-fade-up">
          {loading && <p>Loading evidence…</p>}
          {graph && (
            <>
              <p>Stability: {graph.stability_score.toFixed(0)}/100 · Trend: {graph.confidence_trend}</p>
              <p>Supporting evidence: {graph.supporting_evidence.length}</p>
              <p>Contradicting evidence: {graph.contradicting_evidence.length}</p>
              <p>Confidence history entries: {graph.confidence_changes.length}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function WorldNode({
  label,
  tone,
  children,
}: {
  label: string;
  tone: "accent" | "blue" | "revenue";
  children: React.ReactNode;
}) {
  const glowClass = tone === "blue" ? "glow-border-blue" : tone === "revenue" ? "glow-border-revenue" : "glow-border";
  return (
    <GlassPanel className={`p-4 ${glowClass}`}>
      <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-2">{label}</p>
      {children}
    </GlassPanel>
  );
}

function Connector() {
  return (
    <div className="flex justify-center">
      <div className="w-px h-4 bg-gradient-to-b from-forge-accent/60 to-transparent" />
    </div>
  );
}

function EmptyNote({ text }: { text: string }) {
  return <p className="text-xs text-neutral-600">{text}</p>;
}
