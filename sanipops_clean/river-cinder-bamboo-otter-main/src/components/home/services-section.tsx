import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { services } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { TextLink } from "@/components/layout/text-link";

export function ServicesSection() {
  return (
    <section id="services" className="border-b border-line py-20 lg:py-24">
      <Container>
        <div className="mb-12 flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div>
            <Eyebrow>What we do</Eyebrow>
            <h2 className="font-display text-title tracking-tight text-fg">
              Built around the
              <br />
              <span className="text-muted">actual operation.</span>
            </h2>
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-muted">
            Focused commercial services for teams that need a capable technical
            partner without unnecessary complexity.
          </p>
        </div>
        <div className="grid border-t border-line sm:grid-cols-2 lg:grid-cols-3">
          {services.map((service) => (
            <Link
              key={service.slug}
              to="/services/$slug"
              params={{ slug: service.slug }}
              className="group flex min-h-64 flex-col border-b border-line p-6 transition-colors duration-150 hover:bg-cyan-dim sm:odd:border-r lg:[&:nth-child(3n)]:border-r-0 lg:border-r"
            >
              <div className="flex items-center justify-between font-mono text-micro uppercase tracking-[0.12em] text-dim">
                <span className="text-cyan">{service.number}</span>
                <span>Sanip / Ops</span>
              </div>
              <h3 className="mt-12 max-w-[14rem] font-display text-xl font-semibold tracking-tight text-fg">
                {service.title}
              </h3>
              <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted">
                {service.body}
              </p>
              <span className="mt-auto inline-flex items-center gap-1.5 pt-6 text-nav font-semibold text-cyan">
                Talk through this
                <ArrowUpRight className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </span>
            </Link>
          ))}
        </div>
        <div className="mt-8">
          <TextLink to="/services">All services</TextLink>
        </div>
      </Container>
    </section>
  );
}
