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

The submit endpoint does not write a Signal, entity, event, evidence, or public
projection. The one-time bearer code is returned only to the submitter; it is
stored as a hash and allows opt-out or deletion. Opt-out erases the contact and
answers but keeps keyed HMAC suppression tokens; hard deletion removes the row.
No endpoint returns contact details except the owner summary, which requires
the `X-API-Key` header. No contact value is emitted in the submit receipt.

The owner contact email and provided Cal.com URL are public configuration
values rendered on the unlisted `/forge-bot-intake` page. The email is a
`mailto:` link; neither it nor the booking link triggers an automated send or
booking action. SMTP, inbound email parsing, scheduled summaries, and follow-up
are not connected. No time-based retention policy is configured. Do not add
separate message, opt-out, escalation, or intervention architectures. No
passports, identity documents, academic records, or other sensitive ID data.

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
`FORGE_API_KEY` is configured. The current per-process IP limiter is not
distributed; production ingress abuse controls, a time-based retention policy,
licensed-agency discovery, and any external-send authorization remain
unverified. All automated replies, follow-ups, offers, and spending remain
disabled. The data model is not authorization.
