import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowUpRight, Clock3, FileSearch } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
import { loadDiscoveries, type PublicDiscovery } from "@/lib/content";

export const Route = createFileRoute("/discoveries")({
  component: DiscoveriesPage,
  head: () => ({ meta: [{ title: "Research — Hami" }] }),
});

function DiscoveriesPage() {
  const [rows, setRows] = useState<PublicDiscovery[] | null>(null);
  const [ready, setReady] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setReady(false);
    void loadDiscoveries(50)
      .then((body) => {
        if (active) setRows(body);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [reloadVersion]);

  return (
    <main>
      <PageHeader
        eyebrow="Research / sourced observations"
        title="What Hami has actually collected"
        lede="Each item is something a source published. Hami has not necessarily verified it, priced it, or turned it into an offer."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        {!ready ? <SkeletonCards count={3} label="Checking collected observations…" className="space-y-3" /> : null}
        {ready && rows === null ? (
          <UnavailableState
            title="Observations service unavailable"
            body="The observations service is unavailable. The records could not be checked, so this is not an empty result."
            onRetry={() => setReloadVersion((version) => version + 1)}
          />
        ) : null}
        {ready && rows?.length === 0 ? (
          <EmptyState
            icon={FileSearch}
            title="No observations on record yet"
            body="No external observations are on record yet. The research cycle collects them. An empty list means none have been stored."
          />
        ) : null}
        {ready && rows && rows.length > 0 ? (
          <p className="mb-3 font-mono text-micro uppercase tracking-[0.12em] text-dim">
            {rows.length} sourced observation{rows.length === 1 ? "" : "s"}
          </p>
        ) : null}
        <ol className="grid gap-3 md:grid-cols-2">
          {rows?.map((row, index) => {
            const stale = row.freshness === "stale";
            return (
              <li key={row.id} className="card card-interactive reveal flex flex-col p-5" style={{ "--i": Math.min(index, 8) } as React.CSSProperties}>
                <article className="flex flex-1 flex-col">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="status-pill status-pill-accent">{row.source}</span>
                    <span className="status-pill status-pill-neutral">{row.epistemic_state}</span>
                    <span className={`status-pill ${stale ? "status-pill-warning" : "status-pill-success"}`}>
                      <Clock3 className="size-3" aria-hidden="true" /> {row.freshness || "unknown"}
                    </span>
                  </div>
                  <h2 className="mt-3 font-display text-2xl leading-tight tracking-tight text-ink">{row.title || "Untitled observation"}</h2>
                  <p className="mt-2 flex-1 text-sm leading-6 text-muted">{row.excerpt}</p>
                  {row.canonical_url ? (
                    <a href={row.canonical_url} className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 truncate border-t border-line pt-3 text-sm text-accent">
                      <span className="truncate">{row.canonical_url}</span> <ArrowUpRight className="size-4 shrink-0" aria-hidden="true" />
                    </a>
                  ) : null}
                </article>
              </li>
            );
          })}
        </ol>
      </Container>
    </main>
  );
}
