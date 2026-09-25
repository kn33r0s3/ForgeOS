import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export function ForgeOSSection() {
  return (
    <section className="border-b border-line py-20 lg:py-24">
      <Container className="grid gap-10 rounded-xl border border-line bg-surface p-6 sm:p-10 lg:grid-cols-[auto_1fr] lg:gap-16 lg:p-14">
        <div className="font-display text-6xl font-semibold leading-none tracking-tighter text-fg sm:text-7xl">
          F<span className="text-3xl text-muted sm:text-4xl">OS</span>
        </div>
        <div>
          <Eyebrow tone="amber">Long-term internal engine</Eyebrow>
          <h2 className="font-display text-title tracking-tight text-fg">
            ForgeOS is how
            <br />
            <span className="text-muted">the record stays current.</span>
          </h2>
          <p className="mt-5 max-w-xl text-lede text-muted">
            ForgeOS is the internal, local-first operating engine behind the
            longer-term Forge vision: a way to connect evidence, decisions,
            actions, and outcomes without losing the human context.
          </p>
          <p className="mt-6 max-w-xl border-t border-line pt-5 text-xs leading-relaxed text-dim">
            This website reads the public Forge API. An empty list means that
            record is not stored. Planned capabilities are not presented as
            already shipped, and Forge is not offered for sale.
          </p>
        </div>
      </Container>
    </section>
  );
}
