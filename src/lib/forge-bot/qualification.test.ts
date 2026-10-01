import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  hasDuplicateTestContact,
  normalizeEmail,
  normalizePhone,
  qualificationStage,
  validateTestContact,
  type DemoContact,
  type QualificationAnswers,
} from "./qualification.ts";

const completeAnswers: QualificationAnswers = {
  destination: "Japan",
  course: "Agriculture",
  timeline: "Next year",
  budgetMinimum: "100000",
  budgetMaximum: "250000",
};

describe("Forge Bot deterministic qualification demo", () => {
  it("moves only through inquiry, qualifying, and owner-review-ready states", () => {
    assert.equal(qualificationStage({
      destination: "",
      course: "",
      timeline: "",
      budgetMinimum: "",
      budgetMaximum: "",
    }), "INQUIRY");
    assert.equal(qualificationStage({ ...completeAnswers, course: "" }), "QUALIFYING");
    assert.equal(qualificationStage(completeAnswers), "READY_FOR_OWNER_REVIEW");
  });

  it("rejects malformed or inverted budget ranges", () => {
    assert.equal(
      qualificationStage({ ...completeAnswers, budgetMinimum: "300000" }),
      "QUALIFYING",
    );
    assert.equal(
      qualificationStage({ ...completeAnswers, budgetMaximum: "not-a-number" }),
      "QUALIFYING",
    );
  });

  it("normalizes email and phone keys for in-session duplicate checks", () => {
    assert.equal(normalizeEmail("  TEST+one@EXAMPLE.TEST "), "test+one@example.test");
    assert.equal(normalizePhone("+1 (202) 555-0100"), "12025550100");
    const saved: DemoContact[] = [{ email: "lead@example.test", phone: "" }];
    assert.equal(
      hasDuplicateTestContact(saved, { email: " LEAD@example.test ", phone: "" }),
      true,
    );
    assert.equal(
      hasDuplicateTestContact(
        [{ email: "", phone: "+1 (202) 555-0102" }],
        { email: "", phone: "12025550102" },
      ),
      true,
    );
    assert.equal(
      hasDuplicateTestContact(saved, { email: "other@example.test", phone: "" }),
      false,
    );
  });

  it("accepts reserved TEST contact values only", () => {
    assert.equal(
      validateTestContact({ email: "lead@example.test", phone: "" }),
      null,
    );
    assert.equal(
      validateTestContact({ email: "", phone: "+1 202-555-0100" }),
      null,
    );
    assert.match(
      validateTestContact({ email: "person@gmail.com", phone: "" }) ?? "",
      /reserved example\.test/,
    );
    assert.match(
      validateTestContact({ email: "", phone: "+977 9800000000" }) ?? "",
      /reserved 202-555/,
    );
  });
});
