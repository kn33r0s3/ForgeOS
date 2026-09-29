import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { DemandIntakeForm } from "@/components/pages/demand-intake-form";

export const Route = createFileRoute("/request")({
  component: RequestPage,
  head: () => ({ meta: [{ title: "Start a project — Hami" }] }),
});

const checks = [
  "Recorded as observed, possible demand",
  "No automatic outreach or action",
  "No customer or revenue claim from a submission",
] as const;

function RequestPage() {
  return (
    <main className="relative isolate overflow-hidden py-16 sm:py-20 lg:py-24">
      <div className="hero-glow -z-10" aria-hidden="true" />
      <Container className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>Start a conversation</Eyebrow>
          <h1 className="font-display text-display tracking-tight text-fg">
            Bring us the
            <br />
            <span className="text-muted">business need.</span>
          </h1>
          <p className="mt-6 max-w-md text-lede text-muted">
            Describe a need or problem for Hami to understand. A submission is
            evidence of a request only; it is not qualification, a commercial
            offer, or a promise of follow-up.
          </p>
          <ul className="mt-10 grid gap-3 text-sm text-muted">
            {checks.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <Check className="size-4 text-cyan" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <DemandIntakeForm />
      </Container>
    </main>
  );
}
