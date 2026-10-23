# Item 1 — Wedge ranking (D1–D100 clusters)

**Date:** 2026-10-23 · Scores are 1–5 (5 = most favorable for a 14-day
test). Every score carries its evidence class. Unless stated otherwise,
the underlying evidence is **OBSERVED online discourse at best** —
public threads, press, and seller captions — never Kathmandu ground
truth. Only real conversations upgrade these classes; that is what the
14 days are for.

**Scoring dimensions:** Pain (how much it hurts, in the seller's own
observed words) · Frequency (how often it occurs) · Reachability (can
the owner reach affected sellers through public channels in days) ·
Regulatory safety (5 = lowest legal exposure for a $0, no-funds-held
test) · 14-day testability (can a yes/no answer be produced in 14 days
with a human, no build).

## Clusters and scores

| Cluster (D-rows) | Pain | Freq | Reach | Reg. safety | 14-day test | Evidence class for the scores |
|---|---|---|---|---|---|---|
| **A. Missed / slow inquiry → lost sale** (D1, D2, D11, D12, D13, D71, D78, D89, D90, D91, D92) | 4 | 5 | 5 | 4 | 5 | OBSERVED: sellers' own "can't keep up" statements (D12), coping-announcement reels (D90), "DM for price" funnels forcing every sale through a chat thread (D17, confirmed in this mission's seller sample); D78's ~30% unanswered figure is a single feed-reported observation — HYPOTHESIS for size |
| **B. Payment-confirmation trust** — fake "success" screens, fake screenshots (D14, D18, D19, D20, D21, D79, D80, D81, D82) | 5 | 3 | 4 | 4 | 3 | OBSERVED: scam warnings by Nepali creators (D19), FoneBiz 2.73★ counter-friction complaints (D20), manual-QR + screenshot checkout observed in the wild (D82). Frequency of actual fraud per seller is UNKNOWN — no seller testimony yet |
| **C. COD outcome: refusal/RTO + settlement float** (D24, D60, D61, D62, D63, D64, D100) | 4 | 5 | 5 | 4 | 4 | OBSERVED: courier claims vs seller memes ("COD = Cancel on Delivery", D61); every seller in this mission's sample offers COD all over Nepal. Actual RTO % and remittance days are UNKNOWN until sellers report them |
| **D. E-Commerce Act registration / compliance help** (D16, D72–D77) | 4 | 4 | 5 | 2 | 3 | SUPPORTED that duties exist (primary sources, D72); OBSERVED that vendors already sell compliance help (D76) and the first deadline drew only ~950 listings (D73). Hami has no verified legal competence — advising on compliance without counsel is itself the risk |
| **E. Merchant finance: co-op float, stock credit** (D23, D24, D43–D46, D83) | 5 | 4 | 3 | 1 | 2 | OBSERVED (press + co-op product pages). Any wedge here touches lending/credit — Hami's commercial rule forbids a lender role; testability inside 14 days is low |
| **F. Ledger / bookkeeping** (D25, D31–D34) | 3 | 5 | 5 | 5 | 1 | SUPPORTED that the corner is taken: Karobar, 500k+ installs, profitable (numbers REPORTED). Building here competes with a proven local incumbent — rejected, per FIRST_RUPEE_SPRINT |
| **G. Presence / owner-time tax** (D5, D26, D55–D59, D99) | 4 | 5 | 4 | 5 | 2 | OBSERVED essays/listings. Real but diffuse: it is the *cause* behind cluster A more than a separately sellable wedge; no clean 14-day outcome measure |
| **H. Festival stock risk** (D39–D42, D97, D98) | 5 | 2 | 3 | 4 | 1 | OBSERVED (press on the broken 2026 season). Seasonal — the Dashain window has just passed; no test can run in the next 14 days |
| **I. Migration-fee trust** (D65–D70) | 5 | 4 | 2 | 1 | 2 | OBSERVED (press/Amnesty). Different customer (workers, not sellers), heavy regulatory and reputation exposure; repo AGENTS.md requires licensed-agency-only + extra review. Not a 14-day seller wedge |
| **J. Repair-trade capacity** (D27–D30) | 4 | 3 | 3 | 5 | 3 | OBSERVED (one training-institute page, one owner comment). D29 suggests the core work may be non-delegable — which would kill a capacity wedge for this trade specifically, not generally |
| **K. Export constraints** (D84–D88) | 4 | 2 | 2 | 3 | 1 | OBSERVED/REPORTED (customs data, one exporter account). D87: the binding constraints are state-to-state; no seller-facing 14-day test exists |
| **L. Marketplace economics** (D47–D49) | 3 | 3 | 2 | 4 | 1 | UNKNOWN states; the subjects are platforms, not reachable sellers with a payable pain |
| **M. Jeweler formalization** (D50–D54) | 3 | 2 | 2 | 2 | 2 | OBSERVED (trade press). Narrow, high-value, paper-trail-sensitive trade; poor first-wedge fit |
| **N. Disaster / hazard / grid information** (D93–D96) | 5 | 1 | 1 | 2 | 1 | L1/L2 orientation evidence only. High consequence, no revenue path, no authority to intervene — explicitly not a first-rupee wedge |

## Top 3

### 1. Cluster A — missed / slow inquiry (the mission thesis)
Total 23/25. The only cluster that is simultaneously high-frequency,
reachable this week through public seller pages, testable with a human
and ₨0 of build, and measurable in rupees (recovered sale = an order
that would have died). **Honest challenge, from the repo's own
evidence:** D71 shows unified-inbox *tools* already exist, and D78
suggests a hand-kept shared list — discipline, not software — may be
the actual fix. So the wedge under test is not "an inbox product"; it
is **a human reply service paid only on recovered sales**, with the
inbox prototype as the log. If a free list does the job, the service
has no edge and the thesis dies honestly.
**Kill criterion:** by day 14 — zero sellers (of those the owner
contacts from the approved list) willing to let a baseline week be
counted, OR a counted baseline shows <10% of inquiries unanswered/slow,
OR a trial week recovers zero sales. Any one kills the wedge.

### 2. Cluster C — COD outcome (refusal at the door + days-to-cash)
Total 22/25. Every sampled seller ships COD nationwide; refusal and
remittance lag are pure margin loss on sales already won. The testable
service shape is pre-dispatch confirmation + an outcome log — adjacent
to cluster A's channel and skills, so it is the natural pivot if A
dies. **Kill criterion:** in the first five seller conversations,
sellers report refusal/RTO under ~5% of COD orders AND settlement at
≤48 hours consistently — no pain, no wedge.

### 3. Cluster B — payment-confirmation trust
Total 19/25. Highest single-moment pain (goods handed over against a
fake screen = total loss of that sale), and it fits Hami's EVIDENCE
primitive exactly. It ranks third because frequency is unproven (press
and warnings, no seller testimony) and a trustworthy aid must work on
the merchant's own device at the counter — the hardest 14-day test of
the three. **Kill criterion:** fewer than 2 of the first five sellers
report a fake-screen/fake-screenshot incident from their own experience
(not "heard of it") — then the pain is media, not ground truth, and the
cluster drops below D.

**Challenger noted honestly:** cluster D (registration help) has real,
dated, state-created demand and vendors already charging for it. It
does not beat A for *this* mission because Hami cannot lawfully or
credibly sell compliance help before the D72 counsel answer exists —
the same gate that blocks the paid pilot. If counsel clears a
registration-help offer, D should be re-scored; it may become the
fastest *lawful* rupee even if A wins the test.

## Verdict on the thesis

The missed-inquiry thesis **survives the challenge, narrowed**: the
atomic unit is the verified commitment (inquiry → order → payment →
delivery → outcome, logged with consent), the product under test is
human reply labor paid only on recovery, and the inbox tool is the log
— not the offer. D2 ("what breaks if 10 new customers arrive
tomorrow?") remains the thesis-threatening question and goes first in
every conversation, because if the answer is fulfillment/presence
rather than replies, cluster A is wrong for that seller's segment and
the ranking must be re-cut by segment (D11).
