import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Circle,
  CircleCheck,
  Clock,
  Compass,
  ExternalLink,
  Lock,
  MapPin,
  Package,
  Radio,
  ShieldCheck,
  Target,
  Wrench,
} from "lucide-react";
import type { PublicFeedItem } from "@/lib/content";
import type { PossibilityPath, RelevantItem, Stage } from "@/lib/system/paths";
import { GOAL_LABELS, TIME_LABELS, type SystemState } from "@/lib/system/state";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */

function Tag({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "accent" | "warn" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-[3px] border px-1.5 py-0.5 font-mono text-[0.68rem] font-bold uppercase tracking-[0.08em]",
        tone === "accent" && "border-accent/60 text-accent",
        tone === "warn" && "border-warning/60 text-warning",
        tone === "neutral" && "border-line-strong text-dim",
      )}
    >
      {children}
    </span>
  );
}

export function PanelTitle({ icon: Icon, kicker, title }: { icon: typeof Radio; kicker: string; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-card border-2 border-accent/70 bg-black text-accent">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div>
        <p className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.16em] text-accent">{kicker}</p>
        <h2 className="text-lg font-extrabold leading-tight tracking-tight text-ink">{title}</h2>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Situation: the person's gear                                        */
/* ------------------------------------------------------------------ */

function GearRow({ icon: Icon, label, children }: { icon: typeof Radio; label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[1.75rem_1fr] gap-3 border-t border-line py-3 first:border-t-0">
      <Icon className="mt-0.5 size-4 text-accent" aria-hidden="true" />
      <div className="min-w-0">
        <p className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.12em] text-dim">{label}</p>
        <div className="mt-1 text-sm text-ink">{children}</div>
      </div>
    </div>
  );
}

function Missing({ children }: { children: React.ReactNode }) {
  return <span className="text-dim italic">{children}</span>;
}

export function SituationPanel({ state }: { state: SystemState }) {
  return (
    <section className="card p-5" aria-labelledby="situation-title">
      <div className="flex items-start justify-between gap-3">
        <PanelTitle icon={Target} kicker="Your System" title="Situation" />
        <Link to="/system" className="text-sm font-bold text-accent hover:underline" id="situation-title-edit">
          Edit
        </Link>
      </div>
      <span id="situation-title" className="sr-only">
        Your situation
      </span>
      <div className="mt-4">
        <GearRow icon={MapPin} label="Location">
          {state.location ? state.location.value : <Missing>Not set</Missing>}
        </GearRow>
        <GearRow icon={Clock} label="Weekly time">
          {state.time ? TIME_LABELS[state.time.value] : <Missing>Not set</Missing>}
        </GearRow>
        <GearRow icon={Target} label="Moving toward">
          {state.goals.length ? (
            <span className="flex flex-wrap gap-1.5">
              {state.goals.map((g) => (
                <span key={g.value} className="rounded-[3px] bg-secondary px-2 py-0.5 text-[0.8rem] font-bold">
                  {GOAL_LABELS[g.value]}
                </span>
              ))}
            </span>
          ) : (
            <Missing>No goal yet</Missing>
          )}
        </GearRow>
        <GearRow icon={Wrench} label="Capabilities">
          {state.capabilities.length ? state.capabilities.map((c) => c.value).join(" · ") : <Missing>None added</Missing>}
        </GearRow>
        <GearRow icon={Package} label="Resources">
          {state.resources.length ? state.resources.map((r) => r.value).join(" · ") : <Missing>None added</Missing>}
        </GearRow>
      </div>
      <p className="mt-3 flex items-center gap-2 border-t border-line pt-3 text-xs text-dim">
        <Lock className="size-3.5" aria-hidden="true" /> Stated by you · stored on this device only
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Progression                                                         */
/* ------------------------------------------------------------------ */

export function ProgressPanel({ stages }: { stages: Stage[] }) {
  const reached = stages.filter((s) => s.reached).length;
  return (
    <section className="card p-5" aria-label="Progress">
      <PanelTitle icon={Compass} kicker="Real progress" title={`Stage ${reached} of ${stages.length}`} />
      <ol className="mt-4 grid gap-3">
        {stages.map((s) => (
          <li key={s.id} className="grid grid-cols-[1.5rem_1fr] gap-3">
            {s.reached ? (
              <CircleCheck className="mt-0.5 size-5 text-success" aria-label="Reached" />
            ) : s.evidenceGated ? (
              <ShieldCheck className="mt-0.5 size-5 text-dim" aria-label="Requires verified evidence" />
            ) : (
              <Circle className="mt-0.5 size-5 text-line-strong" aria-label="Not reached" />
            )}
            <div>
              <p className={cn("text-sm font-extrabold", s.reached ? "text-ink" : "text-muted")}>{s.label}</p>
              <p className="text-xs leading-5 text-dim">{s.reached ? s.meaning : s.requirement}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-4 border-t border-line pt-3 text-xs leading-5 text-dim">
        Stages reflect real state, not points. Outcomes count only with verified evidence.
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Possibility paths                                                   */
/* ------------------------------------------------------------------ */

const KIND_LABEL: Record<PossibilityPath["kind"], string> = {
  capability: "Capability",
  resource: "Unused capacity",
  growth: "Growth",
  service: "Service",
  context: "Context",
};

export function PathCard({ path }: { path: PossibilityPath }) {
  return (
    <article className="card card-interactive flex flex-col p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Tag tone="accent">{KIND_LABEL[path.kind]}</Tag>
        <Tag>Possible</Tag>
      </div>
      <h3 className="mt-3 text-lg font-extrabold leading-snug tracking-tight text-ink">{path.title}</h3>
      <p className="mt-2 text-sm leading-6 text-muted">{path.why}</p>
      <div className="mt-3">
        <p className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.12em] text-warning">Still unknown</p>
        <ul className="mt-1 list-disc pl-5 text-sm leading-6 text-muted marker:text-warning/70">
          {path.unknowns.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      </div>
      <div className="mt-auto pt-4">
        <p className="rounded-card border-l-2 border-accent bg-black/40 px-3 py-2 text-sm leading-6 text-ink">
          <span className="font-extrabold text-accent">Next step · </span>
          {path.nextStep}
        </p>
        {path.href ? (
          <Link
            to={path.href}
            className="link-arrow mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
          >
            Take this step <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        ) : null}
        <p className="mt-2 text-[0.72rem] text-dim">From: {path.from.join(" · ")}</p>
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* World-change stream (projection of the real public feed)            */
/* ------------------------------------------------------------------ */

const FEED_KIND: Record<string, string> = {
  signal: "Observed",
  question: "Researching",
  pattern: "Pattern",
  belief: "Hypothesis",
  opportunity: "Opportunity hypothesis",
  capability: "Capability available",
  work_item: "Need",
  connection: "Possible connection",
  outcome: "Recorded outcome",
  actor: "Provider",
};

const EPISTEMIC: Record<string, { label: string; tone: "neutral" | "accent" | "warn" }> = {
  supported: { label: "Supported", tone: "accent" },
  observed: { label: "Observed", tone: "neutral" },
  contested: { label: "Contested", tone: "warn" },
  inference: { label: "Unverified", tone: "warn" },
  inferred_pattern: { label: "Unverified", tone: "warn" },
};

export function relativeTime(value?: string | null, now = Date.now()): string {
  if (!value) return "time unknown";
  const t = new Date(value.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`).getTime();
  if (Number.isNaN(t)) return "time unknown";
  const mins = Math.round((now - t) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function ChangeItem({ item, shared }: { item: PublicFeedItem; shared?: string[] }) {
  const ep = EPISTEMIC[item.epistemic_state] ?? { label: item.epistemic_state, tone: "neutral" as const };
  return (
    <li className="grid grid-cols-[0.75rem_1fr] gap-3 border-t border-line py-4 first:border-t-0">
      <span className="mt-1.5 size-2.5 rounded-[2px] bg-accent/80" aria-hidden="true" />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Tag>{FEED_KIND[item.kind] ?? item.kind}</Tag>
          <Tag tone={ep.tone}>{ep.label}</Tag>
          <span className="font-mono text-[0.7rem] text-dim">{relativeTime(item.updated_at ?? item.occurred_at)}</span>
        </div>
        <p className="mt-2 line-clamp-2 text-sm font-bold leading-6 text-ink">{item.title}</p>
        {shared?.length ? (
          <p className="mt-1 text-xs text-accent">Relates to what you told Hami: {shared.join(", ")}</p>
        ) : null}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs text-dim">
          {item.source ? <span>Source: {item.source}</span> : null}
          {item.source_url ? (
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              Open source <ExternalLink className="size-3" aria-hidden="true" />
            </a>
          ) : null}
        </div>
      </div>
    </li>
  );
}

export function WorldStream({
  items,
  relevant,
  loading,
  unavailable,
}: {
  items: PublicFeedItem[] | null;
  relevant: RelevantItem[];
  loading: boolean;
  unavailable: boolean;
}) {
  const relevantIds = new Set(relevant.map((r) => r.item.id));
  const rest = (items ?? []).filter((i) => !relevantIds.has(i.id)).slice(0, Math.max(0, 6 - relevant.length));
  return (
    <section className="card p-5" aria-label="What changed">
      <div className="flex items-start justify-between gap-3">
        <PanelTitle icon={Radio} kicker="Live world state" title="What changed" />
        <Link to="/feed" className="text-sm font-bold text-accent hover:underline">
          Full stream
        </Link>
      </div>
      {loading ? (
        <p className="mt-5 text-sm text-dim" role="status">
          Reading the latest world state…
        </p>
      ) : unavailable ? (
        <p className="mt-5 text-sm text-warning" role="alert">
          The world-state service is unreachable right now. Nothing is shown rather than guessed.
        </p>
      ) : !items?.length ? (
        <p className="mt-5 text-sm text-muted">
          Nothing has been recorded publicly yet. Items appear here only once they are sourced.
        </p>
      ) : (
        <ul className="mt-3">
          {relevant.slice(0, 6).map((r) => (
            <ChangeItem key={r.item.id} item={r.item} shared={r.shared} />
          ))}
          {rest.map((item) => (
            <ChangeItem key={item.id} item={item} />
          ))}
        </ul>
      )}
      <p className="mt-2 border-t border-line pt-3 text-xs leading-5 text-dim">
        Every item carries its source and truth label. Hypotheses are marked unverified.
      </p>
    </section>
  );
}
