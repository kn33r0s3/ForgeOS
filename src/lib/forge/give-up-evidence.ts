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
import { evidenceRank } from "./value.ts";

export const GIVE_UP_EVIDENCE: GiveUpEvidence[] = [];

export function evidenceFor(unknownId: string): GiveUpEvidence | null {
  // Strongest first: a later verified-payment must outweigh an earlier
  // stated-interest for the same unknown — never the first-recorded entry.
  let best: GiveUpEvidence | null = null;
  for (const e of GIVE_UP_EVIDENCE) {
    if (e.unknownId !== unknownId) continue;
    if (!best || evidenceRank(e) > evidenceRank(best)) best = e;
  }
  return best;
}
