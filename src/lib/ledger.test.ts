import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CLAIMS,
  LedgerGateError,
  canRender,
  latestStateChange,
  publicClaims,
  renderValueLabel,
  verifyAllLedgerClaims,
  verifyLedgerClaim,
  type LedgerClaim,
} from "./ledger.ts";

const good: LedgerClaim = {
  id: "TEST-1",
  title: "A real measured thing",
  titleNe: "वास्तविक मापन",
  state: "completed",
  primitive: "CAPABILITY",
  claim: {
    statement: "A real measurement with a named source and a weakest link.",
    evidenceClass: "observed",
    sources: ["a real run log"],
    confidence: "high",
    weakestLink: "The measurement covers one run only.",
  },
  valueKind: "ACTUAL",
  valueLabel: "42 measured",
  updatedAt: "2026-11-18",
};

describe("ledger gate", () => {
  it("passes a fully-specified claim", () => {
    assert.deepEqual(verifyLedgerClaim({ ...good }), good);
  });

  it("rejects a claim with no state", () => {
    assert.throws(
      () => verifyLedgerClaim({ ...good, state: undefined as never }),
      LedgerGateError,
    );
  });

  it("rejects a claim with no evidence", () => {
    assert.throws(
      () =>
        verifyLedgerClaim({
          ...good,
          claim: { ...good.claim, sources: [] },
        }),
      LedgerGateError,
    );
  });

  it("rejects a claim that is not one of the six primitives", () => {
    assert.throws(
      () =>
        verifyLedgerClaim({
          ...good,
          primitive: "WIDGET" as never,
        }),
      LedgerGateError,
    );
  });

  it("rejects ESTIMATED shown as ACTUAL", () => {
    assert.throws(
      () =>
        verifyLedgerClaim({
          ...good,
          claim: { ...good.claim, evidenceClass: "estimated" },
          valueKind: "ACTUAL",
        }),
      LedgerGateError,
    );
  });

  it("rejects an ESTIMATED value whose label does not say estimated", () => {
    assert.throws(
      () =>
        verifyLedgerClaim({
          ...good,
          claim: { ...good.claim, evidenceClass: "estimated" },
          valueKind: "ESTIMATED",
          valueLabel: "Rs 50,000",
        }),
      LedgerGateError,
    );
  });

  it("accepts an ESTIMATED value that says estimated", () => {
    assert.deepEqual(
      verifyLedgerClaim({
        ...good,
        claim: { ...good.claim, evidenceClass: "estimated", confidence: "medium" },
        valueKind: "ESTIMATED",
        valueLabel: "Rs 50,000 estimated",
      }).valueKind,
      "ESTIMATED",
    );
  });

  it("rejects a contradicted claim that names nothing", () => {
    assert.throws(
      () =>
        verifyLedgerClaim({ ...good, state: "contradicted" }),
      LedgerGateError,
    );
  });

  it("accepts a contradicted claim that names its contradiction", () => {
    assert.deepEqual(
      verifyLedgerClaim({
        ...good,
        state: "contradicted",
        contradictedBy: "the run that disproved it",
      }).state,
      "contradicted",
    );
  });

  it("rejects a claim with no Devanagari heading", () => {
    assert.throws(
      () => verifyLedgerClaim({ ...good, titleNe: "" }),
      LedgerGateError,
    );
  });

  it("canRender is false for a claim that fails the gate", () => {
    assert.equal(canRender({ ...good, state: undefined as never }), false);
    assert.equal(canRender({ ...good }), true);
  });

  it("renderValueLabel returns the label for a good claim", () => {
    assert.equal(renderValueLabel({ ...good }), "42 measured");
  });

  it("rejects duplicate claim ids", () => {
    assert.throws(
      () => verifyAllLedgerClaims([{ ...good }, { ...good }]),
      LedgerGateError,
    );
  });
});

describe("public claims data", () => {
  it("every shipped claim passes the gate", () => {
    assert.deepEqual(verifyAllLedgerClaims(CLAIMS), CLAIMS);
  });

  it("every shipped claim renders", () => {
    for (const claim of CLAIMS) {
      assert.equal(canRender(claim), true, claim.id);
    }
  });

  it("includes Experiment 1 as proposed", () => {
    const exp1 = CLAIMS.find((claim) => claim.id === "EXP-1");
    assert.ok(exp1, "EXP-1 is in the ledger");
    assert.equal(exp1.state, "proposed");
  });

  it("shows a contradicted claim", () => {
    const contradicted = CLAIMS.filter((claim) => claim.state === "contradicted");
    assert.ok(contradicted.length >= 1, "at least one contradicted claim is shown");
    for (const claim of contradicted) {
      assert.ok(claim.contradictedBy, `${claim.id} names its contradiction`);
    }
  });

  it("never shows an ESTIMATED value as ACTUAL", () => {
    for (const claim of CLAIMS) {
      if (claim.claim.evidenceClass === "estimated") {
        assert.equal(claim.valueKind, "ESTIMATED", claim.id);
      }
      if (claim.valueKind === "ESTIMATED") {
        assert.match(claim.valueLabel, /estimated/i, claim.id);
      }
    }
  });

  it("the Rs counter is an explicit zero, not a fabrication", () => {
    const rs = CLAIMS.find((claim) => claim.id === "RS-0");
    assert.ok(rs, "RS-0 is in the ledger");
    assert.equal(rs.valueKind, "ACTUAL");
    assert.match(rs.valueLabel, /Rs 0/);
  });

  it("latestStateChange returns a claim", () => {
    const latest = latestStateChange();
    assert.ok(latest, "there is a latest state change");
    assert.equal(publicClaims().includes(latest), true);
  });
});
