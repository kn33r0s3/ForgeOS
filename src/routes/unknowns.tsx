import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { discoveryUnknowns, unknownsCount } from "@/lib/unknowns";
import { tierLabel, type ValueTier } from "@/lib/forge/value";
import { valueOf } from "@/lib/forge/value-tiers";

export const Route = createFileRoute("/unknowns")({
  component: UnknownsPage,
  head: () => ({
    meta: [
      { title: "Open unknowns — Hami" },
      {
        name: "description",
        content:
          "The questions Hami is working through — ranked by value, each with its state and cheapest test. Known unknowns with shape, not a feed of guesses.",
      },
    ],
  }),
});

type TierFilter = "all" | ValueTier;

const TIER_TABS: Array<{ key: TierFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: 3, label: "Money-close" },
  { key: 2, label: "Enablers" },
  { key: 1, label: "Understanding" },
];

function UnknownsPage() {
  const [tier, setTier] = useState<TierFilter>("all");
  const items = useMemo(() => {
    const scored = discoveryUnknowns.map((u) => ({ ...u, value: valueOf(u.id) }));
    const filtered = tier === "all" ? scored : scored.filter((u) => u.value.tier === tier);
    return [...filtered].sort((a, b) => {
      if (a.value.tier !== b.value.tier) return b.value.tier - a.value.tier;
      return b.round - a.round;
    });
  }, [tier]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: discoveryUnknowns.length, 1: 0, 2: 0, 3: 0 };
    for (const u of discoveryUnknowns) c[valueOf(u.id).tier] += 1;
    return c;
  }, []);

  return (
    <main>
      <PageHeader
        eyebrow="Hami · the fuel inventory"
        title="Open unknowns"
        lede={`Known unknowns with shape, tests, and stakes — ${unknownsCount} questions reality hasn't answered yet, ranked by value. This is what the engine works through, one round at a time. Nothing here is a claim; everything here is a question.`}
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter by value">
          {TIER_TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tier === t.key}
              onClick={() => setTier(t.key)}
              className={`min-h-10 rounded-full border-2 px-4 text-sm font-bold ${
                tier === t.key
                  ? "border-accent bg-accent text-black"
                  : "border-line bg-card text-muted hover:border-accent"
              }`}
            >
              {t.label} ({counts[t.key]})
            </button>
          ))}
        </div>

        <div className="mt-6 grid gap-4">
          {items.map((u) => (
            <article key={u.id} className="card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-accent">{u.id}</span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                    u.value.tier === 3
                      ? "border-accent/40 bg-accent/10 text-accent"
                      : u.value.tier === 2
                        ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
                        : "border-line bg-background text-muted"
                  }`}
                  title={u.value.why}
                >
                  {tierLabel(u.value.tier)}
                </span>
                <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
                  {u.stateNote.split("(")[0].trim()}
                </span>
                <span className="ml-auto text-xs text-muted">round {u.round}</span>
              </div>
              <h2 className="mt-2 font-display text-base font-bold leading-6 text-ink">
                {u.question}
              </h2>
              <p className="mt-1 text-xs italic text-muted/80">{u.value.why}</p>
              <div className="mt-3 grid gap-2 text-sm leading-6">
                <p className="text-muted">
                  <FlaskConical className="mr-1.5 inline size-4 text-accent" aria-hidden="true" />
                  <strong className="text-ink">Cheapest test:</strong> {u.cheapestTest}
                </p>
                <p className="text-muted">
                  <strong className="text-ink">Stakes:</strong> {u.stakes}
                </p>
              </div>
            </article>
          ))}
        </div>

        <p className="mt-8 border-t border-line pt-4 text-xs leading-5 text-dim">
          Unknowns are banked by the hourly discovery rounds through the evidence
          gate. A question leaves this list only when reality answers it —
          never by being filled in.
        </p>
      </Container>
    </main>
  );
}
