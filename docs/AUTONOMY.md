# Hami autonomy tiers

These tiers describe the maximum permitted mode of operation. They do not
assert that Hami currently has the execution capability, evidence, or external
permission required for a tier. A tier never overrides consent, authorization,
privacy, legal, platform, or safety boundaries.

| Tier | Mode | Boundary |
| --- | --- | --- |
| 0 — Observe | Read approved sources and inspect existing state. | Read-only. No external contact, collection of personal data, public posting, spend, or state-changing write. |
| 1 — Prepare | Analyze, draft, and propose code or actions. | A human reviews and explicitly authorizes before publication, contact, spend, or production state change. |
| 2 — Owner-gated | Handle sensitive or high-impact changes and actions. | Explicit owner authorization is required. Changes to paths listed in `.github/CODEOWNERS` require owner review when main-branch protection enforces code-owner approval. |
| 3 — Bounded standing authorization | Execute a specifically pre-authorized, repeatable action. | Authorization must record the action, purpose, scope, spend, rate, privacy, counterparty, exclusions, expiry, and evidence limits. It is revocable and does not supply missing external permission or execution capability. |

## Current limits

- No tier permits manufactured evidence or treating `TEST`, `MOCK`, or
  `HYPOTHESIS` as `REAL`.
- No tier promotes a candidate to a live action without the existing approval
  and authorization gates.
- Forge Bot intake and `FORGE_BOT_LIVE` must stay closed unless the owner
  explicitly authorizes activation.
- Tier 3 is not a claim of autonomous experimentation. Production behavior is
  autonomous only when its actual execution path and standing authorization
  have both been implemented and verified.
- Agents never weaken tests to pass them.
