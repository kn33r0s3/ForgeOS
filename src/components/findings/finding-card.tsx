import { ArrowUpRight, Clock3 } from "lucide-react";
import type { CSSProperties } from "react";
import type { PublicDiscovery } from "@/lib/content";

/**
 * FindingCard — renders one engine evidence record.
 * Used by /discoveries (Findings page) and the homepage Findings preview.
 * SAME component, SAME API data.
 */
export function FindingCard({
  finding,
  index = 0,
}: {
  finding: PublicDiscovery;
  index?: number;
}) {
  const stale = finding.freshness === "stale";
  const relevanceLabels: Record<string, string> = {
    background_observation: "Background",
    unqualified_lead: "Research lead",
    relevant_to_unknown: "Relevant unknown",
    validated_finding: "Validated",
  };
  const relevanceLabel = finding.relevance_status ? relevanceLabels[finding.relevance_status] : null;
  return (
    <li
      className="card card-interactive reveal flex min-w-0 flex-col p-5"
      style={{ "--i": Math.min(index, 8) } as CSSProperties}
    >
      <article className="flex flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2">
          <span className="status-pill status-pill-accent max-w-full break-all">
            {finding.source}
          </span>
          <span className="status-pill status-pill-neutral max-w-full break-all">
            {finding.epistemic_state}
          </span>
          {relevanceLabel && (
            <span className="status-pill status-pill-neutral max-w-full break-all" title="Relevance classification">
              {relevanceLabel}
            </span>
          )}
          <span className={`status-pill ${stale ? "status-pill-warning" : "status-pill-success"}`}>
            <Clock3 className="size-3" aria-hidden="true" /> {finding.freshness || "unknown"}
          </span>
        </div>
        <h3 className="mt-3 break-words font-display text-2xl leading-tight tracking-tight text-ink">
          {finding.title || "Untitled observation"}
        </h3>
        <p className="mt-2 min-w-0 flex-1 break-words text-sm leading-6 text-muted">
          {finding.excerpt}
        </p>
        {/* Evidence trace: what this record establishes and what it doesn't */}
        <div className="mt-3 space-y-1 border-t border-line pt-3 text-xs leading-5">
          <div className="flex gap-2">
            <span className="shrink-0 font-mono font-bold uppercase tracking-wider text-dim">Linked unknown:</span>
            <span className="text-muted">
              {finding.linked_unknown ? finding.linked_unknown : <em>Not established — no unknown linked to this record.</em>}
            </span>
          </div>
          <div className="flex gap-2">
            <span className="shrink-0 font-mono font-bold uppercase tracking-wider text-dim">Next test:</span>
            <span className="text-muted">
              {finding.next_test ? finding.next_test : <em>Not recorded — no test proposed for this record.</em>}
            </span>
          </div>
        </div>
        {finding.canonical_url ? (
          <a
            href={finding.canonical_url}
            className="link-arrow mt-4 inline-flex min-h-10 min-w-0 max-w-full items-center gap-1 border-t border-line pt-3 text-sm text-accent"
          >
            <span className="min-w-0 break-all">{finding.canonical_url}</span>
            <ArrowUpRight className="size-4 shrink-0" aria-hidden="true" />
          </a>
        ) : null}
      </article>
    </li>
  );
}
