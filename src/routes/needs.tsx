import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRightLeft, Handshake, ShieldCheck } from "lucide-react";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { PageHeader } from "@/components/layout/page-header";

export const Route = createFileRoute("/needs")({
  component: NeedsPage,
  head: () => ({ meta: [{ title: "Needs & offers — Hami" }] }),
});

function NeedsPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · needs, offers, and exchange"
        title="Make a fair exchange possible."
        lede="People have needs, skills, time, goods, knowledge, capacity, relationships, and ideas. Hami helps make those possibilities legible so people can propose value and review what each side gives and receives—across domains, not just one industry or idea. A public post records a proposal; it does not establish mutual acceptance."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-5xl py-10 sm:py-14">
        <section className="grid gap-4 md:grid-cols-3" aria-label="Ways to create value">
          <article className="card p-5">
            <ArrowRightLeft className="size-5 text-accent" aria-hidden="true" />
            <h2 className="mt-3 font-display text-xl font-bold text-ink">Start from either side</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Post what you can offer, describe what you need, propose a trade, or look for a useful way to combine resources and capabilities.</p>
          </article>
          <article className="card p-5">
            <Handshake className="size-5 text-accent" aria-hidden="true" />
            <h2 className="mt-3 font-display text-xl font-bold text-ink">Make expectations clear</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Name the deliverable, who can participate, how success is checked, who owns the result, what costs apply, and what happens if the work is partial or disputed.</p>
          </article>
          <article className="card p-5">
            <ShieldCheck className="size-5 text-accent" aria-hidden="true" />
            <h2 className="mt-3 font-display text-xl font-bold text-ink">Keep the record honest</h2>
            <p className="mt-2 text-sm leading-6 text-muted">An offer is a proposal, a match is a suggestion, and a response is not acceptance. Payment and fulfillment remain separate events that need their own evidence.</p>
          </article>
        </section>

        <section className="mt-8 card p-6 sm:p-8" aria-labelledby="make-an-offer">
          <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">Start with the exchange</p>
          <h2 id="make-an-offer" className="mt-2 font-display text-2xl font-bold tracking-tight text-ink">What could you offer—and what would help you?</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
            The public board supports needs/jobs, offers, and trades today. You can state price or reciprocal value and disclose contract terms. Incomplete terms remain a draft proposal and cannot pass the current work-acceptance gate. Do not put private contact details or sensitive data in a public post.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link to="/domain" hash="post-form" className="inline-flex min-h-11 items-center justify-center rounded-card border-2 border-accent bg-accent px-5 text-sm font-extrabold text-black transition-colors hover:bg-transparent hover:text-accent">Post a need or offer</Link>
            <Link to="/domain" className="inline-flex min-h-11 items-center justify-center rounded-card border border-line px-5 text-sm font-semibold text-ink hover:border-accent">Browse current exchanges</Link>
          </div>
        </section>

        <section className="mt-8 grid gap-6 md:grid-cols-2" aria-label="Current Hami capabilities">
          <div className="card p-6">
            <h2 className="font-display text-xl font-bold text-ink">Work Hami can currently propose</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Hami's current catalogue includes software and web development, automation, digital operations, internal tools, workflow systems, and technical support. Scope and availability still need agreement; a catalogue description is not a delivery promise.</p>
            <Link to="/services" className="mt-4 inline-flex min-h-10 items-center gap-2 text-sm font-bold text-accent hover:underline">Explore Hami services <span aria-hidden="true">→</span></Link>
          </div>
          <div className="card p-6">
            <h2 className="font-display text-xl font-bold text-ink">Find a verified provider</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Where a real provider is verified and publicly listed, use the provider path. Booking requests remain requests until the provider confirms; no provider or capacity is invented to fill an empty result.</p>
            <Link to="/providers" className="mt-4 inline-flex min-h-10 items-center gap-2 text-sm font-bold text-accent hover:underline">Browse verified providers <span aria-hidden="true">→</span></Link>
          </div>
        </section>

        <section className="mt-8 border-t border-line pt-5" aria-label="Current state">
          <p className="text-xs leading-5 text-muted">
            Hami is pre-revenue; no merchants served yet. This is a broad entry to existing value-exchange paths, not a claim that Hami has already matched, contacted, or fulfilled an exchange for everyone. The public board may be empty. No automatic outreach or payment is triggered by a post.
          </p>
          <p className="mt-2 text-xs leading-5 text-muted">
            The earlier missed-inquiry sprint remains a hypothesis in Hami's experiment history; it is not the boundary of what Hami can investigate or offer.
          </p>
        </section>
      </Container>
      <HamiPathways current="needs" />
    </main>
  );
}
