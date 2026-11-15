import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  formatDuration,
  isInquiry,
  normalizeInquiry,
  parseOrderValue,
  summarizeWeek,
  weekSummaryText,
  type Inquiry,
} from "./prototype-inbox.ts";

const NOW = Date.UTC(2026, 10, 15, 12, 0, 0);
const inquiry: Inquiry = {
  id: "week-1",
  timeIn: NOW - 60 * 60 * 1000,
  customer: "Local browser name",
  channel: "facebook",
  want: "Product question",
  replyAt: null,
  outcome: "open",
  orderValue: null,
};

describe("parseOrderValue", () => {
  it("keeps decimal amounts and strips currency punctuation", () => {
    assert.equal(parseOrderValue("Rs. 2,250.75"), 2250.75);
    assert.equal(parseOrderValue("free"), 0);
  });
});

describe("inquiry browser records", () => {
  it("accepts a current record with a supported channel", () => {
    assert.equal(isInquiry(inquiry), true);
  });

  it("rejects a record with an unsupported channel", () => {
    assert.equal(isInquiry({ ...inquiry, channel: "messenger-bot" }), false);
  });

  it("upgrades a prior local record without a channel to other", () => {
    const { channel, ...legacy } = inquiry;
    void channel;
    assert.deepEqual(normalizeInquiry(legacy), { ...inquiry, channel: "other" });
  });

  it("drops malformed browser storage rather than throwing", () => {
    assert.equal(normalizeInquiry({ ...inquiry, timeIn: "today" }), null);
  });
});

describe("weekly seller summary", () => {
  it("counts only the last seven days and keeps outcomes distinct", () => {
    const summary = summarizeWeek([
      { ...inquiry, id: "recovered", replyAt: NOW - 30 * 60 * 1000, outcome: "recovered", orderValue: 1250 },
      { ...inquiry, id: "lost", timeIn: NOW - 2 * 60 * 60 * 1000, replyAt: NOW - 90 * 60 * 1000, outcome: "lost" },
      { ...inquiry, id: "old", timeIn: NOW - 8 * 24 * 60 * 60 * 1000, outcome: "recovered", orderValue: 9999 },
    ], NOW);
    assert.deepEqual(summary, { inquiries: 2, averageReplyMs: 30 * 60 * 1000, recoveredSalesNpr: 1250, lost: 1 });
  });

  it("reports no average until a reply exists", () => {
    assert.equal(summarizeWeek([inquiry], NOW).averageReplyMs, null);
  });

  it("exports aggregates only, in English and Devanagari Nepali", () => {
    const summary = summarizeWeek([{ ...inquiry, outcome: "recovered", orderValue: 500 }], NOW);
    const english = weekSummaryText(summary, "en", NOW);
    const nepali = weekSummaryText(summary, "ne", NOW);
    assert.match(english, /Recovered sales: NPR 500/);
    assert.match(nepali, /साप्ताहिक सोधपुछ सारांश/);
    assert.doesNotMatch(english, /Local browser name|Product question/);
    assert.doesNotMatch(nepali, /Local browser name|Product question/);
  });
});

describe("duration labels", () => {
  it("renders compact English and Devanagari labels", () => {
    assert.equal(formatDuration(30_000, "en"), "<1 min");
    assert.equal(formatDuration(30_000, "ne"), "१ मिनेटभन्दा कम");
  });
});
