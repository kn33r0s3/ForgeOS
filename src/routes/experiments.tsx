import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
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
        <PublicOffers />
      </Container>
      <HamiPathways current="experiments" />
    </main>
  );
}


interface PublicOffer {
  id: string;
  title: string;
  audience: "BUYER" | "SELLER" | "CONTRIBUTOR";
  one_sentence_offer: string;
  they_give: string;
  they_get: string;
  consent_text: { en: string; ne: string };
  terms_text: { en: string; ne: string };
  status: "owner-approved" | "live";
  public_copy: boolean;
}

function PublicOffers() {
  const [offers, setOffers] = useState<PublicOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/opv4/offers/public")
      .then(async (response) => {
        if (!response.ok) throw new Error("Public offers are unavailable.");
        return response.json() as Promise<{ offers: PublicOffer[] }>;
      })
      .then((payload) => {
        if (active) {
          setOffers(payload.offers.filter((offer) => offer.public_copy));
          setError(false);
        }
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  return (
    <section aria-label="Owner-approved offers" className="mt-10 border-t border-line pt-8">
      <h2 className="font-display text-xl font-bold text-ink">Offers</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
        Small, consent-led exchanges with their terms shown up front. These appear only after owner approval and
        prerequisite checks. They describe a test, not a promised outcome.
      </p>
      {loading ? (
        <p className="mt-4 text-sm text-muted">Checking approved offer copy…</p>
      ) : error ? (
        <p role="status" className="mt-4 rounded-card border border-line bg-card p-4 text-sm text-muted">
          Approved offers could not be loaded. No action or contact was made.
        </p>
      ) : offers.length === 0 ? (
        <p className="mt-4 rounded-card border border-line bg-card p-4 text-sm text-muted">
          No owner-approved offers are publicly available yet. Drafts and blocked offers stay private.
        </p>
      ) : (
        <div className="mt-4 grid gap-4">
          {offers.map((offer) => (
            <article key={offer.id} className="card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-accent">{offer.audience}</span>
                <span className="rounded-full border border-line px-2 py-0.5 text-xs">{offer.status}</span>
              </div>
              <h3 className="mt-2 font-display text-base font-bold leading-6 text-ink">{offer.title}</h3>
              <p className="mt-2 text-sm leading-6 text-ink">{offer.one_sentence_offer}</p>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">You give</dt>
                  <dd className="mt-1 text-sm leading-6 text-muted">{offer.they_give}</dd>
                </div>
                <div>
                  <dt className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">You get</dt>
                  <dd className="mt-1 text-sm leading-6 text-muted">{offer.they_get}</dd>
                </div>
              </dl>
              <details className="mt-4 border-t border-line pt-3">
                <summary className="cursor-pointer text-sm font-bold text-ink">Read consent and terms · English / नेपाली</summary>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <div>
                    <h4 className="text-xs font-extrabold uppercase tracking-[0.12em] text-accent">Consent · English</h4>
                    <p className="mt-1 text-sm leading-6 text-muted">{offer.consent_text.en}</p>
                    <h4 className="mt-3 text-xs font-extrabold uppercase tracking-[0.12em] text-accent">Consent · नेपाली</h4>
                    <p className="mt-1 text-sm leading-6 text-muted">{offer.consent_text.ne}</p>
                  </div>
                  <div>
                    <h4 className="text-xs font-extrabold uppercase tracking-[0.12em] text-accent">Terms · English</h4>
                    <p className="mt-1 text-sm leading-6 text-muted">{offer.terms_text.en}</p>
                    <h4 className="mt-3 text-xs font-extrabold uppercase tracking-[0.12em] text-accent">Terms · नेपाली</h4>
                    <p className="mt-1 text-sm leading-6 text-muted">{offer.terms_text.ne}</p>
                  </div>
                </div>
              </details>
              <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
                No result is guaranteed. Hami will distinguish reports, evidence, actual outcomes, and unknowns.
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
