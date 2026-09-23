import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { TextLink } from "@/components/layout/text-link";

const pillars = [
  {
    kicker: "Today",
    title: "Useful work, stated plainly.",
    body: "A public platform and focused commercial engagements: software, automation, operations, internal tools, workflow systems, and technical support.",
  },
  {
    kicker: "Building",
    title: "An internal operating core.",
    body: "ForgeOS is in development as Sanip Ops’ local-first engine for long-term execution. It is not sold as a product and is not connected to this website.",
  },
  {
    kicker: "Long-term",
    title: "Directions, not subsidiaries.",
    body: "Technology, operations, ventures, and related areas are strategic directions. None of them are claimed as existing companies until there is evidence of one.",
  },
] as const;

export function GroupTeaser() {
  return (
    <section className="border-b border-line py-20 lg:py-24">
      <Container>
        <div className="grid gap-8 lg:grid-cols-[1fr_1.4fr] lg:items-end">
          <div>
            <Eyebrow>The parent group</Eyebrow>
            <h2 className="font-display text-title tracking-tight text-fg">
              One parent.
              <br />
              <span className="text-muted">Serious directions.</span>
            </h2>
          </div>
          <p className="max-w-xl text-sm leading-relaxed text-muted lg:justify-self-end">
            Sanip Ops is built to eventually own, operate, and scale businesses
            across technology, operations, and ventures — from Nepal, remote-ready.
            What exists today is stated plainly.
          </p>
        </div>
        <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3">
          {pillars.map((item) => (
            <article key={item.kicker} className="bg-surface p-6 sm:p-7">
              <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">
                {item.kicker}
              </p>
              <h3 className="mt-5 font-display text-xl font-semibold tracking-tight text-fg">
                {item.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-muted">{item.body}</p>
            </article>
          ))}
        </div>
        <div className="mt-8">
          <TextLink to="/group">See the group structure</TextLink>
        </div>
      </Container>
    </section>
  );
}
