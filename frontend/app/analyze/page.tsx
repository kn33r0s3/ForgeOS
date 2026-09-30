"use client";

import { useEffect, useState } from "react";
import { api, AnalyzeProgressResponse, AnalyzeResponse } from "@/lib/api";

const MAX_PROGRESS_POLLS = 20;
const PROGRESS_POLL_INTERVAL_MS = 1_500;
const PROGRESS_POLL_TIMEOUT_MS = 45_000;

function progressLabel(progress?: AnalyzeProgressResponse | null, result?: AnalyzeResponse | null) {
  const phase = progress?.phase;
  if (phase === "queued") return "Queued";
  if (phase === "researching") return "Running";
  if (phase === "completed") return "Research complete";
  if (phase === "evidence_found") return "Evidence found";
  if (phase === "awaiting_evidence") return "Awaiting evidence";
  if (phase === "not_started") return "Not started";
  if (phase) return phase.replaceAll("_", " ");
  const researchStatus = progress?.research_status || result?.research_status;
  if (researchStatus === "research_complete") return "Research complete";
  if (
    phase === "blocked" ||
    researchStatus === "research_terminal_unresolved" ||
    researchStatus === "research_failed"
  ) return "Blocked";
  if (researchStatus === "research_started") return "Queued";
  if (researchStatus === "research_in_progress") return "Running";
  if (researchStatus === "research_needs_evidence") return "Awaiting evidence";
  const status = researchStatus;
  return status ? status.replaceAll("_", " ") : "Status unavailable";
}

function isProgressActive(progress: AnalyzeProgressResponse) {
  return progress.phase === "queued" || progress.phase === "researching";
}

const samplePrompts = [
  "I run a small repair shop and want to know whether customers are actively looking for mobile repair services.",
  "Our customer support team is losing time on repetitive scheduling issues. Is there evidence this is a real pain point?",
  "Local service businesses are struggling to get booked appointments. What is the strongest real problem to solve first?",
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <h3 className="mb-2 text-sm font-medium uppercase tracking-[0.12em] text-forge-accent2">{title}</h3>
      <div className="whitespace-pre-line text-sm leading-7 text-neutral-200">{children}</div>
    </div>
  );
}

export default function AnalyzePage() {
  const [idea, setIdea] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [progress, setProgress] = useState<AnalyzeProgressResponse | null>(null);
  const [progressNotice, setProgressNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("Researching");

  useEffect(() => {
    const saved = window.localStorage.getItem("forgeos-public-result");
    if (saved) {
      try {
        setResult(JSON.parse(saved) as AnalyzeResponse);
      } catch {
        window.localStorage.removeItem("forgeos-public-result");
      }
    }
  }, []);

  useEffect(() => {
    if (!result) return;
    window.localStorage.setItem("forgeos-public-result", JSON.stringify(result));
  }, [result]);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = idea.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setProgress(null);
    setProgressNotice(null);
    setStatusText("Researching");

    try {
      const res = await api.analyze(trimmed);
      setResult(res);
      setIdea("");

      if (
        res.research_status_url &&
        (res.research_status === "research_started" || res.research_status === "research_in_progress")
      ) {
        const controller = new AbortController();
        const timeoutId = window.setTimeout(
          () => controller.abort(),
          PROGRESS_POLL_TIMEOUT_MS,
        );
        let latestProgress: AnalyzeProgressResponse | null = null;
        let failedPolls = 0;

        try {
          for (let attempt = 0; attempt < MAX_PROGRESS_POLLS; attempt += 1) {
            if (controller.signal.aborted) break;
            try {
              const currentProgress = await api.getAnalyzeProgress(res.research_status_url, controller.signal);
              latestProgress = currentProgress;
              failedPolls = 0;
              setProgress(currentProgress);
              setStatusText(progressLabel(currentProgress));
              setResult((current) => current ? {
                ...current,
                research_status: currentProgress.research_status,
                evidence_count: currentProgress.evidence_count,
                research_task_ids: currentProgress.tasks.map((task) => task.id),
              } : current);
              if (!isProgressActive(currentProgress)) break;
            } catch {
              failedPolls += 1;
              if (failedPolls >= 3) {
                setProgressNotice("The persisted progress endpoint could not be reached; the last known status is shown.");
                break;
              }
            }

            if (attempt < MAX_PROGRESS_POLLS - 1 && !controller.signal.aborted) {
              await new Promise((resolve) => window.setTimeout(resolve, PROGRESS_POLL_INTERVAL_MS));
            }
          }
        } finally {
          window.clearTimeout(timeoutId);
        }

        if (controller.signal.aborted) {
          setProgressNotice("Progress checks timed out; the last persisted status is shown.");
        } else if (latestProgress && isProgressActive(latestProgress)) {
          setProgressNotice("Research is still running; automatic status checks have paused.");
        }
        setStatusText(progressLabel(latestProgress, res));
      } else {
        setStatusText(progressLabel(null, res));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not reach the Forge backend.";
      setError(message || "Could not reach the Forge backend.");
      setStatusText("Blocked");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 py-10">
      <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 md:p-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-forge-accent2">Hami</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-white md:text-5xl">What problem are you trying to solve?</h1>
          </div>
          <a href="/" className="rounded-full border border-white/10 px-4 py-2 text-sm text-neutral-200 hover:border-white/25 hover:bg-white/[0.03]">
            Public entry</a>
        </div>

        <form onSubmit={handleAnalyze} className="mt-8 space-y-4">
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            rows={5}
            placeholder="I run a small repair shop and want to know whether customers are actively looking for mobile repair services."
            className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-4 text-base text-white outline-none transition focus:border-forge-accent focus:ring-2 focus:ring-forge-accent/30"
          />

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={loading}
              className="rounded-full bg-forge-accent px-6 py-3 text-sm font-medium text-black transition hover:bg-forge-accent2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? statusText + "…" : "Research this problem"}
            </button>
            <span className="text-sm text-neutral-400">Hami checks authorized sources. Research leads are not proof of customer demand.</span>
          </div>
        </form>

        <div className="mt-5 flex flex-wrap gap-2">
          {samplePrompts.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => setIdea(sample)}
              className="rounded-full border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-neutral-300 transition hover:border-white/25 hover:text-white"
            >
              Try an example
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}
      {progressNotice && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          {progressNotice}
        </div>
      )}

      {result && (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-forge-accent/30 bg-forge-accent/10 p-6 md:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-forge-accent2">Current result</p>
                <p className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">{result.problem}</p>
              </div>
              <div className="rounded-full border border-white/10 bg-black/20 px-4 py-2 text-right text-sm text-neutral-200">
                <div>{result.opportunity_id ? `Score: ${result.score.toFixed(0)}/100` : progressLabel(progress, result)}</div>
                <div className="text-xs text-neutral-400">
                  {result.opportunity_id ? result.evidence_quality || "Limited evidence" : progress?.phase || result.research_status || "Status unavailable"}
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="What we found">
              {result.target_customer}
              {"\n\n"}
              {result.solution}
              {"\n\n"}
              {result.market_analysis || "No market analysis was produced yet. The system is still validating whether the problem is real and worth solving."}
            </Section>
            <Section title="Research status">
              {progress
                ? `Latest persisted state: ${progress.research_status}`
                : result.findings_summary || "No findings summary was returned."}
              {"\n\n"}
              {progressLabel(progress, result)}
              {"\n\n"}
              {result.research_question_id ? `Research question: #${result.research_question_id}` : "No research question persisted yet."}
              {result.research_task_ids && result.research_task_ids.length > 0 ? `\nResearch tasks: ${result.research_task_ids.join(", ")}` : "\nNo tasks have completed yet."}
              {typeof (progress?.evidence_count ?? result.evidence_count) === "number" ? `\nEvidence collected: ${progress?.evidence_count ?? result.evidence_count}` : ""}
            </Section>
          </div>

          {result.research_plan && (
            <div className="grid gap-5 lg:grid-cols-2">
              <Section title="Research plan">
                {result.research_plan.status}
                {result.research_plan.budget
                  ? ` · ${result.research_plan.budget.tasks_created}/${result.research_plan.budget.max_tasks} tasks`
                  : ""}
                {"\n\n"}
                Requirements:
                {"\n"}
                {result.research_plan.requirements
                  .map((requirement) => {
                    const reason = requirement.terminal_reason
                      ? ` — ${requirement.terminal_reason}`
                      : "";
                    return `• ${requirement.question}\n  ${requirement.status}${reason}`;
                  })
                  .join("\n")}
                {"\n\n"}
                Candidate sources:
                {"\n"}
                {result.research_plan.candidate_sources
                  .map((source) => `• ${source.source}: ${source.available ? "available" : source.reason || "not cleared"}`)
                  .join("\n")}
                {"\n\n"}
                {result.research_plan.assumptions.map((item) => `Assumption: ${item}`).join("\n")}
              </Section>
              <Section title="Attributed source records">
                {result.research_sources && result.research_sources.length > 0 ? (
                  <div className="space-y-4">
                    {result.research_sources.map((source) => (
                      <article key={source.evidence_id} className="border-b border-white/10 pb-3 last:border-0">
                        {source.url ? (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="font-medium text-white underline decoration-forge-accent/60 underline-offset-4"
                          >
                            {source.title || source.external_id || `Evidence #${source.evidence_id}`}
                          </a>
                        ) : (
                          <p className="font-medium text-white">{source.title || `Evidence #${source.evidence_id}`}</p>
                        )}
                        <p className="mt-1 break-all text-xs text-neutral-400">
                          {source.source}
                          {source.published_at ? ` · published ${source.published_at}` : ""}
                          {source.retrieved_at ? ` · retrieved ${source.retrieved_at}` : ""}
                        </p>
                        <p className="mt-1 text-xs text-neutral-400">
                          Evidence #{source.evidence_id}
                          {source.assessment
                            ? ` · keyword overlap ${source.assessment.keyword_overlap.matched_terms.length}/${source.assessment.keyword_overlap.query_term_count}; source reliability ${source.assessment.source_reliability}; semantic relevance ${source.assessment.semantic_relevance}; contradictions ${source.assessment.contradictions}; claim support ${source.assessment.claim_support}`
                            : ""}
                        </p>
                        {source.assessment && (
                          <p className="mt-1 text-xs text-neutral-500">
                            {source.assessment.keyword_overlap.method}
                            {source.assessment.publication_age_days !== null
                              ? ` · publication age ${source.assessment.publication_age_days} days`
                              : ""}
                          </p>
                        )}
                      </article>
                    ))}
                  </div>
                ) : (
                  "No external source records have been persisted for this question yet."
                )}
              </Section>
            </div>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="Uncertainty">
              {result.unknowns && result.unknowns.length > 0
                ? result.unknowns.map((item) => `• ${item}`).join("\n")
                : "The evidence is still too limited to confirm key assumptions such as willingness to pay, acquisition path, and competitive pressure."}
            </Section>
            <Section title="Next actions">
              {result.recommended_next_experiment || "Interview a small representative sample in the target audience and validate whether they confirm the problem and would pay for a fix."}
              {result.decision_id ? `\n\nDecision record: #${result.decision_id}` : ""}
            </Section>
          </div>

          <Section title="Evidence status">
            Observation status: {result.observation_status || "observed"}
            {"\n"}
            Evidence quality: {result.evidence_quality || "limited"}
            {"\n"}
            {result.opportunity_id ? `Opportunity saved: #${result.opportunity_id}` : "Opportunity not yet justified by evidence"}
            {result.signal_id ? `\nSignal captured: #${result.signal_id}` : ""}
          </Section>
        </div>
      )}
    </div>
  );
}
