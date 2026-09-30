"use client";

import { useState } from "react";
import GlassPanel from "@/components/GlassPanel";
import StatusPill from "@/components/StatusPill";
import QueryStateView from "@/components/QueryStateView";
import { useForgeQuery } from "@/lib/useForgeQuery";
import { api, RepairWorkItem, RepairWorkItemDetail } from "@/lib/api";

export default function RepairShopPage() {
  const [scope, setScope] = useState<"REAL" | "SANDBOX">("SANDBOX");
  const { state, data, error, reload } = useForgeQuery<RepairWorkItem[]>(() => api.listRepairWorkItems(scope), (items) => items.length === 0);
  const [selected, setSelected] = useState<RepairWorkItemDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ customer_name: "", contact_identifier: "", asset_label: "", reported_problem: "" });

  async function createItem() {
    if (!form.customer_name || !form.asset_label || !form.reported_problem) return;
    setBusy(true);
    try {
      await api.createRepairWorkItem({ ...form, consent_state: "OPERATOR_RECORDED", data_scope: scope, idempotency_key: `repair-${scope}-${Date.now()}` });
      setForm({ customer_name: "", contact_identifier: "", asset_label: "", reported_problem: "" });
      reload();
    } finally { setBusy(false); }
  }

  async function openItem(item: RepairWorkItem) { setSelected(await api.getRepairWorkItem(item.id)); }

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-bold tracking-tight">REPAIR SHOP</h1><p className="mt-1 text-sm text-neutral-500">One auditable work item from reported problem to verified payment and learning.</p></div>
      <label className="text-xs uppercase tracking-widest text-neutral-500">Scope<select className="ml-2 rounded-md border border-forge-border bg-forge-panel2 px-2 py-1 text-xs text-white" value={scope} onChange={(e) => { setScope(e.target.value as "REAL" | "SANDBOX"); setSelected(null); }}><option>SANDBOX</option><option>REAL</option></select></label>
    </div>

    <GlassPanel className="p-5"><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">NEW WORK ITEM</h2><span className="text-[10px] uppercase tracking-widest text-forge-warn">No customer contact is automatic</span></div><div className="grid gap-2 md:grid-cols-2"><input className="rounded-md border border-forge-border bg-forge-panel2 px-3 py-2 text-sm" placeholder="Customer / shop name" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })}/><input className="rounded-md border border-forge-border bg-forge-panel2 px-3 py-2 text-sm" placeholder="Contact identifier (optional)" value={form.contact_identifier} onChange={(e) => setForm({ ...form, contact_identifier: e.target.value })}/><input className="rounded-md border border-forge-border bg-forge-panel2 px-3 py-2 text-sm" placeholder="Asset / device" value={form.asset_label} onChange={(e) => setForm({ ...form, asset_label: e.target.value })}/><input className="rounded-md border border-forge-border bg-forge-panel2 px-3 py-2 text-sm" placeholder="Reported problem" value={form.reported_problem} onChange={(e) => setForm({ ...form, reported_problem: e.target.value })}/></div><button disabled={busy} onClick={createItem} className="mt-3 rounded-md border border-forge-border px-3 py-2 text-xs font-medium text-neutral-200 hover:glow-border disabled:opacity-50">{busy ? "CREATING…" : `CREATE ${scope} ITEM`}</button></GlassPanel>

    {state !== "ready" && <QueryStateView state={state} error={error} emptyLabel={`No ${scope} repair work items yet.`} onRetry={reload} />}
    {state === "ready" && data && <div className="grid gap-3">{data.map((item) => <button key={item.id} onClick={() => openItem(item)} className="text-left"><GlassPanel className="p-4 transition hover:border-white/20"><div className="flex items-start justify-between gap-3"><div><p className="text-[10px] uppercase tracking-widest text-neutral-500">{item.asset_label} · {item.data_scope}</p><p className="mt-1 text-sm text-neutral-100">{item.reported_problem}</p><p className="mt-2 text-xs text-neutral-600">work item #{item.id}</p></div><StatusPill label={item.status} /></div></GlassPanel></button>)}</div>}
    {selected && <Detail detail={selected} onChanged={() => openItem(selected.work_item).then(reload)} />}
  </div>;
}

function Detail({ detail, onChanged }: { detail: RepairWorkItemDetail; onChanged: () => void }) {
  const [evidence, setEvidence] = useState("");
  const [triage, setTriage] = useState("Observed problem needs human inspection.");
  const [outcome, setOutcome] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>) { setBusy(true); try { await fn(); onChanged(); } finally { setBusy(false); } }
  return <GlassPanel className="space-y-4 p-5"><div className="flex items-start justify-between"><div><h2 className="text-base font-semibold">{detail.customer.name} · {detail.work_item.asset_label}</h2><p className="text-xs text-neutral-500">{detail.work_item.reported_problem}</p></div><StatusPill label={`${detail.work_item.status} · ${detail.work_item.data_scope}`} /></div><div className="grid gap-4 md:grid-cols-2"><section><h3 className="mb-2 text-xs uppercase tracking-widest text-neutral-500">Evidence</h3><div className="space-y-1 text-xs text-neutral-400">{detail.evidence.map((e) => <p key={e.id}>#{e.id} {e.content} <span className="text-neutral-600">({e.source})</span></p>)}</div><div className="mt-2 flex gap-2"><input className="min-w-0 flex-1 rounded-md border border-forge-border bg-forge-panel2 px-2 py-1 text-xs" placeholder="Observed evidence" value={evidence} onChange={(e) => setEvidence(e.target.value)}/><button disabled={busy || !evidence} onClick={() => run(() => api.attachRepairEvidence(detail.work_item.id, { content: evidence }))} className="rounded-md border border-forge-border px-2 py-1 text-xs">ADD</button></div></section><section><h3 className="mb-2 text-xs uppercase tracking-widest text-neutral-500">Triage / approval</h3><p className="mb-2 text-xs text-neutral-400">{detail.decision ? String(detail.decision.rationale || "Decision recorded") : "No triage decision yet."}</p><div className="flex gap-2"><input className="min-w-0 flex-1 rounded-md border border-forge-border bg-forge-panel2 px-2 py-1 text-xs" value={triage} onChange={(e) => setTriage(e.target.value)}/><button disabled={busy} onClick={() => run(() => api.createRepairTriage(detail.work_item.id, { rationale: triage, expected_outcome: "Technician records actual result", confidence: 50 }))} className="rounded-md border border-forge-warn/40 px-2 py-1 text-xs text-forge-warn">PROPOSE</button></div></section></div><div className="grid gap-4 md:grid-cols-2"><section><h3 className="mb-2 text-xs uppercase tracking-widest text-neutral-500">Reviewed customer status</h3><p className="text-xs text-neutral-500">Draft and approval are local records. Sending remains manual.</p><div className="mt-2 flex gap-2"><input className="min-w-0 flex-1 rounded-md border border-forge-border bg-forge-panel2 px-2 py-1 text-xs" placeholder="Status draft" value={message} onChange={(e) => setMessage(e.target.value)}/><button disabled={busy || !message} onClick={() => run(() => api.proposeRepairStatus(detail.work_item.id, message))} className="rounded-md border border-forge-border px-2 py-1 text-xs">DRAFT</button></div></section><section><h3 className="mb-2 text-xs uppercase tracking-widest text-neutral-500">Outcome / learning</h3><div className="flex gap-2"><input className="min-w-0 flex-1 rounded-md border border-forge-border bg-forge-panel2 px-2 py-1 text-xs" placeholder="What actually happened?" value={outcome} onChange={(e) => setOutcome(e.target.value)}/><button disabled={busy || !outcome} onClick={() => run(() => api.recordRepairOutcome(detail.work_item.id, { actual: outcome, success: true }))} className="rounded-md border border-forge-border px-2 py-1 text-xs">RECORD</button></div></section></div><div className="border-t border-forge-border pt-3 text-xs text-neutral-600">{detail.events.map((event) => <p key={event.id}>{event.created_at.slice(0, 19)} · {event.actor} · {event.previous_state || "—"} → {event.next_state} · {event.reason}</p>)}</div></GlassPanel>;
}
