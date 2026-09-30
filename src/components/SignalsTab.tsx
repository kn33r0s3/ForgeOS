import React, { useMemo, useState } from 'react';
import { Filter, Plus, Radio, Search } from 'lucide-react';
import { parseTags } from '../lib/forgeApi';
import type { Signal } from '../types';

interface SignalsTabProps {
  signals: Signal[];
  totalSignals: number;
  onAddSignal: (observation: { content: string; source: string }) => Promise<void>;
}

function scoreLabel(value: number | null): string {
  return value === null ? '—' : `${value}%`;
}

export const SignalsTab: React.FC<SignalsTabProps> = ({ signals, totalSignals, onAddSignal }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSource, setSelectedSource] = useState('all');
  const [selectedType, setSelectedType] = useState('all');
  const [minImportance, setMinImportance] = useState(0);
  const [showAddModal, setShowAddModal] = useState(false);
  const [content, setContent] = useState('');
  const [source, setSource] = useState('manual');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const sources = useMemo(() => Array.from(new Set(signals.map((signal) => signal.source))).sort(), [signals]);
  const types = useMemo(
    () => Array.from(new Set(signals.map((signal) => signal.signal_type ?? 'unclassified'))).sort(),
    [signals],
  );

  const filteredSignals = signals.filter((signal) => {
    const tags = parseTags(signal.tags);
    const query = searchTerm.toLowerCase();
    const matchesSearch = signal.content.toLowerCase().includes(query)
      || (signal.category ?? '').toLowerCase().includes(query)
      || tags.some((tag) => tag.toLowerCase().includes(query));
    const matchesSource = selectedSource === 'all' || signal.source === selectedSource;
    const matchesType = selectedType === 'all' || (signal.signal_type ?? 'unclassified') === selectedType;
    return matchesSearch && matchesSource && matchesType && signal.importance_score >= minImportance;
  });

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;
    setIsSubmitting(true);
    setSubmissionError(null);
    try {
      await onAddSignal({ content: content.trim(), source: source.trim() || 'manual' });
      setContent('');
      setSource('manual');
      setShowAddModal(false);
    } catch (error) {
      setSubmissionError(error instanceof Error ? error.message : 'The observation could not be recorded');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Radio className="w-5 h-5 text-blue-400" />
            Signals &amp; Demand Observations
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            The backend returns the 200 newest stored observations here. Observer scores do not independently verify a claim.
          </p>
        </div>
        <button
          onClick={() => { setSubmissionError(null); setShowAddModal(true); }}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          Record Observation
        </button>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search content, categories, tags..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <select
              value={selectedSource}
              onChange={(event) => setSelectedSource(event.target.value)}
              className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-2"
            >
              <option value="all">All Returned Sources ({signals.length})</option>
              {sources.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <select
            value={selectedType}
            onChange={(event) => setSelectedType(event.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-2 capitalize"
          >
            <option value="all">All Signal Types</option>
            {types.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-3 pt-1 border-t border-slate-800/80 text-xs text-slate-400">
          <span>Minimum importance: <strong className="text-blue-400 font-mono">{minImportance}</strong></span>
          <input
            type="range"
            min="0"
            max="100"
            value={minImportance}
            onChange={(event) => setMinImportance(Number(event.target.value))}
            className="w-32 accent-blue-500 h-1 bg-slate-800 rounded"
          />
          <span className="text-[11px] text-slate-500 ml-auto">
            Showing {filteredSignals.length} of {signals.length} returned · {totalSignals.toLocaleString()} stored total
          </span>
        </div>
      </div>

      {filteredSignals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-500">
          {signals.length === 0 ? 'The backend returned no signals.' : 'No signals match these filters.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSignals.map((signal) => (
            <article key={signal.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="font-mono text-[10px] text-slate-500">ID #{signal.id}</span>
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border bg-blue-500/10 text-blue-300 border-blue-500/30">
                    {signal.signal_type?.replaceAll('_', ' ') ?? 'unclassified'}
                  </span>
                </div>
                <p className="text-xs font-medium text-slate-200 leading-relaxed mb-3">{signal.content}</p>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {parseTags(signal.tags).map((tag, index) => (
                    <span key={`${tag}-${index}`} className="text-[10px] bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-slate-400">#{tag}</span>
                  ))}
                </div>
              </div>
              <div className="pt-3 border-t border-slate-800/80 space-y-2">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/50">
                    <span className="text-[9px] text-slate-500 block uppercase">Importance</span>
                    <span className="text-xs font-mono font-bold text-blue-400">{scoreLabel(signal.importance_score)}</span>
                  </div>
                  <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/50">
                    <span className="text-[9px] text-slate-500 block uppercase">Source reliability</span>
                    <span className="text-xs font-mono font-bold text-emerald-400">{scoreLabel(signal.reliability_score)}</span>
                  </div>
                  <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/50">
                    <span className="text-[9px] text-slate-500 block uppercase">Quality</span>
                    <span className="text-xs font-mono font-bold text-indigo-400">{scoreLabel(signal.quality_score)}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>Source: <strong className="text-slate-400">{signal.source}</strong>{signal.category && ` · ${signal.category}`}</span>
                  <time dateTime={signal.timestamp}>{new Date(signal.timestamp).toLocaleDateString()}</time>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Radio className="w-4 h-4 text-blue-400" />
                Record an Observation
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-slate-200" aria-label="Close">×</button>
            </div>
            <p className="text-[11px] text-amber-300/90">
              This records what you observed; it does not verify the statement or create a customer, outcome, or revenue record.
            </p>
            <form onSubmit={handleSubmit} className="space-y-3">
              <label className="block text-[11px] font-semibold text-slate-400">
                Observation / content *
                <textarea
                  rows={4}
                  required
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  className="mt-1 w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </label>
              <label className="block text-[11px] font-semibold text-slate-400">
                Source label
                <input
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                  className="mt-1 w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </label>
              {submissionError && <p role="alert" className="text-xs text-rose-300">{submissionError}</p>}
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button type="button" onClick={() => setShowAddModal(false)} className="px-3.5 py-1.5 text-xs text-slate-400">Cancel</button>
                <button type="submit" disabled={isSubmitting} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg disabled:opacity-50">
                  {isSubmitting ? 'Recording…' : 'Record Observation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
