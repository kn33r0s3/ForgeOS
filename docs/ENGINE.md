# Hami Engine — the verification machine

**Owner-directed, 2026-10-04:** "what works and gets money and sells —
we make hami's engine the same as what u did, how u did, with assurity,
verifications, tests, 0 failures or downfalls." And: research exists to
drive and develop Hami, not to decorate the website.

## The greatest goal (prime directive)

**Hami Systems'** greatest goal: a living system for understanding and
acting upon the real world — continuously building knowledge of people,
places, needs, opportunities, resources, relationships, capabilities,
and outcomes, then turning that knowledge into authorized action and
real-world value. AI is one worker; software is one instrument; humans
are participants and partners.

Everything the engine does contributes to this living system. One real rupee is valuable commercial proof at one scale, not the boundary of all useful work. Discovery—including hidden unknowns nobody thought to ask—is one way the system grows toward it.

## Many climbs, one shared engine

Hami is a portfolio of connected work: discovering reality, exposing unknowns, building capabilities, connecting supported knowledge, improving security and reliability, testing hypotheses and measuring outcomes. Tracks can progress concurrently when dependencies and finite time, compute and cost budgets allow. A blocked customer-facing experiment must not stall independent research, maintenance, tests or capability work.

Every climb reuses the six-primitives substrate and existing questions, claims, evidence, Bets, tasks, capabilities and Actions. A climb is not a new semantic primitive or parallel truth store. Record dependencies/provenance so findings help related tracks without silently transferring rights to reuse personal data. Deduplicate before spawning tasks; bound concurrency; make work resumable and idempotent; record costs, uncertainty, authorization and kill criteria.

Prioritize value to affected people, costly uncertainty removed, reuse across climbs, reversibility, risk and test cost. Preserve exploratory breadth so one high-volume topic cannot starve other useful directions. If blocked, log why and continue with the highest-ranked independent safe item. A systemic privacy, security or integrity incident contains dependent paths but does not automatically prohibit unrelated read-only work.

This is the target operating model, not proof that the current runtime runs infinite autonomous loops. Actual autonomy requires durable scheduling, bounded execution, a persistent portfolio, real evaluation/write-back, action-time authorization, exact-head tests and evidence of real runs. Report implementation, tests, deployment readiness, runtime behavior and real-world outcomes separately.

## The legitimacy rule (owner's standing rule, 2026-10-04)

"We not building show off or simulation for public, our engine must be
100% legit and as promised." Concretely:

- Public surfaces show only what is real. Operator tooling lives behind
  the owner key on `/owner` — never on public routes.
- Every claimed capability runs the real engine code. A console that
  exercises a capability imports the real module; a test proves it does.
- No mock, no demo that pretends, no page that implies a capability the
  engine doesn't have. If it isn't built, it isn't shown.

## Value is the method (owner-directed, 2026-10-04)

**What value is:** a real change that matters to someone—income, time, trust, access, capability, safety, resilience, coordination, resource allocation or behavior. Value is defined by affected people and measured honestly. Money changing hands is strong proof for commercial exchange and sustainability, not the only possible measure of usefulness. The revenue ladder remains essential for commercial paths; it does not narrow the engine's domain.

**More valuable:** close to survival (money in/out), scarce alternatives,
urgent pain, measurable gain, trusted source, low friction, recurring need.
**Less valuable** is the mirror: far from money, commodity, someday-pain,
unmeasurable, distrusted, high friction, one-off.

**The method:** every unknown is scored on value-density — *who gives up
what for the answer, and when?* — in `src/lib/forge/value.ts` (the rubric)
and `src/lib/forge/value-tiers.ts` (the scores). The ripeness queue ranks
by value tier first, doability second, age third. Effort-ordering without
value-ordering is just motion. A round that chases a tier-1 unknown while
a tier-3 sits open is a wasted round, no matter how rigorous.

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

## ForgeBot learning model — from fixed rules to compounding capability

The four-stage neural-network analogy is useful, but ForgeBot must not confuse
pattern learning with verified understanding. ForgeBot is not currently training
its own neural-network weights. Its practical learning loop is a system-level
capability built from evidence, memory, evaluation and controlled changes.

### 1. Human blueprint — define the boundaries, not every answer

Humans define the mission, permitted tools, evidence standards, privacy limits,
authorization rules and what counts as a useful outcome. These are guardrails,
not answers to every question. ForgeBot may propose new methods inside those
boundaries; it may not rewrite its own permissions or truth standards.

### 2. Playground — expose it to real, permitted experience

Use real public sources, authorized work, actual feedback and recorded outcomes.
Every input retains provenance, date, scope and evidence class. Examples and
synthetic fixtures may test software, but must never be passed off as real-world
experience or used to claim business success. Missing access means BLOCKED,
not an invitation to fabricate or bypass controls.

### 3. Feedback loop — compare predictions with what happened

For each meaningful task, ForgeBot should record: the question or goal, its
initial belief and uncertainty, the chosen approach, expected result, observed
result, evidence, cost, side effects and what would change its conclusion.
Compare outcome against expectation; classify the miss (bad evidence, wrong
assumption, poor strategy, execution failure or changed conditions); then
update the relevant claim, unknown, strategy evaluation or task priority.
Keep the prior state and provenance so learning is auditable and reversible.

### 4. Emergence — compose reusable methods, then prove they generalize

Repeated, independently supported patterns may become reusable strategies,
tools or hypotheses. They are candidates, not truths. Check them against
contradictions, new cases and held-out examples before broadening their scope.
A method that works for one seller, language, source or task must not silently
be assumed to work everywhere. Record both successful transfer and failure.

### The compounding loop

`observe → represent → hypothesize → choose a bounded action → measure →
compare → update → test on a new case → retain or roll back`

This reuses Hami's existing ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY and
ACTION primitives; it does not create a second truth store or a new primitive.
Knowledge changes must retain source, time, confidence, counter-evidence and
the reason for the update. Strategy changes must retain versions and evaluation
results. Repeating a task without improving a measurable outcome is not learning.

### Promotion gates

- **Observe:** collect and classify evidence without external side effects.
- **Draft:** propose a conclusion or action with sources and uncertainty visible.
- **Evaluate:** compare proposals with human feedback and real outcomes; measure
  correctness, calibration, usefulness, cost and harm.
- **Bounded action:** only small, reversible actions with explicit authorization,
  idempotency, logging and a recovery path.
- **Wider autonomy:** only after repeated real-world evidence shows reliable
  performance across relevant cases, no unacceptable incidents, and an owner-
  approved permission boundary. Never infer permission from model confidence.

### Honest capability statement

The present system may persist structured knowledge and enforce gates, but
those facts alone do not prove ForgeBot independently learns or runs continuously.
Self-running discovery, automatic strategy improvement and model-weight training
are distinct capabilities. Report each only when implemented, tested at the exact
revision, observed running and evaluated against real outcomes. A mock response,
passing unit test or successful deployment is not proof of real-world learning.

## Files

- `src/lib/evidence.ts` — evidence classes, Claim, the gate.
- `src/lib/evidence.test.ts` — gate tests + unknowns inventory tests.
- `src/lib/unknowns.ts` — D1–D46 structured (generated from the map).
- `src/lib/needs.ts` — the 12 candidate needs, evidence-graded.
- `docs/UNKNOWN_MAP.md` — source of truth for unknowns.
- `docs/CAPABILITY_RESEARCH.md` — the staged path to ForgeBot.
