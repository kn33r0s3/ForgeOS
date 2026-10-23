import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical, Plus, Timer, Trash2 } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import {
  isCommitmentEntry,
  isInquiry,
  parseOrderValue,
  summarizeCommitments,
  syncCommitmentEntryToSubstrate,
  type CommitmentEntry,
  type CommitmentStage,
  type Inquiry,
  type Outcome,
} from "@/lib/prototype-inbox";

export const Route = createFileRoute("/prototype/inbox")({
  component: InboxPrototype,
  head: () => ({ meta: [{ title: "Inbox prototype — Hami" }] }),
});

const STORAGE_KEY = "hami-prototype-inbox-v1";
const COMMITMENT_STORAGE_KEY = "hami-prototype-commitments-v1";

function load(): Inquiry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isInquiry) : [];
  } catch {
    return [];
  }
}

function loadCommitments(): CommitmentEntry[] {
  try {
    const raw = localStorage.getItem(COMMITMENT_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isCommitmentEntry) : [];
  } catch {
    return [];
  }
}

const COMMITMENT_STAGES: CommitmentStage[] = ["inquiry", "order", "payment", "delivery", "outcome"];

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtLatency(ms: number): string {
  const mins = Math.round(ms / 60000);
  if (mins < 1) return "<1 min";
  if (mins < 60) return `${mins} min`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

function InboxPrototype() {
  const [items, setItems] = useState<Inquiry[]>([]);
  const [customer, setCustomer] = useState("");
  const [want, setWant] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setItems(load());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
      } catch {
        /* prototype: storage failure is not fatal */
      }
    }
  }, [items, hydrated]);

  const add = () => {
    if (!want.trim()) return;
    const now = Date.now();
    setItems((prev) => [
      {
        id: `${now}-${Math.random().toString(36).slice(2, 7)}`,
        timeIn: now,
        customer: customer.trim() || "—",
        want: want.trim(),
        replyAt: null,
        outcome: "open",
        orderValue: null,
      },
      ...prev,
    ]);
    setCustomer("");
    setWant("");
  };

  const markReplied = (id: string) =>
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, replyAt: Date.now() } : i)));

  const setOutcome = (id: string, outcome: Outcome, orderValue?: number) =>
    setItems((prev) =>
      prev.map((i) =>
        i.id === id
          ? { ...i, outcome, orderValue: outcome === "recovered" ? (orderValue ?? i.orderValue ?? 0) : null }
          : i,
      ),
    );

  const remove = (id: string) => setItems((prev) => prev.filter((i) => i.id !== id));
  const clearAll = () => {
    if (window.confirm("Clear all prototype inquiries?")) setItems([]);
  };

  const [entries, setEntries] = useState<CommitmentEntry[]>([]);
  const [cSellerRef, setCSellerRef] = useState("");
  const [cStage, setCStage] = useState<CommitmentStage>("inquiry");
  const [cAmount, setCAmount] = useState("");
  const [cEvidenceRef, setCEvidenceRef] = useState("");
  const [cConsent, setCConsent] = useState(false);
  const [cVerified, setCVerified] = useState(false);
  const [cRecovered, setCRecovered] = useState("");
  const [cNote, setCNote] = useState("");
  const [cError, setCError] = useState("");
  const [ownerKey, setOwnerKey] = useState("");
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncMessages, setSyncMessages] = useState<Record<string, string>>({});

  useEffect(() => {
    setEntries(loadCommitments());
  }, []);

  useEffect(() => {
    if (hydrated) {
      try {
        localStorage.setItem(COMMITMENT_STORAGE_KEY, JSON.stringify(entries));
      } catch {
        /* prototype: storage failure is not fatal */
      }
    }
  }, [entries, hydrated]);

  const addCommitment = () => {
    if (!cSellerRef.trim()) {
      setCError("A pseudonymous seller reference is required (e.g. seller-01) — never a name or phone number.");
      return;
    }
    if (cVerified && !cEvidenceRef.trim()) {
      setCError("VERIFIED requires an evidence reference. Without one, the entry stays REPORTED.");
      return;
    }
    if (cVerified && !cConsent) {
      setCError("VERIFIED requires the seller's consent to keep this record.");
      return;
    }
    const now = Date.now();
    const entry: CommitmentEntry = {
      id: `${now}-${Math.random().toString(36).slice(2, 7)}`,
      sellerRef: cSellerRef.trim(),
      stage: cStage,
      at: now,
      amount: cAmount.trim() ? parseOrderValue(cAmount) : null,
      verification: cVerified ? "verified" : "reported",
      evidenceRef: cEvidenceRef.trim(),
      sellerConsent: cConsent,
      recovered: cStage === "outcome" && cRecovered ? cRecovered === "yes" : null,
      note: cNote.trim(),
    };
    setEntries((prev) => [entry, ...prev]);
    setCError("");
    setCAmount("");
    setCEvidenceRef("");
    setCNote("");
    setCRecovered("");
  };

  const removeCommitment = (id: string) =>
    setEntries((prev) => prev.filter((e) => e.id !== id));

  const syncCommitment = async (entry: CommitmentEntry) => {
    if (!ownerKey.trim() || syncingId) return;
    setSyncingId(entry.id);
    setSyncMessages((prev) => ({ ...prev, [entry.id]: "Syncing to the canonical Hami substrate…" }));
    try {
      const substrateSync = await syncCommitmentEntryToSubstrate(entry, ownerKey);
      setEntries((prev) => prev.map((current) => current.id === entry.id ? { ...current, substrateSync } : current));
      setSyncMessages((prev) => ({ ...prev, [entry.id]: "Synced to the canonical substrate. The source evidence was not independently inspected by this connector." }));
    } catch (error) {
      setSyncMessages((prev) => ({
        ...prev,
        [entry.id]: error instanceof Error ? error.message : "Sync failed; this entry remains in this browser.",
      }));
    } finally {
      setSyncingId(null);
    }
  };

  const summary = summarizeCommitments(entries);

  const replied = items.filter((i) => i.replyAt !== null);
  const avgLatency =
    replied.length > 0
      ? replied.reduce((s, i) => s + (i.replyAt! - i.timeIn), 0) / replied.length
      : null;
  const recovered = items.filter((i) => i.outcome === "recovered");
  const recoveredValue = recovered.reduce((s, i) => s + (i.orderValue ?? 0), 0);

  return (
    <main>
      <PageHeader
        eyebrow="Hami · prototype — not a live product"
        title="Inquiry inbox"
        lede="A prototype for the first-rupee sprint: log inquiries, reply fast, count recovered sales. Data stays in this browser. Nothing here is a real product yet."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <div className="mb-8 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" aria-hidden="true" />
          <p className="text-sm leading-6 text-muted">
            <strong className="text-ink">Prototype.</strong> Built for the delegate
            running the first-rupee sprint week — to demo to a seller and to log
            the week's inquiries. Starts empty, because no real week has run yet.
            No data leaves this browser.
          </p>
          <ul className="mt-3 space-y-1.5 border-t border-amber-500/20 pt-3 text-sm leading-6 text-muted">
            <li>
              It can&rsquo;t read your Facebook or Messenger messages — you
              type in what the customer asked.
            </li>
            <li>
              Names you type stay in this browser on your device — stored
              locally, never sent anywhere. &ldquo;Clear all prototype
              data&rdquo; wipes them.
            </li>
            <li>
              Free — no account, no payment. In a real sprint week Hami takes
              a cut of recovered sales only; no recovery, no charge.
            </li>
          </ul>
        </div>

        <section aria-label="Week summary" className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Inquiries", value: String(items.length) },
            { label: "Avg reply time", value: avgLatency !== null ? fmtLatency(avgLatency) : "—" },
            { label: "Recovered", value: String(recovered.length) },
            { label: "Recovered value", value: recoveredValue > 0 ? `₨${recoveredValue.toLocaleString()}` : "₨0" },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border border-line bg-surface p-4">
              <p className="text-xs font-medium uppercase tracking-wider text-muted">{s.label}</p>
              <p className="mt-1 font-display text-2xl text-ink">{s.value}</p>
            </div>
          ))}
        </section>

        <section aria-label="Log an inquiry" className="mb-8 rounded-xl border border-line bg-surface p-5">
          <h2 className="font-display text-lg text-ink">Log an inquiry</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_2fr_auto]">
            <input
              value={customer}
              onChange={(e) => setCustomer(e.target.value)}
              placeholder="Customer (optional)"
              aria-label="Customer"
              className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60"
            />
            <input
              value={want}
              onChange={(e) => setWant(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              placeholder="What they want — e.g. red kurta, size M, price?"
              aria-label="What they want"
              className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60"
            />
            <Button onClick={add} disabled={!want.trim()}>
              <Plus className="size-4" aria-hidden="true" /> Log
            </Button>
          </div>
        </section>

        <section aria-label="Inquiries" className="grid gap-3">
          {items.length === 0 && (
            <div className="rounded-xl border border-dashed border-line p-8 text-center">
              <p className="text-sm font-semibold text-ink">No inquiries yet</p>
              <p className="mt-1 text-sm text-muted">
                This is the honest empty state — the prototype comes alive during
                a real sprint week.
              </p>
            </div>
          )}
          {items.map((i) => (
            <article key={i.id} className="rounded-xl border border-line bg-surface p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-bold text-ink">{i.customer}</span>
                <span className="text-xs text-muted">
                  in {fmtTime(i.timeIn)}
                  {i.replyAt !== null && (
                    <span className="ml-2 inline-flex items-center gap-1 text-accent">
                      <Timer className="h-3 w-3" aria-hidden="true" />
                      replied in {fmtLatency(i.replyAt - i.timeIn)}
                    </span>
                  )}
                </span>
                <button
                  onClick={() => remove(i.id)}
                  aria-label="Remove inquiry"
                  className="ml-auto rounded p-1 text-muted hover:text-ink"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <p className="mt-1 text-sm text-muted">{i.want}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {i.replyAt === null ? (
                  <Button size="sm" onClick={() => markReplied(i.id)}>
                    Mark replied
                  </Button>
                ) : (
                  <>
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted">Outcome:</span>
                    {(["recovered", "lost", "browsing"] as Outcome[]).map((o) => (
                      <button
                        key={o}
                        onClick={() => {
                          if (o === "recovered") {
                            const v = window.prompt("Order value in ₨?", String(i.orderValue ?? ""));
                            if (v === null) return;
                            setOutcome(i.id, o, parseOrderValue(v));
                          } else {
                            setOutcome(i.id, o);
                          }
                        }}
                        className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                          i.outcome === o
                            ? o === "recovered"
                              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                              : "border-line bg-background text-ink"
                            : "border-line text-muted hover:text-ink"
                        }`}
                      >
                        {o === "recovered" && i.orderValue ? `Recovered · ₨${i.orderValue.toLocaleString()}` : o}
                      </button>
                    ))}
                  </>
                )}
              </div>
            </article>
          ))}
        </section>

        <section aria-label="Verified-commitment log" className="mt-12">
          <h2 className="font-display text-lg text-ink">Verified-commitment log</h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            One entry per stage of a commitment — inquiry, order, payment,
            delivery, outcome — recorded with the seller&rsquo;s consent.
            Money starts as <strong className="text-ink">REPORTED</strong> and
            the form has an evidence reference and the seller consented. Mark VERIFIED only after you personally reviewed evidence
            under the outcome standard approved by the owner; merely typing a reference does not verify it. Use a pseudonymous
            reference (seller-01), never a name or phone number. Starts empty: no real sprint week has run yet.
          </p>

          <div className="mb-6 mt-4 rounded-xl border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold text-ink">Sync consented records to Hami</h3>
            <p className="mt-1 text-sm leading-6 text-muted">
              Optional manual sync to the existing owner-key-protected substrate. The key stays in this page's memory only.
              Sync sends a pseudonymous seller reference, stage, amount, consent and evidence-reference metadata; it never sends
              customer names, phone numbers, social handles, or the free-text note. The connector does not open or validate the
              referenced proof, so it never upgrades evidence by itself. If production returns HTTP 503, leave the maintenance gate intact.
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
              <input
                type="password"
                value={ownerKey}
                onChange={(event) => setOwnerKey(event.target.value)}
                autoComplete="off"
                spellCheck={false}
                aria-label="Owner API key (memory only)"
                placeholder="Owner API key — used in memory only"
                className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60"
              />
              <button
                type="button"
                onClick={() => setOwnerKey("")}
                className="rounded-lg border border-line px-3 py-2 text-sm text-muted hover:text-ink"
              >
                Clear key
              </button>
            </div>
          </div>

          <div className="mb-6 mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Inquiries logged", value: String(summary.inquiries) },
              { label: "Orders logged", value: String(summary.orders) },
              { label: "Recovered sales (verified)", value: String(summary.recoveredSales) },
              {
                label: "Rupees reported / verified",
                value: `₨${summary.rupeesReported.toLocaleString()} / ₨${summary.rupeesVerified.toLocaleString()}`,
              },
            ].map((s) => (
              <div key={s.label} className="rounded-xl border border-line bg-surface p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-muted">{s.label}</p>
                <p className="mt-1 font-display text-2xl text-ink">{s.value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-line bg-surface p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={cSellerRef}
                onChange={(e) => setCSellerRef(e.target.value)}
                placeholder="Seller reference — e.g. seller-01"
                aria-label="Seller reference"
                className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60"
              />
              <select
                value={cStage}
                onChange={(e) => setCStage(e.target.value as CommitmentStage)}
                aria-label="Commitment stage"
                className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink"
              >
                {COMMITMENT_STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <input
                value={cAmount}
                onChange={(e) => setCAmount(e.target.value)}
                placeholder="Amount in ₨ (payment stage)"
                aria-label="Amount in rupees"
                className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60"
              />
              <input
                value={cEvidenceRef}
                onChange={(e) => setCEvidenceRef(e.target.value)}
                placeholder="Evidence reference — e.g. owner-note-2026-10-24"
                aria-label="Evidence reference"
                className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60"
              />
              <input
                value={cNote}
                onChange={(e) => setCNote(e.target.value)}
                placeholder="Note (de-identified, one line)"
                aria-label="Note"
                className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60 sm:col-span-2"
              />
              {cStage === "outcome" && (
                <select
                  value={cRecovered}
                  onChange={(e) => setCRecovered(e.target.value)}
                  aria-label="Recovered?"
                  className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink"
                >
                  <option value="">Recovered? — unset</option>
                  <option value="yes">Recovered — yes</option>
                  <option value="no">Recovered — no</option>
                </select>
              )}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-muted">
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={cConsent} onChange={(e) => setCConsent(e.target.checked)} />
                Seller consented to this record
              </label>
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={cVerified} onChange={(e) => setCVerified(e.target.checked)} />
                I reviewed the evidence and seller consented (manual assertion)
              </label>
              <Button onClick={addCommitment} className="ml-auto">
                <Plus className="size-4" aria-hidden="true" /> Log stage
              </Button>
            </div>
            {cError && (
              <p role="alert" className="mt-3 text-sm text-amber-300">
                {cError}
              </p>
            )}
          </div>

          <div className="mt-4 grid gap-3">
            {entries.length === 0 && (
              <div className="rounded-xl border border-dashed border-line p-8 text-center">
                <p className="text-sm font-semibold text-ink">No commitments logged yet</p>
                <p className="mt-1 text-sm text-muted">
                  The honest empty state — entries appear only when a real,
                  consented sprint week produces them.
                </p>
              </div>
            )}
            {entries.map((e) => (
              <article key={e.id} className="rounded-xl border border-line bg-surface p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-bold text-ink">{e.sellerRef}</span>
                  <span className="rounded-full border border-line px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-muted">
                    {e.stage}
                  </span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                      e.verification === "verified"
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                        : "border-line text-muted"
                    }`}
                  >
                    {e.verification}
                  </span>
                  {e.amount !== null && (
                    <span className="text-sm text-ink">₨{e.amount.toLocaleString()}</span>
                  )}
                  {e.stage === "outcome" && e.recovered !== null && (
                    <span className="text-xs text-muted">
                      {e.recovered ? "recovered" : "not recovered"}
                    </span>
                  )}
                  <span className="text-xs text-muted">{fmtTime(e.at)}</span>
                  <button
                    onClick={() => removeCommitment(e.id)}
                    aria-label="Remove commitment entry"
                    className="ml-auto rounded p-1 text-muted hover:text-ink"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
                {e.note && <p className="mt-1 text-sm text-muted">{e.note}</p>}
                <p className="mt-1 text-xs text-muted">
                  {e.sellerConsent ? "Seller consented" : "No consent recorded"}
                  {e.evidenceRef ? ` · Evidence: ${e.evidenceRef}` : " · No evidence reference"}
                </p>
                {e.substrateSync ? (
                  <p className="mt-2 text-xs text-muted">
                    Canonical refs — seller ENTITY #{e.substrateSync.sellerEntityId} · commitment ENTITY #{e.substrateSync.commitmentEntityId} · RELATION #{e.substrateSync.relationId} · EVIDENCE #{e.substrateSync.evidenceId} · EVENT #{e.substrateSync.eventId}
                  </p>
                ) : (
                  <button
                    type="button"
                    disabled={!ownerKey.trim() || !e.sellerConsent || syncingId !== null}
                    onClick={() => void syncCommitment(e)}
                    className="mt-3 rounded-lg border border-line px-3 py-2 text-sm text-ink disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {syncingId === e.id ? "Syncing…" : "Sync consented entry to Hami"}
                  </button>
                )}
                {syncMessages[e.id] && (
                  <p role="status" className="mt-2 text-xs text-muted">{syncMessages[e.id]}</p>
                )}
              </article>
            ))}
          </div>
        </section>

        {items.length > 0 && (
          <div className="mt-6 text-right">
            <button onClick={clearAll} className="text-xs text-muted underline-offset-4 hover:underline">
              Clear all prototype data
            </button>
          </div>
        )}
      </Container>
    </main>
  );
}
