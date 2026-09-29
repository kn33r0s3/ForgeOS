import type { ReactNode } from "react";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";
import { cn } from "@/lib/utils";

/** Marketing-page masthead: centred, blackletter title on the 45deg sheen. */
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
    <section className={cn("relative isolate overflow-hidden", className)}>
      <div className="hero-glow -z-10" aria-hidden="true" />
      <div className="hero-grain -z-10" aria-hidden="true" />
      <Container className="reveal flex max-w-3xl flex-col items-center py-16 text-center sm:py-20 lg:py-24">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="font-gothic text-display text-ink [text-shadow:3px_3px_0_#000]">{title}</h1>
        <span className="cut-rule mt-6" aria-hidden="true" />
        {lede ? <p className="mt-6 max-w-xl text-lede text-muted">{lede}</p> : null}
        {children}
      </Container>
      <div className="band-rule" aria-hidden="true" />
    </section>
  );
}
