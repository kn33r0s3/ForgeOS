import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { loadDiscoveries, type PublicDiscovery } from "@/lib/content";

export const Route = createFileRoute("/discoveries")({
  component: DiscoveriesPage,
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
    <main className="py-10 sm:py-14">
      <Container className="max-w-3xl">
        <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Observations</p>
        <h1 className="mt-2 font-display text-4xl tracking-tight text-fg">What the engine has actually collected</h1>
        <p className="mt-3 text-muted">Each item is something a source published. Forge has not verified it, priced it, or turned it into an offer.</p>
        {!ready ? <p className="mt-6 text-muted">Checking collected observations…</p> : null}
        {ready && rows === null ? (
          <div className="mt-6 rounded-2xl border border-line bg-void p-5" role="alert">
            <p className="text-muted">The observations service is unavailable. The records could not be checked, so this is not an empty result.</p>
            <button type="button" onClick={() => setReloadVersion((version) => version + 1)} className="mt-3 min-h-10 rounded-full border border-line px-4 text-sm text-fg">Retry</button>
          </div>
        ) : null}
        {ready && rows?.length === 0 ? (
          <p className="mt-6 rounded-2xl border border-line bg-void p-5 text-muted">No external observations are on record yet. The research cycle collects them. An empty list means none have been stored.</p>
        ) : null}
        <div className="mt-6 space-y-3">
          {rows?.map((row) => (
            <article key={row.id} className="rounded-2xl border border-line bg-void p-5">
              <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">{row.source} · {row.epistemic_state} · {row.freshness || "unknown"}</p>
              <h2 className="mt-1 font-display text-2xl text-fg">{row.title || "Untitled observation"}</h2>
              <p className="mt-2 text-sm text-muted">{row.excerpt}</p>
              {row.canonical_url ? (
                <a href={row.canonical_url} className="mt-3 inline-flex text-sm text-cyan">{row.canonical_url}</a>
              ) : null}
            </article>
          ))}
        </div>
      </Container>
    </main>
  );
}
