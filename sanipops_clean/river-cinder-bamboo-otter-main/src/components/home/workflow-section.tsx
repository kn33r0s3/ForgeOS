import { ArrowRight, Check } from "lucide-react";
import { processSteps } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { TextLink } from "@/components/layout/text-link";

export function WorkflowSection() {
  return (
    <section className="border-b border-line bg-raised py-20 lg:py-24">
      <Container>
        <div className="mb-12 flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <Eyebrow>How we operate</Eyebrow>
            <h2 className="font-display text-title tracking-tight text-fg">
              From unclear to
              <br />
              <span className="text-muted">operational.</span>
            </h2>
          </div>
          <TextLink to="/process">See the process</TextLink>
        </div>
        <div className="grid border-t border-line sm:grid-cols-2 lg:grid-cols-4">
          {processSteps.map((step, index) => (
            <article
              key={step.number}
              className="relative min-h-56 border-b border-line p-6 sm:[&:nth-child(odd)]:border-r lg:border-b-0 lg:border-r lg:last:border-r-0"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-micro text-cyan">{step.number}</span>
                <span className="text-dim">
                  {index < processSteps.length - 1 ? (
                    <ArrowRight className="size-4" />
                  ) : (
                    <Check className="size-4 text-cyan" />
                  )}
                </span>
              </div>
              <h3 className="mt-16 font-display text-2xl font-semibold tracking-tight text-fg">
                {step.title}
              </h3>
              <p className="mt-3 max-w-[15rem] text-sm leading-relaxed text-muted">
                {step.body}
              </p>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
