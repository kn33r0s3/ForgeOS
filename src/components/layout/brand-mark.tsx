import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

/**
 * One Hami Systems lockup shared by the site header and footer.
 * The symbol is also the favicon, so the brand stays consistent at every size.
 */
export function BrandMark({
  className,
  tone = "light",
}: {
  className?: string;
  tone?: "light" | "dark";
}) {
  return (
    <Link
      to="/"
      className={cn("group inline-flex min-w-0 items-center gap-2.5", className)}
      aria-label="Hami Systems home"
    >
      <img
        src="/favicon.svg"
        alt=""
        width={40}
        height={40}
        decoding="async"
        className="size-10 shrink-0 rounded-md transition-transform duration-150 group-hover:-rotate-3"
      />
      <span className="flex flex-col leading-none">
        <span
          className={cn(
            "font-serif text-[1.2rem] font-bold tracking-[0.09em]",
            tone === "dark" ? "text-black" : "text-accent",
          )}
        >
          HAMI
        </span>
        <span
          className={cn(
            "mt-1 font-mono text-[0.52rem] font-bold tracking-[0.3em]",
            tone === "dark" ? "text-black/70" : "text-muted",
          )}
        >
          SYSTEMS
        </span>
      </span>
    </Link>
  );
}
