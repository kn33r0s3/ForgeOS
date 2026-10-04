import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/about")({
  component: AboutPage,
  head: () => ({
    meta: [
      { title: "About — Hami" },
      {
        name: "description",
        content:
          "The reality loop, the six primitives, evidence and authorization rules, and the climb.",
      },
    ],
  }),
});

const PRIMITIVES = [
  { name: "Entity", def: "An identifiable thing in the world." },
  { name: "Relation", def: "A typed connection between things." },
  { name: "Event", def: "Something observed or changed." },
  { name: "Evidence", def: "The sourced basis for a claim." },
  { name: "Capability", def: "What can actually be done." },
  { name: "Action", def: "An operation within authorization." },
] as const;

const RULES = [
  {
    title: "Evidence before claims",
    body: "Nothing is claimed without sourced evidence. ESTIMATED ≠ ACTUAL, REQUESTED ≠ BOOKED, TEST ≠ REAL.",
  },
  {
    title: "Authorization before action",
    body: "Hami acts only when authorized. No action touches the real world without explicit permission.",
  },
  {
    title: "Truth has states",
    body: "Possible → hypothesized → tested → supported. Supported requires evidence. Contradicted means reality pushed back.",
  },
  {
    title: "No manufactured reality",
    body: "No invented people, conversations, transactions, revenue, or outcomes. Ever.",
  },
] as const;

const CLIMB = [
  {
    n: 1,
    title: "One seller, one week",
    body: "Experiment 1: can faster replies recover real sales for one seller? No seller has agreed yet — it remains proposed.",
    earned: true,
  },
  { n: 2, title: "Ten sellers", earned: false },
  { n: 3, title: "A repeatable week", earned: false },
  { n: 4, title: "A local playbook", earned: false },
  { n: 5, title: "Everywhere", earned: false },
] as const;

function AboutPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · about"
        title="About Hami"
        lede="A living system that understands what people need and turns understanding into real value. Built in Kathmandu. Serving everywhere equally."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        {/* The reality loop */}
        <section className="border-b border-line pb-10">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
            The reality loop
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
            Reality → Observation → Evidence → Understanding → Unknown → Question →
            Test or act → New reality. The loop never stops. Each turn produces new
            understanding or new questions.
          </p>
        </section>

        {/* Six primitives */}
        <section className="border-b border-line py-10">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
            Six primitives
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
            Everything Hami knows is built from six primitives. No other data types.
          </p>
          <div className="mt-6 grid grid-cols-2 gap-px bg-line sm:grid-cols-3">
            {PRIMITIVES.map((p) => (
              <div key={p.name} className="bg-card p-4">
                <h3 className="font-display text-sm font-bold uppercase tracking-[0.12em] text-accent">
                  {p.name}
                </h3>
                <p className="mt-1.5 text-xs leading-5 text-muted">{p.def}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Evidence and authorization rules */}
        <section className="border-b border-line py-10">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
            The rules
          </h2>
          <div className="mt-6 space-y-4">
            {RULES.map((r) => (
              <div key={r.title} className="card p-5">
                <h3 className="font-display font-bold text-ink">{r.title}</h3>
                <p className="mt-1 text-sm leading-6 text-muted">{r.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* The climb */}
        <section className="py-10">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
            The climb
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
            Very big, very small. The big aim and the small aim are the same aim at
            different scales. Each step is earned by the one before it.
          </p>
          <div className="mt-6">
            {CLIMB.map((s) => (
              <div
                key={s.n}
                className="flex gap-5 border-t border-line py-5"
                style={{ opacity: s.earned ? 1 : 0.45 }}
              >
                <span
                  className="font-mono text-sm font-bold"
                  style={{ color: s.earned ? "var(--primary)" : "var(--muted)" }}
                >
                  {String(s.n).padStart(2, "0")}
                </span>
                <div>
                  <h3 className="font-display font-bold text-ink">{s.title}</h3>
                  {s.earned ? (
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">{s.body}</p>
                  ) : (
                    <p className="mt-1 text-sm italic text-muted">when earned</p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button asChild variant="primary" className="mt-6">
            <Link to="/experiments">
              See experiments <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </section>
      </Container>
    </main>
  );
}
