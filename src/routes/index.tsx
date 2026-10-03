import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Eye, Lightbulb, Link2, ShieldCheck, Sparkles } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";
import { SystemEditor } from "@/components/system/system-editor";
import {
  PanelTitle,
  PathCard,
  ProgressPanel,
  SituationPanel,
  WorldStream,
} from "@/components/system/system-panels";
import { loadPublicFeed, type PublicFeedItem } from "@/lib/content";
import { derivePaths, deriveStages, relevantFeed } from "@/lib/system/paths";
import { hasAnyState } from "@/lib/system/state";
import { useSystemState } from "@/lib/system/use-system";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({
    meta: [
      { title: "Hami — observing reality" },
      {
        name: "description",
        content:
          "Hami observes recorded sources, evidence, relationships, and uncertainty to discover what may matter without assuming one fixed workflow.",
      },
    ],
  }),
});

function useWorldFeed() {
  const [items, setItems] = useState<PublicFeedItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    void loadPublicFeed(40).then((result) => {
      if (!active) return;
      setItems(result);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);
  return { items, loading, unavailable: !loading && items === null };
}

function HomePage() {
  const { state, ready, update, mode, error } = useSystemState();
  const world = useWorldFeed();
  const active = hasAnyState(state);

  const paths = useMemo(() => (active ? derivePaths(state) : []), [active, state]);
  const stages = useMemo(() => (active ? deriveStages(state) : []), [active, state]);
  const relevant = useMemo(
    () => (active && world.items ? relevantFeed(state, world.items) : []),
    [active, state, world.items],
  );

  return (
    <main>
      {!ready ? (
        <Container className="py-20">
          <p className="text-sm text-dim" role="status">
            Opening your System…
          </p>
        </Container>
      ) : error ? (
        <Container className="py-20">
          <p className="text-sm font-semibold text-danger" role="alert">{error}</p>
        </Container>
      ) : active ? (
        <ActiveSystem
          paths={paths}
          stages={stages}
          state={state}
          world={world}
          relevant={relevant}
        />
      ) : (
        <Welcome onStart={update} state={state} world={world} privacyMode={mode} />
      )}
      <CurrentPaths />
    </main>
  );
}

/* ------------------------------------------------------------------ */

function CurrentPaths() {
  return (
    <section aria-labelledby="current-paths-title" className="border-t-2 border-black bg-card py-10 sm:py-14">
      <Container>
        <div className="max-w-3xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
            Existing paths
          </p>
          <h2 id="current-paths-title" className="mt-2 font-display text-3xl font-black tracking-tight text-ink">
            Start with what is actually available.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            These pages show recorded information and current routes. A hypothesis is not a validated
            opportunity, and a recorded action is not permission to execute it.
          </p>
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <article className="card p-5">
            <h3 className="font-display text-lg font-bold text-ink">Observations and discoveries</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Review public-source observations and accessible persisted findings. Restricted substrate
              records remain unavailable without their server-side authorization.
            </p>
            <Link to="/discoveries" className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
              Review discoveries <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </article>
          <article className="card p-5">
            <h3 className="font-display text-lg font-bold text-ink">Hypotheses and action state</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              See what is publicly surfaced as a possibility and the aggregate action state. Neither
              view represents a sale, approval, or completed outcome.
            </p>
            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2">
              <Link to="/opportunities" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
                Opportunities <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link to="/actions" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
                Action state <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </article>
          <article className="card p-5">
            <h3 className="font-display text-lg font-bold text-ink">Business information</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Read the current business information and the status of the existing Forge Bot inquiry
              path. Online lead intake remains closed.
            </p>
            <Link to="/group/businesses" className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
              For businesses <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </article>
        </div>
      </Container>
    </section>
  );
}

/* ------------------------------------------------------------------ */

function ActiveSystem({
  state,
  paths,
  stages,
  world,
  relevant,
}: {
  state: NonNullable<ReturnType<typeof useSystemState>["state"]>;
  paths: ReturnType<typeof derivePaths>;
  stages: ReturnType<typeof deriveStages>;
  world: ReturnType<typeof useWorldFeed>;
  relevant: ReturnType<typeof relevantFeed>;
}) {
  const next = stages.find((s) => !s.reached && !s.evidenceGated);
  return (
    <Container className="py-8 sm:py-10">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b-2 border-line pb-6">
        <div>
          <p className="flex items-center gap-2 font-mono text-[0.7rem] font-bold uppercase tracking-[0.18em] text-accent">
            <span className="live-dot" aria-hidden="true" /> System active
            {state.location ? <span className="text-dim">· {state.location.value}</span> : null}
          </p>
          <h1 className="mt-2 text-[clamp(1.9rem,4vw,2.9rem)] font-black leading-[1.05] tracking-[-0.03em] text-ink">
            {paths.length
              ? `${paths.length} possible ${paths.length === 1 ? "path" : "paths"} from what you have.`
              : "Your System is listening."}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Paths are possibilities, not promises. Each shows what is still unknown and the smallest real
            next step.
          </p>
        </div>
        {next ? (
          <Link
            to="/system"
            className="inline-flex min-h-11 items-center gap-2 rounded-card border-2 border-accent/70 bg-black px-4 text-sm font-extrabold text-accent hover:bg-accent hover:text-black"
          >
            Edit your context <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        ) : null}
      </header>

      <div className="mt-8 grid gap-6 lg:grid-cols-[18.5rem_minmax(0,1fr)_22rem]">
        <div className="grid content-start gap-6">
          <SituationPanel state={state} />
          <ProgressPanel stages={stages} />
        </div>

        <section aria-label="Possible paths" className="min-w-0">
          <PanelTitle icon={Lightbulb} kicker="What is possible" title="Paths from your gear" />
          {paths.length ? (
            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              {paths.map((p) => (
                <PathCard key={p.id} path={p} />
              ))}
            </div>
          ) : (
            <div className="card mt-4 p-6">
              <p className="text-sm leading-6 text-muted">
                Add a capability or something you own and Hami will show what it could connect to.
              </p>
              <Link to="/system" className="link-arrow mt-3 inline-flex items-center gap-1 text-sm font-bold text-accent">
                Edit personal context <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          )}
        </section>

        <div className="min-w-0">
          <WorldStream
            items={world.items}
            relevant={relevant}
            loading={world.loading}
            unavailable={world.unavailable}
          />
        </div>
      </div>
    </Container>
  );
}

/* ------------------------------------------------------------------ */

const LOOP = [
  { icon: Eye, title: "Observes", body: "Sourced records and the substrate show only what is actually recorded." },
  { icon: Link2, title: "Discovers", body: "Existing methods can surface contradictions, relationships, questions, and capability gaps." },
  { icon: Lightbulb, title: "Keeps uncertainty", body: "Possible and hypothesized findings stay distinct from supported claims." },
  { icon: ShieldCheck, title: "Preserves agency", body: "External action requires authorization; outcomes require real evidence." },
];

function Welcome({
  onStart,
  state,
  world,
  privacyMode,
}: {
  onStart: ReturnType<typeof useSystemState>["update"];
  state: ReturnType<typeof useSystemState>["state"];
  world: ReturnType<typeof useWorldFeed>;
  privacyMode: "guest" | "account";
}) {
  return (
    <>
      <section className="relative isolate overflow-hidden border-b-2 border-black">
        <div className="hero-glow -z-10" aria-hidden="true" />
        <div className="hero-grain -z-10" aria-hidden="true" />
        <Container className="py-12 sm:py-16 lg:py-20">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(24rem,30rem)] lg:gap-14">
            <div>
              <p className="flex items-center gap-2 font-mono text-[0.72rem] font-bold uppercase tracking-[0.18em] text-accent">
                <Sparkles className="size-4" aria-hidden="true" /> Hami · Nepal first
              </p>
              <h1 className="mt-5 max-w-3xl text-[clamp(2.6rem,5.8vw,5rem)] font-black leading-[0.98] tracking-[-0.045em] text-ink">
                A system that keeps observing reality
                <span className="mt-2 block text-muted">and noticing what may matter.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
                Hami follows recorded sources, evidence, relationships, questions, and capability gaps without assuming one category or workflow.
                Personal context is separate from the public world. Guests can keep temporary context in this tab; signed-in users can save it privately. Hami never puts it in public feed or network projections, and sharing requires your authorization.
              </p>
              <div className="mt-6 flex flex-col items-start gap-3">
                <Button asChild size="lg">
                  <Link to="/forge-bot-intake">
                    Share a business need
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </Link>
                </Button>
                <p className="max-w-xl text-sm leading-6 text-muted">
                  For business owners, Hami helps clarify a need and find a practical next step.
                </p>
              </div>
              <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-2">
                {LOOP.map(({ icon: Icon, title, body }) => (
                  <div key={title} className="glass flex gap-3 p-4">
                    <Icon className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-extrabold text-ink">{title}</p>
                      <p className="mt-0.5 text-sm leading-5 text-muted">{body}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card border-accent/60 p-5 sm:p-6" id="start">
              <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
                Personal context · optional
              </p>
              <h2 className="mt-1 text-2xl font-black tracking-tight text-ink">What should Hami keep in mind?</h2>
              <div className="mt-5">
                <SystemEditor state={state} onSave={onStart} privacyMode={privacyMode} compact />
              </div>
            </div>
          </div>
        </Container>
      </section>

      <Container className="py-12 sm:py-14">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div>
            <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
              One open world, not one workflow
            </p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-ink">
              The right next step depends on what reality shows.
            </h2>
            <p className="mt-3 max-w-xl text-base leading-7 text-muted">
              One question may need a simple lookup; another may require several sources, contradiction checks,
              an experiment, or a missing capability. Hami’s purpose stays stable while the investigation method
              can change.
            </p>
            <p className="mt-4 max-w-xl text-sm leading-6 text-dim">
              The discoveries view separates persisted substrate findings from public source observations.
              Empty or protected data stays visibly empty or unavailable; no synthetic records fill the gap.
            </p>
          </div>
          <WorldStream items={world.items} relevant={[]} loading={world.loading} unavailable={world.unavailable} />
        </div>
      </Container>
    </>
  );
}
