function color(score: number) {
  if (score >= 70) return "text-forge-accent border-forge-accent/40 bg-forge-accent/10";
  if (score >= 45) return "text-forge-accent2 border-forge-accent2/40 bg-forge-accent2/10";
  return "text-neutral-400 border-neutral-500/40 bg-neutral-500/10";
}

export default function ImportanceBadge({ score }: { score: number }) {
  return (
    <span
      className={`shrink-0 text-xs font-medium rounded-full border px-2 py-0.5 ${color(score)}`}
    >
      {Math.round(score)}
    </span>
  );
}
