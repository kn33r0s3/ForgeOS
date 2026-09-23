import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight } from "lucide-react";
import { services } from "@/lib/content";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import { PageHero } from "@/components/layout/page-hero";
import { CtaBand } from "@/components/layout/cta-band";

export const Route = createFileRoute("/services/")({ component: ServicesPage });

function ServicesPage() {
  return (
    <main>
      <PageHero
        eyebrow="Services"
        title={
          <>
            Useful systems,
            <br />
            <span className="text-muted">properly supported.</span>
          </>
        }
        lede="Focused technical and operational services for work that needs to become clearer, more reliable, or easier to run."
      >
        <Button asChild className="mt-8">
          <Link to="/request">
            Start a Project
            <ArrowUpRight />
          </Link>
        </Button>
      </PageHero>
      <section className="py-6 sm:py-10">
        <Container>
          <div className="border-t border-line">
            {services.map((service, index) => (
              <Link
                key={service.slug}
                to="/services/$slug"
                params={{ slug: service.slug }}
                className="group grid grid-cols-[2.5rem_1fr_auto] items-center gap-4 border-b border-line py-6 transition-colors duration-150 hover:bg-cyan-dim sm:grid-cols-[3rem_1fr_auto]"
              >
                <span className="font-mono text-micro text-cyan">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h2 className="font-display text-xl font-semibold tracking-tight text-fg sm:text-2xl">
                    {service.title}
                  </h2>
                  <p className="mt-1 text-sm text-muted">{service.short}</p>
                </div>
                <ArrowUpRight className="size-4 text-dim transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-cyan" />
              </Link>
            ))}
          </div>
        </Container>
      </section>
      <CtaBand />
    </main>
  );
}
