import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpenText,
  BriefcaseBusiness,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { Container } from "@/components/layout/container";
import { EmptyState, SkeletonCards } from "@/components/ui/feedback";
import {
  loadDiscoveries,
  loadProviders,
  type ProviderRecord,
  type PublicDiscovery,
} from "@/lib/content";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({ meta: [{ title: "Hami — A useful next step" }] }),
});

function HomePage() {
  const [discoveries, setDiscoveries] = useState<PublicDiscovery[] | null>(null);
  const [providers, setProviders] = useState<ProviderRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const scope = { fresh: reloadVersion > 0 };

    void Promise.allSettled([
      loadDiscoveries(3, scope),
      loadProviders(undefined, scope),
    ]).then(([discoveryResult, providerResult]) => {
      if (!active) return;
      setDiscoveries(
        discoveryResult.status === "fulfilled" ? discoveryResult.value : null,
      );
      setProviders(
        providerResult.status === "fulfilled" ? providerResult.value : null,
      );
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [reloadVersion]);

  return (
    <main>
      <section className="relative isolate overflow-hidden border-b-2 border-black">
        <div className="hero-glow -z-10" aria-hidden="true" />
        <div className="hero-grain -z-10" aria-hidden="true" />
        <Container className="py-16 sm:py-24 lg:py-28">
          <p className="text-micro font-extrabold uppercase tracking-[0.14em] text-accent">
            Hami · Nepal-first real-world coordination
          </p>
          <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(0,1fr)_19rem] lg:items-end">
            <div>
              <h1 className="max-w-4xl font-gothic text-[clamp(2.8rem,7vw,6.5rem)] leading-[1.02] text-ink [text-shadow:3px_3px_0_#000]">
                Make a real need clearer.
                <br />
                <span className="text-muted">Find what is already known.</span>
              </h1>
              <p className="mt-7 max-w-2xl text-lg leading-8 text-muted sm:text-xl">
                Hami brings needs, public observations, and capabilities into one
                shared view, so people can see what is known, what remains
                uncertain, and where a human next step is needed.
              </p>
            </div>
            <aside className="rounded-card border-2 border-line bg-card/80 p-5">
              <ShieldCheck className="size-5 text-accent" aria-hidden="true" />
              <h2 className="mt-3 font-display text-xl font-semibold text-ink">
                No invented activity
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                Public listings appear only from eligible records. A post,
                hypothesis, or possible match is not proof of availability,
                agreement, or an outcome.
              </p>
            </aside>
          </div>

          <div className="mt-9 flex flex-wrap gap-3">
            <Link
              to="/domain"
              className="btn-wipe inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-black bg-accent px-5 font-extrabold text-black"
            >
              Browse or post work <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <Link
              to="/request"
              className="inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-line bg-card px-5 font-bold text-ink transition-colors hover:border-accent"
            >
              Submit a need for understanding
            </Link>
          </div>
        </Container>
      </section>

      <Container className="max-w-site py-12 sm:py-16">
        <section aria-labelledby="start-heading">
          <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
            Start with what you need
          </p>
          <h2
            id="start-heading"
            className="mt-2 max-w-3xl text-3xl font-black tracking-tight text-ink sm:text-4xl"
          >
            Useful paths, with their limits visible.
          </h2>

          <div className="mt-7 grid gap-4 lg:grid-cols-3">
            <article className="card flex flex-col p-5 sm:p-6">
              <BriefcaseBusiness className="size-5 text-accent" aria-hidden="true" />
              <h3 className="mt-4 font-display text-2xl tracking-tight text-ink">
                Find or share work
              </h3>
              <p className="mt-2 flex-1 text-sm leading-6 text-muted">
                Browse public jobs, offers, and trades, or add a post. Posts
                and suggested matches do not guarantee a response or agreement.
              </p>
              <Link
                to="/domain"
                className="link-arrow mt-5 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent"
              >
                Open the public work board <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </article>

            <article className="card flex flex-col p-5 sm:p-6">
              <ShieldCheck className="size-5 text-accent" aria-hidden="true" />
              <h3 className="mt-4 font-display text-2xl tracking-tight text-ink">
                Check listed services
              </h3>
              {loading ? (
                <p className="mt-2 text-sm leading-6 text-muted">
                  Checking public provider records…
                </p>
              ) : providers === null ? (
                <p className="mt-2 text-sm leading-6 text-warning">
                  Provider records could not be checked. No availability is assumed.
                </p>
              ) : providers.length === 0 ? (
                <p className="mt-2 flex-1 text-sm leading-6 text-muted">
                  No verified public providers are listed right now. Hami does
                  not add names to fill an empty directory.
                </p>
              ) : (
                <p className="mt-2 flex-1 text-sm leading-6 text-muted">
                  {providers.length} verified public provider
                  {providers.length === 1 ? "" : "s"} in the current listing.
                  Availability and terms remain provider-specific.
                </p>
              )}
              <Link
                to="/providers"
                className="link-arrow mt-5 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent"
              >
                Browse provider records <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </article>

            <article className="card flex flex-col p-5 sm:p-6">
              <BookOpenText className="size-5 text-accent" aria-hidden="true" />
              <h3 className="mt-4 font-display text-2xl tracking-tight text-ink">
                Follow a source
              </h3>
              <p className="mt-2 flex-1 text-sm leading-6 text-muted">
                Review public observations with their source and evidence label.
                A published source is not automatically a verified claim or an
                offer.
              </p>
              <Link
                to="/discoveries"
                className="link-arrow mt-5 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent"
              >
                Explore sourced observations <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </article>
          </div>
        </section>

        <section
          aria-labelledby="observations-heading"
          className="mt-14 rounded-card border-2 border-line bg-card p-5 sm:mt-16 sm:p-7"
        >
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
                Current public evidence
              </p>
              <h2
                id="observations-heading"
                className="mt-2 font-display text-3xl tracking-tight text-ink"
              >
                Sourced observations
              </h2>
            </div>
            <Link
              to="/discoveries"
              className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent"
            >
              See all observations <ArrowUpRight className="size-4" aria-hidden="true" />
            </Link>
          </div>

          {loading ? (
            <SkeletonCards count={2} label="Checking sourced observations…" className="mt-6 space-y-3" />
          ) : discoveries === null ? (
            <div className="mt-6 rounded-card border border-warning/35 bg-warning/5 p-4">
              <p className="text-sm text-ink" role="status">
                The observation service could not be checked. This is not an empty result.
              </p>
              <button
                type="button"
                onClick={() => setReloadVersion((version) => version + 1)}
                className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-card px-3 text-sm font-semibold text-accent transition-colors hover:bg-secondary"
              >
                <RefreshCw className="size-4" aria-hidden="true" /> Try again
              </button>
            </div>
          ) : discoveries.length === 0 ? (
            <EmptyState
              className="mt-6"
              headingLevel="h3"
              icon={BookOpenText}
              title="No sourced observations are available right now"
              body="Hami leaves this space empty until an eligible source record can be shown."
            />
          ) : (
            <ol className="mt-6 grid gap-3 md:grid-cols-2">
              {discoveries.map((item) => (
                <li key={item.id} className="rounded-card border border-line bg-paper p-4">
                  <div className="flex flex-wrap gap-2">
                    <span className="status-pill status-pill-accent">{item.source}</span>
                    <span className="status-pill status-pill-neutral">
                      {item.epistemic_state}
                    </span>
                    <span className={`status-pill ${item.freshness === "stale" ? "status-pill-warning" : "status-pill-neutral"}`}>
                      {item.freshness || "freshness unknown"}
                    </span>
                  </div>
                  <h3 className="mt-3 font-display text-xl leading-tight text-ink">
                    {item.title || "Untitled observation"}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">{item.excerpt}</p>
                  {item.canonical_url ? (
                    <a
                      href={item.canonical_url}
                      target="_blank"
                      rel="noreferrer"
                      className="link-arrow mt-3 inline-flex min-h-10 items-center gap-1 break-all text-sm text-accent"
                    >
                      Open source <ArrowUpRight className="size-4 shrink-0" aria-hidden="true" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="mt-10 grid gap-5 rounded-card border-l-4 border-accent bg-paper p-5 sm:grid-cols-[1fr_auto] sm:items-center sm:p-7">
          <div>
            <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
              Have a need to clarify?
            </p>
            <h2 className="mt-2 font-display text-2xl tracking-tight text-ink">
              Share it without sending contact details.
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              The request form stores a redacted observation and gives an
              immediate receipt. It does not create a customer, contact anyone,
              or promise a reply. Do not include sensitive information.
            </p>
          </div>
          <Link
            to="/request"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-card bg-accent px-5 text-sm font-extrabold text-accent-ink transition-colors hover:bg-accent/90"
          >
            Submit a need <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </section>
      </Container>
    </main>
  );
}
