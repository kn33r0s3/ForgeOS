"use client";

import { useEffect, useState } from "react";
import { api, ForgeOutcome, LearningEvent } from "@/lib/api";

export default function OutcomesPage() {
  const [outcomes, setOutcomes] = useState<ForgeOutcome[]>([]);
  const [learning, setLearning] = useState<LearningEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getOutcomes(), api.getLearning()])
      .then(([loadedOutcomes, loadedLearning]) => {
        if (!active) return;
        setOutcomes(loadedOutcomes);
        setLearning(loadedLearning);
      })
      .catch(() => {
        if (active) setError("The outcome list could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-xs uppercase tracking-[0.14em] text-forge-accent2">Outcomes</p>
      <h1 className="mt-2 text-3xl text-white">What actually happened</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-neutral-400">
        An outcome is a stored result. A learning event is a stored difference between what was expected and what happened. Neither one creates wealth by being written down.
      </p>
      {error ? <p className="mt-6 text-sm text-neutral-300">{error}</p> : null}
      <section className="mt-8">
        <h2 className="text-lg text-white">Outcomes</h2>
        {outcomes.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No outcomes are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {outcomes.map((row) => (
            <article key={row.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <p className="text-white">{row.qualitative_result || row.outcome_type}</p>
              <p className="mt-1">
                {row.outcome_type}
                {row.actual_value != null ? ` · ${row.actual_value} ${row.unit || ""}` : " · no amount recorded"}
                {row.success == null ? " · success unknown" : row.success ? " · recorded success" : " · recorded failure"}
              </p>
            </article>
          ))}
        </div>
      </section>
      <section className="mt-8">
        <h2 className="text-lg text-white">Learning</h2>
        {learning.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No learning events are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {learning.map((row) => (
            <article key={row.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <p className="text-white">{row.lesson}</p>
              <p className="mt-1">Expected: {row.prediction}</p>
              <p className="mt-1">Actual: {row.actual}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
