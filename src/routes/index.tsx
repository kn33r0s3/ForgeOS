import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({
    meta: [
      { title: "Hami" },
      {
        name: "description",
        content:
          "Hami helps Nepali online sellers never miss a sale to a slow reply. Pre-revenue — no sellers served yet.",
      },
      { property: "og:title", content: "Hami" },
      {
        property: "og:description",
        content:
          "Hami helps Nepali online sellers never miss a sale to a slow reply.",
      },
      { name: "apple-mobile-web-app-title", content: "Hami" },
    ],
  }),
});

function HomePage() {
  return (
    <main>
      <section className="relative isolate overflow-hidden border-b-2 border-black">
        <div className="hero-glow -z-10" aria-hidden="true" />
        <div className="hero-grain -z-10" aria-hidden="true" />
        <Container className="py-12 sm:py-16 lg:py-20">
          <div className="max-w-3xl">
            <p className="font-mono text-[0.72rem] font-bold uppercase tracking-[0.18em] text-accent">
              Hami · हामी
            </p>
            <h1 className="mt-5 text-[clamp(2.6rem,5.8vw,5rem)] font-black leading-[0.98] tracking-[-0.045em] text-ink">
              Never miss a sale to a slow reply.
            </h1>
            <p className="mt-3 text-[clamp(1.4rem,3vw,2rem)] font-bold leading-snug text-muted">
              ढिलो जवाफले बिक्री नगुमाउनुहोस्।
            </p>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
              When a customer messages your shop and nobody replies fast, the
              sale dies quietly. For one week, a person handles your replies
              within minutes — you pay only for the sales that come back
              because of the fast replies.
            </p>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
              जब ग्राहकले सन्देश पठाउँदा छिटो जवाफ आउँदैन, बिक्री खेर जान्छ।
              एक हप्ता हामी तपाईंका जवाफहरू छिटो सम्हाल्छौं — फर्केका बिक्रीमा
              मात्र शुल्क लाग्छ।
            </p>
            <p className="mt-6 max-w-2xl border-l-4 border-accent pl-4 text-sm font-bold leading-6 text-ink">
              Honest status: Hami is pre-revenue. No sellers served yet — the
              first sprint starts when one seller is named.
            </p>
            <div className="mt-6 flex flex-col items-start gap-2">
              <Button asChild size="lg">
                <Link to="/prototype/inbox">
                  Try the free inbox tool
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
              <p className="text-sm text-muted">
                No signup. Your data stays in your browser.
              </p>
            </div>
          </div>
        </Container>
      </section>
    </main>
  );
}
