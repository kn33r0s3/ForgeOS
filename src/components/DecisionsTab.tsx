import React from 'react';
import { Activity, CheckCircle2, FileText, TrendingUp } from 'lucide-react';
import type { Decision, ExecutionAction, Outcome } from '../types';

interface DecisionsTabProps {
  decisions: Decision[];
  actions: ExecutionAction[];
  outcomes: Outcome[];
}

function EmptyState({ label }: { label: string }) {
  return <div className="rounded-xl border border-dashed border-slate-800 p-6 text-center text-xs text-slate-500">{label}</div>;
}

export const DecisionsTab: React.FC<DecisionsTabProps> = ({ decisions, actions, outcomes }) => (
  <div className="space-y-6">
    <div>
      <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
        Decisions, Actions &amp; Outcomes
      </h2>
      <p className="text-xs text-slate-400 mt-0.5">
        These are separate persisted records. A decision or ready action is not evidence of execution or a business outcome.
      </p>
    </div>

    <section className="space-y-3">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-blue-400" />
        Decisions ({decisions.length})
      </h3>
      {decisions.length === 0 ? <EmptyState label="No decisions were returned by the backend." /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {decisions.map((decision) => (
            <article key={decision.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[10px] font-mono text-slate-500">DECISION #{decision.id}</span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300">{decision.status}</span>
                </div>
                <h4 className="text-xs font-bold text-slate-200 leading-snug mb-1">{decision.title}</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">{decision.rationale}</p>
              </div>
              <div className="pt-3 border-t border-slate-800/80 mt-3 flex items-center justify-between text-[11px] text-slate-500">
                <span>{decision.opportunity_id === null ? 'No linked opportunity' : `Opportunity #${decision.opportunity_id}`}</span>
                <time dateTime={decision.created_at}>{new Date(decision.created_at).toLocaleDateString()}</time>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>

    <section className="space-y-3 pt-3">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-amber-400" />
        Action records ({actions.length})
      </h3>
      <p className="text-[11px] text-slate-500">Action records show their stored policy and approval state; they do not prove execution.</p>
      {actions.length === 0 ? <EmptyState label="No action records were returned by the backend." /> : (
        <div className="space-y-3">
          {actions.map((action) => (
            <article key={action.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                <div>
                  <span className="text-[10px] font-mono text-slate-500">ACTION #{action.id} · {action.action_type}</span>
                  <p className="text-xs font-semibold text-slate-100 mt-1">{action.action}</p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">{action.status}</span>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-slate-400">
                <span>Scope: {action.data_scope}</span>
                <span>Owner approval required: {action.requires_owner_approval ? 'Yes' : 'No'}</span>
                {action.policy_decision && <span>Policy: {action.policy_decision}</span>}
              </div>
              {action.policy_reason && <p className="text-[11px] text-slate-500">{action.policy_reason}</p>}
            </article>
          ))}
        </div>
      )}
    </section>

    <section className="space-y-3 pt-3">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
        <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
        Recorded outcomes ({outcomes.length})
      </h3>
      {outcomes.length === 0 ? <EmptyState label="No outcome records were returned by the backend." /> : (
        <div className="space-y-3">
          {outcomes.map((outcome) => (
            <article key={outcome.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2.5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono text-slate-500">
                    OUTCOME #{outcome.id}{outcome.action_id === null ? '' : ` · ACTION #${outcome.action_id}`}
                  </span>
                  <p className="text-xs font-semibold text-slate-100 mt-1">{outcome.qualitative_result || outcome.outcome_type}</p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">{outcome.label}</span>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-slate-400">
                <span>Type: {outcome.outcome_type}</span>
                <span>Scope: {outcome.data_scope}</span>
                {outcome.actual_value !== null && (
                  <span>Recorded actual: {outcome.actual_value.toLocaleString()}{outcome.unit ? ` ${outcome.unit}` : ''}</span>
                )}
                {outcome.success !== null && <span>Success recorded: {outcome.success ? 'Yes' : 'No'}</span>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>

    <div className="flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-[11px] text-slate-500">
      <FileText className="w-4 h-4 shrink-0 text-slate-400" />
      <span>Only the canonical outcome ledger can support actual result claims. No action is initiated from this screen.</span>
    </div>
  </div>
);
