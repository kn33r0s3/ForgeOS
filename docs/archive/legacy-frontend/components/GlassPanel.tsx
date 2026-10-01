export default function GlassPanel({
  children,
  className = "",
  glow = false,
  glowColor = "violet",
}: {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  glowColor?: "violet" | "blue" | "revenue";
}) {
  const glowClass =
    glow
      ? glowColor === "blue"
        ? "glow-border-blue"
        : glowColor === "revenue"
        ? "glow-border-revenue"
        : "glow-border"
      : "";

  return (
    <div
      className={`glass-panel premium-edge rounded-2xl ${glowClass} ${className}`}
    >
      {children}
    </div>
  );
}
