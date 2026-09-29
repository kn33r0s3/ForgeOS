import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Shimmering placeholder block. Decorative: screen readers get the parent's status. */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn("skeleton block h-4", className)} />;
}

/** A labelled loading region made of skeleton cards. */
export function SkeletonCards({
  count = 3,
  label = "Loading",
  className,
  variant = "row",
}: {
  count?: number;
  label?: string;
  className?: string;
  variant?: "row" | "tile";
}) {
  return (
    <div role="status" aria-live="polite" className={className}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, index) =>
        variant === "tile" ? (
          <div key={index} className="card p-4" aria-hidden="true">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-4 h-7 w-12" />
            <Skeleton className="mt-3 h-3 w-32" />
          </div>
        ) : (
          <div key={index} className="card flex gap-4 p-5" aria-hidden="true">
            <Skeleton className="size-10 shrink-0 rounded-card" />
            <div className="min-w-0 flex-1">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="mt-3 h-5 w-3/4" />
              <Skeleton className="mt-3 h-3 w-full" />
              <Skeleton className="mt-2 h-3 w-5/6" />
            </div>
          </div>
        ),
      )}
    </div>
  );
}

/**
 * Honest empty state: says what is missing, why, and where to go next.
 * Never implies activity that is not recorded.
 */
export function EmptyState({
  icon: Icon,
  title,
  body,
  children,
  className,
  headingLevel = "h2",
}: {
  icon?: LucideIcon;
  title: ReactNode;
  body?: ReactNode;
  children?: ReactNode;
  className?: string;
  headingLevel?: "h2" | "h3";
}) {
  const Heading = headingLevel;
  return (
    <div className={cn("card fade-in relative overflow-hidden p-6 sm:p-8", className)}>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-16 size-48 rounded-full bg-accent/10 blur-3xl"
      />
      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start">
        {Icon ? (
          <span className="icon-chip" aria-hidden="true">
            <Icon className="size-4" />
          </span>
        ) : null}
        <div className="min-w-0">
          <Heading className="font-display text-2xl tracking-tight text-ink">{title}</Heading>
          {body ? <div className="mt-2 max-w-2xl text-sm leading-6 text-muted">{body}</div> : null}
          {children ? <div className="mt-5 flex flex-wrap items-center gap-3">{children}</div> : null}
        </div>
      </div>
    </div>
  );
}

/** Data could not be loaded. Distinct from "empty": nothing is inferred. */
export function UnavailableState({
  title,
  body,
  onRetry,
  className,
}: {
  title: ReactNode;
  body?: ReactNode;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "fade-in rounded-card border border-warning/35 bg-warning/5 p-5 sm:p-6",
        className,
      )}
    >
      <p className="flex items-center gap-2 font-mono text-micro uppercase tracking-[0.14em] text-warning">
        <span className="live-dot live-dot-warning" aria-hidden="true" /> Unavailable
      </p>
      <h2 className="mt-3 font-display text-2xl tracking-tight text-ink">{title}</h2>
      {body ? <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{body}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-card border border-line bg-card px-4 text-sm font-semibold text-ink transition-colors hover:border-accent/60"
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          Retry
        </button>
      ) : null}
    </div>
  );
}

/** Compact metric tile; `null` renders as unknown, never as zero. */
export function MetricTile({
  label,
  value,
  note,
  loading = false,
  icon: Icon,
  tone = "default",
  index = 0,
  className,
}: {
  label: string;
  value: number | string | null;
  note?: string;
  loading?: boolean;
  icon?: LucideIcon;
  tone?: "default" | "accent";
  index?: number;
  className?: string;
}) {
  return (
    <article
      className={cn("card card-interactive reveal p-4 sm:p-5", tone === "accent" && "card-accent", className)}
      style={{ "--i": index } as React.CSSProperties}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-micro uppercase tracking-[0.12em] text-dim">{label}</p>
        {Icon ? <Icon className="size-4 text-accent/80" aria-hidden="true" /> : null}
      </div>
      {loading ? (
        <Skeleton className="mt-4 h-8 w-14" />
      ) : (
        <p className="mt-3 font-display text-4xl leading-none tracking-tight tabular-nums text-ink">
          {value === null ? <span className="text-dim" title="Unavailable">—</span> : typeof value === "number" ? value.toLocaleString() : value}
        </p>
      )}
      {note ? <p className="mt-3 text-xs leading-5 text-muted">{note}</p> : null}
    </article>
  );
}
