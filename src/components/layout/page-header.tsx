import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Container } from "./container";

/**
 * Standard page masthead: section tag, blackletter headline with an orange
 * cut rule, lede, optional aside panel. Sits on the grey-to-black 45deg
 * sheen and closes with a pinstripe rule.
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
    <section className={cn("relative isolate overflow-hidden", className)}>
      <div className="hero-glow -z-10" aria-hidden="true" />
      <div className="hero-grain -z-10" aria-hidden="true" />
      <Container className={cn("relative py-12 sm:py-16", containerClassName)}>
        <div className={cn("grid gap-8", aside && "lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-end")}>
          <div className="reveal">
            <p className="tag">{eyebrow}</p>
            <h1 className="mt-5 max-w-3xl font-gothic text-[clamp(2.5rem,6vw,4.6rem)] leading-[1.02] text-ink [text-shadow:3px_3px_0_#000]">
              {title}
            </h1>
            <span className="cut-rule mt-5" aria-hidden="true" />
            {lede ? <p className="mt-5 max-w-2xl text-lede text-muted">{lede}</p> : null}
            {children}
          </div>
          {aside ? (
            <aside
              className="glass reveal border-t-4 border-t-accent p-5"
              style={{ "--i": 2 } as React.CSSProperties}
            >
              {aside}
            </aside>
          ) : null}
        </div>
      </Container>
      <div className="band-rule" aria-hidden="true" />
    </section>
  );
}
