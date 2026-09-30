import React, { useState } from 'react';
import { Terminal, Send, CheckCircle2, Copy, Check, RefreshCw } from 'lucide-react';

export const ApiExplorerTab: React.FC = () => {
  const [selectedEndpoint, setSelectedEndpoint] = useState('/api/health');
  const [responseJson, setResponseJson] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const endpoints = [
    { path: '/api/health', method: 'GET', description: 'Backend readiness and database availability' },
    { path: '/api/ai/status', method: 'GET', description: 'AI provider status & model readiness' },
    { path: '/api/stats', method: 'GET', description: 'Canonical signal, pattern, opportunity and experiment counts' },
    { path: '/api/observer/stats', method: 'GET', description: 'Observer counts and stored quality metrics' },
    { path: '/api/signals', method: 'GET', description: 'Persisted observations and Observer scores' },
    { path: '/api/opportunities', method: 'GET', description: 'Persisted opportunities and estimate fields' },
    { path: '/api/forge/beliefs', method: 'GET', description: 'Persisted beliefs and supporting signal IDs' },
    { path: '/api/forge/decisions', method: 'GET', description: 'Persisted decision records' },
    { path: '/api/forge/execution/actions', method: 'GET', description: 'Execution action records and approval state' },
    { path: '/api/forge/outcomes', method: 'GET', description: 'Recorded outcomes with REAL or SANDBOX scope' },
    { path: '/api/workers', method: 'GET', description: 'Persisted background worker tasks' },
    { path: '/api/forge/cycles', method: 'GET', description: 'Persisted cycle history' },
    { path: '/api/forge/experiments', method: 'GET', description: 'Persisted experiment records' },
    { path: '/api/forge/money/revenue-breakdown', method: 'GET', description: 'Potential, expected and realized values, kept separate' },
  ];

  const handleExecute = async (path: string) => {
    setLoading(true);
    setSelectedEndpoint(path);
    try {
      const res = await fetch(path, { headers: { Accept: 'application/json' } });
      setStatus(res.status);
      const body = await res.text();
      let data: unknown;
      try {
        data = JSON.parse(body);
      } catch {
        throw new Error(`Expected JSON from ${path}; received HTTP ${res.status}`);
      }
      setResponseJson(JSON.stringify(data, null, 2));
      if (!res.ok) {
        setResponseJson(JSON.stringify({ status: res.status, response: data }, null, 2));
      }
    } catch (err: unknown) {
      setStatus(null);
      setResponseJson(JSON.stringify({ error: err instanceof Error ? err.message : 'Request failed' }, null, 2));
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async () => {
    if (!responseJson) return;
    try {
      await navigator.clipboard.writeText(responseJson);
      setCopied(true);
      setCopyError(null);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
      setCopyError('Clipboard access was denied by the browser.');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-amber-400" />
          Interactive ForgeOS / Hami API Explorer
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Read-only canonical FastAPI endpoints. The browser uses same-origin <span className="font-mono text-amber-300">/api</span> routes.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Endpoints List */}
        <div className="lg:col-span-5 space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
            Available Endpoints
          </h3>
          <div className="space-y-1.5">
            {endpoints.map((ep) => (
              <button
                key={ep.path}
                onClick={() => handleExecute(ep.path)}
                className={`w-full text-left p-3 rounded-lg border transition text-xs flex items-center justify-between ${
                  selectedEndpoint === ep.path
                    ? 'bg-slate-800 border-amber-500/50 text-slate-100 shadow-sm'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                <div>
                  <div className="flex items-center gap-2 font-mono">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400">
                      {ep.method}
                    </span>
                    <span className="font-semibold text-slate-200">{ep.path}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1 line-clamp-1">{ep.description}</p>
                </div>
                <Send className="w-3.5 h-3.5 text-slate-500 shrink-0 ml-2" />
              </button>
            ))}
          </div>
        </div>

        {/* Live Response Panel */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="text-slate-500">REQUEST:</span>
                <span className="text-amber-400 font-semibold">{selectedEndpoint}</span>
                {status && (
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    status >= 200 && status < 300 ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400'
                  }`}>
                    {status} {status >= 200 && status < 300 ? 'OK' : 'ERROR'}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleExecute(selectedEndpoint)}
                  disabled={loading}
                  className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                  title="Re-send request"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                </button>
                {responseJson && (
                  <button
                    onClick={copyToClipboard}
                    className="flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                )}
              </div>
            </div>
            {copyError && <p role="alert" className="pt-2 text-[11px] text-rose-300">{copyError}</p>}

            <div className="mt-3">
              {loading ? (
                <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-amber-500" />
                  Querying {selectedEndpoint}...
                </div>
              ) : responseJson ? (
                <pre className="bg-slate-950 p-4 rounded-lg text-emerald-400 font-mono text-[11px] overflow-auto max-h-[460px] border border-slate-800/80 leading-relaxed scrollbar-thin">
                  {responseJson}
                </pre>
              ) : (
                <div className="p-12 text-center text-xs text-slate-500">
                  Select an endpoint from the left or click Execute to test live API responses.
                </div>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-500 font-mono">
            Request path: <code className="text-slate-400">{selectedEndpoint}</code>
          </div>
        </div>
      </div>
    </div>
  );
};
