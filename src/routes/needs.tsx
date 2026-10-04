import { createFileRoute } from "@tanstack/react-router";
import { CircleHelp, Eye, EyeOff, Scale } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import {
  candidateNeeds,
  KNOWN_LABEL,
  needsCount,
  needsRounds,
  type KnownToThem,
} from "@/lib/needs";

export const Route = createFileRoute("/needs")({
  component: NeedsPage,
  head: () => ({ meta: [{ title: "Needs Hami has found — Hami" }] }),
});

const KNOWN_STYLE: Record<KnownToThem, string> = {
  known: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  unknown: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  partially: "border-sky-500/30 bg-sky-500/10 text-sky-200",
};

const KNOWN_ICON: Record<KnownToThem, typeof Eye> = {
  known: Eye,
  unknown: EyeOff,
  partially: Scale,
};

function NeedsPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · candidate needs"
        title="Needs Hami has found"
        lede="Finding what people need — the needs they name and the ones they don't — is the work. These were observed in public sources: reviews, forums, press, app data. They are not yet verified with the people themselves. Each is a candidate until a real conversation confirms or kills it."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <section aria-label="How to read this page" className="mb-10 rounded-xl border border-line bg-surface p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="flex items-center gap-2 text-sm font-bold text-ink">
                <Eye className="h-4 w-4 text-emerald-300" /> Known needs
              </p>
              <p className="mt-1 text-sm leading-6 text-muted">
                They feel it and name it. It hurts out loud.
              </p>
            </div>
            <div>
              <p className="flex items-center gap-2 text-sm font-bold text-ink">
                <EyeOff className="h-4 w-4 text-amber-300" /> Unknown needs
              </p>
              <p className="mt-1 text-sm leading-6 text-muted">
                They don't name it — it shows up in behavior. The higher-value find.
              </p>
            </div>
            <div>
              <p className="flex items-center gap-2 text-sm font-bold text-ink">
                <Scale className="h-4 w-4 text-sky-300" /> Half-seen
              </p>
              <p className="mt-1 text-sm leading-6 text-muted">
                Felt in one segment, invisible in another.
              </p>
            </div>
          </div>
          <p className="mt-4 border-t border-line pt-4 text-sm leading-6 text-muted">
            Evidence class for every entry: <strong className="text-ink">OBSERVED</strong> —
            seen in public sources, paraphrased, never invented. Status:{" "}
            <strong className="text-ink">candidate</strong>. {needsCount} needs from {needsRounds}{" "}
            rounds of listening. Reality gets the final vote.
          </p>
        </section>

        <section aria-label="Candidate needs" className="grid gap-5">
          {candidateNeeds.map((need) => {
            const Icon = KNOWN_ICON[need.knownToThem];
            return (
              <article
                key={need.id}
                className="rounded-xl border border-line bg-surface p-5 sm:p-6"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${KNOWN_STYLE[need.knownToThem]}`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {KNOWN_LABEL[need.knownToThem]}
                  </span>
                  <span className="text-xs font-medium uppercase tracking-wider text-muted">
                    {need.segment}
                  </span>
                  <span className="ml-auto text-xs text-muted">{need.round}</span>
                </div>
                <h2 className="mt-3 font-display text-xl tracking-tight text-ink">
                  {need.title}
                </h2>
                <p className="mt-1 text-sm font-semibold leading-6 text-ink/90">
                  {need.need}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted">{need.observed}</p>
                <p className="mt-3 text-xs leading-5 text-muted">
                  Seen in: {need.sources.join(" · ")}
                </p>
                <p className="mt-3 flex gap-2 rounded-lg border border-line bg-background/60 p-3 text-sm leading-6 text-muted">
                  <CircleHelp className="mt-1 h-4 w-4 shrink-0 text-accent" />
                  <span>
                    <strong className="text-ink">The question it raises: </strong>
                    {need.question}
                  </span>
                </p>
              </article>
            );
          })}
        </section>

        <section aria-label="What happens next" className="mt-10 rounded-xl border border-line p-5">
          <p className="text-sm leading-6 text-muted">
            These are Hami's best current guesses, published so reality can correct them.
            The five conversations with real business owners will verify or kill each one —
            a need nobody confirms is a need Hami drops.
          </p>
        </section>
      </Container>
    </main>
  );
}
