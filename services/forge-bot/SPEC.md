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

`inbound inquiry → deterministic reply → qualification → authorized follow-up
→ booking request/link → reminder → evidence-backed status → daily owner summary`

The owner authorized a consent-scoped web intake record, supplied
`haminp.forge@gmail.com` as the contact address, and supplied the booking link
`https://cal.com/hami-forge-m9agd6/build-hami`. The contact address is a
`mailto:` link only; email inbox parsing, SMTP sends, and automatic booking
actions are not implemented. Public web intake remains disabled by default.
Activation requires `FORGE_BOT_INTAKE_ENABLED=true`, a stable server-only
`FORGE_BOT_CONTACT_HMAC_KEY` of at least 32 characters, and `FORGE_API_KEY`.
The route is not in shared navigation.

The form currently asks destination, course/field, timeline, budget range,
preferred contact channel, and explicit inquiry-response consent. After a
successful submission, the one-time control code can be used in the page to
permanently opt out or delete the inquiry; both actions require a separate
confirmation. Opt-out erases contact and answer fields while retaining
HMAC-only suppression tokens. Deletion removes the entire row, including
suppression tokens. A duplicate submission can receive a non-controlling code
without disclosing whether another record exists. No time-based retention
period is configured. A process-local limit is five submissions per source IP
per hour; this is not a distributed production abuse control and does not
authorize public activation. Email/WhatsApp channel integrations and official
policy review are still required before enabling those channels. No mass
outbound.

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
dedicated `ForgeBotLeadContact` table rather than `Signal` or generic
`SubstrateEntity.attributes`: generic entity reads/projections are not a
private contact store. The table is scoped only to Forge Bot and records
preferred channel, consent timestamp/purpose/provenance, HMAC suppression
tokens, deletion state, contact fields, and the four fixed answers. Lead
details are not returned by public feed, discovery, network, or substrate APIs.
The owner summary endpoint requires `X-API-Key`; public submit responses never
echo contact values. Do not store passports, sensitive ID documents, or
academic records.
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

Intake and consent management are implemented locally only; the route
`GET /forge-bot/config` reports settings, `POST /forge-bot/leads` accepts a
consented submission when enabled, `POST /forge-bot/leads/opt-out` applies
permanent suppression, `POST /forge-bot/leads/delete` erases a submission,
and `GET /forge-bot/leads/summary` returns up to 100 active rows only to an
owner presenting the API key. The summary is not scheduled or emailed.

Use `WorkerTask` idempotency, conditional claim, due time, and retry for
follow-ups/reminders. No follow-up/reminder task or automatic owner-summary
send is currently created. Stale `running` task recovery is not currently
implemented; add it to this existing machinery only after each handler's
external side effects are idempotent and safe to resume. The current deployed
Vercel cron runs once daily on Hobby and is not a sub-daily runner; the local
`backend/worker.py` is a separate process and is not verified as running in
production. Do not claim timed automation until safe recovery and a
commercially permitted production runner are proven.

## Not in v0

No email inbox/outbound SMTP or WhatsApp integration without owner-discovery
justification, verified official policy, explicit send authorization, and
tested channel controls. No
billing system, marketplace, mass outbound, full CRM, negotiation engine,
unapproved publishing or spending, or fabricated prospect simulation.

## Completion evidence

Before activation, prove with labeled `TEST` records that consent gates,
deduplication, rate/abuse limits at the deployed ingress, approved-answer-only
behavior, STOP permanence, deletion, failure halt, delayed-task recovery, and
status provenance work. Also choose a time-based retention policy and verify a
stable production database and private owner access. Local API tests do not
establish production activation.
Then require owner authorization before any `REAL` contact. Report actual
owner interventions and time only from real activity; if no real transaction
exists, `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**.
Architecture or tests alone do not establish autonomous operation.
