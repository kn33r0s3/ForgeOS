import React, { useState } from 'react';
import { 
  FileCheck, 
  CheckCircle2, 
  AlertCircle, 
  Plus, 
  ShieldCheck, 
  Layers,
  HelpCircle
} from 'lucide-react';
import { Belief } from '../types';

interface BeliefsTabProps {
  beliefs: Belief[];
  onAddBelief: (beliefData: Partial<Belief>) => Promise<void>;
}

export const BeliefsTab: React.FC<BeliefsTabProps> = ({ beliefs, onAddBelief }) => {
  const [showModal, setShowModal] = useState(false);
  const [statement, setStatement] = useState('');
  const [confidence, setConfidence] = useState(80);
  const [sourcesInput, setSourcesInput] = useState('interview, consultancy, market_signal');
  const [supportingEvidence, setSupportingEvidence] = useState(5);
  const [contradictingEvidence, setContradictingEvidence] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!statement.trim()) return;
    setIsSubmitting(true);
    try {
      await onAddBelief({
        statement,
        confidence_score: confidence,
        sources: sourcesInput.split(',').map(s => s.trim()).filter(Boolean),
        supporting_evidence: supportingEvidence,
        contradicting_evidence: contradictingEvidence,
      });
      setStatement('');
      setShowModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-indigo-400" />
            World Beliefs &amp; Epistemic Hypotheses
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Knowledge is explicitly labeled: <span className="font-mono text-indigo-300">OBSERVED / INFERRED / ESTIMATED / UNKNOWN / ACTUAL</span>.
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          Add Belief
        </button>
      </div>

      {/* Epistemic Criteria Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        <div className="flex items-start gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
          <div>
            <strong className="text-slate-200 block">What do we know?</strong>
            <span className="text-slate-400">Directly observed customer statements &amp; verified bank outcomes.</span>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <HelpCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
          <div>
            <strong className="text-slate-200 block">What contradicts it?</strong>
            <span className="text-slate-400">Actively logged contrary signals that reduce confidence.</span>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <Layers className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
          <div>
            <strong className="text-slate-200 block">How do we know?</strong>
            <span className="text-slate-400">Citing exact signal sources, not synthetic LLM assertions.</span>
          </div>
        </div>
      </div>

      {/* Beliefs List */}
      <div className="space-y-4">
        {beliefs.map((b) => (
          <div key={b.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700/80 transition space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <span className="text-[10px] font-mono text-slate-500">BELIEF #{b.id}</span>
                <p className="text-sm font-semibold text-slate-100 leading-snug">
                  "{b.statement}"
                </p>
              </div>

              <div className="text-right shrink-0">
                <div className="text-base font-bold font-mono text-indigo-400">{b.confidence_score}%</div>
                <div className="text-[10px] text-slate-500 uppercase tracking-wider">Confidence</div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-800/80 text-xs">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5 text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span className="font-semibold">{b.supporting_evidence}</span>
                  <span className="text-slate-500">supporting</span>
                </div>
                <div className="flex items-center gap-1.5 text-rose-400">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span className="font-semibold">{b.contradicting_evidence}</span>
                  <span className="text-slate-500">contradicting</span>
                </div>
              </div>

              <div className="text-slate-400 sm:text-right">
                <span className="text-slate-500">Sources:</span> {b.sources.join(' • ')}
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <span>Created: {new Date(b.created_at).toLocaleDateString()}</span>
              <span>Last update: {new Date(b.updated_at).toLocaleDateString()}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Add Belief Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-indigo-400" />
                Record Epistemic Belief
              </h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-slate-200">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Belief Statement *
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="State the hypothesis about the market or customer behavior..."
                  value={statement}
                  onChange={(e) => setStatement(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Confidence Score ({confidence}%)
                </label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  value={confidence}
                  onChange={(e) => setConfidence(parseInt(e.target.value, 10))}
                  className="w-full accent-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Supporting Evidence Count
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={supportingEvidence}
                    onChange={(e) => setSupportingEvidence(parseInt(e.target.value, 10) || 0)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Contradicting Evidence Count
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={contradictingEvidence}
                    onChange={(e) => setContradictingEvidence(parseInt(e.target.value, 10) || 0)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Sources (comma separated)
                </label>
                <input
                  type="text"
                  value={sourcesInput}
                  onChange={(e) => setSourcesInput(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3.5 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Recording...' : 'Record Belief'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
