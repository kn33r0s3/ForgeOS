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
        "mt-7 inline-flex items-center border px-3 py-2 font-mono text-micro uppercase tracking-[0.14em]",
        tone === "amber"
          ? "border-amber/40 text-amber"
          : "border-cyan/40 text-cyan",
      )}
    >
      {children}
    </span>
  );
}
