// Value tiers for the discovery unknowns (D1–D64).
// Scored 2026-10-04 on value-density: who gives up what for the answer, and when.
//   3 = money-close: the answer is directly tied to money changing hands or survival
//   2 = enabler: unlocks a tier-3 answer or removes a blocker to value
//   1 = understanding: shapes the picture; far from money. Never first.

import type { ValueScore, ValueTier } from "./value";

const TIERS: Record<string, ValueScore> = {
  D1: { tier: 3, why: "Sizes a pay-per-recovered-job model — the wedge's price tag." },
  D2: { tier: 3, why: "Thesis-threatening: decides whether the wedge is demand or fulfillment." },
  D3: { tier: 2, why: "Maps the trust channels Hami must travel to reach first customers." },
  D4: { tier: 1, why: "Research method — where to listen. Useful, not valuable." },
  D5: { tier: 3, why: "Quantifies the presence tax — the hours chaos steals from revenue." },
  D6: { tier: 2, why: "Decides whether the accountant's job is automatable at all." },
  D7: { tier: 1, why: "Who gets to start — structural context, far from a transaction." },
  D8: { tier: 1, why: "Skill pathways — interesting, no near-term money." },
  D9: { tier: 1, why: "Counts the invisible — shapes the mission, not the revenue." },
  D10: { tier: 2, why: "Tells Hami which categories it can enter on reputation vs. paid reach." },
  D11: { tier: 2, why: "Segments merchants by what binds them — demand or presence." },
  D12: { tier: 3, why: "Counts inquiries dying unanswered — direct revenue leak." },
  D13: { tier: 3, why: "Where the sale actually closes — the transaction's location." },
  D14: { tier: 3, why: "How informal merchants take digital money — the payment reality." },
  D15: { tier: 2, why: "A legal informal-merchant tier would unlock the whole segment." },
  D16: { tier: 2, why: "Regulation moving sellers informal reshapes where Hami must live." },
  D17: { tier: 2, why: "Price-withholding shapes the inquiry funnel Hami would serve." },
  D18: { tier: 3, why: "Settlement friction pushing merchants back to cash — money movement." },
  D19: { tier: 2, why: "Fake-confirmation scams are a trust blocker on digital payments." },
  D20: { tier: 2, why: "Who sees the QR money at the counter — operational trust." },
  D21: { tier: 2, why: "Bad QR app ratings push merchants to cash — adoption blocker." },
  D22: { tier: 3, why: "What a kirana actually nets — the survival number everything prices against." },
  D23: { tier: 2, why: "Whether formal credit reaches merchants — the credit gap's shape." },
  D24: { tier: 3, why: "Udharo in vs. out — the shop's real cash position." },
  D25: { tier: 2, why: "The taken corner — defines exactly where the open wedge is." },
  D26: { tier: 2, why: "Resale liquidity tells how merchants exit — the end of the lifecycle." },
  D27: { tier: 1, why: "Repair-trade paradox — pattern already banked, low marginal value." },
  D28: { tier: 1, why: "Grey parts channel — trade economics, far from Hami's money." },
  D29: { tier: 2, why: "Whether repair skill can be delegated — decides if the trade scales." },
  D30: { tier: 2, why: "How repair customers choose — the trust mechanism to plug into." },
  D31: { tier: 3, why: "Karobar's ARPU is the proven price point — Rs 2,000/yr is real." },
  D32: { tier: 3, why: "What Karobar doesn't do is the open wedge — the gap with a price." },
  D33: { tier: 2, why: "Organic vs. pushed expansion — the growth lesson, not the money." },
  D34: { tier: 2, why: "Why free giants failed to monetize — the pricing lesson." },
  D35: { tier: 1, why: "Ride-sharing regulation history — context, not value." },
  D36: { tier: 1, why: "Tootle's end cost — postmortem, already mined for the lesson." },
  D37: { tier: 1, why: "Pathao vs. Tootle — postmortem comparison, lesson banked." },
  D38: { tier: 1, why: "Regulatory double-bind pattern — lesson banked." },
  D39: { tier: 3, why: "How merchants finance the stock-up — seasonal money movement." },
  D40: { tier: 2, why: "Cash pulse vs. QR — the seasonal payment mix." },
  D41: { tier: 3, why: "Who eats unsold stock — risk is money." },
  D42: { tier: 2, why: "Dhukuti as credit rail — the informal finance to understand." },
  D43: { tier: 2, why: "Co-op borrowing by unpapered merchants — credit access reality." },
  D44: { tier: 2, why: "Co-op fraud wave — the trust crater Hami must navigate." },
  D45: { tier: 2, why: "NRB directive — regulatory shape of the credit landscape." },
  D46: { tier: 1, why: "Co-op active-vs-shell share — a statistic, far from money." },
  D47: { tier: 1, why: "Sastodeal relaunch status — competitor trivia, lesson already banked." },
  D48: { tier: 3, why: "Daraz seller profitability — are platform sellers making money." },
  D49: { tier: 1, why: "Gyapu status — competitor trivia." },
  D50: { tier: 1, why: "Manpower fee procedure — lane detail, far from Hami's money." },
  D51: { tier: 3, why: "Sunchaandi buyback margins — the counter's real economics." },
  D52: { tier: 2, why: "Unofficial gold channels — the trust break Hami could price." },
  D53: { tier: 2, why: "Organized retail vs. family shops — the competitive landscape." },
  D54: { tier: 2, why: "Karigar labor dependence — bargaining power at peaks." },
  D55: { tier: 3, why: "Rent's share of net margin — the survival tax, quantified." },
  D56: { tier: 3, why: "Advance rent as entry fee — the capital barrier to starting." },
  D57: { tier: 2, why: "Shutter-churn repricing — the vacancy economy's mechanics." },
  D58: { tier: 2, why: "Closures to migration vs. reopening — where the people go." },
  D59: { tier: 2, why: "Rent tax passthrough — who really pays." },
  D60: { tier: 3, why: "The COD cash float — the T+ of Nepali online commerce." },
  D61: { tier: 3, why: "Refusal/RTO rates — failed payments, the margin killer." },
  D62: { tier: 3, why: "Rural COD settlement — does the cash ever arrive." },
  D63: { tier: 2, why: "Informal rider volume — the shadow logistics layer." },
  D64: { tier: 2, why: "Physical risk of COD cash — the unpriced failure mode." },
};

export function valueOf(id: string): ValueScore {
  return TIERS[id] ?? { tier: 1, why: "Unscored — defaults to understanding until judged." };
}

export function valueTier(id: string): ValueTier {
  return valueOf(id).tier;
}
