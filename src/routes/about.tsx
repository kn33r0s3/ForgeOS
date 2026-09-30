import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { PageHero } from "@/components/layout/page-hero";
import { CtaBand } from "@/components/layout/cta-band";
import { ProjectInquiryCta } from "@/components/pages/project-inquiry-cta";

export const Route = createFileRoute("/about")({
  component: AboutPage,
  head: () => ({ meta: [{ title: "About — Hami" }] }),
});

const items = [
  {
    number: "01",
    title: "One system",
    body: "Hami is one system. Nepal is the initial focus; global markets are a longer-term direction, not separate architectures. Domains and deployments are not claimed until verified.",
  },
  {
    number: "02",
    title: "The operating core",
    body: "Hami connects services, work, offers, trades, evidence, and outcomes through one shared system.",
  },
  {
    number: "03",
    title: "The standard",
    body: "No invented subsidiaries, clients, revenues, acquisitions, employees, investments, awards, partnerships, or market share are presented.",
  },
] as const;

function AboutPage() {
  return (
    <main>
      <PageHero
        eyebrow="Hami / About"
        title={
          <>
            One system
            <br />
            <span className="text-muted">for useful work.</span>
          </>
        }
        lede="Hami stores records of people, organizations, capabilities, needs, work, services, offers, trades, evidence, and outcomes. It helps people distinguish what is known from what remains unknown; recorded information alone does not authorize or prove an action."
      >
        <ProjectInquiryCta />
      </PageHero>
      <section className="py-16 sm:py-20">
        <Container className="max-w-3xl">
          <div className="border-t border-line">
            {items.map((item) => (
              <article
                key={item.number}
                className="grid grid-cols-[2.75rem_1fr] gap-5 border-b border-line py-7"
              >
                <span className="font-mono text-micro text-cyan">{item.number}</span>
                <div>
                  <h2 className="font-display text-xl font-semibold tracking-tight text-fg">
                    {item.title}
                  </h2>
                  <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted">
                    {item.body}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </Container>
      </section>
      <CtaBand />
    </main>
  );
}
