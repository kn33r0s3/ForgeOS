import { useState } from "react";
import { Bot, CheckCircle2, FlaskConical, Search, ShieldCheck, XCircle } from "lucide-react";
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

export function ForgeConsoleWidgets() {
  return (
    <div>
      <div className="mb-5 flex items-start gap-3 rounded-card border-2 border-line bg-card p-4">
        <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
        <p className="text-sm leading-6 text-muted">
          <strong className="text-ink">ForgeBot v0 — the assistant.</strong>{" "}
          The operator's working console: gate findings, check angles, see
          what's ripest. Everything here runs the real engine code — the
          same gate, unknowns, and guard the rounds use.
        </p>
      </div>
      <div className="grid gap-5">
        <GateTester />
        <AngleChecker />
        <RipenessList />
      </div>
    </div>
  );
}
