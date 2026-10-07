# Transaction Funnel Experiment — where online sales actually die

**Status:** PREPARED — awaiting owner-run conversations. **No real-world
contact has occurred.** Nothing in this document is evidence; it is a
procedure for obtaining some.

**Scope guard:** Do NOT code a new product, new SaaS flow, new credit
product, new ledger product, or new Viber integration. Desk-research is
done. The next valuable event is the first real conversation.

## 1. Experiment question

Where does a real online seller's transaction process break?

At minimum, distinguish per episode: no demand/contact · inquiry arrives
but seller does not respond · seller responds but conversation dies ·
buyer does not trust seller · price/terms kill it · payment fails or is
not trusted · seller cannot fulfill · delivery kills it · buyer disappears
· seller declines · transaction succeeds. Do not assume these are the
only failure modes — record what actually happened, then categorize.

## 2. Why this experiment, why now

- Frontier: how small online purchases in Nepal are actually decided,
  buyer and seller side — and where transactions die.
- The suspected leak (slow/unanswered replies) is HYPOTHESIS, not
  evidence. Nepal desk research is L1 orientation only — it must not
  become a Hami fact, decision evidence, or architecture.
- This is the shared collection layer for Bets A, B, and C (all three
  ride the same five conversations; Bet deadlines 2026-10-28).
- Per the operating model, the contact clock is the kernel: at 14 days
  without real contact, all non-obligatory building freezes.

## 3. Existing machinery reused (nothing new built)

- **OutreachDraft / DoNotContact / OutreachConfig** (`backend/app/models.py`):
  contact-attempt tracking with DRAFT → APPROVED → SENT flow. The owner
  approves and sends from their own account; replies and outcomes are
  recorded, never invented. Do-not-contact is checked first.
- **Evidence / Event / Entity substrate**: every observation recorded
  with provenance and an explicit evidence class (REAL / TEST /
  HYPOTHESIS). Renovation Phase 4 added `source_kind` columns and
  REAL-only public statistics — use them.
- **Bet A/B/C test designs** (`backend/app/services/operating_v4.py`,
  `SEED_FOUNDING_BETS`): the five-conversation protocol, the D2/D11/D13
  questions, and the kill criteria already exist — this experiment
  executes them, it does not redesign them.
- **docs/SPRINT_BRIEF.md**: "where to look" and the honesty norms
  (real name, no fake identity, no double follow-up, never spam) are
  reused. Its one-week-test PITCH is explicitly NOT reused here — this
  conversation proposes nothing.
- **docs/DELEGATE_KIT.md**: seller-finding guidance.

## 4. Seller selection criteria

- Economically active: sells online now, receives inquiries regularly
  (weekly or more — there must be a funnel to observe).
- Channel: Facebook / TikTok / WhatsApp commerce. Kathmandu valley
  preferred (meetable if it works).
- **Do NOT select only on visible strain signals.** Selecting only
  sellers who look overwhelmed selects on the dependent variable and
  biases the experiment toward confirming the slow-reply hypothesis.
  Mix: some with strain signals, some apparently coping.
- Segment awareness (D11): include at least one traditional /
  shutter-retail seller if accessible, to test the demand-vs-presence
  split.
- Consent-first, legitimate contact paths only. Public observation
  before contact; no scraping of private information; no impersonating
  buyers; no fabricated demand; no deception about who Hami is.

## 5. First batch: 5 sellers

Five — not twenty. This matches the Bets' shared collection layer and
the owner-time budget (five 10-minute conversations, ≤3h total). Each
conversation yields 2+ concrete funnel episodes, so five conversations ≈
10–15 episodes — enough to see whether one failure mode repeats across
independent sellers. Expandable after the first batch if the evidence
warrants it.

## 6. Conversation procedure (owner-run, ~10 minutes each)

Neutral. No pitch. No intervention offered. No promises.

1. **Who we are:** your real name; "I'm working with Hami, a Kathmandu
   project studying how shops actually sell." State it is research, not
   a sales call, and they can stop anytime.
2. **D2 first:** "If I brought you 10 new customers tomorrow, what
   breaks?" (Treat the answer as reported belief, not proof.)
3. **Two histories (D11):** "Tell me about the last time you had too
   few customers" vs "the last time customers wanted to buy and you
   could not keep up." (Segments demand-constrained vs
   presence-constrained sellers.)
4. **Funnel walkthrough (the core):** "Walk me through your last 5
   sales, step by step — how did each one actually close?" Then: "Tell
   me about the last 2–3 inquiries that did NOT become sales — what
   happened at each step?" Concrete episodes, not general opinions.
5. **Stage probes** — only where the walkthrough points: response
   latency, trust, price/terms, payment, fulfillment, delivery.
6. **Bet B:** "In the last 30 days, how many times has someone shown
   you a payment confirmation you had to verify? Did a real dispute
   happen? How did you check?" (Reported incidence, 30-day window —
   never a population frequency claim.)
7. **Bet C** (if relevant): "I notice many sellers don't put prices on
   posts — do you? Does it bring more serious buyers?"
8. **Close:** ask permission for one follow-up; thank them for their
   time.

Rules: open questions only. Never lead with "is slow reply your
problem." Write down their words; do not paraphrase into our thesis.
If they ask what Hami sells: "Nothing right now — we're studying
first."

## 7. Data to record (per conversation)

- Seller ref (pseudonym if they prefer), date/time, channel, consent
  given (y/n), duration.
- Per episode: funnel stage reached, where it stopped, seller-stated
  reason, any observed behavior, evidence class, confidence.
- Running funnel-stage counts across all episodes.
- Follow-up permission (y/n). Nothing else — no customer data beyond
  what the conversation needs.

Record in the Evidence/Event substrate with provenance. Contact
attempts go through the OutreachDraft flow.

## 8. Evidence / proof rules

- **REAL:** directly observed, or directly reported by a consenting
  participant, with provenance. Seller-stated reasons are REAL
  (reported) — but reported belief is NOT behavioral proof.
- **TEST:** an experiment Hami ran that is not itself a real customer
  outcome.
- **HYPOTHESIS:** believed, not established. Slow replies as the binding
  constraint lives here until evidence moves it.
- **L1 / RESEARCH:** published or secondhand information, orientation
  only. The Nepal desk research stays here permanently.
- Agent reasoning is never evidence. "Estimated recoverable value" is
  an estimate, never revenue — and an unanswered inquiry is not
  observed revenue.

## 9. Kill criteria (slow-reply hypothesis)

Kill or dampen if, after the first batch:
- Sellers consistently report demand — not response — as the binding
  constraint, with behavioral corroboration (they answer fast and still
  do not sell).
- Transaction deaths cluster at other stages (trust, price, payment,
  fulfillment, delivery) with response time never implicated, across
  3+ independent sellers.
- Sellers already respond fast or have help, with no sales lift.
- Bet A kill triggers: conversations + autopsy cannot complete within
  the owner-time budget; or no seller consents and no behavioral data
  can be obtained.
- Dampen (not full kill) if the constraint is segment-specific —
  e.g. demand binds for shutter retail while presence binds for social
  sellers.

## 10. Continue criteria

- The same failure mode repeats across 3+ independent sellers, with
  seller attribution AND/OR behavioral corroboration.
- Sellers raise the pain unprompted, in their own words.
- Then: design the one-week inquiry autopsy (Bet A test step 4) with
  consenting sellers — still observation, not intervention.

## 11. Intervention gate — do NOT build yet

Build nothing until the experiment establishes ALL of:
1. a real recurring leak;
2. a meaningful economic consequence (ACTUAL, or clearly labeled
   ESTIMATED);
3. a plausible minimal intervention;
4. a way to verify the intervention changed the outcome (actual buyer
   payment, completed/delivered order, seller received money, repeat
   purchase — a claimed improvement is not enough);
5. a pay-only-after-value revenue path.

Until then, explicitly NOT built: inbox SaaS, CRM, seller dashboard,
Viber integration, payment ledger, bank integration, credit scoring,
generic lead generation, automated outreach machine. No new
Seller/Experiment/Bet models — the existing primitives and
projections suffice.

## 12. Commercial rule (non-negotiable)

Hami earns only after the customer receives value / earns. No
flat-fee SaaS bridge. No charging for access to an unproven product.
No lender role. No holding customer money. Seller earns or recovers
value → verified → Hami receives an agreed fair share. No upfront
product fee. No invented revenue. No percentage assumption until an
actual commercial arrangement exists.

## 13. Owner action required

1. **Conduct the five conversations** — only a human body can do this.
   One page per conversation, using the §7 fields, reported back
   exactly as it happened.
2. Log contact attempts via the OutreachDraft flow (draft → approve →
   send from your own account).
3. Do NOT authorize the one-week autopsy or any intervention until the
   conversation evidence supports it — that decision comes after the
   first batch, per §9–§11.
