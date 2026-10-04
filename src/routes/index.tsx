import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, Eye, Lightbulb, ShieldCheck, Sparkles } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({
    meta: [
      { title: "Hami — being built in the open" },
      {
        name: "description",
        content:
          "Hami is a pre-revenue project building a system for understanding real needs with evidence. No merchants served yet; intake closed.",
      },
    ],
  }),
});

function HomePage() {
  return (
    <main>
      <Welcome />
      <CurrentPaths />
    </main>
  );
}

/* ------------------------------------------------------------------ */

function CurrentPaths() {
  return (
    <section aria-labelledby="current-paths-title" className="border-t-2 border-black bg-card py-10 sm:py-14">
      <Container>
        <div className="max-w-3xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
            Existing paths
          </p>
          <h2 id="current-paths-title" className="mt-2 font-display text-3xl font-black tracking-tight text-ink">
            Start with what is actually available.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            These pages show recorded information and current routes. A hypothesis is not a validated
            opportunity, and a recorded action is not permission to execute it.
          </p>
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <article className="card p-5">
            <h3 className="font-display text-lg font-bold text-ink">Observations and discoveries</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Review public-source observations and accessible persisted findings. Restricted substrate
              records remain unavailable without their server-side authorization.
            </p>
            <Link to="/discoveries" className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
              Review discoveries <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </article>
          <article className="card p-5">
            <h3 className="font-display text-lg font-bold text-ink">Hypotheses and action state</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              See what is publicly surfaced as a possibility and the aggregate action state. Neither
              view represents a sale, approval, or completed outcome.
            </p>
            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2">
              <Link to="/opportunities" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
                Opportunities <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link to="/actions" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
                Action state <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </article>
          <article className="card p-5">
            <h3 className="font-display text-lg font-bold text-ink">Business information</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Read the current business information and the status of the existing Forge Bot inquiry
              path. Online lead intake remains closed.
            </p>
            <Link to="/group/businesses" className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
              For businesses <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </article>
        </div>
      </Container>
    </section>
  );
}

/* ------------------------------------------------------------------ */

const PRINCIPLES = [
  { icon: Eye, title: "Shows only what is recorded", body: "Sourced records show what is actually recorded. Nothing is filled in to look complete." },
  { icon: Lightbulb, title: "Keeps uncertainty visible", body: "Possible and hypothesized findings stay distinct from supported claims." },
  { icon: ShieldCheck, title: "Preserves agency", body: "External action requires authorization; outcomes require real evidence." },
];

function Welcome() {
  return (
    <section className="relative isolate overflow-hidden border-b-2 border-black">
      <div className="hero-glow -z-10" aria-hidden="true" />
      <div className="hero-grain -z-10" aria-hidden="true" />
      <Container className="py-12 sm:py-16 lg:py-20">
        <div className="max-w-3xl">
          <p className="flex items-center gap-2 font-mono text-[0.72rem] font-bold uppercase tracking-[0.18em] text-accent">
            <Sparkles className="size-4" aria-hidden="true" /> Hami · हामी
          </p>
          <h1 className="mt-5 text-[clamp(2.6rem,5.8vw,5rem)] font-black leading-[0.98] tracking-[-0.045em] text-ink">
            Understanding what people need
            <span className="mt-2 block text-muted">— with evidence, in the open.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
            Hami is being built in Kathmandu: a system for finding real needs,
            building evidence for them, and turning understanding into action
            with humans as partners. Right now the engine is working through
            open questions — no merchants served yet, no intake open.
            Everything on this site is what it actually is.
          </p>
          <div className="mt-6 flex flex-col items-start gap-3">
            <Button asChild size="lg">
              <Link to="/needs">
                See the needs being worked
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </Button>
            <p className="max-w-xl text-sm leading-6 text-muted">
              The candidate notebook: needs found so far, each labeled with
              what is known, unknown, and half-seen about it.
            </p>
          </div>
          <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-3">
            {PRINCIPLES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="glass flex gap-3 p-4">
                <Icon className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden="true" />
                <div>
                  <p className="text-sm font-extrabold text-ink">{title}</p>
                  <p className="mt-0.5 text-sm leading-5 text-muted">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
