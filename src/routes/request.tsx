import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { ProjectForm } from "@/components/pages/project-form";

export const Route = createFileRoute("/request")({
  component: RequestPage,
  head: () => ({ meta: [{ title: "Start a project — Sanip Ops" }] }),
});

const checks = [
  "A human review of every request",
  "Clear scope before any build",
  "No unsupported promises",
] as const;

function RequestPage() {
  return (
    <main className="py-16 sm:py-20 lg:py-24">
      <Container className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>Start a conversation</Eyebrow>
          <h1 className="font-display text-display tracking-tight text-fg">
            Bring us the
            <br />
            <span className="text-muted">business need.</span>
          </h1>
          <p className="mt-6 max-w-md text-lede text-muted">
            Tell us whether you are exploring a partnership, technology project,
            operational need, venture idea, or strategic inquiry. We’ll help shape
            the right next step.
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
        <ProjectForm />
      </Container>
    </main>
  );
}
