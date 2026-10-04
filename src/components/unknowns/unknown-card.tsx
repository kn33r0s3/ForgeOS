import { FlaskConical } from "lucide-react";
import {
  UNKNOWN_STATE_LABELS,
  type PublicUnknown,
} from "@/lib/content";

const STATE_STYLE: Record<string, string> = {
  UNKNOWN: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  BLOCKED_BY_MISSING_ACCESS: "border-red-500/30 bg-red-500/10 text-red-200",
  TESTED: "border-sky-500/30 bg-sky-500/10 text-sky-200",
  SUPPORTED: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  HYPOTHESIZED: "border-violet-500/30 bg-violet-500/10 text-violet-200",
  CONTRADICTED: "border-orange-500/30 bg-orange-500/10 text-orange-200",
};

/**
 * UnknownCard — renders one world unknown.
 * Used by /unknowns (Unknowns page) and the homepage Unknowns preview.
 * SAME component, SAME API data.
 */
export function UnknownCard({ unknown }: { unknown: PublicUnknown }) {
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-accent">{unknown.id}</span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${STATE_STYLE[unknown.state] ?? "border-line bg-background text-muted"}`}
          title="Engine state: what is actually known about this question"
        >
          {UNKNOWN_STATE_LABELS[unknown.state]}
        </span>
        <span
          className="rounded-full border border-line bg-background px-2 py-0.5 text-xs text-muted"
          title="No give-up evidence recorded — the tier is unearned, not low"
        >
          unscored
        </span>
      </div>
      <h3 className="mt-2 font-display text-base font-bold leading-6 text-ink">
        {unknown.question}
      </h3>
      {unknown.cheapest_test && (
        <p className="mt-3 text-sm leading-6 text-muted">
          <FlaskConical className="mr-1.5 inline size-4 text-accent" aria-hidden="true" />
          <strong className="text-ink">Cheapest test:</strong> {unknown.cheapest_test}
        </p>
      )}
      {unknown.stake && (
        <p className="mt-2 text-xs leading-5 text-dim">
          <strong>Stake:</strong> {unknown.stake}
        </p>
      )}
    </article>
  );
}
