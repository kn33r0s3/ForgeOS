import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";
import { fetchUnknowns, type ApiUnknown } from "@/lib/unknowns-api";

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
      <ExperimentOne />
      <EngineFindings />
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
            Hami is a living system that understands what people need and turns
            understanding into real value.
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-muted sm:text-xl">
            हामी एउटा जीवित प्रणाली हो जसले मानिसहरूलाई के चाहिन्छ भन्ने बुझ्छ
            र बुझाइलाई वास्तविक मूल्यमा बदल्छ।
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

/* 3. Running now — Experiment 1 */

function ExperimentOne() {
  return (
    <section aria-labelledby="running-now-title" className="border-b-2 border-black py-10 sm:py-14">
      <Container>
        <div className="max-w-3xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
            Running now
          </p>
          <h2 id="running-now-title" className="mt-2 font-display text-3xl font-black tracking-tight text-ink">
            Experiment 1
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            One current experiment inside Hami — not Hami itself.
          </p>
          <div className="card mt-6 p-6">
            <h3 className="font-display text-xl font-bold text-ink">
              The slow-reply experiment
            </h3>
            <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
              When a customer messages a shop and nobody replies fast, a sale
              can be lost quietly. For one week, a person handles replies
              within minutes; payment is tied to sales that actually come back
              because of the faster replies.
            </p>
            <p className="mt-3 max-w-2xl text-base leading-7 text-muted">
              जब ग्राहकले सन्देश पठाउँदा छिटो जवाफ आउँदैन, बिक्री खेर जान
              सक्छ। एक हप्ता एक व्यक्तिले केही मिनेटभित्र जवाफहरू सम्हाल्छ;
              छिटो जवाफका कारण फर्केका बिक्रीमा मात्र शुल्क लाग्छ।
            </p>
            <div className="mt-5 flex flex-col items-start gap-2">
              <Button asChild size="lg">
                <Link to="/prototype/inbox">
                  Try the free inbox tool
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
              <p className="text-sm text-muted">No signup.</p>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}

/* 4. What the engine has found — API-backed only */

function EngineFindings() {
  const [items, setItems] = useState<ApiUnknown[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchUnknowns()
      .then((data) => {
        if (live) setItems(data);
      })
      .catch((e: unknown) => {
        if (live) setError(e instanceof Error ? e.message : "unavailable");
      });
    return () => {
      live = false;
    };
  }, []);

  const shown = (items ?? []).slice(0, 4);

  return (
    <section aria-labelledby="engine-found-title" className="border-b-2 border-black bg-card py-10 sm:py-14">
      <Container>
        <div className="max-w-4xl">
          <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.16em] text-accent">
            From the engine
          </p>
          <h2 id="engine-found-title" className="mt-2 font-display text-3xl font-black tracking-tight text-ink">
            What the engine has found
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
            Only what the engine has recorded — each finding with its truth
            state and source. Nothing here was written for this page.
          </p>

          {error !== null && (
            <div className="card mt-6 p-5" role="alert">
              <p className="font-bold text-ink">The engine did not answer.</p>
              <p className="mt-1 text-sm text-muted">
                Findings are unavailable right now ({error}). This section will
                not invent them.
              </p>
            </div>
          )}
          {error === null && items === null && (
            <div className="card mt-6 p-5" aria-busy="true">
              <p className="text-sm text-muted">Loading recorded findings…</p>
            </div>
          )}
          {error === null && items !== null && items.length === 0 && (
            <div className="card mt-6 p-5">
              <p className="font-bold text-ink">Nothing recorded yet.</p>
              <p className="mt-1 text-sm text-muted">
                The engine has not banked any findings. When it does, they
                appear here with their truth state and source.
              </p>
            </div>
          )}
          {error === null && items !== null && items.length > 0 && (
            <>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {shown.map((u) => (
                  <article key={u.id} className="card p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold text-accent">{u.row_id}</span>
                      <span className="rounded-full border border-line bg-background px-2 py-0.5 text-xs font-semibold text-muted">
                        {u.epistemic_state}
                      </span>
                    </div>
                    <h3 className="mt-2 font-display text-base font-bold leading-6 text-ink">
                      {u.question}
                    </h3>
                    {u.provenance && (
                      <p className="mt-2 text-xs leading-5 text-dim">
                        Source: {u.provenance.split(". Cheapest test:")[0]}
                      </p>
                    )}
                  </article>
                ))}
              </div>
              <Link
                to="/what-we-learned"
                className="link-arrow mt-5 inline-flex min-h-10 items-center gap-1 text-sm font-bold text-accent"
              >
                See everything the engine has recorded
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </>
          )}
        </div>
      </Container>
    </section>
  );
}

/* 5. Honest status */

function HonestStatus() {
  return (
    <section aria-label="Status" className="py-10 sm:py-12">
      <Container>
        <p className="max-w-2xl border-l-4 border-accent pl-4 text-sm font-bold leading-6 text-ink">
          Honest status: Hami is pre-revenue and has not yet served a seller.
          Experiment 1 starts with one seller, for one week.
        </p>
      </Container>
    </section>
  );
}
