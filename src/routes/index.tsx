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

function HomePage() {
  return (
    <main>
      <Identity />
      <FourLines />
      <SystemScope />
      <RecordedObservations />
      <CurrentActivity />
      <HonestStatus />
    </main>
  );
}

/* 1. Hami identity — the headline */

function Identity() {
  return (
    <section className="relative isolate overflow-hidden border-b-2 border-black">
      <div className="hero-glow -z-10" aria-hidden="true" />
      <div className="hero-grain -z-10" aria-hidden="true" />
      <Container className="py-12 sm:py-16 lg:py-20">
        <div className="max-w-3xl">
          <p className="font-mono text-[0.72rem] font-bold uppercase tracking-[0.18em] text-accent">
            Hami · हामी
          </p>
          <h1 className="mt-5 text-[clamp(2.2rem,5vw,4.2rem)] font-black leading-[1.02] tracking-[-0.04em] text-ink">
            Hami is a living system that understands what people need and turns understanding into
            real value.
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-muted sm:text-xl">
            हामी एउटा जीवित प्रणाली हो जसले मानिसहरूलाई के चाहिन्छ भन्ने बुझ्छ र बुझाइलाई वास्तविक
            मूल्यमा बदल्छ।
          </p>
          <p className="mt-6 max-w-2xl text-base font-bold leading-7 text-ink">
            Built in Kathmandu. Serving everywhere equally.
          </p>
          <p className="mt-1 max-w-2xl text-base leading-7 text-muted">
            काठमाडौंमा बनेको। सबैका लागि समान रूपमा सेवा।
          </p>
        </div>
      </Container>
    </section>
  );
}

/* 2. Four plain lines */

function FourLines() {
  return (
    <section aria-label="What Hami does" className="border-b-2 border-black bg-card py-10 sm:py-14">
      <Container>
        <ul className="grid max-w-4xl gap-4 sm:grid-cols-2">
          {FOUR_LINES.map(({ en, ne }) => (
            <li key={en[0]} className="card p-5">
              <p className="text-base font-extrabold leading-7 text-ink">
                {en[0]} <span className="font-normal text-muted">— {en[1]}</span>
              </p>
              <p className="mt-2 text-sm leading-6 text-muted">
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
      className="border-b-2 border-black py-10 sm:py-14"
    >
      <Container>
        <div className="max-w-4xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
            In contact with reality
          </p>
          <h2
            id="system-scope-title"
            className="mt-2 font-display text-3xl font-black tracking-tight text-ink"
          >
            Reality is not pre-sorted.
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
            Needs, unused capability, opportunities, mismatches, constraints, relationships,
            resources, and problems worth solving meet in many different ways. Hami looks for what
            matters in those real situations and what might lead to a useful outcome. These are
            things the system can investigate, not discoveries claimed here.
          </p>
          <p className="mt-4 max-w-3xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
            Hami can prepare different ways to help as its understanding and capabilities grow. It
            keeps evidence alongside uncertainty, acts externally only when authorized, and learns
            from actual outcomes. These capacities can inform one another; no fixed sequence or
            single product defines the system.
          </p>
        </div>
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
      className="border-b-2 border-black bg-card py-10 sm:py-14"
    >
      <Container>
        <div className="max-w-4xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
            From the public record
          </p>
          <h2
            id="recorded-observations-title"
            className="mt-2 font-display text-3xl font-black tracking-tight text-ink"
          >
            What is actually recorded
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
            Only stored public observations appear here, with their source and recorded state. A
            sourced observation is not automatically a verified claim.
          </p>

          {!ready && (
            <div className="mt-6 border-t border-line py-5" aria-busy="true">
              <p className="text-sm text-muted">Checking the public record…</p>
            </div>
          )}
          {ready && items === null && (
            <div className="mt-6 border-t border-line py-5" role="status">
              <p className="font-bold text-ink">The public record is unavailable right now.</p>
              <p className="mt-1 text-sm text-muted">
                Hami could not check for observations, so their presence or absence cannot be
                confirmed.
              </p>
            </div>
          )}
          {ready && items?.length === 0 && (
            <div className="mt-6 border-t border-line py-5">
              <p className="font-bold text-ink">
                Nothing is recorded in this public observation record yet.
              </p>
            </div>
          )}
          {ready && items && items.length > 0 && (
            <ol className="mt-6 divide-y divide-line border-y border-line">
              {items.map((item) => (
                <li key={item.id} className="py-5">
                  <article>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-semibold text-dim">
                      <span>{item.source}</span>
                      <span>{item.epistemic_state}</span>
                      <span>{item.freshness || "freshness unknown"}</span>
                    </div>
                    <h3 className="mt-2 font-display text-lg font-bold leading-6 text-ink">
                      {item.title || "Untitled observation"}
                    </h3>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{item.excerpt}</p>
                    {item.canonical_url && (
                      <a
                        href={item.canonical_url}
                        className="link-arrow mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
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
              className="link-arrow mt-4 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
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
    <section aria-labelledby="current-activity-title" className="border-b border-line py-6 sm:py-8">
      <Container>
        <div className="max-w-3xl">
          <p className="font-mono text-[0.65rem] font-bold uppercase tracking-[0.16em] text-dim">
            One proposed investigation · not started
          </p>
          <h2 id="current-activity-title" className="mt-2 font-display text-xl font-bold text-ink">
            Currently exploring
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            Experiment 1 asks whether faster replies could recover sales for one seller. No seller
            has agreed and no messages have been handled; it is one small investigation, not Hami's
            identity or a live offer.
          </p>
          <Link
            to="/needs"
            className="link-arrow mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
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
    <section aria-label="Status" className="py-8 sm:py-10">
      <Container>
        <p className="max-w-2xl border-l-4 border-accent pl-4 text-sm font-bold leading-6 text-ink">
          Honest status: Hami is pre-revenue. Experiment 1 remains proposed; there are no
          participants or results to report.
        </p>
      </Container>
    </section>
  );
}
