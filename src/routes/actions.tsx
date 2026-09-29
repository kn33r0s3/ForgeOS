import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, Cog, Hourglass, ListChecks } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { MetricTile, UnavailableState } from "@/components/ui/feedback";
import { loadRuntimeSnapshot, type RuntimeSnapshot } from "@/lib/operations-data";

export const Route = createFileRoute("/actions")({
  component: ActionsPage,
  head: () => ({ meta: [{ title: "Actions — Hami" }] }),
});

function ActionsPage() {
  const [runtime, setRuntime] = useState<RuntimeSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void loadRuntimeSnapshot()
      .then((result) => {
        if (!active) return;
        setRuntime(result);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setRuntime(null);
        setError(reason instanceof Error ? reason.message : "The runtime action summary could not be checked.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadVersion]);

  const pending = runtime?.truth?.operations.pending_actions ?? null;

  return (
    <main>
      <PageHeader
        eyebrow="Hami / action state"
        title="What is waiting for a decision?"
        lede="This aggregate comes from the current runtime snapshot. A pending record is not execution, authorization, or a completed outcome."
        containerClassName="max-w-5xl"
      >
        <Link
          to="/operations"
          className="link-arrow mt-7 inline-flex min-h-11 items-center gap-1.5 rounded-card border border-line bg-card/60 px-4 text-sm font-semibold text-ink transition-colors hover:border-accent/60"
        >
          Open the approval queue <ArrowUpRight className="size-4" aria-hidden="true" />
        </Link>
      </PageHeader>
      <Container className="max-w-5xl py-10 sm:py-14">
        {!loading && error ? (
          <UnavailableState
            title="Action state is unavailable"
            body={error}
            onRetry={() => setReloadVersion((version) => version + 1)}
          />
        ) : null}
        {loading || runtime !== null ? (
          <section className="grid gap-3 sm:grid-cols-3" aria-label="Runtime action summary" aria-busy={loading}>
            {loading ? <span role="status" className="sr-only">Reading recorded actions…</span> : null}
            <MetricTile index={0} icon={ListChecks} tone="accent" loading={loading} label="Pending action records" value={pending} />
            <MetricTile index={1} icon={Hourglass} loading={loading} label="Queued worker tasks" value={runtime?.worker.queued_tasks ?? null} />
            <MetricTile index={2} icon={Cog} loading={loading} label="Running cycles" value={runtime?.cycles.running_count ?? null} />
          </section>
        ) : null}
        {!loading && runtime !== null ? (
          <div className="card fade-in mt-5 p-6 sm:p-8">
            <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">Interpretation</p>
            {pending === 0 ? (
              <h2 className="mt-3 font-display text-3xl leading-tight tracking-tight text-ink">
                No action records currently have a pending-review status.
              </h2>
            ) : pending !== null ? (
              <h2 className="mt-3 font-display text-3xl leading-tight tracking-tight text-ink">
                {pending.toLocaleString()} action record{pending === 1 ? "" : "s"} have a pending-review status.
              </h2>
            ) : (
              <h2 className="mt-3 font-display text-3xl leading-tight tracking-tight text-ink">
                The runtime snapshot did not include a pending action count.
              </h2>
            )}
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              The runtime aggregate does not expose each action’s data scope or authorization details. No individual action is presented as REAL, approved, or executed from this count.
            </p>
            <dl className="mt-6 grid gap-4 border-t border-line pt-5 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Current continuation state</dt>
                <dd className="mt-1 font-medium text-ink">{runtime.active_stage}</dd>
              </div>
              {runtime.cycles.last_completed?.ended_at ? (
                <div>
                  <dt className="text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Last completed cycle</dt>
                  <dd className="mt-1 text-muted">Recorded at {new Date(runtime.cycles.last_completed.ended_at).toLocaleString()}.</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
      </Container>
    </main>
  );
}
