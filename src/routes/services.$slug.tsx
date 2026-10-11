import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { ArrowUpRight, Check } from "lucide-react";
import { getService, services } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { Eyebrow } from "@/components/layout/eyebrow";
import { CtaBand } from "@/components/layout/cta-band";
import { ProjectInquiryCta } from "@/components/pages/project-inquiry-cta";

export const Route = createFileRoute("/services/$slug")({
  loader: ({ params }) => {
    const service = getService(params.slug);
    if (!service) throw notFound();
    return { service };
  },
  component: ServicePage,
  head: ({ loaderData }) => ({
    meta: [
      {
        title: loaderData
          ? `${loaderData.service.title} — Hami`
          : "Service — Hami",
      },
    ],
  }),
});

function ServicePage() {
  const { service } = Route.useLoaderData();
  const sections = [
    ["The problem", service.problem],
    ["What Hami does", service.does],
    ["What is delivered", service.deliverable],
    ["How the process works", service.process],
    ["Who it is for", service.forWho],
  ] as const;

  return (
    <main>
      <section className="border-b border-line py-16 sm:py-20 lg:py-24">
        <Container className="grid items-end gap-10 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <Eyebrow>Service / {service.slug}</Eyebrow>
            <h1 className="max-w-3xl font-display font-black tracking-[-0.045em] text-display text-fg">
              {service.title}
            </h1>
            <p className="mt-6 max-w-xl text-lede text-muted">{service.short}</p>
            <ProjectInquiryCta />
          </div>
          <div className="flex min-h-48 flex-col justify-between rounded-xl bg-foreground p-6 text-background shadow-md">
            <span className="text-micro font-extrabold uppercase tracking-[0.12em] opacity-60">
              {service.number}—{String(services.length).padStart(2, "0")}
            </span>
            <strong className="font-display text-2xl font-semibold tracking-tight">
              Focused work.
              <br />
              Clear ownership.
            </strong>
            <small className="text-micro font-extrabold uppercase tracking-[0.12em] opacity-60">
              Hami · Nepal
            </small>
          </div>
        </Container>
      </section>
      <section className="py-16 sm:py-20">
        <Container className="grid gap-12 lg:grid-cols-[1fr_1.25fr] lg:gap-20">
          <div>
            <Eyebrow>A useful scope</Eyebrow>
            <h2 className="max-w-md font-display text-title tracking-tight text-fg">
              Good systems begin with the work, not the tool.
            </h2>
          </div>
          <div className="border-t border-line">
            {sections.map(([title, body], index) => (
              <article
                key={title}
                className="grid grid-cols-[2.75rem_1fr] gap-4 border-b border-line py-6"
              >
                <span className="font-mono text-micro text-cyan">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3 className="font-display text-lg font-semibold tracking-tight text-fg">
                    {title}
                  </h3>
                  <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">{body}</p>
                </div>
              </article>
            ))}
            <article className="mt-6 flex gap-4 rounded-xl border border-cyan/25 bg-cyan-dim p-5">
              <Check className="mt-0.5 size-4 shrink-0 text-cyan" />
              <div>
                <h3 className="font-display text-lg font-semibold tracking-tight text-fg">
                  What happens next
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{service.next}</p>
                <div className="mt-4 flex flex-wrap gap-4">
                  <Link to="/process" className="text-cyan hover:underline">
                    See how Hami works
                  </Link>
                  <Link to="/domain" className="text-cyan hover:underline">
                    Browse the public work board
                  </Link>
                </div>
              </div>
            </article>
          </div>
        </Container>
      </section>
      <section className="border-t border-line py-14 sm:py-16">
        <Container>
          <div className="max-w-2xl">
            <Eyebrow>One Hami service catalogue</Eyebrow>
            <h2 className="font-display text-title tracking-tight text-fg">
              Related work, connected.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              These are related service categories within Hami, not separate products or companies.
              Follow a link to compare the scope, then return to the full catalogue at any time.
            </p>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {services.filter((related) => related.slug !== service.slug).map((related) => (
              <Link
                key={related.slug}
                to="/services/$slug"
                params={{ slug: related.slug }}
                className="group rounded-xl border border-line bg-surface p-5 transition-colors hover:border-cyan/50 hover:bg-cyan-dim"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-micro text-cyan">{related.number}</span>
                  <ArrowUpRight className="size-4 text-dim transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-cyan" aria-hidden="true" />
                </div>
                <h3 className="mt-3 font-display text-lg font-semibold tracking-tight text-fg">{related.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{related.short}</p>
              </Link>
            ))}
          </div>
          <Link to="/services" className="link-arrow mt-6 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
            See all Hami services
            <ArrowUpRight className="size-4" aria-hidden="true" />
          </Link>
        </Container>
      </section>
      <CtaBand />
      <HamiPathways current="services" />
    </main>
  );
}
