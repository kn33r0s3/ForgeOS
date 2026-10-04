import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowUpRight, Lightbulb, Link2, ShieldAlert } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
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
    const fresh = reloadVersion > 0;
    void Promise.allSettled([
      loadPublicFeed(100, undefined, undefined, { fresh }),
      loadRuntimeSnapshot({ fresh }),
    ]).then(([feedResult, runtimeResult]) => {
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
    <main>
      <PageHeader
        eyebrow="Hami / opportunity hypotheses"
        title="What might be worth pursuing?"
        lede="This view shows only opportunity records cleared for the public projection. A score or hypothesis is not buyer demand, an offer, or a verified opportunity."
        aside={
          <>
            <p className="flex items-center gap-2 text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
              <ShieldAlert className="size-3.5" aria-hidden="true" /> Validation state
            </p>
            {loading ? (
              <p className="mt-2 text-sm text-muted">Checking the system snapshot…</p>
            ) : validatedCount === 0 ? (
              <p className="mt-2 text-sm leading-6 text-ink">
                No opportunities are marked human-validated in the current system snapshot.
              </p>
            ) : validatedCount != null ? (
              <p className="mt-2 text-sm leading-6 text-ink">
                Human-validated opportunity records: {validatedCount.toLocaleString()}.
              </p>
            ) : (
              <p className="mt-2 text-sm text-muted">The validation count could not be checked.</p>
            )}
          </>
        }
      />
      <Container className="max-w-5xl py-10 sm:py-14">
        {loading ? <SkeletonCards count={4} label="Checking public opportunity records…" className="grid gap-3 md:grid-cols-2" /> : null}
        {!loading && items === null ? (
          <UnavailableState
            title="Opportunity records are unavailable"
            body="The feed could not be checked, so this is not an empty result."
            onRetry={() => setReloadVersion((version) => version + 1)}
          />
        ) : null}
        {!loading && items !== null && opportunities.length === 0 ? (
          <EmptyState
            icon={Lightbulb}
            title="No opportunity hypotheses are publicly surfaced."
            body={
              <>
                <span className="mb-2 block text-micro font-extrabold uppercase tracking-[0.12em] text-dim">Sparse by design</span>
                No opportunity hypotheses are currently surfaced in the public feed. Hami leaves the space honest rather than manufacturing entries.
              </>
            }
          />
        ) : null}
        {!loading && items !== null && opportunities.length > 0 ? (
          <ol className="grid gap-3 md:grid-cols-2">
            {opportunities.map((item, index) => (
            <li key={item.id} className="card card-interactive reveal flex flex-col p-5 sm:p-6" style={{ "--i": Math.min(index, 8) } as React.CSSProperties}>
              <article className="flex flex-1 flex-col">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="status-pill status-pill-warning">
                    <Lightbulb className="size-3" aria-hidden="true" /> Hypothesis
                  </span>
                  <span className="text-muted">{item.epistemic_state.replaceAll("_", " ")}</span>
                  {item.source ? <span className="text-dim">· {item.source}</span> : null}
                </div>
                <h2 className="mt-4 font-display text-2xl leading-tight tracking-tight text-ink">{item.title}</h2>
                <p className="mt-2 flex-1 text-sm leading-6 text-muted">{item.summary}</p>
                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-xs text-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <Link2 className="size-3.5 text-accent" aria-hidden="true" />
                    {item.relations.length} recorded link{item.relations.length === 1 ? "" : "s"}
                  </span>
                  {item.source_url?.startsWith("https://") ? (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="link-arrow inline-flex min-h-10 items-center gap-1 font-semibold text-accent"
                    >
                      View source <ArrowUpRight className="size-3.5" aria-hidden="true" />
                    </a>
                  ) : null}
                </div>
              </article>
            </li>
          ))}
          </ol>
        ) : null}
      </Container>
    </main>
  );
}
