import { createFileRoute, notFound } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { getService } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { TextLink } from "@/components/layout/text-link";
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
              01—06
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
                <div className="mt-4">
                  <span className="text-muted">Contact via owner console</span>
                </div>
              </div>
            </article>
          </div>
        </Container>
      </section>
      <CtaBand />
    </main>
  );
}
