import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  classAtLeast,
  EvidenceGateError,
  verifyAll,
  verifyClaim,
  type Claim,
} from "./evidence.ts";
import { discoveryUnknowns, unknownsCount } from "./unknowns.ts";

const good: Claim = {
  statement: "Merchant QR apps show a 2.73/5 rating across ~1,900 reviews.",
  evidenceClass: "observed",
  sources: ["AppBrain FoneBiz page (2026 snapshot)"],
  confidence: "high",
  weakestLink: "Ratings snapshot is dated; the score may have moved since.",
};

describe("evidence gate", () => {
  it("passes a fully-specified claim", () => {
    assert.deepEqual(verifyClaim({ ...good }), good);
  });

  it("rejects a claim with no sources", () => {
    assert.throws(() => verifyClaim({ ...good, sources: [] }), EvidenceGateError);
  });

  it("rejects a claim with no confidence grade", () => {
    assert.throws(
      () => verifyClaim({ ...good, confidence: undefined as never }),
      EvidenceGateError,
    );
  });

  it("rejects a claim with no weakest link", () => {
    assert.throws(
      () => verifyClaim({ ...good, weakestLink: "fine" }),
      EvidenceGateError,
    );
  });

  it("rejects a thin statement", () => {
    assert.throws(
      () => verifyClaim({ ...good, statement: "shops" }),
      EvidenceGateError,
    );
  });

  it("rejects high confidence on rumor-grade evidence", () => {
    assert.throws(
      () =>
        verifyClaim({
          ...good,
          evidenceClass: "reported",
          confidence: "high",
          weakestLink: "single-source press report, uncorroborated",
        }),
      EvidenceGateError,
    );
  });

  it("requires reported claims to name the rumor risk", () => {
    assert.throws(
      () =>
        verifyClaim({
          ...good,
          evidenceClass: "reported",
          confidence: "medium",
          weakestLink: "looks solid to me",
        }),
      EvidenceGateError,
    );
    // ...but passes when the risk is named.
    verifyClaim({
      ...good,
      evidenceClass: "reported",
      confidence: "medium",
      weakestLink: "single-source founder claim via one outlet, uncorroborated",
    });
  });

  it("orders evidence classes strongest-first", () => {
    assert.equal(classAtLeast("actual", "observed"), true);
    assert.equal(classAtLeast("observed", "observed"), true);
    assert.equal(classAtLeast("reported", "observed"), false);
    assert.equal(classAtLeast("unknown", "actual"), false);
  });

  it("fails the whole batch on one bad claim", () => {
    assert.throws(
      () => verifyAll([good, { ...good, sources: [] }]),
      EvidenceGateError,
    );
    assert.equal(verifyAll([good, good]).length, 2);
  });
});

describe("unknowns fuel inventory", () => {
  it("holds all 49 discovery unknowns with valid shape", () => {
    assert.equal(discoveryUnknowns.length, 49);
    assert.equal(unknownsCount, 49);
    const ids = new Set(discoveryUnknowns.map((u) => u.id));
    assert.equal(ids.size, 49);
    for (const u of discoveryUnknowns) {
      assert.match(u.id, /^D\d+$/);
      assert.ok(u.question.length > 20, `${u.id}: question too thin`);
      assert.ok(["unknown", "supported", "hypothesized"].includes(u.state));
      assert.ok(u.stakes.length > 10, `${u.id}: no stakes recorded`);
      assert.ok(u.round >= 1 && u.round <= 10, `${u.id}: bad round`);
    }
  });

  it("gives every open unknown a cheapest legitimate test", () => {
    const open = discoveryUnknowns.filter((u) => u.state === "unknown");
    assert.ok(open.length > 40, "the fuel inventory should stay mostly open");
    for (const u of open) {
      assert.ok(
        u.cheapestTest.length > 10,
        `${u.id}: open unknown with no cheapest test`,
      );
    }
  });

  it("keeps answered unknowns answered", () => {
    const answered = discoveryUnknowns.filter((u) => u.state !== "unknown");
    assert.ok(answered.length >= 1);
    for (const u of answered) {
      assert.ok(
        /SUPPORTED|HYPOTHESIZED/.test(u.stateNote),
        `${u.id}: state note doesn't carry the evidence`,
      );
    }
  });
});
