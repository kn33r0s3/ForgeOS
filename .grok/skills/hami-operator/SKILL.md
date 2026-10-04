---
name: hami-operator
description: >
  Work on Hami or ForgeOS features, operations, signup, production readiness,
  evidence, revenue, or the seller pilot. Use for broad requests such as
  "make everything live" as well as narrow code changes, and preserve the
  existing system's authorization, privacy, legal, and evidence boundaries.
metadata:
  short-description: "Reality-first Hami and ForgeOS operations"
user-invocable: false
---

# Hami Operator

Use this skill to turn an owner request into the smallest verified improvement
to the existing ForgeOS system. It supplements, never replaces, the repository
rules in `AGENTS.md`.

## Start From Current Evidence

1. Read the current `AGENTS.md`, `HANDOFF.md`, `STATUS.md`, and
   `docs/CAPABILITY_QUEUE.md`; inspect the actual implementation and nearby
   tests before trusting a prior summary.
2. Identify whether the request changes a real-world permission, external
   communication, spend, legal claim, personal data, or public projection.
3. Classify records and claims as `REAL`, `TEST`, `MOCK`, or `HYPOTHESIS`.
   Code, a policy `ALLOW`, a test pass, and an empty response are not evidence
   of a customer, conversation, payment, or outcome.

## Route Work Through the Hard Gate

Before each change, state from code or runtime evidence:

1. The routine owner action still required.
2. The action this change removes.
3. What remains and which permission or infrastructure blocks it.
4. The next removable dependency.

Record the blocker and verification in the existing `docs/CAPABILITY_QUEUE.md`.
Do not create another ledger or canonical domain primitive. For the current
seller pilot, the first unresolved real-world step is an owner-named seller and
explicit authorization for the exact first contact. Do not replace it with
branding, architecture, speculative research, synthetic activity, or a new
dashboard.

## Preserve Boundaries

- Never contact a person, publish an offer, spend money, open intake, or enable
  an outbound-send flag without explicit authorization for that exact action.
- Do not treat a requested action as executed, a test as real, an estimate as
  actual, or a booking request as a booking.
- Keep the six existing primitives: `ENTITY`, `RELATION`, `EVENT`, `EVIDENCE`,
  `CAPABILITY`, and `ACTION`. Operational tables are projections, not new
  sources of truth.
- Keep owner keys server-only or in explicitly entered, ephemeral UI state;
  never put them in source, URLs, local storage, or public client config.
- Keep signup behind the existing 18+ and current-terms permit. Do not write
  legal text or activate a terms version unless the owner has supplied or
  approved that exact document. Never persist date of birth.
- Preserve intentionally closed, private, `noindex`, test-only, and archived
  surfaces as such. "Use every resource" means connect supported paths safely,
  not expose every route or run every worker.
- Report `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` as **NOT MEASURABLE** until
  verified real transactions exist.

## Verify The Actual Seam

Choose a focused test that could disconfirm the local hypothesis, then run it
immediately after the edit. Follow with relevant typecheck/lint/build gates.
For protected UI, test both the no-key rejection and the authorized request
shape without retrieving or inventing a production credential. For production,
prefer read-only health/configuration checks; never test external effects by
creating real accounts, leads, messages, payments, or actions.

After a material change, update `HANDOFF.md` in the same release. State clearly
what is implemented, what was tested, what remains unverified in production,
and the owner decision still required. Do not claim a capability is live merely
because its code builds.