import { createFileRoute, Link } from "@tanstack/react-router";
import { currentOffers, groupAreas } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { PageHero } from "@/components/layout/page-hero";
import { SectionMarker } from "@/components/layout/section-marker";
import { TextLink } from "@/components/layout/text-link";
import { CtaBand } from "@/components/layout/cta-band";
import { OfferCard } from "@/components/pages/offer-card";
import { ProjectInquiryCta } from "@/components/pages/project-inquiry-cta";

export const Route = createFileRoute("/group/businesses")({
  component: BusinessesPage,
  head: () => ({ meta: [{ title: "Businesses — Hami" }] }),
});

function BusinessesPage() {
  return (
    <main>
      <PageHero
        eyebrow="Businesses / solutions"
        title={
          <>
            Grand ambition.
            <br />
            <span className="text-muted">Useful work today.</span>
          </>
        }
        lede="Hami is one connected system. Today, the practical offer is technical and operational work that helps ideas become systems, and systems become durable businesses."
      >
        <div className="mt-8 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
          <ProjectInquiryCta />
          <Link to="/contact" className="text-cyan hover:underline">
            Contact Hami
          </Link>
        </div>
      </PageHero>
      <Container className="py-16 sm:py-20">
        <section className="grid gap-8 lg:grid-cols-[9rem_1fr] lg:gap-12">
          <SectionMarker label="Today" index="01" />
          <div>
            <h2 className="font-display text-title tracking-tight text-fg">
              What Hami can do now
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
              Current offerings are focused engagements around technology,
              software, workflows, operations, infrastructure support, and early
              venture thinking.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {currentOffers.map((offer) => (
                <OfferCard key={offer.title} offer={offer} />
              ))}
            </div>
          </div>
        </section>
        <section className="mt-16 grid gap-8 border-t border-line pt-10 lg:grid-cols-[9rem_1fr] lg:gap-12">
          <SectionMarker label="Building" index="02" />
          <div>
            <h2 className="font-display text-title tracking-tight text-fg">
              Developing the group’s operating core.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
              Hami is the record this site reads. It supports the long-term
              direction. An empty list means that record is not stored, and it
              is not being sold as a separate product.
            </p>
            <div className="mt-5">
              <TextLink to="/about">See the group context</TextLink>
            </div>
            <div className="mt-6 max-w-3xl border-2 border-line bg-card p-5 sm:p-6">
              <p className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.14em] text-accent">
                Existing inquiry path · segment remains a hypothesis
              </p>
              <h3 className="mt-2 font-display text-xl font-bold tracking-tight text-ink">
                Forge Bot inquiry status
              </h3>
              <p className="mt-2 text-sm leading-6 text-muted">
                A consent-scoped inquiry route exists for owner review. This is not a published offer;
                online intake is closed while the pilot and safeguards remain unverified.
              </p>
              <Link
                to="/forge-bot-intake"
                className="link-arrow mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
              >
                Read the inquiry page
              </Link>
            </div>
          </div>
        </section>
        <section className="mt-16 grid gap-8 border-t border-line pt-10 lg:grid-cols-[9rem_1fr] lg:gap-12">
          <SectionMarker label="Long-term" index="03" />
          <div>
            <h2 className="font-display text-title tracking-tight text-fg">
              Areas the parent platform may grow into.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
              These are strategic directions, not existing subsidiaries or
              operating businesses.
            </p>
            <div className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
              {groupAreas.map((area) => {
                const inner = (
                  <>
                    <strong className="font-display text-base font-semibold tracking-tight text-fg">
                      {area.name}
                    </strong>
                    <p className="mt-2 text-xs leading-relaxed text-muted">
                      {area.description}
                    </p>
                  </>
                );
                return area.href ? (
                  <Link
                    key={area.name}
                    to={area.href}
                    className="bg-surface p-5 transition-colors duration-150 hover:bg-cyan-dim"
                  >
                    {inner}
                  </Link>
                ) : (
                  <div key={area.name} className="bg-surface p-5">
                    {inner}
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </Container>
      <CtaBand />
    </main>
  );
}
