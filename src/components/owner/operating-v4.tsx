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

export function OperatingV4({ apiKey }: { apiKey: string }) {
  const [board, setBoard] = useState<Scoreboard | null>(null);
  const [frontier, setFrontier] = useState<Frontier | null>(null);
  const [frontierDraft, setFrontierDraft] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [savingHorizon, setSavingHorizon] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, f, s] = await Promise.all([
        v4Fetch<Scoreboard>("scoreboard", apiKey),
        v4Fetch<Frontier>("frontier", apiKey),
        v4Fetch<Selection>("selection", apiKey),
      ]);
      setBoard(b);
      setFrontier(f);
      setFrontierDraft(f.frontier);
      setSelection(s);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);

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
