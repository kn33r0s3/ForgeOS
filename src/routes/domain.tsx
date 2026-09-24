import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
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
  const [chosenProvider, setChosenProvider] = useState<number | null>(null);
  const [requesterName, setRequesterName] = useState("");
  const [requestedService, setRequestedService] = useState("");
  const navigate = useNavigate();

  async function load() {
    const [domain, matched, changes, linked] = await Promise.all([
      loadPublicDomain(),
      loadPublicMatches(),
      loadPublicAlerts(),
      loadPublicConnections(),
    ]);
    setRows(domain);
    setMatches(matched);
    setAlerts(changes);
    setConnections(linked);
    const latest = domain[0];
    if (latest) {
      setEvents(await loadPublicDomainEvents(latest.id));
      setTrust(await loadPublicTrust("domain_record", latest.id));
    }
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
    setEvents(await loadPublicDomainEvents(result.id));
    setTrust(await loadPublicTrust("domain_record", result.id));
    await load();
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
    setEvents(await loadPublicDomainEvents(closed.id));
    await load();
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
    await load();
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
    <main className="py-10 sm:py-14">
      <Container className="max-w-3xl">
        <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Our records</p>
        <h1 className="mt-2 font-display text-4xl tracking-tight text-fg">Work, offers, and trades posted here</h1>
        <p className="mt-3 text-muted">A price appears only if the person stated it. Closing a post requires the token from creation and a note about what happened.</p>

        <form onSubmit={postRecord} className="mt-8 space-y-3 rounded-[2rem] border border-line bg-raised p-6">
          <select value={kind} onChange={(event) => setKind(event.target.value as Kind)} className="min-h-12 w-full rounded-xl border border-line bg-void px-4 text-fg">
            <option value="job">Job</option>
            <option value="offer">Offer</option>
            <option value="trade">Trade</option>
          </select>
          <input value={title} onChange={(event) => setTitle(event.target.value)} required placeholder="Title" className="min-h-12 w-full rounded-xl border border-line bg-void px-4 text-fg" />
          <textarea value={detail} onChange={(event) => setDetail(event.target.value)} required placeholder="What is actually being posted" className="min-h-28 w-full rounded-xl border border-line bg-void px-4 py-3 text-fg" />
          <input value={city} onChange={(event) => setCity(event.target.value)} placeholder="City, if stated" className="min-h-12 w-full rounded-xl border border-line bg-void px-4 text-fg" />
          <input value={price} onChange={(event) => setPrice(event.target.value)} placeholder="Stated price, if any" className="min-h-12 w-full rounded-xl border border-line bg-void px-4 text-fg" />
          <button type="submit" className="min-h-11 rounded-full bg-fg px-5 text-sm text-void">Post in our records</button>
        </form>

        {token && createdId ? (
          <div className="mt-4 space-y-4 rounded-2xl border border-line bg-void p-4 text-sm text-fg">
            <p>Record #{createdId}. Close token, shown once: {token}</p>
            <p className="text-muted">Closing records what happened. It does not move money. A dispute names no winner.</p>
            <form onSubmit={closeRecord} className="space-y-3">
              <select value={closeResult} onChange={(event) => setCloseResult(event.target.value as "completed" | "withdrawn" | "paid")} className="min-h-12 w-full rounded-xl border border-line bg-raised px-4 text-fg">
                <option value="completed">Completed, no amount recorded</option>
                <option value="withdrawn">Withdrawn</option>
                <option value="paid">Paid, amount actually received</option>
              </select>
              {closeResult === "paid" ? (
                <input value={paidAmount} onChange={(event) => setPaidAmount(event.target.value)} inputMode="numeric" required placeholder="Amount received, whole NPR" className="min-h-12 w-full rounded-xl border border-line bg-raised px-4 text-fg" />
              ) : null}
              <textarea value={closeNote} onChange={(event) => setCloseNote(event.target.value)} required minLength={3} placeholder="What actually happened" className="min-h-20 w-full rounded-xl border border-line bg-raised px-4 py-3 text-fg" />
              <button type="submit" className="min-h-11 rounded-full bg-fg px-5 text-sm text-void">Record the close</button>
            </form>
            <form onSubmit={disputeRecord} className="space-y-3 border-t border-line pt-4">
              <textarea value={disputeNote} onChange={(event) => setDisputeNote(event.target.value)} required minLength={3} placeholder="What is disputed" className="min-h-20 w-full rounded-xl border border-line bg-raised px-4 py-3 text-fg" />
              <button type="submit" className="min-h-11 rounded-full border border-line px-5 text-sm text-fg">Record a dispute</button>
            </form>
          </div>
        ) : null}
        {chosenProvider ? (
          <form onSubmit={book} className="mt-4 space-y-3 rounded-2xl border border-line bg-void p-5">
            <p className="text-sm text-fg">Request provider #{chosenProvider}. This records a request. It does not accept the work or record a payment.</p>
            <input value={requesterName} onChange={(event) => setRequesterName(event.target.value)} required placeholder="Your name" className="min-h-12 w-full rounded-xl border border-line bg-raised px-4 text-fg" />
            <input value={requestedService} onChange={(event) => setRequestedService(event.target.value)} required placeholder="What you are requesting" className="min-h-12 w-full rounded-xl border border-line bg-raised px-4 text-fg" />
            <button type="submit" className="min-h-11 rounded-full bg-fg px-5 text-sm text-void">Record the request</button>
          </form>
        ) : null}
        {message ? <p className="mt-4 text-sm text-muted">{message}</p> : null}

        <div className="mt-8 space-y-3">
          <h2 className="font-display text-2xl text-fg">Recorded changes</h2>
          {alerts.length === 0 ? <p className="text-sm text-muted">No recorded change yet.</p> : alerts.map((alert) => (
            <p key={alert.id} className="text-sm text-muted">{alert.text}</p>
          ))}
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <section className="rounded-2xl border border-line bg-void p-5">
            <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">Trust record</p>
            <p className="mt-2 text-sm text-muted">
              {trust
                ? `${trust.recorded_requests} request(s) recorded · ${trust.disputes} dispute(s)`
                : "No trust record is available for the latest post."}
            </p>
            {trust?.unknowns.length ? <p className="mt-2 text-xs text-muted">{trust.unknowns.join(" · ")}</p> : null}
          </section>
          <section className="rounded-2xl border border-line bg-void p-5">
            <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">Event timeline</p>
            {events ? (
              <p className="mt-2 text-sm text-muted">
                {events.completions} completion(s) · {events.payments.length} payment event(s) · {events.disputes.length} dispute event(s)
              </p>
            ) : (
              <p className="mt-2 text-sm text-muted">No event timeline is recorded yet.</p>
            )}
          </section>
        </div>

        <div className="mt-8 space-y-3">
          <h2 className="font-display text-2xl text-fg">Public connections</h2>
          {connections.length === 0 ? (
            <p className="text-sm text-muted">No public connection is recorded yet.</p>
          ) : connections.map((connection) => (
            <article key={connection.id} className="rounded-2xl border border-line bg-void p-5">
              <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">{connection.state}</p>
              <p className="mt-2 text-sm text-fg">{connection.reason}</p>
              <p className="mt-2 text-xs text-muted">
                {connection.unknown || connection.agreement_gap || "No additional unknowns recorded."}
              </p>
              <p className="mt-2 text-sm text-muted">{connection.latest_response || "No public response recorded. A response is not acceptance."}</p>
              {token && createdId === connection.left_id && connection.left_kind === "domain_record" && ["proposed", "authorized", "contacted"].includes(connection.state) ? (
                <form onSubmit={(event) => respondToConnection(event, connection.id, createdId)} className="mt-4 space-y-2">
                  <textarea
                    value={responseNote}
                    onChange={(event) => setResponseNote(event.target.value)}
                    required
                    placeholder="Record the response you received"
                    className="min-h-20 w-full rounded-xl border border-line bg-raised px-3 py-2 text-sm text-fg"
                  />
                  <p className="text-xs text-muted">A response records contact; it is not acceptance.</p>
                  <button type="submit" className="min-h-10 rounded-full border border-line px-4 text-sm text-fg">Record response</button>
                </form>
              ) : null}
              <p className="mt-2 text-sm text-muted">{connection.latest_fulfillment || "No fulfillment recorded. Fulfillment is not payment."}</p>
            </article>
          ))}
        </div>

        <div className="mt-8 space-y-3">
          <h2 className="font-display text-2xl text-fg">Recorded matches</h2>
          <p className="text-sm text-muted">A match is a shared city or shared words in our records. Missing price, availability, or a completed outcome stays listed as unknown.</p>
          {matches.length === 0 ? <p className="text-sm text-muted">No open post to match.</p> : matches.map((match) => (
            <article key={match.need_id} className="rounded-2xl border border-line bg-void p-5">
              <h3 className="font-display text-xl text-fg">{match.need_title}</h3>
              {match.candidates.length === 0 ? <p className="mt-2 text-sm text-muted">No recorded counterparty.</p> : match.candidates.map((candidate) => (
                <div key={`${candidate.kind}-${candidate.id}`} className="mt-3 text-sm text-muted">
                  <p className="text-fg">{candidate.kind}: {candidate.name}</p>
                  <p>{candidate.reasons.join(" · ")}</p>
                  <p>{candidate.stated_price || "Price not recorded"} · {candidate.stated_availability || "Availability not recorded"}</p>
                  <p>{candidate.unknowns.join(" · ")}</p>
                  {candidate.kind === "provider" ? (
                    <button type="button" onClick={() => void chooseProvider(candidate.id)} className="mt-2 min-h-10 text-sm text-cyan">
                      See trust and request this provider
                    </button>
                  ) : null}
                </div>
              ))}
            </article>
          ))}
        </div>

        <div className="mt-8 space-y-3">
          {rows.length === 0 ? (
            <p className="rounded-2xl border border-line bg-void p-5 text-muted">No open jobs, offers, or trades are in our records.</p>
          ) : rows.map((row) => (
            <article key={row.id} className="rounded-2xl border border-line bg-void p-5">
              <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">{row.kind}</p>
              <h2 className="mt-1 font-display text-2xl text-fg">{row.title}</h2>
              <p className="mt-2 text-sm text-muted">{row.detail}</p>
              <p className="mt-2 text-sm text-muted">{row.city || "City not recorded"} · {row.stated_price || "Price not recorded"}</p>
            </article>
          ))}
        </div>
      </Container>
    </main>
  );
}
