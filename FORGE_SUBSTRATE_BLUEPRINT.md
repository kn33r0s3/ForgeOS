# ForgeOS Universal Substrate — Blueprint & Multi-Agent Contract

**Authority:** This is the authoritative Universal Substrate specification. The
dated amendment below resolves implementation and migration ambiguities in the
original blueprint. Where older wording elsewhere in this file conflicts with
the amendment, the amendment governs. This is a narrow hardening, not a change
to the North Star.

> **North Star.** ForgeOS is never finished by exhausting a list of features; it is designed to
> continuously discover new domains, capabilities, relationships, and forms of value, and incorporate
> legitimate new capabilities into the network. No initial category, geography, ontology, business
> model, or interface defines the limits of ForgeOS.

## Implementation amendment — 2026-09-25

This amendment clarifies how the Universal Substrate coexists with ForgeOS's
existing working systems and makes its validation, identity, evidence, and
migration rules enforceable. It preserves the open-world vision below.

### Logical primitives and physical records

ForgeOS has exactly six **logical substrate primitives**: `ENTITY`, `RELATION`,
`EVENT`, `EVIDENCE`, `CAPABILITY`, and `ACTION`. “Six primitives” describes
the logical model; it does not claim the physical database has only six tables.
Existing operational and legacy tables—including `decisions`, `actions`,
`outcomes`, `learning_events`, `CycleRun`, and current vertical tables—may
remain during migration. Each must map to a logical primitive, serve as
operational infrastructure, or be progressively adapted toward the substrate.
They are not additional logical primitives.

`type_registry.schema_json` is authoritative for the attributes of each
entity, relation, event, or capability type. One shared validation service
must resolve the type, require `active` status for new rows, validate the
attributes with a JSON Schema validator before persistence, and fail closed on
unknown, proposed, deprecated, or malformed types/schemas. The service is the
single implementation point; callers must not duplicate schema rules.

New registry rows start `proposed`. The only path to `active` is an explicit
activation operation that records the approving actor, rationale, and
verifiable activation evidence/process; the operation validates that record
and is covered by tests. `active → deprecated` is likewise an explicit,
recorded lifecycle operation. Creation of a registry row alone never activates
it. Trusted bootstrap vocabulary may be installed active only by a
deterministic, versioned system seed process that records that source.

### Truth transitions and evidence

One canonical transition service governs relation truth-state changes. Its
minimum supported path is `possible → hypothesized → tested → supported`,
with `possible`/`hypothesized → refuted` allowed only when the constitution's
evidence requirements are met; `unknown` remains first-class. No application
path may assign `supported` directly. A transition to `supported` requires a
corresponding stored evidence record with preserved provenance. `refuted`
cannot become `supported` by a direct state edit; new contrary information is
recorded as new evidence and must pass the transition process. Raw evidence is
append-preserved when state changes. Tests must cover transition bypasses,
missing evidence, provenance retention, and attempted revival of refuted
claims.

### Identity, deduplication, and merge history

Entity identity distinguishes the same real-world thing from distinct things
that merely look alike. Adapters use stable source identifiers and canonical
URLs/identifiers, alongside normalized identity attributes and provenance, to
form deterministic idempotency keys protected by database uniqueness. Fuzzy
or uncertain matches are candidates, not merges. Identity progresses through
`candidate → corroborated → canonical` only with recorded evidence/process;
when identity is uncertain, keep separate candidates and state the uncertainty.
Merge detection must be reviewable and must never silently merge. A confirmed
merge archives/marks the displaced row as merged, points to its survivor, and
records merge history as substrate events/evidence. Neither entity nor its
raw evidence is deleted.

### Migration authority and adapters

During each migration stage, existing vertical tables remain functional and
are authoritative for their existing records until an explicit, tested
cutover names the substrate as authority. Registered adapters expose those
records to substrate projections and preserve source IDs, provenance, and
source-to-substrate traceability. Migrations are additive and non-destructive;
source/substrate comparison tests are required. A feature may not silently
maintain two independent truths. The end state converges on the substrate
without discarding useful history.

The first adapter is the mature `Signal → Pattern → Belief → Opportunity`
path. Its existing tables remain authoritative during Wave 1; substrate
entities, relations, events, and evidence are idempotent projections with
links back to their source rows. Wave 1 must prove insertion, type validation,
identity/deduplication, evidence validation, truth transitions, provenance,
idempotency, restart behavior, and adapter consistency before any new domain
is started.

### Feed and Network authority

The Feed is a projection, never canonical storage. During migration it reads
the substrate plus explicitly registered legacy adapters; each item retains
its path to an entity, relation, or event and to its evidence/provenance. The
Network is a projection/traversal over entities, relations, events, and
evidence, plus registered legacy adapters during migration. Relationships
belong in the substrate; neither projection is a hidden entity or relation
database.

### Action, Outcome, LearningEvent

`ACTION` is the logical primitive for an authorized real-world attempt.
`Outcome` is the observation/state resulting from that action. `LearningEvent`
is learning derived from an outcome. Existing physical action, outcome, and
learning tables may remain operational during migration, but adapters map
them to the substrate; they do not form a competing universe. Existing
authorization rules still govern whether an action may execute.

### Concurrent claims and database safety

`docs/CAPABILITY_QUEUE.md` remains the human/agent claim ledger; claim scope
before implementation. Database uniqueness and idempotency keys additionally
protect type, entity identity, and relation/event creation. A missed claim
collision must be recoverable through idempotent retries and explicit
duplicate/merge review, never destructive cleanup or silent merging.

### Preserved constitutional vision

The system remains open-world and is never fixed to its initial categories;
relationship types are arbitrary and extensible; anything can become an
input; possibilities and unknowns are first-class reasoning states; ForgeOS
creates capabilities, discovers value autonomously, composes the network,
propagates capabilities, uses Nepal as bootstrap geography rather than a
boundary, treats money as a primary objective, and continuously expands its
capabilities. None of these principles is narrowed by this amendment.

## 0. Review protocol — how this document gets enforced across agents

This project runs multiple independent AI coding agents in parallel (Grok, Manus, local Qwen/OpenCode,
Claude) with no live channel between them. The working protocol is:

1. You paste an agent's plan, diff, or status report here.
2. I audit it against this document — specifically: did it add a new top-level table when it should
   have added `type_registry` rows (§1.2)? Did it claim something as `supported`/verified without
   evidence (§2.2 invariants #2, #6, #7)? Did it skip the claim ledger (§2.1)? Does it pass the
   generality test (§3 design test) or does it just make one page nicer?
3. I give you back a short, exact, copy-pasteable correction — written as a command for that agent, not
   as commentary to you — so you can relay it directly.

I'll be direct when an agent's output drifts from this contract rather than softening it, since the
whole point of writing this down was to have a fixed reference nobody's summary can quietly water down.

**Purpose of this document.** The mission statement you were given describes *what* ForgeOS should
become. This document is *how* multiple independent AI coding agents (Grok, Manus, local Qwen/OpenCode,
Claude, or any future one) can each work on it in parallel, without a live channel between them, and
still converge instead of fragment. Every agent that touches this repo reads this file **first**, before
writing any code. If an agent's plan conflicts with this file, this file wins.

The core insight: the mission doc's demand for an "open-world, never-fixed-categories" system and your
practical need for "agents that don't dismantle each other's work" are **the same problem**, solved by
**the same design decision**. If every agent extends the system by adding *data* (rows) to a small,
fixed set of generic tables instead of adding *schema* (new tables/models), then independent,
uncoordinated agents become additive by construction — there is nothing for them to collide over, because
none of them are allowed to invent new structure alone.

---

## 1. The Universal Substrate — concrete, not aspirational

Everything in ForgeOS — every Provider, ServiceListing, Opportunity, Belief, Discovery, market signal,
research question, capability, agent, tool — maps to one of exactly **six logical substrate primitives**.
No seventh logical primitive may be introduced. Existing physical operational and vertical tables may
remain during migration under the rules in the amendment above; new concepts use extensible type data
and substrate records rather than a new top-level domain table.

```
ENTITY      — any thing: a person, org, resource, capability, tool, idea, market, product...
RELATION    — any connection between two entities, of any type, with direction/strength/evidence
EVENT       — any observed or logged occurrence, tied to an entity/relation or standalone
EVIDENCE    — any claim about an entity/relation, carrying its truth-state (below)
CAPABILITY  — any reusable thing Forge can now do (a tool, workflow, integration, agent, model)
ACTION      — any authorized attempt at real-world effect, with a resulting OUTCOME
```

### 1.1 Reference record shapes (SQLite/Postgres-compatible)

The SQL below illustrates a compact physical representation of the six logical primitives and their
open type registry. It is not a claim that the live database contains only these tables, nor a mandate
to destructively replace existing tables. Existing physical tables and additive migrations follow the
authority and compatibility rules in the amendment above. `schema_json` and the behavioral invariants
are authoritative; the precise storage layout may evolve through additive, tested migrations.

```sql
-- The open-world registry: THIS is how new "kinds" of entities/relations/events/capabilities
-- get added, without a migration and without a new table. An agent that wants a new concept
-- ("MarketSignal", "ResearchQuestion", "UnusedCapacity") adds a row here, not a CREATE TABLE.
CREATE TABLE type_registry (
    id              INTEGER PRIMARY KEY,
    category        TEXT NOT NULL CHECK (category IN ('entity_type','relation_type','event_type','capability_type')),
    type_name       TEXT NOT NULL,             -- e.g. "market_signal", "repair_shop", "researcher"
    schema_json     TEXT NOT NULL,             -- JSON Schema for the `attributes` payload of this type
    description     TEXT,
    owner_agent     TEXT NOT NULL,             -- which agent/session proposed this type
    status          TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','active','deprecated')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(category, type_name)
);

CREATE TABLE entities (
    id              INTEGER PRIMARY KEY,
    entity_type     TEXT NOT NULL,             -- must reference an active type_registry row (category='entity_type')
    display_name    TEXT NOT NULL,
    attributes      TEXT NOT NULL DEFAULT '{}', -- JSON, validated against type_registry.schema_json
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','merged')),
    created_by      TEXT NOT NULL,             -- agent/session identifier
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE relations (
    id              INTEGER PRIMARY KEY,
    from_entity_id  INTEGER NOT NULL REFERENCES entities(id),
    to_entity_id    INTEGER NOT NULL REFERENCES entities(id),
    relation_type   TEXT NOT NULL,             -- must reference an active type_registry row (category='relation_type')
    attributes      TEXT NOT NULL DEFAULT '{}',
    direction       TEXT NOT NULL DEFAULT 'directed' CHECK (direction IN ('directed','bidirectional')),
    strength        REAL,                      -- 0..1, nullable if not applicable
    truth_state     TEXT NOT NULL DEFAULT 'hypothesized'
                     CHECK (truth_state IN ('possible','hypothesized','tested','supported','refuted','unknown')),
    valid_from      TEXT,
    valid_to        TEXT,                      -- null = still current
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE events (
    id              INTEGER PRIMARY KEY,
    event_type      TEXT NOT NULL,             -- references type_registry (category='event_type')
    entity_id       INTEGER REFERENCES entities(id),
    relation_id     INTEGER REFERENCES relations(id),
    payload         TEXT NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL,             -- where this event came from (collector name, agent, user)
    occurred_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE evidence (
    id              INTEGER PRIMARY KEY,
    subject_kind    TEXT NOT NULL CHECK (subject_kind IN ('entity','relation')),
    subject_id      INTEGER NOT NULL,          -- id into entities or relations, per subject_kind
    claim           TEXT NOT NULL,             -- human-readable claim this evidence supports/refutes
    support_level   TEXT NOT NULL
                    CHECK (support_level IN ('possible','hypothesized','tested','supported','refuted','unknown')),
    confidence      REAL,                      -- 0..1
    source          TEXT NOT NULL,
    provenance      TEXT,                      -- URL, doc reference, raw quote, or method description
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE capabilities (
    id              INTEGER PRIMARY KEY,
    capability_type TEXT NOT NULL,             -- references type_registry (category='capability_type')
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed','building','tested','active','deprecated')),
    spec_ref        TEXT,                      -- path to its spec/design doc
    test_ref        TEXT,                      -- path to its test file(s) — required before status='active'
    owner_agent     TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Existing decisions/actions/outcomes/learning_events remain physical operational records during
-- migration. ACTION is the logical authorized attempt; Outcome is its resulting observation/state;
-- LearningEvent is learning derived from that outcome. Registered adapters map them to the substrate.
```

### 1.2 The rule that makes parallel agents safe

> **An agent may propose a new type row, but it begins proposed. Do not add a new top-level domain
> table. Existing substrate and vertical tables may receive additive, non-destructive migrations when
> required by this contract; document the change, preserve source authority during migration, and test
> adapter/source consistency.**

A new domain (trading, logistics, research-question tracking, whatever a future agent invents) is
implemented as:
1. New `type_registry` rows (entity/relation/event/capability types specific to that domain)
2. Domain-specific **services** (Python modules) that read/write `entities`/`relations`/etc. filtered by
   `entity_type`/`relation_type` — i.e. business logic, not new storage
3. Optionally, a thin API router and a Feed projection (below) — never a new database table

This is what "never be defined by the current ontology" means *in practice*: the ontology lives in
extensible `type_registry` **data**. New rows are proposed first and only become active through the
recorded activation process in the amendment; physical changes remain additive and tested.

---

## 2. Coordination mechanism — how uncoordinated agents avoid collision

Parallel agents (Grok, Manus, local Qwen-coder, Claude) have no real-time channel to each other. The
mechanism below is a **file-based claim ledger** — the closest thing to a lock they can all read and
write without infrastructure.

### 2.1 `docs/CAPABILITY_QUEUE.md` — the claim ledger

Before starting work on any capability gap, an agent appends an entry:

```markdown
## [CLAIMED] Market signal ingestion for commodity trading
- Agent: grok-4-session-2026-09-16
- Claimed at: 2026-09-16T08:00:00Z
- Scope: new entity_type=market_signal, relation_type=signal_implies_opportunity
- Status: building
```

**Rule: an agent must grep this file for its intended scope before starting. If an unresolved claim
already covers that scope, do not duplicate it — either extend the existing claim's output once it
completes, or pick a different gap.** When done, the agent edits its own entry to `[DONE]` with a link to
the capability row it created and the tests that pass. Claims older than 48 hours with no `[DONE]`/
`[ABANDONED]` update are considered stale and may be reclaimed.

This isn't real locking. Database uniqueness and idempotency keys are the second line of defense for
types, entity identities, and relation/event creation. A collision remains recoverable through retries
and explicit duplicate review; it must not trigger silent merging or deletion.

### 2.2 Non-negotiable invariants ("the constitution")

Any agent's output that violates these gets reverted, regardless of how much work it represents:

1. **No new top-level domain tables.** Extend through the logical substrate and registered adapters.
   Existing vertical/operational tables remain during migration; additive schema changes are allowed
   under the amendment. (§1.2)
2. **No claim without evidence.** A canonical transition path must reject unsupported truth-state
   changes. `supported` requires a corresponding `evidence` row with preserved source/test provenance.
3. **No action without authorization.** Every `actions` row (existing closed-loop table) must carry a
   real authorization reference before execution; no autonomous financial or external-communication
   action without one. This is unchanged from the existing ForgeOS rules — it now applies to *every*
   domain, not just the Nepal earning workspace.
4. **No fabricated humans, transactions, or evidence.** Ever. Simulated/seed data must be labeled
   `source='simulated'` and must never be able to reach a `support_level='supported'` state.
5. **No deletion of another agent's rows.** Mark `status='deprecated'`/`'archived'`/`'merged'`. History
   is data.
6. **No capability reaches `status='active'` without a passing test referenced in `test_ref`.** An agent
   claiming "done" without a real, runnable, currently-passing test is the exact failure mode that
   produced the conflicting "111 / 128 / 137 tests passing" reports earlier in this project. Don't repeat it.
7. **Every "verified" claim in any report must link the literal command and output that verified it.**
   Same reasoning as #6 — this project has already been burned by self-reports that overclaimed.
8. **Existing subsystems are foundation, not disposable.** `belief_engine`, `pattern_engine`,
   `opportunity_engine`, the Decision/Action/Outcome/Learning closed loop, the Nepal Earn workspace, the
   scheduler — these get *generalized to read/write the substrate*, not rewritten from scratch. See §3.

### 2.3 Tie-breaker rule

If two agents' work genuinely conflicts (not just overlaps) — e.g., incompatible interpretations of a
`type_registry` schema — **the version consistent with this document wins**, and the other is flagged in
`docs/CONFLICTS.md` for a human decision, never silently overwritten or silently deleted.

---

## 3. Mapping what already exists onto the substrate (do this before adding anything new)

This is the first real task for whichever agent picks this up, and it should be claimed in
`CAPABILITY_QUEUE.md` before starting:

| Existing ForgeOS concept | Becomes, under the substrate |
|---|---|
| `Signal` (raw collected item) | `entities` with `entity_type='signal'`, plus an `events` row for its ingestion |
| `Pattern` | a substrate entity with `derived_from`/`co_occurs_with` relations to its source Signal entities |
| `Belief` | a substrate entity and typed relations to its Pattern/Signal sources; its claims map to evidence with provenance |
| `Opportunity` | `entities` with `entity_type='opportunity'`, linked via `relations` to the signals/patterns/beliefs that produced it |
| `Decision` / `Action` / `Outcome` / `LearningEvent` | Decision authorizes/records intent; Action is the logical authorized real-world attempt; Outcome is its resulting observation/state; LearningEvent is learning derived from Outcome. Existing physical records remain operational and are progressively mapped to substrate actions/events/evidence/relations. |
| Repair-shop `Customer`, `RepairWorkItem`, `WorkItemEvent` | `entities` (`entity_type='customer'`, `'work_item'`) + `events` — this is proof the substrate can hold a real vertical, not just theory |
| Nepal Earn workspace `Offer` | `entities` with `entity_type='earning_offer'`, its status-transition history as `events` |
| `CycleRun` | stays as-is (operational/observability record, not a domain concept) |

**Do not migrate existing data destructively.** Registered adapters expose existing tables to the
substrate while those tables remain authoritative for their records. Preserve provenance and source
links, compare source and substrate representations in tests, and name each authority cutover before
the substrate becomes authoritative. Never maintain two independent truths.

---

## 4. The Feed and Network — projections, not new storage

The Feed is a projection, not storage. During migration it may read substrate records plus explicitly
registered legacy adapters; it has no canonical feed database. Every item retains a trace path to its
entity/relation/event and its evidence/provenance. The Network is a projection/traversal over substrate
entities, relations, events, and evidence plus explicitly registered legacy adapters; relationships live
in the substrate, not in a hidden Network entity store.

---

## 5. Sequencing — waves, not a finish line

The mission doc explicitly rejects a finite checklist, and it's right to — so treat this as the *first
three waves* of a loop that doesn't end, not a project plan with a last page.

### 5.0 Redefine what "launch" means before any agent touches Nepal-specific work

**The first milestone is not "get the first provider/booking."** That definition is too narrow for what
this is. The actual first milestone is:

> Forge Nepal is a live, continuously updating, evidence-backed network of real-world signals, needs,
> capabilities, opportunities, and resources, with autonomous machinery underneath that can turn those
> signals into increasingly valuable actions and creations.

The first real transaction is **evidence the machine works**, not the definition of the machine. Any
agent that reports progress in terms of "got provider #1" or "first booking confirmed" as the headline
milestone is under-scoping the goal — redirect it to report signal/entity/relation density and
capability-gap throughput instead.

**The Nepal launch phases** (geography is a `type_registry`/config concern, not an architecture concern —
see §1.2; this sequencing is about product rollout, not schema):

1. **Nepal intelligence/feed** — the network and feed exist; meaningful economic/work signals
   continuously accumulate as `entities`/`relations`/`events`, evidence-labeled per §1.1.
2. **Nepal network density** — people, organizations, capabilities, needs, resources, and opportunities
   get connected across categories, not just within one vertical.
3. **Autonomous value creation** — Forge proposes, builds tools, creates services, forms opportunities,
   coordinates authorized actions — this is Wave 3 below, the `capabilities` lifecycle.
4. **Economic engine** — revenue streams emerge across many categories rather than depending on one
   marketplace commission.
5. **Replication** — once the core works, geography becomes configuration, not a rewrite. Nepal →
   another country → global network. If step 5 requires touching core schema, an earlier step was built
   wrong — this is the same falsifiability check as Wave 2 below, applied to geography instead of domain.

**Wave 1 — Substrate exists and is provably correct**
- Inspect the existing logical primitives, physical tables, and migration authority; harden their
  validation, identity, truth, evidence, and provenance contracts without replacing existing systems.
- Implement/verify a registered adapter for Signal → Pattern → Belief → Opportunity. The source tables
  remain authoritative in this wave; substrate references/relations/events must be idempotent and
  traceable to source rows.
- Tests: insertion; valid/invalid/unknown/proposed/deprecated types and malformed schemas; identity and
  duplicate detection; evidence validation; canonical truth transitions; provenance retention;
  idempotency; restart behavior; adapter/source consistency.
- Gate: the Wave 1 acceptance tests pass before any new domain begins.

**Wave 2 — One new domain proves the substrate is actually general**
- Pick ONE domain not currently modeled (trading, or logistics, or research-question tracking —
  whichever a claimed agent picks) and implement it **using only `type_registry` inserts + services**,
  zero new tables. If this requires a new table, the substrate design was wrong — stop and fix §1, don't
  patch around it.
- This is the falsifiable test of the whole architecture. Don't skip it.

**Wave 3 — Autonomous capability creation loop**

Implement this exact decision flow as real, running code — not a doc describing the idea of it — driving
the `capabilities` table's `proposed → building → tested → active` lifecycle:

```
Need discovered
      ↓
Can Forge solve it?
   ↙       ↓       ↘
 yes    partially    no
  ↓         ↓         ↓
act      decompose   capability gap
                    ↓
              research/build/find
                    ↓
              acquire capability
                    ↓
                 test it
                    ↓
                add to Forge (capabilities row, status='active', test_ref required)
                    ↓
                  act
```

`CAPABILITY_QUEUE.md` (§2.1) is the human/agent-visible surface of this loop — every "capability gap"
branch above becomes a claimed entry there before an agent starts building it.

### 5.1 The design test — apply this to every proposed feature, from any agent

Before any agent implements anything, it should be able to answer yes to this:

> Does this make Forge more general, more composable, more autonomous, and more capable of entering a
> new domain — or does it merely make one existing page nicer?

Concretely, prefer the left column; reject or redirect a plan built around the right column:

| Build this (generalizes) | Not this (narrows) |
|---|---|
| entity discovery + evidence + relationship formation + capability matching | "Nepal provider matching" |
| event/feed projection over the universal network | "job feed" |
| transaction/outcome state machine | "payment page" |

An agent's plan that's phrased as a single narrow page or a single vertical feature should be redirected
to name the generalized capability it's actually an instance of, per this table, before work starts.

### 5.2 Constitutional boundaries — restated, because "never limited" is not "unconstrained"

These bound *how* Forge acts, never *what domain* it's allowed to enter. Every agent's authority to act
autonomously stops at these lines regardless of how compelling the opportunity looks:

- **Truth** — don't pretend something happened. (§2.2 invariant #7)
- **Authorization** — don't act through accounts/permissions Forge doesn't actually have. (§2.2 invariant #3)
- **Law / terms / privacy** — don't obtain or use information unlawfully or in violation of a source's terms.
- **Security** — don't weaken the system's own safeguards to gain a capability.
- **Risk** — don't take a high-risk action merely because it's theoretically possible; weigh expected
  value against execution cost, transaction cost, compute cost, risk, and opportunity cost. The
  principle is *minimize economic value left unrealized*, not *execute every conceivable transaction*.

**Then repeat, indefinitely**, per the mission doc's own instruction — re-scan for the next gap, claim it,
build it, test it, integrate it. This document doesn't need updating for that to keep working; new
domains are data, and new capabilities self-register.

---

## 6. What every agent should read, in order, before writing a line of code

1. This file
2. `docs/CAPABILITY_QUEUE.md` — is anything relevant already claimed?
3. `type_registry` (query it, don't just read a doc about it — it's the live source of truth for what
   kinds of things already exist)
4. `STATUS.md` — current verified state, not aspirational state
5. Then, and only then: start building, claim your scope in the queue first.
