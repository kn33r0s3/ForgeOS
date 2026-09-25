import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, CircleHelp, Compass, Lightbulb, Link2, Radio, Users, Wrench } from "lucide-react";
import { Container } from "@/components/layout/container";
import { loadPublicFeed, type PublicFeedItem } from "@/lib/content";

export const Route = createFileRoute("/feed")({
  validateSearch: (search: Record<string, unknown>) => ({
    entity_type: typeof search.entity_type === "string" ? search.entity_type : undefined,
    entity_id: Number.isInteger(Number(search.entity_id)) && Number(search.entity_id) > 0
      ? Number(search.entity_id)
      : undefined,
  }),
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

function dateLabel(value?: string | null) {
  if (!value) return "Time unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unknown";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function NetworkFeedPage() {
  const { entity_type: entityType, entity_id: entityId } = Route.useSearch();
  const [items, setItems] = useState<PublicFeedItem[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["value"]>("all");
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    let active = true;
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
  }, [entityId, entityType]);

  const visible = useMemo(
    () => filter === "all" ? items : items.filter((item) => item.kind === filter),
    [filter, items],
  );

  return (
    <main className="min-h-full py-10 sm:py-14">
      <Container className="max-w-5xl">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
          <div>
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Forge Network</p>
            <h1 className="mt-2 font-display text-4xl tracking-tight text-fg sm:text-5xl">Signals, needs, and useful connections</h1>
            <p className="mt-4 max-w-2xl text-lede text-muted">
              A live view assembled from Forge’s evidence, research, work, capability, and network records. Each entry keeps its source and uncertainty visible.
            </p>
            {entityType && entityId ? (
              <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-line bg-raised px-3 py-2 text-xs text-muted">
                Network context: {entityType.replaceAll("_", " ")} #{entityId}
                <Link to="/feed" search={{}} className="text-cyan hover:underline">Clear</Link>
              </p>
            ) : null}
          </div>
          <aside className="rounded-2xl border border-line bg-raised p-4">
            <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">How to read this feed</p>
            <p className="mt-2 text-sm text-muted">Items are shown by most recent recorded change. “Hypothesis”, “possible”, and “unknown” are deliberate states. Forge does not publish a popularity or trust score.</p>
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
            <p className="mt-2 text-sm text-muted">The public API did not answer. No sample activity is shown in its place.</p>
          </div>
        ) : null}
        {state === "ready" && visible.length === 0 ? (
          <div className="mt-8 rounded-2xl border border-line bg-void p-6">
            <h2 className="font-display text-xl text-fg">{filter === "all" ? "No public network activity yet" : "No items in this part of the network yet"}</h2>
            <p className="mt-2 max-w-2xl text-sm text-muted">An empty feed is a valid state. New entries appear when real records pass their source, evidence, and visibility gates.</p>
          </div>
        ) : null}

        <div className="mt-5 space-y-3">
          {visible.map((item) => {
            const Icon = KIND_ICONS[item.kind] ?? Radio;
            const safeSourceUrl = item.source_url?.startsWith("https://") ? item.source_url : null;
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
                      <span>{item.source || "Source not recorded"}</span>
                      <span>{item.epistemic_state.replaceAll("_", " ")}</span>
                      <time dateTime={item.updated_at || item.occurred_at || undefined}>{dateLabel(item.updated_at || item.occurred_at)}</time>
                      {item.location ? <span>{item.location}</span> : null}
                    </div>
                    {item.relations.length > 0 ? (
                      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted">
                        <span>Connected to</span>
                        {item.relations.map((relation) => (
                          <Link
                            key={`${relation.entity_type}:${relation.entity_id}:${relation.relation}`}
                            to="/feed"
                            search={{ entity_type: relation.entity_type, entity_id: relation.entity_id }}
                            className="text-cyan hover:underline"
                          >
                            {relation.entity_type.replaceAll("_", " ")} #{relation.entity_id} · {relation.relation.replaceAll("_", " ")}
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
