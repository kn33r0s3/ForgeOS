"use client";

import { useMemo, useState } from "react";
import {
  api,
  DataScope,
  ProductPipeline,
  ProductSummary,
  Channel,
} from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import { useForgeQuery } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";
import StatusPill from "@/components/StatusPill";

// Product pipeline screen — honest build -> distribute -> measure -> learn.
// Revenue & customer counts here come ONLY from real ACTUAL_* outcomes the
// user records; the system never invents a sale, customer, or dollar.
export default function ProductsPage() {
  const [scope] = useState<DataScope>("REAL");
  const { state, data, error, reload } = useForgeQuery<ProductPipeline>(
    () => api.getProductPipeline(scope),
    (d) => d.total_products === 0 && d.total_leads === 0,
    [scope]
  );

  const [creating, setCreating] = useState(false);
  const [newForm, setNewForm] = useState({
    name: "",
    offer: "",
    target_customer: "",
    pricing: "",
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function createProduct() {
    if (!newForm.name.trim() || !newForm.offer.trim()) {
      setMsg("Give the product a name and a plain-language offer.");
      return;
    }
    setBusy("create");
    try {
      await api.createProduct({
        name: newForm.name.trim(),
        offer: newForm.offer.trim(),
        target_customer: newForm.target_customer.trim() || null,
        pricing: newForm.pricing.trim() || null,
        launch_state: "not_launched",
      });
      setNewForm({ name: "", offer: "", target_customer: "", pricing: "" });
      await reload();
      setMsg("Product recorded as a hypothesis. Nothing claimed — no revenue until real outcomes.");
    } catch (e: any) {
      setMsg("Could not create product: " + (e?.message || "error"));
    } finally {
      setBusy(null);
      setCreating(false);
    }
  }

  const products = useMemo(() => data?.products ?? [], [data?.products]);
  const channels = useMemo(() => data?.channels ?? [], [data?.channels]);
  const events = useMemo(() => data?.customer_events ?? [], [data?.customer_events]);
  const productMap = useMemo(() => {
    const m = new Map<number, ProductSummary>();
    products.forEach((p) => m.set(p.id, p));
    return m;
  }, [products]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">PRODUCT PIPELINE</h1>
          <p className="text-sm text-neutral-500 mt-1">
            From opportunity to offer to customers. Revenue only counts from real outcomes you
            record — never fabricated.
          </p>
        </div>
        <button
          onClick={() => setCreating((v) => !v)}
          className="px-4 py-2 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.08] text-sm"
        >
          {creating ? "Cancel" : "+ New Product"}
        </button>
      </div>

      {msg && <p className="text-sm text-neutral-400">{msg}</p>}

      {creating && (
        <GlassPanel className="p-5 space-y-3">
          <p className="text-xs uppercase tracking-widest text-neutral-500">Form a concrete offer</p>
          <input
            className="w-full bg-black/30 border border-white/[0.08] rounded-md px-3 py-2 text-sm"
            placeholder="Offer name, e.g. No-Show Cutter"
            value={newForm.name}
            onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
          />
          <input
            className="w-full bg-black/30 border border-white/[0.08] rounded-md px-3 py-2 text-sm"
            placeholder="What you actually deliver, in plain words"
            value={newForm.offer}
            onChange={(e) => setNewForm({ ...newForm, offer: e.target.value })}
          />
          <div className="grid md:grid-cols-2 gap-3">
            <input
              className="bg-black/30 border border-white/[0.08] rounded-md px-3 py-2 text-sm"
              placeholder="Target customer"
              value={newForm.target_customer}
              onChange={(e) => setNewForm({ ...newForm, target_customer: e.target.value })}
            />
            <input
              className="bg-black/30 border border-white/[0.08] rounded-md px-3 py-2 text-sm"
              placeholder="Pricing idea"
              value={newForm.pricing}
              onChange={(e) => setNewForm({ ...newForm, pricing: e.target.value })}
            />
          </div>
          <button
            onClick={createProduct}
            disabled={busy === "create"}
            className="px-4 py-2 rounded-lg bg-forge-accent/90 text-black text-sm font-semibold disabled:opacity-50"
          >
            {busy === "create" ? "Saving…" : "Create Product"}
          </button>
        </GlassPanel>
      )}

      {state !== "ready" && <QueryStateView state={state} error={error} onRetry={reload} />}

      {state === "ready" && data && (
        <div className="space-y-6">
          {/* Hero metrics — honest zeros when nothing is recorded */}
          <GlassPanel glow className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Hero label="Products" value={String(data.total_products)} />
              <Hero label="Launched" value={String(data.launched_products)} />
              <Hero label="Reached" value={String(data.total_outreach)} />
              <Hero label="Leads" value={String(data.total_leads)} />
              <Hero label="Revenue (real)" value={`$${data.realized_revenue.toFixed(2)}`} accent />
            </div>
          </GlassPanel>

          {/* Products grid */}
          <div className="grid md:grid-cols-2 gap-4">
            {products.length === 0 && (
              <p className="text-sm text-neutral-600">No products yet. Create one to get started.</p>
            )}
            {products.map((p) => (
              <ProductCard key={p.id} p={p} onUpdated={() => reload()} />
            ))}
          </div>

          {/* Channels */}
          <GlassPanel className="p-4">
            <p className="text-xs uppercase tracking-widest text-neutral-500 mb-3">
              Distribution channels
            </p>
            {channels.length === 0 ? (
              <p className="text-sm text-neutral-600">No channels tracked yet.</p>
            ) : (
              <ul className="space-y-2">
                {channels.map((c) => {
                  const owner = c.product_id ? productMap.get(c.product_id) : null;
                  return <ChannelRow key={c.id} c={c} owner={owner?.name ?? "—"} />;
                })}
              </ul>
            )}
          </GlassPanel>

          {/* Customer ledger */}
          <GlassPanel className="p-4">
            <p className="text-xs uppercase tracking-widest text-neutral-500 mb-3">
              Customer / lead ledger ({events.length})
            </p>
            {events.length === 0 ? (
              <p className="text-sm text-neutral-600">No real contacts recorded yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {events.slice(0, 25).map((e) => (
                  <li key={e.id} className="flex items-center justify-between gap-3 text-sm">
                    <div className="flex items-center gap-2">
                      <StageBadge stage={e.stage} />
                      <span className="text-neutral-300">{e.contact_name || e.contact_identifier || "anonymous"}</span>
                      {e.segment && <span className="text-neutral-600 text-xs">{e.segment}</span>}
                    </div>
                    <span className="text-neutral-600 text-xs">
                      {e.product_id && productMap.get(e.product_id)
                        ? productMap.get(e.product_id)!.name
                        : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </GlassPanel>
        </div>
      )}
    </div>
  );
}

function Hero({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <p className={`text-2xl font-bold tabular ${accent ? "text-forge-revenue" : "text-neutral-100"}`}>
        {value}
      </p>
      <p className="text-[10px] text-neutral-500 uppercase tracking-wide mt-1">{label}</p>
    </div>
  );
}

function ProductCard({ p, onUpdated }: { p: ProductSummary; onUpdated: () => void }) {
  const [recording, setRecording] = useState(false);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);

  async function recordRevenue() {
    const val = parseFloat(amount);
    if (isNaN(val) || val <= 0) return;
    setBusy(true);
    try {
      await api.recordProductOutcome(p.id, val, p.data_scope || "REAL");
      setAmount("");
      setRecording(false);
      onUpdated();
    } catch {
      /* keep open */
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassPanel className="p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="font-semibold text-neutral-100">{p.name}</p>
            <StatusPill label={p.status} />
          </div>
          <p className="text-sm text-neutral-500 mt-1">{p.offer}</p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3 text-center">
        <Metric label="Customers" value={String(p.actual_customers)} />
        <Metric label="Revenue" value={`$${p.actual_revenue.toFixed(2)}`} />
        <Metric label="Leads" value={String(p.lead_count)} />
      </div>
      {p.target_customer && (
        <p className="text-xs text-neutral-600">
          <span className="text-neutral-500">For:</span> {p.target_customer}
        </p>
      )}
      {p.hypothesis && (
        <p className="text-xs text-neutral-600 italic">“{p.hypothesis}”</p>
      )}

      <div className="pt-1">
        {!recording ? (
          <button
            onClick={() => setRecording(true)}
            className="text-xs px-3 py-1.5 rounded-md bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.08]"
          >
            Record real revenue
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <input
              autoFocus
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              className="w-28 bg-black/30 border border-white/[0.08] rounded-md px-2 py-1 text-sm"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && recordRevenue()}
            />
            <button
              onClick={recordRevenue}
              disabled={busy}
              className="text-xs px-3 py-1.5 rounded-md bg-forge-accent/90 text-black disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={() => setRecording(false)}
              className="text-xs px-2 py-1.5 text-neutral-500"
            >
              cancel
            </button>
          </div>
        )}
      </div>
    </GlassPanel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-black/20 p-2">
      <p className="text-lg font-bold tabular text-neutral-100">{value}</p>
      <p className="text-[9px] text-neutral-500 uppercase tracking-wide">{label}</p>
    </div>
  );
}

function ChannelRow({ c, owner }: { c: Channel; owner: string }) {
  return (
    <li className="flex items-center justify-between gap-3 text-sm py-1 border-b border-white/[0.04] last:border-0">
      <div className="flex items-center gap-2">
        <span className="font-medium text-neutral-300">{c.name}</span>
        <StatusPill label={c.status} />
        <span className="text-xs text-neutral-600">{owner}</span>
      </div>
      <span className="text-xs text-neutral-500 tabular">
        {c.outreach_count} reached · {c.conversion_count} converted
      </span>
    </li>
  );
}

function StageBadge({ stage }: { stage: string }) {
  const tone =
    stage === "paid_customer"
      ? "text-forge-revenue border-forge-revenue/30"
      : stage === "churned"
      ? "text-red-400 border-red-400/30"
      : "text-neutral-400 border-white/[0.1]";
  return (
    <span className={`text-[10px] uppercase tracking-wide border rounded px-1.5 py-0.5 ${tone}`}>
      {stage}
    </span>
  );
}
