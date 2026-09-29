import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw } from "lucide-react";
import { Container } from "@/components/layout/container";
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
    <main className="py-8 sm:py-12">
      <Container className="max-w-5xl">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-3xl">
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-primary">Hami / action state</p>
            <h1 className="mt-3 font-display text-title tracking-tight text-foreground">What is waiting for a decision?</h1>
            <p className="mt-4 text-lede text-muted">
              This aggregate comes from the current runtime snapshot. A pending record is not execution, authorization, or a completed outcome.
            </p>
          </div>
        </header>

        {loading ? <p role="status" className="mt-8 text-muted">Reading recorded actions…</p> : null}
        {!loading && error ? (
          <div role="alert" className="mt-8 rounded-2xl border border-danger/25 bg-surface p-6">
            <h2 className="font-display text-xl font-semibold text-foreground">Action state is unavailable</h2>
            <p className="mt-2 text-sm text-muted">{error}</p>
            <button
              type="button"
              onClick={() => setReloadVersion((version) => version + 1)}
              className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-4 text-sm font-semibold text-foreground hover:bg-secondary"
            >
              <RefreshCw className="size-4" aria-hidden="true" /> Retry
            </button>
          </div>
        ) : null}
        {!loading && runtime !== null ? (
          <>
            <section className="mt-7 grid gap-3 sm:grid-cols-3" aria-label="Runtime action summary">
              <SummaryCard label="Pending action records" value={pending} />
              <SummaryCard label="Queued worker tasks" value={runtime.worker.queued_tasks} />
              <SummaryCard label="Running cycles" value={runtime.cycles.running_count} />
            </section>
            <div className="mt-5 rounded-2xl border border-border bg-surface p-6 sm:p-8">
              <p className="font-mono text-micro uppercase tracking-[0.14em] text-primary">Interpretation</p>
              {pending === 0 ? (
                <h2 className="mt-3 font-display text-xl font-semibold text-foreground">
                  No action records currently have a pending-review status.
                </h2>
              ) : pending !== null ? (
                <h2 className="mt-3 font-display text-xl font-semibold text-foreground">
                  {pending.toLocaleString()} action record{pending === 1 ? "" : "s"} have a pending-review status.
                </h2>
              ) : (
                <h2 className="mt-3 font-display text-xl font-semibold text-foreground">
                  The runtime snapshot did not include a pending action count.
                </h2>
              )}
              <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
                The runtime aggregate does not expose each action’s data scope or authorization details. No individual action is presented as REAL, approved, or executed from this count.
              </p>
              <p className="mt-3 text-sm font-medium text-foreground">
                Current continuation state: {runtime.active_stage}
              </p>
              {runtime.cycles.last_completed?.ended_at ? (
                <p className="mt-2 text-xs text-muted">
                  Last completed cycle recorded at {new Date(runtime.cycles.last_completed.ended_at).toLocaleString()}.
                </p>
              ) : null}
            </div>
          </>
        ) : null}
      </Container>
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums text-foreground">
        {value === null ? "Unavailable" : value.toLocaleString()}
      </p>
    </div>
  );
}
