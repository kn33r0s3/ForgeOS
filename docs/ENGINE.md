# Hami Engine — the verification machine

**Owner-directed, 2026-10-04:** "what works and gets money and sells —
we make hami's engine the same as what u did, how u did, with assurity,
verifications, tests, 0 failures or downfalls." And: research exists to
drive and develop Hami, not to decorate the website.

This document is the engine's contract. The engine is not a page. It is
the loop Hami runs on everything it claims to know.

## The loop (musa's loop, as Hami's loop)

1. **Research** — observe reality; never invent. Online discourse is
   OBSERVED-at-best; a real conversation is ACTUAL.
2. **Evidence** — every claim gets a class, named sources, a confidence
   grade, and a weakest link. No exceptions.
3. **Gate** — `verifyClaim()` in `src/lib/evidence.ts` rejects anything
   that can't say what it is, where it came from, how sure it is, and
   what would prove it wrong. One bad claim fails the batch — the way
   one bad fact fails a report.
4. **Test** — the gate itself is tested (`src/lib/evidence.test.ts`).
   Knowledge the tests don't cover doesn't ship.
5. **Bank** — verified claims become structured data (`src/lib/needs.ts`,
   `src/lib/unknowns.ts`), not prose. The unknowns map
   (`docs/UNKNOWN_MAP.md`) is the source of truth; the TS files are its
   machine-readable projection.
6. **Ship** — small commits, tests green before push, production health
   verified after. The ritual the owner endorsed.

"0 failures" means: the gate fails *closed*. A claim that can't pass
doesn't get published with a warning label — it doesn't get banked.

## The money road

The engine exists to move a need along this road — this is the "gets
money and sells" part:

```
candidate → verified → served → paid
```

- **candidate** — observed in public sources, evidence-graded, weakest
  link named. The 12 needs on `/needs` live here. (Today: all 12.)
- **verified** — confirmed or killed by real contact: the five
  conversations, or a real merchant's observed behavior. Needs human
  bodies; the engine waits honestly rather than inventing this step.
- **served** — Hami (or a human through Hami) acted on the verified need
  and produced a real outcome. ESTIMATED ≠ ACTUAL applies in full.
- **paid** — money changed hands for the outcome. ₨1 → ₨10,000 →
  ₨100,000 → recurring. The first rupee is the engine's first proof.

A need nobody verifies is a need the engine drops. A served need nobody
pays for is a need the engine re-examines. The road only moves forward
on evidence.

## What the engine refuses

- Manufacturing reality: no synthetic leads, customers, conversations,
  payments, or outcomes. Ever.
- "Mostly accurate": high confidence requires at least observed
  evidence; reported-class claims must name their rumor risk.
- Bypassing failed checks: the intake decision (stays closed on failed
  readiness) is the engine's own precedent — the gate applies to Hami's
  actions, not just its claims.
- Decorating instead of developing: research output that doesn't move a
  need along the road, kill a bad thesis, or sharpen a build decision
  is fuel unburned. The `/needs` page is a public notebook of candidates,
  not the engine's product.

## ForgeBot's trajectory

ForgeBot's end state (owner-directed): a reasoning agent like the
operator or better, performing all discovery findings itself. The
engine is what it inherits:

- **Now (v0):** the gate, the claim types, the structured unknowns
  (D1–D46), the graded needs. The operator runs the loop; the engine
  enforces the discipline.
- **Next:** the round protocol as an executable spec
  (`docs/CAPABILITY_RESEARCH.md` stages 1–2) — ForgeBot runs rounds
  through the gate instead of the operator.
- **End state:** ForgeBot researches, verifies, banks, and ships with
  the same assurity — then better, because it never gets tired and
  never rounds "mostly accurate" up.

## Files

- `src/lib/evidence.ts` — evidence classes, Claim, the gate.
- `src/lib/evidence.test.ts` — gate tests + unknowns inventory tests.
- `src/lib/unknowns.ts` — D1–D46 structured (generated from the map).
- `src/lib/needs.ts` — the 12 candidate needs, evidence-graded.
- `docs/UNKNOWN_MAP.md` — source of truth for unknowns.
- `docs/CAPABILITY_RESEARCH.md` — the staged path to ForgeBot.
