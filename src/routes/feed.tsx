import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, CircleHelp, Compass, Lightbulb, Link2, Radio, RefreshCw, Users, Wrench } from "lucide-react";
import { Container } from "@/components/layout/container";
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
});

const FILTERS = [
  { label: "Everything", value: "all" },
  { label: "Signals", value: "signal" },
  { label: "Needs & work", value: "work_item" },
  { label: "Opportunities", value: "opportunity" },
  { label: "Capabilities", value: "capability" },
  { label: "People & groups", value: "actor" },
  { label: "Connections", value: "connection" },
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
    message: "Public participant records are verified providers. Pulse does not publish generic people or group profiles yet.",
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
    "Forge pattern engine": "Pulse analysis",
    "Forge knowledge graph": "Pulse synthesis",
    "Forge opportunity engine": "Pulse opportunity assessment",
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
    void loadPublicFeed(100, entityType, entityId).then((result) => {
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

  const visible = useMemo(
    () => filter === "all" ? items : items.filter((item) => item.kind === filter),
    [filter, items],
  );
  const titleByReference = useMemo(() => {
    const titles = new Map<string, string>();
    for (const item of items) {
      titles.set(`${item.entity_type}:${item.entity_id}`, item.title);
      for (const relation of item.relations) {
        if (relation.entity_type === "signal") {
          titles.set(`${relation.entity_type}:${relation.entity_id}`, item.title);
        }
      }
    }
    return titles;
  }, [items]);

  return (
    <main className="min-h-full py-10 sm:py-14">
      <Container className="max-w-5xl">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
          <div>
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Pulse Network</p>
            <h1 className="mt-2 font-display text-4xl tracking-tight text-fg sm:text-5xl">Signals, needs, and useful connections</h1>
            <p className="mt-4 max-w-2xl text-lede text-muted">
              A live view assembled from Pulse evidence, research, work, capability, and network records. Each entry keeps its source and uncertainty visible.
            </p>
            {entityType && entityId ? (
              <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-line bg-raised px-3 py-2 text-xs text-muted">
                Network context: {ENTITY_LABELS[entityType] ?? entityType.replaceAll("_", " ")}
                <Link to="/feed" search={{}} className="text-cyan hover:underline">Clear</Link>
              </p>
            ) : null}
          </div>
          <aside className="rounded-2xl border border-line bg-raised p-4">
            <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">How to read this feed</p>
            <p className="mt-2 text-sm text-muted">Items are shown by most recent recorded change. “Hypothesis”, “possible”, and “unknown” are deliberate states. Pulse does not publish a popularity or trust score.</p>
          </aside>
        </div>

        <div className="mt-8 flex gap-2 overflow-x-auto pb-2" aria-label="Filter network feed">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={filter === item.value}
              onClick={() => setFilter(item.value)}
              className={`min-h-10 shrink-0 rounded-full border px-4 text-sm transition-colors ${filter === item.value ? "border-cyan bg-cyan/10 text-cyan" : "border-line text-muted hover:border-cyan/50 hover:text-fg"}`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {state === "loading" ? <p className="mt-8 text-muted">Reading the network…</p> : null}
        {state === "unavailable" ? (
          <div className="mt-8 rounded-2xl border border-line bg-void p-6">
            <h2 className="font-display text-xl text-fg">The network feed is unavailable</h2>
            <p className="mt-2 text-sm text-muted">The public API did not return usable feed data. No sample activity is shown in its place.</p>
            <button
              type="button"
              onClick={() => setReloadVersion((version) => version + 1)}
              className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-full border border-line px-4 text-sm text-fg hover:border-cyan/50"
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              Retry
            </button>
          </div>
        ) : null}
        {state === "ready" && visible.length === 0 ? (
          <div className="mt-8 rounded-2xl border border-line bg-void p-6">
            <h2 className="font-display text-xl text-fg">{filter === "all" ? "No public network activity yet" : "No items in this part of the network yet"}</h2>
            {filter === "all" ? (
              <>
                <p className="mt-2 max-w-2xl text-sm text-muted">Nothing is added to fill a quiet network. Observations need a source, work appears when posted, and provider capabilities require verification.</p>
                <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm">
                  <Link to="/discoveries" className="text-cyan hover:underline">Collected observations</Link>
                  <Link to="/domain" className="text-cyan hover:underline">Public work board</Link>
                  <Link to="/providers" className="text-cyan hover:underline">Verified providers</Link>
                </div>
              </>
            ) : (
              <>
                <p className="mt-2 max-w-2xl text-sm text-muted">{EMPTY_GUIDANCE[filter]?.message ?? "New entries appear when real records meet their source and visibility requirements."}</p>
                {EMPTY_GUIDANCE[filter] ? (
                  <Link to={EMPTY_GUIDANCE[filter].to} className="mt-4 inline-flex text-sm text-cyan hover:underline">
                    {EMPTY_GUIDANCE[filter].link} <ArrowUpRight className="ml-1 size-4" />
                  </Link>
                ) : null}
              </>
            )}
          </div>
        ) : null}

        <div className="mt-5 space-y-3">
          {visible.map((item) => {
            const Icon = KIND_ICONS[item.kind] ?? Radio;
            const safeSourceUrl = item.source_url?.startsWith("https://") ? item.source_url : null;
            const relatedProviderId = item.kind === "actor"
              ? item.entity_id
              : item.relations.find((relation) => relation.entity_type === "provider")?.entity_id;
            return (
              <article key={item.id} className="rounded-2xl border border-line bg-void p-5 sm:p-6">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl border border-line bg-raised text-cyan" aria-hidden="true">
                    <Icon className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] uppercase tracking-[0.1em] text-cyan">
                      <span>{KIND_LABELS[item.kind] ?? item.kind.replaceAll("_", " ")}</span>
                      {item.category ? <><span aria-hidden="true">·</span><span>{item.category}</span></> : null}
                      {item.status ? <><span aria-hidden="true">·</span><span>{item.status.replaceAll("_", " ")}</span></> : null}
                    </div>
                    <h2 className="mt-1 font-display text-xl text-fg sm:text-2xl">{item.title}</h2>
                    <p className="mt-2 whitespace-pre-line text-sm leading-6 text-muted">{item.summary}</p>
                    <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
                      <span>{sourceLabel(item.source)}</span>
                      <span>{item.epistemic_state.replaceAll("_", " ")}</span>
                      <time dateTime={item.updated_at || item.occurred_at || undefined}>{dateLabel(item.updated_at || item.occurred_at)}</time>
                      {item.location ? <span>{item.location}</span> : null}
                    </div>
                    {item.relations.some((relation) => !["entity", "event", "evidence", "relation"].includes(relation.entity_type)) ? (
                      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted">
                        <span>Connected to</span>
                        {item.relations.filter((relation) => !["entity", "event", "evidence", "relation"].includes(relation.entity_type)).map((relation) => (
                          <Link
                            key={`${relation.entity_type}:${relation.entity_id}:${relation.relation}`}
                            to="/feed"
                            search={{ entity_type: relation.entity_type, entity_id: relation.entity_id }}
                            className="text-cyan hover:underline"
                          >
                            {RELATION_LABELS[relation.relation] ?? "Related to"} · {titleByReference.get(`${relation.entity_type}:${relation.entity_id}`) ?? ENTITY_LABELS[relation.entity_type] ?? "Network record"}
                          </Link>
                        ))}
                      </div>
                    ) : null}
                    <Link
                      to="/feed"
                      search={{ entity_type: item.entity_type, entity_id: item.entity_id }}
                      className="mt-4 inline-flex items-center gap-1 text-xs text-muted hover:text-cyan"
                    >
                      Open network context <ArrowUpRight className="size-3.5" />
                    </Link>
                    {item.kind === "signal" || item.kind === "question" || item.kind === "pattern" || item.kind === "belief" || item.kind === "opportunity" ? (
                      <Link to="/discoveries" className="ml-4 mt-4 inline-flex items-center gap-1 text-xs text-cyan hover:underline">
                        Review observations <ArrowUpRight className="size-3.5" />
                      </Link>
                    ) : null}
                    {item.kind === "capability" || item.kind === "actor" ? (
                      <Link
                        to="/providers"
                        search={relatedProviderId ? { provider: relatedProviderId } : {}}
                        className="ml-4 mt-4 inline-flex items-center gap-1 text-xs text-cyan hover:underline"
                      >
                        Explore providers <ArrowUpRight className="size-3.5" />
                      </Link>
                    ) : null}
                    {item.kind === "work_item" || item.kind === "connection" || item.kind === "outcome" ? (
                      <Link to="/domain" className="ml-4 mt-4 inline-flex items-center gap-1 text-xs text-cyan hover:underline">
                        Open work records <ArrowUpRight className="size-3.5" />
                      </Link>
                    ) : null}
                    {safeSourceUrl ? (
                      <a className="mt-4 inline-flex items-center gap-1 text-sm text-cyan hover:underline" href={safeSourceUrl} target="_blank" rel="noreferrer">
                        Open cited source <ArrowUpRight className="size-3.5" />
                      </a>
                    ) : null}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </Container>
    </main>
  );
}
