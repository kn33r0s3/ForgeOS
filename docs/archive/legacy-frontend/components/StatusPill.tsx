/**
 * Premium status indicator. Every state gets a deliberate color and
 * subtle treatment — never a generic "OK" unless the backend confirmed it.
 */
const STATE_STYLES: Record<string, string> = {
  // connectivity
  CONNECTED: "text-forge-revenue border-forge-revenue/35 bg-forge-revenue/10",
  DEGRADED: "text-forge-warn border-forge-warn/35 bg-forge-warn/10",
  OFFLINE: "text-forge-danger border-forge-danger/35 bg-forge-danger/10",
  UNKNOWN: "text-neutral-400 border-neutral-600/35 bg-neutral-600/10",
  // system
  OBSERVING: "text-forge-revenue border-forge-revenue/35 bg-forge-revenue/10",
  IDLE: "text-neutral-400 border-neutral-600/35 bg-neutral-600/10",
  "CYCLE RUNNING": "text-forge-accent border-forge-accent/40 bg-forge-accent/12 status-live",
  EXECUTING: "text-forge-accent border-forge-accent/40 bg-forge-accent/12 status-live",
  "QUEUED WORK": "text-forge-accent2 border-forge-accent2/35 bg-forge-accent2/10",
  CONNECTING: "text-neutral-400 border-neutral-600/35 bg-neutral-600/10",
  // execution lifecycle
  PLANNED: "text-neutral-300 border-neutral-500/35 bg-neutral-500/10",
  READY: "text-forge-accent2 border-forge-accent2/35 bg-forge-accent2/10",
  "OWNER AUTHORIZATION REQUIRED": "text-forge-warn border-forge-warn/35 bg-forge-warn/10",
  AUTHORIZED: "text-forge-accent2 border-forge-accent2/35 bg-forge-accent2/10",
  "IN PROGRESS": "text-forge-accent border-forge-accent/40 bg-forge-accent/12 status-live",
  COMPLETED: "text-neutral-300 border-neutral-500/35 bg-neutral-500/10",
  VERIFIED: "text-forge-revenue border-forge-revenue/35 bg-forge-revenue/10",
  FAILED: "text-forge-danger border-forge-danger/35 bg-forge-danger/10",
  ABANDONED: "text-forge-danger border-forge-danger/35 bg-forge-danger/10",
  BLOCKED: "text-forge-danger border-forge-danger/35 bg-forge-danger/10",
  LEARNED: "text-forge-revenue border-forge-revenue/35 bg-forge-revenue/10",
  WAITING: "text-forge-warn border-forge-warn/35 bg-forge-warn/10",
  PREDICTED: "text-forge-accent2 border-forge-accent2/35 bg-forge-accent2/10",
};

export default function StatusPill({ label }: { label: string }) {
  const key = label.toUpperCase();
  const style =
    STATE_STYLES[key] ||
    "text-neutral-300 border-neutral-500/35 bg-neutral-500/10";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold tracking-wide ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {label.toUpperCase()}
    </span>
  );
}
