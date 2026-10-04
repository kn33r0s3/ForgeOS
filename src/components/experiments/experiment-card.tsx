import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface Experiment {
  id: string;
  title: string;
  status: "proposed" | "running" | "completed";
  description: string;
  log: Array<{ date: string; entry: string }>;
  toolLink?: { to: string; label: string };
}

/**
 * ExperimentCard — renders one experiment.
 * Used by /experiments (Experiments page) and the homepage Experiments preview.
 * SAME component. Data is static until a real experiment log API exists.
 * Only real log entries appear — no invented outcomes.
 */
export function ExperimentCard({ experiment }: { experiment: Experiment }) {
  return (
    <article className="card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-accent">{experiment.id}</span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
            experiment.status === "running"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
              : experiment.status === "completed"
                ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
                : "border-amber-500/30 bg-amber-500/10 text-amber-200"
          }`}
        >
          {experiment.status}
        </span>
      </div>
      <h3 className="mt-2 font-display text-base font-bold leading-6 text-ink">
        {experiment.title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-muted">{experiment.description}</p>
      {experiment.log.length > 0 ? (
        <ul className="mt-3 space-y-2 border-t border-line pt-3">
          {experiment.log.map((entry, i) => (
            <li key={i} className="text-xs leading-5">
              <span className="font-mono text-muted">{entry.date}</span>{" "}
              <span className="text-ink">{entry.entry}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs italic text-muted">
          No log entries yet — the experiment has not started.
        </p>
      )}
      {experiment.toolLink && (
        <Button asChild variant="secondary" size="sm" className="mt-4">
          <Link to={experiment.toolLink.to}>
            {experiment.toolLink.label} <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </Button>
      )}
    </article>
  );
}

/** The real experiment list. Only real experiments with real logs. */
export const EXPERIMENTS: Experiment[] = [
  {
    id: "EXP-1",
    title: "Slow-reply recovery",
    status: "proposed",
    description:
      "Can faster replies recover real sales for one seller? One seller, one week. No seller has agreed yet — it remains proposed.",
    log: [],
    toolLink: { to: "/prototype/inbox", label: "Try the free inbox tool" },
  },
];
