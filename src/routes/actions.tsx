import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, RefreshCw } from "lucide-react";
import { Container } from "@/components/layout/container";
import { loadExecutionActions, type ActionRecord } from "@/lib/operations-data";

export const Route = createFileRoute("/actions")({
  component: ActionsPage,
  head: () => ({ meta: [{ title: "Actions — Hami" }] }),
});

function awaitingReview(action: ActionRecord) {
  return (
    action.data_scope === "REAL" &&
    action.requires_owner_approval === true &&
    !action.approved_at &&
    !["blocked", "completed", "abandoned"].includes(action.status.toLowerCase())
  );
}

function ActionsPage() {
  const [actions, setActions] = useState<ActionRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void loadExecutionActions()
      .then((result) => {
        if (!active) return;
        setActions(result);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setActions(null);
        setError(reason instanceof Error ? reason.message : "The action service could not be checked.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadVersion]);

  const realActions = actions?.filter((action) => action.data_scope === "REAL") ?? [];
  const sandboxActions = actions?.filter((action) => action.data_scope === "SANDBOX") ?? [];
  const awaiting = realActions.filter(awaitingReview);

  return (
    <main className="py-8 sm:py-12">
      <Container className="max-w-5xl">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-3xl">
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-primary">Hami / action queue</p>
            <h1 className="mt-3 font-display text-title tracking-tight text-foreground">What is waiting for a decision?</h1>
            <p className="mt-4 text-lede text-muted">
              Proposed actions are not execution. Approval records intent; it does not send outreach, spend money, or complete work.
            </p>
          </div>
          <Link
            to="/operations"
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-4 text-sm font-semibold text-foreground hover:bg-secondary"
          >
            Open operating controls <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </header>

        {loading ? <p role="status" className="mt-8 text-muted">Reading recorded actions…</p> : null}
        {!loading && error ? (
          <div role="alert" className="mt-8 rounded-2xl border border-danger/25 bg-surface p-6">
            <h2 className="font-display text-xl font-semibold text-foreground">Actions are unavailable</h2>
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
        {!loading && actions !== null ? (
          <>
            <section className="mt-7 grid gap-3 sm:grid-cols-3" aria-label="Action summary">
              <SummaryCard label="REAL-scope records" value={realActions.length} />
              <SummaryCard label="Awaiting owner review" value={awaiting.length} />
              <SummaryCard label="SANDBOX records" value={sandboxActions.length} />
            </section>

            {actions.length === 0 ? (
              <div className="mt-5 rounded-2xl border border-border bg-surface p-6">
                <h2 className="font-display text-xl font-semibold text-foreground">No execution-action records returned.</h2>
                <p className="mt-2 text-sm leading-6 text-muted">A quiet queue is shown as empty only after the action endpoint responds successfully.</p>
              </div>
            ) : (
              <div className="mt-5 space-y-7">
                <ActionSection title="REAL scope" items={realActions} />
                <ActionSection title="SANDBOX / test scope" items={sandboxActions} />
                {actions.some((action) => !action.data_scope) ? (
                  <ActionSection title="Scope not recorded" items={actions.filter((action) => !action.data_scope)} />
                ) : null}
              </div>
            )}
          </>
        ) : null}
      </Container>
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums text-foreground">{value.toLocaleString()}</p>
    </div>
  );
}

function ActionSection({ title, items }: { title: string; items: ActionRecord[] }) {
  return (
    <section aria-label={title}>
      <h2 className="font-display text-xl font-semibold text-foreground">{title}</h2>
      {items.length === 0 ? (
        <p className="mt-3 rounded-xl border border-border bg-surface p-4 text-sm text-muted">No records in this scope.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {items.map((item) => (
            <li key={item.id} className="rounded-xl border border-border bg-surface p-5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-secondary px-2.5 py-1 font-semibold text-primary">
                  {item.data_scope ?? "SCOPE UNKNOWN"}
                </span>
                <span className="text-muted">{item.action_type || "Action type not recorded"}</span>
                <span className="rounded-full border border-border px-2.5 py-1 text-foreground">{item.status.replaceAll("_", " ")}</span>
              </div>
              <p className="mt-3 text-sm leading-6 text-foreground">{item.action}</p>
              <p className="mt-3 text-xs text-muted">
                {awaitingReview(item)
                  ? "Owner review required; no external action is inferred."
                  : item.approved_at
                    ? "Approval is recorded; execution status remains separate."
                    : "No pending owner approval is indicated by this record."}
              </p>
              {item.policy_reason ? <p className="mt-2 text-xs text-muted">Policy note: {item.policy_reason}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
