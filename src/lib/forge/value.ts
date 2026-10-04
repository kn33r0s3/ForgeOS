// Value is the method.
//
// What value is: what a real person will give something up for — money,
// time, trust, attention, a change in behavior. Nothing is valuable in
// itself; value is always valued-by-someone.
//
// What makes something MORE valuable:
//   - close to survival: money in/out, keeping the shop open
//   - scarce alternatives: nobody else provides it
//   - urgent: the pain is now, not someday
//   - measurable: the gain is visible (a recovered sale, an hour saved)
//   - trusted: they believe the source
//   - low friction: fits existing behavior
//   - recurring: the need repeats
//
// THE EVIDENCE RULE (2026-10-04): a value tier is EARNED by recorded
// give-up evidence, never assigned by hand. Willingness-to-pay stays a
// hypothesis until someone actually gives something up. No evidence =
// "unscored" — never a high tier. An unscored unknown is not worthless;
// it is unpriced.

/** What someone gave up, recorded — not claimed. */
export type GiveUpKind =
  | "verified-payment" // money changed hands (receipt, transfer record)
  | "committed" // binding commitment: signed, deposited, scheduled — not yet paid
  | "replied-engaged" // gave time/attention: replied, used the tool, showed up
  | "stated-interest"; // words only: "I'd pay for that"

export interface GiveUpEvidence {
  /** Which unknown this evidence prices. */
  unknownId: string;
  kind: GiveUpKind;
  /** Who gave it up (segment, never a name without consent). */
  actor: string;
  /** What exactly was given up. */
  gaveUp: string;
  /** Where this is recorded — the receipt, the log line, the event. */
  recordedAt: string;
  note?: string;
}

export type EvidenceTier = 3 | 2 | 1 | "unscored";

/**
 * Tiers derived from recorded give-up evidence, strongest first:
 *   verified-payment (3) > committed (2) > replied-engaged (1) >
 *   stated-interest (1, weaker) > none (unscored).
 *
 * A tier-3 means money moved. Anything less is a weaker claim on value.
 */
export function tierFromEvidence(evidence: GiveUpEvidence | null): EvidenceTier {
  if (!evidence) return "unscored";
  switch (evidence.kind) {
    case "verified-payment":
      return 3;
    case "committed":
      return 2;
    case "replied-engaged":
    case "stated-interest":
      return 1;
  }
}

/** Numeric rank for sorting: verified-payment > committed > engaged > stated > none. */
export function evidenceRank(evidence: GiveUpEvidence | null): number {
  if (!evidence) return 0;
  switch (evidence.kind) {
    case "verified-payment":
      return 4;
    case "committed":
      return 3;
    case "replied-engaged":
      return 2;
    case "stated-interest":
      return 1;
  }
}

export function tierLabel(tier: EvidenceTier): string {
  return tier === 3
    ? "money-close"
    : tier === 2
      ? "enabler"
      : tier === 1
        ? "understanding"
        : "unscored";
}
