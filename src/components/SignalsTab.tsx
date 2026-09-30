import React, { useState } from 'react';
import { 
  Radio, 
  Search, 
  Filter, 
  Plus, 
  Tag, 
  Calendar, 
  ExternalLink, 
  Sparkles,
  CheckCircle,
  AlertTriangle
} from 'lucide-react';
import { Signal } from '../types';

interface SignalsTabProps {
  signals: Signal[];
  onAddSignal: (signalData: Partial<Signal>) => Promise<void>;
}

export const SignalsTab: React.FC<SignalsTabProps> = ({ signals, onAddSignal }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSource, setSelectedSource] = useState('all');
  const [selectedType, setSelectedType] = useState('all');
  const [minImportance, setMinImportance] = useState(0);
  const [showAddModal, setShowAddModal] = useState(false);

  // New Signal Form State
  const [content, setContent] = useState('');
  const [source, setSource] = useState('nepal_education_consultancy');
  const [category, setCategory] = useState('education abroad');
  const [signalType, setSignalType] = useState<'demand' | 'supply' | 'regulatory' | 'market_gap'>('demand');
  const [importanceScore, setImportanceScore] = useState(80);
  const [tagsInput, setTagsInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sources = Array.from(new Set(signals.map(s => s.source)));
  const types = ['demand', 'supply', 'regulatory', 'market_gap'];

  const filteredSignals = signals.filter(sig => {
    const matchesSearch = sig.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sig.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sig.tags.some(t => t.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesSource = selectedSource === 'all' || sig.source === selectedSource;
    const matchesType = selectedType === 'all' || sig.signal_type === selectedType;
    const matchesImportance = sig.importance_score >= minImportance;

    return matchesSearch && matchesSource && matchesType && matchesImportance;
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    setIsSubmitting(true);
    try {
      await onAddSignal({
        content,
        source,
        category,
        signal_type: signalType,
        importance_score: importanceScore,
        tags: tagsInput.split(',').map(t => t.trim()).filter(Boolean),
        reliability_score: 90,
        quality_score: 85,
        freshness_score: 100,
      });
      setContent('');
      setTagsInput('');
      setShowAddModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Radio className="w-5 h-5 text-blue-400" />
            Market Signals &amp; Demand Observations
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Raw economic inputs collected from public forums, licensed consultancies, and regulatory updates.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          Ingest Signal
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search content, categories, tags..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Source Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Sources ({signals.length})</option>
              {sources.map(src => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-blue-500 capitalize"
          >
            <option value="all">All Signal Types</option>
            {types.map(t => (
              <option key={t} value={t}>{t.replace('_', ' ')}</option>
            ))}
          </select>
        </div>

        {/* Importance slider */}
        <div className="flex items-center gap-3 pt-1 border-t border-slate-800/80 text-xs text-slate-400">
          <span>Min Importance: <strong className="text-blue-400 font-mono">{minImportance}</strong></span>
          <input
            type="range"
            min="0"
            max="100"
            value={minImportance}
            onChange={(e) => setMinImportance(parseInt(e.target.value, 10))}
            className="w-32 accent-blue-500 h-1 bg-slate-800 rounded"
          />
          <span className="text-[11px] text-slate-500 ml-auto">
            Showing {filteredSignals.length} of {signals.length} signals
          </span>
        </div>
      </div>

      {/* Signals List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredSignals.map((sig) => (
          <div 
            key={sig.id}
            className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="font-mono text-[10px] text-slate-500">ID #{sig.id}</span>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                  sig.signal_type === 'demand' 
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                    : sig.signal_type === 'regulatory'
                    ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                }`}>
                  {sig.signal_type.replace('_', ' ')}
                </span>
              </div>

              <p className="text-xs font-medium text-slate-200 leading-relaxed mb-3">
                {sig.content}
              </p>

              <div className="flex flex-wrap gap-1.5 mb-3">
                {sig.tags.map((tag, i) => (
                  <span key={i} className="text-[10px] bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-slate-400">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800/80 space-y-2">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/50">
                  <span className="text-[9px] text-slate-500 block uppercase">Importance</span>
                  <span className="text-xs font-mono font-bold text-blue-400">{sig.importance_score}%</span>
                </div>
                <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/50">
                  <span className="text-[9px] text-slate-500 block uppercase">Reliability</span>
                  <span className="text-xs font-mono font-bold text-emerald-400">{sig.reliability_score}%</span>
                </div>
                <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/50">
                  <span className="text-[9px] text-slate-500 block uppercase">Quality</span>
                  <span className="text-xs font-mono font-bold text-indigo-400">{sig.quality_score}%</span>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Source: <strong className="text-slate-400">{sig.source}</strong></span>
                <span>{new Date(sig.timestamp).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Ingest Signal Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Radio className="w-4 h-4 text-blue-400" />
                Ingest New Market Signal
              </h3>
              <button 
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-200 text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Observation / Content *
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="Describe the demand signal, pain point, or observation..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Source
                  </label>
                  <input
                    type="text"
                    required
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Category
                  </label>
                  <input
                    type="text"
                    required
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Signal Type
                  </label>
                  <select
                    value={signalType}
                    onChange={(e) => setSignalType(e.target.value as any)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500 capitalize"
                  >
                    {types.map(t => (
                      <option key={t} value={t}>{t.replace('_', ' ')}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Importance Score ({importanceScore}%)
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    value={importanceScore}
                    onChange={(e) => setImportanceScore(parseInt(e.target.value, 10))}
                    className="w-full mt-2 accent-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Tags (comma separated)
                </label>
                <input
                  type="text"
                  placeholder="nepal, consultancy, intake, documentation"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-1.5 text-xs text-slate-400 hover:text-slate-200 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Ingesting...' : 'Ingest Signal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
