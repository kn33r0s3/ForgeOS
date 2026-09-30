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
  loadPublicFeed,
  loadProviders,
  type ProviderRecord,
  type PublicDiscovery,
  type PublicFeedItem,
} from "@/lib/content";

function feedDateLabel(value?: string | null) {
  if (!value) return "Time not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time not recorded";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({ meta: [{ title: "Hami — A useful next step" }] }),
});

function HomePage() {
  const [discoveries, setDiscoveries] = useState<PublicDiscovery[] | null>(null);
  const [providers, setProviders] = useState<ProviderRecord[] | null>(null);
  const [feedItems, setFeedItems] = useState<PublicFeedItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const scope = { fresh: reloadVersion > 0 };

    void Promise.allSettled([
      loadDiscoveries(3, scope),
      loadProviders(undefined, scope),
      loadPublicFeed(3, undefined, undefined, scope),
    ]).then(([discoveryResult, providerResult, feedResult]) => {
      if (!active) return;
      setDiscoveries(
        discoveryResult.status === "fulfilled" ? discoveryResult.value : null,
      );
      setProviders(
        providerResult.status === "fulfilled" ? providerResult.value : null,
      );
      setFeedItems(
        feedResult.status === "fulfilled" ? feedResult.value : null,
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
        <Container className="py-12 sm:py-16 lg:py-20">
          <p className="text-micro font-extrabold uppercase tracking-[0.14em] text-accent">
            Hami · Nepal-first real-world coordination
          </p>
          <div className="mt-6 grid items-center gap-9 lg:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)] lg:gap-12">
            <div className="max-w-3xl">
              <h1 className="max-w-3xl font-display text-[clamp(2.7rem,5.7vw,5.25rem)] font-black leading-[0.98] tracking-[-0.045em] text-ink">
                Make a real need clearer.
                <span className="mt-2 block text-muted">Find what is already known.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
                Hami brings needs, public observations, and capabilities into one
                shared view, so people can see what is known, what remains
                uncertain, and where a human next step is needed.
              </p>

              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  to="/domain"
                  className="btn-wipe inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-black bg-accent px-5 font-extrabold text-black shadow-[0_4px_0_#000] transition-transform hover:-translate-y-0.5 hover:shadow-[0_6px_0_#000]"
                >
                  Browse or post work <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
                <Link
                  to="/request"
                  className="inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-line bg-card px-5 font-bold text-ink transition-colors hover:border-accent"
                >
                  Share a need
                </Link>
              </div>

              <div className="mt-7 flex max-w-xl items-start gap-3 border-l-2 border-accent pl-4">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden="true" />
                <p className="text-sm leading-6 text-muted">
                  <span className="font-bold text-ink">No invented activity.</span>{" "}
                  A post or possible match is not proof of availability,
                  agreement, or an outcome.
                </p>
              </div>
            </div>

            <figure className="relative isolate mx-auto w-full max-w-2xl overflow-hidden rounded-[1.35rem] border-2 border-line bg-card shadow-[0_24px_70px_-32px_rgba(0,0,0,0.9)]">
              <img
                src="/hami-home.jpg"
                alt="A warmly lit workspace with tools and an open notebook"
                className="h-[17rem] w-full object-cover sm:h-[23rem] lg:h-[26rem]"
                fetchPriority="high"
              />
              <div
                className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/5"
                aria-hidden="true"
              />
              <figcaption className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-4 p-5 sm:p-7">
                <div>
                  <span className="status-pill border-white/20 bg-black/45 text-white">
                    Illustrative workspace
                  </span>
                  <p className="mt-3 max-w-sm font-display text-2xl font-bold leading-tight text-white sm:text-3xl">
                    Real needs. Clearer next steps.
                  </p>
                </div>
                <span
                  className="mb-1 hidden size-11 shrink-0 items-center justify-center rounded-full border border-white/40 bg-white/10 text-white backdrop-blur-sm sm:inline-flex"
                  aria-hidden="true"
                >
                  <ArrowUpRight className="size-5" />
                </span>
              </figcaption>
            </figure>
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

        <section
          aria-labelledby="network-preview-heading"
          className="mt-10 rounded-card border-2 border-line bg-card p-5 sm:mt-12 sm:p-7"
        >
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
                Current public network
              </p>
              <h2
                id="network-preview-heading"
                className="mt-2 font-display text-3xl tracking-tight text-ink"
              >
                Recent eligible records
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                A small view of records already in Hami&apos;s public Feed.
                Status and evidence labels stay attached; an opportunity
                hypothesis is not a confirmed offer.
              </p>
            </div>
            <Link
              to="/feed"
              className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent"
            >
              Explore the network <ArrowUpRight className="size-4" aria-hidden="true" />
            </Link>
          </div>

          {loading ? (
            <SkeletonCards count={2} label="Checking public network records…" className="mt-6 space-y-3" />
          ) : feedItems === null ? (
            <div className="mt-6 rounded-card border border-warning/35 bg-warning/5 p-4">
              <p className="text-sm text-ink" role="status">
                Public network records could not be checked. This is not an empty result.
              </p>
              <button
                type="button"
                onClick={() => setReloadVersion((version) => version + 1)}
                className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-card px-3 text-sm font-semibold text-accent transition-colors hover:bg-secondary"
              >
                <RefreshCw className="size-4" aria-hidden="true" /> Try again
              </button>
            </div>
          ) : feedItems.length === 0 ? (
            <EmptyState
              className="mt-6"
              headingLevel="h3"
              icon={BookOpenText}
              title="No public network records are available right now"
              body="Only eligible records appear here. Hami does not generate activity to fill this space."
            />
          ) : (
            <ol className="mt-6 grid gap-3">
              {feedItems.map((item) => {
                const timestamp = item.updated_at || item.occurred_at;
                return (
                  <li key={item.id} className="rounded-card border border-line bg-paper p-4 sm:p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="status-pill status-pill-accent">
                        {item.kind.replaceAll("_", " ")}
                      </span>
                      {item.status ? (
                        <span className="status-pill status-pill-neutral">
                          {item.status.replaceAll("_", " ")}
                        </span>
                      ) : null}
                      <span className="status-pill status-pill-neutral">
                        {item.epistemic_state.replaceAll("_", " ")}
                      </span>
                    </div>
                    <h3 className="mt-3 font-display text-xl leading-tight text-ink">
                      {item.title}
                    </h3>
                    <p className="mt-2 whitespace-pre-line text-sm leading-6 text-muted">
                      {item.summary}
                    </p>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3 text-xs text-dim">
                      <p>
                        {item.source || "Source not recorded"}
                        {" · "}
                        {feedDateLabel(timestamp)}
                      </p>
                      <Link
                        to="/feed"
                        search={{ entity_type: item.entity_type, entity_id: item.entity_id }}
                        className="link-arrow inline-flex min-h-9 items-center gap-1 font-semibold text-accent"
                      >
                        Open network context <ArrowUpRight className="size-3.5" aria-hidden="true" />
                      </Link>
                    </div>
                  </li>
                );
              })}
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
