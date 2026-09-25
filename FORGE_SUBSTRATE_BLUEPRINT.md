# SUPERSEDED: ForgeOS Universal Substrate — Blueprint & Multi-Agent Contract

This pasted design is retained as source history only. It was superseded on
2026-09-25 by the end-state architecture in `docs/FUTURE_BLUEPRINT.md` and its
sequential Build Path, which extends canonical records and `NetworkConnection`
without introducing a type registry or second entity store. Do not use this
file as an active implementation contract.

> **North Star.** ForgeOS is never finished by exhausting a list of features; it is designed to
> continuously discover new domains, capabilities, relationships, and forms of value, and incorporate
> legitimate new capabilities into the network. No initial category, geography, ontology, business
> model, or interface defines the limits of ForgeOS.

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
research question, capability, agent, tool — is one of exactly **six** primitives. No agent may create a
seventh. No agent may create a new top-level database table for "a new kind of thing." New *kinds* of
things are represented as **data**, not schema.

```
ENTITY      — any thing: a person, org, resource, capability, tool, idea, market, product...
RELATION    — any connection between two entities, of any type, with direction/strength/evidence
EVENT       — any observed or logged occurrence, tied to an entity/relation or standalone
EVIDENCE    — any claim about an entity/relation, carrying its truth-state (below)
CAPABILITY  — any reusable thing Forge can now do (a tool, workflow, integration, agent, model)
ACTION      — any authorized attempt at real-world effect, with a resulting OUTCOME
```

### 1.1 Schema (SQLite/Postgres-compatible; this is authoritative — implement exactly this)

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

-- Decision -> Action -> Outcome -> Learning already exists in ForgeOS today (decisions, actions,
-- outcomes, learning_events tables in the closed-loop work). DO NOT rebuild these. They already ARE
-- the ACTION/OUTCOME primitives this substrate calls for. Extend them; do not duplicate them.
```

### 1.2 The rule that makes parallel agents safe

> **An agent may always INSERT a new row. An agent may never CREATE a new top-level table, and may
> never ALTER the six core tables above, without a human-reviewed spec change to this document.**

A new domain (trading, logistics, research-question tracking, whatever a future agent invents) is
implemented as:
1. New `type_registry` rows (entity/relation/event/capability types specific to that domain)
2. Domain-specific **services** (Python modules) that read/write `entities`/`relations`/etc. filtered by
   `entity_type`/`relation_type` — i.e. business logic, not new storage
3. Optionally, a thin API router and a Feed projection (below) — never a new database table

This is what "never be defined by the current ontology" means *in practice*: the ontology lives in the
`type_registry` **data**, which any agent can extend at any time, not in the **schema**, which is frozen.

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

This isn't real locking — it's a norm every agent is instructed to follow. It's enough, because the
underlying schema rule (§1.2) means even a missed collision is *additive*, not *destructive*: two agents
adding overlapping `type_registry` rows is a cleanup task; two agents each inventing their own
`market_signals` table is architectural fragmentation.

### 2.2 Non-negotiable invariants ("the constitution")

Any agent's output that violates these gets reverted, regardless of how much work it represents:

1. **No new top-level tables.** Extend via `entities`/`relations`/`type_registry`. (§1.2)
2. **No claim without evidence.** Nothing may be inserted as `support_level='supported'` or
   `truth_state='supported'` without a corresponding `evidence` row citing a real source or test result.
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
| `Pattern` | `relations` between the `signal` entities it clusters, `relation_type='co_occurs_with'` |
| `Belief` | `evidence` rows attached to whatever `entities`/`relations` it's a claim about |
| `Opportunity` | `entities` with `entity_type='opportunity'`, linked via `relations` to the signals/patterns/beliefs that produced it |
| `Decision` / `Action` / `Outcome` / `LearningEvent` | **unchanged** — these already are the ACTION/OUTCOME primitives; add `relations` linking them to the `entities` they act on |
| Repair-shop `Customer`, `RepairWorkItem`, `WorkItemEvent` | `entities` (`entity_type='customer'`, `'work_item'`) + `events` — this is proof the substrate can hold a real vertical, not just theory |
| Nepal Earn workspace `Offer` | `entities` with `entity_type='earning_offer'`, its status-transition history as `events` |
| `CycleRun` | stays as-is (operational/observability record, not a domain concept) |

**Do not migrate existing data destructively.** Write adapters: the existing tables keep working, and a
migration path copies/mirrors them into the substrate incrementally, verified with tests at each step
(per the mission doc's own testing section). This satisfies "keep existing useful work... generalize
where necessary" literally, not just in spirit.

---

## 4. The Feed and Network — projections, not new storage

The mission doc is right that the Feed must not become "a chronological list of service listings." Under
this design that's automatic: **the Feed is a read-only query over `entities`+`relations`+`events`
filtered/ranked by recency, relevance, and `truth_state`** — it has no storage of its own. Any agent
building "a Feed feature" is by definition writing a query/ranking function, never a new table. Same for
"the Network" — it's a graph traversal over `entities`/`relations`, not a separate system.

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
- Implement the six tables + `type_registry` exactly as in §1.1
- Write the mapping adapters from §3 for at least one existing subsystem (suggest: Signal → Pattern →
  Belief → Opportunity, since it's the most mature)
- Tests: insertion, type validation against `type_registry.schema_json`, `truth_state` transition rules
  (can't jump `possible` → `supported` without an intermediate `tested` evidence row), idempotency,
  restart behavior
- Gate: `pytest` passing on all of the above before Wave 2 starts

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
