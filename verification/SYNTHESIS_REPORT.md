# Phase E: Evidence-to-Action Synthesis Report

**Date:** 2026-10-05
**Branch:** `phase-e-synthesis`
**Constraint:** No new research. Only recorded material. Additive only.

## 1. CORPUS

### EVIDENCE (what a source actually says)

| ID | Provenance | Text | Source |
|----|-----------|------|--------|
| E1 | primary | Indie Hackers founder: Reddit 563 views → zero signups; Product Hunt → no traffic | deep-listening P1 |
| E2 | primary | Auto-shop owner: "too busy to answer but not busy enough to hire someone" ($35-40k/yr front desk) | deep-listening P3 |
| E3 | primary | Roofer: "By the time I get home to my laptop to make a quote, they hired someone else" | deep-listening P3 |
| E4 | primary | Nepal TikTok (158k plays): "No records = No clarity = No growth" | deep-listening P4 |
| E5 | secondhand | Bangladesh: ~80% of seller pages fraudulent | deep-listening P2 |
| E6 | primary | Tootle (50,000 riders) collapsed under 27-year-old Motor Vehicles Act | deep-listening S5 |
| E7 | secondhand | Nepal: family abroad = payment system (shared cards), credit (50.3% informal loans) | deep-listening P2 |
| E8 | primary | r/smallbusiness: "How do I have a profit if I'm barely surviving?" | deep-listening P4 |

### INTERPRETATION (what an agent concluded)

| ID | Provenance | Text | Source |
|----|-----------|------|--------|
| I1 | agent-written | Distribution is the killer; positioning isn't the problem | deep-listening P1 |
| I2 | agent-written | Trust flows through peers, never vendors | deep-listening P2 |
| I3 | agent-written | Owner presence is the binding constraint | deep-listening P3 |
| I4 | agent-written | Growth distrusted; leanness is the win | deep-listening P5 |
| I5 | agent-written | Nepali founders' #1 complaint is payments, not capital | deep-listening S3 |
| I6 | agent-written | "Find opportunities" wedge may be wrong; presence gap may be real | deep-listening S1 |

**Deduplication:** P6/P7 overlap (service economy built for bigger companies) — merged into I2's context. P8 (strangers over institutions) is evidence for I2, not separate.

**Counts:** 8 EVIDENCE (6 primary, 2 secondhand), 6 INTERPRETATION (6 agent-written)

## 2. DERIVED UNKNOWNS

### TENSIONs

**T1: Distribution vs presence — the wedge contradicts itself**
- Type: TENSION (two recorded items conflict)
- Cites: E1 vs E2/E3; I1 vs I3
- P1 says need more customers. P3 says can't handle existing inquiries. Both can't be priority.

**T2: Sprint offer is vendor-shaped; vendors are auto-distrusted**
- Type: TENSION (assumed thing has no evidence)
- Cites: I2 vs docs/FIRST_RUPEE_SPRINT.md
- No recorded evidence of seller accepting vendor-shaped recovery offer.

**T3: Sprint payment path relies on broken system**
- Type: TENSION (assumed thing has no evidence)
- Cites: I5, E7 vs docs/SPRINT_READY.md
- No evidence personal eSewa/Khalti works for business transactions.

### HIDDEN DEPENDENCIEs

**H1: Discovery depends on English-searchable discourse**
- Type: HIDDEN DEPENDENCY
- Cites: Dry wells; deep-listening §5
- Never listed. Structural, not a question.

**H2: Trust path depends entirely on owner's personal relationships**
- Type: HIDDEN DEPENDENCY
- Cites: I2, E7
- Not a tactic — structural. No relationships = no trust path.

**H3: Unknowns API depends on manual JSON sync**
- Type: HIDDEN DEPENDENCY
- Cites: backend/app/data/unknowns.json; scripts/sync-unknowns-json.mjs
- No CI enforcement. Silent staleness risk.

## 3. FINDING CLASSIFICATIONS

| Classification | Count |
|----------------|-------|
| CHANGES THE MODEL | 2 |
| CHANGES A PLAN OR ACTION | 2 |
| CHANGES A TEST | 2 |
| NO ACTIONABLE CONSEQUENCE | 4 |

### CHANGES THE MODEL
- **I3** (presence binds): Hami can frame wedge as response-capacity, not lead-gen
- **I2** (trust via peers): Hami can design trust traversal via owner, not direct

### CHANGES A PLAN OR ACTION
- **T1** (wedge contradiction): Must test "what breaks" before offering distribution
- **T2** (vendor-shaped): Sprint script needs rewrite via trust bridge

### CHANGES A TEST
- **H1** (English dependency): Discovery needs Nepali surfaces or mark English low-yield
- **H3** (manual sync): Add CI check for unknowns.json freshness

### NO ACTIONABLE CONSEQUENCE (archived from public Findings)
- **E6** (Tootle): Cautionary tale. Hami isn't transport. *Archived: not actionable.*
- **E5** (Bangladesh fraud): Different country, no Hami action. *Archived: context only.*
- **I4** (growth distrusted): Cultural observation. *Archived: doesn't change build/test.*
- **E8** (profit confusion): No capability follows without trust bridge. *Archived: premature.*

## 4. THREE LANES (Unknowns page)

- **Known unknowns:** 81 questions (existing API)
- **Tensions & dependencies:** 6 items (T1-T3, H1-H3) with citations
- **Surprises from reality:** 0 (honest empty state)

## 5. DECISION LEDGER

| Item | What changed | Link |
|------|--------------|------|
| T1 | Sprint plan: add "what breaks" test before distribution offer | docs/FIRST_RUPEE_SPRINT.md (to update) |
| T2 | First-contact script: rewrite to avoid vendor framing | docs/SPRINT_BRIEF.md (to update) |
| H1 | Discovery: add Nepali-language surface or deprioritize English rounds | discovery cron config |
| H3 | CI: add unknowns.json sync check | .github/workflows/forgeos-ci.yml (to update) |
| I3 | Model: wedge = response capacity | docs/EXPANSION_STRATEGY.md (to update) |

### 3 PROPOSED NEXT ACTIONS (not executed)

**P1: Test the "what breaks" question**
- Evidence needed: 1 seller answering "If I brought you 10 customers tomorrow, what breaks?"
- Cheapest test: Owner asks 1 seller in existing network, records verbatim answer
- Authorize: Owner (names seller, approves contact)

**P2: Verify personal-wallet payment for business**
- Evidence needed: 1 successful business transaction via personal eSewa/Khalti
- Cheapest test: Owner completes 1 real small transaction, records receipt
- Authorize: Owner (uses own wallet)

**P3: Add CI check for unknowns.json sync**
- Evidence needed: CI fails when JSON is stale
- Cheapest test: Script comparing JSON timestamp to UNKNOWN_MAP.md mtime
- Authorize: Already authorized (code change, no external action)

## Surprises from reality: 0. Real-world contacts recorded: 0.
