import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/layout/eyebrow";
import {
  loadDiscoveries,
  loadPublicUnknowns,
  type PublicDiscovery,
  type PublicUnknown,
} from "@/lib/content";
import { FindingCard } from "@/components/findings/finding-card";
import { UnknownCard } from "@/components/unknowns/unknown-card";
import {
  ExperimentCard,
  EXPERIMENTS,
} from "@/components/experiments/experiment-card";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({
    meta: [
      { title: "Hami" },
      {
        name: "description",
        content:
          "Hami is a living system that understands what people need and turns understanding into real value. Built in Kathmandu. Serving everywhere equally.",
      },
      { property: "og:title", content: "Hami" },
      {
        property: "og:description",
        content: "Discover what matters. Understand it. Act on it.",
      },
      { name: "apple-mobile-web-app-title", content: "Hami" },
    ],
  }),
});

const LOOP_NODES = [
  "Reality",
  "Observation",
  "Evidence",
  "Understanding",
  "Unknown",
  "Question",
  "Test or act",
  "New reality",
] as const;

function HomePage() {
  return (
    <main className="bg-background text-ink">
      <Hero />
      <FindingsPreview />
      <UnknownsPreview />
      <ExperimentsPreview />
      <AboutLink />
      <StatusRecord />
      <HomeFooter />
    </main>
  );
}

function RealityLoop() {
  const size = 340;
  const cx = size / 2;
  const cy = size / 2;
  const r = 122;
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto h-auto w-full max-w-[340px]"
      role="img"
      aria-label="Reality loop: Reality, Observation, Evidence, Understanding, Unknown, Question, Test or act, New reality"
    >
      {/* Architectural outer ring */}
      <circle
        cx={cx}
        cy={cy}
        r={r + 34}
        fill="none"
        stroke="var(--border)"
        strokeWidth="1"
        strokeDasharray="3 6"
      />
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="var(--border)"
        strokeWidth="1.5"
      />
      {LOOP_NODES.map((_, i) => {
        const a1 = (i / LOOP_NODES.length) * Math.PI * 2 - Math.PI / 2;
        const a2 = ((i + 1) / LOOP_NODES.length) * Math.PI * 2 - Math.PI / 2;
        const am = (a1 + a2) / 2;
        const x = cx + Math.cos(am) * r;
        const y = cy + Math.sin(am) * r;
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="central"
            fill="var(--primary)"
            fontSize="12"
            fontWeight={700}
          >
            ›
          </text>
        );
      })}
      {LOOP_NODES.map((label, i) => {
        const a = (i / LOOP_NODES.length) * Math.PI * 2 - Math.PI / 2;
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r;
        const highlighted = label === "Unknown";
        return (
          <g key={label}>
            <circle
              cx={x}
              cy={y}
              r="31"
              fill={highlighted ? "var(--primary)" : "var(--surface)"}
              stroke={highlighted ? "var(--primary)" : "var(--border)"}
              strokeWidth={highlighted ? 2.5 : 1.5}
            />
            <text
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="central"
              fill={highlighted ? "#0c0b0a" : "var(--foreground)"}
              fontSize="8.5"
              fontWeight={highlighted ? 700 : 500}
              fontFamily="Archivo, sans-serif"
            >
              {label}
            </text>
          </g>
        );
      })}
      {/* Center identity */}
      <text
        x={cx}
        y={cy - 12}
        textAnchor="middle"
        fill="var(--foreground)"
        fontSize="30"
        fontFamily="UnifrakturCook, serif"
        fontWeight={700}
      >
        Hami
      </text>
      <text
        x={cx}
        y={cy + 18}
        textAnchor="middle"
        fill="var(--muted)"
        fontSize="15"
        fontFamily="'Noto Sans Devanagari', sans-serif"
      >
        हामी
      </text>
      {/* Cardinal ticks */}
      {[0, 90, 180, 270].map((deg) => {
        const a = ((deg - 90) * Math.PI) / 180;
        const x1 = cx + Math.cos(a) * (r + 34);
        const y1 = cy + Math.sin(a) * (r + 34);
        const x2 = cx + Math.cos(a) * (r + 42);
        const y2 = cy + Math.sin(a) * (r + 42);
        return (
          <line
            key={deg}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="var(--primary)"
            strokeWidth="2"
          />
        );
      })}
    </svg>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-line">
      <div className="hero-grain" aria-hidden="true" />
      {/* System strip: architectural instrument header */}
      <div className="border-b border-line bg-surface" aria-hidden="true">
        <Container className="flex items-center justify-between py-2">
          <span className="font-mono text-micro font-bold uppercase tracking-[0.2em] text-muted">
            Hami Operating System
          </span>
          <span className="hidden font-mono text-micro uppercase tracking-[0.2em] text-muted sm:block">
            Reality → Evidence → Action
          </span>
          <span className="flex items-center gap-2">
            <span className="live-dot live-dot-idle" />
            <span className="font-mono text-micro font-bold uppercase tracking-[0.2em] text-accent">
              Pre-revenue
            </span>
          </span>
        </Container>
      </div>
      <Container className="relative py-14 sm:py-20 lg:py-28">
        <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16">
          {/* Left: identity + editorial type */}
          <div className="reveal" style={{ "--i": 0 } as React.CSSProperties}>
            <Eyebrow tone="amber">A living system</Eyebrow>
            <div className="mt-2 flex flex-wrap items-end gap-x-6 gap-y-4">
              <span className="plate text-[clamp(3.2rem,9vw,6rem)] leading-none">
                Hami
              </span>
              <span
                className="pb-2 text-[clamp(1.6rem,4vw,2.6rem)] text-muted"
                style={{ fontFamily: "'Noto Sans Devanagari', sans-serif" }}
              >
                हामी
              </span>
            </div>
            <h1 className="mt-8 font-display text-[clamp(2.4rem,5.5vw,4.2rem)] font-extrabold leading-[1.02] tracking-tight text-ink">
              Discover what matters.
              <br />
              Understand it.{" "}
              <span className="text-gradient-gold">Act on it.</span>
            </h1>
            <div className="cut-rule mt-8" aria-hidden="true" />
            <p className="mt-6 max-w-xl font-sans text-lede leading-relaxed text-ink">
              Hami is a living system that understands what people need and turns
              understanding into real value.
            </p>
            <p
              className="mt-3 max-w-xl text-base leading-7 text-muted"
              style={{ fontFamily: "'Noto Sans Devanagari', sans-serif" }}
            >
              हामी एउटा जीवित प्रणाली हो जसले मानिसहरूलाई के चाहिन्छ भन्ने बुझ्छ र
              बुझाइलाई वास्तविक मूल्यमा बदल्छ।
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-4">
              <p className="text-sm font-extrabold uppercase tracking-[0.18em] text-accent">
                Built in Kathmandu.
                <br className="sm:hidden" /> Serving everywhere equally.
              </p>
            </div>
            <div className="mt-8 flex flex-wrap gap-4">
              <Button asChild variant="primary" size="lg">
                <Link to="/about">
                  How Hami works <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
          {/* Right: the loop, framed */}
          <div
            className="reveal"
            style={{ "--i": 2 } as React.CSSProperties}
          >
            <figure className="pinstripe">
              <RealityLoop />
              <figcaption className="mt-4 border-t border-line pt-4 text-center">
                <span className="tag">The reality loop</span>
                <p className="mt-3 text-sm leading-6 text-muted">
                  The operating cycle. Every belief must survive contact with
                  reality — or be revised.
                </p>
              </figcaption>
            </figure>
          </div>
        </div>
      </Container>
    </section>
  );
}

function SectionHead({
  numeral,
  eyebrow,
  title,
  lede,
}: {
  numeral: string;
  eyebrow: string;
  title: string;
  lede: string;
}) {
  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-5">
        <span className="gothic-num text-5xl sm:text-6xl" aria-hidden="true">
          {numeral}
        </span>
        <Eyebrow tone="amber" className="mb-0">
          {eyebrow}
        </Eyebrow>
      </div>
      <h2 className="mt-5 font-display text-title font-extrabold tracking-tight text-ink">
        {title}
      </h2>
      <p className="mt-3 max-w-2xl text-base leading-7 text-muted">{lede}</p>
    </div>
  );
}

function EmptyRecord({
  label,
  message,
}: {
  label: string;
  message: string;
}) {
  return (
    <div className="card mt-8 p-8 text-center sm:p-10">
      <span className="tag tag-muted">{label}</span>
      <p className="mx-auto mt-4 max-w-md text-base font-bold leading-7 text-ink">
        {message}
      </p>
      <p className="mt-2 text-sm text-muted">
        There is nothing here <em className="not-italic font-bold text-accent">yet</em> —
        not because it was forgotten, but because reality hasn't supplied it.
      </p>
    </div>
  );
}

function FindingsPreview() {
  const [items, setItems] = useState<PublicDiscovery[] | null>(null);

  useEffect(() => {
    let live = true;
    loadDiscoveries(3)
      .then((d) => {
        if (live) setItems((d ?? []).filter((f) => f.has_consequence));
      })
      .catch(() => {
        if (live) setItems([]);
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section className="border-b border-line">
      <Container className="py-12 sm:py-16 lg:py-20">
        <SectionHead
          numeral="I"
          eyebrow="Evidence"
          title="Findings"
          lede="What we know and how sure we are — from the engine's evidence records."
        />
        <div className="mt-8">
          {!items ? (
            <div className="skeleton h-32 w-full" aria-label="Loading findings" />
          ) : items.length === 0 ? (
            <EmptyRecord
              label="Empty record"
              message="No findings with recorded consequences yet. Findings appear here once they change a decision, experiment, or outcome."
            />
          ) : (
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((finding, i) => (
                <li key={finding.id} className="reveal" style={{ "--i": i } as React.CSSProperties}>
                  <FindingCard finding={finding} index={i} />
                </li>
              ))}
            </ul>
          )}
        </div>
        <Button asChild variant="primary" className="mt-8">
          <Link to="/discoveries">
            See all findings <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </Container>
    </section>
  );
}

function UnknownsPreview() {
  const [items, setItems] = useState<PublicUnknown[] | null>(null);

  useEffect(() => {
    let live = true;
    loadPublicUnknowns(3)
      .then((d) => {
        if (live) setItems(d);
      })
      .catch(() => {
        if (live) setItems([]);
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section className="identity-band border-b border-line">
      <Container className="py-12 sm:py-16 lg:py-20">
        <SectionHead
          numeral="II"
          eyebrow="The fuel"
          title="Unknowns"
          lede="What we don't know — each with its state, cheapest test, and stake. Known unknowns are the engine's fuel."
        />
        <div className="mt-8">
          {!items ? (
            <div className="skeleton h-32 w-full" aria-label="Loading unknowns" />
          ) : items.length === 0 ? (
            <EmptyRecord
              label="Empty record"
              message="No unknowns recorded yet. The unknowns map grows as Hami meets reality."
            />
          ) : (
            <div className="grid gap-5">
              {items.map((unknown, i) => (
                <div key={unknown.id} className="reveal" style={{ "--i": i } as React.CSSProperties}>
                  <UnknownCard unknown={unknown} />
                </div>
              ))}
            </div>
          )}
        </div>
        <Button asChild variant="primary" className="mt-8">
          <Link to="/unknowns">
            See all unknowns <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </Container>
    </section>
  );
}

function ExperimentsPreview() {
  const items = EXPERIMENTS.slice(0, 3);
  return (
    <section className="border-b border-line">
      <Container className="py-12 sm:py-16 lg:py-20">
        <SectionHead
          numeral="III"
          eyebrow="The real log"
          title="Experiments"
          lede="What we are trying and what happened — real log only. No simulations presented as results."
        />
        <div className="mt-8">
          {items.length === 0 ? (
            <EmptyRecord
              label="Empty record"
              message="No experiments yet. The first experiment begins when reality supplies a participant."
            />
          ) : (
            <div className="grid gap-5 lg:grid-cols-3">
              {items.map((exp, i) => (
                <div
                  key={exp.id}
                  className={i === 0 ? "lg:col-span-2" : ""}
                >
                  <div className="reveal h-full" style={{ "--i": i } as React.CSSProperties}>
                    <ExperimentCard experiment={exp} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <Button asChild variant="primary" className="mt-8">
          <Link to="/experiments">
            See all experiments <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </Container>
    </section>
  );
}

function AboutLink() {
  return (
    <section className="border-b border-line">
      <Container className="py-12 sm:py-16 lg:py-20">
        <div className="grid gap-10 lg:grid-cols-[auto_1fr] lg:items-center">
          <span className="gothic-num text-6xl sm:text-7xl" aria-hidden="true">
            IV
          </span>
          <div className="max-w-3xl">
            <Eyebrow tone="amber">The system</Eyebrow>
            <h2 className="mt-5 font-display text-title font-extrabold tracking-tight text-ink">
              About Hami
            </h2>
            <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
              The loop, the six primitives, the evidence and authorization rules,
              and the climb — how Hami works and what it is building toward.
            </p>
            <div className="mt-6 flex flex-wrap gap-4">
              <Button asChild variant="primary">
                <Link to="/about">
                  About Hami <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild variant="ghost">
                <Link to="/climb" className="link-arrow">
                  The climb <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}

function StatusRecord() {
  return (
    <section className="border-b border-line bg-surface">
      <Container className="py-12 sm:py-16">
        <div className="pinstripe">
          <div className="flex flex-wrap items-center gap-4">
            <span className="status-pill status-pill-warning">
              <span className="live-dot live-dot-idle" aria-hidden="true" />
              Honest status · Pre-revenue
            </span>
            <span className="tag tag-muted">Ledger entry</span>
          </div>
          <div className="mt-6 grid gap-6 sm:grid-cols-3">
            <div>
              <p className="font-mono text-micro font-bold uppercase tracking-[0.14em] text-muted">
                Revenue
              </p>
              <p className="mt-2 font-display text-3xl font-extrabold text-ink">
                Rs 0
              </p>
              <p className="mt-1 text-sm text-muted">No rupees received yet.</p>
            </div>
            <div>
              <p className="font-mono text-micro font-bold uppercase tracking-[0.14em] text-muted">
                Outcomes
              </p>
              <p className="mt-2 font-display text-3xl font-extrabold text-ink">
                0
              </p>
              <p className="mt-1 text-sm text-muted">No verified outcomes yet.</p>
            </div>
            <div>
              <p className="font-mono text-micro font-bold uppercase tracking-[0.14em] text-muted">
                Experiment 1
              </p>
              <p className="mt-2 font-display text-3xl font-extrabold text-accent">
                Proposed
              </p>
              <p className="mt-1 text-sm text-muted">
                Experiment 1 remains proposed. Awaiting a participant from reality.
              </p>
            </div>
          </div>
          <p className="mt-6 max-w-2xl text-sm leading-6 text-muted">
            This is a record, not an apology. Hami reports what reality has
            supplied — currently no participants or results to report — rather
            than manufacturing progress. The first real rupee will appear here
            the moment it exists.
          </p>
        </div>
      </Container>
    </section>
  );
}

function HomeFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="bg-background">
      <Container className="py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-xs text-muted">
            © {year} Hami · Built in Kathmandu, serving everywhere equally.
          </p>
          <Link
            to="/about"
            className="link-arrow text-sm font-bold text-wheat"
          >
            What Hami is <ArrowRight className="inline size-4" aria-hidden="true" />
          </Link>
        </div>
      </Container>
    </footer>
  );
}
