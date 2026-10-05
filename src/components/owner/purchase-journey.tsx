import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

async function residueFetch<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/residue/${path}`, {
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

interface Journey {
  id: number;
  perspective: string;
  claim: string;
  journey: Record<string, string | boolean>;
  recorded_at: string | null;
}

interface ResidueFlag {
  id: number;
  evidence_id: number;
  observation_perspective: string;
  hypothesis_perspectives: string[];
  claim: string | null;
}

const FIELDS = [
  { key: "consulted_who_where", label: "Who was consulted, and where?", hint: "e.g. Asked my sister on Viber; asked in a friends group chat" },
  { key: "what_was_said", label: "What was said?", hint: "In your own words — no screenshots, no private chat quotes" },
  { key: "what_was_checked", label: "What was checked before buying?", hint: "e.g. Facebook reviews, photos, asked about COD" },
  { key: "what_almost_stopped", label: "What almost stopped the purchase?", hint: "The doubt, friction, or missing thing that nearly killed it" },
  { key: "what_decided_it", label: "What decided it in the end?", hint: "The single thing that tipped it to yes" },
] as const;

export function PurchaseJourney({ apiKey }: { apiKey: string }) {
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [flags, setFlags] = useState<ResidueFlag[]>([]);
  const [status, setStatus] = useState<{ journey_count: number; threshold: number; outcome_recorded: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({ perspective: "BUYER" });
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [j, f, s] = await Promise.all([
        residueFetch<Journey[]>("journeys", apiKey),
        residueFetch<ResidueFlag[]>("flags", apiKey),
        residueFetch<{ journey_count: number; threshold: number; outcome_recorded: boolean }>("experiment-status", apiKey),
      ]);
      setJourneys(j);
      setFlags(f);
      setStatus(s);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!consent) {
      setError("Consent is required before recording a purchase journey.");
      return;
    }
    setBusy(true);
    try {
      await residueFetch("journeys", apiKey, {
        method: "POST",
        body: JSON.stringify({ ...form, consent_given: true }),
      });
      setNotice("Journey recorded. Thank you — this is first-person evidence.");
      setError(null);
      setForm({ perspective: "BUYER" });
      setConsent(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-card border-2 border-success/70 bg-success/10 p-4 text-sm">{notice}</p> : null}

      <section aria-label="Experiment status">
        <h3 className="text-lg font-extrabold">Experiment: Where is the sale decided?</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Hypothesis: sales may be decided in private buyer-side talk that sellers never see.
          Outcome stays blank until {status?.threshold ?? 10} journey accounts exist — currently{" "}
          <strong>{status?.journey_count ?? "…"}</strong>.
        </p>
      </section>

      <section aria-label="Record a purchase journey">
        <h3 className="text-lg font-extrabold">Record a purchase journey</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Your own account of a purchase you made — never anyone else's private messages.
          No screenshots, no chat quotes. Only what you yourself experienced, with your consent.
        </p>
        <form onSubmit={submit} className="mt-4 max-w-2xl space-y-4 rounded-card border-2 border-line bg-card p-4">
          <label className="block text-sm">
            <span className="font-bold">Perspective</span>
            <select
              className="mt-1 w-full rounded-card border border-line bg-background p-2 text-sm"
              value={form.perspective ?? "BUYER"}
              onChange={(e) => setForm({ ...form, perspective: e.target.value })}
            >
              <option value="BUYER">BUYER — my own purchase</option>
              <option value="CIRCLE">CIRCLE — discussion around a purchase I was part of</option>
            </select>
          </label>
          {FIELDS.map((f) => (
            <label key={f.key} className="block text-sm">
              <span className="font-bold">{f.label}</span>
              <span className="block text-xs text-muted">{f.hint}</span>
              <textarea
                required
                className="mt-1 w-full rounded-card border border-line bg-background p-2 text-sm"
                rows={2}
                value={form[f.key] ?? ""}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
              />
            </label>
          ))}
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>
              <strong>Consent:</strong> I confirm this is my own account, given freely, and I agree
              to it being recorded as evidence. No private chat content from others is included.
            </span>
          </label>
          <Button type="submit" disabled={busy}>
            {busy ? "Recording…" : "Record journey"}
          </Button>
        </form>
      </section>

      <section aria-label="Recorded journeys">
        <h3 className="text-lg font-extrabold">Recorded journeys ({journeys.length})</h3>
        {journeys.length === 0 ? (
          <p className="mt-2 text-sm text-muted">None recorded yet. The first journey starts the buyer-side evidence base.</p>
        ) : (
          <div className="mt-3 space-y-3">
            {journeys.map((j) => (
              <details key={j.id} className="rounded-card border border-line bg-card p-4">
                <summary className="cursor-pointer text-sm font-bold">
                  <span className="mr-2 rounded-full border px-2 py-0.5 text-[10px] uppercase">{j.perspective}</span>
                  {j.claim}
                </summary>
                <dl className="mt-3 space-y-2 text-sm">
                  {FIELDS.map((f) => (
                    <div key={f.key}>
                      <dt className="font-bold text-accent">{f.label}</dt>
                      <dd className="text-muted">{String(j.journey[f.key] ?? "—")}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            ))}
          </div>
        )}
      </section>

      <section aria-label="Residue flags">
        <h3 className="text-lg font-extrabold">Residue flags ({flags.length})</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Observations no current hypothesis speaks for. All recorded hypotheses are SELLER-side —
          the first BUYER or CIRCLE observation is residue by definition.
        </p>
        {flags.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No unreviewed residue. Every recorded observation fits a hypothesis.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {flags.map((f) => (
              <li key={f.id} className="rounded-card border-2 border-warning/70 bg-warning/10 p-3 text-sm">
                <strong>{f.observation_perspective}</strong> observation #{f.evidence_id} — {f.claim}
                <span className="block text-xs text-muted">
                  Hypotheses cover: {f.hypothesis_perspectives.join(", ") || "none"}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-2"
                  onClick={async () => {
                    await residueFetch(`flags/${f.id}/review`, apiKey, {
                      method: "POST",
                      body: JSON.stringify({ notes: "Reviewed by owner." }),
                    });
                    await load();
                  }}
                >
                  Mark reviewed
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
