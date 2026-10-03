# Forge Bot state mapping

Status: **PARTIAL IMPLEMENTATION — local consent-scoped intake exists but is
disabled by default.** Forge Bot is a feature of ForgeOS, not a separate
application or state system.

| Bot concern | Existing ForgeOS record | Boundary |
|---|---|---|
| Inbound request/problem description | `Signal` | Keep the existing redaction behavior. Do not put raw email addresses or phone numbers in Signal content or provenance. |
| Lead/business identity and lifecycle subject | `SubstrateEntity` | Use the existing entity type registry and source identity. A record is not evidence that the person is a customer. |
| State changes and message/booking/opt-out events | `WorldEvent` | Record only observed events with provenance; an event is not proof of customer or payment status by itself. |
| Consent, message delivery, booking, fulfillment, payment | `Evidence` and existing evidence relationships | Retain source, purpose, timestamp, and evidence scope. A conversation cannot establish payment. |
| Existing capability/channel | `SubstrateCapability` and current integrations | Reuse only an active, authorized capability. Do not add a channel just to complete the design. |
| Owner response policy | `OpForgeBotResponseAuthorization` | Singleton `op_` projection only; absent means closed. Changed policy emits a registered `WorldEvent`; observed preference is not authorization. The projection is read by the canonical ACTION decision, not a sender. |
| Customer-response ACTION and approval | Existing `Action` plus registered `WorldEvent`s | Owner-only proposal and approval; the dedicated adapter records the canonical decision but does not send. Generic provider paths recheck the decision and block matching Forge Bot contacts. |
| Delayed follow-up/reminder work | `WorkerTask` | Reuse idempotency, due time (`next_run_at`), conditional claim, and retry. Stale `running` task recovery is not implemented; do not assume a timed-out task is safe to requeue until handler side effects are idempotent. Production scheduling is not currently sub-daily. |
| Request to book an existing public service | `BookingRequest` | Use only when a real, active Forge public provider/service listing is the subject. This is not a generic bot calendar or booking table. Otherwise send an owner-approved booking link only after contact is authorized. |
| Draft offer and approval | Existing `Product` / offer-preparation flow | Keep proposal and owner approval semantics; never treat a draft or approval as a published offer or sale. |
| Customer-confirmed/paid outcome | Existing `/api/earn` offer state machine and `Outcome` evidence | Preserve its valid transitions and required honest outcome note. Payment remains unverified until acceptable payment evidence is recorded. |
| Narrow private contact and consent | `ForgeBotLeadContact` | Owner-authorized exception limited to Forge Bot leads. It is isolated from public substrate records and projections; no other workflow may use it. Intake remains disabled unless its feature flag, stable HMAC key, and API key are configured. |

## Minimal contact record needed before a live channel

The current anonymous demand endpoint deliberately redacts email and phone
patterns. Do not weaken that behavior or smuggle contact details into a Signal.
The owner approved one narrowly scoped Forge Bot contact table because generic
entity reads/projections expose attributes and are not a safe contact store.
It records only:

- email and optional phone plus normalized deduplication values;
- destination, course, timeline, and budget range as stated by the submitter;
- consent timestamp, purpose, and provenance;
- preferred contact channel;
- permanent opt-out state, timestamp, and HMAC-only suppression tokens;
- deletion state and a one-time self-service control-token hash.

The submit endpoint does not write a Signal, entity, evidence, or public
projection. It emits registered `WorldEvent` lifecycle events containing only
an opaque reference, evidence class, and state transition; contact,
qualification, and consent values remain in the private contact record. The
one-time bearer code is returned only to the submitter; it is stored as a hash
and allows opt-out or deletion. Opt-out erases the contact and answers but
keeps keyed HMAC suppression tokens; hard deletion removes the row while its
privacy-minimized erasure event remains.
No endpoint returns contact details except owner-authenticated lead summary
and detail routes, which require the `X-API-Key` header. No contact value is
emitted in the public submit receipt.

The provided Cal.com URL is public configuration rendered on the `noindex`
`/forge-bot-intake` page, linked contextually from the business information
surface. The optional owner contact email is environment-only and is not
rendered publicly. When an internal owner notification is enabled, its SMTP
provider can process contact and inquiry details; this is not a
customer-facing reply. The booking link itself does not book an appointment.
The owner-only `GET/PUT /forge-bot/response-authorization` endpoints record the
selected existing `email`/`phone` channel, explicit channel and template
authorization, mandatory consent, permanent opt-out boundary,
owner-confirmation boundary, and separate external-send authorization. An
absent setting is closed; policy changes emit `WorldEvent`. The per-inquiry
readiness endpoint returns internal readiness only and distinguishes observed
submitter preference from the owner-selected channel. No channel or template
has been owner-configured, `FORGE_BOT_RESPONSE_SEND_ENABLED` defaults false,
and no Forge Bot sender exists. The canonical decision therefore remains
`BLOCKED`; blocked Forge Bot ACTIONs create no outbox delivery. The internal
daily owner digest is implemented through the authenticated scheduled route
and existing outbox; actual delivery requires SMTP configuration and is not
established by code presence.
Inbound email parsing and customer-facing follow-up are not connected.
Authenticated daily maintenance erases inquiries at least 30 days old when
they remain in `READY_FOR_OWNER_REVIEW` and have no linked Forge Bot response
`ACTION`; the privacy-minimized erasure event is retained. A linked response
`ACTION` is currently exempt from automatic erasure. The proposed 90-day
maximum after a response `ACTION` is not implemented and requires owner
approval. Do not add separate message, opt-out, escalation, or intervention
architectures. No passports, identity documents, academic records, or other
sensitive ID data.

## Safe transition rule

Candidate lifecycle labels (`INQUIRY`, `CONTACTED`, `QUALIFYING`, `QUALIFIED`,
`BOOKED`, `FOLLOW_UP_PENDING`, `INTERESTED`, `CUSTOMER`,
`PAYING_CUSTOMER`) are projections over attributable existing events/evidence,
not a second state machine. A message may support `CONTACTED`; it does not imply
`INTERESTED`, `CUSTOMER`, or `PAYING_CUSTOMER`. A booking is recorded only from
booking evidence. A paid state requires payment evidence and the existing
outcome-note contract.

Intake is disabled unless `FORGE_BOT_INTAKE_ENABLED=true`,
`FORGE_BOT_CONTACT_HMAC_KEY` is stable and at least 32 characters, and
`FORGE_API_KEY` is configured. Durable HMAC-keyed request limits and a 16 KiB
body cap are implemented for the scoped public write endpoints and covered by
SQLite/PostgreSQL tests. Unactioned inquiries in `READY_FOR_OWNER_REVIEW` are
erased after 30 days by authenticated daily maintenance, which also purges
expired rate-limit buckets. A linked response `ACTION` is exempt; the proposed
90-day maximum for those records is not implemented and requires owner
approval. Licensed-agency discovery, a configured response channel/template,
and any production sender remain unavailable. The owner policy record is an
explicit authorization boundary, but is absent by default and cannot enable
sending:
the final send setting defaults false and no sender is wired. All automated
replies, follow-ups, offers, and spending remain disabled. The data model is
not authorization.

## Current verification boundary (2026-10-04)

The current checkout (`1459eec34c0105372e2b089a92994528ac393707`, equal to
`origin/main` at inspection) passed the full backend SQLite suite (**685
passed, 2 skipped**) and `npm test` (**197 script tests and 107 app tests**);
typecheck and lint passed. The full backend suite on throwaway PostgreSQL 18 was **not green** (**676
passed, 9 failed, 2 skipped**): failures occurred in `test_experiment_service`,
two `test_health_readiness` tests, `test_phase1_provenance_and_identity`,
`test_research_question_relation_substrate_adapter`, and four
`test_tool_usefulness` tests. The directly affected Forge Bot, public-write-
limit, and signal-request test files passed **103/103** on PostgreSQL 18. Do
not claim complete PostgreSQL parity until the remaining suite failures are
resolved. The latest GitHub Actions run for this SHA was green. Public `/api/health` returns only `status` and `ready`;
`/api/health/details` requires `X-API-Key`.

Read-only GETs on `haminp.vercel.app` and `forge-os-ebon.vercel.app` returned
health 200/ready and `intake_enabled=false`. On `haminp.vercel.app`, a
390x844 browser verified `/request` and `/request-a-project` render the closed
message with no form controls and no browser errors. These observations do
not establish the deployed commit SHA: the owner readiness endpoint is
protected, and no owner key was used. The database credential access
procedure is not authorized/documented, so no production database was
queried. Intake remains closed; no REAL lead, customer, or transaction is
established by these tests.
