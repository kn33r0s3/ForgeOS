/**
 * Hard bounds for the public evidence-triage contract.
 *
 * Every value here is a security limit, not a preference. Changing any of them
 * changes the public contract and must be reflected in /openapi.json and
 * /.well-known/x402.
 */

/** Service semantic version. Bump on any change to the output shape or scoring. */
export const SERVICE_VERSION = "0.2.0";

/** Maximum accepted request body in bytes (12 KiB). Enforced before parsing. */
export const MAX_INPUT_BYTES = 12 * 1024;

/** Maximum accepted `text` length in UTF-16 code units. */
export const MAX_TEXT_CHARS = 11_500;

/** Minimum accepted `text` length in UTF-16 code units after trimming. */
export const MIN_TEXT_CHARS = 1;

/** Wall-clock budget for one triage execution, in milliseconds. */
export const EXECUTION_BUDGET_MS = 25;

/** Operator-visible identifier for the scoring model. */
export const SCORING_MODEL = "forgeos-evidence-triage/v2";

/** Allowed values of `source_kind`. Closed set - unknown values are rejected. */
export const SOURCE_KINDS = [
  "user_report",
  "public_post",
  "review",
  "forum",
  "document",
  "other",
] as const;

/** Inclusive lower bound of `source_reliability`. */
export const SOURCE_RELIABILITY_MIN = 0;

/** Inclusive upper bound of `source_reliability`. */
export const SOURCE_RELIABILITY_MAX = 1;

/**
 * The only top-level request keys accepted.
 * Any additional key is rejected rather than ignored, so a caller cannot
 * smuggle fields that a future version might interpret.
 */
export const ALLOWED_INPUT_KEYS = ["text", "source_kind", "source_reliability"] as const;
