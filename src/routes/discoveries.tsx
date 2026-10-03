import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowUpRight, Clock3, FileSearch } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
import {
  loadDiscoveries,
  type PublicDiscovery,
} from "@/lib/content";

export const Route = createFileRoute("/discoveries")({
  component: DiscoveriesPage,
  head: () => ({ meta: [{ title: "Discoveries — Hami" }] }),
});

function DiscoveriesPage() {
  const [rows, setRows] = useState<PublicDiscovery[] | null>(null);
  const [ready, setReady] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setReady(false);
    void Promise.allSettled([loadDiscoveries(50, { fresh: reloadVersion > 0 })]).then(([publicResult]) => {
      if (!active) return;
      setRows(publicResult.status === "fulfilled" ? publicResult.value : null);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, [reloadVersion]);

  const retry = () => setReloadVersion((version) => version + 1);

  return (
    <main>
      <PageHeader
        eyebrow="Hami / observation and discovery"
        title="What Hami has actually noticed"
        lede="Persisted substrate findings and public source observations stay separate. A possibility or published item is not automatically verified."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <section aria-labelledby="substrate-discoveries-title">
          <div className="mb-4 border-b border-line pb-3">
            <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
              Canonical substrate · read only
            </p>
            <h2 id="substrate-discoveries-title" className="mt-1 font-display text-2xl tracking-tight text-ink">
              Persisted discoveries
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Persisted substrate findings require internal authorization and are not requested in this public browser view. Opening this page does not run discovery.
            </p>
          </div>
          <UnavailableState
            title="Substrate discoveries are not available in this public view"
            body="The public page does not request owner-authorized substrate records. This is an access boundary, not an empty discovery result."
          />
        </section>

        <section className="mt-12" aria-labelledby="source-observations-title">
          <div className="mb-4 border-b border-line pb-3">
            <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
              Public source projection
            </p>
            <h2 id="source-observations-title" className="mt-1 font-display text-2xl tracking-tight text-ink">
              What sources have published
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              A sourced observation is not, by itself, a verified claim or a completed investigation.
            </p>
          </div>
          {!ready ? (
            <SkeletonCards count={3} label="Checking collected observations…" className="space-y-3" />
          ) : null}
          {ready && rows === null ? (
            <UnavailableState
              title="Observations service unavailable"
              body="The observations service is unavailable. The records could not be checked, so this is not an empty result."
              onRetry={retry}
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
            <p className="mb-3 text-micro font-extrabold uppercase tracking-[0.12em] text-dim">
              {rows.length} sourced observation{rows.length === 1 ? "" : "s"}
            </p>
          ) : null}
          <ol className="grid gap-3 md:grid-cols-2">
            {rows?.map((row, index) => {
              const stale = row.freshness === "stale";
              return (
                <li
                  key={row.id}
                  className="card card-interactive reveal flex min-w-0 flex-col p-5"
                  style={{ "--i": Math.min(index, 8) } as React.CSSProperties}
                >
                  <article className="flex flex-1 flex-col">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="status-pill status-pill-accent max-w-full break-all">{row.source}</span>
                      <span className="status-pill status-pill-neutral max-w-full break-all">{row.epistemic_state}</span>
                      <span className={`status-pill ${stale ? "status-pill-warning" : "status-pill-success"}`}>
                        <Clock3 className="size-3" aria-hidden="true" /> {row.freshness || "unknown"}
                      </span>
                    </div>
                    <h3 className="mt-3 break-words font-display text-2xl leading-tight tracking-tight text-ink">
                      {row.title || "Untitled observation"}
                    </h3>
                    <p className="mt-2 min-w-0 flex-1 break-words text-sm leading-6 text-muted">{row.excerpt}</p>
                    {row.canonical_url ? (
                      <a
                        href={row.canonical_url}
                        className="link-arrow mt-4 inline-flex min-h-10 min-w-0 max-w-full items-center gap-1 border-t border-line pt-3 text-sm text-accent"
                      >
                        <span className="min-w-0 break-all">{row.canonical_url}</span>
                        <ArrowUpRight className="size-4 shrink-0" aria-hidden="true" />
                      </a>
                    ) : null}
                  </article>
                </li>
              );
            })}
          </ol>
        </section>
      </Container>
    </main>
  );
}
