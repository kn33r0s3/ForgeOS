# 002 — A6 triage: 103 Gitleaks + 129 TruffleHog candidates

- **Initial scan finding:** CAPABILITY_QUEUE.md A6 audit entry (18 Nov 16:34): 103 `generic-api-key` candidates (100 unique fingerprints) from Gitleaks + 129 unverified records (Postgres 55, URI 37, Alchemy 30, Pastebin 7) from TruffleHog. Live status was not verified at scan time. Retained evidence: `gitleaks-output-redacted.txt` (48,106 B) and `trufflehog-output-sanitized.ndjson` (27,100 B; 129 lines) in `/tmp/forgeos-a6-credential-audit-20261118T1014Z/evidence/`.
- **Owner:** Copilot
- **Input:** the two evidence files above; the staged triage order at /tmp/a6-gitleaks-rerun-trufflehog-triage-order.md
- **Output:** a triage record in docs/CAPABILITY_QUEUE.md listing the disposition of each candidate group (false positive / test fixture / vendored dep / needs rotation)
- **Verify:** the queue entry names every group and its disposition; no candidate left unclassified without a reason
- **If blocked:** mark the unclassifiable candidate "needs owner review" and continue with the rest; never rotate a key without owner approval

## Execution record — 2026-11-18

- **Status:** triage complete; owner-authorized rotation review remains open.
- **Gitleaks:** all 103 records were dispositioned: 14 records are one
  historical live-preview OAuth client secret duplicated across two paths and
  need owner-authorized rotation review; 30 are vendored dependency API names;
  18 are generated Next.js cache/manifest identifiers; 9 are test fixtures;
  and 32 are documentation or historical test references. Current liveness
  of the historical credential is unknown. No verification or rotation was
  performed.
- **TruffleHog:** all 129 unverified records were dispositioned: 75 are
  vendored dependency examples/RECORD digests, 42 are test fixtures with
  test-domain PostgreSQL URLs and placeholder passwords, and 12 are a copied
  test URL in a renovation artifact. Detector counts: Postgres 55, URI 37,
  Alchemy 30, Pastebin 7; no private-key detector fired.
- The staged `/tmp/a6-gitleaks-rerun-trufflehog-triage-order.md` describes an
  older false-zero/noisy scan. The later retained Gitleaks scan is valid;
  retained TruffleHog status reports zero stderr/error events. Full
  per-location dispositions and evidence paths/sizes are recorded in
  `docs/CAPABILITY_QUEUE.md`. No key rotation, external verification, build,
  test, commit, push, or deployment was performed.
