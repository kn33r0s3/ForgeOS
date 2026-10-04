import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, CircleHelp, Compass, GitBranch, Lightbulb, Link2, Radio, ShieldCheck, Sparkles, Users, Wrench, X } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, MetricTile, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
import { loadPublicFeed, type PublicFeedItem } from "@/lib/content";

export const Route = createFileRoute("/feed")({
  validateSearch: (search: Record<string, unknown>): { entity_type?: string; entity_id?: number } => {
    const entityType = typeof search.entity_type === "string" ? search.entity_type : undefined;
    const entityId = Number.isInteger(Number(search.entity_id)) && Number(search.entity_id) > 0
      ? Number(search.entity_id)
      : undefined;
    return {
      ...(entityType ? { entity_type: entityType } : {}),
      ...(entityId ? { entity_id: entityId } : {}),
    };
  },
  component: NetworkFeedPage,
  head: () => ({ meta: [{ title: "Network — Hami" }] }),
});

const FILTERS = [
  { label: "All records", value: "all" },
  { label: "Signals", value: "signal" },
  { label: "Evidence-linked", value: "evidence" },
  { label: "Opportunities", value: "opportunity" },
  { label: "Capabilities", value: "capability" },
  { label: "Connected records", value: "connection" },
] as const;

const KIND_LABELS: Record<string, string> = {
  signal: "Public signal",
  question: "Research question",
  pattern: "Emerging pattern",
  belief: "Working belief",
  opportunity: "Opportunity hypothesis",
  actor: "Network participant",
  capability: "Capability",
  work_item: "Work / need",
  connection: "Possible connection",
  outcome: "Recorded outcome",
};

const KIND_ICONS: Record<string, typeof Radio> = {
  signal: Radio,
  question: CircleHelp,
  pattern: Compass,
  belief: Lightbulb,
  opportunity: Lightbulb,
  actor: Users,
  capability: Wrench,
  work_item: CircleHelp,
  connection: Link2,
  outcome: Compass,
};

const ENTITY_LABELS: Record<string, string> = {
  claim: "Evidence-backed statement",
  signal: "Observation",
  research_question: "Research question",
  pattern: "Pattern",
  belief: "Working belief",
  opportunity: "Opportunity",
  provider: "Provider",
  service_listing: "Service listing",
  domain_record: "Work or need",
  outcome: "Recorded outcome",
  network_connection: "Connection",
};

const RELATION_LABELS: Record<string, string> = {
  supported_by: "Supported by",
  asks_about: "Research about",
  grounded_in: "Grounded in",
  derived_from: "Derived from",
  informed_by: "Informed by",
  offered_by: "Offered by",
  left_side: "Connected record",
  right_side: "Connected record",
};

const EMPTY_GUIDANCE: Record<string, { message: string; link: string; to: "/discoveries" | "/domain" | "/providers" }> = {
  signal: {
    message: "External observations enter after their source is recorded and the evidence is eligible for public display.",
    link: "Browse collected observations",
    to: "/discoveries",
  },
  work_item: {
    message: "Needs and offers appear when someone posts them to the public work board.",
    link: "Open the work board",
    to: "/domain",
  },
  opportunity: {
    message: "An opportunity appears only after a sourced observation is connected to research and supporting evidence.",
    link: "Review collected observations",
    to: "/discoveries",
  },
  capability: {
    message: "A capability appears when an active service listing belongs to a verified provider and is made public.",
    link: "Explore verified providers",
    to: "/providers",
  },
  actor: {
    message: "Public participant records are verified providers. Hami does not publish generic people or group profiles yet.",
    link: "Explore verified providers",
    to: "/providers",
  },
  connection: {
    message: "A connection appears only when it is public and both linked records are already public. A possible match is not a confirmed agreement.",
    link: "Review public work records",
    to: "/domain",
  },
};

function dateLabel(value?: string | null) {
  if (!value) return "Time unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unknown";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function sourceLabel(value?: string | null) {
  const labels: Record<string, string> = {
    "Forge pattern engine": "Hami analysis",
    "Forge knowledge graph": "Hami synthesis",
    "Forge opportunity engine": "Hami opportunity assessment",
    "public provider registry": "Verified provider record",
    "public service registry": "Verified service listing",
    "public work board": "Public work post",
    "public Forge network": "Public network record",
  };
  return value ? labels[value] ?? value : "Source not recorded";
}

function NetworkFeedPage() {
  const { entity_type: entityType, entity_id: entityId } = Route.useSearch();
  const [items, setItems] = useState<PublicFeedItem[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["value"]>("all");
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setState("loading");
    void loadPublicFeed(100, entityType, entityId, { fresh: reloadVersion > 0 }).then((result) => {
      if (!active) return;
      if (result === null) {
        setState("unavailable");
        return;
      }
      setItems(result);
      setState("ready");
    });
    return () => {
      active = false;
    };
  }, [entityId, entityType, reloadVersion]);

  const visible = useMemo(() => filterItems(items, filter), [filter, items]);
  const filterCounts = useMemo(
    () => Object.fromEntries(FILTERS.map((item) => [item.value, filterItems(items, item.value).length])) as Record<(typeof FILTERS)[number]["value"], number>,
    [items],
  );
  const graphStats = useMemo(() => {
    const entityRefs = new Set<string>();
    const relationRefs = new Set<string>();
    for (const item of items) {
      const source = `${item.entity_type}:${item.entity_id}`;
      entityRefs.add(source);
      for (const relation of item.relations) {
        const target = `${relation.entity_type}:${relation.entity_id}`;
        entityRefs.add(target);
        relationRefs.add(`${source}:${relation.relation}:${target}`);
      }
    }
    return {
      entityRefs: entityRefs.size,
      relationRefs: relationRefs.size,
      capabilities: items.filter((item) => item.kind === "capability").length,
      opportunities: items.filter((item) => item.kind === "opportunity").length,
      evidenceLinks: items.reduce(
        (total, item) => total + item.relations.filter((relation) =>
          ["supported_by", "grounded_in", "informed_by"].includes(relation.relation),
        ).length,
        0,
      ),
    };
  }, [items]);
  const titleByReference = useMemo(() => {
    // Every record is labeled with its own title only. A relation target that
    // is not among the loaded items falls back to its generic entity label in
    // the render below — never to the referring record's title.
    const titles = new Map<string, string>();
    for (const item of items) {
      titles.set(`${item.entity_type}:${item.entity_id}`, item.title);
    }
    return titles;
  }, [items]);

  return (
    <main className="min-h-full">
      <PageHeader
        eyebrow="Hami Network"
        title="Explore the connected world"
        lede="Public entities and their recorded relationships, capabilities, evidence links, and opportunity hypotheses. A connection is a stored relation, not proof of agreement."
        aside={
          <>
            <p className="flex items-center gap-2 text-micro font-extrabold uppercase tracking-[0.12em] text-accent">
              <ShieldCheck className="size-3.5" aria-hidden="true" /> Projection legend
            </p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Entities are records. Relations are sourced links. Capabilities and opportunities remain bounded by their evidence and state.
            </p>
          </>
        }
      >
        {entityType && entityId ? (
          <p className="mt-6 inline-flex items-center gap-2 rounded-card border-2 border-accent bg-black py-1.5 pl-3 pr-1.5 text-xs text-ink">
            <GitBranch className="size-3.5 text-accent" aria-hidden="true" />
            Network context: {ENTITY_LABELS[entityType] ?? entityType.replaceAll("_", " ")}
            <Link
              to="/feed"
              search={{}}
              className="inline-flex min-h-8 items-center gap-1 rounded-card px-2 text-accent hover:bg-accent hover:text-black"
            >
              <X className="size-3.5" aria-hidden="true" /> Clear
            </Link>
          </p>
        ) : null}
      </PageHeader>

      <Container className="max-w-5xl py-10 sm:py-14">
        <section aria-label="Visible network projection" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <MetricTile index={0} loading={state === "loading"} label="Entity refs" value={state === "ready" ? graphStats.entityRefs : null} />
          <MetricTile index={1} loading={state === "loading"} label="Relations" value={state === "ready" ? graphStats.relationRefs : null} />
          <MetricTile index={2} loading={state === "loading"} label="Capabilities" value={state === "ready" ? graphStats.capabilities : null} />
          <MetricTile index={3} loading={state === "loading"} label="Hypotheses" value={state === "ready" ? graphStats.opportunities : null} />
          <MetricTile index={4} loading={state === "loading"} label="Evidence links" value={state === "ready" ? graphStats.evidenceLinks : null} className="col-span-2 sm:col-span-1" />
        </section>

        <div
          className="-mx-5 mt-8 flex flex-wrap gap-2 px-5 pb-2 sm:mx-0 sm:px-0"
          role="group"
          aria-label="Filter network feed"
        >
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={filter === item.value}
              onClick={() => setFilter(item.value)}
              className="chip"
            >
              {item.label}
              {state === "ready" ? <span className="chip-count">{filterCounts[item.value]}</span> : null}
            </button>
          ))}
        </div>

        {state === "loading" ? (
          <SkeletonCards count={4} label="Reading the network…" className="mt-6 space-y-3" />
        ) : null}
        {state === "unavailable" ? (
          <UnavailableState
            className="mt-6"
            title="The network feed is unavailable"
            body="The public API did not return usable feed data. No sample activity is shown in its place."
            onRetry={() => setReloadVersion((version) => version + 1)}
          />
        ) : null}
        {state === "ready" && visible.length === 0 ? (
          filter === "all" ? (
            <EmptyState
              className="mt-6"
              icon={Sparkles}
              title="No public network records yet"
              body="Nothing is added to fill a quiet network. Records appear only when their source and visibility requirements are met."
            >
              <Link to="/discoveries" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                Research observations <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
              <Link to="/domain" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                Public work board <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
              <Link to="/providers" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                Provider capabilities <ArrowUpRight className="size-4" aria-hidden="true" />
              </Link>
            </EmptyState>
          ) : (
            <EmptyState
              className="mt-6"
              icon={KIND_ICONS[filter] ?? Compass}
              title="No items in this part of the network yet"
              body={filter === "evidence" ? "No public records with evidence-related links are available." : EMPTY_GUIDANCE[filter]?.message ?? "New entries appear when real records meet their source and visibility requirements."}
            >
              {EMPTY_GUIDANCE[filter] ? (
                <Link to={EMPTY_GUIDANCE[filter].to} className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                  {EMPTY_GUIDANCE[filter].link} <ArrowUpRight className="size-4" aria-hidden="true" />
                </Link>
              ) : null}
            </EmptyState>
          )
        ) : null}

        {state === "ready" && visible.length > 0 ? (
          <p className="mt-6 text-micro font-extrabold uppercase tracking-[0.12em] text-dim" aria-live="polite">
            Showing {visible.length} of {items.length} record{items.length === 1 ? "" : "s"}
          </p>
        ) : null}

        <ol className="mt-3 space-y-3">
          {visible.map((item, index) => {
            const Icon = KIND_ICONS[item.kind] ?? Radio;
            const safeSourceUrl = item.source_url?.startsWith("https://") ? item.source_url : null;
            const relatedProviderId = item.kind === "actor"
              ? item.entity_id
              : item.relations.find((relation) => relation.entity_type === "provider")?.entity_id;
            const visibleRelations = item.relations.filter((relation) => !["entity", "event", "evidence", "relation"].includes(relation.entity_type));
            return (
              <li
                key={item.id}
                className="card card-interactive reveal min-w-0 p-5 sm:p-6"
                style={{ "--i": Math.min(index, 8) } as React.CSSProperties}
              >
                <article className="flex min-w-0 items-start gap-4">
                  <span className="icon-chip hidden sm:inline-flex" aria-hidden="true">
                    <Icon className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="status-pill status-pill-accent max-w-full break-all">
                        <Icon className="size-3 sm:hidden" aria-hidden="true" />
                        {KIND_LABELS[item.kind] ?? item.kind.replaceAll("_", " ")}
                      </span>
                      {item.category ? <span className="status-pill status-pill-neutral max-w-full break-all">{item.category}</span> : null}
                      {item.status ? <span className="status-pill status-pill-neutral max-w-full break-all">{item.status.replaceAll("_", " ")}</span> : null}
                    </div>
                    <h2 className="mt-3 break-words font-display text-2xl leading-tight tracking-tight text-ink">{item.title}</h2>
                    <p className="mt-2 break-words whitespace-pre-line text-sm leading-6 text-muted">{item.summary}</p>
                    <dl className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-dim">
                      <div className="min-w-0"><dt className="sr-only">Source</dt><dd className="break-all">{sourceLabel(item.source)}</dd></div>
                      <div className="min-w-0"><dt className="sr-only">Evidence state</dt><dd className="break-all">{item.epistemic_state.replaceAll("_", " ")}</dd></div>
                      <div><dt className="sr-only">Updated</dt><dd><time dateTime={item.updated_at || item.occurred_at || undefined}>{dateLabel(item.updated_at || item.occurred_at)}</time></dd></div>
                      {item.location ? <div className="min-w-0"><dt className="sr-only">Location</dt><dd className="break-all">{item.location}</dd></div> : null}
                    </dl>
                    {visibleRelations.length > 0 ? (
                      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                        <span className="text-dim">Connected to</span>
                        {visibleRelations.map((relation) => (
                          <Link
                            key={`${relation.entity_type}:${relation.entity_id}:${relation.relation}`}
                            to="/feed"
                            search={{ entity_type: relation.entity_type, entity_id: relation.entity_id }}
                            className="inline-flex min-h-8 items-center gap-1 rounded-card border-2 border-line bg-black px-3 font-bold text-muted transition-colors hover:border-accent/60 hover:text-accent"
                          >
                            <Link2 className="size-3" aria-hidden="true" />
                            {RELATION_LABELS[relation.relation] ?? "Related to"} · {titleByReference.get(`${relation.entity_type}:${relation.entity_id}`) ?? ENTITY_LABELS[relation.entity_type] ?? "Network record"}
                          </Link>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line pt-3">
                      <Link
                        to="/feed"
                        search={{ entity_type: item.entity_type, entity_id: item.entity_id }}
                        className="link-arrow inline-flex min-h-10 items-center gap-1 text-xs text-muted hover:text-accent"
                      >
                        Open network context <ArrowUpRight className="size-3.5" />
                      </Link>
                      {item.kind === "signal" || item.kind === "question" || item.kind === "pattern" || item.kind === "belief" || item.kind === "opportunity" ? (
                        <Link to={item.kind === "opportunity" ? "/opportunities" : "/discoveries"} className="link-arrow inline-flex min-h-10 items-center gap-1 text-xs font-semibold text-accent">
                          Review observations <ArrowUpRight className="size-3.5" />
                        </Link>
                      ) : null}
                      {item.kind === "capability" || item.kind === "actor" ? (
                        <Link
                          to="/providers"
                          search={relatedProviderId ? { provider: relatedProviderId } : {}}
                          className="link-arrow inline-flex min-h-10 items-center gap-1 text-xs font-semibold text-accent"
                        >
                          Explore providers <ArrowUpRight className="size-3.5" />
                        </Link>
                      ) : null}
                      {item.kind === "work_item" || item.kind === "connection" || item.kind === "outcome" ? (
                        <Link to="/domain" className="link-arrow inline-flex min-h-10 items-center gap-1 text-xs font-semibold text-accent">
                          Open work records <ArrowUpRight className="size-3.5" />
                        </Link>
                      ) : null}
                      {safeSourceUrl ? (
                        <a className="link-arrow inline-flex min-h-10 items-center gap-1 text-xs font-semibold text-accent" href={safeSourceUrl} target="_blank" rel="noreferrer">
                          Open cited source <ArrowUpRight className="size-3.5" />
                        </a>
                      ) : null}
                    </div>
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      </Container>
    </main>
  );
}

type FeedFilter = (typeof FILTERS)[number]["value"];

function filterItems(items: PublicFeedItem[], filter: FeedFilter) {
  if (filter === "all") return items;
  if (filter === "evidence") {
    return items.filter((item) => item.relations.some((relation) =>
      ["supported_by", "grounded_in", "informed_by"].includes(relation.relation),
    ));
  }
  if (filter === "connection") {
    return items.filter((item) => item.kind === "connection" || item.relations.length > 0);
  }
  return items.filter((item) => item.kind === filter);
}
