// Pure helpers for the /prototype/inbox sprint-week prototype.
// Kept side-effect free so they can be unit tested; the route owns localStorage.

export type Outcome = "open" | "recovered" | "lost" | "browsing";

export interface Inquiry {
  id: string;
  timeIn: number;
  customer: string;
  want: string;
  replyAt: number | null;
  outcome: Outcome;
  orderValue: number | null;
}

/**
 * Parse a free-typed rupee amount from window.prompt.
 * Keeps digits and a decimal point; commas/currency symbols are stripped.
 * If several dots survive (e.g. the "Rs." prefix), the LAST one is the decimal
 * separator and earlier ones are punctuation noise — this avoids the old
 * inline version's bug of stripping the decimal point too ("1500.50"→150050).
 * Anything still unparseable becomes 0.
 */
export function parseOrderValue(raw: string): number {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const normalized =
    parts.length <= 2 ? cleaned : parts.slice(0, -1).join("") + "." + parts[parts.length - 1];
  const n = Number(normalized);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Shape guard for inquiry records read back from localStorage. Stored data
 * from an older build — or hand-edited storage — must not crash the page with
 * "Invalid Date" / "NaNh NaNm" rows.
 */
export function isInquiry(x: unknown): x is Inquiry {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o.id === "string" &&
    typeof o.timeIn === "number" &&
    Number.isFinite(o.timeIn) &&
    typeof o.customer === "string" &&
    typeof o.want === "string" &&
    (o.replyAt === null ||
      (typeof o.replyAt === "number" && Number.isFinite(o.replyAt))) &&
    (o.outcome === "open" ||
      o.outcome === "recovered" ||
      o.outcome === "lost" ||
      o.outcome === "browsing") &&
    (o.orderValue === null ||
      (typeof o.orderValue === "number" && Number.isFinite(o.orderValue)))
  );
}

// ---------------------------------------------------------------------------
// Verified-commitment log (First Rupee Sprint, mission item 4).
//
// One entry per stage of a single commitment: inquiry → order → payment →
// delivery → outcome. This is the six-primitive shape in miniature: the
// seller is an ENTITY (pseudonymous ref only — never a name, phone, or
// handle a customer could be identified by), each entry is an EVENT, and
// `evidenceRef` points at the EVIDENCE held outside this browser (an owner
// note, a screenshot kept by the owner, a REVENUE_LOG row). Money starts
// as REPORTED and may only be marked VERIFIED when an evidence reference
// exists AND the seller consented to the record — the same rule
// docs/REVENUE_LOG.md applies. The guard below enforces that invariant on
// every read, so hand-edited storage cannot smuggle in a "verified" rupee.
// ---------------------------------------------------------------------------

export type CommitmentStage = "inquiry" | "order" | "payment" | "delivery" | "outcome";

export type Verification = "reported" | "verified";

export interface CommitmentEntry {
  id: string;
  /** Pseudonymous seller reference (e.g. "seller-01"). Never contact data. */
  sellerRef: string;
  stage: CommitmentStage;
  at: number;
  /** Rupee amount for this stage, when the stage carries one. */
  amount: number | null;
  verification: Verification;
  /** Non-secret pointer to evidence held by the owner. Required for VERIFIED. */
  evidenceRef: string;
  /** True only when the seller consented to this record being kept. */
  sellerConsent: boolean;
  /** Only meaningful on the outcome stage: did this sale recover? */
  recovered: boolean | null;
  note: string;
}

const COMMITMENT_STAGES: readonly string[] = ["inquiry", "order", "payment", "delivery", "outcome"];

/**
 * Shape + invariant guard for commitment entries read back from storage.
 * VERIFIED requires an evidence reference and seller consent; a recovered
 * flag is only valid on the outcome stage.
 */
export function isCommitmentEntry(x: unknown): x is CommitmentEntry {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  if (
    typeof o.id !== "string" ||
    typeof o.sellerRef !== "string" ||
    typeof o.stage !== "string" ||
    !COMMITMENT_STAGES.includes(o.stage) ||
    typeof o.at !== "number" ||
    !Number.isFinite(o.at) ||
    !(o.amount === null || (typeof o.amount === "number" && Number.isFinite(o.amount))) ||
    !(o.verification === "reported" || o.verification === "verified") ||
    typeof o.evidenceRef !== "string" ||
    typeof o.sellerConsent !== "boolean" ||
    !(o.recovered === null || typeof o.recovered === "boolean") ||
    typeof o.note !== "string"
  ) {
    return false;
  }
  if (o.verification === "verified" && (o.evidenceRef.trim() === "" || o.sellerConsent !== true)) {
    return false;
  }
  if (o.recovered !== null && o.stage !== "outcome") {
    return false;
  }
  return true;
}

export interface CommitmentSummary {
  entries: number;
  inquiries: number;
  orders: number;
  payments: number;
  deliveries: number;
  outcomes: number;
  /** Outcome entries marked recovered AND verified — the only count the
   *  scoreboard may call recovered sales. */
  recoveredSales: number;
  /** Sum of payment-stage amounts still at REPORTED. */
  rupeesReported: number;
  /** Sum of payment-stage amounts at VERIFIED (evidence + consent). */
  rupeesVerified: number;
}

/**
 * Aggregate a commitment log for the scoreboard. Reported money and
 * verified money are summed separately and never merged; an outcome only
 * counts as a recovered sale when it is verified.
 */
export function summarizeCommitments(entries: CommitmentEntry[]): CommitmentSummary {
  const s: CommitmentSummary = {
    entries: entries.length,
    inquiries: 0,
    orders: 0,
    payments: 0,
    deliveries: 0,
    outcomes: 0,
    recoveredSales: 0,
    rupeesReported: 0,
    rupeesVerified: 0,
  };
  for (const e of entries) {
    if (e.stage === "inquiry") s.inquiries += 1;
    if (e.stage === "order") s.orders += 1;
    if (e.stage === "delivery") s.deliveries += 1;
    if (e.stage === "payment") {
      s.payments += 1;
      if (e.amount !== null) {
        if (e.verification === "verified") s.rupeesVerified += e.amount;
        else s.rupeesReported += e.amount;
      }
    }
    if (e.stage === "outcome") {
      s.outcomes += 1;
      if (e.recovered === true && e.verification === "verified") s.recoveredSales += 1;
    }
  }
  return s;
}
