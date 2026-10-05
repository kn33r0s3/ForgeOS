import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

async function v3Fetch<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
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

interface Bet {
  id: number;
  claim: string;
  status: string;
  deadline: string | null;
  kill_criterion: string;
}

interface Pulse {
  days_since_last_contact: number | null;
  observations: number;
  conversations: number;
  bets_by_status: Record<string, number>;
  highest_proof_level: number;
  verified_rupees: number;
  starved: boolean;
}

interface Gate {
  day: number;
  title: string;
  kill_criterion: string | null;
  result: string | null;
}

export function OperatingV3({ apiKey }: { apiKey: string }) {
  const [bets, setBets] = useState<Bet[]>([]);
  const [pulse, setPulse] = useState<Pulse | null>(null);
  const [gates, setGates] = useState<Gate[]>([]);
  const [violations, setViolations] = useState<{ evidence_id: number; proof_level: number }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [b, p, g, v] = await Promise.all([
        v3Fetch<Bet[]>("bets", apiKey),
        v3Fetch<Pulse>("pulse", apiKey),
        v3Fetch<Gate[]>("gates", apiKey),
        v3Fetch<{ evidence_id: number; proof_level: number }[]>("proof-violations", apiKey),
      ]);
      setBets(b);
      setPulse(p);
      setGates(g);
      setViolations(v);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  const live = bets.filter((b) => b.status === "live");

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}

      {pulse?.starved && (
        <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm font-bold">
          STARVED — no real contact for 14+ days. Build tasks are blocked until a real conversation happens.
        </p>
      )}

      <section aria-label="Pulse scoreboard">
        <h3 className="text-lg font-extrabold">Pulse</h3>
        {pulse ? (
          <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              ["Days since last contact", pulse.days_since_last_contact ?? "never"],
              ["Observations", pulse.observations],
              ["Conversations", pulse.conversations],
              ["Highest proof level", `L${pulse.highest_proof_level}`],
              ["Verified rupees", `Rs ${pulse.verified_rupees}`],
              ["Live bets", pulse.bets_by_status.live ?? 0],
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
      </section>

      <section aria-label="Bets">
        <h3 className="text-lg font-extrabold">Bets ({live.length}/3 live)</h3>
        {bets.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No bets placed. Archive, never delete.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {bets.map((b) => (
              <li key={b.id} className="rounded-card border-2 border-line bg-card p-3 text-sm">
                <span className="mr-2 rounded-full border px-2 py-0.5 text-[10px] uppercase">{b.status}</span>
                <strong>{b.claim}</strong>
                <span className="block text-xs text-muted">Kill: {b.kill_criterion}</span>
                {b.status === "live" && (
                  <div className="mt-2 flex gap-2">
                    {["amplified", "dampened", "killed"].map((d) => (
                      <Button
                        key={d}
                        size="sm"
                        variant="secondary"
                        onClick={async () => {
                          await v3Fetch(`bets/${b.id}/decide`, apiKey, {
                            method: "POST",
                            body: JSON.stringify({ decision: d }),
                          });
                          await load();
                        }}
                      >
                        {d}
                      </Button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Tripwires">
        <h3 className="text-lg font-extrabold">Tripwires</h3>
        {violations.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No proof-level violations. No claim asserts "found" below L5.</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {violations.map((v) => (
              <li key={v.evidence_id} className="rounded-card border-2 border-warning/70 bg-warning/10 p-2">
                Evidence #{v.evidence_id} claims "found" at L{v.proof_level} (needs L5)
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Gates">
        <h3 className="text-lg font-extrabold">Gates</h3>
        {gates.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No gates set. Day 14/30/60/90 milestones with kill criteria go here.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {gates.map((g) => (
              <li key={g.day} className="rounded-card border border-line bg-card p-3 text-sm">
                <strong>Day {g.day}:</strong> {g.title}
                <span className="block text-xs text-muted">
                  Kill criterion: {g.kill_criterion ?? "not set yet"}
                </span>
                {g.result && <span className="block text-xs">Result: {g.result}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
