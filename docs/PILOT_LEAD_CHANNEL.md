# Pilot lead channel — decision record

**Date:** 2026-10-04
**Status:** DECIDED — by owner-delegated authority (musa), 2026-10-04.
Channel 1 confirmed as the pilot lead channel. Channel 2 remains the
built, tested stage-2 path, to be opened only when the five conversations
reveal a pattern worth systematizing.
**Evidence boundary:** this document records the decision. It authorizes
nothing beyond the decision itself. Intake stays closed until the
activation prerequisites are met.

## The question

Where does a real business/customer lead actually arrive? Until exactly one
real, authorized, zero-cost channel is selected and documented, Forge Bot
cannot transition from design to a real pilot. `FORGE_BOT_LIVE` stays CLOSED.

## Candidate channels

### 1. Owner-run conversations (in-person / direct)

- **Source:** conversations the owner has directly with business owners
- **Consent:** verbal, in the moment, noted by the owner
- **Intake format:** owner notes, entered into the console as observed demand
- **Owner visibility:** immediate — the owner is the channel
- **Acknowledgement method:** the conversation itself
- **Retention:** owner notes; system retention rules apply once entered
- **Handoff:** the owner decides on the spot
- **Cost:** $0
- **Note:** this is already the documented plan — the owner reports five real
  conversations before any digital intake is considered.

### 2. Existing web form (Forge Bot intake, currently closed)

- **Source:** `/forge-bot-intake` on the production domain
- **Consent:** explicit form consent, versioned (`forge_bot_web_form_v1`)
- **Intake format:** structured fields; contact/consent kept separate from
  public signal data
- **Owner visibility:** owner console
- **Acknowledgement method:** synchronous in-page receipt (implemented, tested)
- **Retention:** 30-day purge for unactioned leads
- **Handoff:** owner reviews in console; any response ACTION requires explicit
  owner approval and a separately authorized sender path
- **Cost:** $0
- **Note:** built, tested, closed. The digital path when the owner is ready.

### 3. WhatsApp (Cloud API)

- Plausibly $0 at pilot scale (1,000 free conversations/month), but requires a
  phone number, Business API setup, and webhook handling Hami does not have.
  The response path must live on WhatsApp too. Real setup cost in time and
  moving parts before the first outcome. Not recommended before the first
  real outcome.

### 4. Facebook Messenger / Email

- Messenger API is free; email via Gmail is $0. But Messenger needs a Page and
  app setup steps, and email needs the monitored mailbox that is not
  established. Both add infrastructure before the first real lead. Not
  recommended before the first real outcome.

## Recommendation

**Channel 1 first, then channel 2.** The first pilot is owner-run discovery:
five real conversations, zero infrastructure, zero pretense. The unknown the
project is after lives in what those five owners say that was not expected —
not in the channel itself. When those conversations reveal a pattern worth
systematizing, channel 2 is built, tested, and waiting to be opened.

## After each conversation (surprise log)

Record four lines:

1. Who, and when.
2. What they said that was not expected.
3. What would have been guessed before.
4. One question this raises.

After three or four entries, bring them to the reasoning layer to turn into
hypotheses and the smallest real test for each.

## Decision required from the owner

- [x] ~~Confirm channel 1 (owner-run conversations) as the pilot lead channel,
      or select a different channel from the candidates above.~~
      **DECIDED 2026-10-04 (owner-delegated): channel 1 confirmed.**
- [x] ~~Only after channel confirmation: establish the zero-cost response path
      on the same channel before opening any intake.~~
      **DECIDED 2026-10-04 (owner-delegated): the response path is the
      conversation itself — direct human reply on the same channel, $0,
      no new infrastructure before the first real outcome.** Protocol: the
      person who holds the conversation replies in that conversation;
      anything worth keeping is entered into the console as observed
      demand with the surprise-log four lines. For channel 2 (when opened):
      owner manual reply from the console; any automated sender needs a
      separately authorized sender path, which does not exist yet.

## Execution note

Channel 1 needs a human to hold the conversations — the delegate kit
(`docs/DELEGATE_KIT.md`) is ready; no delegate named yet. The decision is
made; the conversations themselves are human work and cannot be delegated
to software.
