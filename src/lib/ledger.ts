/**
 * Hami public proof ledger — claim schema.
 *
 * Rules (from the owner):
 * - Six primitives only: ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION.
 * - A claim renders only with a state AND evidence that passes the evidence
 *   gate (see ./evidence.ts). No state or no evidence means no render.
 * - Contradicted claims are shown, never hidden. A contradicted claim must
 *   name what contradicts it.
 * - ESTIMATED is never shown as ACTUAL. The value kind must match the
 *   evidence class, and an ESTIMATED value must say "estimated" in its label.
 * - No fabricated customers, revenue, or outcomes. Every value in CLAIMS is
 *   a real measurement or an explicit zero. No personal data on public pages.
 * - No new spend. The ledger reads static data; it makes no network calls
 *   and buys nothing.
 */

import {
  verifyClaim,
  type Claim as EvidenceClaim,
  type EvidenceClass,
} from "./evidence.ts";

/** The six primitives. Nothing else is a Hami primitive. */
export type Primitive =
  | "ENTITY"
  | "RELATION"
  | "EVENT"
  | "EVIDENCE"
  | "CAPABILITY"
  | "ACTION";

export const PRIMITIVES: Primitive[] = [
  "ENTITY",
  "RELATION",
  "EVENT",
  "EVIDENCE",
  "CAPABILITY",
  "ACTION",
];

export type LedgerClaimState =
  | "proposed"
  | "running"
  | "completed"
  | "contradicted";

export type LedgerValueKind = "ACTUAL" | "ESTIMATED";

export interface LedgerClaim {
  /** Stable id, e.g. "EXP-1", "M6-H", "RS-0". */
  id: string;
  /** English title. */
  title: string;
  /** Devanagari-first heading. Headings render this first, English second. */
  titleNe: string;
  state: LedgerClaimState;
  /** Which of the six primitives this claim is about. */
  primitive: Primitive;
  /** The evidence-gated statement. Must pass verifyClaim. */
  claim: EvidenceClaim;
  /** ACTUAL = measured. ESTIMATED = a number with stated assumptions. */
  valueKind: LedgerValueKind;
  /** The display value. An ESTIMATED value must say "estimated" in it. */
  valueLabel: string;
  /** Required when state is "contradicted": the id of the claim or record
   *  that contradicts this one. */
  contradictedBy?: string;
  /** ISO date of the last state change. */
  updatedAt: string;
}

export class LedgerGateError extends Error {
  constructor(reason: string) {
    super(`ledger gate rejected claim: ${reason}`);
    this.name = "LedgerGateError";
  }
}

/**
 * The ledger gate. Throws LedgerGateError on anything that must not render.
 * A claim renders only when it has a state, passes the evidence gate, its
 * value kind matches its evidence class, an ESTIMATED value is labeled as
 * such, and a contradicted claim names what contradicts it.
 */
export function verifyLedgerClaim(claim: LedgerClaim): LedgerClaim {
  if (!claim || typeof claim !== "object") {
    throw new LedgerGateError("not a claim at all");
  }
  if (!claim.id || claim.id.trim().length === 0) {
    throw new LedgerGateError("no id");
  }
  if (!claim.title || claim.title.trim().length < 3) {
    throw new LedgerGateError(`"${claim.id}" title too thin`);
  }
  if (!claim.titleNe || claim.titleNe.trim().length === 0) {
    throw new LedgerGateError(`"${claim.id}" missing Devanagari heading`);
  }
  if (
    !(["proposed", "running", "completed", "contradicted"] as string[]).includes(
      claim.state,
    )
  ) {
    throw new LedgerGateError(`"${claim.id}" has no state`);
  }
  if (!PRIMITIVES.includes(claim.primitive)) {
    throw new LedgerGateError(`"${claim.id}" is not one of the six primitives`);
  }
  // ESTIMATED is never shown as ACTUAL. The value kind must follow the
  // evidence class: only actual/observed evidence may be ACTUAL. This
  // check runs before the evidence gate so the ledger owns the error.
  const measured: EvidenceClass[] = ["actual", "observed"];
  if (claim.valueKind === "ACTUAL" && !measured.includes(claim.claim.evidenceClass)) {
    throw new LedgerGateError(
      `"${claim.id}" shows ACTUAL but its evidence is "${claim.claim.evidenceClass}"`,
    );
  }
  if (claim.valueKind === "ESTIMATED" && !/estimated/i.test(claim.valueLabel)) {
    throw new LedgerGateError(
      `"${claim.id}" is ESTIMATED but its label does not say so`,
    );
  }
  if (claim.valueKind !== "ACTUAL" && claim.valueKind !== "ESTIMATED") {
    throw new LedgerGateError(`"${claim.id}" has no value kind`);
  }
  // Evidence gate: a claim with no evidence does not render. The ledger
  // gate owns the error, so an evidence rejection is re-thrown as one.
  try {
    verifyClaim(claim.claim);
  } catch (err) {
    throw new LedgerGateError(`"${claim.id}" failed the evidence gate: ${(err as Error).message}`);
  }
  // Contradicted claims are shown, and must name what contradicts them.
  if (claim.state === "contradicted" && !claim.contradictedBy) {
    throw new LedgerGateError(
      `"${claim.id}" is contradicted but names nothing that contradicts it`,
    );
  }
  if (!claim.updatedAt || Number.isNaN(Date.parse(claim.updatedAt))) {
    throw new LedgerGateError(`"${claim.id}" has no valid updatedAt`);
  }
  return claim;
}

/** A claim renders only when it passes the ledger gate. */
export function canRender(claim: LedgerClaim): boolean {
  try {
    verifyLedgerClaim(claim);
    return true;
  } catch {
    return false;
  }
}

/**
 * The display label for a value. ACTUAL values render as measured.
 * ESTIMATED values always carry the word "estimated" so they are never
 * mistaken for a measurement.
 */
export function renderValueLabel(claim: LedgerClaim): string {
  verifyLedgerClaim(claim);
  return claim.valueLabel;
}

/** Verify every claim in a list. Throws on the first bad one. */
export function verifyAllLedgerClaims(claims: LedgerClaim[]): LedgerClaim[] {
  const seen = new Set<string>();
  for (const claim of claims) {
    if (seen.has(claim.id)) {
      throw new LedgerGateError(`duplicate claim id "${claim.id}"`);
    }
    seen.add(claim.id);
    verifyLedgerClaim(claim);
  }
  return claims;
}

/**
 * The real current claims. Every entry is a real measurement, a real
 * proposal, or an explicit zero. Nothing here is fabricated, projected,
 * or copied from another project's numbers.
 *
 * - EXP-1 is the real Experiment 1 (Slow-reply recovery), proposed, no
 *   seller agreed yet. Source: src/components/experiments/experiment-card.tsx.
 * - M6-H is the real capacity proof (1,000 tracks / 2,000 viewers).
 * - M7-H-TARGET is the real contradicted claim: the 9,000 / 10,000 target
 *   is NOT proven on one laptop (p99 fails). The M7-H park entry is what
 *   contradicts it.
 * - SFT-EVAL is the real held-out result: adapter 58 vs base 73.
 * - A6-KEYS is the real corrected scan: 0 private-key headers in 14,064 blobs.
 * - RS-0 is the real verified revenue: Rs 0. No seller has paid. The counter
 *   shows zero because zero is the measured number, not because it is hidden.
 */
export const CLAIMS: LedgerClaim[] = [
  {
    id: "EXP-1",
    title: "Slow-reply recovery",
    titleNe: "ढिलो जवाफ पुन:प्राप्ति",
    state: "proposed",
    primitive: "ACTION",
    claim: {
      statement:
        "Experiment 1 proposes to test whether faster replies recover real sales for one seller in one week. No seller has agreed yet, so it remains proposed and has not started.",
      evidenceClass: "observed",
      sources: [
        "src/components/experiments/experiment-card.tsx (EXP-1, status proposed, log empty)",
      ],
      confidence: "high",
      weakestLink:
        "A proposal is not a result. Until a seller agrees and a week runs, nothing about recovery is known.",
    },
    valueKind: "ACTUAL",
    valueLabel: "0 sellers agreed, 0 sales recovered (measured)",
    updatedAt: "2026-11-18",
  },
  {
    id: "M6-H",
    title: "Own media engine passes M6-H",
    titleNe: "आफ्नै मिडिया इन्जिन",
    state: "completed",
    primitive: "CAPABILITY",
    claim: {
      statement:
        "Hami's own media engine passed M6-H on one MacBook: 1,000 tracks, 2,000 viewers, p95 0.34 ms, p99 17.8 ms, zero drops, zero errors.",
      evidenceClass: "observed",
      sources: [
        "hami-reports/2026-11-17-m6-h-proof-report.md",
        "hami-reports/2026-11-17-m6-h-proof.md",
      ],
      confidence: "high",
      weakestLink:
        "Receive latency, not capture-to-render. A proof on one laptop, not a production deployment.",
    },
    valueKind: "ACTUAL",
    valueLabel: "p95 0.34 ms, p99 17.8 ms (measured, 2,000 viewers)",
    updatedAt: "2026-11-17",
  },
  {
    id: "M7-H-TARGET",
    title: "9,000 streamers / 10,000 viewers in one room",
    titleNe: "९,००० स्ट्रिमर / १०,००० दर्शक",
    state: "contradicted",
    primitive: "CAPABILITY",
    claim: {
      statement:
        "The target of 9,000 streamers watched by 10,000 viewers in one room on one laptop is not proven. M7-H parked: p95 passes all 3,000 viewers (11.2 ms median) but p99 fails (~294 ms median, 115 of 3,000 pass).",
      evidenceClass: "observed",
      sources: [
        "docs/CAPABILITY_QUEUE.md (M7-H park entry)",
        "/tmp/m7h-attempt12-r3-latency-analysis.txt",
      ],
      confidence: "high",
      weakestLink:
        "The p99 tail clusters at +25 s and +40 s; the periodic cause is not yet identified.",
    },
    valueKind: "ACTUAL",
    valueLabel: "p99 115 of 3,000 pass (measured, target not met)",
    contradictedBy: "M7-H park entry (p99 fails, 115/3,000)",
    updatedAt: "2026-11-18",
  },
  {
    id: "SFT-EVAL",
    title: "Nepali SFT adapter vs base",
    titleNe: "नेपाली एसएफटी मूल्याङ्कन",
    state: "completed",
    primitive: "EVIDENCE",
    claim: {
      statement:
        "The 500-example Nepali SFT adapter loses to the base model on held-out rows: base 73/120 vs adapter 58/120 on 20 rows (4 adapter wins, 9 base wins, 7 ties).",
      evidenceClass: "observed",
      sources: ["/tmp/hami-sft-heldout-eval.ifDVJb/ (held-out scores, run 16:30-16:34 +0545)"],
      confidence: "medium",
      weakestLink:
        "Model-assisted scoring by the same base model, 20 examples only. Data quality is the suspected bottleneck.",
    },
    valueKind: "ACTUAL",
    valueLabel: "base 73/120 vs adapter 58/120 (measured, 20 rows)",
    updatedAt: "2026-11-18",
  },
  {
    id: "A6-KEYS",
    title: "No private-key headers in history",
    titleNe: "इतिहासमा निजी कुञ्जी छैन",
    state: "completed",
    primitive: "EVIDENCE",
    claim: {
      statement:
        "A full-history scan of 14,064 blobs (2,148,503,946 bytes) found zero private-key headers for the specified marker set (RSA/EC/DSA/OpenSSH/PKCS#8/PGP/PuTTY/base64). A6 stays TESTED, NOT CLEAN.",
      evidenceClass: "observed",
      sources: [
        "/tmp/forgeos-a6-credential-audit-20261118T1014Z/evidence/private-key-header-scan-20261118T110954Z-summary.txt",
      ],
      confidence: "high",
      weakestLink:
        "Marker set only. No arbitrary DER/JWK parsing. 103 Gitleaks and 129 TruffleHog candidates still need triage.",
    },
    valueKind: "ACTUAL",
    valueLabel: "0 matches in 14,064 blobs (measured)",
    updatedAt: "2026-11-18",
  },
  {
    id: "RS-0",
    title: "Verified rupees earned",
    titleNe: "प्रमाणित आम्दानी",
    state: "completed",
    primitive: "EVENT",
    claim: {
      statement:
        "Verified real rupees earned by Hami so far: Rs 0. No seller has paid, no pilot has run, no revenue has been received. Zero is the measured number.",
      evidenceClass: "observed",
      sources: [
        "income research (your_files/income-now-and-better-approach.md): no verified revenue",
        "Hamsawears questionnaire sent 18 Nov 12:13, no reply yet",
      ],
      confidence: "high",
      weakestLink:
        "Revenue is zero today. The counter moves only when a real payment lands and is verified.",
    },
    valueKind: "ACTUAL",
    valueLabel: "Rs 0 verified",
    updatedAt: "2026-11-18",
  },
];

/** Only the claims that pass the gate. Everything else stays internal. */
export function publicClaims(): LedgerClaim[] {
  return verifyAllLedgerClaims(CLAIMS).filter((claim) => canRender(claim));
}

/** The latest state change across the public claims, for the home strip. */
export function latestStateChange(): LedgerClaim | undefined {
  const claims = publicClaims();
  return claims.reduce<LedgerClaim | undefined>((latest, claim) => {
    if (!latest) return claim;
    return Date.parse(claim.updatedAt) >= Date.parse(latest.updatedAt)
      ? claim
      : latest;
  }, undefined);
}
