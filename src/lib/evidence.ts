/**
 * Hami's evidence engine — the operator's verification loop, as code.
 *
 * Rule: nothing enters Hami's knowledge — no need, no unknown resolution,
 * no claim on any public surface — without passing the gate. A claim needs
 * an evidence class, at least one named source, a confidence grade, and a
 * weakest link (the part most likely to be wrong). Anything less is
 * rejected: never banked, never displayed, never acted on.
 *
 * Evidence classes, strongest first:
 *   actual    — measured in reality (a real conversation, a real transaction)
 *   observed  — seen directly in a primary source (telemetry, a document)
 *   reported  — carried by press or a single party (treat as rumor-grade
 *               until corroborated)
 *   inferred  — our synthesis from observations (labeled as ours)
 *   estimated — a number with stated assumptions, not a measurement
 *   unknown   — we don't know; the honest default
 */

export type EvidenceClass =
  | "actual"
  | "observed"
  | "reported"
  | "inferred"
  | "estimated"
  | "unknown";

export type Confidence = "high" | "medium" | "low";

const CLASS_RANK: Record<EvidenceClass, number> = {
  actual: 6,
  observed: 5,
  reported: 4,
  inferred: 3,
  estimated: 2,
  unknown: 1,
};

/** Returns true if `a` is at least as strong as `b`. */
export function classAtLeast(a: EvidenceClass, b: EvidenceClass): boolean {
  return CLASS_RANK[a] >= CLASS_RANK[b];
}

export interface Claim {
  /** The statement being made. No invented voices, no long fabricated quotes. */
  statement: string;
  evidenceClass: EvidenceClass;
  /** Named sources. "Research" is not a source; name the document, dataset, or voice. */
  sources: string[];
  confidence: Confidence;
  /** The part of this claim most likely to be wrong, and what would change our mind. */
  weakestLink: string;
}

export class EvidenceGateError extends Error {
  constructor(reason: string) {
    super(`evidence gate rejected claim: ${reason}`);
    this.name = "EvidenceGateError";
  }
}

/**
 * The gate. Throws EvidenceGateError on anything that doesn't meet the bar.
 * This is the "0 failures" discipline: a claim that can't say what it is,
 * where it came from, how sure it is, and what would prove it wrong
 * does not get banked. Ever.
 */
export function verifyClaim(claim: Claim): Claim {
  if (!claim || typeof claim !== "object") {
    throw new EvidenceGateError("not a claim at all");
  }
  if (!claim.statement || claim.statement.trim().length < 10) {
    throw new EvidenceGateError("statement too thin to mean anything");
  }
  if (!CLASS_RANK[claim.evidenceClass]) {
    throw new EvidenceGateError(`unknown evidence class "${claim.evidenceClass}"`);
  }
  if (!Array.isArray(claim.sources) || claim.sources.length === 0) {
    throw new EvidenceGateError("no sources named");
  }
  for (const s of claim.sources) {
    if (!s || s.trim().length === 0) {
      throw new EvidenceGateError("empty source entry");
    }
  }
  if (!["high", "medium", "low"].includes(claim.confidence)) {
    throw new EvidenceGateError(`no confidence grade ("${claim.confidence}")`);
  }
  if (!claim.weakestLink || claim.weakestLink.trim().length < 10) {
    throw new EvidenceGateError("no weakest link named");
  }
  // "Mostly accurate" is not the bar: high confidence requires strong evidence.
  if (
    claim.confidence === "high" &&
    !classAtLeast(claim.evidenceClass, "observed")
  ) {
    throw new EvidenceGateError(
      `high confidence needs at least observed evidence, got "${claim.evidenceClass}"`,
    );
  }
  // A claim carried only by rumor-grade evidence must say so in its weakest link.
  if (
    claim.evidenceClass === "reported" &&
    !/single-source|press-reported|rumor|unverified|corroborat/i.test(claim.weakestLink)
  ) {
    throw new EvidenceGateError(
      "reported-class claims must name the single-source/rumor risk in their weakest link",
    );
  }
  return claim;
}

/**
 * Batch gate: verifies every claim, returns the verified list.
 * One bad claim fails the batch — the way one bad fact fails a report.
 */
export function verifyAll(claims: Claim[]): Claim[] {
  return claims.map(verifyClaim);
}
