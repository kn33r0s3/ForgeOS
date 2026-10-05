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
