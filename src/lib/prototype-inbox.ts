// Browser-only helpers for the /prototype/inbox sprint-week prototype.
// The route owns localStorage and downloads; this module never performs I/O.

export type Outcome = "open" | "recovered" | "lost" | "browsing";
export type Channel = "facebook" | "instagram" | "tiktok" | "whatsapp" | "other";

export interface Inquiry {
  id: string;
  timeIn: number;
  customer: string;
  channel: Channel;
  want: string;
  replyAt: number | null;
  outcome: Outcome;
  orderValue: number | null;
}

export interface WeekSummary {
  inquiries: number;
  averageReplyMs: number | null;
  recoveredSalesNpr: number;
  lost: number;
}

const CHANNELS: readonly Channel[] = ["facebook", "instagram", "tiktok", "whatsapp", "other"];
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

/** Parse a free-typed NPR amount without producing NaN. */
export function parseOrderValue(raw: string): number {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const normalized =
    parts.length <= 2 ? cleaned : parts.slice(0, -1).join("") + "." + parts[parts.length - 1];
  const value = Number(normalized);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

/** Validate current records before saving or using them in a summary. */
export function isInquiry(value: unknown): value is Inquiry {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "string" &&
    typeof item.timeIn === "number" && Number.isFinite(item.timeIn) &&
    typeof item.customer === "string" &&
    typeof item.want === "string" &&
    typeof item.channel === "string" && CHANNELS.includes(item.channel as Channel) &&
    (item.replyAt === null || (typeof item.replyAt === "number" && Number.isFinite(item.replyAt))) &&
    (item.outcome === "open" || item.outcome === "recovered" || item.outcome === "lost" || item.outcome === "browsing") &&
    (item.orderValue === null || (typeof item.orderValue === "number" && Number.isFinite(item.orderValue)))
  );
}

/** Preserve pre-channel local records by assigning the explicit "other" channel. */
export function normalizeInquiry(value: unknown): Inquiry | null {
  if (typeof value !== "object" || value === null) return null;
  const item = value as Record<string, unknown>;
  const normalized = { ...item, channel: item.channel ?? "other" };
  return isInquiry(normalized) ? normalized : null;
}

export function summarizeWeek(inquiries: Inquiry[], now = Date.now()): WeekSummary {
  const start = now - WEEK_MS;
  const week = inquiries.filter((item) => item.timeIn >= start && item.timeIn <= now);
  const replied = week.filter((item) => item.replyAt !== null);
  const averageReplyMs = replied.length
    ? replied.reduce((total, item) => total + Math.max(0, item.replyAt! - item.timeIn), 0) / replied.length
    : null;
  return {
    inquiries: week.length,
    averageReplyMs,
    recoveredSalesNpr: week.reduce(
      (total, item) => total + (item.outcome === "recovered" ? item.orderValue ?? 0 : 0),
      0,
    ),
    lost: week.filter((item) => item.outcome === "lost").length,
  };
}

export function formatDuration(milliseconds: number, language: "en" | "ne"): string {
  const minutes = Math.max(0, Math.floor(milliseconds / 60000));
  if (language === "ne") {
    if (minutes < 1) return "१ मिनेटभन्दा कम";
    if (minutes < 60) return `${minutes} मिनेट`;
    return `${Math.floor(minutes / 60)} घण्टा ${minutes % 60} मिनेट`;
  }
  if (minutes < 1) return "<1 min";
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

/** A privacy-safe export: aggregate week metrics only, never names or inquiry text. */
export function weekSummaryText(summary: WeekSummary, language: "en" | "ne", now = Date.now()): string {
  const date = new Date(now).toLocaleDateString(language === "ne" ? "ne-NP" : "en-NP");
  if (language === "ne") {
    return [
      "Hami — साप्ताहिक सोधपुछ सारांश",
      `मिति: ${date}`,
      `सोधपुछ प्राप्त: ${summary.inquiries}`,
      `औसत जवाफ समय: ${summary.averageReplyMs === null ? "—" : formatDuration(summary.averageReplyMs, "ne")}`,
      `पुनः प्राप्त बिक्री: रु ${summary.recoveredSalesNpr.toLocaleString("en-NP")}`,
      `हराएका: ${summary.lost}`,
      "यो फाइलमा ग्राहकको नाम, सन्देश वा सम्पर्क विवरण छैन।",
    ].join("\n");
  }
  return [
    "Hami — Weekly inquiry summary",
    `Date: ${date}`,
    `Inquiries received: ${summary.inquiries}`,
    `Average reply time: ${summary.averageReplyMs === null ? "—" : formatDuration(summary.averageReplyMs, "en")}`,
    `Recovered sales: NPR ${summary.recoveredSalesNpr.toLocaleString("en-NP")}`,
    `Lost: ${summary.lost}`,
    "This export contains no customer names, messages, or contact details.",
  ].join("\n");
}
