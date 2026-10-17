import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FileSearch } from "lucide-react";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
import { FindingCard } from "@/components/findings/finding-card";
import {
  loadDiscoveries,
  type PublicDiscovery,
} from "@/lib/content";

export const Route = createFileRoute("/discoveries")({
  component: DiscoveriesPage,
  head: () => ({ meta: [{ title: "Findings — Hami" }] }),
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
        eyebrow="Hami · learning in public"
        title="What we have learned so far"
        lede="Here you can see observations Hami has collected from public sources. A source gives us something to investigate; it does not automatically make a claim true. We keep uncertainty visible rather than presenting guesses as facts."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <section aria-labelledby="source-observations-title">
          <div className="mb-5 border-b border-line pb-4">
            <h2 id="source-observations-title" className="font-display text-2xl tracking-tight text-ink">
              Public observations
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Each item is a lead to understand, not a promise or a final conclusion. Hami does not expose private working records on this page.
            </p>
          </div>
          {!ready ? (
            <SkeletonCards count={3} label="Checking collected observations…" className="space-y-3" />
          ) : null}
          {ready && rows === null ? (
            <UnavailableState
              title="We could not load observations"
              body="The public observations could not be checked just now, so we cannot say whether there are any. Try again in a moment."
              onRetry={retry}
            />
          ) : null}
          {ready && rows?.length === 0 ? (
            <EmptyState
              icon={FileSearch}
              title="Nothing public to show yet"
              body="Hami has no public observations to display right now. We would rather show an honest empty state than fill this page with invented examples."
            />
          ) : null}
          {ready && rows && rows.length > 0 ? (
            <p className="mb-3 text-micro font-extrabold uppercase tracking-[0.12em] text-dim">
              {rows.length} sourced observation{rows.length === 1 ? "" : "s"}
            </p>
          ) : null}
          <ol className="grid gap-3 md:grid-cols-2">
            {rows?.map((row, index) => (
              <FindingCard key={row.id} finding={row} index={index} />
            ))}
          </ol>
        </section>
      </Container>
      <HamiPathways current="findings" />
    </main>
  );
}
