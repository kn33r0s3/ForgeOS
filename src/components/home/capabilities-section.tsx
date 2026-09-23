import { capabilities } from "@/lib/content";
import { cn } from "@/lib/utils";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export function CapabilitiesSection() {
  return (
    <section className="border-b border-line py-20 lg:py-24">
      <Container className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>Capabilities</Eyebrow>
          <h2 className="font-display text-title tracking-tight text-fg">
            Commercial work,
            <br />
            <span className="text-muted">labelled as such.</span>
          </h2>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-muted">
            Client-facing work is commercial. Internal research is a prototype.
            The distinction is kept visible so nothing is sold that is not ready.
          </p>
          <div className="mt-8 flex max-w-md gap-3 border-l-2 border-cyan pl-4">
            <span className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">
              Honest status
            </span>
            <p className="text-xs leading-relaxed text-muted">
              <strong className="font-medium text-fg">Prototype ≠ product. </strong>
              Media and data processing remains internal R&D. It is not a
              commercial offer.
            </p>
          </div>
        </div>
        <div className="border-t border-line">
          {capabilities.map((item, index) => (
            <div
              key={item.name}
              className="grid grid-cols-[2.5rem_1fr_auto] items-center gap-3 border-b border-line py-4"
            >
              <span className="font-mono text-micro text-cyan">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <strong className="block font-display text-base font-semibold tracking-tight text-fg">
                  {item.name}
                </strong>
                <p className="mt-1 hidden text-xs text-muted sm:block">{item.note}</p>
              </div>
              <span
                className={cn(
                  "font-mono text-micro uppercase tracking-[0.12em]",
                  item.kind === "prototype" ? "text-amber" : "text-dim",
                )}
              >
                {item.kind}
              </span>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
