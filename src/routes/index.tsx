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

const C = {
  ground: "#171310",
  panel: "#1E1A15",
  line: "#3A2E1A",
  amber: "#E2A04B",
  text: "#EDE6D6",
  muted: "#BDB29F",
} as const;

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
    <main style={{ background: C.ground, color: C.text }}>
      <Hero />
      <FindingsPreview />
      <UnknownsPreview />
      <ExperimentsPreview />
      <AboutLink />
      <HomeFooter />
    </main>
  );
}

function RealityLoop() {
  const size = 320;
  const cx = size / 2;
  const cy = size / 2;
  const r = 118;
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto h-auto w-full max-w-[320px]"
      role="img"
      aria-label="Reality loop: Reality, Observation, Evidence, Understanding, Unknown, Question, Test or act, New reality"
    >
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={C.line} strokeWidth="1.5" />
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
            fill={C.amber}
            fontSize="11"
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
              r="30"
              fill={highlighted ? C.amber : C.panel}
              stroke={highlighted ? C.amber : C.line}
              strokeWidth={highlighted ? 2.5 : 1.5}
            />
            <text
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="central"
              fill={highlighted ? "#171310" : C.text}
              fontSize="8.5"
              fontWeight={highlighted ? 700 : 500}
              fontFamily="Archivo, sans-serif"
            >
              {label}
            </text>
          </g>
        );
      })}
      <text
        x={cx}
        y={cy - 10}
        textAnchor="middle"
        fill={C.text}
        fontSize="26"
        fontFamily="UnifrakturCook, serif"
      >
        Hami
      </text>
      <text
        x={cx}
        y={cy + 16}
        textAnchor="middle"
        fill={C.muted}
        fontSize="14"
        fontFamily="'Noto Sans Devanagari', sans-serif"
      >
        हामी
      </text>
    </svg>
  );
}

function Hero() {
  return (
    <section style={{ borderBottom: `1px solid ${C.line}` }}>
      <Container className="py-12 sm:py-16 lg:py-20">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <Eyebrow tone="amber">Hami · हामी</Eyebrow>
            <h1
              className="mt-5 text-[clamp(2.4rem,5.5vw,4.5rem)] font-extrabold leading-[1.05] tracking-tight"
              style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
            >
              Discover what matters.
              <br />
              Understand it. <span style={{ color: C.amber }}>Act on it.</span>
            </h1>
            <p
              className="mt-6 max-w-xl text-lg leading-8"
              style={{ fontFamily: "'Source Sans 3', sans-serif", color: C.text }}
            >
              Hami is a living system that understands what people need and turns
              understanding into real value.
            </p>
            <p
              className="mt-2 max-w-xl text-base leading-7"
              style={{ fontFamily: "'Noto Sans Devanagari', sans-serif", color: C.muted }}
            >
              हामी एउटा जीवित प्रणाली हो जसले मानिसहरूलाई के चाहिन्छ भन्ने बुझ्छ र
              बुझाइलाई वास्तविक मूल्यमा बदल्छ।
            </p>
            <p
              className="mt-5 text-sm font-bold uppercase tracking-[0.18em]"
              style={{ color: C.amber }}
            >
              Built in Kathmandu. Serving everywhere equally.
            </p>
          </div>
          <div className="text-center">
            <RealityLoop />
          </div>
        </div>
      </Container>
    </section>
  );
}

function PreviewSection({
  title,
  lede,
  to,
  linkLabel,
  children,
}: {
  title: string;
  lede: string;
  to: string;
  linkLabel: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ borderBottom: `1px solid ${C.line}` }}>
      <Container className="py-10 sm:py-14">
        <div className="max-w-4xl">
          <h2
            className="text-3xl font-extrabold tracking-tight sm:text-4xl"
            style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
          >
            {title}
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7" style={{ color: C.muted }}>
            {lede}
          </p>
          <div className="mt-8">{children}</div>
          <Button asChild variant="primary" className="mt-6">
            <Link to={to}>
              {linkLabel} <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </Container>
    </section>
  );
}

function FindingsPreview() {
  const [items, setItems] = useState<PublicDiscovery[] | null>(null);

  useEffect(() => {
    let live = true;
    loadDiscoveries(3)
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
    <PreviewSection
      title="Findings"
      lede="What we know and how sure we are — from the engine's evidence records."
      to="/discoveries"
      linkLabel="See all findings"
    >
      {!items ? (
        <p className="text-sm" style={{ color: C.muted }}>
          Loading…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm font-bold" style={{ color: C.text }}>
          Nothing recorded yet.
        </p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((finding, i) => (
            <FindingCard key={finding.id} finding={finding} index={i} />
          ))}
        </ul>
      )}
    </PreviewSection>
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
    <PreviewSection
      title="Unknowns"
      lede="What we don't know — each with its state, cheapest test, and stake."
      to="/unknowns"
      linkLabel="See all unknowns"
    >
      {!items ? (
        <p className="text-sm" style={{ color: C.muted }}>
          Loading…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm font-bold" style={{ color: C.text }}>
          No unknowns recorded yet.
        </p>
      ) : (
        <div className="grid gap-4">
          {items.map((unknown) => (
            <UnknownCard key={unknown.id} unknown={unknown} />
          ))}
        </div>
      )}
    </PreviewSection>
  );
}

function ExperimentsPreview() {
  const items = EXPERIMENTS.slice(0, 3);
  return (
    <PreviewSection
      title="Experiments"
      lede="What we are trying and what happened — real log only."
      to="/experiments"
      linkLabel="See all experiments"
    >
      {items.length === 0 ? (
        <p className="text-sm font-bold" style={{ color: C.text }}>
          No experiments yet.
        </p>
      ) : (
        <div className="grid gap-4">
          {items.map((exp) => (
            <ExperimentCard key={exp.id} experiment={exp} />
          ))}
        </div>
      )}
    </PreviewSection>
  );
}

function AboutLink() {
  return (
    <section style={{ borderBottom: `1px solid ${C.line}`, background: C.panel }}>
      <Container className="py-10 sm:py-14">
        <div className="max-w-4xl">
          <h2
            className="text-3xl font-extrabold tracking-tight sm:text-4xl"
            style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
          >
            About Hami
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7" style={{ color: C.muted }}>
            The loop, the six primitives, the evidence and authorization rules, and the
            climb — how Hami works and what it is building toward.
          </p>
          <Button asChild variant="primary" className="mt-6">
            <Link to="/about">
              About Hami <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </Container>
    </section>
  );
}

function HomeFooter() {
  const year = new Date().getFullYear();
  return (
    <footer style={{ background: C.panel }}>
      <Container className="py-8">
        <p className="max-w-2xl text-sm font-bold leading-6" style={{ color: C.text }}>
          Honest status: Hami is pre-revenue. Experiment 1 remains proposed; there are no
          participants or results to report.
        </p>
        <p className="mt-2 text-xs" style={{ color: C.muted }}>
          © {year} Hami · Built in Kathmandu, serving everywhere equally.
        </p>
      </Container>
    </footer>
  );
}
