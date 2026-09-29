import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <Link
      to="/"
      className={cn("group flex items-center gap-2.5", className)}
      aria-label="Hami home"
    >
      <img
        src="/hami-mark.png"
        alt=""
        width={32}
        height={32}
        className="size-8 rounded-card border border-line bg-card object-cover transition-colors duration-150 group-hover:border-accent/60"
      />
      <span className="font-display text-xl tracking-tight text-ink">Hami</span>
    </Link>
  );
}
