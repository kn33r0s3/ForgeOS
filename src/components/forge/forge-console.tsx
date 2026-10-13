import { useEffect, useState, type FormEvent } from "react";
import { Bot, CheckCircle2, Search, ShieldCheck, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  isAngleTried,
  ripenessQueue,
  verifyRound,
  type RoundFinding,
} from "@/lib/forge/assistant";
import { tierLabel } from "@/lib/forge/value";
import type { Confidence, EvidenceClass } from "@/lib/evidence";

const CLASSES: EvidenceClass[] = ["actual", "observed", "reported", "inferred", "estimated", "unknown"];
const CONFIDENCES: Confidence[] = ["high", "medium", "low"];

const inputCls =
  "w-full rounded-lg border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/60";


type ForgeProviderStatus = {
  provider: string;
  status: string;
};

type ForgeProviderObservation = {
  provider: string;
  mode: string;
  model: string | null;
  status: string;
  inference_invoked: boolean;
  prompt_eval_tokens: number | null;
  completion_eval_tokens: number | null;
  total_duration_ms: number | null;
};

type ForgeKnowledgeRecord = {
  id: number;
  title: string;
  content: string;
  category: string | null;
  source_type: string;
  source_id: number;
  confidence_score: number;
  created_at: string;
  updated_at: string;
};

type ForgeAskResponse = {
  question: string;
  answer: string;
  memories_used: ForgeKnowledgeRecord[];
  provider_observation?: ForgeProviderObservation | null;
};

type ForgeChatTurn = {
  id: string;
  question: string;
  answer: string;
  records: ForgeKnowledgeRecord[];
  providerObservation: ForgeProviderObservation | null;
  askedAt: string;
};

function ForgeKnowledgeChat({ apiKey }: { apiKey: string }) {
  const [providerStatus, setProviderStatus] = useState<ForgeProviderStatus | null>(null);
  const [providerLoading, setProviderLoading] = useState(true);
  const [providerError, setProviderError] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");
  const [successfulQueries, setSuccessfulQueries] = useState(0);
  const [turns, setTurns] = useState<ForgeChatTurn[]>([]);

  useEffect(() => {
    let active = true;
    setProviderLoading(true);
    setProviderError("");
    setProviderStatus(null);
    fetch("/api/ai/status", { headers: { "X-API-Key": apiKey } })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(response.status === 401
            ? "Owner authentication failed. Re-open the console with the correct key."
            : "Provider configuration could not be read (HTTP " + response.status + ").");
        }
        const payload: unknown = await response.json();
        if (typeof payload !== "object" || payload === null ||
            !("provider" in payload) || !("status" in payload) ||
            typeof payload.provider !== "string" || typeof payload.status !== "string") {
          throw new Error("Provider status returned an unexpected response.");
        }
        if (active) setProviderStatus({ provider: payload.provider, status: payload.status });
      })
      .catch((cause) => {
        if (active) {
          setProviderStatus(null);
          setProviderError(cause instanceof Error ? cause.message : "Provider status is unavailable.");
        }
      })
      .finally(() => {
        if (active) setProviderLoading(false);
      });
    return () => { active = false; };
  }, [apiKey]);

  const providerName = providerStatus?.provider.trim().toLowerCase() ?? "";
  const providerHealth = providerStatus?.status.trim().toUpperCase() ?? "";
  const approvedZeroCostProvider = providerName === "mock" || providerName === "ollama";
  const paidProvider = providerName === "openai";
  const mockProvider = providerName === "mock" &&
    (providerHealth === "READY" || providerHealth === "MOCK");
  const providerCanAnswer = providerStatus !== null &&
    providerName === "ollama" && providerHealth === "MODEL_AVAILABLE";
  const canAsk = !providerLoading && !providerError && providerCanAnswer;

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedQuestion = question.trim();
    if (!submittedQuestion || submittedQuestion.length > 1000 || asking || !canAsk) return;
    setAsking(true);
    setAskError("");
    try {
      const response = await fetch("/api/forge/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
        body: JSON.stringify({ question: submittedQuestion }),
      });
      if (!response.ok) {
        const payload: unknown = await response.json().catch(() => null);
        const detail = typeof payload === "object" && payload !== null &&
          "detail" in payload && typeof payload.detail === "string"
          ? payload.detail.slice(0, 220)
          : "Forge could not answer this request (HTTP " + response.status + ").";
        throw new Error(detail);
      }
      const payload: unknown = await response.json();
      if (typeof payload !== "object" || payload === null ||
          !("answer" in payload) || typeof payload.answer !== "string" ||
          !("memories_used" in payload) || !Array.isArray(payload.memories_used)) {
        throw new Error("Forge returned an unexpected answer format; nothing was saved by this panel.");
      }
      const data = payload as ForgeAskResponse;
      const rawObservation = data.provider_observation;
      const providerObservation: ForgeProviderObservation | null =
        typeof rawObservation === "object" && rawObservation !== null &&
        typeof rawObservation.provider === "string" &&
        typeof rawObservation.mode === "string" &&
        typeof rawObservation.status === "string" &&
        typeof rawObservation.inference_invoked === "boolean"
          ? {
              provider: rawObservation.provider.slice(0, 80),
              mode: rawObservation.mode.slice(0, 40),
              model: typeof rawObservation.model === "string" ? rawObservation.model.slice(0, 120) : null,
              status: rawObservation.status.slice(0, 40),
              inference_invoked: rawObservation.inference_invoked,
              prompt_eval_tokens: Number.isInteger(rawObservation.prompt_eval_tokens) && (rawObservation.prompt_eval_tokens ?? -1) >= 0 ? rawObservation.prompt_eval_tokens : null,
              completion_eval_tokens: Number.isInteger(rawObservation.completion_eval_tokens) && (rawObservation.completion_eval_tokens ?? -1) >= 0 ? rawObservation.completion_eval_tokens : null,
              total_duration_ms: typeof rawObservation.total_duration_ms === "number" && Number.isFinite(rawObservation.total_duration_ms) && rawObservation.total_duration_ms >= 0 ? rawObservation.total_duration_ms : null,
            }
          : null;
      const records = data.memories_used.filter((record) =>
        record !== null && typeof record === "object" &&
        Number.isInteger(record.id) && typeof record.title === "string" &&
        typeof record.content === "string" && typeof record.source_type === "string" &&
        Number.isInteger(record.source_id));
      const turn: ForgeChatTurn = {
        id: Date.now().toString() + "-" + (successfulQueries + 1).toString(),
        question: submittedQuestion,
        answer: data.answer,
        records,
        providerObservation,
        askedAt: new Date().toISOString(),
      };
      setTurns((current) => [...current, turn].slice(-8));
      setSuccessfulQueries((count) => count + 1);
      setQuestion("");
    } catch (cause) {
      setAskError(cause instanceof Error ? cause.message : "Forge could not answer this request.");
    } finally {
      setAsking(false);
    }
  }

  const suggestions = [
    "हामीलाई अहिले के थाहा छ?",
    "Hami le ke kura ajhai janchna baaki chha?",
    "What important thing is still unknown?",
    "What evidence would make an important claim trustworthy?",
  ];

  return (
    <section aria-label="Talk to ForgeBot" className="rounded-2xl border border-line bg-card p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-display text-lg text-ink">
            <Bot className="h-5 w-5 text-accent" aria-hidden="true" />
            Talk to ForgeBot
          </h3>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Ask in Nepali (देवनागरी), Romanized Nepali, English, or a mix. ForgeBot should answer in your language and show the Hami knowledge records used.
            When the stored evidence is insufficient, it should say so instead of guessing. You can start with an example below or ask your own question.
          </p>
        </div>
        <span className="rounded-full border border-line px-3 py-1 text-xs font-semibold text-muted">Temporary chat</span>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-background p-3 sm:p-4">
        <p className="text-sm font-bold text-ink">Can ForgeBot answer right now?</p>
        {providerLoading ? (
          <p role="status" className="mt-1 text-sm text-muted">Checking whether ForgeBot is ready…</p>
        ) : providerError ? (
          <p role="alert" className="mt-1 text-sm text-warning">I couldn’t confirm ForgeBot’s status. Refresh the page and try again. {providerError}</p>
        ) : providerStatus ? (
          <>
            {paidProvider ? (
              <>
                <p className="mt-1 text-sm font-semibold text-ink">ForgeBot chat is paused to avoid charges.</p>
                <p className="mt-1 text-sm leading-5 text-muted">
                  Hami is configured for a paid cloud AI. To protect your budget, this page will not send a paid model request.
                </p>
              </>
            ) : mockProvider ? (
              <>
                <p className="mt-1 text-sm font-semibold text-ink">Real inference is not enabled.</p>
                <p className="mt-1 text-sm leading-5 text-muted">
                  This environment is using deterministic test templates. Hami will not present them as intelligence or enable questions until a real, reachable local model is available.
                </p>
              </>
            ) : providerHealth === "MODEL_AVAILABLE" && providerName === "ollama" ? (
              <>
                <p className="mt-1 text-sm font-semibold text-ink">The local model is installed and reachable.</p>
                <p className="mt-1 text-sm leading-5 text-muted">
                  This checks Ollama and the configured model, not generation quality. ForgeBot still needs to complete the request successfully and ground its answer in the knowledge shown.
                </p>
              </>
            ) : providerHealth === "READY" && !approvedZeroCostProvider ? (
              <>
                <p className="mt-1 text-sm font-semibold text-ink">ForgeBot chat is paused.</p>
                <p className="mt-1 text-sm leading-5 text-muted">
                  This provider isn't on Hami's approved zero-cost list. No model request will be sent from this page.
                </p>
              </>
            ) : (
              <>
                <p className="mt-1 text-sm font-semibold text-ink">ForgeBot is not ready yet.</p>
                <p className="mt-1 text-sm leading-5 text-muted">
                  Questions are paused rather than silently switching to another provider.
                </p>
              </>
            )}
          </>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2" aria-label="Example questions you can ask">
        {suggestions.map((suggestion) => (
          <button key={suggestion} type="button" disabled={!canAsk || asking}
            onClick={() => setQuestion(suggestion)}
            className="min-h-9 rounded-full border border-line px-3 py-1 text-left text-xs font-semibold text-ink hover:border-accent disabled:cursor-not-allowed disabled:opacity-50">
            {suggestion}
          </button>
        ))}
      </div>

      <form onSubmit={submitQuestion} className="mt-4 grid gap-3">
        <label htmlFor="forgebot-owner-question" className="text-sm font-bold text-ink">
          What would you like to know?
        </label>
        <textarea id="forgebot-owner-question" value={question}
          onChange={(event) => setQuestion(event.target.value.slice(0, 1000))}
          rows={3} maxLength={1000} required disabled={!canAsk || asking}
          placeholder="Type naturally, like you would ask a person. Please do not include private customer details or passwords."
          className={inputCls + " min-h-24 resize-y leading-6"} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted">Questions and answers stay on this page only.</p>
          <button type="submit" disabled={!canAsk || asking || !question.trim()}
            className="min-h-11 rounded-lg border-2 border-accent bg-accent px-4 font-bold text-black disabled:cursor-not-allowed disabled:opacity-50">
            {asking ? "Thinking…" : "Ask ForgeBot"}
          </button>
        </div>
      </form>

      <details className="mt-4 border-t border-line pt-3">
        <summary className="cursor-pointer text-sm font-semibold text-muted">Privacy and how answers work</summary>
        <p className="mt-2 text-sm leading-5 text-muted">
          Please do not paste phone numbers, private conversations, payment details or passwords. Your question is sent to Hami's owner API
          to produce an answer. This panel does not add the chat to Hami's knowledge records. The visible conversation stays in this page session
          and disappears when you lock or leave. ForgeBot's answer is a guide, not proof; it does not change Hami's records, send messages or perform actions.
        </p>
      </details>

      {askError ? <p role="alert" className="mt-4 rounded-lg border border-warning/60 bg-warning/10 p-3 text-sm text-ink">{askError}</p> : null}

      {turns.length ? (
        <div className="mt-5 grid gap-4" aria-label="ForgeBot query results" aria-live="polite">
          {[...turns].reverse().map((turn) => (
            <article key={turn.id} className="min-w-0 rounded-lg border border-line bg-background p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">You asked · {new Date(turn.askedAt).toLocaleTimeString()}</p>
              <p className="mt-1 break-words font-semibold text-ink">{turn.question}</p>
              <div className="mt-3 border-l-2 border-accent pl-3">
                <p className="text-xs font-bold uppercase tracking-wide text-muted">ForgeBot’s answer</p>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{turn.answer}</p>
              </div>
              {turn.providerObservation?.inference_invoked ? (
                <p className="mt-2 text-xs leading-5 text-muted">
                  Observed model call: {turn.providerObservation.mode === "SELF_HOSTED" ? "self-hosted Ollama" : "local Ollama"}
                  {turn.providerObservation.model ? " · " + turn.providerObservation.model : ""}
                  {typeof turn.providerObservation.total_duration_ms === "number" ? " · " + Math.round(turn.providerObservation.total_duration_ms) + " ms" : ""}
                  {typeof turn.providerObservation.prompt_eval_tokens === "number" && typeof turn.providerObservation.completion_eval_tokens === "number" ? " · " + (turn.providerObservation.prompt_eval_tokens + turn.providerObservation.completion_eval_tokens) + " tokens" : ""}
                  . The response was generated, but its claims are not independently verified by this telemetry.
                </p>
              ) : null}
              <details className="mt-3 border-t border-line pt-3">
                <summary className="cursor-pointer text-sm font-semibold text-ink">
                  See the records behind this answer ({turn.records.length})
                </summary>
                {turn.records.length ? (
                  <div className="mt-3 grid gap-2">
                    {turn.records.map((record) => (
                      <div key={record.id} className="rounded-md border border-line p-3">
                        <p className="break-words text-sm font-bold">{record.title}</p>
                        <p className="mt-1 text-xs text-muted">
                          Record #{record.id} · {record.source_type} #{record.source_id}
                          {record.updated_at ? " · updated " + new Date(record.updated_at).toLocaleString() : ""}
                          {typeof record.confidence_score === "number" ? " · stored confidence " + record.confidence_score : ""}
                        </p>
                        <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-5 text-muted">
                          {record.content.length > 500 ? record.content.slice(0, 500) + "…" : record.content}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-warning">
                    No related knowledge records were returned. Treat claims as UNKNOWN unless separately supported.
                  </p>
                )}
              </details>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 rounded-lg border border-dashed border-line p-4 text-sm text-muted">
          No queries in this page session. Start with one of the suggestions; Forge's response and returned records will appear here.
        </p>
      )}
    </section>
  );
}



function GateTester() {
  const [statement, setStatement] = useState("");
  const [evidenceClass, setEvidenceClass] = useState<EvidenceClass>("observed");
  const [sources, setSources] = useState("");
  const [confidence, setConfidence] = useState<Confidence>("medium");
  const [weakestLink, setWeakestLink] = useState("");
  const [unknownIds, setUnknownIds] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const run = () => {
    const finding: RoundFinding = {
      statement,
      evidenceClass,
      sources: sources.split("\n").map((s) => s.trim()).filter(Boolean),
      confidence,
      weakestLink,
      unknownIds: unknownIds.split(",").map((s) => s.trim()).filter(Boolean),
    };
    const verdict = verifyRound([finding]);
    if (verdict.verified.length === 1) {
      setResult({ ok: true, message: "Passed the gate — this finding would be banked." });
    } else {
      setResult({ ok: false, message: verdict.rejected[0]?.reason ?? "Rejected." });
    }
  };

  return (
    <section aria-label="Gate a finding" className="rounded-xl border border-line bg-surface p-5">
      <h2 className="flex items-center gap-2 font-display text-lg text-ink">
        <ShieldCheck className="h-5 w-5 text-accent" aria-hidden="true" />
        Gate a finding
      </h2>
      <p className="mt-1 text-sm text-muted">
        The same gate every round finding passes through. Try breaking it —
        leave the weakest link empty, or claim high confidence on a rumor.
      </p>
      <div className="mt-4 grid gap-3">
        <textarea value={statement} onChange={(e) => setStatement(e.target.value)} rows={2}
          placeholder="Statement — e.g. COD couriers settle cash on a T+0 to 2-day float."
          aria-label="Statement" className={inputCls} />
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-muted">Evidence class
            <select value={evidenceClass} onChange={(e) => setEvidenceClass(e.target.value as EvidenceClass)}
              className={`${inputCls} mt-1`}>
              {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="text-xs text-muted">Confidence
            <select value={confidence} onChange={(e) => setConfidence(e.target.value as Confidence)}
              className={`${inputCls} mt-1`}>
              {CONFIDENCES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        </div>
        <textarea value={sources} onChange={(e) => setSources(e.target.value)} rows={2}
          placeholder={"Sources — one per line, named:\nNepali courier press coverage\nPathao COD terms"}
          aria-label="Sources" className={inputCls} />
        <textarea value={weakestLink} onChange={(e) => setWeakestLink(e.target.value)} rows={2}
          placeholder="Weakest link — the part most likely wrong, and what would change your mind."
          aria-label="Weakest link" className={inputCls} />
        <input value={unknownIds} onChange={(e) => setUnknownIds(e.target.value)}
          placeholder="Unknown IDs it addresses — e.g. D60" aria-label="Unknown IDs" className={inputCls} />
        <div>
          <Button onClick={run}>Run the gate</Button>
        </div>
        {result && (
          <p className={`flex items-start gap-2 rounded-lg border p-3 text-sm leading-6 ${
            result.ok
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
              : "border-red-500/30 bg-red-500/10 text-red-100"
          }`}>
            {result.ok
              ? <CheckCircle2 className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />
              : <XCircle className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />}
            <span>{result.message}</span>
          </p>
        )}
      </div>
    </section>
  );
}

function AngleChecker() {
  const [angle, setAngle] = useState("");
  const [result, setResult] = useState<string | null>(null);

  const check = () => {
    if (!angle.trim()) return;
    setResult(
      isAngleTried(angle)
        ? "Tried — this ground is covered. Pick a new slice."
        : "New ground — no round has tried this angle.",
    );
  };

  return (
    <section aria-label="Check an angle" className="rounded-xl border border-line bg-surface p-5">
      <h2 className="flex items-center gap-2 font-display text-lg text-ink">
        <Search className="h-5 w-5 text-accent" aria-hidden="true" />
        Check an angle
      </h2>
      <p className="mt-1 text-sm text-muted">
        The loop never re-tills the same field. Test whether an angle was already tried.
      </p>
      <div className="mt-4 flex gap-2">
        <input value={angle} onChange={(e) => setAngle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && check()}
          placeholder="e.g. the COD courier and cash on delivery"
          aria-label="Proposed angle" className={inputCls} />
        <Button onClick={check}>Check</Button>
      </div>
      {result && <p className="mt-3 text-sm font-semibold text-ink">{result}</p>}
    </section>
  );
}

function RipenessList() {
  const [count, setCount] = useState(6);
  const queue = ripenessQueue(count);

  return (
    <section aria-label="What's ripest" className="rounded-xl border border-line bg-surface p-5">
      <h2 className="flex items-center gap-2 font-display text-lg text-ink">
        <Bot className="h-5 w-5 text-accent" aria-hidden="true" />
        What's ripest
      </h2>
      <p className="mt-1 text-sm text-muted">
        Open unknowns ranked by earned value — evidence tier first, then the
        WTP hypothesis as tiebreaker, doable now before needs-a-human. Live
        from the engine's fuel. This is a local round aid, not Hami's global
        next-experiment selector.
      </p>
      <div className="mt-4 grid gap-3">
        {queue.map((item) => (
          <div key={item.id} className="rounded-lg border border-line bg-background/60 p-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-accent">{item.id}</span>
              <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                item.valueTier === 3
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : item.valueTier === 2
                    ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
                    : "border-line bg-background text-muted"
              }`} title={item.valueTier === "unscored" ? "No give-up evidence recorded — tier unearned, not low" : item.valueWhy}>
                {tierLabel(item.valueTier)}
              </span>
              <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${
                item.ripeness === "now"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-200"
              }`}>
                {item.ripeness === "now" ? "doable now" : "needs a human"}
              </span>
              <span className="ml-auto text-xs text-muted">
                {item.round === null ? "round unassigned" : `round ${item.round}`}
              </span>
            </div>
            <p className="mt-1 text-sm leading-6 text-muted">{item.question}</p>
            <p className="mt-1 text-xs italic text-muted/80">
              hypothesis (not a tier): {item.valueWhy}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-4">
        <Button variant="secondary" onClick={() => setCount((c) => c + 6)}>Show more</Button>
      </div>
    </section>
  );
}

export function ForgeConsoleWidgets({ apiKey }: { apiKey: string }) {
  return (
    <div>
      <div className="mt-5">
        <ForgeKnowledgeChat apiKey={apiKey} />
      </div>
      <details className="mt-5 rounded-xl border border-line bg-card p-4">
        <summary className="cursor-pointer text-sm font-bold text-ink">Advanced tools (optional)</summary>
        <p className="mt-2 text-sm leading-5 text-muted">
          These tools help inspect evidence checks and research prioritisation. Most days, you can leave them closed and just talk with ForgeBot.
        </p>
        <div className="mt-4 grid gap-5">
          <GateTester />
          <AngleChecker />
          <RipenessList />
        </div>
      </details>
    </div>
  );
}
