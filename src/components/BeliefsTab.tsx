import React from 'react';
import { FileCheck, HelpCircle, Layers } from 'lucide-react';
import type { Belief } from '../types';

interface BeliefsTabProps {
  beliefs: Belief[];
}

export const BeliefsTab: React.FC<BeliefsTabProps> = ({ beliefs }) => (
  <div className="space-y-5">
    <div>
      <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
        <FileCheck className="w-5 h-5 text-indigo-400" />
        World Beliefs &amp; Epistemic Hypotheses
      </h2>
      <p className="text-xs text-slate-400 mt-0.5">
        Persisted beliefs from the canonical backend. Confidence is a stored estimate, not independent verification.
      </p>
    </div>

    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
      <div className="flex items-start gap-2.5">
        <FileCheck className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
        <div><strong className="text-slate-200 block">What is recorded?</strong><span className="text-slate-400">The belief statement and stored confidence value.</span></div>
      </div>
      <div className="flex items-start gap-2.5">
        <Layers className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
        <div><strong className="text-slate-200 block">What is linked?</strong><span className="text-slate-400">Supporting signal IDs returned by the belief endpoint.</span></div>
      </div>
      <div className="flex items-start gap-2.5">
        <HelpCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <div><strong className="text-slate-200 block">What is not shown?</strong><span className="text-slate-400">This endpoint does not return a contradiction count.</span></div>
      </div>
    </div>

    {beliefs.length === 0 ? (
      <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-500">
        The backend returned no persisted beliefs.
      </div>
    ) : (
      <div className="space-y-4">
        {beliefs.map((belief) => (
          <article key={belief.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700/80 transition space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <span className="text-[10px] font-mono text-slate-500">BELIEF #{belief.id}</span>
                <p className="text-sm font-semibold text-slate-100 leading-snug">{belief.statement}</p>
              </div>
              <div className="text-right shrink-0">
                <div className="text-base font-bold font-mono text-indigo-400">{belief.confidence_score}%</div>
                <div className="text-[10px] text-slate-500 uppercase tracking-wider">Stored confidence</div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800/80 text-xs">
              <span className="text-slate-500">Supporting signal IDs: </span>
              <span className="text-slate-300">{belief.supporting_signal_ids || 'None linked in this response'}</span>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <span>Created: {new Date(belief.created_at).toLocaleDateString()}</span>
              <span>Last updated: {new Date(belief.last_updated).toLocaleDateString()}</span>
            </div>
          </article>
        ))}
      </div>
    )}
  </div>
);
