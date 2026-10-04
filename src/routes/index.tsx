import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { loadDiscoveries, type PublicDiscovery } from "@/lib/content";

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
        content:
          "Hami is a living system that understands what people need and turns understanding into real value.",
      },
      { name: "apple-mobile-web-app-title", content: "Hami" },
    ],
  }),
});

const FOUR_LINES = [
  {
    en: ["Observes", "sees what is happening in the real world."],
    ne: ["अवलोकन", "वास्तविक संसारमा के भइरहेको छ भनेर हेर्छ।"],
  },
  {
    en: ["Keeps evidence and uncertainty", "separates what is known from what is not."],
    ne: ["प्रमाण र अनिश्चितता राख्छ", "के थाहा छ र के थाहा छैन भनेर छुट्याउँछ।"],
  },
  {
    en: ["Acts only when authorized", "no external action without permission."],
    ne: ["अनुमति पाएपछि मात्र काम गर्छ", "बिना अनुमति बाह्य कार्य गर्दैन।"],
  },
  {
    en: ["Learns from outcomes", "what actually happens changes what Hami knows and can do next."],
    ne: ["परिणामबाट सिक्छ", "वास्तवमा के हुन्छ त्यसले हामीको ज्ञान र क्षमता बदल्छ।"],
  },
] as const;

const SYSTEM_FLOW = [
  {
    stage: "SYSTEM",
    title: "Purpose and boundaries",
    description: "One shared system; recorded information does not authorize action.",
    to: "/about",
    action: "About Hami",
  },
  {
    stage: "WORLD",
    title: "Public observations",
    description: "Source observations stay separate from verified claims.",
    to: "/discoveries",
    action: "View discoveries",
  },
  {
    stage: "OPPORTUNITIES",
    title: "Evidence-gated hypotheses",
    description: "A possibility is not validated demand or a buyer.",
    to: "/opportunities",
    action: "Explore opportunities",
  },
  {
    stage: "CAPABILITIES",
    title: "Public capability records",
    description: "Shown only for verified providers with active public service listings.",
    to: "/feed",
    action: "Explore the network",
  },
  {
    stage: "ACTION",
    title: "Recorded action state",
    description: "Aggregate status is not authorization or execution.",
    to: "/actions",
    action: "View action state",
  },
  {
    stage: "OUTCOMES",
    title: "Findings with sources",
    description: "Recorded findings keep their truth state; no result is assumed.",
    to: "/what-we-learned",
    action: "Read what is recorded",
  },
] as const;

function HomePage() {
  return (
    <main className="bg-night text-ink">
      <Identity />
      <FourLines />
      <SystemScope />
      <RecordedObservations />
      <CurrentActivity />
      <HonestStatus />
    </main>
  );
}

/* 1. Hami identity — the headline, in the original dark/gold voice */

function Identity() {
  return (
    <section className="relative isolate overflow-hidden bg-night">
      <div className="hero-glow -z-10" aria-hidden="true" />
      <div className="hero-grain -z-10" aria-hidden="true" />
      <Container className="py-10 sm:py-14 lg:py-16">
        {/* Ornate gold frame, as the original */}
        <div className="relative border-2 border-accent/70 px-6 py-10 sm:px-10 sm:py-14 lg:px-16">
          <div
            className="pointer-events-none absolute inset-2 border border-accent/30"
            aria-hidden="true"
          />
          <div className="relative mx-auto max-w-4xl text-center">
            <p className="inline-block border border-accent/50 px-3 py-1 font-mono text-[0.68rem] font-bold uppercase tracking-[0.22em] text-accent">
              Hami · Living System
            </p>
            <h1 className="mt-6 font-gothic text-[clamp(2rem,5.2vw,4.4rem)] leading-[1.08] text-ink">
              Hami is a living system that understands what people need and turns understanding into
              real value.
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-ink/70">
              हामी एउटा जीवित प्रणाली हो जसले मानिसहरूलाई के चाहिन्छ भन्ने बुझ्छ र बुझाइलाई वास्तविक
              मूल्यमा बदल्छ।
            </p>
            <p className="mt-6 text-sm font-bold uppercase tracking-[0.18em] text-accent">
              Built in Kathmandu. Serving everywhere equally.
            </p>
            <p className="mt-1 text-sm text-ink/60">काठमाडौंमा बनेको। सबैका लागि समान रूपमा सेवा।</p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/about"
                className="inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-black bg-accent px-6 font-extrabold text-black transition-colors hover:bg-warning"
              >
                Explore the system <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                to="/discoveries"
                className="inline-flex min-h-12 items-center gap-2 rounded-card border-2 border-ink/40 bg-transparent px-6 font-bold text-ink transition-colors hover:border-accent hover:text-accent"
              >
                Public record
              </Link>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}

/* 2. Four plain lines, in the dark voice */

function FourLines() {
  return (
    <section aria-label="What Hami does" className="border-t border-accent/20 bg-night py-10 sm:py-14">
      <Container>
        <ul className="mx-auto grid max-w-5xl gap-4 sm:grid-cols-2">
          {FOUR_LINES.map(({ en, ne }) => (
            <li
              key={en[0]}
              className="border border-accent/25 bg-black/40 p-5 transition-colors hover:border-accent/60"
            >
              <p className="text-base font-extrabold leading-7 text-ink">
                {en[0]} <span className="font-normal text-ink/60">— {en[1]}</span>
              </p>
              <p className="mt-2 text-sm leading-6 text-ink/50">
                {ne[0]} — {ne[1]}
              </p>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}

/* 3. An open-ended system, not a fixed sequence */

function SystemScope() {
  return (
    <section
      aria-labelledby="system-scope-title"
      className="border-t border-accent/20 bg-night py-10 sm:py-14"
    >
      <Container>
        <div className="mx-auto max-w-4xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.22em] text-accent">
            In contact with reality
          </p>
          <h2
            id="system-scope-title"
            className="mt-3 font-gothic text-3xl leading-tight text-ink sm:text-4xl"
          >
            Reality is not pre-sorted.
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-7 text-ink/70 sm:text-lg sm:leading-8">
            Needs, unused capability, opportunities, mismatches, constraints, relationships,
            resources, and problems worth solving meet in many different ways. Hami looks for what
            matters in those real situations and what might lead to a useful outcome. These are
            things the system can investigate, not discoveries claimed here.
          </p>
          <p className="mt-4 max-w-3xl text-base leading-7 text-ink/70 sm:text-lg sm:leading-8">
            Hami can prepare different ways to help as its understanding and capabilities grow. It
            keeps evidence alongside uncertainty, acts externally only when authorized, and learns
            from actual outcomes. These capacities can inform one another; no fixed sequence or
            single product defines the system.
          </p>
        </div>
        <section aria-labelledby="operating-map-title" className="mx-auto mt-8 max-w-6xl">
          <div className="flex flex-col gap-3 border-y border-accent/25 py-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.2em] text-accent">
                One way to follow the system
              </p>
              <h3 id="operating-map-title" className="mt-2 font-gothic text-2xl leading-tight text-ink sm:text-3xl">
                From reality to recorded learning
              </h3>
            </div>
            <p className="max-w-xl text-sm leading-6 text-ink/60">
              An open map, not a fixed funnel. These links show where each view lives, not that
              every stage has happened.
            </p>
          </div>
          <ol aria-label="System, world, opportunities, capabilities, action, and outcomes" className="grid gap-x-8 sm:grid-cols-2 xl:grid-cols-3">
            {SYSTEM_FLOW.map((step, index) => (
              <li key={step.stage} className="border-t border-accent/25">
                <Link to={step.to} className="group flex min-h-44 flex-col py-4 sm:py-5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-ink/45">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="font-mono text-[0.65rem] font-bold uppercase tracking-[0.12em] text-accent">
                      {step.stage}
                    </span>
                    <ArrowUpRight className="ml-auto size-4 text-ink/40 transition-colors group-hover:text-accent" aria-hidden="true" />
                  </div>
                  <h4 className="mt-3 font-display text-lg font-bold leading-6 text-ink group-hover:text-accent">
                    {step.title}
                  </h4>
                  <p className="mt-2 flex-1 text-sm leading-6 text-ink/60">{step.description}</p>
                  <span className="mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent">
                    {step.action} <ArrowRight className="size-4" aria-hidden="true" />
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      </Container>
    </section>
  );
}

/* 4. Public observations shown only when present in the existing record */

function RecordedObservations() {
  const [items, setItems] = useState<PublicDiscovery[] | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let live = true;
    void loadDiscoveries(4)
      .then((data) => {
        if (live) {
          setItems(data);
          setReady(true);
        }
      })
      .catch(() => {
        if (live) {
          setItems(null);
          setReady(true);
        }
      });
    return () => {
      live = false;
    };
  }, []);

  return (
    <section
      aria-labelledby="recorded-observations-title"
      className="border-t border-accent/20 bg-night py-10 sm:py-14"
    >
      <Container>
        <div className="mx-auto max-w-4xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.22em] text-accent">
            From the public record
          </p>
          <h2
            id="recorded-observations-title"
            className="mt-3 font-gothic text-3xl leading-tight text-ink sm:text-4xl"
          >
            What is actually recorded
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-ink/60">
            Only stored public observations appear here, with their source and recorded state. A
            sourced observation is not automatically a verified claim.
          </p>

          {!ready && (
            <div className="mt-6 border-t border-accent/20 py-5" aria-busy="true">
              <p className="text-sm text-ink/60">Checking the public record…</p>
            </div>
          )}
          {ready && items === null && (
            <div className="mt-6 border-t border-accent/20 py-5" role="status">
              <p className="font-bold text-ink">The public record is unavailable right now.</p>
              <p className="mt-1 text-sm text-ink/60">
                Hami could not check for observations, so their presence or absence cannot be
                confirmed.
              </p>
            </div>
          )}
          {ready && items?.length === 0 && (
            <div className="mt-6 border-t border-accent/20 py-5">
              <p className="font-bold text-ink">
                Nothing is recorded in this public observation record yet.
              </p>
            </div>
          )}
          {ready && items && items.length > 0 && (
            <ol className="mt-6 divide-y divide-accent/20 border-y border-accent/20">
              {items.map((item) => (
                <li key={item.id} className="py-5">
                  <article>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-semibold text-ink/50">
                      <span>{item.source}</span>
                      <span>{item.epistemic_state}</span>
                      <span>{item.freshness || "freshness unknown"}</span>
                    </div>
                    <h3 className="mt-2 font-display text-lg font-bold leading-6 text-ink">
                      {item.title || "Untitled observation"}
                    </h3>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/60">{item.excerpt}</p>
                    {item.canonical_url && (
                      <a
                        href={item.canonical_url}
                        className="mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent hover:text-ink"
                      >
                        View source
                        <ArrowUpRight className="size-4" aria-hidden="true" />
                      </a>
                    )}
                  </article>
                </li>
              ))}
            </ol>
          )}
          {ready && items && items.length > 0 && (
            <Link
              to="/discoveries"
              className="mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent hover:text-ink"
            >
              Open the public record
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          )}
        </div>
      </Container>
    </section>
  );
}

/* 5. One small investigation, subordinate to the system and its record */

function CurrentActivity() {
  return (
    <section
      aria-labelledby="current-activity-title"
      className="border-t border-accent/20 bg-night py-6 sm:py-8"
    >
      <Container>
        <div className="mx-auto max-w-3xl border border-accent/25 bg-black/40 p-5">
          <p className="font-mono text-[0.65rem] font-bold uppercase tracking-[0.18em] text-ink/50">
            One proposed investigation · not started
          </p>
          <h2 id="current-activity-title" className="mt-2 font-display text-xl font-bold text-ink">
            Currently exploring
          </h2>
          <p className="mt-2 text-sm leading-6 text-ink/60">
            Experiment 1 asks whether faster replies could recover sales for one seller. No seller
            has agreed and no messages have been handled; it is one small investigation, not Hami's
            identity or a live offer.
          </p>
          <Link
            to="/needs"
            className="mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent hover:text-ink"
          >
            Read its scope
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </Container>
    </section>
  );
}

/* 6. Honest current state */

function HonestStatus() {
  return (
    <section aria-label="Status" className="border-t border-accent/20 bg-night py-8 sm:py-10">
      <Container>
        <p className="mx-auto max-w-2xl border-l-4 border-accent pl-4 text-sm font-bold leading-6 text-ink">
          Honest status: Hami is pre-revenue. Experiment 1 remains proposed; there are no
          participants or results to report.
        </p>
      </Container>
    </section>
  );
}
