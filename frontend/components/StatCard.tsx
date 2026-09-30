export default function StatCard({
  label,
  value,
  accent = false,
  subtitle,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
  subtitle?: string;
}) {
  return (
    <div className="rounded-xl border border-forge-border bg-forge-panel/80 p-5 card-interactive">
      <p className="section-label mb-2">{label}</p>
      <p
        className={`text-3xl font-semibold tracking-tight tabular ${
          accent ? "text-forge-accent" : "text-neutral-50"
        }`}
      >
        {value}
      </p>
      {subtitle && (
        <p className="text-xs text-forge-muted mt-1.5">{subtitle}</p>
      )}
    </div>
  );
}
