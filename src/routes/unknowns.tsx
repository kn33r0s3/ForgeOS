import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { UnknownCard } from "@/components/unknowns/unknown-card";
import { PageHeader } from "@/components/layout/page-header";
import {
  loadPublicUnknowns,
  UNKNOWN_STATE_LABELS,
  type PublicUnknown,
  type UnknownState,
} from "@/lib/content";

export const Route = createFileRoute("/unknowns")({
  component: UnknownsPage,
  head: () => ({
    meta: [
      { title: "Open unknowns — Hami" },
      {
        name: "description",
        content:
          "The questions Hami is working through — each with its state, cheapest test, and stake. Known unknowns with shape, not a feed of guesses.",
      },
    ],
  }),
});

type StateFilter = "all" | UnknownState;

function UnknownsPage() {
  const [items, setItems] = useState<PublicUnknown[] | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [state, setState] = useState<StateFilter>("all");

  useEffect(() => {
    let live = true;
    loadPublicUnknowns(200)
      .then((data) => {
        if (live) {
          if (data === null) setUnavailable(true);
          else setItems(data);
        }
      })
      .catch(() => {
        if (live) setUnavailable(true);
      });
    return () => {
      live = false;
    };
  }, []);

  const states = useMemo(() => {
    const s = new Set((items ?? []).map((u) => u.state));
    return ["all" as const, ...[...s].sort()];
  }, [items]);

  const filtered = useMemo(() => {
    const list = items ?? [];
    return state === "all" ? list : list.filter((u) => u.state === state);
  }, [items, state]);

  return (
    <main>
      <PageHeader
        eyebrow="Hami · the fuel inventory"
        title="Open unknowns"
        lede="Questions reality hasn't answered yet — about the world, not Hami's backlog. Each shows its engine state, cheapest test, and what's at stake. Value tiers are earned by recorded give-up evidence, and none has been recorded yet, so every unknown is unscored."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        {unavailable && (
          <div className="card p-6" role="alert">
            <p className="font-bold text-ink">The unknowns list is unavailable right now.</p>
            <p className="mt-1 text-sm text-muted">
              Hami could not load the recorded unknowns. This page shows only what is recorded — it
              will not invent a list.
            </p>
          </div>
        )}
        {!unavailable && items === null && (
          <div className="card p-6" aria-busy="true">
            <p className="text-sm text-muted">Loading the recorded unknowns…</p>
          </div>
        )}
        {!unavailable && items !== null && items.length === 0 && (
          <div className="card p-6">
            <p className="font-bold text-ink">No unknowns recorded yet.</p>
            <p className="mt-1 text-sm text-muted">
              The discovery rounds have not banked any world questions. When they do, they appear
              here with their state, cheapest test, and stake.
            </p>
          </div>
        )}
        {!unavailable && items !== null && items.length > 0 && (
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
                  {s === "all" ? "All" : UNKNOWN_STATE_LABELS[s as UnknownState]} (
                  {s === "all" ? items.length : items.filter((u) => u.state === s).length})
                </button>
              ))}
            </div>

            <div className="mt-6 grid gap-4">
              {filtered.map((u) => (
                <UnknownCard key={u.id} unknown={u} />
              ))}
            </div>
          </>
        )}

        <p className="mt-8 border-t border-line pt-4 text-xs leading-5 text-dim">
          Unknowns are banked by the discovery rounds from real observations. World unknowns (about
          markets, sellers, behavior) appear here. Unknowns about Hami&apos;s own systems and
          backlog appear in the owner console only.
        </p>
      </Container>
    </main>
  );
}
