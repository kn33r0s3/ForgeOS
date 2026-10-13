import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
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
import {
  clearStoredCheckoutAttempt,
  createCheckoutAttemptKey,
  readStoredCheckoutAttempt,
  writeStoredCheckoutAttempt,
  type CheckoutProvider,
  type StoredCheckoutAttempt,
} from "@/lib/checkout-attempt-storage";

export const Route = createFileRoute("/")({
  component: HomePage,
  head: () => ({
    meta: [
      { title: "Hami" },
      {
        name: "description",
        content:
          "Hami is a living system for understanding needs, knowledge, capabilities, resources, and outcomes across domains. Built in Kathmandu. Serving everywhere equally; action stays evidence-led and authorized.",
      },
      { property: "og:title", content: "Hami" },
      {
        property: "og:description",
        content: "Discover what matters. Understand it. Act on it. Built in Kathmandu; serving everywhere equally.",
      },
      { name: "apple-mobile-web-app-title", content: "Hami" },
    ],
  }),
});

type PublicPaymentOffer = {
  id: number;
  name: string;
  offer: string;
  pricing: string;
  currency: "NPR";
  amount_paisa: number;
  checkout_enabled: boolean;
  providers: Array<"esewa" | "khalti">;
};

type CheckoutRecoveryResponse = {
  intent: string | null;
  offer_id: number;
  provider: CheckoutProvider | null;
  status: string;
  retry_allowed: boolean;
  recovery: {
    checked: boolean;
    retry_allowed: boolean;
    provider_status: string | null;
    message: string;
  };
};

type PublicCheckoutResponse = {
  intent: string;
  status: string;
  amount_paisa: number;
  amount_npr: string;
  currency: "NPR";
  product_name: string;
  checkout: null | (
    | { type: "form_post"; url: string; fields: Record<string, string> }
    | { type: "redirect"; url: string }
  );
};

type CheckoutAttemptError = {
  offerId: number;
  provider: CheckoutProvider;
  message: string;
  retryable: boolean;
  newAttempt?: boolean;
};

function PublicOffers() {
  const [offers, setOffers] = useState<PublicPaymentOffer[] | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [keys, setKeys] = useState<Record<number, string>>({});
  const [providersByOffer, setProvidersByOffer] = useState<Record<number, CheckoutProvider>>({});
  const [error, setError] = useState<CheckoutAttemptError | null>(null);

  useEffect(() => {
    let current = true;
    fetch("/api/payments/offers", { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Published offers are temporarily unavailable.");
        return (await response.json()) as PublicPaymentOffer[];
      })
      .then((items) => {
        if (!current) return;
        const availableOffers = Array.isArray(items) ? items : [];
        setOffers(availableOffers);
        const restoredKeys: Record<number, string> = {};
        const restoredProviders: Record<number, CheckoutProvider> = {};
        for (const offer of availableOffers) {
          const stored = readStoredCheckoutAttempt(offer.id);
          if (stored.state !== "stored") continue;
          restoredKeys[offer.id] = stored.attempt.key;
          restoredProviders[offer.id] = stored.attempt.provider;
        }
        setKeys(restoredKeys);
        setProvidersByOffer(restoredProviders);
      })
      .catch(() => { if (current) setOffers([]); });
    return () => { current = false; };
  }, []);

  async function reconcileCheckout(offer: PublicPaymentOffer) {
    if (busyId !== null) return;
    const storedRead = readStoredCheckoutAttempt(offer.id);
    const storedAttempt = storedRead.state === "stored" ? storedRead.attempt : null;
    const key = keys[offer.id] ?? storedAttempt?.key;
    const provider = providersByOffer[offer.id] ?? storedAttempt?.provider;
    if (!key || !provider) {
      setError({
        offerId: offer.id,
        provider: provider ?? "esewa",
        message: storedRead.state === "invalid" || storedRead.state === "unavailable"
          ? "Hami cannot verify this tab's saved checkout identity. To prevent a duplicate payment, no new attempt was started."
          : "No saved checkout identity is available to verify. Do not start another attempt from this message.",
        retryable: false,
      });
      return;
    }
    setBusyId(offer.id);
    setError(null);
    try {
      const response = await fetch("/api/payments/products/" + offer.id + "/checkout/reconcile", {
        method: "POST",
        headers: { "Idempotency-Key": key, Accept: "application/json" },
        cache: "no-store",
      });
      const payload = await response.json().catch(() => null) as
        | (CheckoutRecoveryResponse & { detail?: string })
        | null;
      if (!response.ok || !payload) {
        throw new Error(payload && typeof payload.detail === "string"
          ? payload.detail
          : "The provider could not confirm a safe retry. Keep the existing checkout attempt.");
      }
      if (payload.status === "VERIFIED" && payload.intent) {
        window.location.assign("/payment-result?intent=" + encodeURIComponent(payload.intent));
        return;
      }
      const recoveryMessage = payload.recovery?.message ?? "Provider status could not establish a safe retry.";
      if (payload.retry_allowed === true) {
        if (!clearStoredCheckoutAttempt(offer.id)) {
          setError({
            offerId: offer.id,
            provider,
            message: "The provider confirms the previous attempt ended, but this tab could not clear its saved attempt key. No new attempt was started.",
            retryable: false,
          });
          return;
        }
        setKeys((current) => {
          const nextKeys = { ...current };
          delete nextKeys[offer.id];
          return nextKeys;
        });
        setProvidersByOffer((current) => {
          const nextProviders = { ...current };
          delete nextProviders[offer.id];
          return nextProviders;
        });
        setError({
          offerId: offer.id,
          provider,
          message: recoveryMessage,
          retryable: true,
          newAttempt: true,
        });
        return;
      }
      setError({ offerId: offer.id, provider, message: recoveryMessage, retryable: false });
    } catch (cause) {
      setError({
        offerId: offer.id,
        provider,
        message: cause instanceof Error ? cause.message : "The provider could not confirm a safe retry.",
        retryable: false,
      });
    } finally {
      setBusyId(null);
    }
  }

  async function beginCheckout(offer: PublicPaymentOffer, provider: CheckoutProvider) {
    if (busyId !== null) return;
    const storedRead = readStoredCheckoutAttempt(offer.id);
    const storedAttempt = storedRead.state === "stored" ? storedRead.attempt : null;
    const existingKey = keys[offer.id] ?? storedAttempt?.key;
    const existingProvider = providersByOffer[offer.id] ?? storedAttempt?.provider;
    if (
      !existingKey &&
      (storedRead.state === "invalid" || storedRead.state === "unavailable")
    ) {
      setError({
        offerId: offer.id,
        provider,
        message: "Hami cannot verify this tab's saved checkout identity. To prevent a duplicate payment, no new attempt was started.",
        retryable: false,
      });
      return;
    }
    if (existingKey && !existingProvider) {
      setError({
        offerId: offer.id,
        provider,
        message: "The saved checkout key has no verified provider identity. No checkout request was sent.",
        retryable: false,
      });
      return;
    }
    if (existingKey && existingProvider && existingProvider !== provider) {
      setError({
        offerId: offer.id,
        provider: existingProvider,
        message: "This offer already has a checkout attempt with " +
          (existingProvider === "esewa" ? "eSewa" : "Khalti") +
          ". Retry that same attempt before switching providers.",
        retryable: true,
      });
      return;
    }
    const key = existingKey ?? createCheckoutAttemptKey();
    if (!key) {
      setError({
        offerId: offer.id,
        provider,
        message: "This browser cannot generate a secure checkout identity. No checkout request was sent.",
        retryable: false,
      });
      return;
    }
    setBusyId(offer.id);
    setError(null);
    const attempt: StoredCheckoutAttempt = { key, provider };
    setKeys((current) => ({ ...current, [offer.id]: key }));
    setProvidersByOffer((current) => ({ ...current, [offer.id]: provider }));
    if (!writeStoredCheckoutAttempt(offer.id, attempt)) {
      setError({
        offerId: offer.id,
        provider,
        message: "This browser cannot safely persist the checkout attempt. No checkout request was sent.",
        retryable: false,
      });
      setBusyId(null);
      return;
    }
    let retryable = true;
    try {
      const response = await fetch("/api/payments/products/" + offer.id + "/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": key,
        },
        body: JSON.stringify({ provider }),
      });
      const payload = await response.json().catch(() => null) as
        | (PublicCheckoutResponse & { detail?: string })
        | null;
      if (!response.ok) {
        retryable = false;
        throw new Error(payload && "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : "Checkout could not be started (" + response.status + ").");
      }
      if (!payload) {
        throw new Error("Checkout returned an incomplete response. Retry the same checkout attempt.");
      }
      if (!payload.checkout) {
        window.location.assign("/payment-result?intent=" + encodeURIComponent(payload.intent));
        return;
      }
      if (payload.checkout.type === "redirect") {
        const destination = new URL(payload.checkout.url);
        if (destination.protocol !== "https:") throw new Error("The payment provider returned a non-HTTPS destination.");
        window.location.assign(destination.toString());
        return;
      }
      if (payload.checkout.type === "form_post") {
        const destination = new URL(payload.checkout.url);
        if (destination.protocol !== "https:") throw new Error("The payment provider returned a non-HTTPS form destination.");
        const form = document.createElement("form");
        form.method = "POST";
        form.action = destination.toString();
        form.style.display = "none";
        for (const [name, value] of Object.entries(payload.checkout.fields)) {
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = name;
          input.value = value;
          form.appendChild(input);
        }
        document.body.appendChild(form);
        form.submit();
        return;
      }
      throw new Error("The payment provider returned an unsupported checkout flow.");
    } catch (cause) {
      setError({
        offerId: offer.id,
        provider,
        message: cause instanceof Error ? cause.message : "Checkout could not be started.",
        retryable,
      });
    } finally {
      setBusyId(null);
    }
  }

  if (offers === null || offers.length === 0) return null;

  return (
    <section className="border-b border-line bg-surface" aria-labelledby="published-offers-heading">
      <Container className="py-12 sm:py-16">
        <Eyebrow tone="amber">Published offers</Eyebrow>
        <h2 id="published-offers-heading" className="mt-3 font-display text-title font-extrabold tracking-tight text-ink">
          Offers that passed the evidence gate
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
          Only currently published products with verified demand appear here. Provider verification confirms payment; Hami records revenue only after an owner confirms the promised service or deliverable was fulfilled.
        </p>
        {error ? <p role="alert" className="mt-4 rounded-card border border-danger/60 p-3 text-sm">{error.message}</p> : null}
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {offers.map((offer) => (
            <article key={offer.id} className="rounded-card border-2 border-line bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <h3 className="text-lg font-extrabold">{offer.name}</h3>
                <span className="rounded border border-line px-2 py-1 font-mono text-xs">{offer.currency}</span>
              </div>
              <p className="mt-3 text-sm leading-6">{offer.offer}</p>
              <p className="mt-4 font-display text-2xl font-extrabold">{offer.pricing}</p>
              {offer.checkout_enabled && offer.providers.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {offer.providers.map((provider) => (
                    <button
                      key={provider}
                      type="button"
                      disabled={
                        busyId !== null ||
                        Boolean(providersByOffer[offer.id] && providersByOffer[offer.id] !== provider)
                      }
                      onClick={() => void beginCheckout(offer, provider)}
                      className="min-h-11 rounded-card border-2 border-accent px-4 py-2 text-sm font-bold text-accent disabled:opacity-60"
                    >
                      {busyId === offer.id ? "Opening secure checkout…" : "Pay with " + (provider === "esewa" ? "eSewa" : "Khalti")}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted">Checkout is not enabled for this offer yet. No payment has been requested.</p>
              )}
              {error?.offerId === offer.id && error.retryable ? (
                <button
                  type="button"
                  onClick={() => void beginCheckout(offer, error.provider)}
                  className="mt-3 text-xs font-bold text-muted underline"
                >
                  {error.newAttempt ? "Start a new checkout attempt" : "Retry the same checkout attempt"}
                </button>
              ) : null}
            {error?.offerId === offer.id && !error.retryable ? (
              <button
                type="button"
                disabled={busyId !== null}
                onClick={() => void reconcileCheckout(offer)}
                className="mt-3 block text-xs font-bold text-muted underline disabled:opacity-60"
              >
                {busyId === offer.id ? "Checking provider status…" : "Check provider status before retrying"}
              </button>
            ) : null}
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}

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
      <PublicOffers />
      <Capabilities />
      <FindingsPreview />
      <UnknownsPreview />
      <ExperimentsPreview />
      <AboutLink />
      <StatusRecord />
      <HamiPathways current="home" />
      <HomeFooter />
    </main>
  );
}

function Capabilities() {
  const capabilities = [
    {
      name: "Observe",
      description: "Discover through the five currently configured, explicitly governed source adapters — OpenAlex, Crossref, World Bank, GDELT, and GovInfo. These instruments are not a boundary on the kinds of value Hami may investigate.",
      status: "Implemented",
      statusTone: "text-emerald-600",
    },
    {
      name: "Preserve",
      description: "Retain evidence, provenance, scope, and uncertainty so possibilities and interpretations do not become unsupported claims.",
      status: "Implemented",
      statusTone: "text-emerald-600",
    },
    {
      name: "Investigate",
      description: "Turn observations into relevant unknowns, hypotheses, and tests. Background information alone does not prove a need, demand, or valuable transformation.",
      status: "Implemented",
      statusTone: "text-emerald-600",
    },
    {
      name: "Act",
      description: "Attempt transformations only within capability, authorization, privacy, safety, and legal boundaries. Consequential actions remain gated.",
      status: "Gated",
      statusTone: "text-amber-600",
    },
    {
      name: "Learn",
      description: "Compare expectations with observed outcomes, record success or failure, and update understanding. No verified real-world value outcome has yet established economic validation.",
      status: "Not yet validated",
      statusTone: "text-muted",
    },
  ];

  return (
    <section className="border-b border-line bg-surface">
      <Container className="py-12 sm:py-16 lg:py-20">
        <SectionHead
          numeral="§"
          eyebrow="System"
          title="What Hami does"
          lede="Five current capabilities form one value loop. They are instruments, not limits on Hami’s domain; each retains its honest implementation and evidence status."
        />
        <div className="mt-8 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((cap, i) => (
            <div
              key={cap.name}
              className="reveal rounded-lg border border-line bg-background p-6"
              style={{ "--i": i } as React.CSSProperties}
            >
              <div className="flex items-center justify-between">
                <h3 className="font-display text-xl font-bold text-ink">{cap.name}</h3>
                <span className={`font-mono text-micro font-bold uppercase tracking-[0.15em] ${cap.statusTone}`}>
                  {cap.status}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">{cap.description}</p>
            </div>
          ))}
          <div
            className="reveal rounded-lg border border-dashed border-line p-6"
            style={{ "--i": 5 } as React.CSSProperties}
          >
            <h3 className="font-display text-xl font-bold text-ink">The gap</h3>
            <p className="mt-3 text-sm leading-6 text-muted">
              Engineering capability is not realized value. Hami has not yet produced a
              verified real-world outcome with a participant. No value-realization claim is
              made until an actual outcome is measurable and appropriately evidenced.
            </p>
          </div>
        </div>
      </Container>
    </section>
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
        fontFamily="Georgia, 'Times New Roman', serif"
        fontWeight={700}
      >
        HAMI
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
            HAMI SYSTEMS
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
              <span className="flex flex-col">
                <span className="font-serif text-[clamp(3.2rem,9vw,6rem)] font-bold uppercase leading-[0.95] tracking-[0.035em] text-accent">
                  HAMI
                </span>
                <span className="mt-3 font-mono text-xs font-bold uppercase tracking-[0.32em] text-foreground">
                  SYSTEMS
                </span>
              </span>
              <span
                className="pb-1 text-[clamp(1.6rem,4vw,2.6rem)] text-muted"
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
            <p className="mt-4 max-w-xl text-sm leading-6 text-muted">
              Value itself is Hami’s domain: needs, knowledge, people, resources, and
              possibilities across fields. Its scope is universal; actions remain bounded
              by evidence, authorization, safety, and fair value-sharing.
            </p>
            <p className="mt-4 max-w-xl font-mono text-[0.68rem] font-bold uppercase leading-6 tracking-[0.12em] text-muted">
              People · Work · Knowledge · Resources · Opportunities · Outcomes
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
              <Button asChild variant="secondary" size="lg">
                <Link to="/experiments">
                  See what Hami is testing <ArrowRight aria-hidden="true" />
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
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    // Load enough to find consequential findings; filter AFTER loading,
    // not before. Loading only 3 then filtering can miss relevant findings
    // that fall outside the first three results.
    loadDiscoveries(20)
      .then((d) => {
        if (!live) return;
        if (d === null) {
          // Null means the loader couldn't retrieve data (not empty)
          setFailed(true);
          setItems([]);
        } else {
          setItems(d.filter((f) => f.has_consequence).slice(0, 3));
        }
      })
      .catch(() => {
        if (live) {
          // API failure is distinct from verified empty dataset
          setFailed(true);
          setItems([]);
        }
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
          {!items && !failed ? (
            <div className="skeleton h-32 w-full" aria-label="Loading findings" />
          ) : failed ? (
            <EmptyRecord
              label="Unavailable"
              message="The findings service is currently unavailable. Please try again later."
            />
          ) : items!.length === 0 ? (
            <EmptyRecord
              label="Empty record"
              message="No findings with recorded consequences yet. Findings appear here once they change a decision, experiment, or outcome."
            />
          ) : (
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {items!.map((finding, i) => (
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
                <Link to="/about" hash="climb" className="link-arrow">
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
