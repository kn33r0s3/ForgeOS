import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export const Route = createFileRoute("/climb")({
  component: ClimbPage,
  head: () => ({
    meta: [
      { title: "The climb — Hami" },
      {
        name: "description",
        content:
          "The big aim and the small aim are the same aim at different scales. Each step is earned by the one before it.",
      },
    ],
  }),
});

const STEPS = [
  {
    n: 1,
    title: "One seller, one week",
    body: "Experiment 1: can faster replies recover real sales for one seller? No seller has agreed yet — it remains proposed.",
    link: { to: "/prototype/inbox" as const, label: "Try the free inbox tool" },
    earned: true,
  },
  { n: 2, title: "Ten sellers", body: "", earned: false },
  { n: 3, title: "A repeatable week", body: "", earned: false },
  { n: 4, title: "A local playbook", body: "", earned: false },
  { n: 5, title: "Everywhere", body: "", earned: false },
] as const;

function ClimbPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · the climb"
        title="Very big, very small."
        lede="The big aim and the small aim are the same aim at different scales. Each step is earned by the one before it — nothing is claimed in advance."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <div className="mt-4">
          {STEPS.map((s) => (
            <div
              key={s.n}
              className="flex gap-5 border-t border-line py-6"
              style={{ opacity: s.earned ? 1 : 0.45 }}
            >
              <span
                className="font-mono text-sm font-bold"
                style={{ color: s.earned ? "var(--primary)" : "var(--muted)" }}
              >
                {String(s.n).padStart(2, "0")}
              </span>
              <div>
                <h2 className="font-display text-xl font-bold text-ink">{s.title}</h2>
                {s.earned ? (
                  <>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{s.body}</p>
                    {"link" in s && s.link && (
                      <Link
                        to={s.link.to}
                        className="mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
                      >
                        {s.link.label} <ArrowRight className="size-4" aria-hidden="true" />
                      </Link>
                    )}
                  </>
                ) : (
                  <p className="mt-2 text-sm italic text-muted">when earned</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </Container>
    </main>
  );
}
