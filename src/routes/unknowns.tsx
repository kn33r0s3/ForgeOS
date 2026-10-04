import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
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

const STATE_STYLE: Record<string, string> = {
  UNKNOWN: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  BLOCKED_BY_MISSING_ACCESS: "border-red-500/30 bg-red-500/10 text-red-200",
  TESTED: "border-sky-500/30 bg-sky-500/10 text-sky-200",
  SUPPORTED: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  HYPOTHESIZED: "border-violet-500/30 bg-violet-500/10 text-violet-200",
  CONTRADICTED: "border-orange-500/30 bg-orange-500/10 text-orange-200",
};

function UnknownsPage() {
  const [items, setItems] = useState<PublicUnknown[] | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [state, setState] = useState<StateFilter>("all");
  const [activeLane, setActiveLane] = useState<"known" | "tensions" | "surprises">("known");

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
        {/* Three lanes */}
        <div className="mb-6 flex flex-wrap gap-2" role="tablist" aria-label="Unknown lanes">
          {(
            [
              { id: "known", label: "Known unknowns" },
              { id: "tensions", label: "Tensions & dependencies" },
              { id: "surprises", label: "Surprises from reality" },
            ] as const
          ).map((lane) => (
            <button
              key={lane.id}
              role="tab"
              aria-selected={activeLane === lane.id}
              onClick={() => setActiveLane(lane.id)}
              className={`min-h-10 rounded-full border-2 px-4 text-sm font-bold ${
                activeLane === lane.id
                  ? "border-accent bg-accent text-black"
                  : "border-line bg-card text-muted hover:border-accent"
              }`}
            >
              {lane.label}
              {lane.id === "known" && items ? ` (${items.length})` : ""}
              {lane.id === "tensions" ? " (6)" : ""}
              {lane.id === "surprises" ? " (0)" : ""}
            </button>
          ))}
        </div>

        {activeLane === "tensions" && <TensionsLane />}
        {activeLane === "surprises" && <SurprisesLane />}

        {activeLane === "known" && !unavailable && items !== null && items.length > 0 && (
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

const TENSIONS: Array<{ id: string; type: string; title: string; text: string; cites: string }> = [
  {
    id: "T1",
    type: "TENSION",
    title: "Distribution vs presence: the wedge contradicts itself",
    text: "P1 says distribution is the killer (need more customers). P3 says presence is the binding constraint (can't handle existing inquiries). If presence binds, then 'find more opportunities' actively harms the seller.",
    cites: "E1 (563 views → 0 signups) vs E2/E3 (too busy to answer, lost job)",
  },
  {
    id: "T2",
    type: "TENSION",
    title: "Sprint offer is vendor-shaped; evidence says vendors are auto-distrusted",
    text: "The First Rupee Sprint offers a service for a cut. P2's evidence: 'anything that smells like a vendor is automatically distrusted.' No recorded evidence shows a seller accepting this model.",
    cites: "I2 vs docs/FIRST_RUPEE_SPRINT.md",
  },
  {
    id: "T3",
    type: "TENSION",
    title: "Sprint payment path relies on the system evidence says is broken",
    text: "I5 establishes payments as the top complaint — caps, no gateways, fragile workarounds. The sprint routes the first rupee through personal eSewa/Khalti. No evidence this works for business.",
    cites: "I5, E7 vs docs/SPRINT_READY.md",
  },
  {
    id: "H1",
    type: "HIDDEN DEPENDENCY",
    title: "Discovery depends on English-searchable discourse",
    text: "Every discovery round assumes owners talk in English on searchable platforms. Dry wells proved Nepali owners don't. Never listed as an unknown — it's structural.",
    cites: "Dry wells, deep-listening-synthesis.md §5",
  },
  {
    id: "H2",
    type: "HIDDEN DEPENDENCY",
    title: "Hami's trust path depends entirely on the owner's personal relationships",
    text: "Hami is vendor-shaped and will be auto-distrusted per P2. The only trust bridge is the owner's existing relationships. Not a tactic — structural.",
    cites: "I2, E7",
  },
  {
    id: "H3",
    type: "HIDDEN DEPENDENCY",
    title: "Unknowns API depends on manual JSON sync",
    text: "Deployed API can't read docs/. Serves manually-synced JSON. If UNKNOWN_MAP.md is edited without sync, API serves stale data silently. No CI check.",
    cites: "backend/app/data/unknowns.json",
  },
];

function TensionsLane() {
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        Tensions and hidden dependencies found in Hami&apos;s own recorded evidence.
        Each cites the specific records it comes from.
      </p>
      {TENSIONS.map((t) => (
        <article key={t.id} className="card p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold text-accent">{t.id}</span>
            <span
              className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                t.type === "TENSION"
                  ? "border-orange-500/30 bg-orange-500/10 text-orange-200"
                  : "border-violet-500/30 bg-violet-500/10 text-violet-200"
              }`}
            >
              {t.type}
            </span>
          </div>
          <h3 className="mt-2 font-display text-base font-bold leading-6 text-ink">
            {t.title}
          </h3>
          <p className="mt-2 text-sm leading-6 text-muted">{t.text}</p>
          <p className="mt-2 text-xs text-dim">
            <strong>Cites:</strong> {t.cites}
          </p>
        </article>
      ))}
    </div>
  );
}

function SurprisesLane() {
  return (
    <div className="card p-6">
      <p className="font-bold text-ink">No surprises from reality yet.</p>
      <p className="mt-1 text-sm text-muted">
        Surprises come only from real contact with the world — a conversation, a
        transaction, an outcome. No real-world contacts have been recorded yet.
        When they are, surprises appear here.
      </p>
      <p className="mt-3 font-mono text-xs text-dim">
        Surprises from reality: 0. Real-world contacts recorded: 0.
      </p>
    </div>
  );
}
