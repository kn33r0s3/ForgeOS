import { createFileRoute } from "@tanstack/react-router";
import { processSteps } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { PageHero } from "@/components/layout/page-hero";
import { CtaBand } from "@/components/layout/cta-band";

export const Route = createFileRoute("/process")({
  component: ProcessPage,
  head: () => ({ meta: [{ title: "How we work — Hami" }] }),
});

function ProcessPage() {
  return (
    <main>
      <PageHero
        eyebrow="How we work"
        title={
          <>
            A clear path through
            <br />
            <span className="text-muted">the unclear part.</span>
          </>
        }
        lede="Understand → Build → Operate → Improve. A public process for shaping useful work without pretending every brief is the same."
      />
      <section className="py-16 sm:py-20">
        <Container className="max-w-3xl">
          <div className="border-t border-line">
            {processSteps.map((step) => (
              <article
                key={step.number}
                className="grid grid-cols-[2.75rem_1fr] gap-5 border-b border-line py-7"
              >
                <span className="font-mono text-micro text-cyan">{step.number}</span>
                <div>
                  <h2 className="font-display text-xl font-semibold tracking-tight text-fg">
                    {step.title}
                  </h2>
                  <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted">
                    {step.body}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </Container>
      </section>
      <CtaBand
        eyebrow="Put the process to work"
        title={
          <>
            Start with a real need.
            <br />
            <span className="text-muted">Build from what is known.</span>
          </>
        }
        body="Hami's current service catalogue is the practical entry point for technical and operational work. Online inquiries remain closed; this route describes scope, not a promise of acceptance."
        to="/services"
        actionLabel="Explore Hami services"
      />
      <HamiPathways current="process" />
    </main>
  );
}
