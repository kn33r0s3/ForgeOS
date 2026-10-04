import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { fetchUnknowns, type ApiUnknown } from "@/lib/unknowns-api";

export const Route = createFileRoute("/what-we-learned")({
  component: WhatWeLearnedPage,
  head: () => ({
    meta: [
      { title: "What we've learned — Hami" },
      {
        name: "description",
        content:
          "Only what Hami's engine has recorded, each item with its truth state and source. Nothing on this page was written by hand.",
      },
      { property: "og:title", content: "Hami" },
    ],
  }),
});

const STATE_STYLE: Record<string, string> = {
  unknown: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  blocked: "border-red-500/30 bg-red-500/10 text-red-200",
  tested: "border-sky-500/30 bg-sky-500/10 text-sky-200",
  supported: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  hypothesized: "border-violet-500/30 bg-violet-500/10 text-violet-200",
  contradicted: "border-orange-500/30 bg-orange-500/10 text-orange-200",
};

function WhatWeLearnedPage() {
  const [items, setItems] = useState<ApiUnknown[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const groups = useMemo(() => {
    const map = new Map<string, ApiUnknown[]>();
    for (const u of items ?? []) {
      const list = map.get(u.epistemic_state) ?? [];
      list.push(u);
      map.set(u.epistemic_state, list);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [items]);

  return (
    <main>
      <PageHeader
        eyebrow="Hami · the record"
        title="What we've learned"
        lede="Only what the engine has recorded — each item with its truth state and source. Nothing on this page was written by hand. A finding moves up only when evidence does."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        {error !== null && (
          <div className="card p-6" role="alert">
            <p className="font-bold text-ink">The record is unavailable right now.</p>
            <p className="mt-1 text-sm text-muted">
              The engine did not answer ({error}). This page shows only what the
              engine has recorded — it will not invent findings.
            </p>
          </div>
        )}
        {error === null && items === null && (
          <div className="card p-6" aria-busy="true">
            <p className="text-sm text-muted">Loading what the engine has recorded…</p>
          </div>
        )}
        {error === null && items !== null && items.length === 0 && (
          <div className="card p-6">
            <p className="font-bold text-ink">Nothing recorded yet.</p>
            <p className="mt-1 text-sm text-muted">
              The engine has not banked any findings. When it does, they appear
              here with their truth state and source — not before.
            </p>
          </div>
        )}
        {error === null && items !== null && items.length > 0 && (
          <>
            <p className="text-sm text-muted">
              {items.length} recorded findings. Every one passed the evidence
              gate; every one carries its source.
            </p>
            {groups.map(([state, list]) => (
              <section key={state} aria-label={`Findings in state ${state}`} className="mt-8">
                <h2 className="flex items-center gap-3 font-display text-xl font-black text-ink">
                  <span
                    className={`rounded-full border px-3 py-1 text-xs font-semibold ${STATE_STYLE[state] ?? "border-line bg-background text-muted"}`}
                  >
                    {state}
                  </span>
                  <span className="text-sm font-bold text-muted">
                    {list.length} {list.length === 1 ? "finding" : "findings"}
                  </span>
                </h2>
                <div className="mt-4 grid gap-4">
                  {list.map((u) => (
                    <article key={u.id} className="card p-5">
                      <p className="text-xs font-bold text-accent">{u.row_id}</p>
                      <h3 className="mt-1 font-display text-base font-bold leading-6 text-ink">
                        {u.question}
                      </h3>
                      {u.cheapest_test && (
                        <p className="mt-3 text-sm leading-6 text-muted">
                          <strong className="text-ink">Cheapest test:</strong>{" "}
                          {u.cheapest_test}
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
              </section>
            ))}
          </>
        )}

        <p className="mt-8 border-t border-line pt-4 text-xs leading-5 text-dim">
          Findings are banked by the discovery rounds through the evidence gate.
          Nothing here is a hand-written claim — if the engine did not record
          it, it is not on this page.
        </p>
      </Container>
    </main>
  );
}
