# Round Protocol — the discovery loop as an executable spec

**Purpose:** the exact procedure the operator runs every discovery round,
written so precisely that executing it is mechanical. ForgeBot v0 (the
assistant) enforces it; later ForgeBot runs it.

## Definitions

- **Round:** one hour, one tight angle, one gain.
- **Angle:** a single slice of reality not tried before (checked with
  `isAngleTried()` against `src/lib/forge/tried-angles.ts`).
- **Gain:** what changed in our version of reality — a surprise
  (EXPECTED ≠ OBSERVED), a confirmation, a contradiction, or a dry well
  (one honest line, never padded).
- **Finding:** a `RoundFinding` — a `Claim` (statement, evidence class,
  named sources, confidence, weakest link) plus the unknown IDs it
  addresses.

## The protocol

1. **Read state.** Open `docs/UNKNOWN_MAP.md` (unknowns D1–D64+, states)
   and the discovery log (angles tried). Reality may have moved since
   the last round — re-read, never assume.
2. **Pick the angle.** One tight slice, finishable in the hour, not
   tried before. Consult `ripenessQueue()` — oldest open unknowns first,
   desk-doable before human-gated. Invent beyond the queue when a better
   slice appears; never repeat a round's angle.
3. **Research.** Real sources only: `browser.search`, `social.search`,
   thread reading, press, public listings, app telemetry. **Listening
   only** — no accounts, no posting, no contacting real people, no fake
   inquiries, no spending. Online discourse is OBSERVED-at-best; a
   single source is REPORTED-at-best.
4. **Extract the gain.** Ask: what surprised? (EXPECTED ≠ OBSERVED is the
   most valuable output.) What confirmed? What contradicted? If nothing
   new: one line, no padding, no restating old findings.
5. **Hunt the hidden unknown.** Known unknowns are D-entries; *hidden*
   unknowns are the ones nobody thought to ask. After the gain,
   interrogate the negative space:
   - What did this round NOT look at? What's adjacent but untouched?
   - What did sources assume without saying? (Assumptions are hidden
     unknowns wearing confidence.)
   - Does anything here contradict a banked finding? Contradictions are
     hidden unknowns surfacing.
   - The dog that didn't bark: what should exist in this picture but
     doesn't appear?
   Bank what surfaces as a D-entry like any other unknown — mark its
   question with "(hidden: …)" so the map shows where it came from.
5. **Grade every finding.** Each new claim gets: evidence class, named
   sources (documents/datasets/voices — "research" is not a source),
   confidence (high needs ≥ observed), weakest link (the part most
   likely wrong + what would change our mind).
6. **Gate.** Run `verifyRound(findings)`. Bank ONLY `verdict.verified`.
   Rejected findings are reworked or dropped — never banked with a
   warning label. The gate fails closed.
7. **Bank.**
   - Append the round entry to the discovery log (angle, method, gains,
     surprises, new unknowns, sharpest question, sources).
   - Add genuinely new unknowns to `docs/UNKNOWN_MAP.md`, continuing
     D-numbering, each with state, cheapest legitimate test, and stakes.
   - Regenerate `src/lib/unknowns.ts` from the map; update the guard
     counts in `src/lib/evidence.test.ts`.
   - Regenerate `src/lib/forge/tried-angles.ts` from the log.
8. **Verify.** Tests green (`npm test`). No test run for docs-only
   commits is acceptable; any `src/` change needs the suite.
9. **Push.** Commit with a real message, push to `origin/main`, verify
   sync. The standing rule: always in sync, live-time pushed.
10. **Report.** The gain only — one tight message: what changed, what
    surprised, the sharpest new question. Brevity is respect.

## Standing constraints (never overridden by the protocol)

- No outreach, no messaging anyone, no spending money.
- No intake/send-flag changes.
- No production code changes without a concrete reality-driven reason.
- Never manufacture evidence. Synthetic findings are forbidden, always.
- The five real conversations are the center; rounds sharpen their
  questions and never substitute for them.
- `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is NOT MEASURABLE until a
  real transaction exists — never zero, never estimated.

## Stages (from `docs/CAPABILITY_RESEARCH.md` + `docs/ENGINE.md`)

- **v0 — assistant (now):** the operator runs rounds; the assistant
  gates findings (`verifyRound`), ranks ripeness (`ripenessQueue`), and
  refuses repeats (`isAngleTried`). Used by the operator every round.
- **v1 — competitor:** ForgeBot executes the protocol itself —
  plans the angle, researches with its tools, grades, gates, banks.
  The operator reviews and grades its rounds.
- **v2 — better:** cross-round contradiction detection, question
  generation from the unknowns graph, self-directed angle selection.
  The trainee outperforms the fuel.
