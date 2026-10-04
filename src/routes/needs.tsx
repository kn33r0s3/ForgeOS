import { createFileRoute } from "@tanstack/react-router";
import { Handshake, ScrollText } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export const Route = createFileRoute("/needs")({
  component: NeedsPage,
  head: () => ({ meta: [{ title: "What Hami is doing — Hami" }] }),
});

function NeedsPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · the wedge"
        title="The missed inquiry"
        lede="Many small sellers run their whole shop through chat apps. When a customer writes and nobody answers fast, the sale dies quietly. Hami's wedge is simple: for one week, a human handles the seller's replies fast, the recovered sales are counted, and Hami takes a cut only of what came back. No recovery, no charge — the thesis dies honestly."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <section aria-label="The offer" className="card p-6">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink">
            <Handshake className="h-5 w-5 text-accent" aria-hidden="true" />
            The offer being tested
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            One seller, one week. A person answers their customers within 15
            minutes, 9am to 9pm, and every sale that comes back because of the
            fast reply is counted. The seller pays a cut only of those
            recovered sales. Hami is not a tool the seller operates — it is
            the work being done for them, measured in rupees recovered.
          </p>
          <p className="mt-2 text-sm leading-6 text-muted">
            This is a hypothesis, not an established offer. It stands or falls on
            the first real week.
          </p>
        </section>

        <section aria-label="Week log" className="mt-6 card p-6">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink">
            <ScrollText className="h-5 w-5 text-accent" aria-hidden="true" />
            The week log
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            When a sprint week runs with a real seller, the numbers go here:
            inquiries seen, sales recovered, rupees. Not signups — rupees
            recovered, a seller who comes back, a seller who would be upset if
            it stopped.
          </p>
          <div className="mt-4 rounded-lg border border-line bg-background/60 p-4">
            <p className="font-bold text-ink">No week has run yet.</p>
            <p className="mt-1 text-sm text-muted">
              The first sprint starts when one seller and one human are named.
              Until then this log stays empty — it will not be filled with
              projections.
            </p>
          </div>
        </section>

        <p className="mt-8 border-t border-line pt-4 text-xs leading-5 text-dim">
          Hami is pre-revenue: no merchants served yet, no intake open. This
          page describes the work being attempted, not results achieved.
        </p>
      </Container>
    </main>
  );
}
