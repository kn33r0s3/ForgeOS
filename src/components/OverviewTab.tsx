import React from 'react';
import {
  ArrowRight,
  Cpu,
  FileCheck,
  Lightbulb,
  Radio,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';
import type {
  Belief,
  Cycle,
  ObserverStats,
  Opportunity,
  Signal,
  SystemStats,
} from '../types';

interface OverviewTabProps {
  stats: SystemStats;
  observerStats: ObserverStats;
  latestCycle: Cycle | null;
  recentSignals: Signal[];
  opportunities: Opportunity[];
  beliefs: Belief[];
  setActiveTab: (tab: string) => void;
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-lg border border-dashed border-slate-800 p-4 text-xs text-slate-500">{label}</p>;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  stats,
  observerStats,
  latestCycle,
  recentSignals,
  opportunities,
  beliefs,
  setActiveTab,
}) => {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-500/30 rounded-xl p-5 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30">
                Core Substrate Invariant
              </span>
              <span className="text-xs text-slate-400 font-mono">Evidence before action</span>
            </div>
            <h2 className="text-lg font-bold text-slate-100 tracking-tight">Drive Owner Dependency Down</h2>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              Prefer fewer owner actions per verified economic outcome. Tests, synthetic inputs, and hypotheses do not count as customer or revenue evidence.
            </p>
          </div>
          <button
            onClick={() => setActiveTab('opportunities')}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition shadow-sm"
          >
            View Opportunities
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Verified revenue recorded</span>
            <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400"><TrendingUp className="w-4 h-4" /></span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">
              {observerStats.verified_revenue === null ? 'Not recorded' : observerStats.verified_revenue.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
              <ShieldCheck className="w-3 h-3" />
              {observerStats.outcomes_real === null ? 'Real outcome count unavailable' : `${observerStats.outcomes_real} verified real outcomes`}
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500">
            Owner interventions per real transaction: <span className="font-mono text-slate-300">NOT MEASURABLE</span>
          </div>
        </div>

        <button
          onClick={() => setActiveTab('signals')}
          className="text-left bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between transition"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Recorded Signals</span>
            <span className="p-2 rounded-lg bg-blue-500/10 text-blue-400"><Radio className="w-4 h-4" /></span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">{stats.total_signals.toLocaleString()}</div>
            <div className="text-[11px] text-blue-300 mt-0.5">
              {observerStats.high_importance_count.toLocaleString()} scored high importance by Observer
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Observer quality flags: {observerStats.low_quality_count.toLocaleString()}</span><ArrowRight className="w-3 h-3" />
          </div>
        </button>

        <button
          onClick={() => setActiveTab('opportunities')}
          className="text-left bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between transition"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Opportunity records</span>
            <span className="p-2 rounded-lg bg-amber-500/10 text-amber-400"><Lightbulb className="w-4 h-4" /></span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">{opportunities.length.toLocaleString()}</div>
            <div className="text-[11px] text-amber-300 mt-0.5">Actionable records returned by the Opportunity engine</div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Filtered by the canonical quality gate</span><ArrowRight className="w-3 h-3" />
          </div>
        </button>

        <button
          onClick={() => setActiveTab('workers')}
          className="text-left bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between transition"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Recorded Cycles</span>
            <span className="p-2 rounded-lg bg-purple-500/10 text-purple-400"><Cpu className="w-4 h-4" /></span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">
              {latestCycle ? `#${latestCycle.id}` : 'None'}
            </div>
            <div className="text-[11px] text-purple-300 mt-0.5">{latestCycle?.status ?? 'No cycle record returned'}</div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Latest cycle from persisted history</span><ArrowRight className="w-3 h-3" />
          </div>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-bold text-slate-100">Recent Signals</h3>
            </div>
            <button onClick={() => setActiveTab('signals')} className="text-xs text-blue-300 hover:text-blue-200">
              View all recent ({recentSignals.length}) →
            </button>
          </div>
          {recentSignals.length === 0 ? <EmptyState label="No signals were returned by the backend." /> : (
            <div className="space-y-3">
              {recentSignals.map((signal) => (
                <article key={signal.id} className="p-3.5 bg-slate-950/60 rounded-lg border border-slate-800">
                  <p className="text-xs text-slate-200 leading-snug">{signal.content}</p>
                  <div className="mt-2 flex justify-between gap-3 text-[11px] text-slate-500">
                    <span>{signal.source} · {signal.signal_type ?? 'unclassified'}</span>
                    <time dateTime={signal.timestamp}>{new Date(signal.timestamp).toLocaleDateString()}</time>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-bold text-slate-100">Persisted Beliefs</h3>
            </div>
            <button onClick={() => setActiveTab('beliefs')} className="text-xs text-indigo-300 hover:text-indigo-200">
              View all ({beliefs.length}) →
            </button>
          </div>
          {beliefs.length === 0 ? <EmptyState label="No beliefs were returned by the backend." /> : (
            <div className="space-y-3">
              {beliefs.slice(0, 3).map((belief) => (
                <article key={belief.id} className="p-3.5 bg-slate-950/60 rounded-lg border border-slate-800">
                  <p className="text-xs text-slate-200 leading-snug">{belief.statement}</p>
                  <div className="mt-2 flex justify-between text-[11px] text-slate-500">
                    <span>Belief #{belief.id}</span>
                    <span>Confidence {belief.confidence_score}%</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
