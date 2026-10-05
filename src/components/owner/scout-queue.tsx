import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

async function scoutFetch<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/scout/${path}`, {
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

interface Draft {
  id: number;
  candidate_entity_id: number;
  observed_fact: string;
  message_en: string;
  message_ne: string;
  status: string;
}

interface RegistryExperiment {
  id: number;
  action: string;
  kind: string;
  status: string;
  five_fields: {
    reality: string;
    possibility: string;
    constraint: string;
    constraint_state: string;
    intervention: string;
    outcome: string;
  } | null;
}

export function ScoutQueue({ apiKey }: { apiKey: string }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [experiments, setExperiments] = useState<RegistryExperiment[]>([]);
  const [config, setConfig] = useState<{ daily_cap: number; sent_today: number } | null>(null);
  const [dnc, setDnc] = useState<{ entity_id: number; reason: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [editEn, setEditEn] = useState("");
  const [editNe, setEditNe] = useState("");

  const load = useCallback(async () => {
    try {
      const [d, e, c, n] = await Promise.all([
        scoutFetch<Draft[]>("drafts", apiKey),
        scoutFetch<RegistryExperiment[]>("experiments", apiKey),
        scoutFetch<{ daily_cap: number; sent_today: number }>("config", apiKey),
        scoutFetch<{ entity_id: number; reason: string }[]>("do-not-contact", apiKey),
      ]);
      setDrafts(d);
      setExperiments(e);
      setConfig(c);
      setDnc(n);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    }
  }, [apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(fn: () => Promise<unknown>, okMsg: string) {
    try {
      await fn();
      setNotice(okMsg);
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    }
  }

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-card border-2 border-danger/70 bg-danger/10 p-4 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-card border-2 border-success/70 bg-success/10 p-4 text-sm">{notice}</p> : null}

      {/* Approval queue */}
      <section aria-label="Approval queue">
        <h3 className="text-lg font-extrabold">Approval queue</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Review each draft. You edit the words, you approve, and you send from your own account —
          nothing here sends anything by itself. Daily cap: {config ? `${config.sent_today}/${config.daily_cap}` : "…"} sent today.
        </p>
        {drafts.length === 0 ? (
          <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">
            No drafts awaiting review. The queue is empty — no candidates have been scouted yet.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {drafts.map((d) => (
              <article key={d.id} className="rounded-card border-2 border-line bg-card p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-muted">
                  Draft #{d.id} · {d.status} · observed: {d.observed_fact}
                </p>
                {editing === d.id ? (
                  <div className="mt-3 space-y-3">
                    <label className="block text-sm">
                      <span className="font-bold">English</span>
                      <textarea
                        className="mt-1 w-full rounded-card border border-line bg-background p-2 text-sm"
                        rows={4}
                        value={editEn}
                        onChange={(e) => setEditEn(e.target.value)}
                      />
                    </label>
                    <label className="block text-sm">
                      <span className="font-bold">Nepali</span>
                      <textarea
                        className="mt-1 w-full rounded-card border border-line bg-background p-2 text-sm"
                        rows={4}
                        value={editNe}
                        onChange={(e) => setEditNe(e.target.value)}
                      />
                    </label>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() =>
                          act(
                            () => scoutFetch(`drafts/${d.id}/edit`, apiKey, { method: "POST", body: JSON.stringify({ message_en: editEn, message_ne: editNe }) }),
                            "Draft updated.",
                          ).then(() => setEditing(null))
                        }
                      >
                        Save
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="mt-2 text-sm leading-6">{d.message_en}</p>
                    <p className="mt-2 text-sm leading-6 text-muted">{d.message_ne}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {d.status === "DRAFT" && (
                        <Button size="sm" onClick={() => act(() => scoutFetch(`drafts/${d.id}/approve`, apiKey, { method: "POST" }), "Draft approved. Send it from your own account, then mark sent.")}>
                          Approve
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          setEditing(d.id);
                          setEditEn(d.message_en);
                          setEditNe(d.message_ne);
                        }}
                      >
                        Edit
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => act(() => scoutFetch(`drafts/${d.id}/skip`, apiKey, { method: "POST" }), "Draft skipped.")}>
                        Skip
                      </Button>
                      {d.status === "APPROVED" && (
                        <Button
                          size="sm"
                          variant="warning"
                          onClick={() => {
                            const channel = window.prompt("Which channel did you send from? (e.g. facebook, viber, whatsapp)");
                            if (channel) act(() => scoutFetch(`drafts/${d.id}/sent`, apiKey, { method: "POST", body: JSON.stringify({ channel }) }), "Send logged with your authorization.");
                          }}
                        >
                          I sent it — mark sent
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {/* Experiments registry */}
      <section aria-label="Experiments registry">
        <h3 className="text-lg font-extrabold">Experiments registry</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          Observation experiments may run in parallel. Conversations run in batches of 5 with your approval.
          At most one active intervention at a time.
        </p>
        {experiments.length === 0 ? (
          <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">
            Registry not seeded yet.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {experiments.map((e) => (
              <details key={e.id} className="rounded-card border border-line bg-card p-4">
                <summary className="cursor-pointer text-sm font-bold">
                  <span className="mr-2 rounded-full border px-2 py-0.5 text-[10px] uppercase">{e.kind}</span>
                  {e.action} <span className="ml-2 font-normal text-muted">({e.status})</span>
                </summary>
                {e.five_fields && (
                  <dl className="mt-3 space-y-2 text-sm">
                    <div><dt className="font-bold text-accent">Reality</dt><dd className="text-muted">{e.five_fields.reality}</dd></div>
                    <div><dt className="font-bold text-accent">Possibility</dt><dd className="text-muted">{e.five_fields.possibility}</dd></div>
                    <div><dt className="font-bold text-accent">Constraint ({e.five_fields.constraint_state})</dt><dd className="text-muted">{e.five_fields.constraint}</dd></div>
                    <div><dt className="font-bold text-accent">Intervention</dt><dd className="text-muted">{e.five_fields.intervention}</dd></div>
                    <div><dt className="font-bold text-accent">Outcome</dt><dd className="text-muted">{e.five_fields.outcome}</dd></div>
                  </dl>
                )}
              </details>
            ))}
          </div>
        )}
      </section>

      {/* Do-not-contact */}
      <section aria-label="Do not contact">
        <h3 className="text-lg font-extrabold">Do-not-contact list</h3>
        {dnc.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Empty. Nobody is on the do-not-contact list.</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {dnc.map((r) => (
              <li key={r.entity_id} className="text-muted">
                Entity #{r.entity_id} — {r.reason}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Legal check */}
      <section aria-label="Legal check" className="rounded-card border-2 border-warning/70 bg-warning/10 p-4">
        <h3 className="text-lg font-extrabold">Legal check — required before any outreach</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6">
          <li>Nepal rules on unsolicited messages (spam / cold outreach) — <strong>not yet read by a lawyer</strong>.</li>
          <li>Nepal rules on registering online businesses (E-commerce Act reporting) — <strong>not yet read by a lawyer</strong>.</li>
        </ul>
        <p className="mt-2 text-sm text-muted">
          Do not send any outreach until a lawyer has reviewed both items. This is a hard gate, not a suggestion.
        </p>
      </section>
    </div>
  );
}
