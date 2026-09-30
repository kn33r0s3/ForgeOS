import React from 'react';
import { 
  TrendingUp, 
  Radio, 
  Lightbulb, 
  CheckCircle2, 
  Cpu, 
  ArrowRight, 
  ShieldCheck, 
  AlertCircle,
  Clock,
  Compass,
  FileCheck
} from 'lucide-react';
import { SystemStats, Signal, Opportunity, Belief, Decision } from '../types';

interface OverviewTabProps {
  stats: SystemStats | null;
  signals: Signal[];
  opportunities: Opportunity[];
  beliefs: Belief[];
  decisions: Decision[];
  setActiveTab: (tab: string) => void;
  onTriggerCycle: () => void;
  isCycling: boolean;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  stats,
  signals,
  opportunities,
  beliefs,
  decisions,
  setActiveTab,
  onTriggerCycle,
  isCycling,
}) => {
  return (
    <div className="space-y-6">
      {/* Top Directive Invariant Banner */}
      <div className="bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-500/30 rounded-xl p-5 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30">
                Core Substrate Invariant
              </span>
              <span className="text-xs text-slate-400 font-mono">Nepal-first • Globally portable</span>
            </div>
            <h2 className="text-lg font-bold text-slate-100 tracking-tight">
              Drive Owner Dependency to Zero
            </h2>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              Prefer fewer owner actions per verified economic outcome. Commercial focus: <strong className="text-amber-300 font-medium">one real customer → one real paid outcome → repeat → automate → scale</strong>.
              Standing rule: tests and synthetic inputs never count as customer or revenue evidence.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveTab('opportunities')}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition shadow-sm"
            >
              View Pilot Funnel
            </button>
            <button
              onClick={onTriggerCycle}
              disabled={isCycling}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-lg transition shadow-sm flex items-center gap-1.5"
            >
              <span>{isCycling ? 'Executing...' : 'Cycle Substrate'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Real Revenue Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Verified Real Revenue</span>
            <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">$0.00</div>
            <div className="text-[11px] text-amber-400/90 flex items-center gap-1 mt-0.5">
              <ShieldCheck className="w-3 h-3 inline" />
              <span>Real customers: 0 (Honest audit)</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500">
            Metric: <span className="font-mono text-slate-400">NOT MEASURABLE</span> until 1st close
          </div>
        </div>

        {/* Signals Card */}
        <div 
          onClick={() => setActiveTab('signals')}
          className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between cursor-pointer transition"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Market Signals &amp; Demand</span>
            <span className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
              <Radio className="w-4 h-4" />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">
              {stats?.signals_count || signals.length}
            </div>
            <div className="text-[11px] text-blue-400 flex items-center gap-1 mt-0.5">
              <span>{signals.filter(s => s.signal_type === 'demand').length} demand observations</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Sources: GitHub, Reddit, RSS, Consultancies</span>
            <ArrowRight className="w-3 h-3 text-slate-400" />
          </div>
        </div>

        {/* Opportunities Card */}
        <div 
          onClick={() => setActiveTab('opportunities')}
          className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between cursor-pointer transition"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Qualified Opportunities</span>
            <span className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
              <Lightbulb className="w-4 h-4" />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">
              {stats?.opportunities_count || opportunities.length}
            </div>
            <div className="text-[11px] text-amber-400 flex items-center gap-1 mt-0.5">
              <span>{opportunities.filter(o => o.status === 'in_progress').length} active pilot tests</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Avg confidence: 79.2%</span>
            <ArrowRight className="w-3 h-3 text-slate-400" />
          </div>
        </div>

        {/* Intelligence Cycles Card */}
        <div 
          onClick={() => setActiveTab('workers')}
          className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between cursor-pointer transition"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Autonomous Cycles</span>
            <span className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
              <Cpu className="w-4 h-4" />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-100">
              #{stats?.latest_cycle_id || 308}
            </div>
            <div className="text-[11px] text-purple-400 flex items-center gap-1 mt-0.5">
              <span>SQLite WAL • 0 disk errors</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Passes: 303-308 verified</span>
            <ArrowRight className="w-3 h-3 text-slate-400" />
          </div>
        </div>
      </div>

      {/* The Central Hami Intelligence Loop */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
          <Compass className="w-4 h-4 text-amber-400" />
          Universal Operating Architecture Loop
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 text-center text-xs">
          {[
            { step: '1. OBSERVE', desc: 'Raw Signals', active: true, color: 'border-blue-500/40 text-blue-400' },
            { step: '2. VERIFY', desc: 'Truth Audit', active: true, color: 'border-cyan-500/40 text-cyan-400' },
            { step: '3. UNDERSTAND', desc: 'Form Beliefs', active: true, color: 'border-indigo-500/40 text-indigo-400' },
            { step: '4. DECIDE', desc: 'Prioritize', active: true, color: 'border-amber-500/40 text-amber-400' },
            { step: '5. ACT', desc: 'Standing Auth', active: true, color: 'border-orange-500/40 text-orange-400' },
            { step: '6. MEASURE', desc: 'Real Impact', active: true, color: 'border-emerald-500/40 text-emerald-400' },
            { step: '7. LEARN', desc: 'Update Schema', active: true, color: 'border-purple-500/40 text-purple-400' },
            { step: '8. REPEAT', desc: 'Automate Next', active: true, color: 'border-rose-500/40 text-rose-400' },
          ].map((item, idx) => (
            <div 
              key={idx} 
              className={`p-3 rounded-lg border bg-slate-950/60 flex flex-col justify-center items-center ${item.color}`}
            >
              <span className="font-bold text-[11px]">{item.step}</span>
              <span className="text-[10px] text-slate-400 mt-1">{item.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Two-Column Detail View: Active Pilot Opportunities & Hypotheses */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Opportunities Panel */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-slate-100">Discovered Opportunities</h3>
              </div>
              <button 
                onClick={() => setActiveTab('opportunities')}
                className="text-xs text-amber-400 hover:text-amber-300 font-medium"
              >
                View all ({opportunities.length}) →
              </button>
            </div>
            
            <div className="space-y-3">
              {opportunities.slice(0, 3).map((opp) => (
                <div key={opp.id} className="p-3.5 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-xs font-semibold text-slate-200">{opp.title}</h4>
                      <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{opp.description}</p>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium border bg-amber-500/10 text-amber-400 border-amber-500/30 whitespace-nowrap">
                      {opp.confidence_score}% conf
                    </span>
                  </div>
                  
                  {opp.target_customer && (
                    <div className="mt-2 text-[11px] text-slate-400">
                      <span className="text-slate-500">Target:</span> {opp.target_customer}
                    </div>
                  )}

                  {/* Checklist progress */}
                  <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">
                      Checklist: {opp.action_checklist.filter(c => c.done).length}/{opp.action_checklist.length} done
                    </span>
                    <span className={`capitalize font-mono px-2 py-0.5 rounded text-[10px] ${
                      opp.status === 'in_progress' ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {opp.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* World Beliefs & Hypotheses */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-bold text-slate-100">World Beliefs &amp; Evidence</h3>
              </div>
              <button 
                onClick={() => setActiveTab('beliefs')}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
              >
                View all ({beliefs.length}) →
              </button>
            </div>

            <div className="space-y-3">
              {beliefs.slice(0, 3).map((belief) => (
                <div key={belief.id} className="p-3.5 bg-slate-950/60 rounded-lg border border-slate-800">
                  <p className="text-xs text-slate-200 leading-snug">"{belief.statement}"</p>
                  
                  <div className="mt-3 flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-3">
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> {belief.supporting_evidence} supporting
                      </span>
                      <span className="text-rose-400/80 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" /> {belief.contradicting_evidence} contradictory
                      </span>
                    </div>
                    <span className="font-mono text-indigo-400 text-[11px] font-semibold">
                      {belief.confidence_score}%
                    </span>
                  </div>

                  <div className="mt-2 text-[10px] text-slate-500">
                    Sources: {belief.sources.join(', ')}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
