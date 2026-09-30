import { EarningPathway } from "@/lib/earn/pathways";

type Props = {
  pathways: EarningPathway[];
  selected: string;
  onSelect: (id: string) => void;
};

export function PathwayPicker({ pathways, selected, onSelect }: Props) {
  return (
    <section className="space-y-3">
      <div>
        <p className="section-label">CHOOSE A PATH</p>
        <p className="text-sm text-neutral-500">Start with one small experiment, not a promise of income.</p>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {pathways.map((path) => (
          <button
            key={path.id}
            onClick={() => onSelect(path.id)}
            className={`text-left glass-panel p-4 transition card-interactive ${
              selected === path.id ? "border-forge-accent2/60 bg-forge-accent/10" : "hover:border-white/15"
            }`}
          >
            <p className="font-semibold text-neutral-100">{path.title}</p>
            <p className="text-xs text-forge-accent2 mt-1">{path.nepali}</p>
            <p className="text-xs text-neutral-400 mt-3 leading-relaxed">{path.examples}</p>
          </button>
        ))}
      </div>
    </section>
  );
}
