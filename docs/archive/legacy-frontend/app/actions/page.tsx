"use client";

import { useEffect, useState } from "react";
import { api, ActionPackage, ExecutionAction } from "@/lib/api";

export default function ActionsPage() {
  const [rows, setRows] = useState<ExecutionAction[]>([]);
  const [blocked, setBlocked] = useState<ExecutionAction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ExecutionAction | null>(null);
  const [pkg, setPkg] = useState<ActionPackage | null>(null);
  const [result, setResult] = useState("");
  const [revenue, setRevenue] = useState({ amount: "", currency: "USD", source: "", reference: "" });

  function load() {
    return Promise.all([api.getExecutionActions(), api.getBlockedActions()])
      .then(([actions, blockedActions]) => {
        setRows(actions);
        setBlocked(blockedActions);
      })
      .catch(() => setError("The action list could not be loaded."));
  }

  useEffect(() => {
    void load();
  }, []);

  async function approve(id: number) {
    setError(null);
    try {
      await api.approveExecutionAction(id);
      await load();
    } catch {
      setError("Approval was refused by the backend.");
    }
  }

  async function select(id: number) {
    setError(null);
    try {
      const action = await api.getExecutionAction(id);
      setSelected(action);
      setPkg(null);
      if (action.policy_decision === "require_approval") setPkg(await api.getActionPackage(id));
    } catch {
      setError("The action detail could not be loaded.");
    }
  }

  async function mutate(operation: () => Promise<unknown>) {
    setError(null);
    try {
      await operation();
      await load();
      if (selected) await select(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The backend refused this action.");
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-xs uppercase tracking-[0.14em] text-forge-accent2">Actions</p>
      <h1 className="mt-2 text-3xl text-white">Authorization</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-neutral-400">
        The backend decides whether an action may proceed. This page only sends the existing approve call and shows the status that comes back.
      </p>
      {error ? <p className="mt-6 text-sm text-neutral-300">{error}</p> : null}
      <section className="mt-8">
        <h2 className="text-lg text-white">Waiting or in progress</h2>
        {rows.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No execution actions are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {rows.map((row) => (
            <article key={row.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <button type="button" onClick={() => void select(row.id)} className="text-left text-white hover:text-forge-accent2">{row.action}</button>
              <p className="mt-1">Status: {row.status} · Policy: {row.policy_decision || "not recorded"}</p>
              <p className="mt-1">{row.policy_reason || "No policy reason recorded."}</p>
              {row.requires_owner_approval && !row.approved_at ? (
                <button type="button" onClick={() => void approve(row.id)} className="mt-3 min-h-10 rounded-full bg-white px-4 text-sm text-black">
                  Send approval
                </button>
              ) : null}
              {row.approved_at ? <p className="mt-2">Approved at {row.approved_at}</p> : null}
              <p className="mt-2 text-xs text-neutral-500">Click the action to inspect evidence and record its actual response.</p>
            </article>
          ))}
        </div>
      </section>
      {selected ? <section className="mt-8 rounded-2xl border border-forge-accent/30 bg-forge-accent/5 p-5">
        <p className="text-xs uppercase tracking-[0.14em] text-forge-accent2">Action detail #{selected.id}</p>
        <h2 className="mt-2 text-lg text-white">{selected.action}</h2>
        <p className="mt-2 text-sm text-neutral-400">{selected.policy_reason || "No policy reason recorded."}</p>
        {pkg ? <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-neutral-300"><p className="text-xs uppercase tracking-widest text-neutral-500">Evidence package</p><p className="mt-2">Execution allowed: {pkg.execution_allowed ? "yes" : "no"} · cited evidence: {pkg.evidence.length}</p>{pkg.evidence.map((item) => <p key={item.signal_id} className="mt-2">{item.source || "unknown source"}: {item.text || "no excerpt recorded"}</p>)}</div> : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {selected.requires_owner_approval && !selected.approved_at ? <button type="button" onClick={() => void mutate(() => api.approveExecutionAction(selected.id))} className="rounded-full bg-white px-4 py-2 text-sm text-black">Approve</button> : null}
          {selected.approved_at && !selected.started_at ? <button type="button" onClick={() => void mutate(() => api.startExecutionAction(selected.id))} className="rounded-full bg-forge-accent px-4 py-2 text-sm text-black">Start</button> : null}
        </div>
        {selected.started_at && !selected.completed_at ? <div className="mt-4 space-y-2"><textarea value={result} onChange={(e) => setResult(e.target.value)} placeholder="Record what actually happened" className="min-h-24 w-full rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white" /><button type="button" disabled={!result.trim()} onClick={() => void mutate(async () => { await api.recordHumanResult(selected.id, result.trim()); setResult(""); })} className="rounded-full border border-white/20 px-4 py-2 text-sm text-white disabled:opacity-50">Record actual response</button></div> : null}
        {selected.completed_at && selected.revenue === null ? <div className="mt-4 grid gap-2 md:grid-cols-4"><input value={revenue.amount} onChange={(e) => setRevenue({ ...revenue, amount: e.target.value })} placeholder="Amount" className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white" /><input value={revenue.source} onChange={(e) => setRevenue({ ...revenue, source: e.target.value })} placeholder="Payment source" className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white" /><input value={revenue.reference} onChange={(e) => setRevenue({ ...revenue, reference: e.target.value })} placeholder="Verified reference" className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white" /><button type="button" onClick={() => void mutate(() => api.recordVerifiedRevenue(selected.id, { amount: Number(revenue.amount), currency: revenue.currency, source: revenue.source, reference: revenue.reference }))} className="rounded-full border border-forge-revenue/40 px-4 py-2 text-sm text-forge-revenue">Record verified revenue</button></div> : null}
      </section> : null}
      <section className="mt-8">
        <h2 className="text-lg text-white">Blocked</h2>
        {blocked.length === 0 ? <p className="mt-3 text-sm text-neutral-400">No blocked actions are stored.</p> : null}
        <div className="mt-3 space-y-3">
          {blocked.map((row) => (
            <article key={row.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
              <p className="text-white">{row.action}</p>
              <p className="mt-1">{row.policy_reason || "Blocked by policy."}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
