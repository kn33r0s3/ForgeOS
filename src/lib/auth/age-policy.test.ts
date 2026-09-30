import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  consumeSignupPermit,
  evaluateAdultEligibility,
  evaluateSignupRequirements,
} from "./age-policy.ts";

const NOW = new Date("2030-09-30T12:00:00.000Z");
const TEST_TERMS = { version: "TEST-terms-v1", url: "https://invalid.test/terms" };

describe("account age eligibility", () => {
  it("requires a real, non-future civil date", () => {
    assert.deepEqual(evaluateAdultEligibility(undefined, NOW), {
      eligible: false,
      reason: "dob_required",
    });
    assert.deepEqual(evaluateAdultEligibility("2000-02-30", NOW), {
      eligible: false,
      reason: "dob_invalid",
    });
    assert.deepEqual(evaluateAdultEligibility("2030-10-01", NOW), {
      eligible: false,
      reason: "dob_invalid",
    });
  });

  it("uses the 18th birthday boundary rather than subtracting birth years", () => {
    assert.deepEqual(evaluateAdultEligibility("2012-10-01", NOW), {
      eligible: false,
      reason: "under_18",
    });
    assert.deepEqual(evaluateAdultEligibility("2012-09-30", NOW), { eligible: true });
  });

  it("uses UTC civil dates and advances a February 29 birthday on March 1 in non-leap years", () => {
    assert.deepEqual(
      evaluateAdultEligibility("2008-02-29", new Date("2026-02-28T23:59:59Z")),
      { eligible: false, reason: "under_18" },
    );
    assert.deepEqual(
      evaluateAdultEligibility("2008-02-29", new Date("2026-03-01T00:00:00Z")),
      { eligible: true },
    );
    assert.deepEqual(
      evaluateAdultEligibility("2012-09-30", new Date("2030-09-30T23:30:00-12:00")),
      { eligible: true },
    );
  });

  it("keeps signup closed until real terms are configured and accepted", () => {
    assert.deepEqual(
      evaluateSignupRequirements({
        dateOfBirth: "2000-01-01",
        acceptedTerms: true,
        activeTerms: null,
        now: NOW,
      }),
      { eligible: false, reason: "terms_not_configured" },
    );
    assert.deepEqual(
      evaluateSignupRequirements({
        dateOfBirth: "2000-01-01",
        acceptedTerms: false,
        activeTerms: TEST_TERMS,
        now: NOW,
      }),
      { eligible: false, reason: "terms_acceptance_required" },
    );
  });

  it("requires a server-issued single-use consent permit for account creation", async () => {
    const records = new Map([
      [
        "hami-signup:0123456789abcdefghijklmnopqrstuvwxyz_ABCDEF",
        {
          value: JSON.stringify({
            termsVersion: TEST_TERMS.version,
            termsAcceptedAt: "2030-09-30T12:00:00.000Z",
          }),
        },
      ],
    ]);
    const consume = async (identifier: string) => {
      const value = records.get(identifier) ?? null;
      records.delete(identifier);
      return value;
    };

    assert.equal(await consumeSignupPermit(null, TEST_TERMS, consume), null);
    assert.deepEqual(
      await consumeSignupPermit(
        "hami_signup_permit=0123456789abcdefghijklmnopqrstuvwxyz_ABCDEF",
        TEST_TERMS,
        consume,
      ),
      {
        termsVersion: TEST_TERMS.version,
        termsAcceptedAt: new Date("2030-09-30T12:00:00.000Z"),
      },
    );
    assert.equal(
      await consumeSignupPermit(
        "hami_signup_permit=0123456789abcdefghijklmnopqrstuvwxyz_ABCDEF",
        TEST_TERMS,
        consume,
      ),
      null,
    );
  });
});
