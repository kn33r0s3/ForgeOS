# Hami authority contract

**Status:** governing policy contract. This file is not a grant ledger and does not itself authorize any action.

## 1. Purpose and order of authority

Hami uses the existing six primitives and existing authorization, policy, Action, Event, evidence, worker and audit seams. Do not create a second authorization database or parallel ledger. This policy is subordinate to applicable law, source licenses/terms, platform permissions and the owner's explicit instructions.

A capability, model answer, plan, scheduled job or policy `ALLOW` is not authority by itself. The action executor must re-check authorization at execution time and record the result through the existing audit/event path.

## 2. Required standing-authorization envelope

Every standing authorization, wherever recorded in the existing system, must be explicit and machine-checkable. It must define:

- **Issuer and identifier:** who granted it, a unique reference, and the existing audit/event reference recording the grant.
- **Purpose and action class:** one operational purpose and exact action classes permitted.
- **Target and scope:** permitted repository, resource, exact source URLs, data fields, environment and counterparties. No implied access to a neighboring target.
- **Data boundary:** permitted data classes, privacy minimization, source-license/terms basis, retention and output restrictions.
- **Limits:** maximum batch size, request rate, concurrency, retries and compute/runtime ceiling. Spend/money movement is prohibited; the permitted spend limit is always **zero**.
- **Time:** `valid_from`, absolute `expires_at`, and any stricter per-run expiry. Missing, invalid or expired times mean **DENY**.
- **Exclusions and stop conditions:** forbidden actions, kill criteria, failure behaviour and persistent HALT state that blocks action execution.
- **Evidence and audit:** deterministic preconditions, validation checks, required postcondition evidence and the existing trace/event reference recording start, result, error and recovery.

No wildcard over people, accounts, domains, sources, data categories or actions. Renewal requires a fresh explicit owner decision. Failure, timeout, ambiguity, changed purpose/target, changed data boundary or expiry means fail closed. Do not turn a prior grant or inferred intent into a new grant.

## 3. Actions that standing authorization can never permit

A standing authorization must **never** authorize:

- contacting people, sending messages to prospects/customers, replying to them, or making calls;
- spending, charging, transferring, refunding or otherwise moving/committing money;
- publishing consequential claims, offers, public conclusions or customer-facing content;
- signing contracts, accepting legal terms, hiring/firing or making commitments on the owner's behalf;
- enabling public intake, checkout, production messaging, external action paths or other high-impact flags;
- accessing private accounts/data, bypassing authentication, or collecting/retaining data outside the approved scope.

These require a separate, specific owner-controlled decision through the existing authorization path; a document, standing grant, agent recommendation or test fixture cannot substitute for it. A Telegram delivery is still a message; this file does not authorize it merely because it is labelled an alert.

## 4. Source and model boundaries

Authorization does not grant rights missing from a source's robots policy, terms, license or access controls. Register exact source URLs only after source review is recorded; mirror copies are weaker than primary records. If access is blocked, record `BLOCKED_BY_MISSING_ACCESS` with the failed check; never invent missing content or silently switch to a mirror.

Local inference must be selected explicitly. Silent mock fallback is not evidence of real inference. Keep `REAL`, `TEST`, `MOCK` and `HYPOTHESIS` distinct; model proposals remain proposals until deterministic validation and the independent evidence gate pass.

## 5. HALT, heartbeat and recovery

HALT is a persistent stop state for governed action execution. While HALT is active, the worker must not claim success, dispatch consequential actions, or clear HALT because a later model output suggests continuing. Release requires an explicit owner-controlled decision recorded through the existing owner-control path.

Every cycle must leave a durable cycle record, timestamped heartbeat, stage statuses, bounded failure category and recovery position. Retry only within existing retry/idempotency limits. Alerting is not proof of delivery; provider acceptance is not proof that a person received a message. This policy itself does not enable Telegram alerts.

## 6. Review and evidence

Review authorization whenever scope, purpose, data, model destination, deployment, risk or provider behaviour changes. Record grants, revocations, refusals, expiry and HALT transitions through existing audit events. Do not create another authorization or evidence ledger.

If required fields or evidence are missing, the result is **NOT AUTHORIZED / NOT VERIFIED**, never inferred approval. Metrics without a qualifying measured denominator must be reported **NOT MEASURABLE**.
