// Value is the method.
//
// What value is: what a real person will give something up for — money,
// time, trust, attention, a change in behavior. Nothing is valuable in
// itself; value is always valued-by-someone. Money changing hands is the
// observable proof. The revenue ladder (Rs 1 → 10,000 → 100,000 → recurring)
// is the ground truth the engine optimizes toward.
//
// What makes something MORE valuable:
//   - close to survival: money in/out, keeping the shop open
//   - scarce alternatives: nobody else provides it
//     (known things are commodities; unknowns are the asset)
//   - urgent: the pain is now, not someday
//   - measurable: the gain is visible (a recovered sale, an hour saved)
//   - trusted: they believe the source (owners auto-distrust vendor-shaped things)
//   - low friction: fits existing behavior (phone-first, cash-honest)
//   - recurring: the need repeats (one-off value dies; recurring compounds)
//
// What makes something LESS valuable is the mirror: far from money,
// commodity, someday-pain, unmeasurable, distrusted, high friction, one-off.
//
// The method: every unknown is scored on value-density — who gives up what
// for the answer, and when. The ripeness queue ranks by value first,
// doability second. Effort-ordering without value-ordering is just motion.

export type ValueTier = 1 | 2 | 3;

/**
 * Value tiers:
 *   3 — the answer is directly tied to money changing hands or survival.
 *       (Would a merchant pay, wait, or change behavior for this answer?)
 *   2 — the answer enables a tier-3 answer or removes a blocker to value.
 *   1 — shapes understanding; far from money. Still worth knowing, never first.
 */
export interface ValueScore {
  tier: ValueTier;
  /** One line: who gives up what for this answer, and when. */
  why: string;
}

export function tierLabel(tier: ValueTier): string {
  return tier === 3 ? "money-close" : tier === 2 ? "enabler" : "understanding";
}
