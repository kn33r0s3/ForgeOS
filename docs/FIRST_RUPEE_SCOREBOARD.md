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
3. **Offer terms:** the drafts carry `[__]%` — set the percentage of a
   recovered sale, or strike the offer entirely. Blocked until item 4
   clears; FIRST_RUPEE_SPRINT forbids proposing any cut before then.
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
7. **Prototype copy conflict (from STEP 0):** `/prototype/inbox`
   publicly states "Hami takes a cut of recovered sales only" — a term
   items 3–4 have not approved. Approve corrected copy (e.g. "terms
   not yet set") or leave until the terms exist. Flagged, not changed.
8. **Vercel plan (UNKNOWN_MAP C2):** Hobby prohibits commercial use.
   Before the first *paid* pilot: move to Pro (spend — owner approval)
   or migrate the frontend to a commercial-use free tier. Not blocking
   discovery; blocking revenue.

## Status line

2026-10-23: Mission items 1–5 built and queued. Conversations: 0.
Rupees reported: ₨0. Rupees verified: ₨0. The next event in this
workstream is an owner decision from the queue above — everything
after it (sends, conversations, the 14-day clock) is the owner's hand
on the trigger, by design.

2026-10-23 (later): Queue item 1 DECIDED — owner approved sellers
#6, #7, #22, #26. Items 2 (exact message) and 3 (offer terms) are
next; nothing has been sent to anyone.


## QA hold — source identity and mapping (2026-10-23)

- The current public signal list uses stable S01–S30 IDs. The prior recorded selection uses old-list numbers. No automatic remapping was made.
- The prior selected #6 and #7 lack direct/native profile verification; #22 and #26 have no auditable source URL in the previous record. **Nothing has been sent.** Owner action: **REVERIFY** exact pages or **REPLACE** with named S-IDs, then approve exact discovery message and route.
- The previous reference to `workspace/discovery/five-conversations-kit.md` is not in the tracked GitHub tree available here. Use tracked `docs/SPRINT_BRIEF.md`; machine-local workspace content could not be independently inspected through this remote connector.
