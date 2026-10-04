import { createFileRoute } from "@tanstack/react-router";
import { CalendarClock, CircleAlert, ShieldCheck } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export const Route = createFileRoute("/needs")({
  component: NeedsPage,
  head: () => ({
    meta: [
      { title: "Experiment 1 — Hami" },
      {
        name: "description",
        content:
          "The scope and current status of Hami's proposed one-week faster-reply experiment. No seller has agreed and no week has run.",
      },
    ],
  }),
});

function NeedsPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Hami · one bounded experiment"
        title="Experiment 1: faster replies for one seller"
        lede="The hypothesis is that faster replies may recover sales that would otherwise disappear. If a seller agrees, a person would help handle incoming customer messages for one explicitly agreed week. There is no upfront payment; any fee would be tied only to sales both sides attribute to faster replies. This is not a performance guarantee."
        containerClassName="max-w-4xl"
      />
      <Container className="max-w-4xl py-10 sm:py-14">
        <section aria-labelledby="experiment-status" className="card border-accent p-6">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink">
            <CircleAlert className="h-5 w-5 text-accent" aria-hidden="true" />
            <span id="experiment-status">Current status</span>
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            No seller has agreed to participate. No customer messages have
            been handled, and no experiment week has run. No sign-up or live
            intake is available on this page.
          </p>
          <p className="mt-2 text-sm leading-6 text-muted">
            The segment, participant eligibility, exact operating period,
            response expectations, attribution rules, and fee terms must be
            agreed and verified before any work begins.
          </p>
        </section>

        <section aria-labelledby="scope-title" className="mt-6 card p-6">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink">
            <ShieldCheck className="h-5 w-5 text-accent" aria-hidden="true" />
            <span id="scope-title">Boundaries to agree before starting</span>
          </h2>
          <ul className="mt-4 grid gap-3 text-sm leading-6 text-muted sm:grid-cols-2">
            <li className="border-l-2 border-line pl-3">Named seller and contact; the contact's role must not be assumed.</li>
            <li className="border-l-2 border-line pl-3">Seller's explicit permission for the exact channels, messages, and access.</li>
            <li className="border-l-2 border-line pl-3">Agreed dates, hours, response expectations, and who handles exceptions.</li>
            <li className="border-l-2 border-line pl-3">A baseline and shared definitions for a reply and an attributable sale.</li>
            <li className="border-l-2 border-line pl-3">Fee terms agreed before work; payment only for attributable real sales.</li>
            <li className="border-l-2 border-line pl-3">Eligibility, legal review, privacy boundaries, and evidence location.</li>
          </ul>
        </section>

        <section aria-label="Next dependency" className="mt-6 flex items-start gap-3 border-t border-line pt-5">
          <CalendarClock className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
          <p className="text-sm leading-6 text-muted">
            The next dependency is owner-run discovery and an explicitly
            authorized first contact. This page does not send messages or
            authorize access. Hami remains pre-revenue; no seller has been
            served, and the experiment has not started.
          </p>
        </section>
      </Container>
    </main>
  );
}
