"use client";

import { useEffect, useState } from "react";
import { api, Evidence, ResearchQuestion, ResearchTask, Signal } from "@/lib/api";

export default function ResearchPage() {
  const [questions, setQuestions] = useState<ResearchQuestion[]>([]);
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [claims, setClaims] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getQuestions(), api.getTasks(), api.getSignals(), api.getEvidence(), api.getClaims()])
      .then(([loadedQuestions, loadedTasks, loadedSignals, loadedEvidence, loadedClaims]) => {
        if (!active) return;
        setQuestions(loadedQuestions);
        setTasks(loadedTasks);
        setSignals(loadedSignals);
        setEvidence(loadedEvidence);
        setClaims(loadedClaims);
      })
      .catch(() => {
        if (active) setError("The research list could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-xs uppercase tracking-[0.14em] text-forge-accent2">Research</p>
      <h1 className="mt-2 text-3xl text-white">Questions and tasks</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-neutral-400">
        These are the questions and collection tasks already stored. A question is not a public fact. Evidence still has to be collected before a claim can move.
      </p>
      {error ? <p className="mt-6 text-sm text-neutral-300">{error}</p> : null}
      <div className="mt-8 grid gap-4 lg:grid-cols-2">
      <section>
        <h2 className="text-lg text-white">Questions</h2>
        {questions.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No research questions are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {questions.map((question) => (
            <article key={question.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <p className="text-white">{question.question}</p>
              <p className="mt-1">Status: {question.status}</p>
            </article>
          ))}
        </div>
      </section>
      <section>
        <h2 className="text-lg text-white">Signals</h2>
        {signals.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No signals are stored.</p> : null}
        <div className="mt-3 space-y-3">{signals.slice(0, 8).map((signal) => <article key={signal.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300"><p className="text-white">{signal.content}</p><p className="mt-1">Source: {signal.source} · Importance: {signal.importance_score.toFixed(1)}</p></article>)}</div>
      </section>
      <section>
        <h2 className="text-lg text-white">Evidence and claims</h2>
        <p className="mt-3 text-sm text-neutral-400">Evidence remains internal and is shown with its recorded provenance. Claims are not treated as verified facts automatically.</p>
        <div className="mt-3 space-y-3">
          {evidence.slice(0, 8).map((item) => <article key={`evidence-${item.id}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300"><p className="text-white">{item.content}</p><p className="mt-1">{item.direction} · source: {item.source || "unknown"} · signal #{item.signal_id ?? "—"}</p></article>)}
          {claims.slice(0, 8).map((claim, index) => <article key={`claim-${String(claim.id ?? index)}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300"><p className="text-white">{String(claim.statement ?? claim.claim ?? "Recorded claim")}</p><p className="mt-1">Claim #{String(claim.id ?? "—")} · status {String(claim.status ?? "unknown")}</p></article>)}
          {evidence.length === 0 && claims.length === 0 ? <p className="text-sm text-neutral-400">No evidence or claims are stored.</p> : null}
        </div>
      </section>
      </div>
      <section className="mt-8">
        <h2 className="text-lg text-white">Tasks</h2>
        <div className="mt-3 flex gap-4 text-sm text-neutral-300">
          <span>Planned: {tasks.filter((task) => task.status === "planned").length}</span>
          <span>Failed: {tasks.filter((task) => task.status === "failed").length}</span>
        </div>
        {tasks.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No research tasks are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {tasks.map((task) => (
            <article key={task.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <p className="text-white">{task.query}</p>
              <p className="mt-1">Source: {task.source} · Status: {task.status}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
