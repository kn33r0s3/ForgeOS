# Capability spec: Research (autonomous discovery rounds)

Status: **SPEC — not implemented.** This is a definition, not a build order.
Promote to build only when a real pilot or a concrete builder need requires it.
(Rule: code stays frozen unless reality exposes a concrete gap.)

## What it is

Hami's discovery loop — REALITY → OBSERVATION → EVIDENCE → UNDERSTANDING →
UNKNOWN → QUESTION → TEST/ACTION → NEW REALITY — run as a first-class
capability instead of a one-off activity. The rounds run in October 2026
(round 1: broad forum listening; round 2: Nepal-first surfaces) are the
reference implementation of the protocol, executed by the builder's agent.
This spec defines what it would mean for *Hami itself* to hold the capability.

## The four shapes are one thing

The user asked: memory, storage, engine, or bot? In Hami's terms it is all
four, already slotted into existing primitives:

- **Memory** — per-domain unknowns and evidence: what Hami believes, what it
  doesn't know, and what would change its mind. (Project-level precedent:
  `docs/UNKNOWN_MAP.md`, `workspace/discovery/discovery-log.md`.)
- **Storage** — EVIDENCE and EVENT primitives. Every observation banked with
  source, date, and evidence class. No casual deletes; archive or merge.
- **Engine** — the process layer (dependency-aware event-driven work graph)
  running observe → evidence → unknown → question cycles on a schedule,
  each round picking an angle not previously tried.
- **Bot** — the agent executing rounds: searching public sources, reading
  threads, synthesizing. Listening only.

Nothing here needs a new primitive. The capability is a *wiring* of existing
ones, plus the protocol below.

## The protocol (from the reference rounds)

1. Read the discovery log: never repeat an angle.
2. Pick one tight, untried angle — a different slice of reality each time.
3. Research public sources only. Listening: no accounts, no posting, no
   contacting real people, no fake inquiries.
4. Extract the gain: patterns (paraphrased, never invented), surprises
   (EXPECTED ≠ OBSERVED), confirmations, contradictions. A dry well is a
   finding — log it, don't pad.
5. Bank it: unknowns (D-numbered), evidence with class labels, questions.
6. Report the gain only, briefly.

## Builder-side vs user-facing — different bets

- **Builder-side** (Hami learning about reality so its model improves):
  already paying off. Rounds 1–2 reshaped the wedge thesis (D2/D11).
  This is the validated half.
- **User-facing** (Hami researching *for* a shopkeeper, e.g. "should I
  stock X?"): NOT validated. Round 1 evidence suggests headwind — owners
  trust horizontal peers and strangers, auto-distrust vendor-shaped things,
  and their binding constraint is presence, not information. A research
  feature would need its own discovery round before build.

Do not build the user-facing half on speculation.

## Hard rules (inherited from the reference rounds)

- Never manufacture voices, evidence, or outcomes.
- Evidence classes labeled always: ACTUAL > OBSERVED > INFERRED >
  ESTIMATED > UNKNOWN. Online discourse is OBSERVED-at-best.
- blocked ≠ completed. Thin sources are reported as thin.
- Near-zero cost: public sources only. Any paid source needs owner approval.
- No outreach, no messaging, no intake/send-flag changes — research moves
  nothing in the world except the model.

## Cost bounds

A round is bounded by time and public sources. No standing infrastructure
beyond the scheduler and the log. If a round needs a paid source, a login,
or human access, that is BLOCKED_BY_MISSING_ACCESS — recorded, not worked
around.

## What promotes this to build

1. A real pilot where Hami's model of a domain must update itself between
   runs (not a builder running rounds manually).
2. A user-facing research question validated by a discovery round.
3. Owner decision, as with any externally consequential capability.

Until then: the builder's agent runs the rounds; Hami holds the spec.
