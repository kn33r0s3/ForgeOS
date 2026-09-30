/**
 * Public request/response types for the evidence-triage contract.
 *
 * These types are the machine-readable contract. They are mirrored in
 * /openapi.json and /.well-known/agent-card.json; when this file changes, those
 * documents must change with it.
 */

import type { SOURCE_KINDS } from "./limits.ts";

/** Accepted values of `source_kind`. */
export type SourceKind = (typeof SOURCE_KINDS)[number];

/** Validated, normalized input to the triage core. */
export type TriageInput = {
  text: string;
  source_kind: SourceKind;
  source_reliability: number;
};

/**
 * How a reported field was produced.
 *
 * - `observed`  - the value is a verbatim span of the submitted text.
 * - `derived`   - the value is a deterministic function of the submitted text.
 * - `unknown`   - the extractor found no supporting span; the value is null.
 *
 * Nothing is ever reported as `observed` unless the span appears in the input.
 */
export type FieldProvenance = "observed" | "derived" | "unknown";

/** Deterministic economic extraction result. */
export type EconomicExtraction = {
  problem: string | null;
  affected_customer: string | null;
  customer_type: string | null;
  pain: string | null;
  consequence: string | null;
  existing_solution: string | null;
  desired_outcome: string | null;
  buying_intent: boolean | null;
  urgency: boolean | null;
  frequency: string | null;
  monetary_impact: string | null;
};

/** Evidence fields plus their provenance and the exact supporting span. */
export type EvidenceReport = {
  values: EconomicExtraction;
  provenance: Record<keyof EconomicExtraction, FieldProvenance>;
  spans: Record<keyof EconomicExtraction, string | null>;
  evidence_text: string;
};

/** Integer scores. Every score is 0-100 inclusive. */
export type EconomicScores = {
  pain_score: number;
  urgency_score: number;
  monetary_impact_score: number;
  demand_score: number;
  solution_gap_score: number;
  evidence_strength: number;
  source_quality: number;
};

/** Match counts that back the importance score. */
export type ImportanceScores = {
  score: number;
  pain_matches: number;
  business_matches: number;
  urgency_matches: number;
  pain_score: number;
  business_score: number;
  urgency_score: number;
  base_score: number;
};

export type Scores = {
  model: string;
  economic: EconomicScores;
  importance: ImportanceScores;
};

/** Machine-readable eligibility decision with its exact basis. */
export type Eligibility = {
  economically_meaningful: boolean;
  basis: string;
  unmet_requirements: string[];
};

/** The hashed, deterministically-produced body of a fulfillment. */
export type FulfillmentBody = {
  service_version: string;
  input_hash: string;
  evidence: EvidenceReport;
  scores: Scores;
  unknowns: string[];
  eligibility: Eligibility;
  fulfillment_id: string;
};

/** A complete fulfillment, including the hash of its own body. */
export type Fulfillment = FulfillmentBody & { output_hash: string };

/** A field-level validation failure. */
export type ValidationIssue = {
  field: string;
  code: string;
  message: string;
};
