import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Striped placeholder block. Decorative: screen readers get the parent's status. */
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
    <div
      className={cn(
        "card fade-in relative overflow-hidden bg-[linear-gradient(45deg,#4a4953_0%,#000_45%_100%)] px-6 py-8 text-center sm:px-10 sm:py-10",
        className,
      )}
    >
      <div className="relative mx-auto flex max-w-2xl flex-col items-center">
        {Icon ? (
          <span className="medallion mb-5" aria-hidden="true">
            <Icon className="size-7" strokeWidth={2.25} />
          </span>
        ) : null}
        <Heading className="text-2xl font-extrabold tracking-tight text-accent">{title}</Heading>
        {body ? <div className="mt-3 text-sm leading-6 text-muted">{body}</div> : null}
        {children ? (
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-3">{children}</div>
        ) : null}
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
        "fade-in rounded-card border-2 border-warning/70 bg-black p-5 shadow-md sm:p-6",
        className,
      )}
    >
      <p className="inline-flex items-center gap-2 rounded-[3px] bg-warning px-2 py-1 text-micro font-extrabold uppercase tracking-[0.14em] text-black">
        <span className="live-dot live-dot-warning" aria-hidden="true" /> Unavailable
      </p>
      <h2 className="mt-3 text-2xl font-extrabold tracking-tight text-ink">{title}</h2>
      {body ? <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{body}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="btn-secondary mt-4 inline-flex min-h-11 items-center gap-2 rounded-card border-2 border-black/70 bg-[#f5f1f1] px-4 text-sm font-extrabold text-black hover:border-accent focus-visible:border-accent"
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
      <div className="flex items-start justify-between gap-2">
        <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-wheat">{label}</p>
        {Icon ? (
          <span className="icon-chip size-8" aria-hidden="true">
            <Icon className="size-4" />
          </span>
        ) : null}
      </div>
      <span className="mt-2 block h-[3px] w-8 bg-accent" aria-hidden="true" />
      {loading ? (
        <Skeleton className="mt-4 h-8 w-14" />
      ) : (
        <p className="mt-3 text-4xl font-black leading-none tracking-tight tabular-nums text-ink">
          {value === null ? <span className="text-dim" title="Unavailable">—</span> : typeof value === "number" ? value.toLocaleString() : value}
        </p>
      )}
      {note ? <p className="mt-3 text-xs leading-5 text-muted">{note}</p> : null}
    </article>
  );
}
