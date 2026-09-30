import React from 'react';
import { Activity, CheckCircle2, Clock, Cpu, Terminal } from 'lucide-react';
import type { Cycle, WorkerTask } from '../types';

interface WorkersTabProps {
  workers: WorkerTask[];
  cycles: Cycle[];
}

function statusStyle(status: string): string {
  if (status.toLowerCase() === 'completed') return 'bg-emerald-950 text-emerald-300 border-emerald-800/60';
  if (status.toLowerCase() === 'failed') return 'bg-rose-950 text-rose-300 border-rose-800/60';
  if (status.toLowerCase() === 'queued' || status.toLowerCase() === 'running') return 'bg-amber-950 text-amber-300 border-amber-800/60';
  return 'bg-slate-800 text-slate-300 border-slate-700';
}

export const WorkersTab: React.FC<WorkersTabProps> = ({ workers, cycles }) => {
  const latestCycle = cycles[0] ?? null;
  const queuedTasks = workers.filter((worker) => worker.status.toLowerCase() === 'queued').length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-purple-400" />
          Background Tasks &amp; Cycle History
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Read-only records returned by the canonical worker and cycle endpoints. This screen does not start a cycle or task.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Latest recorded cycle</span><Activity className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-lg font-bold font-mono text-amber-300">{latestCycle ? `#${latestCycle.id}` : 'None'}</div>
          <p className="text-[11px] text-slate-500">{latestCycle?.status ?? 'No cycle returned'}</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Cycles in response</span><Clock className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-lg font-bold font-mono text-blue-300">{cycles.length}</div>
          <p className="text-[11px] text-slate-500">The API returned at most 20 recent records.</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Queued worker tasks</span><Terminal className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-lg font-bold font-mono text-purple-300">{queuedTasks}</div>
          <p className="text-[11px] text-slate-500">Of {workers.length} worker-task records returned</p>
        </div>
      </div>

      <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-purple-400" />
            Worker tasks
          </h3>
          <span className="text-[11px] font-mono text-slate-500">{workers.length} returned</span>
        </div>
        {workers.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-6 text-center text-xs text-slate-500">
            The backend returned no worker-task records.
          </div>
        ) : (
          <div className="space-y-3">
            {workers.map((worker) => (
              <article key={worker.id} className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-slate-300 font-semibold">{worker.task_name}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30 font-mono">
                      {worker.worker_type}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">Task #{worker.id} · priority {worker.priority}</div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <time className="text-[11px] text-slate-500" dateTime={worker.updated_at}>
                    {new Date(worker.updated_at).toLocaleString()}
                  </time>
                  <span className={`px-2.5 py-1 rounded text-[10px] font-mono uppercase font-bold border flex items-center gap-1 ${statusStyle(worker.status)}`}>
                    {worker.status.toLowerCase() === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                    {worker.status}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Cycle history</h3>
          <span className="text-[11px] font-mono text-slate-500">{cycles.length} returned</span>
        </div>
        {cycles.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-6 text-center text-xs text-slate-500">
            The backend returned no cycle records.
          </div>
        ) : (
          <div className="space-y-2">
            {cycles.map((cycle) => (
              <div key={cycle.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 py-2 text-xs">
                <span className="font-mono text-slate-300">Cycle #{cycle.id}</span>
                <div className="flex items-center gap-3 text-slate-500">
                  <time dateTime={cycle.started_at}>{new Date(cycle.started_at).toLocaleString()}</time>
                  <span className={`px-2 py-0.5 rounded border font-mono text-[10px] ${statusStyle(cycle.status)}`}>{cycle.status}</span>
                  {cycle.duration_ms !== null && <span>{cycle.duration_ms.toLocaleString()} ms</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
