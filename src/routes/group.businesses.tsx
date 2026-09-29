import { createFileRoute } from "@tanstack/react-router";
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
        lede="Hami is one system evolving from ForgeOS. Today, the practical offer is technical and operational work that helps ideas become systems, and systems become durable businesses."
      >
        <div className="mt-8 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
          <ProjectInquiryCta />
          <TextLink to="/contact">Contact details</TextLink>
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
              {groupAreas.map((area) => (
                <div key={area.name} className="bg-surface p-5">
                  <strong className="font-display text-base font-semibold tracking-tight text-fg">
                    {area.name}
                  </strong>
                  <p className="mt-2 text-xs leading-relaxed text-muted">
                    {area.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </Container>
      <CtaBand />
    </main>
  );
}
