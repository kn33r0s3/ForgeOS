import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Eyebrow({
  children,
  className,
  tone = "cyan",
}: {
  children: ReactNode;
  className?: string;
  tone?: "cyan" | "amber" | "muted";
}) {
  const toneClass =
    tone === "amber" ? "text-amber" : tone === "muted" ? "text-dim" : "text-cyan";
  return (
    <p
      className={cn(
        "mb-5 flex items-center gap-2 font-mono text-kicker font-medium uppercase tracking-[0.16em]",
        toneClass,
        className,
      )}
    >
      {children}
    </p>
  );
}
