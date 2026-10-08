// HYPOTHESIZED value density for the discovery unknowns (D1-D70).
//
// WTP HYPOTHESIS - NOT EVIDENCE. These are hand judgments about which
// answers look money-close, kept only as an internal tiebreaker for the
// ripeness queue. They are never displayed as tiers, never called scores,
// and never leave the engine. A tier is earned by recorded give-up
// evidence (see ./value.ts + ./give-up-evidence.ts) or the unknown is
// "unscored". Willingness-to-pay stays a hypothesis until evidence.
// Value tiers for the discovery unknowns (D1–D70).
// Scored 2026-10-04 on value-density: who gives up what for the answer, and when.
//   3 = money-close: the answer is directly tied to money changing hands or survival
//   2 = enabler: unlocks a tier-3 answer or removes a blocker to value
//   1 = understanding: shapes the picture; far from money. Never first.

import type { EvidenceTier } from "./value";
import { evidenceFor } from "./give-up-evidence.ts";
import { tierFromEvidence } from "./value.ts";

/** A WTP hypothesis: which answers look money-close. Not evidence. Never displayed. */
export interface HypothesizedValue {
  hypothesis: 1 | 2 | 3 | null;
  why: string;
}

const HYPOTHESES: Record<string, HypothesizedValue> = {
  D1: { hypothesis: 3, why: "Sizes a pay-per-recovered-job model — the wedge's price tag." },
  D2: { hypothesis: 3, why: "Thesis-threatening: decides whether the wedge is demand or fulfillment." },
  D3: { hypothesis: 2, why: "Maps the trust channels Hami must travel to reach first customers." },
  D4: { hypothesis: 1, why: "Research method — where to listen. Useful, not valuable." },
  D5: { hypothesis: 3, why: "Quantifies the presence tax — the hours chaos steals from revenue." },
  D6: { hypothesis: 2, why: "Decides whether the accountant's job is automatable at all." },
  D7: { hypothesis: 1, why: "Who gets to start — structural context, far from a transaction." },
  D8: { hypothesis: 1, why: "Skill pathways — interesting, no near-term money." },
  D9: { hypothesis: 1, why: "Counts the invisible — shapes the mission, not the revenue." },
  D10: { hypothesis: 2, why: "Tells Hami which categories it can enter on reputation vs. paid reach." },
  D11: { hypothesis: 2, why: "Segments merchants by what binds them — demand or presence." },
  D12: { hypothesis: 3, why: "Counts inquiries dying unanswered — direct revenue leak." },
  D13: { hypothesis: 3, why: "Where the sale actually closes — the transaction's location." },
  D14: { hypothesis: 3, why: "How informal merchants take digital money — the payment reality." },
  D15: { hypothesis: 2, why: "A legal informal-merchant tier would unlock the whole segment." },
  D16: { hypothesis: 2, why: "Regulation moving sellers informal reshapes where Hami must live." },
  D17: { hypothesis: 2, why: "Price-withholding shapes the inquiry funnel Hami would serve." },
  D18: { hypothesis: 3, why: "Settlement friction pushing merchants back to cash — money movement." },
  D19: { hypothesis: 2, why: "Fake-confirmation scams are a trust blocker on digital payments." },
  D20: { hypothesis: 2, why: "Who sees the QR money at the counter — operational trust." },
  D21: { hypothesis: 2, why: "Bad QR app ratings push merchants to cash — adoption blocker." },
  D22: { hypothesis: 3, why: "What a kirana actually nets — the survival number everything prices against." },
  D23: { hypothesis: 2, why: "Whether formal credit reaches merchants — the credit gap's shape." },
  D24: { hypothesis: 3, why: "Udharo in vs. out — the shop's real cash position." },
  D25: { hypothesis: 2, why: "The taken corner — defines exactly where the open wedge is." },
  D26: { hypothesis: 2, why: "Resale liquidity tells how merchants exit — the end of the lifecycle." },
  D27: { hypothesis: 1, why: "Repair-trade paradox — pattern already banked, low marginal value." },
  D28: { hypothesis: 1, why: "Grey parts channel — trade economics, far from Hami's money." },
  D29: { hypothesis: 2, why: "Whether repair skill can be delegated — decides if the trade scales." },
  D30: { hypothesis: 2, why: "How repair customers choose — the trust mechanism to plug into." },
  D31: { hypothesis: 3, why: "Karobar's ARPU is the proven price point — Rs 2,000/yr is real." },
  D32: { hypothesis: 3, why: "What Karobar doesn't do is the open wedge — the gap with a price." },
  D33: { hypothesis: 2, why: "Organic vs. pushed expansion — the growth lesson, not the money." },
  D34: { hypothesis: 2, why: "Why free giants failed to monetize — the pricing lesson." },
  D35: { hypothesis: 1, why: "Ride-sharing regulation history — context, not value." },
  D36: { hypothesis: 1, why: "Tootle's end cost — postmortem, already mined for the lesson." },
  D37: { hypothesis: 1, why: "Pathao vs. Tootle — postmortem comparison, lesson banked." },
  D38: { hypothesis: 1, why: "Regulatory double-bind pattern — lesson banked." },
  D39: { hypothesis: 3, why: "How merchants finance the stock-up — seasonal money movement." },
  D40: { hypothesis: 2, why: "Cash pulse vs. QR — the seasonal payment mix." },
  D41: { hypothesis: 3, why: "Who eats unsold stock — risk is money." },
  D42: { hypothesis: 2, why: "Dhukuti as credit rail — the informal finance to understand." },
  D43: { hypothesis: 2, why: "Co-op borrowing by unpapered merchants — credit access reality." },
  D44: { hypothesis: 2, why: "Co-op fraud wave — the trust crater Hami must navigate." },
  D45: { hypothesis: 2, why: "NRB directive — regulatory shape of the credit landscape." },
  D46: { hypothesis: 1, why: "Co-op active-vs-shell share — a statistic, far from money." },
  D47: { hypothesis: 1, why: "Sastodeal relaunch status — competitor trivia, lesson already banked." },
  D48: { hypothesis: 3, why: "Daraz seller profitability — are platform sellers making money." },
  D49: { hypothesis: 1, why: "Gyapu status — competitor trivia." },
  D50: { hypothesis: 1, why: "Manpower fee procedure — lane detail, far from Hami's money." },
  D51: { hypothesis: 3, why: "Sunchaandi buyback margins — the counter's real economics." },
  D52: { hypothesis: 2, why: "Unofficial gold channels — the trust break Hami could price." },
  D53: { hypothesis: 2, why: "Organized retail vs. family shops — the competitive landscape." },
  D54: { hypothesis: 2, why: "Karigar labor dependence — bargaining power at peaks." },
  D55: { hypothesis: 3, why: "Rent's share of net margin — the survival tax, quantified." },
  D56: { hypothesis: 3, why: "Advance rent as entry fee — the capital barrier to starting." },
  D57: { hypothesis: 2, why: "Shutter-churn repricing — the vacancy economy's mechanics." },
  D58: { hypothesis: 2, why: "Closures to migration vs. reopening — where the people go." },
  D59: { hypothesis: 2, why: "Rent tax passthrough — who really pays." },
  D60: { hypothesis: 3, why: "The COD cash float — the T+ of Nepali online commerce." },
  D61: { hypothesis: 3, why: "Refusal/RTO rates — failed payments, the margin killer." },
  D62: { hypothesis: 3, why: "Rural COD settlement — does the cash ever arrive." },
  D63: { hypothesis: 2, why: "Informal rider volume — the shadow logistics layer." },
  D64: { hypothesis: 2, why: "Physical risk of COD cash — the unpriced failure mode." },
  D65: { hypothesis: 3, why: "Receipt-vs-cash gap is the migration lane's money truth." },
  D66: { hypothesis: 2, why: "Locates the actual fee collection point regulation misses." },
  D67: { hypothesis: 3, why: "Worker-borne cost of the lane's shocks — the fragility number." },
  D68: { hypothesis: 3, why: "The debt product, not the fee, is the real trap." },
  D69: { hypothesis: 2, why: "Decides whether the Malaysia corridor re-concentrates." },
  D70: { hypothesis: 3, why: "Fee harvest without departures is the next trust poison." },
};

export function hypothesizedValueOf(id: string): HypothesizedValue {
  return HYPOTHESES[id] ?? {
    hypothesis: null,
    why: "Unassessed — no value/WTP hypothesis recorded.",
  };
}

/** The evidence tier: earned or unscored. The only tier the engine shows. */
export function evidenceTierOf(id: string): EvidenceTier {
  return tierFromEvidence(evidenceFor(id));
}
