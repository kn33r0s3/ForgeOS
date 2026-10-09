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

At 14 days without real contact:

**All non-obligatory building freezes.**

Only contact preparation, sensing, verification, and System Obligations may continue.

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
proof-level API.

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

Build work is permitted only when it unblocks a live Bet or satisfies a System Obligation.

Parallel reasoning is allowed.

Parallel intervention programs are not.

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

### 7. Frozen frontier

One frontier is active for 90 days.

Everything else belongs in the **horizon register**.

Nothing in the horizon register receives work merely because an agent thinks it is interesting.

The current frontier is:

**How small online purchases in Nepal are actually decided, on both the buyer and seller side.**

Changing the frontier is itself a decision governed by the review gates.

At each 30-day review, Hami must name the strongest alternative frontier and compare it against the active one.

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

14 days without real contact freezes building.

### Proof inflation

A public claim exceeding its recorded proof level is blocked.

### Unverified reporting

A report asserting verification without an independently recorded check is rejected.

### Scope drift

A request for a new domain enters the horizon register.

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

A discovery that cannot plausibly reach earning stays in the horizon.

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
