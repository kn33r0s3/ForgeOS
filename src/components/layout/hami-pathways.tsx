import { Link } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { SYSTEM_PATHWAYS, type SystemSurface } from "@/lib/hami-system";

/**
 * Related routes are presented as steps in the same evidence → question →
 * test → action loop, not as disconnected products or standalone microsites.
 */
export function HamiPathways({ current }: { current: SystemSurface }) {
  const pathways = SYSTEM_PATHWAYS[current];
  return (
    <section className="border-t border-line bg-surface" aria-label="Continue through Hami">
      <Container className="max-w-5xl py-8 sm:py-10">
        <div className="rounded-xl border border-line bg-background p-5 sm:p-6">
          <p className="text-micro font-extrabold uppercase tracking-[0.14em] text-accent">
            One Hami · Connected pathways
          </p>
          <h2 className="mt-2 font-display text-xl font-bold tracking-tight text-ink">
            Continue through the system
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Move between observations, open questions, connected records, tests, and useful work.
            Each surface stays part of the same Hami system.
          </p>
          <nav className="mt-5 flex flex-wrap gap-2" aria-label="Related Hami surfaces">
            {pathways.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="inline-flex min-h-10 items-center rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink transition-colors hover:border-accent hover:text-accent"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </Container>
    </section>
  );
}
