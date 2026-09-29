import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BookOpenCheck,
  CircleCheck,
  Compass,
  Eye,
  FlaskConical,
  Lightbulb,
  Network,
  Radio,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Container } from "@/components/layout/container";
import { EmptyState, MetricTile, Skeleton, SkeletonCards } from "@/components/ui/feedback";
import {
  loadDiscoveries,
  loadEngineHealth,
  loadPublicFeed,
  type EngineHealth,
  type PublicDiscovery,
  type PublicFeedItem,
} from "@/lib/content";
import {
  loadRuntimeSnapshot,
  type RuntimeSnapshot,
} from "@/lib/operations-data";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({ meta: [{ title: "Hami — Discover what matters" }] }),
});

function HomePage() {
  const [health, setHealth] = useState<EngineHealth | null>(null);
  const [runtime, setRuntime] = useState<RuntimeSnapshot | null>(null);
  const [feed, setFeed] = useState<PublicFeedItem[] | null>(null);
  const [discoveries, setDiscoveries] = useState<PublicDiscovery[] | null>(null);
  const [unavailable, setUnavailable] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.allSettled([
      loadEngineHealth(),
      loadRuntimeSnapshot(),
      loadPublicFeed(40),
      loadDiscoveries(3),
    ]).then(([healthResult, runtimeResult, feedResult, discoveryResult]) => {
      if (!active) return;
      const failed: string[] = [];

      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value);
        if (!healthResult.value.reachable) failed.push("health");
      } else {
        setHealth(null);
        failed.push("health");
      }
      if (runtimeResult.status === "fulfilled") setRuntime(runtimeResult.value);
      else {
        setRuntime(null);
        failed.push("system state");
      }
      if (feedResult.status === "fulfilled" && feedResult.value !== null) {
        setFeed(feedResult.value);
      } else {
        setFeed(null);
        failed.push("public network records");
      }
      if (discoveryResult.status === "fulfilled" && discoveryResult.value !== null) {
        setDiscoveries(discoveryResult.value);
      } else {
        setDiscoveries(null);
        failed.push("research observations");
      }

      setUnavailable(failed);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [reloadVersion]);

  const signals = useMemo(
    () => feed?.filter((item) => item.kind === "signal") ?? [],
    [feed],
  );
  const opportunities = useMemo(
    () => feed?.filter((item) => item.kind === "opportunity") ?? [],
    [feed],
  );
  const evidenceLinks = useMemo(
    () => feed?.reduce(
      (total, item) => total + item.relations.filter((relation) =>
        ["supported_by", "grounded_in", "informed_by"].includes(relation.relation),
      ).length,
      0,
    ) ?? null,
    [feed],
  );
  const labels = runtime?.truth?.epistemic_labels;
  const pendingActions = runtime?.truth?.operations.pending_actions ?? null;
  const actualOutcomes = labels?.actual_outcomes;
  const validatedOpportunities = labels?.human_validated_problems;
  const lastCycle = runtime?.cycles.last_completed;
  const systemReachable = health?.reachable === true;

  const statusTone = loading ? "idle" : systemReachable ? "live" : "warning";

  return (
    <main>
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="hero-glow" aria-hidden="true" />
        <div className="hero-grain" aria-hidden="true" />
        <Container className="relative grid items-center gap-10 py-14 sm:py-20 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-14 lg:py-24">
          <div>
            <p className="reveal flex items-center gap-2 font-mono text-micro uppercase tracking-[0.14em] text-accent">
              <span aria-hidden="true" className="h-px w-6 bg-accent/70" />
              Hami · Nepal-first intelligence
            </p>
            <h1
              className="reveal mt-5 font-display text-[clamp(2.75rem,6.4vw,5.25rem)] leading-[0.96] text-balance tracking-tight text-ink"
              style={{ "--i": 1 } as React.CSSProperties}
            >
              Discover what matters.
              <br />
              <span className="text-gradient-gold">
                Understand it. <span className="whitespace-nowrap">Act on it.</span>
              </span>
            </h1>
            <p
              className="reveal mt-6 max-w-xl text-lede text-muted"
              style={{ "--i": 2 } as React.CSSProperties}
            >
              Hami connects observations, research, options, decisions, and outcomes.
              Evidence stays visible; a hypothesis never becomes a customer or a result
              just because it is recorded.
            </p>
            <div className="reveal mt-9 flex flex-wrap items-center gap-3" style={{ "--i": 3 } as React.CSSProperties}>
              <Link
                to="/feed"
                className="link-arrow group inline-flex h-12 items-center gap-2 rounded-card bg-accent px-6 text-sm font-semibold text-accent-ink shadow-[0_12px_32px_-12px_rgb(226_160_26/0.6)] transition-[background-color,transform] duration-150 hover:bg-accent/90 active:scale-[0.98]"
              >
                Explore the network <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                to="/discoveries"
                className="inline-flex h-12 items-center gap-2 rounded-card border border-line bg-card/60 px-5 text-sm font-semibold text-ink transition-colors hover:border-accent/60"
              >
                Review research
              </Link>
              <Link
                to="/operations"
                className="link-arrow inline-flex h-12 items-center gap-1.5 px-2 text-sm font-semibold text-muted transition-colors hover:text-accent"
              >
                Operating dashboard <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
            <ul
              className="reveal mt-10 grid max-w-xl gap-4 border-t border-line pt-6 text-sm text-muted sm:grid-cols-3"
              style={{ "--i": 4 } as React.CSSProperties}
              aria-label="Operating principles"
            >
              <li className="flex items-start gap-2">
                <Eye className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                Evidence stays visible
              </li>
              <li className="flex items-start gap-2">
                <Scale className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                Hypotheses stay labelled
              </li>
              <li className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                Owner approves actions
              </li>
            </ul>
          </div>

          {/* Visual: workshop photograph with a live system card over it. */}
          <div className="reveal relative" style={{ "--i": 2 } as React.CSSProperties}>
            <div
              aria-hidden="true"
              className="absolute -inset-6 rounded-[2rem] bg-[radial-gradient(closest-side,rgb(226_160_26/0.22),transparent)] blur-2xl"
            />
            <figure className="relative overflow-hidden rounded-card border border-line">
              <img
                src="/hami-home.jpg"
                alt="A lit workbench with tools and an open notebook in a dusk workshop doorway"
                width={1376}
                height={768}
                fetchPriority="high"
                className="aspect-[4/3] w-full object-cover object-[52%_45%] sm:aspect-[16/12] lg:aspect-[5/6]"
              />
              <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-paper via-paper/10 to-transparent" />
            </figure>

            <section
              aria-labelledby="continuation-heading"
              className="glass relative -mt-20 mx-3 p-5 sm:absolute sm:-bottom-10 sm:right-5 sm:mx-0 sm:mt-0 sm:w-[21rem]"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-sm font-semibold text-ink" role="status">
                  <span
                    className={
                      statusTone === "live"
                        ? "live-dot"
                        : statusTone === "warning"
                          ? "live-dot live-dot-warning"
                          : "live-dot live-dot-idle"
                    }
                    aria-hidden="true"
                  />
                  {loading ? "Checking system" : systemReachable ? "System connected" : "System state unavailable"}
                </p>
                <Activity className="size-4 text-accent" aria-hidden="true" />
              </div>
              <h2 id="continuation-heading" className="mt-4 font-display text-2xl tracking-tight text-ink">
                What happens next
              </h2>
              {loading ? (
                <Skeleton className="mt-3 h-3 w-4/5" />
              ) : (
                <p className="mt-1.5 text-sm leading-6 text-muted">
                  {runtime
                    ? runtime.active_stage
                    : "The continuation state has not loaded. No activity is assumed."}
                </p>
              )}
              <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm">
                <div>
                  <dt className="font-mono text-micro uppercase tracking-[0.1em] text-dim">Queued tasks</dt>
                  <dd className="mt-1 font-semibold tabular-nums text-ink">
                    {loading ? <Skeleton className="h-4 w-8" /> : runtime ? runtime.worker.queued_tasks.toLocaleString() : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-micro uppercase tracking-[0.1em] text-dim">Last cycle</dt>
                  <dd className="mt-1 font-semibold text-ink">
                    {loading ? (
                      <Skeleton className="h-4 w-20" />
                    ) : lastCycle?.ended_at ? (
                      new Date(lastCycle.ended_at).toLocaleString()
                    ) : lastCycle ? (
                      "Recorded, time unknown"
                    ) : runtime ? (
                      "None recorded"
                    ) : (
                      "Unavailable"
                    )}
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        </Container>
      </section>

      <Container className="max-w-site py-14 sm:py-20">
        {unavailable.length > 0 ? (
          <div
            role="status"
            className="fade-in mb-8 flex flex-wrap items-center justify-between gap-3 rounded-card border border-warning/35 bg-warning/5 px-4 py-3 text-sm text-ink"
          >
            <span className="flex items-center gap-2">
              <span className="live-dot live-dot-warning" aria-hidden="true" />
              Some live panels could not be checked: {unavailable.join(", ")}. Unavailable data is not shown as zero.
            </span>
            <button
              type="button"
              onClick={() => setReloadVersion((version) => version + 1)}
              className="inline-flex min-h-10 items-center gap-2 rounded-card px-3 font-semibold text-accent transition-colors hover:bg-secondary"
            >
              <RefreshCw className="size-4" aria-hidden="true" /> Refresh
            </button>
          </div>
        ) : null}

        {/* ── System overview ─────────────────────────────────────────── */}
        <section aria-labelledby="overview-heading">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-mono text-micro uppercase tracking-[0.14em] text-accent">System state</p>
              <h2 id="overview-heading" className="mt-2 font-display text-4xl tracking-tight text-ink sm:text-5xl">
                Live state, not theatre.
              </h2>
            </div>
            <p className="max-w-sm text-sm leading-6 text-muted">
              Counts come straight from stored records. A dash means the source could not be checked.
            </p>
          </div>
          <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-5">
            <MetricTile index={0} icon={Radio} loading={loading} label="Public signals" value={feed === null ? null : signals.length} note="Visible observation records" />
            <MetricTile index={1} icon={FlaskConical} loading={loading} label="Research tasks" value={runtime?.research_tasks ?? null} note="All recorded task states" />
            <MetricTile index={2} icon={Lightbulb} loading={loading} label="Opportunities" value={feed === null ? null : opportunities.length} note="Public hypotheses, not commitments" />
            <MetricTile index={3} icon={BookOpenCheck} loading={loading} label="Pending actions" value={pendingActions} note="Stored review states; execution is not inferred" />
            <MetricTile index={4} icon={CircleCheck} loading={loading} tone="accent" className="col-span-2 lg:col-span-1" label="Outcomes" value={actualOutcomes ?? null} note="REAL-scope outcome records" />
          </div>
        </section>

        {/* ── Evidence + side panels ─────────────────────────────────── */}
        <section className="mt-14 grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
          <div className="card p-5 sm:p-7">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-mono text-micro uppercase tracking-[0.14em] text-accent">Evidence trail</p>
                <h2 className="mt-2 font-display text-3xl tracking-tight text-ink">Recent public records</h2>
              </div>
              <Link to="/feed" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                Open network <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
            {loading ? (
              <SkeletonCards count={3} label="Loading recent public records" className="mt-6 space-y-3" />
            ) : feed === null ? (
              <p className="mt-6 rounded-card border border-line bg-paper p-4 text-sm text-muted">
                Public records are unavailable right now; no empty result is inferred.
              </p>
            ) : feed.length === 0 ? (
              <EmptyState
                className="mt-6"
                headingLevel="h3"
                icon={Sparkles}
                title="No public records yet"
                body="No public records are available to show yet. Records appear here once a sourced observation, a verified provider or a public work post exists."
              >
                <Link to="/domain" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                  Post to the work board <ArrowUpRight className="size-4" aria-hidden="true" />
                </Link>
                <Link to="/providers" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-muted hover:text-accent">
                  Browse providers <ArrowUpRight className="size-4" aria-hidden="true" />
                </Link>
              </EmptyState>
            ) : (
              <ol className="mt-6 space-y-3">
                {feed.slice(0, 4).map((item, index) => (
                  <li
                    key={item.id}
                    className="card card-interactive reveal p-4 sm:p-5"
                    style={{ "--i": index } as React.CSSProperties}
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="status-pill status-pill-accent">{item.kind.replaceAll("_", " ")}</span>
                      <span className="text-muted">{item.epistemic_state.replaceAll("_", " ")}</span>
                      {item.source ? <span className="text-dim">· {item.source}</span> : null}
                    </div>
                    <h3 className="mt-3 font-display text-xl tracking-tight text-ink">{item.title}</h3>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted">{item.summary}</p>
                    {item.relations.length > 0 ? (
                      <p className="mt-2 flex items-center gap-1.5 text-xs text-dim">
                        <Network className="size-3.5" aria-hidden="true" />
                        {item.relations.length} recorded connection{item.relations.length === 1 ? "" : "s"}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
            {!loading && evidenceLinks !== null ? (
              <p className="mt-5 border-t border-line pt-4 text-xs text-muted">
                {evidenceLinks.toLocaleString()} visible evidence-related links in this projection.
              </p>
            ) : null}
          </div>

          <div className="space-y-5">
            <section className="card card-accent p-5 sm:p-6">
              <div className="flex items-center gap-2 text-accent">
                <Compass className="size-4" aria-hidden="true" />
                <p className="font-mono text-micro uppercase tracking-[0.14em]">Opportunity status</p>
              </div>
              {loading ? (
                <div className="mt-4 space-y-2">
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                </div>
              ) : feed === null ? (
                <p className="mt-4 text-sm text-muted">Opportunity records are unavailable.</p>
              ) : opportunities.length === 0 ? (
                <p className="mt-4 text-sm leading-6 text-muted">
                  No public opportunity hypotheses are surfaced yet. Hami does not invent opportunities to fill this space.
                </p>
              ) : (
                <>
                  <p className="mt-4 font-display text-5xl leading-none tracking-tight tabular-nums text-ink">
                    {opportunities.length}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    public hypothesis record{opportunities.length === 1 ? "" : "s"} surfaced. They remain hypotheses until evidence and human validation support them.
                  </p>
                </>
              )}
              {validatedOpportunities === 0 ? (
                <p className="mt-4 rounded-card border border-line bg-paper/60 px-3 py-2 text-sm font-medium text-ink">
                  No verified opportunities yet.
                </p>
              ) : validatedOpportunities != null ? (
                <p className="mt-3 text-sm text-muted">
                  Human-validated opportunity records: {validatedOpportunities.toLocaleString()}.
                </p>
              ) : null}
              <Link to="/opportunities" className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                Review opportunities <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </section>

            <section className="card p-5 sm:p-6">
              <div className="flex items-center gap-2 text-accent">
                <Network className="size-4" aria-hidden="true" />
                <p className="font-mono text-micro uppercase tracking-[0.14em]">Research activity</p>
              </div>
              {loading ? (
                <div className="mt-4 space-y-3">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              ) : discoveries === null ? (
                <p className="mt-3 text-sm text-muted">Research observations are unavailable.</p>
              ) : discoveries.length === 0 ? (
                <p className="mt-3 text-sm leading-6 text-muted">No external source observations are currently available to show.</p>
              ) : (
                <ul className="mt-4 space-y-4">
                  {discoveries.slice(0, 2).map((item) => (
                    <li key={item.id} className="border-l-2 border-accent/50 pl-3">
                      <p className="text-sm font-semibold text-ink">{item.title || "Untitled observation"}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{item.excerpt}</p>
                      <p className="mt-1 font-mono text-micro uppercase tracking-[0.08em] text-dim">{item.source} · {item.epistemic_state}</p>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/discoveries" className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                Open research <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </section>
          </div>
        </section>

        {/* ── Operating loop ─────────────────────────────────────────── */}
        <section aria-labelledby="loop-heading" className="mt-20">
          <p className="font-mono text-micro uppercase tracking-[0.14em] text-accent">How Hami works</p>
          <h2 id="loop-heading" className="mt-2 max-w-2xl font-display text-4xl tracking-tight text-ink sm:text-5xl">
            One loop, every step on the record.
          </h2>
          <ol className="step-rail mt-10 grid gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
            {LOOP.map((step) => (
              <li key={step.title} className="bg-card p-5 transition-colors duration-200 hover:bg-surface-elevated">
                <step.icon className="mt-4 size-5 text-accent" aria-hidden="true" />
                <h3 className="mt-3 font-display text-2xl tracking-tight text-ink">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>
      </Container>
    </main>
  );
}

const LOOP = [
  { title: "Observe", body: "Public and authorised signals are recorded with their source.", icon: Radio },
  { title: "Research", body: "Open questions are asked of the evidence, not assumed.", icon: FlaskConical },
  { title: "Qualify", body: "An opportunity stays a hypothesis until evidence supports it.", icon: Lightbulb },
  { title: "Act", body: "Proposed actions wait for owner approval before anything runs.", icon: ShieldCheck },
  { title: "Record", body: "Outcomes are stored as they happened, including no result.", icon: BookOpenCheck },
] as const;
