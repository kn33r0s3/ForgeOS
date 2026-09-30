import React, { useMemo, useState } from 'react';
import { Filter, Lightbulb, Search } from 'lucide-react';
import type { Opportunity } from '../types';

interface OpportunitiesTabProps {
  opportunities: Opportunity[];
}

function recordedAmount(value: number | null): string {
  return value === null ? 'Not recorded' : value.toLocaleString();
}

export const OpportunitiesTab: React.FC<OpportunitiesTabProps> = ({ opportunities }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const statuses = useMemo(
    () => Array.from(new Set(opportunities.map((opportunity) => opportunity.status))).sort(),
    [opportunities],
  );

  const filteredOpportunities = opportunities.filter((opportunity) => {
    const query = searchTerm.toLowerCase();
    const matchesSearch = opportunity.problem.toLowerCase().includes(query)
      || opportunity.solution.toLowerCase().includes(query)
      || opportunity.target_customer.toLowerCase().includes(query);
    return matchesSearch && (selectedStatus === 'all' || opportunity.status === selectedStatus);
  });

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-amber-400" />
          Persisted Opportunities
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Read-only projection of opportunity records. Estimates are not revenue; customer validation and status changes are not inferred here.
        </p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search problem, solution, target customer..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <select
            value={selectedStatus}
            onChange={(event) => setSelectedStatus(event.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-2 capitalize"
          >
            <option value="all">All returned statuses ({opportunities.length})</option>
            {statuses.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}
          </select>
        </div>
      </div>

      {filteredOpportunities.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-500">
          {opportunities.length === 0 ? 'The backend returned no opportunity records.' : 'No opportunities match these filters.'}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredOpportunities.map((opportunity) => (
            <article key={opportunity.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700/80 transition space-y-4 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-slate-500">OPPORTUNITY #{opportunity.id}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium border bg-amber-500/10 text-amber-400 border-amber-500/30">
                      {opportunity.status.replaceAll('_', ' ')}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">{opportunity.problem}</h3>
                  {opportunity.solution && <p className="text-xs text-slate-300 leading-relaxed max-w-4xl">{opportunity.solution}</p>}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800/60 text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Target customer</span>
                  <span className="text-slate-200 font-medium">{opportunity.target_customer || 'Not recorded'}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Business model</span>
                  <span className="text-slate-200 font-medium">{opportunity.business_model || 'Not recorded'}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Estimated revenue · 30 days</span>
                  <span className="text-slate-200 font-mono">{recordedAmount(opportunity.estimated_revenue_30d)}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Estimated startup cost</span>
                  <span className="text-slate-200 font-mono">{recordedAmount(opportunity.estimated_startup_cost)}</span>
                </div>
              </div>

              {(opportunity.market_analysis || opportunity.mvp_plan || opportunity.validation_plan) && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  {opportunity.market_analysis && (
                    <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/60">
                      <span className="text-[10px] text-slate-500 block uppercase font-medium mb-1">Market analysis</span>
                      <p className="text-slate-300 whitespace-pre-wrap">{opportunity.market_analysis}</p>
                    </div>
                  )}
                  {opportunity.mvp_plan && (
                    <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/60">
                      <span className="text-[10px] text-slate-500 block uppercase font-medium mb-1">MVP plan</span>
                      <p className="text-slate-300 whitespace-pre-wrap">{opportunity.mvp_plan}</p>
                    </div>
                  )}
                  {opportunity.validation_plan && (
                    <div className="bg-slate-950/40 p-3 rounded-lg border border-slate-800/60">
                      <span className="text-[10px] text-slate-500 block uppercase font-medium mb-1">Validation plan</span>
                      <p className="text-slate-300 whitespace-pre-wrap">{opportunity.validation_plan}</p>
                    </div>
                  )}
                </div>
              )}

              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
                <span>Created: {new Date(opportunity.created_at).toLocaleDateString()}</span>
                <span>Revenue fields are estimates only</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};
