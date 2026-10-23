import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

/**
 * Stacked masthead mark: the Hami icon above a blackletter wordmark.
 * `tone="dark"` (black type) is for light/orange surfaces; `"light"` (orange
 * type) for dark surfaces such as the current night masthead and footer.
 * Only "light" is used today.
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
      className={cn("group flex items-center gap-2.5", className)}
      aria-label="HAMI SYSTEMS home"
    >
      <picture className="size-8 shrink-0">
        <source srcSet="/favicon.svg" type="image/svg+xml" />
        <img
          src="/hami-mark.png"
          alt=""
          width={32}
          height={32}
          decoding="async"
          className={cn(
            "size-8 rounded-card border-2 object-cover transition-transform duration-150 group-hover:-rotate-6",
            tone === "dark" ? "border-black bg-black" : "border-line bg-card",
          )}
        />
      </picture>
      <span className="flex flex-col items-start gap-0.5">
        <span
          className={cn(
            "font-gothic text-2xl leading-none",
            tone === "dark" ? "text-black" : "text-accent",
          )}
        >
          Hami
        </span>
        <span
          className={cn(
            "text-[0.55rem] font-extrabold uppercase leading-none tracking-[0.2em]",
            tone === "dark" ? "text-black" : "text-accent",
          )}
        >
          SYSTEMS
        </span>
      </span>
    </Link>
  );
}
