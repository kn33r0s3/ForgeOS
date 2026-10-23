import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isCommitmentEntry,
  isInquiry,
  parseOrderValue,
  summarizeCommitments,
  type CommitmentEntry,
} from "./prototype-inbox.ts";

describe("parseOrderValue", () => {
  it("keeps decimal amounts intact", () => {
    assert.equal(parseOrderValue("1500.50"), 1500.5);
  });

  it("strips commas and currency symbols", () => {
    assert.equal(parseOrderValue("₨1,500"), 1500);
    assert.equal(parseOrderValue("Rs. 2,250.75"), 2250.75);
  });

  it("plain integers parse as-is", () => {
    assert.equal(parseOrderValue("500"), 500);
  });

  it("empty or garbage input becomes 0, never NaN", () => {
    assert.equal(parseOrderValue(""), 0);
    assert.equal(parseOrderValue(".."), 0);
    assert.equal(parseOrderValue("free"), 0);
  });

  it("multiple dots: last one wins as the decimal separator", () => {
    assert.equal(parseOrderValue("1.2.3"), 12.3);
  });
});

describe("isInquiry", () => {
  const good = {
    id: "1728000000000-abc12",
    timeIn: 1728000000000,
    customer: "Sita",
    want: "red kurta, size M",
    replyAt: null,
    outcome: "open",
    orderValue: null,
  };

  it("accepts a well-formed inquiry", () => {
    assert.equal(isInquiry(good), true);
  });

  it("accepts replied and recovered shapes", () => {
    assert.equal(
      isInquiry({ ...good, replyAt: 1728000060000, outcome: "recovered", orderValue: 250 }),
      true,
    );
  });

  it("rejects non-objects", () => {
    assert.equal(isInquiry(null), false);
    assert.equal(isInquiry("inquiry"), false);
    assert.equal(isInquiry(42), false);
    assert.equal(isInquiry(undefined), false);
  });

  it("rejects wrong field types", () => {
    assert.equal(isInquiry({ ...good, timeIn: "yesterday" }), false);
    assert.equal(isInquiry({ ...good, replyAt: "fast" }), false);
    assert.equal(isInquiry({ ...good, orderValue: "lots" }), false);
  });

  it("rejects unknown outcomes", () => {
    assert.equal(isInquiry({ ...good, outcome: "maybe" }), false);
  });

  it("rejects missing required fields", () => {
    const { want, ...rest } = good;
    void want;
    assert.equal(isInquiry(rest), false);
  });
});

describe("isCommitmentEntry", () => {
  const good: CommitmentEntry = {
    id: "1728000000000-cmt01",
    sellerRef: "seller-01",
    stage: "inquiry",
    at: 1728000000000,
    amount: null,
    verification: "reported",
    evidenceRef: "",
    sellerConsent: false,
    recovered: null,
    note: "Seller reported 12 inquiries on day 1.",
  };

  it("accepts a well-formed reported entry", () => {
    assert.equal(isCommitmentEntry(good), true);
  });

  it("accepts a verified entry with evidence and consent", () => {
    assert.equal(
      isCommitmentEntry({
        ...good,
        stage: "payment",
        amount: 2500,
        verification: "verified",
        evidenceRef: "owner-note-2026-10-24",
        sellerConsent: true,
      }),
      true,
    );
  });

  it("rejects a verified entry without an evidence reference", () => {
    assert.equal(
      isCommitmentEntry({ ...good, verification: "verified", sellerConsent: true }),
      false,
    );
  });

  it("rejects a verified entry without seller consent", () => {
    assert.equal(
      isCommitmentEntry({ ...good, verification: "verified", evidenceRef: "ref-1" }),
      false,
    );
  });

  it("rejects non-objects and wrong field types", () => {
    assert.equal(isCommitmentEntry(null), false);
    assert.equal(isCommitmentEntry("entry"), false);
    assert.equal(isCommitmentEntry({ ...good, at: "today" }), false);
    assert.equal(isCommitmentEntry({ ...good, amount: "lots" }), false);
    assert.equal(isCommitmentEntry({ ...good, sellerConsent: "yes" }), false);
  });

  it("rejects unknown stages and verification states", () => {
    assert.equal(isCommitmentEntry({ ...good, stage: "shipped" }), false);
    assert.equal(isCommitmentEntry({ ...good, verification: "proven" }), false);
  });

  it("rejects a recovered flag on a non-outcome stage", () => {
    assert.equal(isCommitmentEntry({ ...good, recovered: true }), false);
    assert.equal(
      isCommitmentEntry({ ...good, stage: "outcome", recovered: false }),
      true,
    );
  });
});

describe("summarizeCommitments", () => {
  const base: CommitmentEntry = {
    id: "x",
    sellerRef: "seller-01",
    stage: "inquiry",
    at: 1728000000000,
    amount: null,
    verification: "reported",
    evidenceRef: "",
    sellerConsent: false,
    recovered: null,
    note: "",
  };

  it("empty log summarizes to honest zeros", () => {
    const s = summarizeCommitments([]);
    assert.equal(s.entries, 0);
    assert.equal(s.inquiries, 0);
    assert.equal(s.orders, 0);
    assert.equal(s.recoveredSales, 0);
    assert.equal(s.rupeesReported, 0);
    assert.equal(s.rupeesVerified, 0);
  });

  it("reported money never counts as verified", () => {
    const s = summarizeCommitments([
      { ...base, id: "1", stage: "payment", amount: 3000 },
      {
        ...base,
        id: "2",
        stage: "payment",
        amount: 1500,
        verification: "verified",
        evidenceRef: "ref-2",
        sellerConsent: true,
      },
    ]);
    assert.equal(s.rupeesReported, 3000);
    assert.equal(s.rupeesVerified, 1500);
  });

  it("counts stages and recovered outcomes; unverified outcomes do not count as recovered sales", () => {
    const s = summarizeCommitments([
      { ...base, id: "1", stage: "inquiry" },
      { ...base, id: "2", stage: "inquiry" },
      { ...base, id: "3", stage: "order", amount: 900 },
      { ...base, id: "4", stage: "outcome", recovered: true },
      {
        ...base,
        id: "5",
        stage: "outcome",
        recovered: true,
        verification: "verified",
        evidenceRef: "ref-5",
        sellerConsent: true,
      },
      { ...base, id: "6", stage: "outcome", recovered: false },
    ]);
    assert.equal(s.inquiries, 2);
    assert.equal(s.orders, 1);
    assert.equal(s.recoveredSales, 1);
  });
});
