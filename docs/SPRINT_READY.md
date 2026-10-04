# Sprint Ready Package — First Rupee

**Status: PENDING_REAL_WORLD_AUTHORIZATION.** Everything below is
prepared. Nothing here contacts anyone, moves money, or starts the week.
One human action unlocks it all (see §1).

## 1. The single real-world action (needs the owner)

**Name one social seller you can reach personally, and authorize the
first contact.**

That is the whole action: a name + "yes, send the first message." The
first-contact script is in `docs/SPRINT_BRIEF.md` — honest, no pitch, no
fake identity. Everything else in the sprint (the week, the replies, the
log, the count, the price talk) is prepared below and in the brief.

No agent can take this step: it needs a human in Kathmandu with a real
relationship or a real introduction. Until it happens, the sprint is
pending — not blocked-by-process, just waiting on a person.

## 2. Offer text (final)

> "Hey — I see you sell through [TikTok/WhatsApp]. I'm testing an idea:
> for one week, I handle your customer replies fast. Free test — you
> only pay if it actually recovers sales. Want the 2-minute version?"

End of week:

> "This week the fast replies recovered ₨X in sales that would have
> died. My cut is 10%. If you don't feel it was worth it, pay nothing."

Terms: one week, agreed hours (e.g. 9am–9pm), replies within 15 minutes
inside hours. The human never takes over the seller's account — added to
DMs by the seller, replies as a helper, never pretends to be staff.
Recovered = a sale that would have died without the fast reply;
conservative counting — when in doubt, don't count it.

## 3. Payment path (first rupee rails)

No business payment rails exist (company registration pending, only a
personal PAN). The first rupee moves on personal rails:

- Seller pays Hami's cut via **eSewa/Khalti transfer to the owner's
  personal account** — the same rails every Nepali social seller already
  uses (D14).
- Record the transfer ID, amount, date. That record is the
  verified-payment evidence (see §4).
- Migrate to business rails after company registration + PAN + merchant
  onboarding. The first rupee proves the mechanism; the rails get
  formalized before rupee #100.

No donations, no advance fees, no payment before recovered sales exist.

## 4. Evidence-capture events (six primitives)

Every sprint event is recorded as an EVENT with EVIDENCE — this is what
turns the week into the engine's first real data:

| Event | Primitives | Evidence |
|---|---|---|
| `inquiry.logged` | EVENT + ENTITY(customer inquiry) | timestamp in, channel, what they wanted |
| `reply.sent` | EVENT + ACTION(human reply) | timestamp out → reply latency |
| `sale.recovered` | EVENT + EVIDENCE | order value, why it would have died |
| `sale.lost` | EVENT + EVIDENCE | reason in one line |
| `payment.received` | EVENT + EVIDENCE(transfer record) | transfer ID, amount → **verified-payment give-up evidence** |
| `week.reported` | EVENT | the one-page report (see brief) |

The `payment.received` event is the first entry in the give-up evidence
ledger (`src/lib/forge/give-up-evidence.ts`) — the moment an unknown
earns a tier instead of "unscored."

## 5. What happens after authorization

1. Owner names the seller → first contact sent (human).
2. Week runs per `docs/SPRINT_BRIEF.md` (human).
3. Events logged per §4 → the week log fills on `/needs`.
4. Price talk → first rupee or honest zero.
5. Report back: one page, exactly as it happened.

**The legal note (D72):** work ONLY with a seller already registered
under the reported e-commerce registration law (act name and compliance
figures are REPORTED, not verified against the Department's own notice).
Helping sellers register is a scope jump — regulatory education Hami
will not pioneer. The real legal read (including whether Hami-as-platform
needs registration when it takes a cut) comes with company registration,
not from the agent.
