# CURRENT_FOCUS.md — S10: One Verified Provider Pilot

**Last updated**: 2026-09-25
**Work order**: [SERIAL_PATH.md](SERIAL_PATH.md) is the only queue.

## Current state

S10's code path is in place. No provider or booking may be added without real evidence and an operator-submitted request. At the last production verification on 2026-09-25, the provider and service lists were empty. The current production state has not been rechecked in this session.

The repository now contains a protected, once-daily Vercel trigger for the existing cycle runner. Its production deployment and `CRON_SECRET` configuration are unverified, so this code is not evidence that production cycles are running.

## S10 evidence checklist

- [ ] A real provider supplies evidence for a service they actually offer.
- [ ] An operator reviews and records the verification evidence type, reference, and reviewer.
- [ ] Publish the provider and service only after that verification; leave a missing price null.
- [ ] An operator submits a real booking request before a booking record is created.
- [ ] Record the actual result when it occurs; do not infer acceptance, fulfillment, or payment.

Do not seed demo providers, prices, bookings, or outcomes. Do not fabricate a person or contact anyone on their behalf. No payment credentials are part of this step.

## Separate publicity gate

The footer domain and contact mailbox remain pending until the operator supplies a domain they control and a monitored mailbox. See [PUBLICITY_GATE.md](PUBLICITY_GATE.md).

The cycle trigger also needs a production deployment and a configured `CRON_SECRET`; its once-daily schedule invokes the canonical runner only. It does not publish providers, send messages, or invent prices.
