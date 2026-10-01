import { EarningPathway } from "@/lib/earn/pathways";
import { Offer, OfferStatus, STATUS_LABEL } from "@/lib/earn/types";

type Props = {
  saved: Offer[];
  pathways: EarningPathway[];
  outcomeDrafts: Record<string, string>;
  onOutcomeDraftChange: (id: string, value: string) => void;
  onToggleNextAction: (id: string, index: number) => void;
  onUpdateStatus: (id: string, status: OfferStatus) => void;
  onRemove: (id: string) => void;
};

export function OfferList({
  saved,
  pathways,
  outcomeDrafts,
  onOutcomeDraftChange,
  onToggleNextAction,
  onUpdateStatus,
  onRemove,
}: Props) {
  return (
    <section className="space-y-3">
      <div>
        <p className="section-label">YOUR LOCAL WORKSPACE</p>
        <p className="text-xs text-neutral-500">
          Stored only in this browser. Advance status only when the real-world event actually happens.
        </p>
      </div>

      {saved.length === 0 ? (
        <div className="glass-panel p-6 text-sm text-neutral-500">No offers drafted yet. Create one above.</div>
      ) : (
        <div className="space-y-3">
          {saved.map((item) => {
            const st = STATUS_LABEL[item.status];
            const path = pathways.find((p) => p.id === item.pathway);
            return (
              <div key={item.id} className="glass-panel premium-edge p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-neutral-100">{item.title}</p>
                    <p className="text-xs text-neutral-500 mt-1">
                      {item.customer} · NPR {item.price || "—"} · {path?.title || item.pathway}
                    </p>
                    <p className="text-xs text-neutral-600 mt-0.5">Skill: {item.skill}</p>
                  </div>
                  <span className={`text-[10px] uppercase tracking-wider font-semibold ${st.color}`}>{st.en}</span>
                </div>

                <div className="rounded-xl border border-white/5 bg-black/20 p-3 space-y-2">
                  <p className="text-[10px] uppercase tracking-wider text-neutral-500">Next real actions</p>
                  {item.nextActions.map((action, index) => (
                    <label key={`${item.id}-${index}`} className="flex items-start gap-2 text-xs text-neutral-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={action.completed}
                        onChange={() => onToggleNextAction(item.id, index)}
                        className="mt-0.5 accent-forge-accent2"
                      />
                      <span className={action.completed ? "line-through text-neutral-600" : ""}>{action.text}</span>
                    </label>
                  ))}
                </div>

                {(item.status === "draft" || item.status === "customer_confirmed") && (
                  <label className="block">
                    <span className="text-[10px] uppercase tracking-wider text-neutral-500">
                      Honest outcome note (required to close)
                    </span>
                    <textarea
                      className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-forge-accent2/50"
                      rows={2}
                      value={outcomeDrafts[item.id] || item.outcomeNote || ""}
                      onChange={(e) => onOutcomeDraftChange(item.id, e.target.value)}
                      placeholder="What actually happened? For example: customer declined NPR 1,500, or payment received in cash."
                    />
                  </label>
                )}
                {item.outcomeNote && item.status !== "draft" && item.status !== "customer_confirmed" && (
                  <p className="text-xs text-neutral-400">
                    <strong className="text-neutral-300">Recorded outcome:</strong> {item.outcomeNote}
                  </p>
                )}

                <div className="flex flex-wrap gap-2">
                  {item.status === "draft" && (
                    <button
                      onClick={() => onUpdateStatus(item.id, "customer_confirmed")}
                      className="text-xs px-3 py-1.5 rounded-lg border border-forge-accent2/40 text-forge-accent2 hover:bg-forge-accent2/10"
                    >
                      Mark: customer confirmed interest
                    </button>
                  )}
                  {item.status === "customer_confirmed" && (
                    <button
                      onClick={() => onUpdateStatus(item.id, "paid")}
                      className="text-xs px-3 py-1.5 rounded-lg border border-forge-revenue/40 text-forge-revenue hover:bg-forge-revenue/10"
                    >
                      Mark: payment received
                    </button>
                  )}
                  {item.status !== "failed" && item.status !== "abandoned" && (
                    <button
                      onClick={() => onUpdateStatus(item.id, "failed")}
                      className="text-xs px-3 py-1.5 rounded-lg border border-forge-danger/30 text-forge-danger/90 hover:bg-forge-danger/10"
                    >
                      Mark: no sale
                    </button>
                  )}
                  {item.status !== "paid" && item.status !== "failed" && item.status !== "abandoned" && (
                    <button
                      onClick={() => onUpdateStatus(item.id, "abandoned")}
                      className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-neutral-400 hover:bg-white/[0.04]"
                    >
                      Mark: abandoned
                    </button>
                  )}
                  <button
                    onClick={() => onRemove(item.id)}
                    className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-neutral-500 hover:text-neutral-300"
                  >
                    Remove
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
