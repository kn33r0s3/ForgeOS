import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import {
  canRender,
  latestStateChange,
  publicClaims,
  renderValueLabel,
  type LedgerClaim,
  type LedgerClaimState,
} from "@/lib/ledger";

export const Route = createFileRoute("/ledger")({
  component: LedgerPage,
  head: () => ({
    meta: [
      { title: "Proof ledger — Hami" },
      {
        name: "description",
        content:
          "Every public claim Hami makes, with its state, its evidence, and its measured value. A claim renders only with state and evidence. Contradicted claims are shown, never hidden.",
      },
    ],
  }),
});

/**
 * Border + text classes for a claim state. States are told by type and
 * border, not by new hues: proposed and running use amber, completed uses
 * wheat, contradicted uses the existing danger red and is always shown.
 */
function stateClasses(state: LedgerClaimState): { tag: string; bar: string } {
  if (state === "contradicted") {
    return {
      tag: "border-ledger-danger text-ledger-danger",
      bar: "border-l-ledger-danger",
    };
  }
  if (state === "completed") {
    return {
      tag: "border-ledger-wheat text-ledger-wheat",
      bar: "border-l-ledger-wheat",
    };
  }
  return {
    tag: "border-ledger-amber text-ledger-amber",
    bar: "border-l-ledger-amber",
  };
}

/**
 * The latest verified state change, in a .term-window, matching the home
 * LiveStrip. The claim renders only with state + evidence (the ledger
 * gate); if there is no claim, the window shows the prompt only.
 */
function LatestChange() {
  const latest = latestStateChange();
  return (
    <div className="term-window">
      <div className="term-titlebar">
        <span className="term-dot term-dot--red" aria-hidden="true" />
        <span className="term-dot term-dot--yellow" aria-hidden="true" />
        <span className="term-dot term-dot--green" aria-hidden="true" />
        <span>niroj@hami: ~</span>
      </div>
      <div className="term-body">
        <p className="term-prompt">hami ledger --latest</p>
        {latest ? (
          <>
            <p>
              [{latest.state}] {latest.id} — {latest.title}
            </p>
            <p className="text-ink">{renderValueLabel(latest)}</p>
            <p className="text-muted">
              {latest.titleNe} · updated {latest.updatedAt}
            </p>
          </>
        ) : (
          <p className="text-muted">no verified change yet</p>
        )}
        <p>
          <span className="term-prompt">hami ledger</span>{" "}
          <span className="term-cursor" aria-hidden="true" />
        </p>
      </div>
    </div>
  );
}

/**
 * One public claim. Devanagari heading first, English title second.
 * The value comes from renderValueLabel so an ESTIMATED value always
 * says "estimated" and is never shown as ACTUAL. A contradicted claim
 * is shown, never hidden, and names what contradicts it.
 */
function ClaimCard({ claim }: { claim: LedgerClaim }) {
  const value = renderValueLabel(claim);
  const state = stateClasses(claim.state);
  return (
    <article
      className={`rounded-md border border-ledger-border border-l-4 ${state.bar} bg-ledger-surface p-5 shadow-md sm:p-6`}
      aria-label={`${claim.id}: ${claim.title}`}
    >
      <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
        <span className="font-bold text-ledger-ink">{claim.id}</span>
        <span className={`rounded-sm border px-2 py-0.5 font-bold uppercase tracking-wider ${state.tag}`}>
          {claim.state}
        </span>
        <span className="rounded-sm border border-ledger-border px-2 py-0.5 font-bold uppercase tracking-wider text-ledger-muted">
          {claim.primitive}
        </span>
        <span className="ml-auto text-ledger-muted">
          updated {claim.updatedAt}
        </span>
      </div>
      <h2 className="mt-4 font-ledger-heading text-2xl leading-snug text-ledger-ink">
        {claim.titleNe}
      </h2>
      <p className="mt-1 font-display text-lg font-bold text-ledger-ink">
        {claim.title}
      </p>
      <p className="mt-3 font-mono text-sm text-ledger-amber">{value}</p>
      <p className="mt-3 text-base leading-7 text-ledger-ink">
        {claim.claim.statement}
      </p>
      {claim.state === "contradicted" && claim.contradictedBy ? (
        <p className="mt-3 border border-ledger-danger bg-ledger-black px-3 py-2 text-sm leading-6 text-ledger-danger">
          Contradicted by: {claim.contradictedBy}
        </p>
      ) : null}
      <div className="mt-4 border-t border-ledger-border pt-3">
        <p className="font-mono text-xs uppercase tracking-wider text-ledger-muted">
          Evidence
        </p>
        <ul className="mt-2 space-y-1">
          {claim.claim.sources.map((source) => (
            <li key={source} className="font-mono text-xs leading-5 text-ledger-muted">
              {source}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function LedgerPage() {
  // publicClaims() returns only claims that pass the ledger gate. The
  // canRender filter makes the gate explicit in the page itself: nothing
  // renders without state + evidence.
  const claims = publicClaims().filter((claim) => canRender(claim));
  return (
    <>
      <section className="border-b border-line bg-background" aria-label="Latest verified change">
        <Container className="py-8 sm:py-10">
          <p className="font-ledger-wordmark text-5xl leading-none text-ledger-amber sm:text-6xl">
            Hami
          </p>
          <h1 className="mt-3 font-ledger-heading text-2xl leading-snug text-ledger-ink sm:text-3xl">
            प्रमाण खाता
          </h1>
          <p className="mt-1 font-display text-xl font-bold text-ledger-ink">
            Proof ledger
          </p>
          <p className="mt-3 max-w-2xl text-base leading-7 text-ledger-muted">
            Every public claim, with its state, its evidence, and its measured
            value. A claim renders only with state and evidence. Contradicted
            claims are shown, never hidden.
          </p>
          <div className="mt-6">
            <LatestChange />
          </div>
        </Container>
      </section>
      <section className="bg-background" aria-label="Public claims">
        <Container className="py-8 sm:py-10">
          <div className="grid gap-5 md:grid-cols-2">
            {claims.map((claim) => (
              <ClaimCard key={claim.id} claim={claim} />
            ))}
          </div>
        </Container>
      </section>
    </>
  );
}
