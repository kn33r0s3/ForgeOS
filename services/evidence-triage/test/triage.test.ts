import assert from "node:assert/strict";
import test from "node:test";
import { handleEvidenceTriage } from "../src/app.ts";
import { MAX_INPUT_BYTES, triage } from "../src/triage.ts";

const input = { text: "Small contractors are wasting 5 hours every week manually reconciling invoices. They would pay for a tool because missed invoices are costing $500.", source_kind: "public_post", source_reliability: 80 };

test("returns deterministic, evidence-bound fulfillment", async () => {
  const [first, second] = await Promise.all([triage(input), triage(input)]);
  assert.deepEqual(first, second);
  assert.equal(first.eligibility.economically_meaningful, true);
  assert.equal(first.evidence.pain, "wasting time");
  assert.equal(first.scores.economic.source_quality, 80);
  assert.match(first.fulfillment_id, /^ful_[0-9a-f]{24}$/);
});

test("frequency is not misclassified as an affected customer", async () => {
  const result = await triage(input);

  assert.equal(result.evidence.affected_customer, null);
  assert.equal(result.evidence.customer_type, "contractor");
  assert.equal(result.evidence.frequency, "5 hours");
  assert.equal(result.evidence.pain, "wasting time");
});

test("unknowns remain explicit rather than inferred", async () => {
  const result = await triage({ text: "A document mentions dentists.", source_kind: "document", source_reliability: 100 });
  assert.equal(result.eligibility.economically_meaningful, false);
  assert.ok(result.unknowns.includes("pain"));
  assert.ok(result.unknowns.includes("monetary_impact"));
});

test("HTTP boundary rejects oversized, malformed, and unsupported requests", async () => {
  const malformed = await handleEvidenceTriage(new Request("https://service/v1/evidence-triage", { method: "POST", headers: { "content-type": "application/json" }, body: "{" }));
  assert.equal(malformed.status, 400);
  const huge = await handleEvidenceTriage(new Request("https://service/v1/evidence-triage", { method: "POST", headers: { "content-type": "application/json", "content-length": String(MAX_INPUT_BYTES + 1) }, body: "{}" }));
  assert.equal(huge.status, 413);
  const wrong = await handleEvidenceTriage(new Request("https://service/v1/evidence-triage", { method: "GET" }));
  assert.equal(wrong.status, 405);
});

test("HTTP boundary returns the actual deterministic fulfillment", async () => {
  const response = await handleEvidenceTriage(new Request("https://service/v1/evidence-triage", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(input) }));
  assert.equal(response.status, 200);
  const result = await response.json() as { output_hash: string; fulfillment_id: string };
  assert.match(result.output_hash, /^[0-9a-f]{64}$/);
  assert.match(result.fulfillment_id, /^ful_/);
});
