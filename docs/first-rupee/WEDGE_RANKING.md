# Wedge ranking — D1–D100, evidence-labelled

**QA revision:** 2026-10-23. This is a decision aid, not a market measurement. Sources are the tracked `docs/UNKNOWN_MAP.md` D1–D100, existing sprint/brief/expansion documents, and current public signal checks.

## Scoring rule

Scores range 1–5; higher means more favourable for a 14-day test, not higher objective pain. Ranking uses a judgement-weighted lens: pain/gap 25%, frequency 15%, reachability 20%, regulatory safety 15%, testability 25%. Every score names its evidence class. Evidence for the score is not proof of seller ground truth.

- **OBSERVED:** a public post, page, forum thread, warning or public listing contains the signal. It does not represent the whole market or a specific merchant’s losses.
- **SUPPORTED:** an appropriate primary source or multiple-source context supports the existence of a mechanism/rule, not necessarily Hami-specific demand.
- **REPORTED:** attributed company/individual/press claim, not independently audited.
- **HYPOTHESIS / UNKNOWN:** requires first-hand real-world evidence and/or a measured outcome.

Reachability means a lawful, practical path to a consented conversation—not that a public page is discoverable. No seller has yet had a real conversation with Hami; all claims about slow replies, missed sales, willingness to try and willingness to pay remain UNKNOWN/HYPOTHESIS.

## D1–D100 clusters — score every dimension

| Cluster and map rows | Pain / gap | Frequency | Reachability | Regulatory safety (5 = safer) | 14-day testability | Decision note |
|---|---|---|---|---|---|---|
| **A. Missed/slow inquiry → order outcome** (D1–D2, D11–D13, D71, D78, D89–D92) | 3 (OBSERVED DM/order workflow; pain HYPOTHESIS) | 3 (OBSERVED repeated DM-order patterns; losses UNKNOWN) | 2 (OBSERVED public pages; consented access UNKNOWN) | 3 (HYPOTHESIS; non-commercial discovery only until D72) | 4 (HYPOTHESIS if owner gets consented baseline) | First hypothesis: narrow, observable inquiry→order path; public captions do not prove lost sales. |
| **B. Payment-confirmation trust** (D14, D18–D21, D79–D82) | 3 (OBSERVED scam warnings/workflows; seller cases UNKNOWN) | 2 (HYPOTHESIS; actual incident rate unknown) | 2 (OBSERVED merchant pages; permission UNKNOWN) | 3 (HYPOTHESIS; no funds held but operational questions remain) | 3 (HYPOTHESIS; ask first-hand incidents) | Adjacent fallback; warnings alone do not prove merchant-level frequency. |
| **C. COD refusal/RTO + settlement** (D24, D60–D64, D100) | 3 (OBSERVED COD/shipping claims; costs UNKNOWN) | 2 (HYPOTHESIS; refusal/settlement distribution unknown) | 2 (OBSERVED pages; contact path/consent UNKNOWN) | 3 (HYPOTHESIS; observation only, not money handling) | 4 (HYPOTHESIS; last-five-order reconstruction can test it) | Closest pivot; reuse same seller and transaction stages. |
| **D. E-commerce registration/compliance help** (D16, D72–D77) | 3 (SUPPORTED duties exist; individual pain UNKNOWN) | 2 (OBSERVED vendors advertise help; buyer need UNKNOWN) | 3 (OBSERVED public vendor/official content; seller access UNKNOWN) | 1 (SUPPORTED legal/competence exposure; D72 open) | 1 (HYPOTHESIS; no advice/paid service before counsel) | Do not choose until qualified Nepali legal/accounting review clears scope. |
| **E. Merchant finance / stock credit** (D23–D24, D43–D46, D83) | 4 (REPORTED credit squeeze; no seller first-hand evidence) | 3 (REPORTED press/product pages; base rate UNKNOWN) | 2 (HYPOTHESIS) | 1 (SUPPORTED risk class; Hami must not act as lender) | 1 (HYPOTHESIS; poor 14-day verify path) | Excluded from first-rupee experiment. |
| **F. Ledger/bookkeeping** (D25, D31–D34) | 1 (SUPPORTED category served; distinct gap unproven) | 4 (REPORTED adoption/use claims; metrics not audited) | 3 (OBSERVED public product availability; switching intent UNKNOWN) | 5 (HYPOTHESIS for passive demo only) | 1 (HYPOTHESIS; clone lacks 14-day differentiation proof) | Do not build a generic khata clone. |
| **G. Presence / owner-time tax** (D5, D26, D55–D59, D99) | 3 (OBSERVED essays/listings; local magnitude UNKNOWN) | 3 (OBSERVED recurring narratives; prevalence UNKNOWN) | 1 (HYPOTHESIS; diffuse segment and path) | 4 (HYPOTHESIS for observational research) | 2 (HYPOTHESIS; hard to tie to a payable single action) | Possible cause behind A/C, not a validated standalone product. |
| **H. Seasonal/festival stock risk** (D39–D42, D97–D98) | 4 (REPORTED 2026 disruption; seller-level cost UNKNOWN) | 2 (OBSERVED seasonality; not continuous) | 2 (HYPOTHESIS) | 3 (HYPOTHESIS) | 1 (SUPPORTED timing issue: Dashain period has passed) | Not suited to next 14-day test. |
| **I. Migration-fee trust** (D65–D70) | 5 (REPORTED serious harm; each case still needs proof) | 3 (REPORTED across sources; population rate UNKNOWN) | 1 (HYPOTHESIS; different network/trust channel) | 1 (SUPPORTED heightened legal/reputational risk) | 1 (HYPOTHESIS) | Excluded from this sprint; licensed/qualified actors required. |
| **J. Repair-trade capacity/delegation** (D27–D30) | 3 (OBSERVED public accounts; generality UNKNOWN) | 2 (HYPOTHESIS) | 2 (OBSERVED directories/posts; consent UNKNOWN) | 4 (HYPOTHESIS for discovery-only work) | 2 (HYPOTHESIS; core repair may not be delegable) | Potential later test; no evidence it beats A now. |
| **K. Export constraints** (D84–D88) | 4 (REPORTED exporter/state constraints; case attribution UNKNOWN) | 2 (HYPOTHESIS) | 1 (HYPOTHESIS) | 2 (HYPOTHESIS; trade-compliance sensitivity) | 1 (HYPOTHESIS; long state-to-state dependency) | Not a micro-test for 14 days. |
| **L. Marketplace/platform economics** (D47–D49) | 2 (OBSERVED platform narrative; gap UNKNOWN) | 2 (HYPOTHESIS) | 2 (HYPOTHESIS) | 3 (HYPOTHESIS for observation-only) | 1 (HYPOTHESIS; too broad to test fast) | Do not infer a Hami wedge from platform headlines alone. |
| **M. Jeweller formalization** (D50–D54) | 3 (REPORTED trade reporting; first-hand pain absent) | 2 (HYPOTHESIS) | 2 (HYPOTHESIS) | 2 (SUPPORTED documentation sensitivity) | 2 (HYPOTHESIS) | Narrow and paperwork-sensitive. |
| **N. Disaster/hazard/grid information** (D93–D96) | 5 (SUPPORTED high consequence; specific avoidable value UNKNOWN) | 1 (HYPOTHESIS for immediate paid frequency) | 1 (HYPOTHESIS) | 2 (SUPPORTED authority/high-consequence limits) | 1 (HYPOTHESIS; intervention/revenue path unproven) | Continue independent research, not first rupee. |

## Top three and kill criteria

### 1. A — Missed/slow inquiry → order outcome
First because it has a narrow observable path (inquiry → reply → order → payment/delivery/outcome), can use the existing inbox commitment log, and does not require Hami to hold money. **This is the first hypothesis, not a validated winner.** Public DM-to-order pages establish only channel structure; they do not establish response delay or revenue loss.

**Kill early if any one occurs:** (a) zero of the first five genuine owner-contacted sellers agree to a consented baseline; (b) a properly counted baseline shows fewer than 10% of inquiries are unanswered/slow under a pre-agreed definition; or (c) a consented trial week recovers zero independently supported sales. Under the mission rule, if at day 14 there is neither a payment nor a written commitment to pay, declare A dead. The field clock remains unstarted until owner-approved contact and real field activity.

### 2. C — COD refusal/RTO + settlement timing
Same sellers/orders can produce evidence; the minimum useful sample is the seller’s last five recent COD orders, refused deliveries, and time until settlement actually reaches the seller. COD claims themselves do not establish losses.

**Kill condition:** across the first five real seller conversations, sellers’ own recent-order reports consistently show refusal/RTO below ~5% and settlement at or before 48 hours. Do not keep the wedge alive on courier marketing claims alone.

### 3. B — Payment-confirmation trust
Fits Hami’s evidence/verification capabilities, but first-hand incidents are missing; public scam warnings do not estimate merchant-level frequency.

**Kill condition:** fewer than two of the first five interviewed sellers report an actual false payment screen/screenshot incident from their own experience. If fewer than two do, drop B below other candidates.

## Challenge to A

Nothing in public-source research proves that A is commercially superior to C or B. These three remain close and the seller-level frequency is unknown. A remains the first test because its baseline and possible outcome can be measured at low build cost without taking custody of money. If the first interviews show that fulfillment or COD settlement—not reply latency—is binding, switch based on that evidence instead of defending the original thesis.

Recent public reporting indicates social commerce is an active channel, not that Hami has demand: [The Kathmandu Post, 28 Sep 2026](https://kathmandupost.com/money/2026/09/28/dashain-sales-move-from-shopfronts-to-social-media). TikTok’s current U.S. Terms (last updated 15 Jul 2026) prohibit automated scraping/extraction absent written approval: [official TikTok terms](https://t.tiktok.com/legal/page/us/terms-of-service/en). This QA used indexed public search results and published pages only; it did not log in, automate platform extraction, bypass controls, or send messages.

The official [Department of Commerce page for Nepal’s Electronic Business (E-Commerce) Act 2081](https://doc.gov.np/content/324/electronic-business--e-commerce--act--2081/) establishes that the Act exists. Its application to Hami’s proposed paid intermediary role remains a D72 question for qualified Nepali legal/accounting review. No paid service or compliance advice before that gate clears.
