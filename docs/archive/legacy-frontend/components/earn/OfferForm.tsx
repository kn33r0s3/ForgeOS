import { FormEvent } from "react";
import { EarningPathway } from "@/lib/earn/pathways";

type OfferDraft = { title: string; skill: string; customer: string; price: string };

type Props = {
  chosen: EarningPathway;
  offer: OfferDraft;
  onChange: (offer: OfferDraft) => void;
  onSubmit: (e: FormEvent) => void;
  message: string;
};

export function OfferForm({ chosen, offer, onChange, onSubmit, message }: Props) {
  return (
    <section className="glass-panel premium-edge p-5 space-y-4">
      <div>
        <p className="section-label">DRAFT YOUR FIRST OFFER · SAVES OFFLINE</p>
        <p className="text-sm text-neutral-400 mt-1">
          Selected: <strong className="text-neutral-200">{chosen.title}</strong>. Reality test: {chosen.firstTest}
        </p>
      </div>

      <div className="rounded-xl border border-white/5 bg-black/20 p-4">
        <p className="text-xs text-neutral-500 mb-2 uppercase tracking-wider">Next real-world actions</p>
        <ol className="list-decimal list-inside space-y-1 text-sm text-neutral-300">
          {chosen.nextActions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ol>
      </div>

      <form onSubmit={onSubmit} className="grid md:grid-cols-2 gap-3">
        <input
          className="rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm outline-none focus:border-forge-accent2/50"
          placeholder="Specific offer (e.g. 3 social posts for a cafe)"
          value={offer.title}
          onChange={(e) => onChange({ ...offer, title: e.target.value })}
        />
        <input
          className="rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm outline-none focus:border-forge-accent2/50"
          placeholder="Your real skill / proof"
          value={offer.skill}
          onChange={(e) => onChange({ ...offer, skill: e.target.value })}
        />
        <input
          className="rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm outline-none focus:border-forge-accent2/50"
          placeholder="Customer type (e.g. local cafe owner)"
          value={offer.customer}
          onChange={(e) => onChange({ ...offer, customer: e.target.value })}
        />
        <input
          className="rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm outline-none focus:border-forge-accent2/50"
          type="number"
          min={0}
          step={1}
          placeholder="Expected price in NPR (not revenue)"
          value={offer.price}
          onChange={(e) => onChange({ ...offer, price: e.target.value })}
        />
        <button
          className="md:col-span-2 rounded-lg bg-forge-accent/90 hover:bg-forge-accent text-white font-medium py-2.5 text-sm transition"
          type="submit"
        >
          Save offer locally
        </button>
      </form>
      {message && <p className="text-sm text-forge-warn">{message}</p>}
    </section>
  );
}
