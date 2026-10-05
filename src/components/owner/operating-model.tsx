import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

async function opFetch<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/operating/${path}`, {
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

interface Assumption {
  id: number;
  statement: string;
  status: string;
  deal_killer: boolean;
  cost_to_test: string | null;
  cheapest_test: string | null;
  evidence_links: string[];
  milestone: string | null;
  source_note: string | null;
}

interface Probe {
  id: number;
  assumption_id: number;
  assumption: string | null;
  probe_type: string;
  affordable_loss: string;
  kill_criterion: string;
  result: string | null;
  decision: string | null;
}

interface Capability {
  id: number;
  name: string;
  description: string | null;
  event_id: number;
  evidence_id: number;
}

export function OperatingModel({ apiKey }: { apiKey: string }) {
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [probes, setProbes] = useState<Probe[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, p, c] = await Promise.all([
        opFetch<Assumption[]>("assumptions", apiKey),
        opFetch<Probe[]>("probes", apiKey),
        opFetch<Capability[]>("capabilities", apiKey),
      ]);
      setAssumptions(a);
      setProbes(p);
      setCapabilities(c);
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
      {notice ? <p role="status" className="rounded-card border-2 border-success/70 bg-success/10 p-4 text-sm">{notice}</p> : null}

      <section aria-label="Assumption register">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-extrabold">Assumption register</h3>
          <Button
            size="sm"
            variant="secondary"
            onClick={async () => {
              await opFetch("assumptions/seed", apiKey, { method: "POST" });
              setNotice("Assumptions seeded.");
              await load();
            }}
          >
            Seed the six
          </Button>
        </div>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Ranked deal-killer + cheapest first. Nothing is marked supported without linked evidence.
        </p>
        {assumptions.length === 0 ? (
          <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">
            No assumptions recorded. Seed the six to begin.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {assumptions.map((a) => (
              <article key={a.id} className="rounded-card border-2 border-line bg-card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  {a.deal_killer && (
                    <span className="rounded-full border border-danger/70 bg-danger/10 px-2 py-0.5 text-[10px] font-bold uppercase text-danger">
                      Deal-killer
                    </span>
                  )}
                  <span className="rounded-full border px-2 py-0.5 text-[10px] uppercase">{a.status}</span>
                  {a.milestone && <span className="text-xs text-muted">Milestone: {a.milestone}</span>}
                </div>
                <p className="mt-2 text-sm font-bold">{a.statement}</p>
                <p className="mt-1 text-xs text-muted">
                  Cheapest test: {a.cheapest_test} · Cost: {a.cost_to_test}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Evidence: {a.evidence_links.length > 0 ? a.evidence_links.join(", ") : "none linked"}
                </p>
                {a.source_note && <p className="mt-1 text-xs italic text-muted">Source: {a.source_note}</p>}
              </article>
            ))}
          </div>
        )}
      </section>

      <section aria-label="Probe portfolio">
        <h3 className="text-lg font-extrabold">Probe portfolio ({probes.length})</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Each probe tests one assumption. Observations run in parallel; conversations in batches of 5;
          one intervention at a time.
        </p>
        {probes.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No probes yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {probes.map((p) => (
              <li key={p.id} className="rounded-card border border-line bg-card p-3 text-sm">
                <span className="mr-2 rounded-full border px-2 py-0.5 text-[10px] uppercase">{p.probe_type}</span>
                <strong>{p.assumption}</strong>
                <span className="block text-xs text-muted">
                  Affordable loss: {p.affordable_loss} · Kill: {p.kill_criterion}
                </span>
                {p.decision ? (
                  <span className="mt-1 inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase">
                    {p.decision}
                  </span>
                ) : (
                  <span className="mt-1 inline-block text-xs text-muted">Running</span>
                )}
                {p.result && <p className="mt-1 text-xs">Result: {p.result}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Capability map">
        <h3 className="text-lg font-extrabold">Capability map ({capabilities.length})</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Only verified outcomes (Event + Evidence) appear here — never prose claims.
        </p>
        {capabilities.length === 0 ? (
          <p className="mt-2 rounded-card border border-line bg-card p-4 text-sm text-muted">
            No verified capabilities yet. Nothing has produced a verified outcome.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {capabilities.map((c) => (
              <li key={c.id} className="rounded-card border-2 border-success/70 bg-success/10 p-3 text-sm">
                <strong>{c.name}</strong>
                {c.description && <p className="text-xs text-muted">{c.description}</p>}
                <p className="text-xs text-muted">
                  Event #{c.event_id} · Evidence #{c.evidence_id}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
