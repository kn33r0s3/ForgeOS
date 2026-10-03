# Forge Bot v0 — Native ForgeOS lead follow-up

Status: **HYPOTHESIS / PARTIAL LOCAL IMPLEMENTATION. Public intake is disabled
by default; no automated response, email, booking action, or outbound contact
is enabled.** Forge Bot is one feature of ForgeOS. It runs natively on existing
ForgeOS services; n8n is not a dependency.

## Bootstrap boundary

The goal is one real customer, one real paid outcome, then repeat and automate.
Do not buy software or infrastructure before first real customer revenue,
unless a verified legal, security, payment, or critical-execution requirement
necessitates it. Do not contact a person, publish an offer, spend money, or
simulate a prospect conversation without the owner's explicit authorization.
Mark records `REAL`, `TEST`, `MOCK`, or `HYPOTHESIS`; test activity is never
customer or revenue evidence.

The initial segment is only a hypothesis: licensed Nepal education-abroad
consultancies. Foreign-employment agencies have additional regulatory and
reputation risk and are not an initial target without separate owner review.
The owner must conduct about five real discovery conversations. Only their
reported findings may set qualification fields, channel order, follow-up
cadence, booking method, and pilot terms. See
[`docs/FORGE_BOT_DISCOVERY.md`](../../docs/FORGE_BOT_DISCOVERY.md).

## Intended lifecycle

`inbound web inquiry → synchronous in-browser receipt → owner review and
qualification → authorized follow-up → booking request/link → reminder →
evidence-backed status → daily owner summary`

The synchronous receipt acknowledges only the web submission. It is not a
reply on the submitter's selected email/phone channel.

The response authorization boundary is implemented as owner-only
`GET/PUT /forge-bot/response-authorization` endpoints backed by the singleton
`op_forge_bot_response_authorization` operational projection. An absent
configuration is SAFE/CLOSED. The owner must explicitly select and authorize
one existing `email` or `phone` channel, authorize a non-contact template
reference, retain the consent requirement, and set the opt-out and
owner-confirmation boundaries. Each changed policy emits a registered
`WorldEvent`; the submitter's observed preference remains separate and must
match the owner-selected channel. A response ACTION uses the existing `Action`
primitive, requires explicit owner approval, and emits registered events for
proposal, approval, and its canonical authorization decision. The dedicated
`forge_bot_response` adapter is authorization-only and never sends. The
canonical decision is rechecked before outbox creation and provider dispatch;
generic SMTP/Twilio requests matching a lead or its suppression HMAC are
blocked. `GET /forge-bot/leads/{reference}/response-readiness` uses the same
decision and remains `BLOCKED` while the ACTION, final send gate, or sender is
missing. The response-send setting defaults false and no Forge Bot sender is
available, so no external response is possible.

The booking link
`https://cal.com/hami-forge-m9agd6/build-hami` is public configuration. The
optional owner contact address is environment-only and is not rendered on the
public site or returned by the public config endpoint. When SMTP credentials
and that address are configured, an internal owner notification may include
the inquiry's contact and answer fields; the email provider therefore processes
those details. The daily digest includes up to 100 references, evidence
classes, stages, and creation times, but no contact details. Without SMTP
credentials or an owner address, delivery is skipped, not reported as sent.
Email inbox parsing, customer-facing email, and automatic booking actions are
not implemented. Public web intake remains disabled by default. Activation
requires `FORGE_BOT_INTAKE_ENABLED=true`, a stable server-only
`FORGE_BOT_CONTACT_HMAC_KEY` of at least 32 characters, and `FORGE_API_KEY`.
The route is not in the global primary navigation. The inquiry page is linked
from the business information surface for context; it remains `noindex` and
does not publish an active offer.

The form asks for an email address or phone number, destination, course/field,
timeline, budget range, preferred contact channel, and explicit
inquiry-response consent. After a successful submission, the one-time control
code can be used to permanently opt out or delete the inquiry; both actions
require a separate confirmation. Opt-out erases contact and answer fields
while retaining HMAC-only suppression tokens. Deletion removes the contact
row, including suppression tokens; a privacy-minimized erasure event retains
only the opaque reference, evidence class, and state transition. A duplicate
submission can receive a non-controlling code without disclosing whether
another record exists.

The authenticated daily maintenance erases inquiries at least 30 days old
only when they remain in `READY_FOR_OWNER_REVIEW`, are not opted out or
previously erased, and have no linked Forge Bot response `ACTION`. It retains
the privacy-minimized erasure event and purges expired rate-limit buckets in
the same successful maintenance run. A linked response `ACTION` currently
exempts the inquiry from automatic erasure; see the proposed, unimplemented
maximum in “Proposed retention after a response ACTION.”

Public write routes use durable counters keyed by a server-side HMAC of the
visitor identifier, not a raw IP value in the counter table. Limits are five
requests per visitor per hour for public posts/requests and 20 per visitor per
hour for public domain close/dispute/response operations. Public write bodies
are capped at 16 KiB. Tests cover the counter and size-limit boundaries on
SQLite and PostgreSQL. These safeguards do not authorize public activation.
Email/WhatsApp customer-facing channels and official policy review are still
required before enabling those channels. No mass outbound.

When intake is enabled while `FORGE_BOT_LIVE=false`, the server accepts only
synthetic TEST records (`@example.test` email or reserved `202-555-01xx`
phone); a non-TEST submission is rejected with HTTP 403 before persistence.
`FORGE_BOT_LIVE=true` is required before a REAL record can be stored and
remains an explicit owner activation decision.

Qualification is client-configurable, not universal. Destination, course or
service, timeline, and budget range are candidate fields only. The client's
approved factual answers are the only permitted reply source. Use deterministic
state-machine replies; AI remains `MOCK` unless a legitimate provider,
credentials, budget, and separate approval exist.

## Reuse and data boundary

Use only the existing ForgeOS records and workflows listed in
[`state/MAPPING.md`](./state/MAPPING.md): Signal, SubstrateEntity, WorldEvent,
Evidence, SubstrateCapability, WorkerTask, BookingRequest where its existing
public-service contract applies, and the existing Product/offer and
Outcome/Earn state machines. Do not create a second lead, message, opt-out,
escalation, booking, or owner-intervention system.

The anonymous demand intake remains demand-understanding-only and continues to
redact email/phone patterns. Forge Bot contact information is isolated in the
dedicated `ForgeBotLeadContact` operational table rather than `Signal` or
generic `SubstrateEntity.attributes`: generic entity reads/projections are not
a private contact store. The table is scoped only to Forge Bot and records
preferred channel, consent timestamp/purpose/provenance, HMAC suppression
tokens, deletion state, contact fields, and the four fixed answers. Lead
details are not returned by public feed, discovery, network, or substrate APIs.
All owner lead-summary and lead-detail endpoints require `X-API-Key`; public
submit responses never echo contact values. Do not store passports, sensitive
ID documents, or academic records.
`BookingRequest` is for a request against an existing public provider/service
listing, not a general-purpose appointment calendar. Elsewhere use only an
owner-approved booking link or existing scheduling integration.

## Truthful lifecycle and authorization

Candidate labels are projections from evidence, not a new state architecture:
`INQUIRY`, `CONTACTED`, `QUALIFYING`, `QUALIFIED`, `BOOKED`,
`FOLLOW_UP_PENDING`, `INTERESTED`, `CUSTOMER`, and `PAYING_CUSTOMER`.
Conversation alone must never infer interest, customer status, fulfillment, or
payment. Booking requires booking evidence. Paid status requires payment
evidence and the existing honest outcome-note contract.

Before any outbound or public action, require an explicit owner authorization
covering action, purpose, source, scope, counterparty, content, limits, opt-out,
expiry/review, and evidence. No standing authorization currently exists for
Forge Bot. `STOP` must be permanent; no resume without valid re-consent. Check
opt-out and authorization on every send path. Disclose automation. Never make
visa, admission, employment, scholarship, or unsupported fee promises. Escalate
unknown/out-of-policy questions, complaints, legal/refund matters, and minors;
halt outbound on integration or policy failure.

Intake and consent management are implemented, but production intake remains
disabled. The route `GET /forge-bot/config` reports settings,
`POST /forge-bot/leads` accepts a consented submission when enabled,
`POST /forge-bot/leads/opt-out` applies permanent suppression,
`POST /forge-bot/leads/delete` erases a submission, and
`GET /forge-bot/leads/summary` returns up to 100 active rows only to an owner
presenting the API key. The daily digest points to this owner-only summary for
contact details and never includes those details in email. The response
authorization, readiness, and ACTION endpoints also require the owner API key.
Readiness checks the owner-authorized channel against the observed submitter
preference, explicit consent, opt-out/erasure state, and authorized template
reference without sending or queueing a message.

Use `WorkerTask` idempotency, conditional claim, due time, and retry for
follow-ups/reminders; no follow-up/reminder task is currently created. The
daily owner digest uses the existing authenticated Vercel cron and
`integration_outbox` idempotency rather than creating a new task or schema.
Stale `running` task recovery is not currently implemented; add it to this
existing machinery only after each handler's external side effects are
idempotent and safe to resume. The Vercel cron runs once daily on Hobby and is
not a sub-daily runner; the local `backend/worker.py` is a separate process
and is not verified as running in production. Do not claim timed automation
until safe recovery and a commercially permitted production runner are
proven.

## Proposed retention after a response ACTION

The current daily purge deletes inquiries older than 30 days only when no
Forge Bot response `ACTION` is linked. A linked response `ACTION` exempts the
contact record from that purge, and there is currently no later automatic
maximum. This section is a proposal only; it does not change retention
behavior.

Proposed maximum: erase the lead's contact and answer fields no later than
90 days after its original submission, whether or not an `ACTION` was
recorded. Later status events do not restart that clock. If work is still
active at the deadline, the owner must either close and erase the inquiry, or
move only the minimum necessary facts into existing customer/outcome records
under a separately verified purpose and consent before erasing the lead
contact. Any legal hold must have a documented reason, scope, and review date.
Keep only the existing privacy-minimized non-contact erasure event.

The owner must approve this proposal and its handling of suppression data
before implementation. Until then, the implemented 30-day no-`ACTION` purge
remains unchanged, and inquiries with a linked response `ACTION` have no
automatic maximum retention.

## Not in v0

No customer-facing email or WhatsApp sending path is implemented. The
owner-only authorization record is not a sender or standing approval to
contact anyone; external sending still requires a separately enabled final
gate and a verified, zero-cost sender path. The internal owner digest is not a
customer channel.
No
billing system, marketplace, mass outbound, full CRM, negotiation engine,
unapproved publishing or spending, or fabricated prospect simulation.

## Completion evidence

Before activation, prove with labeled `TEST` records that consent gates,
deduplication, rate/abuse limits at the deployed ingress, approved-answer-only
behavior, STOP permanence, deletion, failure halt, delayed-task recovery, and
status provenance work. The implemented retention rule erases unactioned
`READY_FOR_OWNER_REVIEW` inquiries after 30 days and purges expired
rate-limit buckets during daily maintenance. A proposed 90-day maximum for
inquiries with a response `ACTION` is not implemented and requires owner
approval. Verify stable production database and private owner access;
unauthenticated production checks do not establish either.

Local verification on 2026-10-04: the full backend suite passed with 681
passed and 2 skipped on SQLite and on throwaway PostgreSQL 18. The focused
Forge Bot owner-notification/API tests passed 69/69 on PostgreSQL 18.
The public `/api/health` response contains only `status` and `ready`; health
diagnostics require the owner key at `/api/health/details`. Focused health
authorization and ingress tests passed 16/16 on SQLite and PostgreSQL 18.
`npm test` passed 197 script tests and 106 app tests; typecheck, lint, and
production build passed. The build migration step was skipped because
`DATABASE_URL` was intentionally unset. Production intake remains disabled;
these tests and build do not authorize activation or establish a real lead,
customer, payment, or outcome.
Then require owner authorization before any `REAL` contact. Report actual
owner interventions and time only from real activity; if no real transaction
exists, `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**.
Architecture or tests alone do not establish autonomous operation.
