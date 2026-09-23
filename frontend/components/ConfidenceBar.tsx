/**
 * A labeled 0-100 meter — used for confidence, money_score, stability,
 * evidence strength, anywhere a real backend-computed number needs a
 * visual bar. Never animates toward a fabricated target; the fill
 * width is always the actual current value.
 */
export default function ConfidenceBar({
  label,
  value,
  suffix = "%",
  colorClass = "bg-forge-accent",
}: {
  label: string;
  value: number;
  suffix?: string;
  colorClass?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-neutral-400 tracking-wide uppercase">{label}</span>
        <span className="tabular text-neutral-200 font-medium">
          {Math.round(value)}
          {suffix}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-forge-border overflow-hidden">
        <div
          className={`h-full rounded-full ${colorClass} transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
