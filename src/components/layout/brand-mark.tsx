import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <Link
      to="/"
      className={cn("group flex items-center gap-2.5", className)}
      aria-label="Hami home"
    >
      <span
        className="grid size-8 place-items-center rounded-sm border border-line bg-raised font-display text-sm font-semibold tracking-tight text-fg transition-colors duration-150 group-hover:border-cyan/50 group-hover:text-cyan"
        aria-hidden="true"
      >
        H
      </span>
      <span className="font-display text-base font-semibold tracking-tight text-fg">
        Hami
      </span>
    </Link>
  );
}
