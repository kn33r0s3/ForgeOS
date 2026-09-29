# Forge Bot v0: Lead Follow-up and Booking

Status: **TARGET ARCHITECTURE.** Spec only, not yet implemented.
Forge Bot is one ForgeOS feature, not a separate platform.
Runtime: **self-hosted n8n**, built and maintained by the operator. Clients cannot edit workflows.

## Purpose
Reply to every inbound lead for an education-abroad consultancy within 60 seconds, qualify it, follow up until it books or goes cold, and give the owner a daily view.

## Flow
1. **Intake.** A web form (n8n Form or a webhook from the client's site) and the client's inbound email. The lead is deduplicated by email or phone, and a lead ID is assigned.
2. **Instant reply.** The reply includes an automation disclosure ("This is an automated assistant for <Consultancy>"), STOP instructions, and the first qualifying question.
3. **Qualify.** Four fields: destination country, course or level, intake timeline, and budget range (client-defined bands, never an exact amount). Other questions are answered only from client-approved FAQ text.
4. **Follow-up.** Configurable schedule, default day 1, day 3 and day 7, then the lead is marked cold. Messages are sent only outside the client's quiet hours. Follow-ups stop on reply, booking, opt-out or escalation.
5. **Booking.** A qualified lead receives the client's booking link. A booking-tool webhook marks the lead `booked` where available. Otherwise staff mark it manually.
6. **Daily owner summary.** An email with counts per status, new leads, and leads needing a human, plus a lead-status table with name, source, the four fields, status, last contact and next action.

## Lead states
`new → contacted → qualifying → qualified → booking_sent → booked`
Side states: `escalated` (a human must act), `cold` (follow-ups exhausted), `opted_out` (permanent and terminal).

## Guardrails
- Every first contact discloses automation. The bot never claims to be human.
- **STOP:** STOP, UNSUBSCRIBE, and client-configured local-language equivalents set the lead to `opted_out` permanently. Every send path checks opt-out first. Emails carry an unsubscribe line.
- **No visa, admission, job, fee or scholarship promises.** The bot answers only from client-approved text. Anything else escalates: the bot sends a holding reply and the owner is notified.
- The bot also escalates on complaints, legal or refund topics, minors, and low AI confidence.
- **Minimal data:** name, email or phone, source, the four fields, consent and opt-out flags, status and timestamps. No passport details, documents or academic records. Message bodies follow the client retention setting.

## Channels
- **v0:** web form + email.
- **v1: WhatsApp, lead-initiated only.** Per Meta docs checked 2026-09-29, a user message opens a 24-hour customer service window that resets with each user message. Free-form replies are allowed only inside that window. Outside it, only approved templates may be sent. From **2026-10-01** Meta charges per message for service (non-template) replies. This requires a verified WhatsApp Business account with a payment method on file. Re-verify before building v1.
- **v2: Messenger.** 24-hour standard messaging window. Message tags cover approved use cases only, so sales follow-ups outside the window are not allowed. Re-verify before building v2.

## Runtime design
- **Workflows** (`services/forge-bot/workflows/*.json`): Intake, Converse/Qualify, a Send sub-workflow that every outbound message goes through (opt-out check, quiet hours, disclosure, logging), a Follow-up scheduler, a Booking webhook, the Daily summary, and an Error handler.
- **State:** Postgres, see `state/schema.sql`. Per-client behaviour lives in `client_config`. The operator changes config, never the client.
- Standard n8n nodes only. Committed JSON contains no secrets. Credentials are recreated per instance.
- **Substrate mapping (later, no migration now):** lead = ENTITY, message = EVENT, booking or opt-out proof = EVIDENCE, channel = CAPABILITY, send = ACTION.

## Open decisions
1. AI model provider (OpenAI / Anthropic / local).
2. Email sending: client mailbox via SMTP/IMAP, or a sending service. SPF/DKIM are required either way.
3. Booking tool: Cal.com (self-hostable, sends webhooks) or the client's existing tool.

## Done when
A test lead gets its reply within 60 seconds, is qualified over a few messages, receives follow-ups on schedule, stops immediately on STOP, escalates on a visa-odds question, and appears correctly in the daily summary.

Pricing is out of scope until 5 owner conversations are logged in `docs/REVENUE_LOG.md`.
