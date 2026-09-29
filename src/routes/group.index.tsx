import { createFileRoute, Link } from "@tanstack/react-router";
import { groupAreas } from "@/lib/content";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";
import { PageHero } from "@/components/layout/page-hero";
import { SectionMarker } from "@/components/layout/section-marker";
import { StatusPill } from "@/components/layout/status-pill";
import { TextLink } from "@/components/layout/text-link";
import { CtaBand } from "@/components/layout/cta-band";

export const Route = createFileRoute("/group/")({ component: GroupPage });

function GroupPage() {
  return (
    <main>
      <PageHero
        eyebrow="Hami / The group"
        title={
          <>
            One system.
            <br />
            <span className="text-muted">Serious directions.</span>
          </>
        }
        lede="Hami is one evolving system, not separate Nepal and global architectures. What exists today is stated plainly; strategic directions are not presented as operating businesses."
      >
        <StatusPill>One unified platform</StatusPill>
      </PageHero>
      <section className="identity-band" aria-hidden="true">
        <Container className="flex flex-wrap items-center justify-between gap-3 py-5 font-mono text-kicker font-semibold uppercase tracking-[0.16em]">
          <span className="text-fg">Technology</span>
          <span className="rounded-sm bg-amber px-2 py-0.5 text-ink">Operations</span>
          <span className="text-ink">Ventures</span>
        </Container>
      </section>
      <Container className="py-16 sm:py-20">
        <section className="grid gap-8 lg:grid-cols-[9rem_1fr] lg:gap-12">
          <SectionMarker label="Today" index="01" />
          <div>
            <h2 className="font-display text-title tracking-tight text-fg">
              What is real right now.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
              A working public platform and a live offer of focused technical and
              operational work. Nothing on this page is a claim of subsidiaries,
              revenue, or partnerships.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              <article className="rounded-xl border border-line bg-surface p-6">
                <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">
                  Live
                </p>
                <h3 className="mt-4 font-display text-xl font-semibold tracking-tight text-fg">
                  The public platform
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  This website — services, group structure, and a working
                  project-request flow.
                </p>
                <div className="mt-5">
                  <TextLink to="/">Explore the platform</TextLink>
                </div>
              </article>
              <article className="rounded-xl border border-line bg-surface p-6">
                <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">
                  Available
                </p>
                <h3 className="mt-4 font-display text-xl font-semibold tracking-tight text-fg">
                  Technical & operational work
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  Focused engagements: software, automation, operations, internal
                  tools, workflow systems, support.
                </p>
                <div className="mt-5">
                  <TextLink to="/group/businesses">See the current offers</TextLink>
                </div>
              </article>
            </div>
          </div>
        </section>
        <section className="mt-16 grid gap-8 border-t border-line pt-10 lg:grid-cols-[9rem_1fr] lg:gap-12">
          <SectionMarker label="Building" index="02" />
          <div>
            <h2 className="font-display text-title tracking-tight text-fg">
              The operating core.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
              Hami is the record this site reads: observe, verify, understand,
              decide, act, measure, learn. An empty list means that record is
              not stored. It is not sold as a product.
            </p>
            <div className="mt-5">
              <TextLink to="/process">How we work</TextLink>
            </div>
          </div>
        </section>
        <section className="mt-16 grid gap-8 border-t border-line pt-10 lg:grid-cols-[9rem_1fr] lg:gap-12">
          <SectionMarker label="Long-term" index="03" />
          <div>
            <h2 className="font-display text-title tracking-tight text-fg">
              Directions the system may grow into.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
              Strategic directions only — not existing subsidiaries, operating
              companies, or revenue. Each becomes a declared business only when
              there is clear evidence of one behind it.
            </p>
            <div className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
              {groupAreas.map((area) => {
                const inner = (
                  <>
                    <strong className="font-display text-base font-semibold tracking-tight text-fg">
                      {area.name}
                    </strong>
                    <p className="mt-2 text-xs leading-relaxed text-muted">
                      {area.description}
                    </p>
                  </>
                );
                return area.href ? (
                  <Link
                    key={area.name}
                    to={area.href}
                    className="bg-surface p-5 transition-colors duration-150 hover:bg-cyan-dim"
                  >
                    {inner}
                  </Link>
                ) : (
                  <div key={area.name} className="bg-surface p-5">
                    {inner}
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </Container>
      <CtaBand
        eyebrow="The standard"
        title={
          <>
            Stated plainly,
            <br />
            <span className="text-muted">built to last.</span>
          </>
        }
        body="No invented subsidiaries, clients, revenue, investments, awards, partnerships, or market share — anywhere on this platform. That rule is the product."
      />
    </main>
  );
}
