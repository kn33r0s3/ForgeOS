import { cn } from "@/lib/utils";

export function StatusPill({
  children,
  tone = "cyan",
}: {
  children: string;
  tone?: "cyan" | "amber";
}) {
  return (
    <span
      className={cn(
        "status-pill mt-7",
        tone === "amber" ? "status-pill-warning" : "status-pill-accent",
      )}
    >
      {children}
    </span>
  );
}
