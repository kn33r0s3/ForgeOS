import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isAngleTried,
  ripenessQueue,
  verifyRound,
  type RoundFinding,
} from "./assistant.ts";
import { triedAnglesCount } from "./tried-angles.ts";

const goodFinding: RoundFinding = {
  statement: "COD couriers settle cash to sellers on a T+0 to 2-day float.",
  evidenceClass: "observed",
  sources: ["Nepali courier press coverage", "Pathao COD terms"],
  confidence: "medium",
  weakestLink: "Settlement terms are press-reported; no seller ledger checked.",
  unknownIds: ["D60"],
};

describe("forge assistant — verifyRound", () => {
  it("passes a fully-gated finding", () => {
    const verdict = verifyRound([goodFinding]);
    assert.equal(verdict.verified.length, 1);
    assert.equal(verdict.rejected.length, 0);
  });

  it("rejects a finding with no weakest link and names the reason", () => {
    const verdict = verifyRound([{ ...goodFinding, weakestLink: "" }]);
    assert.equal(verdict.verified.length, 0);
    assert.equal(verdict.rejected.length, 1);
    assert.match(verdict.rejected[0].reason, /weakest link/i);
  });

  it("rejects a finding that addresses no unknown", () => {
    const verdict = verifyRound([{ ...goodFinding, unknownIds: [] }]);
    assert.equal(verdict.rejected.length, 1);
    assert.match(verdict.rejected[0].reason, /no unknown/i);
  });

  it("banks only the verified findings", () => {
    const verdict = verifyRound([
      goodFinding,
      { ...goodFinding, sources: [] },
    ]);
    assert.equal(verdict.verified.length, 1);
    assert.equal(verdict.rejected.length, 1);
  });

  it("handles an empty round", () => {
    const verdict = verifyRound([]);
    assert.deepEqual(verdict, { verified: [], rejected: [] });
  });
});

describe("forge assistant — ripenessQueue", () => {
  it("returns only open unknowns with tests attached", () => {
    const queue = ripenessQueue(50);
    assert.ok(queue.length > 40);
    for (const item of queue) {
      assert.ok(item.id.startsWith("D"));
      assert.ok(item.question.length > 20);
      assert.ok(item.cheapestTest.length > 10, `${item.id}: no cheapest test`);
      assert.ok(item.stakes.length > 10);
    }
  });

  it("ranks by value tier first, then doability, then age", () => {
    const queue = ripenessQueue(64);
    for (let k = 1; k < queue.length; k++) {
      const prev = queue[k - 1];
      const cur = queue[k];
      assert.ok(
        cur.valueTier <= prev.valueTier,
        `${cur.id} (tier ${cur.valueTier}) before ${prev.id} (tier ${prev.valueTier})`,
      );
      if (cur.valueTier === prev.valueTier) {
        const order = (r: string) => (r === "now" ? 0 : 1);
        assert.ok(order(cur.ripeness) >= order(prev.ripeness));
        if (cur.ripeness === prev.ripeness) {
          assert.ok(cur.round >= prev.round);
        }
      }
    }
  });

  it("every open unknown carries a value tier and a reason", () => {
    const queue = ripenessQueue(64);
    for (const item of queue) {
      assert.ok([1, 2, 3].includes(item.valueTier), `${item.id}: no tier`);
      assert.ok(item.valueWhy.length > 10, `${item.id}: no value reason`);
    }
  });

  it("money-close unknowns lead the queue", () => {
    const queue = ripenessQueue(10);
    assert.ok(
      queue.every((i) => i.valueTier === 3),
      `top 10 should all be tier 3, got ${queue.map((i) => `${i.id}:t${i.valueTier}`).join(", ")}`,
    );
  });

  it("respects the limit", () => {
    assert.equal(ripenessQueue(5).length, 5);
  });
});

describe("forge assistant — isAngleTried", () => {
  it("recognizes tried angles", () => {
    assert.equal(triedAnglesCount >= 13, true);
    assert.equal(isAngleTried("the COD courier and cash on delivery"), true);
    assert.equal(isAngleTried("what killed the Tootle ride-hailing startup"), true);
  });

  it("passes genuinely new angles", () => {
    assert.equal(isAngleTried("lunar masonry techniques in Mustang"), false);
    assert.equal(isAngleTried(""), false);
  });
});
