import { getGroupArea } from "@/lib/content";
import { PageHero } from "@/components/layout/page-hero";
import { StatusPill } from "@/components/layout/status-pill";
import { TextLink } from "@/components/layout/text-link";
import { CtaBand } from "@/components/layout/cta-band";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export function AreaView({ name }: { name: "Technology" | "Operations" | "Ventures" }) {
  const area = getGroupArea(name);
  return (
    <>
      <PageHero
        eyebrow={`Strategic area / ${name}`}
        title={
          <>
            {name}
            <br />
            <span className="text-muted">is building.</span>
          </>
        }
        lede={`${area?.description ?? ""} This is a long-term direction for Pulse, not a claim that a separate subsidiary or operating company exists today.`}
      >
        <StatusPill tone="amber">Long-term direction</StatusPill>
      </PageHero>
      <section className="py-16 sm:py-20">
        <Container className="max-w-2xl">
          <Eyebrow>Current status</Eyebrow>
          <h2 className="font-display text-title tracking-tight text-fg">
            Direction before declaration.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            Pulse will only describe a business area as active when there is
            clear evidence of an operating business behind it. Until then, the work
            is to learn, build carefully, and keep the distinction visible.
          </p>
          <div className="mt-6">
            <TextLink to="/group/businesses">See what is available today</TextLink>
          </div>
        </Container>
      </section>
      <CtaBand />
    </>
  );
}
