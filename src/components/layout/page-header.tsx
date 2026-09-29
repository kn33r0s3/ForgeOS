import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Container } from "./container";

/**
 * Standard page masthead: eyebrow, serif headline, lede, optional aside.
 * Sits on a soft glow band so every surface opens with the same hierarchy.
 */
export function PageHeader({
  eyebrow,
  title,
  lede,
  aside,
  children,
  className,
  containerClassName,
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  lede?: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
  className?: string;
  containerClassName?: string;
}) {
  return (
    <section className={cn("relative overflow-hidden border-b border-line", className)}>
      <div className="hero-glow" aria-hidden="true" />
      <div className="hero-grain" aria-hidden="true" />
      <Container className={cn("relative py-12 sm:py-16", containerClassName)}>
        <div className={cn("grid gap-8", aside && "lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-end")}>
          <div className="reveal">
            <p className="flex items-center gap-2 font-mono text-micro uppercase tracking-[0.14em] text-accent">
              <span aria-hidden="true" className="h-px w-6 bg-accent/70" />
              {eyebrow}
            </p>
            <h1 className="mt-4 max-w-3xl font-display text-[clamp(2.4rem,5.5vw,4.25rem)] leading-[1] tracking-tight text-ink">
              {title}
            </h1>
            {lede ? <p className="mt-5 max-w-2xl text-lede text-muted">{lede}</p> : null}
            {children}
          </div>
          {aside ? (
            <aside className="glass reveal p-5" style={{ "--i": 2 } as React.CSSProperties}>
              {aside}
            </aside>
          ) : null}
        </div>
      </Container>
    </section>
  );
}
