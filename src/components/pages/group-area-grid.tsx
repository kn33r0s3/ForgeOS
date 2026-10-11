import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { groupAreas } from "@/lib/content";

/** Strategic directions always lead into an existing Hami pathway, never a parallel business page. */
export function GroupAreaGrid() {
  return (
    <div className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
      {groupAreas.map((area) => (
        <Link
          key={area.name}
          to={area.href}
          className="bg-surface p-5 transition-colors duration-150 hover:bg-cyan-dim"
        >
          <strong className="font-display text-base font-semibold tracking-tight text-fg">
            {area.name}
          </strong>
          <p className="mt-2 text-xs leading-relaxed text-muted">{area.description}</p>
          <span className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-cyan">
            {area.hrefLabel}
            <ArrowUpRight className="size-3.5" aria-hidden="true" />
          </span>
        </Link>
      ))}
    </div>
  );
}
