import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Section tag: a small black stamp with a split corner mark. */
export function Eyebrow({
  children,
  className,
  tone = "cyan",
}: {
  children: ReactNode;
  className?: string;
  tone?: "cyan" | "amber" | "muted";
}) {
  // "cyan" and "amber" both map to the orange accent; "muted" is quiet grey.
  return (
    <p className={cn("tag mb-5", tone === "muted" && "tag-muted", className)}>{children}</p>
  );
}
