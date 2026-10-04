// Recorded give-up evidence: what real people gave up for an answer.
//
// THIS LEDGER IS EMPTY. That is the honest state: no merchant has paid,
// committed, engaged, or stated interest for any unknown yet. A tier is
// earned here or it is "unscored" — never assigned.
//
// When evidence exists, record it:
//
//   { unknownId: "D12", kind: "verified-payment", actor: "Kathmandu retailer",
//     gaveUp: "Rs 500 for the recovered-sale count", recordedAt: "2026-10-09",
//     note: "sprint week log, day 3" }
//
// Kinds, strongest first: verified-payment > committed > replied-engaged >
// stated-interest. WTP stays a hypothesis until it lands here.

import type { GiveUpEvidence } from "./value";

export const GIVE_UP_EVIDENCE: GiveUpEvidence[] = [];

export function evidenceFor(unknownId: string): GiveUpEvidence | null {
  return GIVE_UP_EVIDENCE.find((e) => e.unknownId === unknownId) ?? null;
}
