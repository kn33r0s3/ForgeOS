import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, BriefcaseBusiness, Handshake, KeyRound, Link2, MapPin, PenLine, Radio } from "lucide-react";
import { Container } from "@/components/layout/container";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
import {
  closePublicDomainRecord,
  createBookingRequest,
  createPublicDomainRecord,
  disputePublicDomainRecord,
  loadPublicAlerts,
  loadPublicConnections,
  loadPublicDomain,
  loadPublicDomainEvents,
  loadPublicMatches,
  loadPublicTrust,
  recordPublicConnectionResponse,
  type PublicAlert,
  type PublicConnection,
  type PublicDomainEvents,
  type PublicDomainRecord,
  type PublicDomainTerms,
  type PublicMatch,
  type PublicTrust,
} from "@/lib/content";
import type { CacheScope } from "@/lib/api-cache";

export const Route = createFileRoute("/domain")({
  component: DomainPage,
  head: () => ({ meta: [{ title: "Needs, offers, and fair exchanges — Hami" }] }),
});

type Kind = "job" | "offer" | "trade";
const AGREEMENT_FIELDS: Array<{
  key: Exclude<keyof PublicDomainTerms, "amount_npr">;
  label: string;
  placeholder: string;
}> = [
  { key: "requested", label: "Exact work, good, or result", placeholder: "What exactly will be delivered or exchanged?" },
  { key: "who_can_submit", label: "Who can take part", placeholder: "Who may offer, request, or accept this exchange?" },
  { key: "success", label: "Definition of complete", placeholder: "How will both sides know the work or exchange is complete?" },
  { key: "evidence_required", label: "Proof or handoff", placeholder: "What evidence or handoff confirms completion?" },
  { key: "ownership", label: "Ownership and data", placeholder: "Who owns the result, materials, files, and data?" },
  { key: "payment_due", label: "Payment or reciprocal value", placeholder: "When is payment due, or what will each side give in a non-cash trade?" },
  { key: "partial", label: "Partial completion", placeholder: "What happens if only part of the work is completed?" },
  { key: "rejection", label: "Rejection and disputes", placeholder: "How can either side reject work or raise a dispute?" },
  { key: "resale", label: "Reuse or resale", placeholder: "May either side reuse or resell any result or materials?" },
  { key: "costs", label: "Costs and expenses", placeholder: "Who pays for materials, transport, fees, or other costs?" },
];

function hasAgreementTerms(value: PublicDomainTerms): boolean {
  return typeof value.amount_npr === "number" ||
    AGREEMENT_FIELDS.some((field) => Boolean(value[field.key]?.trim()));
}

function DomainPage() {
  const [rows, setRows] = useState<PublicDomainRecord[]>([]);
  const [matches, setMatches] = useState<PublicMatch[]>([]);
  const [alerts, setAlerts] = useState<PublicAlert[]>([]);
  const [connections, setConnections] = useState<PublicConnection[]>([]);
  const [events, setEvents] = useState<PublicDomainEvents | null>(null);
  const [trust, setTrust] = useState<PublicTrust | null>(null);
  const [kind, setKind] = useState<Kind>("offer");
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [city, setCity] = useState("");
  const [price, setPrice] = useState("");
  const [terms, setTerms] = useState<PublicDomainTerms>({});
  const [token, setToken] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [closeResult, setCloseResult] = useState<"completed" | "withdrawn" | "paid">("completed");
  const [closeNote, setCloseNote] = useState("");
  const [paidAmount, setPaidAmount] = useState("");
  const [disputeNote, setDisputeNote] = useState("");
  const [responseNote, setResponseNote] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [apiUnavailable, setApiUnavailable] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isPosting, setIsPosting] = useState(false);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [chosenProvider, setChosenProvider] = useState<number | null>(null);
  const [isBooking, setIsBooking] = useState(false);
  const [requesterName, setRequesterName] = useState("");
  const [requestedService, setRequestedService] = useState("");
  const navigate = useNavigate();

  async function load(scope?: CacheScope, isActive: () => boolean = () => true) {
    setIsLoading(true);
    setEvents(null);
    setTrust(null);
    const [domain, matched, changes, linked] = await Promise.all([
      loadPublicDomain(scope),
      loadPublicMatches(scope),
      loadPublicAlerts(undefined, scope),
      loadPublicConnections(scope),
    ]);
    if (!isActive()) return;
    setApiUnavailable(domain === null || matched === null || changes === null || linked === null);
    setRows(domain ?? []);
    setMatches(matched ?? []);
    setAlerts(changes ?? []);
    setConnections(linked ?? []);
    const latest = domain?.[0];
    if (latest) {
      setEvents(await loadPublicDomainEvents(latest.id, scope));
      setTrust(await loadPublicTrust("domain_record", latest.id, scope));
      if (!isActive()) return;
    }
    setIsLoading(false);
  }

  useEffect(() => {
    let active = true;
    void load(undefined, () => active);
    return () => {
      active = false;
    };
  }, []);

  async function postRecord(event: React.FormEvent) {
    event.preventDefault();
    if (isPosting) return;
    setIsPosting(true);
    setMessage(null);
    try {
      const result = await createPublicDomainRecord({
        kind,
        title,
        detail,
        city: city || null,
        stated_price: price || null,
        terms: hasAgreementTerms(terms) ? terms : null,
      });
      if (!result) {
        setMessage("Hami could not confirm the post was recorded. Check the board before retrying; a timed-out request may still have reached the server.");
        return;
      }
      setCreatedId(result.id);
      setToken(result.close_token);
      setTokenCopied(false);
      setTitle("");
      setDetail("");
      setPrice("");
      setTerms({});
      setMessage(`Proposal #${result.id} was recorded. No one was contacted and no agreement or payment was created.`);
      // Reads after a write must reflect it, so they bypass the short read cache.
      setEvents(await loadPublicDomainEvents(result.id, { fresh: true }));
      setTrust(await loadPublicTrust("domain_record", result.id, { fresh: true }));
      await load({ fresh: true });
    } catch {
      setMessage("Hami could not confirm the post was recorded. Check the board before retrying to avoid a duplicate.");
    } finally {
      setIsPosting(false);
    }
  }

  async function copyCloseToken() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setTokenCopied(true);
      setMessage("Close token copied. Save it securely; Hami cannot recover it later.");
    } catch {
      setTokenCopied(false);
      setMessage("Clipboard access is unavailable. Select and copy the close token shown above before leaving this page.");
    }
  }

  async function closeRecord(event: React.FormEvent) {
    event.preventDefault();
    if (!createdId || !token) return;
    setMessage(null);
    const amount = paidAmount.trim() ? Number(paidAmount) : null;
    if (closeResult === "paid" && (amount === null || !Number.isInteger(amount) || amount < 0)) {
      setMessage("A paid close needs the whole-number amount actually received.");
      return;
    }
    const closed = await closePublicDomainRecord({
      recordId: createdId,
      close_token: token,
      result: closeResult,
      note: closeNote,
      amount_npr: amount,
    });
    if (!closed) {
      setMessage("The close was not recorded. The token must match an open post, and a paid close needs the amount received.");
      return;
    }
    setMessage(`Record #${closed.id} is closed as ${closeResult}. A recorded amount is not a money transfer.`);
    setEvents(await loadPublicDomainEvents(closed.id, { fresh: true }));
    await load({ fresh: true });
  }

  async function disputeRecord(event: React.FormEvent) {
    event.preventDefault();
    if (!createdId || !token) return;
    setMessage(null);
    const disputed = await disputePublicDomainRecord({
      recordId: createdId,
      close_token: token,
      note: disputeNote,
    });
    if (!disputed) {
      setMessage("The dispute was not recorded. The token must match this post.");
      return;
    }

    setEvents(disputed);
    setMessage(`A dispute is recorded on #${createdId}. No winner is named.`);
  }

  async function respondToConnection(event: React.FormEvent, connectionId: number, recordId: number) {
    event.preventDefault();
    if (!token) return;
    const response = await recordPublicConnectionResponse({
      recordId,
      connectionId,
      close_token: token,
      note: responseNote,
    });
    if (!response) {
      setMessage("The response was not recorded. Check the close token and connection state.");
      return;
    }
    setResponseNote("");
    setMessage("The response is recorded. A response is not acceptance.");
    await load({ fresh: true });
  }

  async function chooseProvider(providerId: number) {
    setChosenProvider(providerId);
    setTrust(await loadPublicTrust("provider", providerId));
  }

  async function book(event: React.FormEvent) {
    event.preventDefault();
    if (!chosenProvider || isBooking) return;
    setIsBooking(true);
    setMessage(null);
    try {
      const result = await createBookingRequest({
        provider_id: chosenProvider,
        requester_name: requesterName,
        requested_service: requestedService,
      });
      if (!result) {
        setMessage("Hami could not confirm this request was recorded. Check before retrying; a timed-out request may still have reached the server.");
        return;
      }
      await navigate({ to: "/requests/$id", params: { id: String(result.id) } });
    } catch {
      setMessage("Hami could not confirm this request. Check your request status before trying again.");
    } finally {
      setIsBooking(false);
    }
  }

  return (
    <main>
      <PageHeader
        eyebrow="Our records"
        title="Needs, offers, and fair exchanges"
        lede="Offer a skill, service, good, resource, or idea—or say what you need. Put the expectations on the table so both sides can judge the exchange. A post or match is only a starting point, never acceptance, payment, or proof of fulfillment."
      />

      <Container className="grid gap-10 py-10 sm:py-14 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
        <div className="min-w-0 space-y-12">
          {apiUnavailable ? (
            <UnavailableState
              title="Some services did not respond"
              body="Some public network services are unavailable. Missing records below are not being treated as confirmed empty results."
              onRetry={() => void load()}
            />
          ) : null}

          <section aria-labelledby="open-posts">
            <SectionHead id="open-posts" icon={BriefcaseBusiness} title="Open posts" count={isLoading ? null : rows.length} />
            {isLoading ? (
              <SkeletonCards count={3} label="Checking open posts…" className="grid gap-3 sm:grid-cols-2" />
            ) : !apiUnavailable && rows.length === 0 ? (
              <EmptyState
                icon={BriefcaseBusiness}
                headingLevel="h3"
                title="The board is quiet"
                body="No open jobs, offers, or trades are in our records."
              >
                <a href="#post-form" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                  Post the first one <ArrowUpRight className="size-4" aria-hidden="true" />
                </a>
              </EmptyState>
            ) : (
              <ol className="grid gap-3 sm:grid-cols-2">
                {rows.map((row, index) => (
                  <li key={row.id} className="card card-interactive reveal flex flex-col p-5" style={{ "--i": Math.min(index, 8) } as React.CSSProperties}>
                    <article className="flex flex-1 flex-col">
                      <span className={`status-pill self-start ${row.kind === "offer" ? "status-pill-success" : row.kind === "trade" ? "status-pill-neutral" : "status-pill-accent"}`}>{row.kind === "offer" ? "Offer" : row.kind === "trade" ? "Trade" : "Need / job"}</span>
                      <h3 className="mt-3 font-display text-2xl leading-tight tracking-tight text-ink">{row.title}</h3>
                      <p className="mt-2 flex-1 text-sm leading-6 text-muted">{row.detail}</p>
                      {row.terms && Object.keys(row.terms).length > 0 ? (
                        <details className="mt-3 rounded-card border border-line p-3">
                          <summary className="cursor-pointer text-sm font-semibold text-ink">
                            {row.terms_complete ? "Contract terms recorded (not acceptance)" : "Draft terms — more detail needed"}
                          </summary>
                          {row.terms.amount_npr != null ? <p className="mt-3 text-sm text-ink">Contract amount: NPR {row.terms.amount_npr.toLocaleString()}</p> : null}
                          <dl className="mt-2 space-y-2">
                            {AGREEMENT_FIELDS.map((field) => {
                              const value = row.terms?.[field.key];
                              return value?.trim() ? (
                                <div key={field.key}>
                                  <dt className="text-xs font-bold uppercase tracking-wide text-dim">{field.label}</dt>
                                  <dd className="mt-0.5 whitespace-pre-wrap break-words text-sm text-muted">{value}</dd>
                                </div>
                              ) : null;
                            })}
                          </dl>
                          {!row.terms_complete ? <p className="mt-3 text-xs text-muted">This is still a proposal; the existing acceptance gate requires all terms to be completed.</p> : null}
                        </details>
                      ) : (
                        <p className="mt-3 text-xs text-muted">Agreement terms not yet recorded. A match alone is not permission to begin work.</p>
                      )}
                      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-sm">
                        <span className="inline-flex items-center gap-1.5 text-muted"><MapPin className="size-4 text-accent" aria-hidden="true" />{row.city || "City not recorded"}</span>
                        <span className={row.stated_price ? "font-semibold text-ink" : "text-dim"}>{row.stated_price || "Price not recorded"}</span>
                      </div>
                    </article>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section aria-labelledby="recorded-matches">
            <SectionHead id="recorded-matches" icon={Handshake} title="Recorded matches" count={isLoading ? null : matches.length} />
            <p className="-mt-2 mb-4 max-w-2xl text-sm leading-6 text-muted">A match is a shared city or shared words in our records. Missing price, availability, or a completed outcome stays listed as unknown.</p>
            {!isLoading && !apiUnavailable && matches.length === 0 ? (
              <p className="rounded-card border border-dashed border-line p-5 text-sm text-muted">No open post to match.</p>
            ) : (
              <div className="space-y-3">
                {matches.map((match) => (
                  <article key={match.need_id} className="card p-5">
                    <h3 className="font-display text-xl tracking-tight text-ink">{match.need_title}</h3>
                    {match.candidates.length === 0 ? <p className="mt-2 text-sm text-muted">No recorded counterparty.</p> : (
                      <ul className="mt-3 divide-y divide-line">
                        {match.candidates.map((candidate) => (
                          <li key={`${candidate.kind}-${candidate.id}`} className="py-3 text-sm text-muted first:pt-0 last:pb-0">
                            <p className="font-medium text-ink"><span className="text-micro font-extrabold uppercase tracking-[0.1em] text-accent">{candidate.kind}</span> · {candidate.name}</p>
                            <p className="mt-1">{candidate.reasons.join(" · ")}</p>
                            <p className="mt-1 text-dim">{candidate.stated_price || "Price not recorded"} · {candidate.stated_availability || "Availability not recorded"}</p>
                            <p className="mt-1 text-xs text-dim">{candidate.unknowns.join(" · ")}</p>
                            {candidate.kind === "provider" ? (
                              <button type="button" onClick={() => void chooseProvider(candidate.id)} className="btn-ghost mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
                                See trust and request this provider <ArrowUpRight className="size-4" aria-hidden="true" />
                              </button>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="public-connections">
            <SectionHead id="public-connections" icon={Link2} title="Public connections" count={isLoading ? null : connections.length} />
            {!isLoading && !apiUnavailable && connections.length === 0 ? (
              <p className="rounded-card border border-dashed border-line p-5 text-sm text-muted">No public connection is recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {connections.map((connection) => (
                  <article key={connection.id} className="card p-5">
                    <span className="status-pill status-pill-accent">{connection.state}</span>
                    <p className="mt-3 text-sm text-ink">{connection.reason}</p>
                    <p className="mt-2 text-xs text-dim">
                      {connection.unknown || connection.agreement_gap || "No additional unknowns recorded."}
                    </p>
                    <p className="mt-2 text-sm text-muted">{connection.latest_response || "No public response recorded. A response is not acceptance."}</p>
                    {token && createdId === connection.left_id && connection.left_kind === "domain_record" && ["proposed", "authorized", "contacted"].includes(connection.state) ? (
                      <form onSubmit={(event) => respondToConnection(event, connection.id, createdId)} className="mt-4 space-y-2">
                        <label className="block">
                          <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Response received</span>
                          <textarea
                            value={responseNote}
                            onChange={(event) => setResponseNote(event.target.value)}
                            required
                            maxLength={2000}
                            placeholder="Record the response you received (max 2,000 characters)"
                            className="min-h-20 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)] text-sm"
                          />
                        </label>
                        <p className="text-xs text-dim">A response records contact; it is not acceptance.</p>
                        <button type="submit" className="btn-secondary inline-flex min-h-11 items-center justify-center gap-2 rounded-card border border-line bg-card px-5 text-sm font-semibold text-ink hover:border-accent focus-visible:border-accent">Record response</button>
                      </form>
                    ) : null}
                    <p className="mt-2 text-sm text-muted">{connection.latest_fulfillment || "No fulfillment recorded. Fulfillment is not payment."}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <form id="post-form" onSubmit={postRecord} className="card card-accent scroll-mt-28 space-y-3 p-5 sm:p-6">
            <h2 className="flex items-center gap-2 font-display text-2xl tracking-tight text-ink"><PenLine className="size-5 text-accent" aria-hidden="true" /> Post a need, offer, or trade</h2>
            <p className="text-xs leading-5 text-muted">
              This post will be public. Do not include phone numbers, email
              addresses, identity documents, or other private information.
              Posting does not contact anyone or guarantee a match.
            </p>
            <label className="block">
              <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Kind</span>
              <select value={kind} onChange={(event) => setKind(event.target.value as Kind)} className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]">
                <option value="offer">Offer something</option>
                <option value="job">Need / job</option>
                <option value="trade">Trade</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={160} placeholder="Title (max 160 characters)" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Detail</span>
              <textarea value={detail} onChange={(event) => setDetail(event.target.value)} required maxLength={5000} placeholder="What is actually being posted (max 5,000 characters)" className="min-h-28 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
            </label>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">City</span>
                <input value={city} onChange={(event) => setCity(event.target.value)} maxLength={100} placeholder="City, if stated (max 100 characters)" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Stated price</span>
                <input value={price} onChange={(event) => setPrice(event.target.value)} maxLength={120} placeholder="Stated price, if any (max 120 characters)" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                <span className="mt-1 block text-xs text-dim">A quote is not a confirmed payment. Keep this consistent with the agreement amount below.</span>
              </label>
            </div>
            <details open className="rounded-card border border-line p-3">
              <summary className="cursor-pointer py-1 text-sm font-bold text-ink">Set clear exchange terms (needed before work can be accepted)</summary>
              <p className="mt-2 text-xs leading-5 text-muted">
                Be specific about what each side gives and receives. These fields can be saved as a draft, but an incomplete contract cannot pass the existing acceptance gate. For a non-cash exchange, enter NPR 0 and explain the reciprocal value under payment or reciprocal value.
              </p>
              <label className="mt-3 block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Contract amount (whole NPR)</span>
                <input type="number" min={0} step={1} inputMode="numeric" value={terms.amount_npr ?? ""} max={1000000000000} onChange={(event) => setTerms((current) => ({ ...current, amount_npr: event.target.value.trim() === "" ? undefined : Number(event.target.value) }))} placeholder="0 for a non-cash exchange" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <div className="mt-3 space-y-3">
                {AGREEMENT_FIELDS.map((field) => (
                  <label key={field.key} className="block">
                    <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">{field.label}</span>
                    <textarea maxLength={1000} value={terms[field.key] ?? ""} onChange={(event) => setTerms((current) => ({ ...current, [field.key]: event.target.value }))} placeholder={field.placeholder} className="min-h-16 w-full rounded-card border border-line bg-paper px-4 py-3 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                  </label>
                ))}
              </div>
            </details>
            <p className="text-xs leading-5 text-muted">A match is a suggestion, not agreement. Do not post private contact details. Both sides should understand the terms before any work, handover, or payment.</p>
            <button type="submit" disabled={isPosting} aria-busy={isPosting} className="btn-wipe btn-primary inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent disabled:cursor-wait disabled:opacity-60">{isPosting ? "Posting proposal…" : "Post proposal"}</button>
          </form>

          {token && createdId ? (
            <div className="card fade-in space-y-4 p-5 text-sm text-ink" role="status">
              <p className="flex items-start gap-2"><KeyRound className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" /><span>Record #{createdId}. Save this one-time close token before leaving: <code className="break-all rounded bg-paper px-1.5 py-0.5 font-mono text-accent">{token}</code></span></p>
              <button type="button" onClick={() => void copyCloseToken()} className="min-h-10 rounded-card border border-line px-3 text-sm font-semibold hover:border-accent">{tokenCopied ? "Token copied" : "Copy close token"}</button>
              <p className="text-muted">Closing records what happened. It does not move money. A dispute names no winner.</p>
              <form onSubmit={closeRecord} className="space-y-3">
                <label className="block">
                  <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Result</span>
                  <select value={closeResult} onChange={(event) => setCloseResult(event.target.value as "completed" | "withdrawn" | "paid")} className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]">
                    <option value="completed">Completed, no amount recorded</option>
                    <option value="withdrawn">Withdrawn</option>
                    <option value="paid">Paid, amount actually received</option>
                  </select>
                </label>
                {closeResult === "paid" ? (
                  <label className="block">
                    <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Amount received</span>
                    <input value={paidAmount} onChange={(event) => setPaidAmount(event.target.value)} inputMode="numeric" type="number" min={0} max={1000000000000} step={1} required placeholder="Amount received, whole NPR" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                  </label>
                ) : null}
                <label className="block">
                  <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">What happened</span>
                  <textarea value={closeNote} onChange={(event) => setCloseNote(event.target.value)} required minLength={3} maxLength={2000} placeholder="What actually happened (max 2,000 characters)" className="min-h-20 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                </label>
                <button type="submit" className="btn-wipe btn-primary inline-flex min-h-11 items-center justify-center gap-2 rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent">Record the close</button>
              </form>
              <form onSubmit={disputeRecord} className="space-y-3 border-t border-line pt-4">
                <label className="block">
                  <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Dispute</span>
                  <textarea value={disputeNote} onChange={(event) => setDisputeNote(event.target.value)} required minLength={3} maxLength={2000} placeholder="What is disputed (max 2,000 characters)" className="min-h-20 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                </label>
                <button type="submit" className="btn-secondary inline-flex min-h-11 items-center justify-center gap-2 rounded-card border border-line bg-card px-5 text-sm font-semibold text-ink hover:border-accent focus-visible:border-accent">Record a dispute</button>
              </form>
            </div>
          ) : null}
          {chosenProvider ? (
            <form onSubmit={book} className="card fade-in space-y-3 p-5">
              <p className="text-sm text-ink">Request provider #{chosenProvider}. This records a request. It does not accept the work or record a payment.</p>
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Your name</span>
                <input value={requesterName} onChange={(event) => setRequesterName(event.target.value)} required maxLength={160} placeholder="Your name (max 160 characters)" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Request</span>
                <input value={requestedService} onChange={(event) => setRequestedService(event.target.value)} required maxLength={2000} placeholder="What you are requesting (max 2,000 characters)" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <button type="submit" disabled={isBooking} aria-busy={isBooking} className="btn-wipe btn-primary inline-flex min-h-11 items-center justify-center gap-2 rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent disabled:cursor-wait disabled:opacity-60">{isBooking ? "Recording request…" : "Record the request"}</button>
            </form>
          ) : null}
          {message ? <p role="status" className="rounded-card border border-line bg-card px-4 py-3 text-sm text-muted">{message}</p> : null}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <section className="card p-5">
              <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">Trust record</p>
              <p className="mt-2 text-sm text-muted">
                {trust
                  ? `${trust.recorded_requests} request(s) recorded · ${trust.disputes} dispute(s)`
                  : apiUnavailable ? "Trust data is unavailable while the public service is failing."
                    : "No trust record is available for the latest post."}
              </p>
              {trust?.unknowns.length ? <p className="mt-2 text-xs text-dim">{trust.unknowns.join(" · ")}</p> : null}
            </section>
            <section className="card p-5">
              <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-accent">Event timeline</p>
              {events ? (
                <p className="mt-2 text-sm text-muted">
                  {events.completions} completion(s) · {events.payments.length} payment event(s) · {events.disputes.length} dispute event(s)
                </p>
              ) : (
                <p className="mt-2 text-sm text-muted">{apiUnavailable ? "The event timeline could not be checked." : "No event timeline is recorded yet."}</p>
              )}
            </section>
          </div>

          <section className="card p-5" aria-labelledby="recorded-changes">
            <h2 id="recorded-changes" className="flex items-center gap-2 font-display text-2xl tracking-tight text-ink"><Radio className="size-4 text-accent" aria-hidden="true" /> Recorded changes</h2>
            <div className="mt-3 space-y-2">
              {isLoading ? <p className="text-sm text-muted">Checking recorded changes…</p> : !apiUnavailable && alerts.length === 0 ? <p className="text-sm text-muted">No recorded change yet.</p> : alerts.map((alert) => (
              <p key={alert.id} className="border-l-2 border-accent/40 pl-3 text-sm text-muted">
                <span className="font-semibold text-accent">Derived activity, not a verified outcome. </span>
                {alert.text}
              </p>
              ))}
            </div>
          </section>
        </div>
      </Container>
      <HamiPathways current="work" />
    </main>
  );
}

function SectionHead({
  id,
  icon: Icon,
  title,
  count,
}: {
  id: string;
  icon: typeof Radio;
  title: string;
  count: number | null;
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3 border-b border-line pb-3">
      <h2 id={id} className="flex items-center gap-2 font-display text-3xl tracking-tight text-ink">
        <Icon className="size-5 text-accent" aria-hidden="true" />
        {title}
      </h2>
      {count !== null ? <span className="chip-count text-muted">{count}</span> : null}
    </div>
  );
}
