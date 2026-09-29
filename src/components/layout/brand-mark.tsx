import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

/**
 * Stacked masthead mark: the Hami icon above a blackletter wordmark.
 * `tone="dark"` is for the orange masthead (black type); `"light"` for
 * dark surfaces such as the footer (orange type).
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
      aria-label="Hami home"
    >
      <img
        src="/hami-mark.png"
        alt=""
        width={32}
        height={32}
        className={cn(
          "size-8 rounded-card border-2 object-cover transition-transform duration-150 group-hover:-rotate-6",
          tone === "dark" ? "border-black bg-black" : "border-line bg-card",
        )}
      />
      <span
        className={cn(
          "font-gothic text-2xl leading-none",
          tone === "dark" ? "text-black" : "text-accent",
        )}
      >
        Hami
      </span>
    </Link>
  );
}
