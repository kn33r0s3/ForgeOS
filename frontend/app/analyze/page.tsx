"use client";

import { useState } from "react";
import { api, AnalyzeResponse } from "@/lib/api";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-forge-border bg-forge-panel p-5">
      <h3 className="text-sm font-medium text-forge-accent2 mb-2">{title}</h3>
      <div className="text-sm text-neutral-300 whitespace-pre-line leading-relaxed">
        {children}
      </div>
    </div>
  );
}

export default function AnalyzePage() {
  const [idea, setIdea] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    if (!idea.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.analyze(idea.trim());
      setResult(res);
    } catch {
      setError("Could not reach the Forge backend. Check the configured API URL and backend availability.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Analyze</h1>
        <p className="text-neutral-400 text-sm mt-1">
          Describe a business idea or a problem you've noticed. Forge will break it down.
        </p>
      </div>

      <form onSubmit={handleAnalyze} className="space-y-3">
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={4}
          placeholder="Describe a business idea or a problem you've observed…"
          className="w-full rounded-md bg-forge-panel border border-forge-border px-4 py-3 text-sm outline-none focus:border-forge-accent resize-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-forge-accent text-forge-bg font-medium px-5 py-2.5 text-sm disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Analyze with Forge"}
        </button>
      </form>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 text-red-300 text-sm px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-forge-accent/40 bg-forge-accent/10 px-5 py-4">
            <div>
              <p className="text-xs text-neutral-400">Opportunity score</p>
              <p className="text-3xl font-semibold text-forge-accent">
                {result.score.toFixed(0)}
                <span className="text-base text-neutral-500">/100</span>
              </p>
            </div>
            <div className="text-right text-xs text-neutral-400">
              <p>difficulty: {result.difficulty}</p>
              <p>opportunity #{result.opportunity_id}</p>
            </div>
          </div>

          <Section title="Problem">{result.problem}</Section>
          <Section title="Target customer">{result.target_customer}</Section>
          <Section title="Market analysis">{result.market_analysis}</Section>
          <Section title="Solution">{result.solution}</Section>
          <Section title="Business model">{result.business_model}</Section>
          <Section title="Pricing idea">{result.pricing_idea}</Section>
          <Section title="MVP plan">{result.mvp_plan}</Section>
          <Section title="Validation plan">{result.validation_plan}</Section>
        </div>
      )}
    </div>
  );
}
