import { useCallback, useEffect, useState } from "react";

async function v4Fetch<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/opv3/${path}`, {
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
}

export function OperatingV4({ apiKey }: { apiKey: string }) {
  const [board, setBoard] = useState<Scoreboard | null>(null);
  const [frontier, setFrontier] = useState<Frontier | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, f] = await Promise.all([
        v4Fetch<Scoreboard>("scoreboard", apiKey),
        v4Fetch<Frontier>("frontier", apiKey),
      ]);
      setBoard(b);
      setFrontier(f);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}

      {board?.starved && (
        <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm font-bold">
          STARVED — no real contact for 14+ days. Building is frozen except System Obligations.
        </p>
      )}

      {frontier && (
        <section aria-label="Frozen frontier">
          <h3 className="text-lg font-extrabold">Frozen frontier</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6">{frontier.frontier}</p>
          <p className="mt-1 text-xs text-muted">
            Frozen {frontier.frozen_from} → day 90 on {frontier.day_90}. Everything else is horizon.
          </p>
        </section>
      )}

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
