import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, CircleAlert, CircleCheck, Compass, Network, RefreshCw } from "lucide-react";
import { Container } from "@/components/layout/container";
import {
  loadDiscoveries,
  loadEngineHealth,
  loadPublicFeed,
  type EngineHealth,
  type PublicDiscovery,
  type PublicFeedItem,
} from "@/lib/content";
import {
  loadExecutionActions,
  loadRuntimeSnapshot,
  type ActionRecord,
  type RuntimeSnapshot,
} from "@/lib/operations-data";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({ meta: [{ title: "Hami — Discover what matters" }] }),
});

function needsOwnerReview(action: ActionRecord) {
  return (
    action.data_scope === "REAL" &&
    action.requires_owner_approval === true &&
    !action.approved_at &&
    !["blocked", "completed", "abandoned"].includes(action.status.toLowerCase())
  );
}

function HomePage() {
  const [health, setHealth] = useState<EngineHealth | null>(null);
  const [runtime, setRuntime] = useState<RuntimeSnapshot | null>(null);
  const [actions, setActions] = useState<ActionRecord[] | null>(null);
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
      loadExecutionActions(),
      loadPublicFeed(40),
      loadDiscoveries(3),
    ]).then(([healthResult, runtimeResult, actionsResult, feedResult, discoveryResult]) => {
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
      if (actionsResult.status === "fulfilled") setActions(actionsResult.value);
      else {
        setActions(null);
        failed.push("actions");
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
  const awaitingReview = actions?.filter(needsOwnerReview).length ?? null;
  const labels = runtime?.truth?.epistemic_labels;
  const actualOutcomes = labels?.actual_outcomes;
  const validatedOpportunities = labels?.human_validated_problems;
  const lastCycle = runtime?.cycles.last_completed;
  const systemReachable = health?.reachable === true;

  return (
    <main className="py-8 sm:py-12">
      <Container className="max-w-6xl">
        <section className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
          <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm sm:p-9">
            <p className="font-mono text-micro font-medium uppercase tracking-[0.16em] text-primary">
              Hami / current state
            </p>
            <h1 className="mt-5 max-w-3xl font-display text-title tracking-tight text-foreground">
              Discover what matters.
              <br />
              Understand it. Act on it.
            </h1>
            <p className="mt-5 max-w-2xl text-lede text-muted">
              Hami connects observations, research, options, decisions, and outcomes.
              Evidence stays visible; a hypothesis never becomes a customer or a result
              just because it is recorded.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                to="/feed"
                className="inline-flex min-h-11 items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Explore the network <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                to="/discoveries"
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-semibold text-foreground transition-colors hover:bg-secondary"
              >
                Review research
              </Link>
            </div>
          </div>

          <section
            aria-labelledby="continuation-heading"
            className="flex flex-col justify-between rounded-2xl border border-border bg-surface-elevated p-6 sm:p-7"
          >
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                {systemReachable ? (
                  <CircleCheck className="size-4 text-success" aria-hidden="true" />
                ) : health ? (
                  <CircleAlert className="size-4 text-warning" aria-hidden="true" />
                ) : (
                  <span className="size-2 rounded-full bg-muted" aria-hidden="true" />
                )}
                {loading ? "Checking system" : systemReachable ? "System connected" : "System state unavailable"}
              </div>
              <h2 id="continuation-heading" className="mt-6 font-display text-xl font-semibold text-foreground">
                What happens next
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                {runtime
                  ? runtime.active_stage
                  : "The continuation state has not loaded. No activity is assumed."}
              </p>
            </div>
            <dl className="mt-7 grid grid-cols-2 gap-4 border-t border-border pt-5 text-sm">
              <div>
                <dt className="text-muted">Queued worker tasks</dt>
                <dd className="mt-1 font-semibold tabular-nums text-foreground">
                  {runtime ? runtime.worker.queued_tasks.toLocaleString() : "Unavailable"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Last completed cycle</dt>
                <dd className="mt-1 font-semibold text-foreground">
                  {lastCycle?.ended_at
                    ? new Date(lastCycle.ended_at).toLocaleString()
                    : lastCycle
                      ? "Recorded, time unknown"
                      : runtime
                        ? "None recorded"
                        : "Unavailable"}
                </dd>
              </div>
            </dl>
          </section>
        </section>

        {unavailable.length > 0 ? (
          <div role="status" className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-foreground">
            <span>Some live panels could not be checked: {unavailable.join(", ")}. Unavailable data is not shown as zero.</span>
            <button
              type="button"
              onClick={() => setReloadVersion((version) => version + 1)}
              className="inline-flex min-h-10 items-center gap-2 rounded-md px-3 font-semibold text-primary hover:bg-secondary"
            >
              <RefreshCw className="size-4" aria-hidden="true" /> Refresh
            </button>
          </div>
        ) : null}

        <section aria-label="System overview" className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <OverviewMetric label="Public signals" value={feed === null ? null : signals.length} note="Visible observation records" />
          <OverviewMetric label="Research tasks" value={runtime?.research_tasks ?? null} note="All recorded task states" />
          <OverviewMetric label="Opportunities" value={feed === null ? null : opportunities.length} note="Public hypotheses, not commitments" />
          <OverviewMetric label="Actions" value={awaitingReview} note="REAL-scope items awaiting review" />
          <OverviewMetric label="Outcomes" value={actualOutcomes ?? null} note="REAL-scope outcome records" />
        </section>

        <section className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(17rem,0.65fr)]">
          <div className="rounded-2xl border border-border bg-surface p-5 sm:p-7">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-mono text-micro uppercase tracking-[0.14em] text-primary">Evidence trail</p>
                <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Recent public records</h2>
              </div>
              <Link to="/feed" className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-primary hover:underline">
                Open network <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
            {feed === null ? (
              <p className="mt-5 rounded-xl border border-border bg-background p-4 text-sm text-muted">
                Public records are unavailable right now; no empty result is inferred.
              </p>
            ) : feed.length === 0 ? (
              <p className="mt-5 rounded-xl border border-border bg-background p-4 text-sm text-muted">
                No public records are available to show yet.
              </p>
            ) : (
              <div className="mt-4 divide-y divide-border">
                {feed.slice(0, 4).map((item) => (
                  <article key={item.id} className="py-4 first:pt-2 last:pb-1">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-full bg-secondary px-2.5 py-1 font-medium text-primary">
                        {item.kind.replaceAll("_", " ")}
                      </span>
                      <span className="text-muted">{item.epistemic_state.replaceAll("_", " ")}</span>
                      {item.source ? <span className="text-muted">· {item.source}</span> : null}
                    </div>
                    <h3 className="mt-2 font-semibold text-foreground">{item.title}</h3>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted">{item.summary}</p>
                    {item.relations.length > 0 ? (
                      <p className="mt-2 text-xs text-muted">
                        {item.relations.length} recorded connection{item.relations.length === 1 ? "" : "s"}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
            {evidenceLinks !== null ? (
              <p className="mt-4 border-t border-border pt-4 text-xs text-muted">
                {evidenceLinks.toLocaleString()} visible evidence-related links in this projection.
              </p>
            ) : null}
          </div>

          <div className="space-y-5">
            <section className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
              <div className="flex items-center gap-2 text-primary">
                <Compass className="size-4" aria-hidden="true" />
                <p className="font-mono text-micro uppercase tracking-[0.14em]">Opportunity status</p>
              </div>
              {feed === null ? (
                <p className="mt-4 text-sm text-muted">Opportunity records are unavailable.</p>
              ) : opportunities.length === 0 ? (
                <p className="mt-4 text-sm leading-6 text-muted">
                  No public opportunity hypotheses are surfaced yet. Hami does not invent opportunities to fill this space.
                </p>
              ) : (
                <p className="mt-4 text-sm leading-6 text-muted">
                  {opportunities.length} public hypothesis record{opportunities.length === 1 ? "" : "s"} surfaced. They remain hypotheses until evidence and human validation support them.
                </p>
              )}
              {validatedOpportunities === 0 ? (
                <p className="mt-3 rounded-lg bg-secondary px-3 py-2 text-sm font-medium text-foreground">
                  No verified opportunities yet.
                </p>
              ) : validatedOpportunities != null ? (
                <p className="mt-3 text-sm text-muted">
                  Human-validated opportunity records: {validatedOpportunities.toLocaleString()}.
                </p>
              ) : null}
              <Link to="/opportunities" className="mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-primary hover:underline">
                Review opportunities <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </section>

            <section className="rounded-2xl border border-border bg-secondary p-5 sm:p-6">
              <div className="flex items-center gap-2 text-primary">
                <Network className="size-4" aria-hidden="true" />
                <p className="font-mono text-micro uppercase tracking-[0.14em]">Research activity</p>
              </div>
              {discoveries === null ? (
                <p className="mt-3 text-sm text-muted">Research observations are unavailable.</p>
              ) : discoveries.length === 0 ? (
                <p className="mt-3 text-sm leading-6 text-muted">No external source observations are currently available to show.</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {discoveries.slice(0, 2).map((item) => (
                    <li key={item.id} className="border-l-2 border-primary/40 pl-3">
                      <p className="text-sm font-semibold text-foreground">{item.title || "Untitled observation"}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{item.excerpt}</p>
                      <p className="mt-1 text-xs text-muted">{item.source} · {item.epistemic_state}</p>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/discoveries" className="mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-primary hover:underline">
                Open research <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </section>
          </div>
        </section>
      </Container>
    </main>
  );
}

function OverviewMetric({ label, value, note }: { label: string; value: number | null; note: string }) {
  return (
    <article className="rounded-xl border border-border bg-surface p-4 shadow-sm">
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className="mt-3 font-display text-3xl font-semibold tabular-nums text-foreground">
        {value === null ? "—" : value.toLocaleString()}
      </p>
      <p className="mt-2 text-xs leading-5 text-muted">{note}</p>
    </article>
  );
}
