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
  // "cyan" and "amber" both map to the Hami gold accent; "muted" is dim ink.
  const toneClass = tone === "muted" ? "text-dim" : "text-accent";
  return (
    <p
      className={cn(
        "mb-5 flex items-center gap-2 font-mono text-micro uppercase tracking-[0.14em]",
        toneClass,
        className,
      )}
    >
      {children}
    </p>
  );
}
