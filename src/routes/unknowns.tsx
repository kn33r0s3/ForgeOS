import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { fetchUnknowns, type ApiUnknown } from "@/lib/unknowns-api";

export const Route = createFileRoute("/unknowns")({
  component: UnknownsPage,
  head: () => ({
    meta: [
      { title: "Open unknowns — Hami" },
      {
        name: "description",
        content:
          "The questions Hami is working through — each with its state, cheapest test, and source. Known unknowns with shape, not a feed of guesses.",
      },
    ],
  }),
});

type StateFilter = "all" | string;

const STATE_STYLE: Record<string, string> = {
  unknown: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  blocked: "border-red-500/30 bg-red-500/10 text-red-200",
  tested: "border-sky-500/30 bg-sky-500/10 text-sky-200",
  supported: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  hypothesized: "border-violet-500/30 bg-violet-500/10 text-violet-200",
  contradicted: "border-orange-500/30 bg-orange-500/10 text-orange-200",
};

function UnknownsPage() {
  const [items, setItems] = useState<ApiUnknown[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<StateFilter>("all");

  useEffect(() => {
    let live = true;
    fetchUnknowns()
      .then((data) => {
        if (live) setItems(data);
      })
      .catch((e: unknown) => {
        if (live) setError(e instanceof Error ? e.message : "unavailable");
      });
    return () => {
      live = false;
    };
  }, []);

  const states = useMemo(() => {
    const s = new Set((items ?? []).map((u) => u.epistemic_state));
    return ["all", ...[...s].sort()];
  }, [items]);

  const filtered = useMemo(() => {
    const list = items ?? [];
    return state === "all" ? list : list.filter((u) => u.epistemic_state === state);
  }, [items, state]);

  return (
    <main>
      <PageHeader
        eyebrow="Hami · the fuel inventory"
        title="Open unknowns"
        lede="Questions reality hasn't answered yet — banked by the discovery rounds through the evidence gate, shown with their state and source. Nothing here is a claim; everything here is a question. Value tiers are earned by recorded give-up evidence, and none has been recorded yet, so every unknown is unscored."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        {error !== null && (
          <div className="card p-6" role="alert">
            <p className="font-bold text-ink">The unknowns list is unavailable right now.</p>
            <p className="mt-1 text-sm text-muted">
              The engine did not answer ({error}). This page shows only what the
              engine has recorded — it will not invent a list.
            </p>
          </div>
        )}
        {error === null && items === null && (
          <div className="card p-6" aria-busy="true">
            <p className="text-sm text-muted">Loading the unknowns the engine has banked…</p>
          </div>
        )}
        {error === null && items !== null && items.length === 0 && (
          <div className="card p-6">
            <p className="font-bold text-ink">No unknowns banked yet.</p>
            <p className="mt-1 text-sm text-muted">
              The discovery rounds have not recorded any questions. When they do,
              they appear here with their state and source.
            </p>
          </div>
        )}
        {error === null && items !== null && items.length > 0 && (
          <>
            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter by state">
              {states.map((s) => (
                <button
                  key={s}
                  role="tab"
                  aria-selected={state === s}
                  onClick={() => setState(s)}
                  className={`min-h-10 rounded-full border-2 px-4 text-sm font-bold ${
                    state === s
                      ? "border-accent bg-accent text-black"
                      : "border-line bg-card text-muted hover:border-accent"
                  }`}
                >
                  {s === "all" ? "All" : s} (
                  {s === "all"
                    ? items.length
                    : items.filter((u) => u.epistemic_state === s).length}
                  )
                </button>
              ))}
            </div>

            <div className="mt-6 grid gap-4">
              {filtered.map((u) => (
                <article key={u.id} className="card p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-accent">{u.row_id}</span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${STATE_STYLE[u.epistemic_state] ?? "border-line bg-background text-muted"}`}
                      title="Truth label: what the engine actually knows about this question"
                    >
                      {u.epistemic_state}
                    </span>
                    <span
                      className="rounded-full border border-line bg-background px-2 py-0.5 text-xs text-muted"
                      title="No give-up evidence recorded — the tier is unearned, not low"
                    >
                      unscored
                    </span>
                  </div>
                  <h2 className="mt-2 font-display text-base font-bold leading-6 text-ink">
                    {u.question}
                  </h2>
                  {u.cheapest_test && (
                    <p className="mt-3 text-sm leading-6 text-muted">
                      <FlaskConical
                        className="mr-1.5 inline size-4 text-accent"
                        aria-hidden="true"
                      />
                      <strong className="text-ink">Cheapest test:</strong> {u.cheapest_test}
                    </p>
                  )}
                  {u.provenance && (
                    <p className="mt-2 text-xs leading-5 text-dim">
                      Source: {u.provenance.split(". Cheapest test:")[0]}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </>
        )}

        <p className="mt-8 border-t border-line pt-4 text-xs leading-5 text-dim">
          Unknowns are banked by the hourly discovery rounds through the evidence
          gate. A question leaves this list only when reality answers it —
          never by being filled in.
        </p>
      </Container>
    </main>
  );
}
