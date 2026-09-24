import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { CtaBand } from "@/components/layout/cta-band";
import { Container } from "@/components/layout/container";
import {
  loadDiscoveries,
  loadEngineHealth,
  loadPublicAlerts,
  loadPublicDomain,
  loadProviders,
  type EngineHealth,
  type ProviderRecord,
  type PublicAlert,
  type PublicDiscovery,
  type PublicDomainRecord,
} from "@/lib/content";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [discoveries, setDiscoveries] = useState<PublicDiscovery[]>([]);
  const [work, setWork] = useState<PublicDomainRecord[]>([]);
  const [alerts, setAlerts] = useState<PublicAlert[]>([]);
  const [health, setHealth] = useState<EngineHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void Promise.all([
      loadEngineHealth(),
      loadDiscoveries(8),
      loadPublicDomain(),
      loadPublicAlerts(8),
      loadProviders(),
    ]).then(([engine, found, posts, changes, loaded]) => {
      if (!active) return;
      setHealth(engine);
      setDiscoveries(found);
      setWork(posts);
      setAlerts(changes);
      setProviders(loaded);
      setIsLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  const filteredProviders = useMemo(() => {
    return providers.filter((provider) => {
      const matchesCategory = category === "All" || provider.category === category;
      const haystack = `${provider.name} ${provider.summary} ${provider.category} ${provider.location} ${provider.listings.map((listing) => `${listing.title} ${listing.description} ${listing.category ?? ""}`).join(" ")}`.toLowerCase();
      const matchesQuery = haystack.includes(query.trim().toLowerCase());
      return matchesCategory && matchesQuery;
    });
  }, [category, providers, query]);

  const categories = ["All", ...Array.from(new Set(providers.map((provider) => provider.category).filter(Boolean)))];

  return (
    <main>
      <section className="border-b border-line py-12 sm:py-16">
        <Container>
          <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Canonical world</p>
          <h1 className="mt-2 font-display text-display tracking-tight text-fg">What is stored right now</h1>
          <p className="mt-4 max-w-2xl text-lede text-muted">
            This page reads the public API. An empty list means that record is not stored. A failed read means the engine is not reachable from this page.
          </p>
          {isLoading ? <p className="mt-6 text-muted">Reading the canonical API…</p> : null}
          {!isLoading && health && !health.reachable ? (
            <p className="mt-6 rounded-2xl border border-line bg-raised p-5 text-fg">
              The API did not answer. Nothing below is live until the canonical backend is reachable.
            </p>
          ) : null}
          {!isLoading && health?.reachable ? (
            <p className="mt-6 font-mono text-micro uppercase tracking-[0.12em] text-cyan">
              Engine {health.status || "ok"}
              {health.cycle?.id ? ` · cycle ${health.cycle.id} ${health.cycle.status || ""}` : " · no cycle recorded"}
              {health.cycle?.ended_at ? ` · ended ${health.cycle.ended_at}` : ""}
            </p>
          ) : null}
          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            <article className="rounded-2xl border border-line bg-void p-5 lg:col-span-2">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-display text-2xl text-fg">Observations</h2>
                <Link to="/discoveries" className="text-sm text-cyan">Open the list</Link>
              </div>
              {!isLoading && discoveries.length === 0 ? <p className="mt-3 text-sm text-muted">No external observation with a linked claim is public yet.</p> : null}
              <div className="mt-3 space-y-3">
                {discoveries.map((row) => (
                  <div key={row.id}>
                    <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">{row.source} · {row.epistemic_state} · {row.freshness || "unknown"}</p>
                    <p className="mt-1 text-fg">{row.title || "Untitled observation"}</p>
                    <p className="mt-1 text-sm text-muted">{row.excerpt}</p>
                  </div>
                ))}
              </div>
            </article>
            <article className="rounded-2xl border border-line bg-void p-5">
              <h2 className="font-display text-2xl text-fg">Open work</h2>
              {!isLoading && work.length === 0 ? <p className="mt-3 text-sm text-muted">No open job, offer, or trade is recorded.</p> : null}
              <div className="mt-3 space-y-3">
                {work.slice(0, 6).map((row) => (
                  <div key={row.id}>
                    <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">{row.kind}</p>
                    <p className="text-fg">{row.title}</p>
                    <p className="text-sm text-muted">{row.city || "City not recorded"} · {row.stated_price || "Price not recorded"}</p>
                  </div>
                ))}
              </div>
              <Link to="/domain" className="mt-4 inline-flex text-sm text-cyan">Post or close work</Link>
              <h2 className="mt-6 font-display text-2xl text-fg">Recorded changes</h2>
              {!isLoading && alerts.length === 0 ? <p className="mt-3 text-sm text-muted">No outcome has been recorded yet.</p> : null}
              {alerts.map((alert) => <p key={alert.id} className="mt-2 text-sm text-muted">{alert.text}</p>)}
            </article>
          </div>
        </Container>
      </section>

      <section className="py-12 sm:py-16">
        <Container>
          <div className="rounded-[2rem] border border-line bg-raised p-4 sm:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Search services</p>
                <h2 className="mt-2 font-display text-3xl tracking-tight text-fg">Review live service records</h2>
              </div>
              <Button asChild>
                <Link to="/providers">
                  Browse all providers
                  <ArrowRight />
                </Link>
              </Button>
            </div>

            <div className="mt-6 flex flex-col gap-4 lg:flex-row">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search for plumbing, repair, cleaning, errands..."
                className="min-h-12 flex-1 rounded-xl border border-line bg-void px-4 text-base text-fg placeholder:text-muted"
              />
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="min-h-12 rounded-xl border border-line bg-void px-4 text-base text-fg"
              >
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {isLoading ? (
                <div className="rounded-2xl border border-line bg-void p-6 text-muted md:col-span-2 xl:col-span-3">
                  Loading live service records from the backend…
                </div>
              ) : filteredProviders.length > 0 ? (
                filteredProviders.map((provider) => (
                  <div key={provider.id} className="rounded-2xl border border-line bg-void p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">{provider.category}</p>
                        <h3 className="mt-2 font-display text-xl text-fg">{provider.name}</h3>
                      </div>
                      {provider.verified && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-cyan/40 bg-cyan-dim px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-cyan">
                          <ShieldCheck className="size-3" />
                          Verified
                        </span>
                      )}
                    </div>
                    <p className="mt-3 text-sm text-muted">{provider.summary}</p>

                    <div className="mt-4 space-y-2 text-sm text-muted">
                      <p>{provider.location}</p>
                      <p>{provider.response}</p>
                      <p className="font-medium text-fg">{provider.price}</p>
                    </div>

                    <Button asChild className="mt-5 w-full">
                      <Link to="/providers" search={{ provider: provider.id, q: query.trim() || undefined }}>
                        View details
                      </Link>
                    </Button>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-line bg-void p-6 text-muted md:col-span-2 xl:col-span-3">
                  No verified providers match this search. A provider appears here only after identity is verified and the listing is made public. Nothing on this page is an estimated rating or a predicted price.
                </div>
              )}
            </div>
          </div>
        </Container>
      </section>

      <section className="border-t border-line py-12 sm:py-16">
        <Container>
          <div className="grid gap-8 lg:grid-cols-3">
            <div>
              <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">How it works</p>
              <h2 className="mt-2 font-display text-3xl tracking-tight text-fg">Simple, trusted, local.</h2>
            </div>
            <div className="rounded-2xl border border-line bg-raised p-5">
              <div className="mb-3 inline-flex size-9 items-center justify-center rounded-full border border-cyan/40 bg-cyan-dim font-mono text-micro text-cyan">01</div>
              <h3 className="font-display text-xl text-fg">Search by need</h3>
              <p className="mt-2 text-sm text-muted">Find the right kind of help for your home, office, or day-to-day task.</p>
            </div>
            <div className="rounded-2xl border border-line bg-raised p-5">
              <div className="mb-3 inline-flex size-9 items-center justify-center rounded-full border border-cyan/40 bg-cyan-dim font-mono text-micro text-cyan">02</div>
              <h3 className="font-display text-xl text-fg">Read the recorded offer</h3>
              <p className="mt-2 text-sm text-muted">Scope, stated price, and availability come from the provider’s public listing. Missing fields stay missing.</p>
            </div>
            <div className="rounded-2xl border border-line bg-raised p-5 lg:col-start-2">
              <div className="mb-3 inline-flex size-9 items-center justify-center rounded-full border border-cyan/40 bg-cyan-dim font-mono text-micro text-cyan">03</div>
              <h3 className="font-display text-xl text-fg">Request the job</h3>
              <p className="mt-2 text-sm text-muted">A request stays pending until that provider accepts it. Acceptance is not implied by sending the form.</p>
            </div>
            <div className="rounded-2xl border border-line bg-raised p-5">
              <div className="mb-3 inline-flex size-9 items-center justify-center rounded-full border border-cyan/40 bg-cyan-dim font-mono text-micro text-cyan">04</div>
              <h3 className="font-display text-xl text-fg">Check the status</h3>
              <p className="mt-2 text-sm text-muted">The request page shows the recorded status and any reply the provider has actually written.</p>
            </div>
          </div>
        </Container>
      </section>

      <section className="border-t border-line bg-raised py-12 sm:py-16">
        <Container className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Why this works</p>
            <h2 className="mt-2 font-display text-3xl tracking-tight text-fg">Only recorded facts are shown.</h2>
          </div>

          {[
            "Unverified providers stay off the public list.",
            "A stated price is the provider’s price, not a forecast.",
            "No review score appears until completed jobs exist to measure.",
          ].map((item) => (
            <div key={item} className="flex items-start gap-3 rounded-2xl border border-line bg-void p-5">
              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-cyan" />
              <p className="text-base text-fg">{item}</p>
            </div>
          ))}
        </Container>
      </section>

      <CtaBand />
    </main>
  );
}
