import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight } from "lucide-react";
import { SITE } from "@/lib/content";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export const Route = createFileRoute("/contact")({
  component: ContactPage,
  head: () => ({ meta: [{ title: "Contact — Forge" }] }),
});

function ContactPage() {
  return (
    <main className="py-16 sm:py-20 lg:py-24">
      <Container className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <Eyebrow>Contact Forge</Eyebrow>
          <h1 className="font-display text-display tracking-tight text-fg">
            Start with the
            <br />
            <span className="text-muted">situation.</span>
          </h1>
          <p className="mt-6 max-w-md text-lede text-muted">
            For a project, operating question, or conversation about building
            something useful, start with the context.
          </p>
          <Button asChild className="mt-8">
            <Link to="/request">
              Start a Project
              <ArrowUpRight />
            </Link>
          </Button>
        </div>
        <aside className="self-start rounded-xl border border-line bg-surface p-7">
          <Eyebrow>Direct line</Eyebrow>
          <a
            href={`mailto:${SITE.email}`}
            className="block font-display text-2xl font-semibold tracking-tight text-fg transition-colors duration-150 hover:text-cyan sm:text-3xl"
          >
            {SITE.email}
          </a>
          <p className="mt-3 text-sm text-muted">
            A direct note before you are ready to scope work.
          </p>
          <div className="my-8 h-px bg-line" />
          <Eyebrow>Location</Eyebrow>
          <p className="text-sm text-muted">{SITE.location}</p>
          <div className="my-8 h-px bg-line" />
          <Eyebrow>Entity</Eyebrow>
          <p className="text-sm text-muted">
            {SITE.legalName}
            <br />
            {SITE.name}
            <br />
            {SITE.domain}
          </p>
        </aside>
      </Container>
    </main>
  );
}
