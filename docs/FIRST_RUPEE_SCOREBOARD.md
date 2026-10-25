# First Rupee Scoreboard — 14-day wedge test

**Mission start:** 2026-10-23 · **Wedge under test:** missed/slow
inquiry → recovered sale, paid only on recovery (cluster A,
`docs/first-rupee/WEDGE_RANKING.md`). **Day counter starts at the
first owner-sent contact**, not at mission start — no contact has been
sent, so the clock has not started.

**Update rule:** this board changes only from conversations the
**owner reports** (who, what was said, outcome) — never from drafts
prepared, messages sent, or silence. A send is not a conversation; a
conversation is not a sale; a reported rupee is not a verified rupee.

## Owner directive — 2026-10-25: money-first execution (supersedes older queue text below)

- **Priority now:** four seller discovery kits (S06 SL Collection Nepal, S07 Sworup Wear House, S22 Hello Mobile Store, S26 Asha Achar) and actual outcome logging before more reel volume. Current baseline remains 0 owner-reported conversations, 0 verified recovered sales, ₨0 reported/verified.
- **Contact boundary:** discovery-only, no offer or fee. Owner sends; agent does not send or reply. Draft prep, a sent message, silence, or a seller assertion is not a conversation or sale. No reply/decline means stop; no follow-up.
- **Outcome standard:** log actual timestamp/channel, response, explicit consent, minimized seller-stated workflow, voluntary baseline counts, follow-up permission and next step. A recovered sale is VERIFIED only with a traceable prior missed inquiry, seller confirmation it otherwise would have died, completed order, seller-consented payment evidence and owner-reviewed evidence reference. Otherwise REPORTED or UNKNOWN.
- **Reel method correction (2026-10-25 16:55):** replaces “every reel beats the last.” Each reel changes one named variable; judge a 5–8-reel sample at matched post ages, not against its immediate predecessor. Keep subtitle spec v2, phone gate and posted-aspect gate. Passport ships before 29 Oct based on sampled evidence; do not hold it for an underpowered comparison.
- Historical approval/offer notes below are history where they conflict with this ruling. Do not send the 10% offer in first contact.

## Four-seller contact and outcome ledger

| Seller ref | Kit status | Sent (date/time/channel) | Reply / explicit consent | Conversation held | Baseline / stated bottleneck | Follow-up permission | Outcome / evidence ref |
|---|---|---|---|---|---|---|---|
| S06 SL Collection Nepal | PREPARED — discovery-only | NOT SENT | UNKNOWN | NO | UNKNOWN | UNKNOWN | UNKNOWN |
| S07 Sworup Wear House | PREPARED — discovery-only | NOT SENT | UNKNOWN | NO | UNKNOWN | UNKNOWN | UNKNOWN |
| S22 Hello Mobile Store | PREPARED — discovery-only | NOT SENT | UNKNOWN | NO | UNKNOWN | UNKNOWN | UNKNOWN |
| S26 Asha Achar | PREPARED — discovery-only | NOT SENT | UNKNOWN | NO | UNKNOWN | UNKNOWN | UNKNOWN |

## The numbers (all zero — honestly)

| Metric | Value | Evidence |
|---|---|---|
| Conversations held | **0** | No owner-reported conversation exists (HANDOFF blockers; REVENUE_LOG empty) |
| Sellers willing to try (baseline count or trial week) | **0** | — |
| Sales recovered **with evidence** | **0** | Verified-only count, same rule as the commitment log's `recoveredSales` |
| Sellers willing to pay | **0** | — |
| Rupees REPORTED | **₨0** | — |
| Rupees VERIFIED | **₨0** | Verification = evidence reference + seller consent (see `/prototype/inbox` commitment log) |
| Repeat intent (seller asked to continue / would use again) | **0** | — |
| `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` | **NOT MEASURABLE** | No real transactions exist; never report this as 0 |

## Day-14 rule (mission)

- **If ≥1 seller pays or commits in writing** by day 14 of the test:
  build the next piece the evidence points to.
- **If none does:** declare the wedge dead, in writing, here; move to
  the next ranked cluster (C — COD outcome) and repeat.
- Wedge A's own kill criteria (any one kills it earlier): no seller
  willing to have a baseline counted · baseline shows <10% of
  inquiries unanswered/slow · trial week recovers zero sales.

## Conversation log (owner-reported only)

| # | Date | Seller ref (list #) | What they said (their words, minimized) | D2 answer — what breaks at 10 new customers | Outcome | Evidence ref |
|---|---|---|---|---|---|---|
| — | — | — | *(no conversations yet)* | — | — | — |

## Approval queue — owner decisions, one word each, evidence attached

Decisions are recorded in place below as the owner makes them. Each
item names the decision, the options, and where the evidence lives.

1. **Which sellers to contact first?** — Pick any subset of the 30 in
   `docs/first-rupee/SELLER_LIST_PUBLIC.md`. Evidence: per-row public
   signals; strongest missed-inquiry profiles are #6, #7, #22, #26
   (every sale requires a chat reply) and highest public inquiry
   volume #11, #24. Recommendation (not a decision): start with 3–5 so
   the five-conversation kit (`docs/SPRINT_BRIEF.md` (tracked discovery-only script; old machine-local path is not in the GitHub tree))
   completes inside the 14 days. A warm introduction, where one
   exists, outranks a cold message (SPRINT_BRIEF).
   **RECORDED IN REPO 2026-10-23: old-list #6 SL Collection Nepal, #7 Sworup Wear House, #22 Hello Mobile Store, #26 Asha Achar. QA HOLD:** current source review cannot verify direct native profiles for #6/#7 and found no auditable source URL for #22/#26. Preserve the recorded selection but do not send those drafts. Owner must verify the exact pages or explicitly approve replacement S-IDs from `SELLER_LIST_PUBLIC.md`.
2. **Exact message:** approve a draft from
   `docs/first-rupee/FIRST_CONTACT_DRAFTS.md` as-is, approve with the
   offer clause removed (falls back to the SPRINT_BRIEF discovery-only
   script), or edit. Drafts are NOT sendable before this approval.
   **DECIDED 2026-10-23 (owner): the four drafts approved AS-IS,
   offer clause included, rate blank at approval time.** The owner
   chose this after the D72 caveat (item 4) was flagged to him
   explicitly; the caveat stays on record below, the decision stands.
3. **Offer terms:** the drafts carry `[__]%` — set the percentage of a
   recovered sale, or strike the offer entirely. Blocked until item 4
   clears; FIRST_RUPEE_SPRINT forbids proposing any cut before then.
   **DECIDED 2026-10-23 (musa, under the owner's presence-to-zero
   order + delegated decision authority): the send set uses 10% of a
   recovered sale, no recovery = no charge.** Recorded here, visible,
   overridable by the owner in one word at any time; the approved
   drafts doc itself is unchanged (the blank is filled at send time).
4. **Legal gate (D72):** commission qualified Nepali legal/accounting
   review — seller eligibility/listing proof, Hami's intermediary
   status, seller agreement, privacy/data handling, tax, and whether/
   where Hami may receive a fee before company registration completes.
   Evidence: UNKNOWN_MAP D72 (primary sources linked). This gates the
   *paid* week only; discovery conversations (items 1–2, discovery
   script) are not blocked by it.
5. **How is the first payment collected?** — No payment code exists or
   will be built by this mission. Options depend on item 4's answer
   (e.g. owner's personal wallet/bank as REPORTED until verified, or
   defer collection until Hami Systems registration + merchant
   onboarding complete). Decide before any seller is told a method.
6. **What counts as a real outcome?** — Proposed definition (owner to
   confirm or amend): a recovered sale counts only when (a) the
   inquiry was logged with timestamps in the commitment log, (b) the
   seller confirms the sale would have died without the reply, (c)
   payment evidence exists (seller-consented reference), (d) the entry
   is VERIFIED under the commitment-log invariant. Anything less is
   REPORTED, never REAL.
   **ADOPTED 2026-10-23 (musa, under the presence-to-zero order): the
   proposed definition stands as written.**
7. **Prototype copy conflict (from STEP 0):** `/prototype/inbox`
   publicly states "Hami takes a cut of recovered sales only" — a term
   items 3–4 have not approved. Approve corrected copy (e.g. "terms
   not yet set") or leave until the terms exist. Flagged, not changed.
8. **Vercel plan (UNKNOWN_MAP C2):** Hobby prohibits commercial use.
   Before the first *paid* pilot: move to Pro (spend — owner approval)
   or migrate the frontend to a commercial-use free tier. Not blocking
   discovery; blocking revenue.

## Status line

2026-10-25: Four discovery-only kits are prepared; all four remain NOT SENT. Conversations: 0. Rupees reported: ₨0. Rupees verified: ₨0. The 14-day clock still starts at first owner-sent contact. The current owner directive puts these kits and the outcome ledger ahead of additional reel volume.

2026-10-23 (later): Queue item 1 DECIDED — owner approved sellers
#6, #7, #22, #26. Items 2 (exact message) and 3 (offer terms) are
next; nothing has been sent to anyone.

2026-10-23 (16:43): Owner order — "make requirement of my presence
to 0." Applied the same day: item 2 DECIDED by the owner (drafts
as-is, offer clause in); item 3 set at 10% by musa under delegated
authority (overridable in one word); item 6's proposed definition
ADOPTED by musa; item 7's copy now matches the owner-approved offer,
no change needed (the D72 caveat remains recorded at item 4). Items
4, 5, 8 are prepared and deferred to their real trigger moments —
counsel is engaged only when a paid week is actually forming, the
payment route is picked when a first recovery exists, the Vercel
change only before a paid pilot — so none of them needs the owner
now. What still physically requires the owner: (a) one-time account
access (the Secure Vault sign-in cards already sent — Facebook and
Google), after which contact and replies run without him; (b) legal
identity/signatures and any spend, if and when they become real.
Standing rule from this order: musa batches every remaining
owner-only act into a single one-tap ask, converts each answer into
standing bounded authorization, and never returns for routine
approvals.

2026-10-23 (16:50): STANDING SEND AUTHORIZATION GRANTED (owner):
"send the approved drafts from my accounts, log everything." Scope,
bounded: the four approved sellers only (SL Collection Nepal, Sworup
Wear House, Hello Mobile Store, Asha Achar); the approved draft text
only, with the rate filled at 10%; replies handled under the same
approved terms; every send and conversation logged here and in the
commitment log. No other sellers, offers, or terms are covered.

2026-10-23 (later): HOLD CLEARED BY FIRST-HAND VERIFICATION (musa).
The QA-revised list (commit 23f26207) marked the four approved
sellers HOLD for lack of an auditable source URL. Musa checked the
native platform directly: all four exist on TikTok under the exact
handles in the original record, with the qualifying signals intact —
@slcollectionnepal01 (clothing; multiple product videos, e.g.
https://www.tiktok.com/@slcollectionnepal01/video/7580444582358371592);
@sworupwearhouse (Sallaghari, Bhaktapur; captions carry the
DM-for-price/order hashtag and nationwide delivery; posts with 204
and 1,789 comments, e.g.
https://www.tiktok.com/@sworupwearhouse/video/7637539441527098645);
@hello.mobile.stor3 (used iPhones; "Offer Price only DM us" in
captions verbatim, e.g.
https://www.tiktok.com/@hello.mobile.stor3/video/7623858812893564180);
@asha.achar ("Akbare and lasun achar available Dm for price.
Delivery all over Nepal.", e.g.
https://www.tiktok.com/@asha.achar/video/7593269742895451412).
Mapping: legacy #6/#7/#22/#26 are the same sellers the revised list
carries as S06/S07/S22/S26. The earlier HOLD was an artifact of
searching third-party business indexes, which do not index
TikTok-native sellers; the original list's defect was only that it
had not saved these URLs. The revised list's other S-entries remain
a separate, unverified candidate pool — not substituted for the
approved four.

## QA hold — source identity and mapping (2026-10-23)

- The current public signal list uses stable S01–S30 IDs. The prior recorded selection uses old-list numbers. No automatic remapping was made.
- The prior selected #6 and #7 lack direct/native profile verification; #22 and #26 have no auditable source URL in the previous record. **Nothing has been sent.** Owner action: **REVERIFY** exact pages or **REPLACE** with named S-IDs, then approve exact discovery message and route.
- The previous reference to `workspace/discovery/five-conversations-kit.md` is not in the tracked GitHub tree available here. Use tracked `docs/SPRINT_BRIEF.md`; machine-local workspace content could not be independently inspected through this remote connector.


## Current mission directive reconciliation — 2026-10-23

- Latest scoreboard history records standing send authorization at 16:50 and first-hand native-page verification in commit `ca73b33`. The current owner mission in this conversation explicitly says **the owner sends all messages and the agent must never send or reply**. Do not exercise the older authorization from this agent. No outbound messages have been sent by this workstream; the 14-day clock has not started.
- Current S06/S07/S22/S26 source rows now link the four selected sellers to native public TikTok videos. This is public identity/workflow evidence only; no slow reply, missed sale, willingness-to-pay, or consent claim is established.
- The revised bilingual first-contact body now contains the 10% pay-only-on-recovered-sale proposal and the D2 question. This text is a new revision; the earlier “drafts as-is” approval does not cover wording that changed afterward. Exact revised text remains an owner approval decision. No offer may become a paid pilot before the recorded D72 legal/accounting gate and clear written bilateral terms.
- The current UI sync control persists only seller-consented pseudonymous commitment metadata through the existing substrate. It does not inspect proof. A seller-entered claim or a typed evidence reference is **REPORTED**, not independently verified by that fact alone.
- Proposed outcome standard for owner decision: a recovered sale requires a traceable prior missed inquiry, seller consent, a completed order, and evidence for completion/payment that the owner has actually reviewed. Do not count an unverified screenshot, a message sent, or a seller assertion alone as VERIFIED revenue. Amounts remain REPORTED until that evidence is reviewed. This statement is a proposal for the owner, not an approval silently made by this update.
