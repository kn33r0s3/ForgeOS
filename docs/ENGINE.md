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

## ForgeBot reasoning method — difference-guided synthesis

Do not define ForgeBot by analogy to a brain. That analogy does not tell the
system which existing line to change, which observation makes a claim true,
or why one attempt worked and another failed. The reusable method is a
disciplined search over candidate transformations, with verification that is
separate from candidate generation.

An established ancestor is **counterexample-guided inductive synthesis
(CEGIS)**: a generator proposes a candidate, a verifier checks it against a
specification, and a counterexample narrows the next search. See the
[CEGIS synthesis overview](https://link.springer.com/chapter/10.1007/978-3-319-96145-3_15).
Formal guarantees apply only when the specification and verifier justify
them. Software-test success must never be treated as proof of a real-world
economic outcome.

### The working loop

1. **Recover the real starting point.** Read the current source, tests,
   recent history, and the earliest relevant implementation from Hami's
   preserved lineage. Use `git log --follow`, `git blame`, and targeted
   history searches when available. Find the existing function, route, model,
   event, or component that already carries the meaning. Prefer the smallest
   correct in-place change; a new subsystem requires proof that the existing
   seam cannot express the behavior.

2. **Define the state change, not a slogan.** State the starting conditions,
   desired observable transition, invariants, evidence standard, cost/risk
   limit, and a falsifier or kill rule. When the right question is unknown,
   preserve competing explanations and look for contradictions, anomalies,
   missing transitions, repeated failures, and overlooked resources. Do not
   force the world into a preset category list.

3. **Generate bounded alternatives.** Start with the current implementation
   or nearest evidenced method. Compare a minimal repair, a different
   mechanism, and a genuinely new candidate only when useful. Rank allowable
   candidates by likely value to affected people, costly uncertainty removed,
   reuse potential, reversibility, risk, time, and cost. Do not reward the
   number of ideas, agents, lines, commits, or tests.

4. **Challenge candidates independently.** For code, use existing contracts,
   regression tests, adversarial cases, type/security checks, and the relevant
   runtime observation. For factual claims, check source identity, date,
   scope, provenance, contradictions, and authority. For a claim about
   real-world value, require a real observation or outcome at the appropriate
   verification level. The generator cannot serve as its own verifier.

5. **Find the smallest informative difference.** On a miss, preserve the
   exact failing input or situation, expected transition, observed result,
   and evidence. Determine whether the miss came from a wrong specification,
   weak or stale evidence, a bad mapping/assumption, the chosen mechanism,
   unavailable capability, denied permission, failed execution, measurement,
   attribution, or changed conditions. UNKNOWN is neither success nor failure;
   an action being requested or executed is not proof that its intended
   outcome occurred.

6. **Make the failure change the next attempt.** Add the counterexample to
   the relevant regression or evaluation set, update the existing strategy,
   question, evidence, capability, task priority, or lesson through its current
   seam, and keep the prior state/provenance. A prose lesson that changes no
   candidate ranking, test, decision, or action is not yet operational
   learning. Never adjust confidence just because the generator sounds sure.

7. **Transfer the mechanism, not the surface pattern.** A reusable method
   records its preconditions, the transformation it applies, the expected
   state change, the evidence supporting it, and the conditions under which
   it failed. Test it against counterexamples and unseen cases before widening
   its scope. A method that works once is a candidate; independent replication
   across relevant contexts is stronger evidence. Similar wording or shape
   is not proof of the same underlying mechanism.

8. **Promote only what survived.** Internal read-only discovery and bounded
   code work can continue without routine owner involvement. External actions
   still require actual capability, applicable law, consent, and authorized
   scope. Wider autonomy requires repeatable observed performance, a recovery
   path, idempotency, action-time authorization, and an explicit permission
   boundary—not model confidence or a green unit test.

9. **Stop spinning; continue elsewhere.** End a line when its declared
   success condition is evidenced, a kill rule is reached, or the required
   information/action is genuinely blocked. Record the blocker and continue
   the highest-value independent safe work. Do not manufacture activity to
   keep a loop appearing busy, and do not claim a scheduler is running unless
   its persisted effects have been observed.

### One method, domain-specific verifiers

The common outer shape is:

`context + constraints → candidate transformation → independent check
→ observed difference → refined candidate`

The verifier differs by domain. Code may have executable tests or formal
invariants. A current policy claim needs a properly dated authoritative source.
A market hypothesis needs relevant real-world evidence. A causal claim needs
consideration of alternative explanations and a defensible comparison, not
just an outcome that happened after an action. No single scoring rule can make
those evidence standards interchangeable.

This uses Hami's existing ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY and
ACTION primitives. It does not create a second truth store, a competing
ontology, or another engine. Record possibility, hypothesis, supported claim,
execution and realized outcome as distinct states. Preserve rejected
candidates and contradictory evidence so Hami does not repeatedly pay to
rediscover known failures.

### What “zero owner work” means

Zero routine owner interventions per real transaction is the target, not a
current achievement. Automate repeatable internal work and actions already
covered by explicit standing authorization. Do not bypass missing channel
credentials, external consent, legal review, financial authority, or an
owner-only permission. When one path is blocked, Hami should advance unrelated
safe work rather than ask the owner to do speculative busywork. Until verified
real transactions exist, `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains
**NOT MEASURABLE**, never an invented zero.

### Honest capability statement

The repository already has discovery, evidence, strategy, experiment, outcome,
learning, and scheduled-worker components. Their existence does not prove that
a complete candidate → independent verification → counterexample → improved
next candidate loop runs autonomously in production. Claim that capability
only after exact-head tests, observed execution, and an evaluation showing
that failures really alter subsequent choices. A mock, written design, passing
test, or deployment-ready status is not proof of real-world learning.

## Files

- `src/lib/evidence.ts` — evidence classes, Claim, the gate.
- `src/lib/evidence.test.ts` — gate tests + unknowns inventory tests.
- `src/lib/unknowns.ts` — D1–D46 structured (generated from the map).
- `src/lib/needs.ts` — the 12 candidate needs, evidence-graded.
- `docs/UNKNOWN_MAP.md` — source of truth for unknowns.
- `docs/CAPABILITY_RESEARCH.md` — the staged path to ForgeBot.
