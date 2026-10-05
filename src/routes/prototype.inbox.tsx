import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical, Plus, Timer, Trash2 } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { isInquiry, parseOrderValue, type Inquiry, type Outcome } from "@/lib/prototype-inbox";

export const Route = createFileRoute("/prototype/inbox")({
  component: InboxPrototype,
  head: () => ({ meta: [{ title: "Inbox prototype — Hami" }] }),
});

const STORAGE_KEY = "hami-prototype-inbox-v1";

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
