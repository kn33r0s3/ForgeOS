import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, BriefcaseBusiness, Handshake, KeyRound, Link2, MapPin, PenLine, Radio } from "lucide-react";
import { Container } from "@/components/layout/container";
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
  type PublicMatch,
  type PublicTrust,
} from "@/lib/content";
import type { CacheScope } from "@/lib/api-cache";

export const Route = createFileRoute("/domain")({
  component: DomainPage,
});

type Kind = "job" | "offer" | "trade";
function DomainPage() {
  const [rows, setRows] = useState<PublicDomainRecord[]>([]);
  const [matches, setMatches] = useState<PublicMatch[]>([]);
  const [alerts, setAlerts] = useState<PublicAlert[]>([]);
  const [connections, setConnections] = useState<PublicConnection[]>([]);
  const [events, setEvents] = useState<PublicDomainEvents | null>(null);
  const [trust, setTrust] = useState<PublicTrust | null>(null);
  const [kind, setKind] = useState<Kind>("job");
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [city, setCity] = useState("");
  const [price, setPrice] = useState("");
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
  const [chosenProvider, setChosenProvider] = useState<number | null>(null);
  const [requesterName, setRequesterName] = useState("");
  const [requestedService, setRequestedService] = useState("");
  const navigate = useNavigate();

  async function load(scope?: CacheScope) {
    setIsLoading(true);
    setEvents(null);
    setTrust(null);
    const [domain, matched, changes, linked] = await Promise.all([
      loadPublicDomain(scope),
      loadPublicMatches(scope),
      loadPublicAlerts(undefined, scope),
      loadPublicConnections(scope),
    ]);
    setApiUnavailable(domain === null || matched === null || changes === null || linked === null);
    setRows(domain ?? []);
    setMatches(matched ?? []);
    setAlerts(changes ?? []);
    setConnections(linked ?? []);
    const latest = domain?.[0];
    if (latest) {
      setEvents(await loadPublicDomainEvents(latest.id, scope));
      setTrust(await loadPublicTrust("domain_record", latest.id, scope));
    }
    setIsLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  async function postRecord(event: React.FormEvent) {
    event.preventDefault();
    setMessage(null);
    const result = await createPublicDomainRecord({
      kind,
      title,
      detail,
      city: city || null,
      stated_price: price || null,
    });
    if (!result) {
      setMessage("The post was not recorded.");
      return;
    }
    setCreatedId(result.id);
    setToken(result.close_token);
    setTitle("");
    setDetail("");
    setPrice("");
    // Reads after a write must reflect it, so they bypass the short read cache.
    setEvents(await loadPublicDomainEvents(result.id, { fresh: true }));
    setTrust(await loadPublicTrust("domain_record", result.id, { fresh: true }));
    await load({ fresh: true });
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
    if (!chosenProvider) return;
    const result = await createBookingRequest({
      provider_id: chosenProvider,
      requester_name: requesterName,
      requested_service: requestedService,
    });
    if (!result) {
      setMessage("The request was not recorded. Only a verified public provider can receive one.");
      return;
    }
    await navigate({ to: "/requests/$id", params: { id: String(result.id) } });
  }

  return (
    <main>
      <PageHeader
        eyebrow="Our records"
        title="Work, offers, and trades posted here"
        lede="A price appears only if the person stated it. Closing a post requires the token from creation and a note about what happened."
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
                      <span className={`status-pill self-start ${row.kind === "offer" ? "status-pill-success" : row.kind === "trade" ? "status-pill-neutral" : "status-pill-accent"}`}>{row.kind}</span>
                      <h3 className="mt-3 font-display text-2xl leading-tight tracking-tight text-ink">{row.title}</h3>
                      <p className="mt-2 flex-1 text-sm leading-6 text-muted">{row.detail}</p>
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
                            placeholder="Record the response you received"
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

        <div className="space-y-5 lg:sticky lg:top-[calc(var(--header-h)+1.5rem)]">
          <form id="post-form" onSubmit={postRecord} className="card card-accent scroll-mt-28 space-y-3 p-5 sm:p-6">
            <h2 className="flex items-center gap-2 font-display text-2xl tracking-tight text-ink"><PenLine className="size-5 text-accent" aria-hidden="true" /> Post in our records</h2>
            <p className="text-xs leading-5 text-muted">
              This post will be public. Do not include phone numbers, email
              addresses, identity documents, or other private information.
              Posting does not contact anyone or guarantee a match.
            </p>
            <label className="block">
              <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Kind</span>
              <select value={kind} onChange={(event) => setKind(event.target.value as Kind)} className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]">
                <option value="job">Job</option>
                <option value="offer">Offer</option>
                <option value="trade">Trade</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} required placeholder="Title" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Detail</span>
              <textarea value={detail} onChange={(event) => setDetail(event.target.value)} required placeholder="What is actually being posted" className="min-h-28 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
            </label>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">City</span>
                <input value={city} onChange={(event) => setCity(event.target.value)} placeholder="City, if stated" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Stated price</span>
                <input value={price} onChange={(event) => setPrice(event.target.value)} placeholder="Stated price, if any" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
            </div>
            <button type="submit" className="btn-wipe btn-primary inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent">Post in our records</button>
          </form>

          {token && createdId ? (
            <div className="card fade-in space-y-4 p-5 text-sm text-ink" role="status">
              <p className="flex items-start gap-2"><KeyRound className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" /><span>Record #{createdId}. Close token, shown once: <code className="break-all rounded bg-paper px-1.5 py-0.5 font-mono text-accent">{token}</code></span></p>
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
                    <input value={paidAmount} onChange={(event) => setPaidAmount(event.target.value)} inputMode="numeric" required placeholder="Amount received, whole NPR" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                  </label>
                ) : null}
                <label className="block">
                  <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">What happened</span>
                  <textarea value={closeNote} onChange={(event) => setCloseNote(event.target.value)} required minLength={3} placeholder="What actually happened" className="min-h-20 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
                </label>
                <button type="submit" className="btn-wipe btn-primary inline-flex min-h-11 items-center justify-center gap-2 rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent">Record the close</button>
              </form>
              <form onSubmit={disputeRecord} className="space-y-3 border-t border-line pt-4">
                <label className="block">
                  <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Dispute</span>
                  <textarea value={disputeNote} onChange={(event) => setDisputeNote(event.target.value)} required minLength={3} placeholder="What is disputed" className="min-h-20 w-full rounded-card border border-line bg-paper px-4 py-3 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
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
                <input value={requesterName} onChange={(event) => setRequesterName(event.target.value)} required placeholder="Your name" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-micro font-extrabold uppercase tracking-[0.1em] text-dim">Request</span>
                <input value={requestedService} onChange={(event) => setRequestedService(event.target.value)} required placeholder="What you are requesting" className="min-h-12 w-full rounded-card border border-line bg-paper px-4 text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]" />
              </label>
              <button type="submit" className="btn-wipe btn-primary inline-flex min-h-11 items-center justify-center gap-2 rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent">Record the request</button>
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
