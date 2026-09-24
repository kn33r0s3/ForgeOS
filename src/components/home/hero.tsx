import { ArrowUpRight, ChevronRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-line">
      <div className="site-grid pointer-events-none absolute inset-0" aria-hidden="true" />
      <Container className="relative grid items-center gap-12 py-16 lg:grid-cols-2 lg:gap-16 lg:py-24">
        <div>
          <Eyebrow>
            <span className="size-1.5 rounded-full bg-cyan shadow-[0_0_0_4px_var(--color-cyan-dim)]" />
            Forge
          </Eyebrow>
          <h1 className="font-display text-display tracking-tight text-fg">
            One network
            <br />
            <span className="text-muted">for real work.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lede text-muted">
            Services are one path that is usable now. Work, offers, trades, evidence, and outcomes stay in the same world. Nepal is the first geography.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button asChild size="lg">
              <Link to="/providers">
                Find a service
                <ArrowUpRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link to="/services">
                Explore categories
                <ChevronRight />
              </Link>
            </Button>
          </div>
          <p className="mt-10 flex items-center gap-2 font-mono text-micro uppercase tracking-[0.14em] text-dim">
            <span className="size-1.5 rounded-full bg-cyan" />
            backend-backed listings · live service flow
          </p>
        </div>
        <div className="relative min-h-80 overflow-hidden rounded-xl border border-line bg-raised p-5 shadow-[var(--shadow-border)] sm:min-h-96 lg:min-h-[28rem]">
          <div className="hero-rings" aria-hidden="true" />
          <div className="relative z-10 flex items-center justify-between font-mono text-micro uppercase tracking-[0.12em] text-dim">
            <span>Nepal</span>
            <span className="text-amber">verified records only</span>
          </div>
          <div className="relative z-10 mx-auto mt-16 flex w-56 flex-col gap-2 rounded-lg bg-fg p-5 text-void shadow-[6px_8px_0_rgb(0_0_0_/_0.35)] sm:mt-20 sm:w-60">
            <span className="font-mono text-micro uppercase tracking-[0.14em] opacity-60">
              Need help?
            </span>
            <strong className="font-display text-lg font-semibold tracking-tight">
              Search → Verify → Book
            </strong>
            <span className="text-xs opacity-60">services are one path</span>
          </div>
          <div className="relative z-10 mt-16 hidden gap-2 sm:flex">
            <span className="rounded-sm border border-cyan/40 bg-void/90 px-2.5 py-1.5 font-mono text-micro uppercase tracking-[0.12em] text-muted">
              01 / Search
            </span>
            <span className="rounded-sm border border-line bg-void/90 px-2.5 py-1.5 font-mono text-micro uppercase tracking-[0.12em] text-muted">
              02 / Compare
            </span>
            <span className="rounded-sm border border-line bg-void/90 px-2.5 py-1.5 font-mono text-micro uppercase tracking-[0.12em] text-cyan">
              03 / Book
            </span>
          </div>
          <div className="relative z-10 mt-8 flex items-center gap-3 font-mono text-micro uppercase tracking-[0.12em] text-dim">
            <span>Local</span>
            <span className="h-px flex-1 bg-line" />
            <span className="text-fg">trusted network</span>
          </div>
        </div>
      </Container>
    </section>
  );
}
