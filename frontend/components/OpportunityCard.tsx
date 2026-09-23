import { Opportunity } from "@/lib/api";

function scoreColor(score: number) {
  if (score >= 70) return "text-forge-revenue border-forge-revenue/35 bg-forge-revenue/10";
  if (score >= 45) return "text-forge-accent2 border-forge-accent2/35 bg-forge-accent2/10";
  return "text-neutral-400 border-neutral-500/35 bg-neutral-500/10";
}

export default function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
  return (
    <div className="rounded-2xl border border-forge-border bg-forge-panel/90 p-5 space-y-3.5 card-interactive premium-edge">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-neutral-50 leading-snug tracking-tight">
          {opportunity.problem}
        </h3>
        <span
          className={`shrink-0 text-sm font-bold rounded-full border px-2.5 py-1 tabular ${scoreColor(
            opportunity.score
          )}`}
        >
          {opportunity.score.toFixed(0)}
        </span>
      </div>

      <div className="text-sm text-neutral-400">
        <span className="text-neutral-500 font-medium">Target · </span>
        {opportunity.target_customer}
      </div>

      <div className="text-sm text-neutral-300 leading-relaxed">
        <span className="text-neutral-500 font-medium">Solution · </span>
        {opportunity.solution}
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        {opportunity.difficulty && (
          <span className="rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-0.5 text-[11px] text-neutral-400 font-medium">
            difficulty: {opportunity.difficulty}
          </span>
        )}
        {opportunity.pricing_idea && (
          <span className="rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-0.5 text-[11px] text-neutral-400 font-medium">
            {opportunity.pricing_idea.length > 40
              ? opportunity.pricing_idea.slice(0, 40) + "…"
              : opportunity.pricing_idea}
          </span>
        )}
      </div>
    </div>
  );
}
