import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { Container } from "@/components/layout/container";
import { loadPublicFeed, type PublicFeedItem } from "@/lib/content";
import { loadRuntimeSnapshot } from "@/lib/operations-data";

export const Route = createFileRoute("/opportunities")({
  component: OpportunitiesPage,
  head: () => ({ meta: [{ title: "Opportunities — Hami" }] }),
});

function OpportunitiesPage() {
  const [items, setItems] = useState<PublicFeedItem[] | null>(null);
  const [validatedCount, setValidatedCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.allSettled([loadPublicFeed(100), loadRuntimeSnapshot()]).then(([feedResult, runtimeResult]) => {
      if (!active) return;
      setItems(feedResult.status === "fulfilled" ? feedResult.value : null);
      setValidatedCount(
        runtimeResult.status === "fulfilled"
          ? runtimeResult.value.truth?.epistemic_labels.human_validated_problems ?? null
          : null,
      );
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [reloadVersion]);

  const opportunities = items?.filter((item) => item.kind === "opportunity") ?? [];

  return (
    <main className="py-8 sm:py-12">
      <Container className="max-w-5xl">
        <header className="max-w-3xl">
          <p className="font-mono text-micro uppercase tracking-[0.14em] text-primary">Hami / opportunity hypotheses</p>
          <h1 className="mt-3 font-display text-title tracking-tight text-foreground">What might be worth pursuing?</h1>
          <p className="mt-4 text-lede text-muted">
            This view shows only opportunity records cleared for the public projection.
            A score or hypothesis is not buyer demand, an offer, or a verified opportunity.
          </p>
          {validatedCount === 0 ? (
            <p className="mt-4 inline-flex rounded-full bg-secondary px-3 py-2 text-sm font-medium text-foreground">
              No opportunities are marked human-validated in the current system snapshot.
            </p>
          ) : validatedCount != null ? (
            <p className="mt-4 inline-flex rounded-full bg-secondary px-3 py-2 text-sm font-medium text-foreground">
              Human-validated opportunity records: {validatedCount.toLocaleString()}.
            </p>
          ) : null}
        </header>

        {loading ? <p className="mt-8 text-muted" role="status">Checking public opportunity records…</p> : null}
        {!loading && items === null ? (
          <div className="mt-8 rounded-2xl border border-danger/25 bg-surface p-6" role="alert">
            <h2 className="font-display text-xl font-semibold text-foreground">Opportunity records are unavailable</h2>
            <p className="mt-2 text-sm leading-6 text-muted">The feed could not be checked, so this is not an empty result.</p>
            <button
              type="button"
              onClick={() => setReloadVersion((version) => version + 1)}
              className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-4 text-sm font-semibold text-foreground hover:bg-secondary"
            >
              <RefreshCw className="size-4" aria-hidden="true" /> Retry
            </button>
          </div>
        ) : null}
        {!loading && items !== null && opportunities.length === 0 ? (
          <div className="mt-8 rounded-2xl border border-border bg-surface p-6 sm:p-8">
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-muted">Sparse by design</p>
            <h2 className="mt-3 font-display text-2xl font-semibold text-foreground">No opportunity hypotheses are publicly surfaced.</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
              No opportunity hypotheses are currently surfaced in the public feed. Hami leaves the space honest rather than manufacturing entries.
            </p>
          </div>
        ) : null}
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {opportunities.map((item) => (
            <article key={item.id} className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-secondary px-2.5 py-1 font-semibold text-primary">HYPOTHESIS</span>
                <span className="text-muted">{item.epistemic_state.replaceAll("_", " ")}</span>
                {item.source ? <span className="text-muted">· {item.source}</span> : null}
              </div>
              <h2 className="mt-4 font-display text-xl font-semibold text-foreground">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted">{item.summary}</p>
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-xs text-muted">
                <span>{item.relations.length} recorded link{item.relations.length === 1 ? "" : "s"}</span>
                {item.source_url?.startsWith("https://") ? (
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-10 items-center gap-1 font-semibold text-primary hover:underline"
                  >
                    View source <ArrowUpRight className="size-3.5" aria-hidden="true" />
                  </a>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </Container>
    </main>
  );
}
