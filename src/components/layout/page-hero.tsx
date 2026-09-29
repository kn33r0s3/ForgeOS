import type { ReactNode } from "react";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";
import { cn } from "@/lib/utils";

export function PageHero({
  eyebrow,
  title,
  lede,
  children,
  className,
}: {
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "relative isolate overflow-hidden border-b border-line py-16 sm:py-20 lg:py-24",
        className,
      )}
    >
      <div className="hero-glow -z-10" aria-hidden="true" />
      <div className="hero-grain -z-10" aria-hidden="true" />
      <Container className="fade-in max-w-3xl">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="font-display text-display tracking-tight text-ink">{title}</h1>
        {lede ? (
          <p className="mt-6 max-w-xl text-lede text-muted">{lede}</p>
        ) : null}
        {children}
      </Container>
    </section>
  );
}
