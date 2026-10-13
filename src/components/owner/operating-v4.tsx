import { useCallback, useEffect, useState } from "react";

async function v4Fetch<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/opv4/${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
      "X-API-Key": key,
    },
  });
  if (response.status === 401) throw new Error("Owner authentication failed.");
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

interface Scoreboard {
  days_since_last_contact: number | null;
  observations: number;
  conversations: number;
  live_bets: number;
  bets_killed: number;
  bets_amplified: number;
  highest_proof_level: number;
  verified_rupees: number;
  sampling_gaps: string[];
  who_not_heard_from: string[];
  owner_time_used: string;
  owner_budget_remaining: string;
  starved: boolean;
}

interface Frontier {
  frontier: string;
  frozen_from: string;
  day_90: string;
  is_default: boolean;
  editable: boolean;
  universe_boundary: false;
}

interface Assessment {
  level: "high" | "medium" | "low" | "unassessed";
  provenance: "observed" | "computed" | "owner-confirmed" | "model-proposed" | "unassessed";
  confirmed: boolean;
  is_evidence: false;
}

interface Candidate {
  candidate_id: string;
  candidate: string;
  source_unknown_id: string | null;
  candidate_lane: "known_unknown" | "unknown_unknown_discovery";
  discovery_source: string | null;
  discovery_basis: string;
  provisional_unknown: boolean;
  model_proposed: boolean;
  claim_or_question: string;
  why_it_matters: string;
  assessments: Record<string, Assessment>;
  evidence_status: string;
  kill_rule: string;
  expected_first_evidence: string;
  horizon_relation: "inside" | "outside" | "unassessed";
  gate_blockers: string[];
  missing_information: string[];
  selection_reason: string | null;
  rank: number | null;
}

interface Responsibility {
  stage: string;
  performed_by: string[];
  current_boundary: string;
  authorization: string;
}

interface Selection {
  ranked_candidates: Candidate[];
  selected_slate: Candidate[];
  live_bet_count: number;
  available_live_slots: number;
  comparison_method: string;
  assessment_guidance: string;
  portfolio_gaps: string[];
  responsibility: Responsibility[];
}



interface OfferRecord {
  id: string;
  title: string;
  audience: "BUYER" | "SELLER" | "CONTRIBUTOR";
  one_sentence_offer: string;
  they_give: string;
  they_get: string;
  cost_to_hami: {
    cash_estimate_npr: number;
    owner_time_minutes_estimate: number;
    assumptions: string;
  };
  consent_text: { en: string; ne: string };
  terms_text: { en: string; ne: string };
  test: { question: string; method: string; sample_size: string; success_signal: string };
  kill_criterion: string;
  depends_on: string[];
  status: "draft" | "owner-approved" | "live" | "killed";
  bet_id: number;
  bet_name: string;
  owner_approved_at: string | null;
  readiness: { blocked: boolean; blockers: string[]; linked_bet_status: string };
  public_copy: boolean;
}

interface OfferLegalRead {
  item_id: string;
  action_id: number | null;
  title: string;
  topics: string[];
  status: string;
  read_by_lawyer: boolean;
  review_record: {
    lawyer_name: string;
    review_date: string;
    source_reference: string;
    summary: string;
    verification: string;
  } | null;
}

interface OfferQueue {
  offers: OfferRecord[];
  legal_read: OfferLegalRead;
  buyer_purchase_accounts: number;
  real_consented_seller_evidence: number;
  outreach_boundary: string;
}

export function OperatingV4({ apiKey }: { apiKey: string }) {
  const [board, setBoard] = useState<Scoreboard | null>(null);
  const [frontier, setFrontier] = useState<Frontier | null>(null);
  const [frontierDraft, setFrontierDraft] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [offerQueue, setOfferQueue] = useState<OfferQueue | null>(null);
  const [offerBusy, setOfferBusy] = useState<string | null>(null);
  const [killReasons, setKillReasons] = useState<Record<string, string>>({});
  const [legalForm, setLegalForm] = useState({ lawyer_name: "", review_date: "", source_reference: "", summary: "" });
  const [savingHorizon, setSavingHorizon] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, f, s, offers] = await Promise.all([
        v4Fetch<Scoreboard>("scoreboard", apiKey),
        v4Fetch<Frontier>("frontier", apiKey),
        v4Fetch<Selection>("selection", apiKey),
        v4Fetch<OfferQueue>("offers", apiKey),
      ]);
      setBoard(b);
      setFrontier(f);
      setFrontierDraft(f.frontier);
      setSelection(s);
      setOfferQueue(offers);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);


  async function seedOfferDrafts() {
    setOfferBusy("seed");
    setError(null);
    setNotice(null);
    try {
      await v4Fetch("offers/seed", apiKey, { method: "POST" });
      setNotice("Draft offer views seeded idempotently. Nothing was published or sent.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Offer drafts could not be seeded.");
    } finally {
      setOfferBusy(null);
    }
  }

  async function changeOfferStatus(
    offer: OfferRecord,
    status: "owner-approved" | "live" | "killed",
  ) {
    const kill_reason = (killReasons[offer.id] ?? "").trim();
    if (status === "killed" && !kill_reason) {
      setError("Give a short reason before killing an offer.");
      return;
    }
    setOfferBusy(offer.id);
    setError(null);
    setNotice(null);
    try {
      await v4Fetch("offers/" + encodeURIComponent(offer.id) + "/status", apiKey, {
        method: "POST",
        body: JSON.stringify({ status, kill_reason: status === "killed" ? kill_reason : undefined }),
      });
      setNotice(status === "owner-approved"
        ? "Offer approved by owner. Public copy is eligible only while all current gates remain clear."
        : status === "live"
          ? "Offer marked live after owner approval and current gate checks."
          : "Offer killed and the reason recorded.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Offer status could not be changed.");
    } finally {
      setOfferBusy(null);
    }
  }

  async function recordLegalRead() {
    setOfferBusy("legal-read");
    setError(null);
    setNotice(null);
    try {
      await v4Fetch<OfferLegalRead>("offers/legal-read", apiKey, {
        method: "POST",
        body: JSON.stringify(legalForm),
      });
      setNotice("Lawyer-read details recorded as owner-reported. This does not independently verify the lawyer or advice.");
      setLegalForm({ lawyer_name: "", review_date: "", source_reference: "", summary: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Legal-read item could not be recorded.");
    } finally {
      setOfferBusy(null);
    }
  }

  async function saveWatchHorizon() {
    setSavingHorizon(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await v4Fetch<{
        frontier: string;
        is_default: boolean;
        universe_boundary: false;
      }>("horizon/watch", apiKey, {
        method: "PUT",
        body: JSON.stringify({ frontier: frontierDraft }),
      });
      setFrontier((current) => current ? { ...current, ...updated } : null);
      setFrontierDraft(updated.frontier);
      setNotice("Watch horizon updated. It remains a focus, not a universe boundary.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Watch horizon could not be updated.");
    } finally {
      setSavingHorizon(false);
    }
  }

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-card border border-success/50 bg-success/10 p-4 text-sm">{notice}</p> : null}

      {board?.starved && (
        <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm font-bold">
          STARVED — no real contact for 14+ days. Building is frozen except System Obligations.
        </p>
      )}

      {frontier && (
        <section aria-label="Editable watch horizon" className="rounded-card border border-line bg-card p-5">
          <h3 className="text-lg font-extrabold">Current watch horizon</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6">
            {frontier.is_default ? "Initial focus from the prior watch line. " : "Owner-edited focus. "}
            This guides attention but is not a universe boundary; the exploration slot can go outside it.
          </p>
          <label className="mt-3 block text-sm font-semibold">
            Watch focus
            <textarea
              value={frontierDraft}
              maxLength={2000}
              onChange={(event) => setFrontierDraft(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink"
              aria-label="Current watch horizon"
            />
          </label>
          <button
            type="button"
            onClick={saveWatchHorizon}
            disabled={savingHorizon || !frontierDraft.trim() || frontierDraft === frontier.frontier}
            className="mt-3 min-h-10 rounded-lg bg-accent px-4 py-2 text-sm font-bold text-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {savingHorizon ? "Saving…" : "Save watch horizon"}
          </button>
          <p className="mt-2 text-xs text-muted">
            Previous wording remains in the Horizon event history. Prior freeze dates: {frontier.frozen_from} → {frontier.day_90}.
          </p>
        </section>
      )}

      <section aria-label="Next experiments" className="space-y-4">
        <div>
          <h3 className="text-lg font-extrabold">Next experiments</h3>
          <p className="mt-1 text-sm leading-6 text-muted">
            Read-only global comparison of explicitly registered candidate Bets. No candidate is promoted,
            contacted, or executed here. Opportunity and money rankings remain separate exploitation lanes.
          </p>
          {selection && <p className="mt-2 text-xs text-muted">{selection.comparison_method}</p>}
          {selection && <p className="mt-1 text-xs text-muted">{selection.assessment_guidance}</p>}
        </div>
        {selection ? (
          <>
            <p className="text-sm font-semibold">
              {selection.live_bet_count} live Bets · {selection.available_live_slots} available live slots · {selection.selected_slate.length} recommendations for owner review
            </p>
            {selection.portfolio_gaps.map((gap) => (
              <p key={gap} role="status" className="rounded-lg border border-warning/50 bg-warning/10 p-3 text-sm">{gap}</p>
            ))}
            {selection.selected_slate.length ? selection.selected_slate.map((item) => (
              <CandidateCard key={item.candidate_id} candidate={item} selected />
            )) : (
              <p className="rounded-card border border-line bg-card p-4 text-sm text-muted">
                No candidate currently passes all admission gates for an available review slot.
                Blocked candidates and missing information remain visible below.
              </p>
            )}
            <details className="rounded-card border border-line bg-card p-4">
              <summary className="cursor-pointer font-bold">
                Full ranked candidate pool ({selection.ranked_candidates.length})
              </summary>
              <div className="mt-4 space-y-3">
                {selection.ranked_candidates.map((item) => (
                  <CandidateCard
                    key={item.candidate_id}
                    candidate={item}
                    selected={selection.selected_slate.some((chosen) => chosen.candidate_id === item.candidate_id)}
                  />
                ))}
              </div>
            </details>
            <details className="rounded-card border border-line bg-card p-4">
              <summary className="cursor-pointer font-bold">Who performs each stage today?</summary>
              <div className="mt-4 space-y-3">
                {selection.responsibility.map((stage) => (
                  <article key={stage.stage} className="border-t border-line pt-3">
                    <h4 className="font-bold">{stage.stage} <span className="font-normal text-muted">· {stage.performed_by.join(", ")}</span></h4>
                    <p className="mt-1 text-sm text-muted">{stage.current_boundary}</p>
                    <p className="mt-1 text-xs text-muted"><strong>Authorization:</strong> {stage.authorization}</p>
                  </article>
                ))}
              </div>
            </details>
          </>
        ) : (
          <p className="rounded-card border border-line bg-card p-4 text-sm text-muted">Loading the owner-only candidate comparison…</p>
        )}
      </section>


      <section aria-label="Offer approval queue" className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-extrabold">Offers · owner approval</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              Offers are views attached to existing Bets, not a new primitive or route. Drafts are private.
              Only explicitly owner-approved copy can appear under Experiments, and only while its gates remain clear.
              No guaranteed outcomes or unearned claims.
            </p>
          </div>
          <button type="button" onClick={seedOfferDrafts} disabled={offerBusy !== null}
            className="min-h-10 rounded-lg border border-line px-4 py-2 text-sm font-bold disabled:opacity-50">
            {offerBusy === "seed" ? "Seeding…" : "Seed / refresh drafts"}
          </button>
        </div>

        {offerQueue ? (
          <>
            <div className="rounded-card border border-line bg-card p-4">
              <p className="font-bold">{offerQueue.legal_read.title}</p>
              <p className="mt-1 text-sm"><strong>Status:</strong> {offerQueue.legal_read.status}</p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-muted">
                {offerQueue.legal_read.topics.map((topic) => <li key={topic}>{topic}</li>)}
              </ul>
              {offerQueue.legal_read.review_record && (
                <p className="mt-2 text-xs text-muted">
                  Recorded by owner for {offerQueue.legal_read.review_record.lawyer_name} · {offerQueue.legal_read.review_record.review_date} ·
                  {" "}{offerQueue.legal_read.review_record.source_reference}. {offerQueue.legal_read.review_record.verification}.
                </p>
              )}
              <form className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2"
                onSubmit={(event) => { event.preventDefault(); void recordLegalRead(); }}>
                <p className="text-sm font-semibold sm:col-span-2">
                  Record this only after the review has actually happened. The lawyer identity and advice are owner-reported, not independently verified.
                </p>
                <label className="block text-sm">
                  Reviewing lawyer
                  <input required minLength={2} maxLength={200} value={legalForm.lawyer_name}
                    onChange={(event) => setLegalForm({ ...legalForm, lawyer_name: event.target.value })}
                    className="mt-1 w-full rounded-lg border border-line bg-background px-3 py-2 text-ink" />
                </label>
                <label className="block text-sm">
                  Review date
                  <input required type="date" value={legalForm.review_date}
                    onChange={(event) => setLegalForm({ ...legalForm, review_date: event.target.value })}
                    className="mt-1 w-full rounded-lg border border-line bg-background px-3 py-2 text-ink" />
                </label>
                <label className="block text-sm sm:col-span-2">
                  Review/evidence reference
                  <input required minLength={4} maxLength={500} value={legalForm.source_reference}
                    onChange={(event) => setLegalForm({ ...legalForm, source_reference: event.target.value })}
                    placeholder="Private document reference; do not paste sensitive legal advice here"
                    className="mt-1 w-full rounded-lg border border-line bg-background px-3 py-2 text-ink" />
                </label>
                <label className="block text-sm sm:col-span-2">
                  Summary and follow-up conditions
                  <textarea required minLength={10} maxLength={3000} rows={3} value={legalForm.summary}
                    onChange={(event) => setLegalForm({ ...legalForm, summary: event.target.value })}
                    className="mt-1 w-full rounded-lg border border-line bg-background px-3 py-2 text-ink" />
                </label>
                <button type="submit" disabled={offerBusy !== null}
                  className="min-h-10 rounded-lg bg-accent px-4 py-2 text-sm font-bold text-black disabled:opacity-50 sm:col-span-2">
                  {offerBusy === "legal-read" ? "Recording…" : "Record actual lawyer read"}
                </button>
              </form>
            </div>

            <p className="text-xs text-muted">
              Gate counts are real-data checks, not proof by themselves: {offerQueue.buyer_purchase_accounts} consented buyer/circle purchase accounts ·
              {" "}{offerQueue.real_consented_seller_evidence} real firsthand consented seller evidence records linked to Rescue Week’s Bet.
            </p>

            {offerQueue.offers.length === 0 ? (
              <p className="rounded-card border border-line bg-card p-4 text-sm text-muted">
                No offer drafts yet. Seed the five draft views above; this does not contact anyone or publish copy.
              </p>
            ) : (
              <div className="grid gap-4">
                {offerQueue.offers.map((offer) => (
                  <article key={offer.id} className="rounded-card border border-line bg-card p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-line px-2 py-1 text-xs font-bold">{offer.audience}</span>
                      <span className="rounded-full border border-line px-2 py-1 text-xs">{offer.status}</span>
                      <span className="text-xs text-muted">Bet #{offer.bet_id} · {offer.bet_name}</span>
                      {offer.public_copy ? <span className="text-xs font-bold text-success">Public copy eligible</span> : null}
                    </div>
                    <h4 className="mt-3 font-extrabold">{offer.title}</h4>
                    <p className="mt-1 text-sm leading-6">{offer.one_sentence_offer}</p>
                    <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div><dt className="text-xs font-bold uppercase text-muted">They give</dt><dd className="mt-1 text-sm">{offer.they_give}</dd></div>
                      <div><dt className="text-xs font-bold uppercase text-muted">They get</dt><dd className="mt-1 text-sm">{offer.they_get}</dd></div>
                      <div><dt className="text-xs font-bold uppercase text-muted">Cost to Hami (estimate, includes owner time)</dt>
                        <dd className="mt-1 text-sm">NPR {offer.cost_to_hami.cash_estimate_npr} cash · {offer.cost_to_hami.owner_time_minutes_estimate} owner-minutes</dd>
                        <dd className="mt-1 text-xs text-muted">{offer.cost_to_hami.assumptions}</dd>
                      </div>
                      <div><dt className="text-xs font-bold uppercase text-muted">Test</dt>
                        <dd className="mt-1 text-sm">{offer.test.question}</dd>
                        <dd className="mt-1 text-xs text-muted">{offer.test.method}</dd>
                        <dd className="mt-1 text-xs text-muted">Sample: {offer.test.sample_size}</dd>
                        <dd className="mt-1 text-xs text-muted">Success signal: {offer.test.success_signal}</dd>
                      </div>
                    </dl>
                    <details className="mt-4 border-t border-line pt-3">
                      <summary className="cursor-pointer text-sm font-bold">Consent, terms, dependencies, and kill criterion</summary>
                      <div className="mt-3 grid gap-4 sm:grid-cols-2">
                        <div>
                          <p className="text-xs font-bold uppercase text-muted">Consent · English</p>
                          <p className="mt-1 text-sm leading-6">{offer.consent_text.en}</p>
                          <p className="mt-3 text-xs font-bold uppercase text-muted">Consent · नेपाली</p>
                          <p className="mt-1 text-sm leading-6">{offer.consent_text.ne}</p>
                        </div>
                        <div>
                          <p className="text-xs font-bold uppercase text-muted">Terms · English</p>
                          <p className="mt-1 text-sm leading-6">{offer.terms_text.en}</p>
                          <p className="mt-3 text-xs font-bold uppercase text-muted">Terms · नेपाली</p>
                          <p className="mt-1 text-sm leading-6">{offer.terms_text.ne}</p>
                        </div>
                      </div>
                      <p className="mt-3 text-sm"><strong>Depends on:</strong> {offer.depends_on.join(" · ") || "No named dependency"}</p>
                      <p className="mt-2 text-sm"><strong>Kill criterion:</strong> {offer.kill_criterion}</p>
                    </details>
                    {offer.readiness.blockers.length > 0 && (
                      <div role="status" className="mt-4 rounded-lg border border-warning/50 bg-warning/10 p-3">
                        <p className="text-sm font-bold">Blocked · not eligible for approval/activation</p>
                        <ul className="mt-1 list-inside list-disc space-y-1 text-sm">
                          {offer.readiness.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
                        </ul>
                      </div>
                    )}
                    {offer.status !== "killed" && (
                      <div className="mt-4 border-t border-line pt-4">
                        <label className="block text-sm">
                          Kill reason (required to close this offer)
                          <input value={killReasons[offer.id] ?? ""} maxLength={1000}
                            onChange={(event) => setKillReasons((current) => ({ ...current, [offer.id]: event.target.value }))}
                            className="mt-1 w-full rounded-lg border border-line bg-background px-3 py-2 text-ink" />
                        </label>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {offer.status === "draft" && (
                            <button type="button" onClick={() => void changeOfferStatus(offer, "owner-approved")}
                              disabled={offerBusy !== null || offer.readiness.blocked}
                              className="min-h-10 rounded-lg bg-accent px-4 py-2 text-sm font-bold text-black disabled:opacity-50">
                              {offerBusy === offer.id ? "Saving…" : "Owner-approve copy"}
                            </button>
                          )}
                          {offer.status === "owner-approved" && (
                            <button type="button" onClick={() => void changeOfferStatus(offer, "live")}
                              disabled={offerBusy !== null || offer.readiness.blocked || offer.readiness.linked_bet_status !== "live"}
                              className="min-h-10 rounded-lg bg-accent px-4 py-2 text-sm font-bold text-black disabled:opacity-50">
                              {offerBusy === offer.id ? "Saving…" : "Mark live"}
                            </button>
                          )}
                          <button type="button" onClick={() => void changeOfferStatus(offer, "killed")}
                            disabled={offerBusy !== null || !(killReasons[offer.id] ?? "").trim()}
                            className="min-h-10 rounded-lg border border-danger/50 px-4 py-2 text-sm font-bold text-danger disabled:opacity-50">
                            Kill offer
                          </button>
                        </div>
                        {offer.status === "owner-approved" && offer.readiness.linked_bet_status !== "live" && (
                          <p className="mt-2 text-xs text-muted">Activation is also blocked because the linked Bet is not live.</p>
                        )}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
            <p className="text-sm text-muted">{offerQueue.outreach_boundary}</p>
          </>
        ) : (
          <p className="rounded-card border border-line bg-card p-4 text-sm text-muted">
            Loading the owner-only offer queue…
          </p>
        )}
      </section>

      <section aria-label="Honest scoreboard">
        <h3 className="text-lg font-extrabold">Scoreboard</h3>
        <p className="mt-1 text-xs text-muted">Read-only. Zero and unknown are valid results.</p>
        {board ? (
          <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              ["Days since last contact", board.days_since_last_contact ?? "never"],
              ["Observations logged", board.observations],
              ["Conversations held", board.conversations],
              ["Live bets", board.live_bets],
              ["Bets killed", board.bets_killed],
              ["Bets amplified", board.bets_amplified],
              ["Highest proof level", `L${board.highest_proof_level}`],
              ["Verified rupees", `Rs ${board.verified_rupees}`],
              ["Owner time used", board.owner_time_used],
              ["Owner budget remaining", board.owner_budget_remaining],
            ].map(([k, v]) => (
              <div key={k} className="rounded-card border border-line bg-card p-3">
                <dt className="text-xs text-muted">{k}</dt>
                <dd className="text-xl font-extrabold">{v}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-2 text-sm text-muted">Loading…</p>
        )}
        {board && board.sampling_gaps.length > 0 && (
          <p className="mt-3 text-sm text-muted">
            <strong>Sampling gaps:</strong> no observations from {board.sampling_gaps.join(", ")}.
          </p>
        )}
        {board && board.who_not_heard_from.length > 0 && (
          <p className="mt-1 text-sm text-muted">
            <strong>Not heard from:</strong> {board.who_not_heard_from.join(", ")}.
          </p>
        )}
      </section>
    </div>
  );
}

function CandidateCard({ candidate, selected }: { candidate: Candidate; selected: boolean }) {
  return (
    <article className="rounded-card border border-line bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-line px-2 py-1 text-xs font-bold">
          {candidate.rank === null ? "Unranked" : `Rank ${candidate.rank}`}
        </span>
        <span className="text-xs text-muted">{candidate.source_unknown_id ?? candidate.candidate_id}</span>
        <span className={`rounded-full px-2 py-1 text-xs font-bold ${
          candidate.gate_blockers.length
            ? "bg-danger/10 text-danger"
            : selected
              ? "bg-success/10 text-success"
              : "bg-surface text-muted"
        }`}>
          {candidate.gate_blockers.length ? "Blocked" : selected ? "Selected for review" : "Admitted"}
        </span>
        <span className={`rounded-full border px-2 py-1 text-xs font-bold ${
          candidate.candidate_lane === "unknown_unknown_discovery"
            ? "border-amber-500/40 text-amber-600"
            : "border-line text-muted"
        }`}>
          {candidate.candidate_lane === "unknown_unknown_discovery" ? "DISCOVERY" : "KNOWN UNKNOWN"}
        </span>
        {candidate.provisional_unknown && (
          <span className="rounded-full border border-line px-2 py-1 text-xs text-muted">
            provisional · from discovery
          </span>
        )}
      </div>
      <h4 className="mt-3 font-extrabold">{candidate.candidate}</h4>
      <p className="mt-1 text-sm leading-6">{candidate.claim_or_question}</p>
      {candidate.candidate_lane === "unknown_unknown_discovery" && candidate.discovery_basis && (
        <p className="mt-2 text-sm text-muted"><strong>Why Hami suspects a blind spot:</strong> {candidate.discovery_basis}</p>
      )}
      <p className="mt-2 text-sm text-muted"><strong>Why it matters:</strong> {candidate.why_it_matters || "Unassessed"}</p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {Object.entries(candidate.assessments).map(([dimension, assessment]) => (
          <div key={dimension} className="rounded-lg border border-line p-2">
            <dt className="text-xs capitalize text-muted">{dimension.replaceAll("_", " ")}</dt>
            <dd className="text-sm font-semibold">
              {assessment.level} · {assessment.provenance}
              {assessment.provenance === "model-proposed" ? " (unconfirmed; not evidence)" : ""}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-muted"><strong>Evidence:</strong> {candidate.evidence_status}</p>
      <p className="mt-1 text-xs text-muted"><strong>First evidence:</strong> {candidate.expected_first_evidence} · <strong>Horizon:</strong> {candidate.horizon_relation}</p>
      <p className="mt-1 text-xs text-muted"><strong>Kill rule:</strong> {candidate.kill_rule}</p>
      {candidate.gate_blockers.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-bold text-danger">Admission blockers</p>
          <ul className="list-inside list-disc text-xs text-danger">
            {candidate.gate_blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
          </ul>
        </div>
      )}
      {candidate.missing_information.length > 0 && (
        <p className="mt-2 text-xs text-muted"><strong>Missing information:</strong> {candidate.missing_information.join("; ")}</p>
      )}
      <p className="mt-3 border-t border-line pt-2 text-sm"><strong>Selection:</strong> {candidate.selection_reason ?? "Not selected."}</p>
    </article>
  );
}
