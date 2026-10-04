import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ExperimentCard, EXPERIMENTS } from "@/components/experiments/experiment-card";

export const Route = createFileRoute("/experiments")({
  component: ExperimentsPage,
  head: () => ({
    meta: [
      { title: "Experiments — Hami" },
      {
        name: "description",
        content:
          "What Hami is trying and what happened. Real log only — no invented outcomes.",
      },
    ],
  }),
});

function ExperimentsPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · experiments"
        title="Experiments"
        lede="What we are trying and what happened. Only real log entries appear — no invented outcomes, no projected results."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        {EXPERIMENTS.length === 0 ? (
          <div className="card p-6">
            <p className="font-bold text-ink">No experiments yet.</p>
            <p className="mt-1 text-sm text-muted">
              When an experiment starts, it appears here with its real log.
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {EXPERIMENTS.map((exp) => (
              <ExperimentCard key={exp.id} experiment={exp} />
            ))}
          </div>
        )}
      </Container>
    </main>
  );
}
