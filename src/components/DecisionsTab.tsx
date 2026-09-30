import React, { useState } from 'react';
import { 
  CheckCircle2, 
  Clock, 
  ShieldCheck, 
  AlertTriangle, 
  Plus, 
  FileText,
  DollarSign,
  TrendingUp,
  Activity
} from 'lucide-react';
import { Decision, Execution } from '../types';

interface DecisionsTabProps {
  decisions: Decision[];
  executions: Execution[];
  onAddDecision: (decData: Partial<Decision>) => Promise<void>;
  onAddExecution: (execData: Partial<Execution>) => Promise<void>;
}

export const DecisionsTab: React.FC<DecisionsTabProps> = ({
  decisions,
  executions,
  onAddDecision,
  onAddExecution,
}) => {
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [showExecutionModal, setShowExecutionModal] = useState(false);
  const [selectedDecisionId, setSelectedDecisionId] = useState<number>(decisions[0]?.id || 201);

  // New Decision Form
  const [action, setAction] = useState('');
  const [justification, setJustification] = useState('');
  const [riskLevel, setRiskLevel] = useState<'low' | 'medium' | 'high'>('low');
  const [standingAuth, setStandingAuth] = useState(false);

  // New Execution Form
  const [outcome, setOutcome] = useState('');
  const [actualCost, setActualCost] = useState('0');
  const [revenueGen, setRevenueGen] = useState('0');
  const [honestNotes, setHonestNotes] = useState('');

  const handleDecisionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!action.trim()) return;
    await onAddDecision({
      action,
      justification,
      risk_level: riskLevel,
      standing_authorization: standingAuth,
      status: 'recommended',
      opportunity_id: 101,
    });
    setAction('');
    setJustification('');
    setShowDecisionModal(false);
  };

  const handleExecutionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!outcome.trim()) return;
    await onAddExecution({
      decision_id: selectedDecisionId,
      outcome,
      actual_cost: parseInt(actualCost, 10) || 0,
      revenue_generated: parseInt(revenueGen, 10) || 0,
      honest_notes: honestNotes,
      status: 'completed',
    });
    setOutcome('');
    setHonestNotes('');
    setShowExecutionModal(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            Decisions &amp; Execution Ledger
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Decisions take authorized real-world actions. Standing authorization executes within scope limits.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDecisionModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            Propose Decision
          </button>
          <button
            onClick={() => setShowExecutionModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            Record Execution
          </button>
        </div>
      </div>

      {/* Decisions List */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-blue-400" />
          Authorized Decisions
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {decisions.map((dec) => (
            <div key={dec.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[10px] font-mono text-slate-500">DECISION #{dec.id}</span>
                  <div className="flex items-center gap-1.5">
                    {dec.standing_authorization && (
                      <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full flex items-center gap-1 font-mono">
                        <ShieldCheck className="w-3 h-3" /> Standing Auth
                      </span>
                    )}
                    <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded ${
                      dec.status === 'executed' ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-800 text-slate-300'
                    }`}>
                      {dec.status}
                    </span>
                  </div>
                </div>

                <h4 className="text-xs font-bold text-slate-200 leading-snug mb-1">
                  {dec.action}
                </h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {dec.justification}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-800/80 mt-3 flex items-center justify-between text-[11px] text-slate-500">
                <span className="capitalize">Risk: <strong className={dec.risk_level === 'low' ? 'text-emerald-400' : 'text-amber-400'}>{dec.risk_level}</strong></span>
                <span>{new Date(dec.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Executions Log */}
      <div className="space-y-3 pt-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
          Execution Outcomes &amp; Honest Evidence
        </h3>

        <div className="space-y-3">
          {executions.map((exec) => (
            <div key={exec.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-slate-700/80 transition space-y-2.5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono text-slate-500">EXEC #{exec.id} • Decision #{exec.decision_id}</span>
                  <p className="text-xs font-semibold text-slate-100 mt-1">
                    {exec.outcome}
                  </p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  {exec.status}
                </span>
              </div>

              <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 text-xs">
                <span className="text-[10px] text-slate-500 block uppercase font-medium">Honest Evidence Note</span>
                <span className="text-slate-300 italic">{exec.honest_notes}</span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs pt-1 border-t border-slate-800/80">
                <div>
                  <span className="text-slate-500">Actual Out-of-Pocket Cost:</span>
                  <span className="font-mono text-slate-200 ml-2">NPR {exec.actual_cost}</span>
                </div>
                <div>
                  <span className="text-slate-500">Revenue Generated:</span>
                  <span className="font-mono text-emerald-400 font-semibold ml-2">NPR {exec.revenue_generated}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Decision Modal */}
      {showDecisionModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100">Propose Decision Action</h3>
              <button onClick={() => setShowDecisionModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>
            <form onSubmit={handleDecisionSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">Action Description *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="Specify authorized real-world action..."
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">Economic Justification</label>
                <input
                  type="text"
                  placeholder="Why does this drive owner dependency to zero?"
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">Risk Level</label>
                  <select
                    value={riskLevel}
                    onChange={(e) => setRiskLevel(e.target.value as any)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    <option value="low">Low Risk</option>
                    <option value="medium">Medium Risk</option>
                    <option value="high">High Risk</option>
                  </select>
                </div>
                <div className="flex items-center gap-2 pt-5">
                  <input
                    type="checkbox"
                    id="standingAuthCheck"
                    checked={standingAuth}
                    onChange={(e) => setStandingAuth(e.target.checked)}
                    className="accent-emerald-500 rounded"
                  />
                  <label htmlFor="standingAuthCheck" className="text-xs text-slate-300">
                    Standing Authorization
                  </label>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button type="button" onClick={() => setShowDecisionModal(false)} className="px-3.5 py-1.5 text-xs text-slate-400">Cancel</button>
                <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow-sm">Save Decision</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Execution Modal */}
      {showExecutionModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100">Record Execution Outcome</h3>
              <button onClick={() => setShowExecutionModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>
            <form onSubmit={handleExecutionSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">Target Decision</label>
                <select
                  value={selectedDecisionId}
                  onChange={(e) => setSelectedDecisionId(parseInt(e.target.value, 10))}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  {decisions.map(d => (
                    <option key={d.id} value={d.id}>Decision #{d.id}: {d.action.slice(0, 45)}...</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">Outcome *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="What specifically happened in the real world?"
                  value={outcome}
                  onChange={(e) => setOutcome(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">Honest Evidence Notes *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="Record fact without exaggeration (e.g. 3 of 5 responded, no deposit yet)"
                  value={honestNotes}
                  onChange={(e) => setHonestNotes(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">Actual Cost (NPR)</label>
                  <input
                    type="number"
                    value={actualCost}
                    onChange={(e) => setActualCost(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">Revenue Generated (NPR)</label>
                  <input
                    type="number"
                    value={revenueGen}
                    onChange={(e) => setRevenueGen(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button type="button" onClick={() => setShowExecutionModal(false)} className="px-3.5 py-1.5 text-xs text-slate-400">Cancel</button>
                <button type="submit" className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-sm">Record Outcome</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
