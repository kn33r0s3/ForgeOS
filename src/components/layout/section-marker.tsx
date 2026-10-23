export function SectionMarker({
  label,
  index,
}: {
  label: string;
  index: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-t-2 border-accent pt-3 lg:max-w-36">
      <span className="text-kicker font-extrabold uppercase tracking-[0.14em] text-wheat">{label}</span>
      <span className="gothic-num text-2xl">{index}</span>
    </div>
  );
}
