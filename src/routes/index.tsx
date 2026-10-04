import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import {
  loadDiscoveries,
  loadUnknownsSummary,
  UNKNOWN_STATE_LABELS,
  type PublicDiscovery,
  type UnknownsSummary,
  type UnknownState,
} from "@/lib/content";

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

/* Design tokens for the unknowns surface */
const C = {
  ground: "#0C0B0A",
  panel: "#15130F",
  line: "#3A2E1A",
  amber: "#F2A33A",
  text: "#F4EFE6",
  muted: "#BDB29F",
} as const;

/* Reality loop nodes, in order */
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

/* Six primitives with one-line definitions */
const PRIMITIVES = [
  { name: "Entity", def: "An identifiable thing in the world." },
  { name: "Relation", def: "A typed connection between things." },
  { name: "Event", def: "Something observed or changed." },
  { name: "Evidence", def: "The sourced basis for a claim." },
  { name: "Capability", def: "What can actually be done." },
  { name: "Action", def: "An operation within authorization." },
] as const;

function HomePage() {
  return (
    <main style={{ background: C.ground, color: C.text }}>
      <Hero />
      <PrimitivesStrip />
      <PowerOfUnknown />
      <VeryBigVerySmall />
      <WhatWeHaveLearned />
      <HomeFooter />
    </main>
  );
}

/* 1. Hero with SVG reality loop */

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
      {/* circle guide */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={C.line} strokeWidth="1.5" />
      {/* arrows between nodes */}
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
      {/* nodes */}
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
              fill={highlighted ? "#0C0B0A" : C.text}
              fontSize="8.5"
              fontWeight={highlighted ? 700 : 500}
              fontFamily="Archivo, sans-serif"
            >
              {label}
            </text>
          </g>
        );
      })}
      {/* center */}
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
  const [summary, setSummary] = useState<UnknownsSummary | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let live = true;
    loadUnknownsSummary()
      .then((d) => {
        if (live) {
          if (d === null) setUnavailable(true);
          else setSummary(d);
        }
      })
      .catch(() => {
        if (live) setUnavailable(true);
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section style={{ borderBottom: `1px solid ${C.line}` }}>
      <Container className="py-12 sm:py-16 lg:py-20">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <p
              className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.22em]"
              style={{ color: C.amber }}
            >
              Hami · हामी
            </p>
            <h1
              className="mt-5 text-[clamp(2.4rem,5.5vw,4.5rem)] font-extrabold leading-[1.05] tracking-tight"
              style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
            >
              Discover what matters.
              <br />
              Understand it.{" "}
              <span style={{ color: C.amber }}>Act on it.</span>
            </h1>
            <p
              className="mt-6 max-w-xl text-lg leading-8"
              style={{ fontFamily: "'Source Sans 3', sans-serif", color: C.text }}
            >
              Hami is a living system that understands what people need and turns understanding
              into real value.
            </p>
            <p
              className="mt-2 max-w-xl text-base leading-7"
              style={{ fontFamily: "'Noto Sans Devanagari', sans-serif", color: C.muted }}
            >
              हामी एउटा जीवित प्रणाली हो जसले मानिसहरूलाई के चाहिन्छ भन्ने बुझ्छ र बुझाइलाई
              वास्तविक मूल्यमा बदल्छ।
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
            <p className="mt-4 text-xs" style={{ color: C.muted }}>
              Last loop completed:{" "}
              {unavailable ? (
                <span>unavailable</span>
              ) : summary?.last_loop ? (
                <span style={{ color: C.text }}>{summary.last_loop}</span>
              ) : (
                <span>checking…</span>
              )}
            </p>
          </div>
        </div>
      </Container>
    </section>
  );
}

/* 2. Six primitives strip */

function PrimitivesStrip() {
  return (
    <section style={{ borderBottom: `1px solid ${C.line}`, background: C.panel }}>
      <Container className="py-8 sm:py-10">
        <div className="grid grid-cols-2 gap-px sm:grid-cols-3 lg:grid-cols-6" style={{ background: C.line }}>
          {PRIMITIVES.map((p) => (
            <div key={p.name} className="p-4" style={{ background: C.panel }}>
              <h3
                className="text-sm font-bold uppercase tracking-[0.12em]"
                style={{ fontFamily: "Archivo, sans-serif", color: C.amber }}
              >
                {p.name}
              </h3>
              <p className="mt-1.5 text-xs leading-5" style={{ color: C.muted }}>
                {p.def}
              </p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}

/* 3. The power of the unknown — counts by state from the API */

const STATE_ORDER: UnknownState[] = [
  "UNKNOWN",
  "HYPOTHESIZED",
  "TESTED",
  "SUPPORTED",
  "CONTRADICTED",
  "BLOCKED_BY_MISSING_ACCESS",
];

function PowerOfUnknown() {
  const [summary, setSummary] = useState<UnknownsSummary | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let live = true;
    loadUnknownsSummary()
      .then((d) => {
        if (live) {
          if (d === null) setUnavailable(true);
          else setSummary(d);
        }
      })
      .catch(() => {
        if (live) setUnavailable(true);
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section style={{ borderBottom: `1px solid ${C.line}` }}>
      <Container className="py-10 sm:py-14">
        <div className="max-w-4xl">
          <h2
            className="text-3xl font-extrabold tracking-tight sm:text-4xl"
            style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
          >
            The power of the unknown.
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7" style={{ color: C.muted }}>
            Known things are commodities — everything known is known by everyone. The unknowns are
            the asset: questions reality hasn&apos;t answered yet.
          </p>
          {unavailable ? (
            <p className="mt-6 text-sm" style={{ color: C.muted }}>
              Unknown counts unavailable right now.
            </p>
          ) : !summary ? (
            <p className="mt-6 text-sm" style={{ color: C.muted }}>
              Counting recorded unknowns…
            </p>
          ) : (
            <dl className="mt-8 grid grid-cols-2 gap-px sm:grid-cols-3" style={{ background: C.line }}>
              {STATE_ORDER.map((s) => (
                <div key={s} className="p-5" style={{ background: C.panel }}>
                  <dt
                    className="text-xs font-bold uppercase tracking-[0.14em]"
                    style={{ color: C.muted }}
                  >
                    {UNKNOWN_STATE_LABELS[s]}
                  </dt>
                  <dd
                    className="mt-1 text-4xl font-extrabold"
                    style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
                  >
                    {summary.counts[s] ?? 0}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <Link
            to="/unknowns"
            className="mt-6 inline-flex min-h-10 items-center gap-1 text-sm font-bold"
            style={{ color: C.amber }}
          >
            Open the unknowns <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </Container>
    </section>
  );
}

/* 4. Very big, very small — the climb */

const CLIMB_STEPS = [
  {
    n: 1,
    title: "One seller, one week",
    body: "Experiment 1: can faster replies recover real sales for one seller? No seller has agreed yet — it remains proposed.",
    link: { to: "/prototype/inbox" as const, label: "Try the free inbox tool" },
    earned: true,
  },
  { n: 2, title: "Ten sellers", body: "[when earned]", earned: false },
  { n: 3, title: "A repeatable week", body: "[when earned]", earned: false },
  { n: 4, title: "A local playbook", body: "[when earned]", earned: false },
  { n: 5, title: "Everywhere", body: "[when earned]", earned: false },
] as const;

function VeryBigVerySmall() {
  return (
    <section style={{ borderBottom: `1px solid ${C.line}`, background: C.panel }}>
      <Container className="py-10 sm:py-14">
        <div className="max-w-4xl">
          <h2
            className="text-3xl font-extrabold tracking-tight sm:text-4xl"
            style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
          >
            Very big, very small.
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7" style={{ color: C.muted }}>
            The big aim and the small aim are the same aim at different scales. Each step is
            earned by the one before it — nothing is claimed in advance.
          </p>
          <ol className="mt-8 space-y-0">
            {CLIMB_STEPS.map((s) => (
              <li
                key={s.n}
                className="flex gap-5 border-t py-5"
                style={{ borderColor: C.line, opacity: s.earned ? 1 : 0.45 }}
              >
                <span
                  className="font-mono text-sm font-bold"
                  style={{ color: s.earned ? C.amber : C.muted }}
                >
                  {String(s.n).padStart(2, "0")}
                </span>
                <div>
                  <h3
                    className="font-bold"
                    style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
                  >
                    {s.title}
                  </h3>
                  {s.earned ? (
                    <>
                      <p className="mt-1 max-w-2xl text-sm leading-6" style={{ color: C.muted }}>
                        {s.body}
                      </p>
                      {"link" in s && s.link && (
                        <Link
                          to={s.link.to}
                          className="mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-bold"
                          style={{ color: C.amber }}
                        >
                          {s.link.label} <ArrowRight className="size-4" aria-hidden="true" />
                        </Link>
                      )}
                    </>
                  ) : (
                    <p className="mt-1 text-sm italic" style={{ color: C.muted }}>
                      when earned
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </Container>
    </section>
  );
}

/* 5. What we have learned — findings from the API only */

function chipFor(epistemic: string): { label: string; color: string } {
  const e = epistemic.toLowerCase();
  if (e.includes("support")) return { label: "Supported", color: "#72d38f" };
  if (e.includes("hypothes")) return { label: "Hypothesis", color: "#c4b5fd" };
  return { label: "Observed", color: C.amber };
}

function WhatWeHaveLearned() {
  const [items, setItems] = useState<PublicDiscovery[] | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let live = true;
    loadDiscoveries(4)
      .then((d) => {
        if (live) {
          if (d === null) setUnavailable(true);
          else setItems(d);
        }
      })
      .catch(() => {
        if (live) setUnavailable(true);
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section style={{ borderBottom: `1px solid ${C.line}` }}>
      <Container className="py-10 sm:py-14">
        <div className="max-w-4xl">
          <h2
            className="text-3xl font-extrabold tracking-tight sm:text-4xl"
            style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
          >
            What we have learned.
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-7" style={{ color: C.muted }}>
            Only what the record actually holds — with source and date. A sourced observation is
            not automatically a verified claim.
          </p>
          {unavailable ? (
            <p className="mt-6 text-sm" style={{ color: C.muted }}>
              Findings unavailable right now.
            </p>
          ) : !items ? (
            <p className="mt-6 text-sm" style={{ color: C.muted }}>
              Checking the record…
            </p>
          ) : items.length === 0 ? (
            <p className="mt-6 text-sm font-bold" style={{ color: C.text }}>
              Nothing recorded yet.
            </p>
          ) : (
            <ul className="mt-8 space-y-4">
              {items.map((item) => {
                const chip = chipFor(item.epistemic_state || "");
                return (
                  <li
                    key={item.id}
                    className="border p-5"
                    style={{ borderColor: C.line, background: C.panel }}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="rounded-full border px-2 py-0.5 text-xs font-semibold"
                        style={{ borderColor: chip.color, color: chip.color }}
                      >
                        {chip.label}
                      </span>
                      <span className="text-xs" style={{ color: C.muted }}>
                        {item.source}
                        {item.retrieved_at
                          ? ` · ${new Date(item.retrieved_at).toISOString().slice(0, 10)}`
                          : ""}
                      </span>
                    </div>
                    <h3
                      className="mt-2 font-bold leading-6"
                      style={{ fontFamily: "Archivo, sans-serif", color: C.text }}
                    >
                      {item.title || "Untitled observation"}
                    </h3>
                    <p className="mt-1.5 max-w-3xl text-sm leading-6" style={{ color: C.muted }}>
                      {item.excerpt}
                    </p>
                    {item.canonical_url && (
                      <a
                        href={item.canonical_url}
                        className="mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-bold"
                        style={{ color: C.amber }}
                      >
                        View source <ArrowUpRight className="size-4" aria-hidden="true" />
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </Container>
    </section>
  );
}

/* 6. Footer — honest status, contact only if real */

function HomeFooter() {
  return (
    <footer style={{ background: C.panel }}>
      <Container className="py-8">
        <p className="max-w-2xl text-sm font-bold leading-6" style={{ color: C.text }}>
          Honest status: Hami is pre-revenue. Experiment 1 remains proposed; there are no
          participants or results to report.
        </p>
        <p className="mt-2 text-xs" style={{ color: C.muted }}>
          © 2026 Hami · Built in Kathmandu, serving everywhere equally.
        </p>
      </Container>
    </footer>
  );
}
