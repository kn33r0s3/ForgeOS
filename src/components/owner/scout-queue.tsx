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

interface PendingReply {
  id: number;
  candidate_entity_id: number;
  observed_fact: string;
  message_en: string;
  message_ne: string;
  status: string;
  sent_at: string | null;
  send_channel: string | null;
  reply_received: boolean;
  outcome_notes: string | null;
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
  const [pendingReplies, setPendingReplies] = useState<PendingReply[]>([]);
  const [replySummaries, setReplySummaries] = useState<Record<number, string>>({});
  const [dryWellSummaries, setDryWellSummaries] = useState<Record<number, string>>({});
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
      const [d, p, e, c, n] = await Promise.all([
        scoutFetch<Draft[]>("drafts", apiKey),
        scoutFetch<PendingReply[]>("pending-replies", apiKey),
        scoutFetch<RegistryExperiment[]>("experiments", apiKey),
        scoutFetch<{ daily_cap: number; sent_today: number }>("config", apiKey),
        scoutFetch<{ entity_id: number; reason: string }[]>("do-not-contact", apiKey),
      ]);
      setDrafts(d);
      setPendingReplies(p);
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

      {/* Sent contacts: record a real reply or an honest dry well. */}
      <section aria-label="Sent contacts awaiting response">
        <h3 className="text-lg font-extrabold">Sent contacts — outcomes</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
          These messages were marked sent by the owner; recipient receipt is not independently verified.
          Record a reply only if one actually arrived. A no-response note is a dry well, not evidence of demand,
          and it never unlocks another message to the same person. Both records remain owner-reported.
        </p>
        {pendingReplies.length === 0 ? (
          <p className="mt-3 rounded-card border border-line bg-card p-4 text-sm text-muted">
            No sent contacts need an outcome update.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {pendingReplies.map((d) => {
              const replySummary = replySummaries[d.id] ?? "";
              const dryWellSummary = dryWellSummaries[d.id] ?? "";
              return (
                <article key={d.id} className="rounded-card border-2 border-line bg-card p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-muted">
                    Draft #{d.id} · owner-marked SENT · {d.send_channel || "channel unknown"}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    Sent: {d.sent_at ? new Date(d.sent_at).toLocaleString() : "time unknown"} · Entity #{d.candidate_entity_id}
                  </p>
                  <p className="mt-2 text-sm font-semibold">{d.observed_fact}</p>
                  <p className="mt-2 text-sm leading-6">{d.message_en}</p>

                  {d.outcome_notes ? (
                    <p className="mt-3 rounded-card border border-warning/60 bg-warning/10 p-3 text-sm">
                      <span className="font-bold">Dry well already recorded (owner report): </span>
                      {d.outcome_notes}
                      <span className="mt-1 block text-xs text-muted">
                        This note does not prevent recording a later actual reply.
                      </span>
                    </p>
                  ) : (
                    <div className="mt-3">
                      <label className="block text-sm">
                        <span className="font-bold">No response observed — dry-well note</span>
                        <textarea
                          className="mt-1 w-full rounded-card border border-line bg-background p-2 text-sm"
                          rows={2}
                          value={dryWellSummary}
                          placeholder="What did you check, and as of what date/time?"
                          onChange={(event) =>
                            setDryWellSummaries((current) => ({ ...current, [d.id]: event.target.value }))
                          }
                        />
                      </label>
                      <Button
                        className="mt-2"
                        size="sm"
                        variant="secondary"
                        disabled={!dryWellSummary.trim()}
                        onClick={() =>
                          act(
                            () => scoutFetch(`drafts/${d.id}/no-response`, apiKey, {
                              method: "POST",
                              body: JSON.stringify({ summary: dryWellSummary }),
                            }),
                            "No response recorded as an owner-reported dry well. Further contact remains blocked.",
                          )
                        }
                      >
                        Record no response (dry well)
                      </Button>
                    </div>
                  )}

                  <div className="mt-4 border-t border-line pt-3">
                    <label className="block text-sm">
                      <span className="font-bold">Recipient's actual reply</span>
                      <textarea
                        className="mt-1 w-full rounded-card border border-line bg-background p-2 text-sm"
                        rows={3}
                        value={replySummary}
                        placeholder="Only enter what the recipient actually said. Do not infer interest, acceptance, fulfillment, or payment."
                        onChange={(event) =>
                          setReplySummaries((current) => ({ ...current, [d.id]: event.target.value }))
                        }
                      />
                    </label>
                    <Button
                      className="mt-2"
                      size="sm"
                      disabled={!replySummary.trim()}
                      onClick={() =>
                        act(
                          () => scoutFetch(`drafts/${d.id}/reply`, apiKey, {
                            method: "POST",
                            body: JSON.stringify({ summary: replySummary }),
                          }),
                          "Recipient response recorded as owner-reported; not independently verified.",
                        )
                      }
                    >
                      Record reply received
                    </Button>
                  </div>
                </article>
              );
            })}
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
