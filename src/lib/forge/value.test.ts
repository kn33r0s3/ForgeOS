import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  evidenceRank,
  tierFromEvidence,
  tierLabel,
  type GiveUpEvidence,
} from "./value.ts";
import { evidenceFor, GIVE_UP_EVIDENCE } from "./give-up-evidence.ts";
import { evidenceTierOf } from "./value-tiers.ts";

function ev(kind: GiveUpEvidence["kind"]): GiveUpEvidence {
  return {
    unknownId: "D12",
    kind,
    actor: "Kathmandu retailer",
    gaveUp: "test",
    recordedAt: "2026-10-04",
  };
}

describe("value from evidence", () => {
  it("derives tiers from give-up evidence, strongest first", () => {
    assert.equal(tierFromEvidence(ev("verified-payment")), 3);
    assert.equal(tierFromEvidence(ev("committed")), 2);
    assert.equal(tierFromEvidence(ev("replied-engaged")), 1);
    assert.equal(tierFromEvidence(ev("stated-interest")), 1);
  });

  it("no evidence means unscored — never a high tier", () => {
    assert.equal(tierFromEvidence(null), "unscored");
    assert.equal(tierLabel("unscored"), "unscored");
  });

  it("ranks evidence kinds for sorting", () => {
    assert.ok(evidenceRank(ev("verified-payment")) > evidenceRank(ev("committed")));
    assert.ok(evidenceRank(ev("committed")) > evidenceRank(ev("replied-engaged")));
    assert.ok(evidenceRank(ev("replied-engaged")) > evidenceRank(ev("stated-interest")));
    assert.equal(evidenceRank(null), 0);
  });

  it("the ledger is empty: every unknown is unscored until someone gives something up", () => {
    assert.equal(GIVE_UP_EVIDENCE.length, 0);
    assert.equal(evidenceFor("D1"), null);
    assert.equal(evidenceFor("D70"), null);
    assert.equal(evidenceTierOf("D1"), "unscored");
    assert.equal(evidenceTierOf("D70"), "unscored");
  });
});
