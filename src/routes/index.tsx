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
    // First paint reuses a recent read; a "Refresh" press must always re-query.
    const fresh = reloadVersion > 0;
    setLoading(true);
    void Promise.allSettled([
      loadEngineHealth({ fresh }),
      loadRuntimeSnapshot({ fresh }),
      loadPublicFeed(40, undefined, undefined, { fresh }),
      loadDiscoveries(3, { fresh }),
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
      {/* ── Hero: pinstripe-framed masthead, then slab statement + live status ── */}
      <section className="relative isolate overflow-hidden">
        <div className="hero-glow -z-10" aria-hidden="true" />
        <div className="hero-grain -z-10" aria-hidden="true" />
        <Container className="py-8 sm:py-12">
          <div className="pinstripe reveal overflow-hidden">
            <img
              src="/hami-home.jpg"
              alt=""
              width={1376}
              height={768}
              fetchPriority="high"
              decoding="async"
              className="absolute inset-0 size-full object-cover object-[52%_45%] opacity-40"
            />
            <div aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(45deg,#000_20%,rgb(0_0_0/0.55)_60%,rgb(0_0_0/0.2))]" />
            <div className="relative z-[2] flex flex-col items-center px-4 py-12 text-center sm:px-10 sm:py-20">
              <p className="tag">Hami · Nepal-first intelligence</p>
              <h1 className="mt-6 font-gothic text-[clamp(2.6rem,7.4vw,6rem)] leading-[1.04] text-ink [text-shadow:3px_3px_0_#000]">
                Discover what matters.
                <br />
                Understand it.{" "}
                <span className="plate mt-2 inline-block whitespace-nowrap">Act on it.</span>
              </h1>
              <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                <Link
                  to="/feed"
                  className="btn-wipe inline-flex h-12 items-center gap-2 rounded-card border-2 border-black/70 bg-accent px-6 text-base font-extrabold text-black shadow-sm hover:text-accent"
                >
                  Explore the network <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
                <Link
                  to="/discoveries"
                  className="btn-wipe inline-flex h-12 items-center gap-2 rounded-card border-2 border-black/70 bg-[#f5f1f1] px-5 text-base font-extrabold text-black shadow-sm hover:text-white"
                >
                  Review research
                </Link>
                <Link
                  to="/operations"
                  className="link-arrow inline-flex h-12 items-center gap-1.5 px-2 text-sm font-bold text-wheat hover:text-white"
                >
                  Operating dashboard <ArrowUpRight className="size-4" aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>

          <div className="mt-10 grid items-center gap-8 lg:grid-cols-[auto_minmax(0,1fr)_minmax(0,22rem)] lg:gap-10">
            <div className="reveal mx-auto size-40 overflow-hidden rounded-full border-[3px] border-accent bg-black sm:size-48" style={{ "--i": 1 } as React.CSSProperties}>
              <img src="/hami-home.jpg" alt="" width={1376} height={768} loading="lazy" decoding="async" className="size-full object-cover object-[52%_45%]" />
            </div>
            <div className="reveal" style={{ "--i": 2 } as React.CSSProperties}>
              <p className="slab px-5 py-4 text-center text-base italic leading-7 sm:text-lg">
                “Hami connects observations, research, options, decisions, and outcomes.
                Evidence stays visible; a hypothesis never becomes a customer or a result
                just because it is recorded.”
              </p>
              <ul className="mt-5 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm font-bold text-wheat" aria-label="Operating principles">
                <li className="flex items-center gap-2"><Eye className="size-4 text-accent" aria-hidden="true" />Evidence stays visible</li>
                <li className="flex items-center gap-2"><Scale className="size-4 text-accent" aria-hidden="true" />Hypotheses stay labelled</li>
                <li className="flex items-center gap-2"><ShieldCheck className="size-4 text-accent" aria-hidden="true" />Owner approves actions</li>
              </ul>
            </div>

            <section
              aria-labelledby="continuation-heading"
              className="glass reveal border-t-4 border-t-accent p-5"
              style={{ "--i": 3 } as React.CSSProperties}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 text-sm font-bold text-ink" role="status">
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
              <h2 id="continuation-heading" className="mt-3 text-xl font-extrabold text-accent">
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
              <dl className="mt-4 grid grid-cols-2 gap-4 border-t-2 border-line pt-4 text-sm">
                <div>
                  <dt className="text-micro font-extrabold uppercase tracking-[0.1em] text-wheat">Queued tasks</dt>
                  <dd className="mt-1 font-bold tabular-nums text-ink">
                    {loading ? <Skeleton className="h-4 w-8" /> : runtime ? runtime.worker.queued_tasks.toLocaleString() : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt className="text-micro font-extrabold uppercase tracking-[0.1em] text-wheat">Last cycle</dt>
                  <dd className="mt-1 font-bold text-ink">
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
        <div className="band-rule" aria-hidden="true" />
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
              <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">System state</p>
              <h2 id="overview-heading" className="mt-2 text-3xl font-black tracking-tight text-ink sm:text-4xl">
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
                <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">Evidence trail</p>
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
                <p className="text-micro font-extrabold uppercase tracking-[0.12em]">Opportunity status</p>
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
                <p className="text-micro font-extrabold uppercase tracking-[0.12em]">Research activity</p>
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
                      <p className="mt-1 text-micro font-extrabold uppercase tracking-[0.08em] text-dim">{item.source} · {item.epistemic_state}</p>
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
          <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">How Hami works</p>
          <h2 id="loop-heading" className="mt-2 max-w-2xl text-3xl font-black tracking-tight text-ink sm:text-4xl">
            One loop, every step on the record.
          </h2>
          <ol className="step-rail mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {LOOP.map((step) => (
              <li key={step.title} className="card card-interactive p-5">
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
