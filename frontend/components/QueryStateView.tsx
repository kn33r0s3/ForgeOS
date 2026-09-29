import { QueryState } from "@/lib/useForgeQuery";

const copy: Record<string, { title: string; body: string }> = {
  loading: { title: "Observing current signals…", body: "Hami is reading the latest available state." },
  offline: { title: "Hami is offline", body: "The frontend could not reach the Hami backend. Check the connection, then retry." },
  error: { title: "Hami could not load this view", body: "Some backend data was unavailable. The rest of the system may still be usable." },
};

export default function QueryStateView({ state, error, emptyLabel = "Nothing verified here yet.", onRetry }: { state: QueryState; error?: string | null; emptyLabel?: string; onRetry?: () => void }) {
  if (state === "empty") return <div className="empty-state mx-auto mt-10 max-w-xl text-center"><p className="font-medium text-neutral-300">{emptyLabel}</p><p className="mt-2 text-sm text-neutral-500">Hami will show this area when the underlying evidence exists.</p></div>;
  if (!(state in copy)) return null;
  const item = copy[state];
  return <div className={`glass-panel mx-auto mt-10 max-w-xl p-10 text-center ${state === "offline" || state === "error" ? "border-forge-danger/25" : ""}`}><div className="mx-auto mb-5 flex h-10 w-10 items-center justify-center rounded-full border border-white/[0.1] bg-white/[0.04]"><span className={`h-2 w-2 rounded-full ${state === "loading" ? "animate-pulse bg-forge-accent2" : "bg-forge-danger"}`} /></div><p className="font-display text-lg font-semibold text-white">{item.title}</p><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-neutral-500">{item.body}</p>{error && state === "error" && <p className="mx-auto mt-4 max-w-md text-xs text-neutral-600">{error}</p>}{onRetry && <button onClick={onRetry} className="action mt-6">Retry connection</button>}</div>;
}
