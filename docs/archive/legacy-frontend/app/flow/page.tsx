"use client";

import { useState } from "react";
import { api, DataScope, FlowOutcome, FlowResponse, FlowState, setSessionApiKey, Channel, ProductSummary } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import StatusPill from "@/components/StatusPill";
import QueryStateView from "@/components/QueryStateView";
import { useForgeQuery } from "@/lib/useForgeQuery";

const stages = ["PROPOSED", "APPROVAL_REQUIRED", "EXECUTABLE", "OUTCOME_PENDING", "LEARNED"];

function JsonBlock({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-neutral-600">—</span>;
  return <pre className="whitespace-pre-wrap break-words text-xs text-neutral-400">{JSON.stringify(value, null, 2)}</pre>;
}

function FlowCard({ item, scope, refresh }: { item: FlowState; scope: DataScope; refresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOutcome, setShowOutcome] = useState(false);
  const [showProduct, setShowProduct] = useState(false);
  const [showCommercial, setShowCommercial] = useState(false);
  const [showDecision, setShowDecision] = useState(false);
  const [decision, setDecision] = useState<{ title?: string | null; rationale?: string | null } | null>(null);
  const [outcome, setOutcome] = useState({ actual: "", success: "", conversions: "", contacts: "[]" });
  const [product, setProduct] = useState({ name: "", offer: "", target_customer: "", pricing: "" });
  const [channel, setChannel] = useState({ product_id: "", channel_type: "", name: "", description: "" });
  const [customer, setCustomer] = useState({ product_id: "", channel_id: "", contact_name: "", contact_identifier: "", stage: "lead", event_type: "", notes: "" });
  const [revenue, setRevenue] = useState({ product_id: "", amount: "", source: "manual", description: "", idempotencyKey: "" });
  const stageIndex = stages.indexOf(item.experiment.stage);

  async function action(kind: "advance" | "approve" | "execute" | "reject") {
    setBusy(true); setError(null);
    try {
      if (kind === "advance") await api.advanceFlow(item.opportunity_id, scope);
      if (kind === "approve") await api.approveFlow(item.opportunity_id, scope);
      if (kind === "execute") await api.executeFlow(item.opportunity_id, scope);
      if (kind === "reject") await api.rejectFlow(item.opportunity_id, scope);
      refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setBusy(false); }
  }

  async function submitOutcome() {
    let contacts: unknown;
    try { contacts = JSON.parse(outcome.contacts); } catch { setError("Contacts must be valid JSON."); return; }
    if (!outcome.actual.trim() || !Array.isArray(contacts)) { setError("Enter the actual response and a JSON array of contacts."); return; }
    if (!["", "true", "false"].includes(outcome.success)) { setError("Success must be true, false or blank."); return; }
    const body: FlowOutcome = { data_scope: scope, source: scope === "SANDBOX" ? "SANDBOX operator entry" : "human_interview", actual: outcome.actual.trim(), success: outcome.success === "" ? null : outcome.success === "true", conversions: outcome.conversions === "" ? null : Number(outcome.conversions), contacts: contacts as Record<string, unknown>[] };
    setBusy(true); setError(null);
    try { await api.recordFlowOutcome(item.opportunity_id, body, scope); setShowOutcome(false); refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Outcome submission failed"); }
    finally { setBusy(false); }
  }

  async function submitProduct() {
    if (!product.name.trim()) { setError("Enter an offer hypothesis name."); return; }
    setBusy(true); setError(null);
    try { const gate = await api.createFlowProduct(item.opportunity_id, { name: product.name }, scope) as unknown as {status: string; reason?: string};
      if (!["created", "exists"].includes(gate.status)) throw new Error(gate.reason || "Recorded evidence has not cleared the validation gate.");
      setShowProduct(false); refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Product creation failed"); }
    finally { setBusy(false); }
  }

  async function loadNextDecision() {
    setBusy(true); setError(null);
    try { setDecision(await api.getNextDecision(item.opportunity_id, scope)); setShowDecision(true); }
    catch (e) { setError(e instanceof Error ? e.message : "Next-decision request failed"); }
    finally { setBusy(false); }
  }

  async function submitChannel() {
    const productId = Number(channel.product_id);
    if (!productId || !channel.channel_type.trim() || !channel.name.trim()) { setError("Select a product and provide channel type and name."); return; }
    setBusy(true); setError(null);
    try { await api.addChannel(productId, { channel_type: channel.channel_type.trim(), name: channel.name.trim(), description: channel.description.trim() || null }, scope); setChannel({ product_id: "", channel_type: "", name: "", description: "" }); refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Channel creation failed"); }
    finally { setBusy(false); }
  }

  async function submitCustomerEvent() {
    const productId = customer.product_id ? Number(customer.product_id) : undefined;
    const channelId = customer.channel_id ? Number(customer.channel_id) : undefined;
    if (!productId && !channelId) { setError("Select a product or channel for the event."); return; }
    setBusy(true); setError(null);
    try { await api.addCustomerEvent({ product_id: productId, channel_id: channelId, opportunity_id: item.opportunity_id, contact_name: customer.contact_name.trim() || null, contact_identifier: customer.contact_identifier.trim() || null, stage: customer.stage, event_type: customer.event_type.trim() || "customer_event", notes: customer.notes.trim() || null }, scope); setCustomer({ product_id: "", channel_id: "", contact_name: "", contact_identifier: "", stage: "lead", event_type: "", notes: "" }); refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Customer event failed"); }
    finally { setBusy(false); }
  }

  async function submitRevenue() {
    const productId = Number(revenue.product_id);
    const amount = Number(revenue.amount);
    if (!productId || !revenue.amount.trim() || !Number.isFinite(amount) || amount < 0 || !revenue.source.trim() || !revenue.description.trim()) { setError("Select a product and provide a non-negative USD amount, source, and description."); return; }
    setBusy(true); setError(null);
    try { const key = revenue.idempotencyKey.trim() || `flow-revenue-${scope.toLowerCase()}-${productId}-${crypto.randomUUID()}`; setRevenue(current => ({ ...current, idempotencyKey: key })); await api.recordProductOutcome(productId, amount, scope, key, revenue.source.trim(), revenue.description.trim()); setRevenue({ product_id: "", amount: "", source: "manual", description: "", idempotencyKey: "" }); refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Revenue recording failed"); }
    finally { setBusy(false); }
  }

  return <GlassPanel className="p-5 space-y-5">
    <div className="flex items-start justify-between gap-4">
      <div><p className="section-label">Opportunity #{item.opportunity.id} · {scope} DATA</p><h2 className="text-lg font-semibold mt-1">{item.opportunity.problem}</h2><p className="text-xs text-neutral-500 mt-2">Target: {item.opportunity.target_customer} · score {item.opportunity.score.toFixed(1)}</p></div>
      <StatusPill label={item.experiment.stage} />
    </div>
    <div className="grid md:grid-cols-5 gap-2">{stages.map((stage, index) => <div key={stage} className={`rounded-lg border p-2 text-center text-[10px] tracking-wide ${index <= stageIndex ? "border-forge-accent2/40 bg-forge-accent2/10 text-forge-accent2" : "border-white/[0.06] text-neutral-600"}`}>{stage.replaceAll("_", " ")}</div>)}</div>
    <div className="grid md:grid-cols-2 gap-4 text-sm">
      <section><p className="section-label">Task / question</p><p className="mt-1 text-neutral-300">{item.experiment.hypothesis || item.opportunity.value_hypothesis || "—"}</p><pre className="whitespace-pre-wrap break-words text-xs text-neutral-400 mt-3">{item.experiment.required_inputs.join("\n")}</pre><p className="section-label mt-3">Expected result</p><p className="mt-1 text-neutral-400">{item.experiment.expected_result || "—"}</p></section>
      <section><p className="section-label">Decision rationale</p><p className="mt-1 text-neutral-300">{item.decision?.rationale || "—"}</p><p className="section-label mt-3">Evidence</p><p className="mt-1 text-neutral-400">{item.opportunity.economic_evidence_summary || item.opportunity.problem_evidence_signal_ids || "No evidence recorded."}</p></section>
    </div>
    <div className="grid md:grid-cols-3 gap-3 text-sm"><div><p className="section-label">Outcomes</p><p className="mt-1 text-neutral-300">{item.outcomes_count} recorded</p><JsonBlock value={item.outcomes} /></div><div><p className="section-label">Learning / lessons</p><p className="mt-1 text-neutral-300">{item.learning_events?.length || 0} learning events · {item.lessons?.length || item.lessons_recalled} lessons</p><JsonBlock value={{ learning: item.learning_events, lessons: item.lessons }} /></div><div><p className="section-label">Products / channels / customers</p><p className="mt-1 text-neutral-300">{item.products.length} / {item.channels?.length || 0} / {item.customer_events?.length || 0}</p><JsonBlock value={{ products: item.products, channels: item.channels, customers: item.customer_events }} /></div></div>
    {error && <p className="rounded-lg border border-forge-danger/30 bg-forge-danger/10 p-3 text-xs text-forge-danger">{error}</p>}
    <div className="flex flex-wrap gap-2"><button disabled={busy} onClick={loadNextDecision} className="action">Next decision</button>{item.experiment.stage === "PROPOSED" && <button disabled={busy} onClick={() => action("advance")} className="action">Prepare validation</button>}{item.experiment.stage === "APPROVAL_REQUIRED" && <><button disabled={busy} onClick={() => action("approve")} className="action warn">Approve</button><button disabled={busy} onClick={() => action("reject")} className="action danger">Reject</button></>}{item.experiment.stage === "EXECUTABLE" && <button disabled={busy} onClick={() => action("execute")} className="action accent">Execute human task</button>}{item.experiment.stage === "OUTCOME_PENDING" && <button disabled={busy} onClick={() => setShowOutcome(v => !v)} className="action">Record validation outcome</button>}{item.experiment.stage === "LEARNED" && <button disabled={busy} onClick={() => setShowProduct(v => !v)} className="action accent">Create gated product</button>}<button disabled={busy} onClick={() => setShowCommercial(v => !v)} className="action accent">Commercial actions</button></div>
    {showDecision && decision && <div className="rounded-lg border border-forge-accent2/30 bg-forge-accent2/10 p-3 text-sm"><p className="section-label">NEXT DECISION · {scope}</p><p className="mt-1 text-neutral-200">{decision.title || "Decision returned"}</p><p className="mt-2 whitespace-pre-line text-neutral-400">{decision.rationale || "No rationale returned."}</p></div>}
    {showOutcome && <div className="grid md:grid-cols-4 gap-2 border-t border-white/[0.06] pt-4"><input className="field" placeholder="What did the human actually report?" value={outcome.actual} onChange={e => setOutcome({ ...outcome, actual: e.target.value })} /><input className="field" placeholder="Success true/false" value={outcome.success} onChange={e => setOutcome({ ...outcome, success: e.target.value })} /><input className="field" placeholder="Conversions" value={outcome.conversions} onChange={e => setOutcome({ ...outcome, conversions: e.target.value })} /><textarea className="field" placeholder='Contacts JSON, e.g. []' value={outcome.contacts} onChange={e => setOutcome({ ...outcome, contacts: e.target.value })} /><button disabled={busy} onClick={submitOutcome} className="action accent md:col-span-4">{busy ? "Saving…" : "Submit validation outcome"}</button></div>}
    {showProduct && <div className="space-y-2 border-t border-white/[0.06] pt-4"><p className="text-xs text-forge-warn">{scope} scope selected. Product is created in this scope only.</p><input className="field w-full" placeholder="Product name" value={product.name} onChange={e => setProduct({ ...product, name: e.target.value })} /><p className="text-xs text-neutral-400">Target, offer, and pricing are derived from the originating opportunity and recorded evidence, not invented here.</p><button disabled={busy} onClick={submitProduct} className="action accent">{busy ? "Creating…" : `Create ${scope.toLowerCase()} product`}</button></div>}
    {showCommercial && <div className="space-y-4 border-t border-white/[0.06] pt-4"><p className="text-xs text-forge-warn">Commercial records use the selected {scope} scope. Customer event is not paid revenue. SANDBOX never counts as real business traction.</p><div className="grid md:grid-cols-2 gap-3"><section className="space-y-2"><p className="section-label">Create channel</p><select className="field w-full" value={channel.product_id} onChange={e => setChannel({ ...channel, product_id: e.target.value })}><option value="">Select product</option>{item.products.map((p: ProductSummary) => <option key={p.id} value={p.id}>{p.name} · {p.data_scope || scope}</option>)}</select><input className="field w-full" placeholder="Channel type (email, partner...)" value={channel.channel_type} onChange={e => setChannel({ ...channel, channel_type: e.target.value })} /><input className="field w-full" placeholder="Channel name" value={channel.name} onChange={e => setChannel({ ...channel, name: e.target.value })} /><input className="field w-full" placeholder="Description" value={channel.description} onChange={e => setChannel({ ...channel, description: e.target.value })} /><button disabled={busy} onClick={submitChannel} className="action accent">Create channel</button></section><section className="space-y-2"><p className="section-label">Record customer event · not paid revenue</p><select className="field w-full" value={customer.product_id} onChange={e => setCustomer({ ...customer, product_id: e.target.value })}><option value="">Select product</option>{item.products.map((p: ProductSummary) => <option key={p.id} value={p.id}>{p.name}</option>)}</select><select className="field w-full" value={customer.channel_id} onChange={e => setCustomer({ ...customer, channel_id: e.target.value })}><option value="">Optional channel</option>{(item.channels || []).map((c: Channel) => <option key={c.id} value={c.id}>{c.name}</option>)}</select><input className="field w-full" placeholder="Contact name or identifier" value={customer.contact_name} onChange={e => setCustomer({ ...customer, contact_name: e.target.value })} /><select className="field w-full" value={customer.stage} onChange={e => setCustomer({ ...customer, stage: e.target.value })}><option value="lead">Lead</option><option value="contacted">Contacted</option><option value="interested">Interested</option><option value="paid_customer">Paid customer</option><option value="churned">Churned</option></select><input className="field w-full" placeholder="Event type" value={customer.event_type} onChange={e => setCustomer({ ...customer, event_type: e.target.value })} /><textarea className="field w-full" placeholder="Notes" value={customer.notes} onChange={e => setCustomer({ ...customer, notes: e.target.value })} /><button disabled={busy} onClick={submitCustomerEvent} className="action accent">Record event</button></section></div><section className="space-y-2"><p className="section-label">Record ACTUAL_REVENUE · USD only</p><div className="grid md:grid-cols-4 gap-2"><select className="field" value={revenue.product_id} onChange={e => setRevenue({ ...revenue, product_id: e.target.value })}><option value="">Select product</option>{item.products.map((p: ProductSummary) => <option key={p.id} value={p.id}>{p.name}</option>)}</select><input className="field" type="number" min="0" step="0.01" placeholder="Amount USD (0 allowed)" value={revenue.amount} onChange={e => setRevenue({ ...revenue, amount: e.target.value })} /><input className="field" placeholder="Source description" value={revenue.source} onChange={e => setRevenue({ ...revenue, source: e.target.value })} /><input className="field" placeholder="What was paid / evidence" value={revenue.description} onChange={e => setRevenue({ ...revenue, description: e.target.value })} /></div><input className="field w-full" placeholder="Idempotency key (optional; generated per submit and stable for retry)" value={revenue.idempotencyKey} onChange={e => setRevenue({ ...revenue, idempotencyKey: e.target.value })} /><button disabled={busy} onClick={submitRevenue} className="action accent">{busy ? "Recording…" : `Record ${scope} actual revenue`}</button></section></div>}
  </GlassPanel>;
}

export default function FlowPage() {
  const [scope, setScope] = useState<DataScope>("REAL");
  const [apiKey, setApiKey] = useState("");
  const { state, data, error, reload } = useForgeQuery<FlowResponse>(() => api.getFlow(10, scope), value => value.flow.length === 0, [scope]);
  return <div className="space-y-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="section-label">CANONICAL LOOP</p><h1 className="text-3xl font-bold tracking-tight mt-2">OPPORTUNITY → OUTCOME → LEARNING</h1><p className="text-sm text-neutral-500 mt-2 max-w-3xl">Questions, rationale, evidence, outcomes, learning, products, channels, and customers are shown only when recorded by the backend.</p></div><div className="flex flex-wrap gap-2 items-center"><select value={scope} onChange={e => setScope(e.target.value as DataScope)} className="field"><option value="REAL">REAL</option><option value="SANDBOX">SANDBOX</option></select><input type="password" value={apiKey} onChange={e => { setApiKey(e.target.value); setSessionApiKey(e.target.value); }} placeholder="Session API key" className="field" /></div></div>{scope === "SANDBOX" && <p className="text-xs text-forge-warn">SANDBOX DATA — excluded from real business metrics.</p>}{state !== "ready" && <QueryStateView state={state} error={error} onRetry={reload} emptyLabel={`No ${scope.toLowerCase()} opportunity flow has been prepared yet.`} />}{state === "ready" && data && <div className="space-y-4">{data.flow.map(item => <FlowCard key={`${scope}-${item.opportunity_id}`} item={item} scope={scope} refresh={reload} />)}</div>}</div>;
}
