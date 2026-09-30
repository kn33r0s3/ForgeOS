import { createFileRoute } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { ProjectInquiryCta } from "@/components/pages/project-inquiry-cta";

export const Route = createFileRoute("/contact")({
  component: ContactPage,
  head: () => ({ meta: [{ title: "Contact — Hami" }] }),
});

function ContactPage() {
  return (
    <main className="relative isolate overflow-hidden py-16 sm:py-20 lg:py-24">
      <div className="hero-glow -z-10" aria-hidden="true" />
      <Container className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>Contact Hami</Eyebrow>
          <h1 className="font-display font-black tracking-[-0.045em] text-display text-fg">
            Start with the
            <br />
            <span className="text-muted">situation.</span>
          </h1>
          <p className="mt-6 max-w-md text-lede text-muted">
            For a project, operating question, or conversation about building
            something useful, start with the context.
          </p>
          <ProjectInquiryCta />
        </div>
        <aside className="self-start rounded-xl border border-line bg-surface p-7">
          <Eyebrow>Direct line</Eyebrow>
          {SITE.email ? (
            <a href={`mailto:${SITE.email}`} className="block font-display text-2xl font-semibold tracking-tight text-fg transition-colors duration-150 hover:text-cyan sm:text-3xl">
              {SITE.email}
            </a>
          ) : <p className="font-display text-2xl font-semibold tracking-tight text-muted sm:text-3xl">Contact mailbox pending</p>}
          <p className="mt-3 text-sm text-muted">
            {SITE.email ? "A direct note before you are ready to scope work." : "A monitored contact address has not been configured yet."}
          </p>
          <div className="my-8 h-px bg-line" />
          <Eyebrow>Location</Eyebrow>
          <p className="text-sm text-muted">{SITE.location}</p>
          <div className="my-8 h-px bg-line" />
          <Eyebrow>System</Eyebrow>
          <p className="text-sm text-muted">
            {SITE.name}
            <br />
            {SITE.domain}
          </p>
        </aside>
      </Container>
    </main>
  );
}
