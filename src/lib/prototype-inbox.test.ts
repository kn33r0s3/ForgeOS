import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { isInquiry, parseOrderValue } from "./prototype-inbox.ts";

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
