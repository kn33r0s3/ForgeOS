"use client";

import { useEffect, useState } from "react";
import { api, CycleRun, ForgeRuntime } from "@/lib/api";

export default function RuntimePage() {
  const [runtime, setRuntime] = useState<ForgeRuntime | null>(null);
  const [cycles, setCycles] = useState<CycleRun[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getRuntime(), api.getCycles()])
      .then(([loadedRuntime, loadedCycles]) => {
        if (!active) return;
        setRuntime(loadedRuntime);
        setCycles(loadedCycles);
      })
      .catch(() => {
        if (active) setError("The runtime record could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, []);

  const counts = runtime
    ? [
        ["Signals", runtime.signals],
        ["Evidence", runtime.evidence],
        ["Claims", runtime.claims],
        ["Research tasks", runtime.research_tasks],
        ["Opportunities", runtime.opportunities],
        ["Outcomes", runtime.outcomes],
        ["Learning events", runtime.learning_events],
      ]
    : [];

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-xs uppercase tracking-[0.14em] text-forge-accent2">Runtime</p>
      <h1 className="mt-2 text-3xl text-white">Cycle and stored counts</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-neutral-400">
        These numbers are counts of records already stored. A count is not a judgment that the network is healthy in the world.
      </p>
      {error ? <p className="mt-6 text-sm text-neutral-300">{error}</p> : null}
      {runtime ? (
        <section className="mt-8 grid gap-3 sm:grid-cols-2">
          {counts.map(([label, value]) => (
            <p key={String(label)} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
              <span className="text-white">{label}</span>
              <span className="mt-1 block">{value == null ? "not recorded" : value}</span>
            </p>
          ))}
          <p className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
            <span className="text-white">Last cycle</span>
            <span className="mt-1 block">{runtime.cycles.last?.status || "none recorded"}</span>
          </p>
          <p className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
            <span className="text-white">Queued worker tasks</span>
            <span className="mt-1 block">{runtime.worker.queued_tasks}</span>
          </p>
        </section>
      ) : null}
      <section className="mt-8">
        <h2 className="text-lg text-white">Cycle history</h2>
        {cycles.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No cycles are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {cycles.map((cycle) => (
            <article key={cycle.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <p className="text-white">Cycle {cycle.id} · {cycle.status}</p>
              <p className="mt-1">{cycle.error || "No error recorded."}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
