import { trustPoints } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export function TrustSection() {
  return (
    <section className="py-20 lg:py-24">
      <Container className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>Trust, without theatre</Eyebrow>
          <h2 className="font-display text-title tracking-tight text-fg">
            Serious about the
            <br />
            <span className="text-muted">work itself.</span>
          </h2>
        </div>
        <div className="border-t border-line">
          {trustPoints.map((point) => (
            <article
              key={point.number}
              className="grid grid-cols-[2.75rem_1fr] gap-4 border-b border-line py-6"
            >
              <span className="font-mono text-micro text-cyan">{point.number}</span>
              <div>
                <h3 className="font-display text-lg font-semibold tracking-tight text-fg">
                  {point.title}
                </h3>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
                  {point.body}
                </p>
              </div>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
