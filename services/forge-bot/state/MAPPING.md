# Forge Bot state mapping

Status: **DESIGN ONLY — no Forge Bot lead/contact workflow is implemented.**
Forge Bot is a feature of ForgeOS, not a separate application or state system.

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

## Minimal contact record needed before a live channel

The current anonymous demand endpoint deliberately redacts email and phone
patterns. Do not weaken that behavior or smuggle contact details into a Signal.
Before any lead-reply channel is exposed, add one narrowly scoped contact record
linked to the existing entity, with only:

- channel and normalized destination;
- consent timestamp, purpose, and provenance;
- permanent opt-out state and timestamp;
- deletion/retention state needed to honor the stated policy.

Do not add separate lead, message, opt-out, escalation, or intervention
architectures. Store the minimum message/event evidence needed for the existing
Forge records to explain what occurred; do not retain message bodies by default.
No passports, identity documents, academic records, or other sensitive ID data.

## Safe transition rule

Candidate lifecycle labels (`INQUIRY`, `CONTACTED`, `QUALIFYING`, `QUALIFIED`,
`BOOKED`, `FOLLOW_UP_PENDING`, `INTERESTED`, `CUSTOMER`,
`PAYING_CUSTOMER`) are projections over attributable existing events/evidence,
not a second state machine. A message may support `CONTACTED`; it does not imply
`INTERESTED`, `CUSTOMER`, or `PAYING_CUSTOMER`. A booking is recorded only from
booking evidence. A paid state requires payment evidence and the existing
outcome-note contract.

Until consent, the owner-authorized channel, factual answer set, opt-out
enforcement, rate limits, abuse controls, and a reliable due-task runner are
implemented and verified, all external replies, follow-ups, offers, and
spending remain disabled. The data model is not authorization.
