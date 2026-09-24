import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import { PageHero } from "@/components/layout/page-hero";
import { CtaBand } from "@/components/layout/cta-band";

export const Route = createFileRoute("/about")({
  component: AboutPage,
  head: () => ({ meta: [{ title: "About — Forge" }] }),
});

const items = [
  {
    number: "01",
    title: "The parent",
    body: "Sanip Operations is the parent identity. Future group areas are strategic directions, not a claim that subsidiaries or operating companies already exist.",
  },
  {
    number: "02",
    title: "The operating core",
    body: "Forge is the network this site reads. Services, work, offers, and trades are domains inside it. Nepal is the first geography, not the boundary of the records.",
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
        eyebrow="Forge / About"
        title={
          <>
            A parent platform
            <br />
            <span className="text-muted">for useful work.</span>
          </>
        }
        lede="Forge stores recorded people, organizations, capabilities, needs, work, services, offers, trades, evidence, and outcomes. It helps people read what is known and what remains unknown; it does not decide a match."
      >
        <Button asChild className="mt-8">
          <Link to="/request">
            Start a Project
            <ArrowUpRight />
          </Link>
        </Button>
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
