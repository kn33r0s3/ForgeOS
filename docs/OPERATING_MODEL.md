# Hami Operating Model v4

## Purpose

Hami does not assume that its process is correct, that its frontier is correct, or that its experiments will succeed.

The operating model exists to make failure visible early, keep losses affordable, force contact with reality, constrain self-deception, and preserve the ability to change course.

The model is itself a Bet.

If, by Day 90, Hami has followed the model and still cannot produce the required external evidence, the failure may belong to the frontier, the model, or both. That result must change the next decision.

---

## Always-on kernel

### 1. Contact clock

Record the elapsed time since the last real-world contact.

Real-world contact means interaction with an external person, organization, transaction, behavior, or other independently observable reality relevant to the frontier.

At 14 days without recorded REAL contact, mark the active intervention frontier `STARVED` and review access, legitimacy, doability, cost, falsifier and kill criterion.

**Freeze only building that depends on that starved intervention.** Do not manufacture contact or keep adding features to avoid missing real-world evidence. Independent safe Hami work continues: public-source research, unknown/evidence quality, reusable capabilities, cross-climb integration, reliability, security/privacy, testing and System Obligations. Each continuation needs a canonical queue rationale and acceptance check; a blocked frontier does not authorize a new external intervention merely to reset the clock.

---

### 2. Bet

The operating unit is a **Bet**, not a question, feature, project, or experiment.

A Bet contains:

* falsifiable claim about reality
* current evidence and provenance
* binding constraint being addressed
* smallest real-world test
* affordable loss
* owner time and energy budget
* deadline
* pre-registered kill criterion
* skeptic's case
* decision rule: amplify, dampen, or kill
* linked evidence, actions, events, and outcomes

A Bet is a projection over the six Hami primitives:

**ENTITY · RELATION · EVENT · EVIDENCE · CAPABILITY · ACTION**

It is not a seventh primitive.

Every task must serve a live Bet or a declared System Obligation.

Otherwise it is archived.

---

### 3. Proof ladder and decision state

Proof level answers:

**How far may this evidence be trusted?**

Decision state answers:

**What action may we take because of it?**

They are separate.

```text
L0  idea / agent-written text
    may suggest a Bet

L1  secondhand source
    paper, forum, article, etc.
    may suggest; never decides

L2  direct observation
    may shape priorities

L3  another person's consented account
    may justify a probe or change a plan

L4  observed behavior
    what they actually did

L5  costly signal
    real time, money, effort, reputation,
    access, inventory, or other meaningful sacrifice

L6  repeated costly signals
    from independently observed participants

L7  repeated verified outcome
    independently verified across repetitions
```

L5 and above require external anchoring.

A counterparty confirmation or third-party timestamp may establish provenance, timing, or occurrence, but it does not automatically establish a costly signal. The underlying evidence must still satisfy the proof-level definition.

For network payments, an owner confirmation alone does not verify a transfer.
The payment must link the specific outcome and connection to evidence explicitly
classified REAL, sourced as `third_party`, and recorded at L5 or above with its
external verifier reference plus a stored external URL or provider reference.
Public trust fails closed for older VERIFIED rows that lack that evidence. Once
linked to a verified payment, the proof record cannot be changed through the
proof-level API. A disputed payment's settlement requires a distinct,
independently anchored evidence row linked as an update to the payment; proof
for the original payment alone cannot establish the settlement amount.

Agents may propose interpretations.

Agents cannot promote evidence by assertion.

Plans cannot be changed on the basis of agent-written material alone.

Public claims cannot exceed their recorded proof level.

---

### 4. Work-in-progress limits

At most:

**3 live Bets**

**1 active intervention design**

The single intervention may involve multiple consenting participants.

System Obligations are exempt.

Internal work must be recorded in the canonical queue and justify at least one of: unblocking a live Bet or bounded test; resolving a mapped unknown or improving evidence quality; creating a reusable capability or hardening with value across climbs; connecting existing canonical records/capabilities or closing a verified integration gap; or satisfying a System Obligation/reducing security, privacy or reliability risk. A one-off vertical build cannot bypass evidence gates or be justified only by adding activity. Mark direct intervention dependency explicitly with `depends_on_active_intervention: true` (or an active/frontier Bet identifier) so the STARVED gate blocks only work tied to that frontier; absent that dependency, generic reusable/internal work remains eligible.

Parallel reasoning, research and internal build tracks are allowed. Parallel real-world intervention programs are not. The three-live-Bet and one-active-intervention limits bound external tests, not Hami's internal exploration or the ability to work on unrelated climbs.

---

### 5. Independent verification

The author of an implementation or report is not its verifier.

Verification is a mechanical process outside the builder's ability to rewrite after the fact.

Where applicable it records:

```text
deployed SHA
verification time
fetched production artifact/content
test counts
test results
expected state
actual state
pass/fail result
```

The verifier does not merely review a report claiming that verification occurred.

**Verified means the external check actually ran.**

---

### 6. External anchoring

Evidence at L5+ must be anchored outside Hami's own narrative.

Acceptable anchors can include counterparty-confirmed records, independently timestamped records, externally generated transaction records, or other evidence whose existence Hami cannot cheaply rewrite.

The purpose is not bureaucratic formality.

The purpose is to prevent Hami from becoming its own source of proof.

---

### 7. Open-ended investigation, bounded intervention

Hami's **investigation domain is value itself**. No single industry, customer type,
market, geography, resource class, or experiment defines the system's domain.

The current working frontier remains how small online purchases in Nepal are
actually decided, on buyer and seller sides. That is a current execution focus,
not a finding that seller transactions are the largest, best, or only form of
value Hami should investigate.

**Investigation is open-ended even while interventions are bounded.** The
90-day window is a review horizon, not an obligation to keep a disproven
frontier. It limits uncontrolled switching of the active real-world
intervention; it does not prohibit reading, observing, checking sources,
mapping existing capabilities, comparing hypotheses, or discovering value in
other domains.

Use the existing `docs/UNKNOWN_MAP.md` as the durable candidate/unknown
registry, alongside existing Entity, Relation, Event, Evidence, Capability,
Action, claim, and outcome records. Do not create a second horizon register,
parallel queue, taxonomy, or discovery engine. A candidate from any domain may
be examined through the same primitives. Categories and examples are search
lenses only; no fixed list exhausts possible value.

In each discovery cycle, compare the current frontier with any materially
promising alternative surfaced by legitimate evidence. Ask, without limiting
the answer to a preset domain list:

- What value exists, could be created, preserved, connected, transformed, used,
  protected, or recovered?
- Which entities hold it, need it, enable it, block it, or bear the cost when it
  is missing or lost?
- What relationship, resource, capability, information, or action could change
  that state?
- What evidence supports the interpretation, what contradicts it, and what is
  still unknown?
- What is the cheapest legitimate observation or test, what outcome would it
  measure, and what risk, permission, time, or cost does it require?
- If this is a commercial path, who benefits, who pays or fairly shares value,
  and how would that exchange be verified? Do not force a non-economic value
  question to pretend it has immediate revenue.

Compare candidates by evidenced consequence and reach, urgency, confidence and
counter-evidence, time and cost to learn, current capability fit, safety/legal/
privacy constraints, reversibility, and how clearly the result could be
verified. This comparison informs judgment; a score or agent assertion never
proves value or authorizes action.

Bounded execution stays in force: at most three live Bets and one active
intervention design. Broad exploration does not authorize parallel
interventions, contacting people, spending, publishing claims, or activating a
closed channel. Any real-world action still needs its relevant authorization,
capability, affordable-loss limit, and verification plan.

Review the chosen intervention at least every 30 days and earlier when:
- its registered kill criterion is met or new evidence materially contradicts it;
- a different candidate has materially stronger evidence and a more viable,
  safer, or more consequential test;
- the 14-day no-contact tripwire marks the active intervention STARVED and freezes only building dependent on that intervention; unrelated safe climbs continue.

At a no-contact tripwire, do not preserve the starved frontier through inertia
or respond by building more for that same intervention. Reassess access, the
legitimacy and doability of the test, and competing value candidates. Keep the
current intervention only when evidence and real constraints still justify it.
Independent Hami research, reliability, security/privacy, testing and reusable
capability work continues through the canonical portfolio queue. A frontier can
be revised, paused, or killed through the existing decision/evidence path; the
calendar is not proof that it is correct.

---

## What is scaffolding

These mechanisms are useful but are not part of the irreducible kernel:

* sensor circle
* specialized agent roles
* weekly Pulse ritual
* domain adapters
* contributor give-back loops
* additional dashboards
* automation beyond the minimum needed to preserve the kernel

Scaffolding is enabled only when the current problem justifies its overhead.

The system must never turn process into the work.

---

## Human budget

The owner's time, attention, and energy are scarce resources.

Affordable loss includes them.

A Bet that consumes more owner capacity than its registered budget must:

**shrink, delegate, pause, or die.**

The model may not count exhaustion as an acceptable operating cost.

---

## Sensors

Sensors are recorded as sensors.

They are not treated as "the market."

Each observation records enough provenance to understand:

* who or what generated it
* context
* time
* consent status where applicable
* directness
* proof level
* linked Bet

Sampling gaps are visible.

The scoreboard must show not only who has been heard from, but who has **not** been heard from.

---

## Weekly Pulse

When the scaffolding is active:

**Daily:** at most one hour of owner sensing effort, preferably one observation or conversation.

**Monday:** select up to three Bets.

**Friday:** verify, decide amplify/dampen/kill, update beliefs, and publish the scoreboard.

**Days 30, 60, 90:** review the frontier, the Bets, the model, and the evidence.

---

## Tripwires

### Reality starvation

14 days without recorded REAL contact marks the active intervention STARVED and freezes only dependent intervention work, not Hami-wide internal progress.

### Proof inflation

A public claim exceeding its recorded proof level is blocked.

### Unverified reporting

A report asserting verification without an independently recorded check is rejected.

### Scope drift

A new domain is not automatically scope drift: Hami's investigation domain is
open-ended. Record a promising new unknown or hypothesis in the existing
unknown/evidence substrate and compare it with the active frontier. Do not
automatically build for it or start a parallel intervention.

### Owner overload

Exceeding the human budget forces scope reduction.

### Unsupported surprise

A “surprise” without a source is archived rather than promoted into fact.

### Scoreboard contamination

Agents may read the scoreboard but cannot write authoritative scoreboard evidence.

---

## Honest scoreboard

The scoreboard reports only what is actually supported.

```text
days since last real contact
observations logged
conversations held
live Bets
Bets killed
Bets amplified
highest proof level reached
verified rupees
sampling gaps
owner time used
owner budget remaining
```

Zero is a valid result.

Unknown is a valid result.

“No evidence” is a valid result.

---

## Dormancy

Stopping must not destroy continuity.

Dormancy freezes the current state into a durable state record containing:

* active frontier
* live Bets
* proof levels
* evidence references
* decisions
* pending actions
* deadlines
* kill criteria
* current scoreboard
* known unknowns

Resumption begins from that recorded state.

No memory of the system may depend on one AI, one conversation, or one person remembering what happened.

---

## Anti-gaming principle

Agents cannot make reality more true by producing more text about it.

The easiest way to increase an evidence count must not be to generate additional internal artifacts.

The strongest progress signal should remain external to Hami:

**someone acted, sacrificed, committed, paid, repeated, or produced a verified outcome.**

---

## The central cycle

```text
ORIENT
  ↓
DIAGNOSE
  ↓
BET
  ↓
PROBE
  ↓
VERIFY
  ↓
EARNING
  ↓
AMPLIFY / DAMPEN / KILL
  ↓
MAP
  ↓
ORIENT AGAIN
```

The orientation changes because the evidence changed.

The decision changes because reality changed.

---

## The EARNING gate (owner-set, 2026-10-08)

VERIFY establishes that a signal is real. EARNING establishes that the
signal can become a transaction someone pays for. The two are not the
same, and the cycle must not assume the second follows the first.

**No earning → no expensive real-world intervention.**

Concretely:

* A verified mechanism with no credible earning path remains knowledge.
  It is mapped, not acted on.
* Crossing into consequential real-world action — spending owner money
  or significant owner time, committing to counterparties, operating at
  any real scale — requires a named earning path: who pays, for what
  verified outcome, and how Hami captures part of the recovered or
  created value.
* Earning here means the first verified rupee of external revenue on
  the path the Bet defined — not profit yet (see the revenue milestone
  ladder: ₨1 verified external revenue → ₨1 contribution profit →
  repeatable positive economics), but a real transaction, not a plan
  to transact. Owner time is tracked as a real cost from the start.
* AMPLIFY / DAMPEN / KILL is then decided on actual economic results,
  not on how convincing the verified mechanism sounded.

The hunting question this gate strengthens:

> Where does value disappear — and can Hami capture some of that
> recovered value?

A discovery that cannot yet plausibly be realized or measured remains a
knowledge/unknown-map candidate; it is not discarded merely because it is not a
seller or an immediate revenue path. The EARNING gate applies to consequential
commercial interventions, not to the boundary of Hami's investigation domain.
Revenue is one possible value outcome, not a gate on what Hami may investigate.

---

## Why this model exists

It does not guarantee:

* that the frontier is correct
* that an experiment succeeds
* that the market responds
* that legal risk disappears
* that agents cannot game the process
* that Hami will create value
* that the owner can sustain unlimited sensing

It does guarantee none of those things.

It creates constraints under which those failures become easier to detect.

That is the assurance claim.

And that claim is itself a Bet.
