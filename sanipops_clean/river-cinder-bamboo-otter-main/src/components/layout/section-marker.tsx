export function SectionMarker({
  label,
  index,
}: {
  label: string;
  index: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-t border-line pt-3 font-mono text-kicker uppercase tracking-[0.14em] text-cyan lg:max-w-36">
      <span>{label}</span>
      <span>{index}</span>
    </div>
  );
}
