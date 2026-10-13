import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
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
          "The reality loop, six primitives, evidence rules, and many connected paths toward shared progress.",
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

const FIVE_QUESTIONS = [
  {
    q: "1. Reality",
    plain: "What actually exists, or what actually happened? Not what we hope — what we can show.",
  },
  {
    q: "2. Possibility",
    plain: "What could become true here? What valuable outcome is within reach?",
  },
  {
    q: "3. Constraint",
    plain: "Why isn't it true yet? Treated as a hypothesis until evidence supports it — never asserted as fact.",
  },
  {
    q: "4. Intervention",
    plain: "What can legitimately be done to move reality toward it — with the right authorization?",
  },
  {
    q: "5. Outcome",
    plain: "Did reality actually change? If not, the loop starts again with better questions.",
  },
] as const;

const CLIMBS = [
  { title: "Understand reality", body: "Learn from lived experience, system behavior, existing resources, and what actually changes across domains and places.", feeds: "Better questions, stronger evidence, more useful decisions." },
  { title: "Expand what is known", body: "Find missing knowledge, surface hidden constraints, test assumptions, preserve contradictions, and keep uncertainty visible.", feeds: "Every other climb gets a clearer map of what is known, unknown, or blocked." },
  { title: "Connect what is separate", body: "Relate needs, people, capabilities, resources, knowledge, and opportunities when the connection is relevant, permitted, and useful to those involved.", feeds: "One supported discovery can unlock many paths without creating a second source of truth." },
  { title: "Build what is missing", body: "Extend software, tools, interfaces, workflows, integrations, skills, and operating capacity where a real gap is evidenced.", feeds: "Reusable capabilities strengthen more than the one problem that revealed the gap." },
  { title: "Test, act, and learn", body: "Turn understanding into the smallest legitimate test or authorized action, measure what changed, and keep negative results.", feeds: "Real outcomes correct the map, reprioritize work, and stop wasted effort from repeating." },
  { title: "Strengthen shared capacity", body: "Improve trust, privacy, resilience, local knowledge, fair exchange, skills, access, and the ability for people to help one another.", feeds: "Progress should compound for participants—not depend on extracting their data or forcing one path." },
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

        {/* Five questions */}
        <section className="border-b border-line py-10">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
            Five questions
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
            Before Hami does anything serious, it tries to answer these — in
            plain words, honestly, with evidence where it exists and honesty
            where it doesn't.
          </p>
          <ol className="mt-6 space-y-4">
            {FIVE_QUESTIONS.map((q) => (
              <li key={q.q} className="card p-5">
                <h3 className="font-display font-bold text-ink">{q.q}</h3>
                <p className="mt-1 text-sm leading-6 text-muted">{q.plain}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Six primitives */}
        <section className="border-b border-line py-10">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">
            Six primitives
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
            Hami can represent open-ended domains through six shared semantic primitives. Domain-specific types belong within the registered model; they do not require a seventh top-level primitive.
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

        {/* Many connected climbs */}
        <section id="climb" className="py-10 scroll-mt-24">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-ink">Many climbs. One living system.</h2>
          <p className="mt-3 max-w-3xl text-base leading-7 text-muted">There is no final rung and no fixed number of paths. Reality keeps opening new questions, possibilities, relationships, capabilities, and ways to create value. These directions strengthen one another; they do not wait in one line for a single pilot to succeed.</p>
          <div className="mt-6 rounded-2xl border border-line bg-card p-5 sm:p-6">
            <p className="font-display text-lg font-bold text-ink">Hami · Hamro</p>
            <p className="mt-2 text-sm leading-6 text-muted"><strong>Hami</strong> is the name of the living system. <strong>Hamro</strong> means “our/ours” and expresses the direction: knowledge and capabilities should connect so people can help one another create fair, real value. Shared progress never means shared access to private data—consent, privacy, attribution, safety and individual choice remain binding.</p>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {CLIMBS.map((climb) => (
              <article key={climb.title} className="card p-5">
                <h3 className="font-display font-bold text-ink">{climb.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{climb.body}</p>
                <p className="mt-3 border-t border-line pt-3 text-sm leading-6 text-muted"><strong className="text-ink">How it strengthens the rest:</strong>{" "}{climb.feeds}</p>
              </article>
            ))}
          </div>
          <div className="mt-6 border-l-2 border-line pl-4">
            <h3 className="font-display font-bold text-ink">One pilot is one pilot.</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">The missed-inquiry seller idea is one candidate economic test, not Hami’s identity, an established need, or permission to act. No seller has agreed yet. Every real-world action still needs the right evidence, consent, legal clarity and authorization. A blocked action does not stop independent research, engineering, verification or other safe work.</p>
          </div>
          <p className="mt-6 max-w-3xl text-sm leading-6 text-muted">This is the operating direction, not a claim that every loop is already autonomous. Current discoveries, unknowns and experiments retain their own evidence and status; implemented code, successful tests, deployed behavior and real-world outcomes are reported separately.</p>
          <Button asChild variant="primary" className="mt-6"><Link to="/experiments">See experiments <ArrowRight className="size-4" aria-hidden="true" /></Link></Button>
        </section>
      </Container>
      <HamiPathways current="about" />
    </main>
  );
}
