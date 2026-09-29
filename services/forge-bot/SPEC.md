# Forge Bot v0 — Native ForgeOS lead follow-up

Status: **HYPOTHESIS / TARGET ONLY. Not implemented, not enabled, and not
authorized to contact anyone.** Forge Bot is one feature of ForgeOS. It must
run natively on existing ForgeOS services; n8n is not a dependency.

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

The first channel is **not selected yet**. A web form is a candidate only; it
does not exist in this flow. Choose the cheapest controllable channel justified
by the owner's discovery, and build rate limiting, abuse controls, consent,
idempotency, retention, deletion, and provenance before making it public.
Email or WhatsApp is not assumed. Recheck current official channel policy
before implementing an integration. No mass outbound.

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
redact email/phone patterns. Lead contact information requires a separate,
consent-scoped contact record linked to an existing entity; it must include
channel, consent timestamp, purpose, permanent opt-out, and a deletion path.
Do not store passports, sensitive ID documents, or academic records.
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

Use `WorkerTask` idempotency, conditional claim, due time, and retry for
follow-ups/reminders. Stale `running` task recovery is not currently
implemented; add it to this existing machinery only after each handler's
external side effects are idempotent and safe to resume. The current deployed
Vercel cron runs once daily on Hobby and is not a sub-daily runner; the local
`backend/worker.py` is a separate process and is not verified as running in
production. Do not claim timed automation until safe recovery and a
commercially permitted production runner are proven.

## Not in v0

No WhatsApp/email integration without owner-discovery justification, verified
official policy, explicit authorization, and tested channel controls. No
billing system, marketplace, mass outbound, full CRM, negotiation engine,
unapproved publishing or spending, or fabricated prospect simulation.

## Completion evidence

Before activation, prove with labeled `TEST` records that consent gates,
idempotency, rate/abuse limits, approved-answer-only behavior, STOP permanence,
deletion, failure halt, delayed-task recovery, and status provenance work.
Then require owner authorization before any `REAL` contact. Report actual
owner interventions and time only from real activity; if no real transaction
exists, `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**.
Architecture or tests alone do not establish autonomous operation.
