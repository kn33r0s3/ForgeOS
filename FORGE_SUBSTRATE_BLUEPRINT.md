# ForgeOS Universal Substrate — Blueprint & Multi-Agent Contract

**Authority:** This is the authoritative Universal Substrate specification. The dated amendment below resolves implementation and migration ambiguities in the original blueprint. Where older wording elsewhere in this file conflicts with the amendment, the amendment governs. This is a narrow hardening and expansion of the operating model, not a narrowing of the North Star.

> **North Star.** ForgeOS is never finished by exhausting a list of features. It is designed to continuously discover new domains, capabilities, relationships, information, resources, opportunities, and forms of value, incorporate legitimate new capabilities into the network, and compose what it knows and can do into useful outcomes.
>
> No initial category, geography, ontology, business model, product, marketplace, or interface defines the limits of ForgeOS.

> **Core operating thesis.** The world already contains enormous amounts of information, demand, supply, capability, unused capacity, relationships, assets, work, and opportunity. ForgeOS does not need to manually recreate the world. It builds lawful, permissioned, evidence-backed connections to it, structures what it can legitimately know, and uses that network to discover, compose, and execute useful outcomes.

> **User principle.** Users are guests, not operators of the machinery. ForgeOS should absorb complexity internally and expose simple intentions, choices, approvals, and outcomes. The sophistication of the engine should increase the simplicity of the experience.

---

# Implementation amendment — 2026-09-25

## Logical primitives and physical records

ForgeOS has exactly six **logical substrate primitives**:

`ENTITY`, `RELATION`, `EVENT`, `EVIDENCE`, `CAPABILITY`, and `ACTION`.

“Six primitives” describes the logical model; it does not claim the physical database has only six tables.

Existing operational and legacy tables—including `decisions`, `actions`, `outcomes`, `learning_events`, `CycleRun`, and current vertical tables—may remain during migration. Each must map to a logical primitive, serve as operational infrastructure, or be progressively adapted toward the substrate. They are not additional logical primitives.

`type_registry.schema_json` is authoritative for the attributes of each entity, relation, event, or capability type. One shared validation service must resolve the type, require `active` status for new rows, validate the attributes with a JSON Schema validator before persistence, and fail closed on unknown, proposed, deprecated, or malformed types/schemas.

The service is the single implementation point; callers must not duplicate schema rules.

New registry rows start `proposed`. The only path to `active` is an explicit `proposed → active` activation operation. `active → deprecated` is the only deprecation transition. Each records the actor, rationale, and verifiable activation evidence/process; the operation validates that record and is covered by tests.

Trusted bootstrap vocabulary may be installed active only by a deterministic, versioned system seed process that records its source.

---

# 0. Universal Product Model

ForgeOS is simultaneously:

1. a **universal substrate** for representing the world,
2. a **network** connecting what exists,
3. an **evidence system** for distinguishing what is known from what is uncertain,
4. a **capability system** describing what Forge can do,
5. an **opportunity engine** identifying potentially valuable combinations,
6. an **action engine** capable of authorized real-world execution,
7. a **composition engine** capable of combining existing resources into useful outcomes,
8. a **learning system** that improves from outcomes,
9. and a **user interface** that hides this complexity behind simple experiences.

The public website is therefore not the entire product.

The website is the human-facing surface of a deeper network and execution system.

---

# 0.1 The world is already full of supply

ForgeOS must not assume that every useful record must be manually discovered and entered by Forge staff or agents.

Real-world information already exists through many legitimate channels:

* users
* businesses
* providers
* marketplaces
* directories
* public datasets
* websites
* APIs
* feeds
* partners
* organizations
* communities
* documents
* transactions
* previous Forge interactions
* other authorized sources

The objective is therefore not:

> manually create a record for every thing in existence.

The objective is:

> **connect Forge to useful existing information and allow the network to grow through many lawful sources and participants.**

A marketplace does not manufacture the houses it lists.

Likewise, Forge does not need to manufacture every opportunity it eventually represents.

It needs to create the infrastructure through which existing supply, demand, information, capability, and opportunity can enter, connect, become useful, and produce outcomes.

---

# 0.2 Network density is an engine, not a vanity metric

Every legitimate addition to the network can potentially create new relationships and new combinations.

For example:

```text
person
  +
capability
  +
business need
  +
market information
  +
available asset
  +
distribution channel
  +
existing service
      ↓
new combination
      ↓
useful product / service / work / outcome
```

The value of the network therefore does not grow only linearly with the number of records.

Relationships, evidence, capabilities, and combinations can create additional value from information that already exists.

Forge should continuously search for useful combinations rather than merely accumulate records.

---

# 0.3 Opportunity composition

ForgeOS must distinguish between:

### Discovery

Finding a potentially useful thing, relationship, signal, need, capability, asset, or opportunity.

### Assessment

Determining whether the possibility is sufficiently supported, feasible, valuable, authorized, and actionable.

### Composition

Combining existing resources, information, capabilities, relationships, opportunities, and infrastructure into a potentially useful outcome.

### Execution

Taking an authorized real-world action.

### Verification

Observing what actually happened and preserving evidence.

### Learning

Using the result to improve future discovery, composition, and execution.

The core loop is therefore:

```text
WORLD
  ↓
DATA / SIGNALS
  ↓
STRUCTURE
  ↓
RELATIONSHIPS
  ↓
EVIDENCE
  ↓
OPPORTUNITIES
  ↓
COMPOSITION
  ↓
ACTION
  ↓
OUTCOME
  ↓
LEARNING
  ↓
BETTER NETWORK
  ↓
MORE OPPORTUNITIES
```

This loop is continuous.

---

# 0.4 Opportunity composition is not arbitrary combination

Forge must not interpret “compose anything” as “execute everything.”

Potential combinations must be evaluated against:

* evidence
* feasibility
* authorization
* law
* privacy
* source terms
* ownership
* security
* transaction cost
* compute cost
* execution cost
* risk
* opportunity cost
* expected value
* reversibility
* user intent where user approval is required

The objective is:

> **minimize legitimate value left unrealized**

not:

> execute every conceivable transaction.

---

# 0.5 One network, many products

Forge should not need a separate conceptual universe for every product it creates.

The same underlying network may support:

* marketplaces
* service businesses
* matching systems
* directories
* research products
* analytics
* APIs
* workflow products
* procurement systems
* discovery tools
* job/work systems
* logistics systems
* knowledge products
* financial/economic opportunities
* internal automation
* new products not yet conceived

A new product is often a **projection, workflow, capability composition, or interface over the existing network**, rather than a new universe.

---

# 0.6 Users are guests

ForgeOS should make the system's internal complexity invisible wherever possible.

A user should not be required to understand:

* entities
* relations
* evidence graphs
* ontology
* research tasks
* capability registries
* opportunity schemas
* agent orchestration
* database structure
* network traversal
* internal state machines

A user may simply express an intention:

> “I want to buy a house in Kathmandu.”

or:

> “I need someone to repair my website.”

or:

> “I have this skill. Can Forge find useful ways to make money from it?”

or:

> “I don't know exactly what I need.”

Forge should handle as much of the underlying work as it is legitimately able to perform.

The user should primarily encounter:

* understandable results
* useful recommendations
* simple actions
* clear approvals
* meaningful explanations
* honest uncertainty
* verified outcomes

The internal complexity should be absorbed by Forge.

---

# 0.7 The Guest-to-Engine model

The ideal interaction is:

```text
USER
  ↓
simple intention
  ↓
FORGE UNDERSTANDS
  ↓
DISCOVERS
  ↓
RESEARCHES
  ↓
CONNECTS
  ↓
COMPOSES
  ↓
PROPOSES
  ↓
USER APPROVES WHEN REQUIRED
  ↓
ACTS
  ↓
VERIFIES
  ↓
DELIVERS OUTCOME
```

Where Forge can legally and technically complete the workflow itself, it should not unnecessarily make the user perform internal operations manually.

Where authorization, consent, payment approval, account access, legal responsibility, or another human decision is required, Forge should stop at that boundary and make the required decision easy.

---

# 0.8 Data is an economic input, not an end in itself

ForgeOS should treat useful information as a major form of leverage.

However:

> **Data is valuable when it is accurate, relevant, fresh, connected, permissioned, and actionable.**

The system should therefore preserve:

* provenance
* source identity
* acquisition method
* timestamps
* freshness
* confidence
* truth state
* authorization/usage constraints
* transformation history
* relationships
* resulting outcomes

Forge should be able to transform:

```text
raw information
    ↓
structured information
    ↓
connected information
    ↓
knowledge
    ↓
intelligence
    ↓
opportunity
    ↓
product/service/action
    ↓
economic or useful outcome
```

The same underlying network may support multiple legitimate value surfaces.

This is a central economic property of the substrate.

---

# 0.9 Data acquisition must remain lawful and permission-aware

“Mine the world” does not mean unrestricted collection.

Forge may use information only where it has a legitimate basis to access, store, transform, and use that information.

Agents must respect:

* law
* privacy
* contractual restrictions
* source terms
* ownership/IP
* authentication boundaries
* rate limits
* robots/access controls where applicable
* user permissions
* partner permissions
* security requirements

The network should preserve enough provenance to determine where information came from and what its allowed use is.

---

# 0.10 The economic flywheel

ForgeOS should continuously seek useful value creation:

```text
MORE LEGITIMATE SOURCES
        ↓
MORE NETWORK INFORMATION
        ↓
MORE CONNECTIONS
        ↓
MORE EVIDENCE
        ↓
MORE DISCOVERABLE OPPORTUNITIES
        ↓
MORE COMBINATIONS
        ↓
MORE PRODUCTS / SERVICES / WORK
        ↓
MORE OUTCOMES
        ↓
MORE VERIFIED KNOWLEDGE
        ↓
BETTER NETWORK
        ↓
MORE VALUE CREATION
```

Revenue is a primary objective where appropriate, but not every useful outcome is immediately monetized.

The engine should recognize:

* direct revenue
* cost reduction
* increased utilization
* customer acquisition
* new products
* new capabilities
* new distribution
* partnerships
* information assets
* improved decision quality
* strategic optionality
* future opportunities

as potentially valuable outcomes.

---

# Implementation amendment — Truth, identity, migration, and evidence

## Truth transitions and evidence

One canonical transition service governs relation truth-state changes.

Minimum supported path:

`possible → hypothesized → tested → supported`

`possible` / `hypothesized → refuted` is allowed only when the constitution's evidence requirements are met.

`unknown` remains first-class.

No application path may assign `supported` directly.

A transition to `supported` requires a corresponding stored evidence record with preserved provenance.

`refuted` cannot become `supported` through direct state editing. New contrary information is recorded as new evidence and must pass the transition process.

Raw evidence is append-preserved when state changes.

Tests must cover:

* transition bypasses
* missing evidence
* provenance retention
* attempted revival of refuted claims
* contradictory evidence
* stale evidence
* source traceability

---

# Identity, deduplication, and merge history

Entity identity distinguishes the same real-world thing from distinct things that merely look alike.

Adapters use:

* stable source identifiers
* canonical URLs/identifiers
* normalized identity attributes
* provenance

to form deterministic idempotency keys protected by database uniqueness.

Fuzzy or uncertain matches are candidates, not merges.

Identity progresses through:

`candidate → corroborated → canonical`

only with recorded evidence/process.

When identity is uncertain, keep separate candidates and state the uncertainty.

Merge detection must be reviewable and must never silently merge.

A confirmed merge:

* archives/marks the displaced row as merged
* points to its survivor
* records merge history as substrate events/evidence
* preserves raw evidence

Neither entity nor its raw evidence is silently deleted.

---

# Migration authority and adapters

During each migration stage, existing vertical tables remain functional and authoritative for their existing records until an explicit, tested cutover names the substrate as authority.

Registered adapters expose those records to substrate projections while preserving:

* source IDs
* provenance
* source-to-substrate traceability

Migrations are:

* additive
* non-destructive
* tested
* reversible where practical

Source/substrate comparison tests are required.

A feature may not silently maintain two independent truths.

The end state converges on the substrate without discarding useful history.

The first adapter remains the mature:

`Signal → Pattern → Belief → Opportunity`

path.

Its existing tables remain authoritative during Wave 1.

Substrate entities, relations, events, and evidence are idempotent projections with links back to source rows.

Wave 1 must prove:

* insertion
* type validation
* identity/deduplication
* evidence validation
* truth transitions
* provenance
* idempotency
* restart behavior
* adapter consistency

before new domains are expanded.

---

# Feed and Network authority

The Feed is a projection, never canonical storage.

During migration it reads:

* substrate records
* explicitly registered legacy adapters

Every item retains its path to:

* entity
* relation
* event
* evidence
* provenance

The Network is a projection/traversal over:

* entities
* relations
* events
* evidence
* registered legacy adapters during migration

Relationships belong in the substrate.

Neither Feed nor Network is a hidden entity/relation database.

---

# Action, Outcome, LearningEvent

`ACTION` is the logical primitive for an authorized real-world attempt.

`Outcome` is the observation/state resulting from that action.

`LearningEvent` is learning derived from an outcome.

Existing physical action, outcome, and learning tables may remain operational during migration.

Adapters map them to the substrate.

They do not form a competing universe.

Existing authorization rules continue to govern whether an action may execute.

---

# Composition Engine

ForgeOS must eventually maintain an explicit **composition layer** above the substrate.

The composition layer does not introduce a seventh logical primitive.

It operates by discovering useful combinations among existing primitives.

A composition may contain:

* entities
* relations
* evidence
* capabilities
* opportunities
* actions
* outcomes
* external resources
* authorized integrations

A composition should be representable through existing substrate primitives and their relationships.

---

## Composition lifecycle

```text
candidate combination
        ↓
evidence check
        ↓
constraint check
        ↓
capability check
        ↓
value estimation
        ↓
feasibility check
        ↓
authorization check
        ↓
compose plan
        ↓
user approval if required
        ↓
authorized actions
        ↓
outcome
        ↓
verification
        ↓
learning
```

The engine should be capable of discovering both:

### Direct opportunities

```text
need ↔ capability
```

and:

### Composed opportunities

```text
need
+
capability A
+
capability B
+
asset
+
distribution
+
existing infrastructure
+
market information
    ↓
new product/service/work opportunity
```

---

# Composition does not imply ownership

Forge may discover that useful resources exist without owning them.

The system should distinguish:

* known
* accessible
* authorized
* available
* owned
* controlled
* partner-provided
* externally hosted
* merely possible

No action may assume ownership or authority that Forge does not actually possess.

---

# Capability propagation

Once Forge develops or acquires a verified capability, that capability should be reusable across domains where applicable.

For example:

```text
research capability
      ↓
housing research
business research
supplier research
market research
job research
...
```

Likewise:

```text
matching capability
      ↓
provider matching
job matching
supplier matching
asset matching
capital matching
...
```

Capabilities should therefore be modeled as reusable system assets rather than hard-coded into one vertical.

---

# Marketplace pattern

A marketplace is one valid pattern Forge can compose.

Forge does not need to manually create all supply.

Instead:

```text
existing world
      ↓
authorized sources / participants
      ↓
Forge network
      ↓
identity + evidence + normalization
      ↓
search + matching + composition
      ↓
transaction / service / outcome
```

Users and organizations may contribute supply directly.

External sources may contribute authorized data.

Forge may discover demand.

Forge may discover relationships between supply and demand.

Forge may create interfaces or services over the resulting network.

This allows large-scale network density without requiring Forge to manually visit every real-world participant.

---

# Coordination mechanism — parallel agents

Parallel agents have no guaranteed real-time communication.

The mechanism remains the file-based claim ledger:

`docs/CAPABILITY_QUEUE.md`

Before starting work on any capability gap, an agent appends:

```markdown
## [CLAIMED] Example capability

- Agent: agent-session-id
- Claimed at: timestamp
- Scope: exact scope
- Status: building
```

An agent must grep the queue before beginning.

If an unresolved claim already covers the scope:

* do not duplicate it
* extend the existing output
* or choose another gap

Claims older than 48 hours without `[DONE]` or `[ABANDONED]` may be reclaimed.

This is not real locking.

Database uniqueness and idempotency remain the second line of defense.

---

# Non-negotiable invariants

Any agent output violating these rules gets reverted.

## 1. No new top-level domain tables

Extend through the logical substrate and registered adapters.

Existing vertical/operational tables remain during migration.

Additive schema changes are permitted only under this contract.

---

## 2. No claim without evidence

Canonical truth transitions must reject unsupported state changes.

`supported` requires corresponding evidence with preserved provenance.

---

## 3. No action without authorization

Every real-world action must have an appropriate authorization reference before execution.

No autonomous financial or external-communication action without the required authorization.

---

## 4. No fabricated humans, transactions, opportunities, or evidence

Simulated/seed data must be labeled:

`source='simulated'`

and must never reach `support_level='supported'`.

---

## 5. No deletion of another agent's rows

Use:

* deprecated
* archived
* merged

where appropriate.

History is data.

---

## 6. No capability becomes active without a passing test

`status='active'` requires a valid `test_ref` and currently passing test.

---

## 7. Every verified claim must have literal verification evidence

Every report claiming verification must include:

* command
* relevant output
* date/context
* test/build reference

---

## 8. Existing subsystems are foundation, not disposable

The following are generalized rather than casually replaced:

* `belief_engine`
* `pattern_engine`
* `opportunity_engine`
* Decision/Action/Outcome/Learning loop
* Nepal Earn workspace
* scheduler
* existing public API
* existing useful frontend
* existing provider/service systems

---

## 9. No user-hostile complexity by default

New capabilities should not automatically become new forms, dashboards, configuration screens, or workflows for users.

If Forge can perform complexity internally, it should.

The default product question is:

> **Can Forge do this for the user instead of asking the user to operate the machinery?**

---

## 10. No narrow vertical capture

A new capability should be designed so that useful portions can generalize.

A housing marketplace may be an initial application.

The underlying capabilities should remain reusable for:

* vehicles
* services
* jobs
* assets
* suppliers
* equipment
* businesses
* other future domains

---

# Existing concepts mapped onto the substrate

| Existing concept | Substrate representation                                    |
| ---------------- | ----------------------------------------------------------- |
| Signal           | `ENTITY(signal)` + ingestion `EVENT`                        |
| Pattern          | substrate entity + source relations                         |
| Belief           | substrate entity + evidence-backed relations                |
| Opportunity      | `ENTITY(opportunity)` + evidence/causal relations           |
| Decision         | operational authorization/intent record mapped to substrate |
| Action           | logical `ACTION`                                            |
| Outcome          | resulting observation/state                                 |
| LearningEvent    | learning derived from outcome                               |
| Provider         | `ENTITY(provider)`                                          |
| ServiceListing   | entity + typed capability/availability relations            |
| Customer         | `ENTITY(customer)`                                          |
| RepairWorkItem   | `ENTITY(work_item)` + events                                |
| Offer            | `ENTITY(earning_offer)` + status events                     |
| MarketSignal     | registered entity type                                      |
| ResearchQuestion | registered entity/event types                               |
| UnusedCapacity   | registered entity type                                      |
| Asset            | registered entity type                                      |
| Product          | registered entity type                                      |
| Need             | registered entity type                                      |
| Capability       | logical `CAPABILITY`                                        |
| Relationship     | logical `RELATION`                                          |
| Feed item        | projection of substrate record                              |
| Marketplace      | product/projection/workflow over substrate                  |
| Composition      | relationships + capabilities + opportunity/action workflow  |
| `CycleRun`       | operational observability record                            |

Do not migrate existing data destructively.

---

# Feed and Network product philosophy

The Feed should expose the network without forcing users to understand the network.

It may contain:

* signals
* needs
* work
* opportunities
* capabilities
* people
* organizations
* assets
* discoveries
* connections
* evidence
* outcomes

But the presentation should remain human-oriented.

The Feed should answer:

> **What is useful to me right now?**

rather than:

> What database records exist?

The Network should make the richness of Forge discoverable without turning users into database operators.

---

# Product generation

ForgeOS should be able to identify when the network contains enough:

* demand
* supply
* data
* capability
* evidence
* distribution
* infrastructure
* relationships

to justify constructing a new useful product or service.

The engine may then:

1. identify the opportunity,
2. research it,
3. estimate feasibility and value,
4. identify missing capabilities,
5. acquire/build/test those capabilities,
6. compose the required resources,
7. construct a product/workflow/service,
8. test it,
9. expose it through an appropriate interface,
10. observe outcomes,
11. learn,
12. iterate.

This does not mean every idea becomes a product.

The system should continuously compare potential value against:

* cost
* risk
* feasibility
* authorization
* available capability
* time
* competition
* distribution
* evidence
* opportunity cost

---

# Economic engine

ForgeOS should treat legitimate economic value creation as a primary system objective.

It should continuously look for:

* revenue opportunities
* useful services
* underutilized assets
* unmet demand
* valuable information
* capability gaps
* distribution opportunities
* partnerships
* efficiency gains
* new products
* arbitrage-like inefficiencies where lawful and authorized
* opportunities to package existing capabilities
* opportunities to create reusable infrastructure

The system must not assume that one business model, marketplace fee, or vertical is the economic endpoint.

The same network may generate many independent economic surfaces.

---

# Autonomous capability creation loop

The capability lifecycle remains:

`proposed → building → tested → active → deprecated`

The autonomous capability loop is:

```text
Need / opportunity discovered
            ↓
      Can Forge solve it?
       ↙      ↓       ↘
     yes   partially    no
      ↓       ↓         ↓
     act   decompose   capability gap
                         ↓
                    research / build / find
                         ↓
                    acquire capability
                         ↓
                       test
                         ↓
                  activate capability
                         ↓
                     compose
                         ↓
                       act
                         ↓
                     outcome
                         ↓
                     learning
                         ↓
                  scan again
```

Every capability gap becomes a `CAPABILITY_QUEUE.md` claim before implementation.

---

# Sequencing

The mission is continuous.

These are waves, not a final checklist.

## Wave 1 — Correct substrate

Prove:

* type validation
* identity
* deduplication
* evidence
* truth transitions
* provenance
* idempotency
* migration safety
* adapter consistency

using the existing Signal → Pattern → Belief → Opportunity path.

---

## Wave 2 — Generality proof

Select one genuinely new domain.

Implement it using:

* `type_registry`
* substrate primitives
* services
* adapters

and zero unnecessary new top-level domain tables.

If the domain cannot be represented cleanly, fix the substrate.

Do not patch around a flawed abstraction.

---

## Wave 3 — Network density

Expand legitimate ingestion and contribution paths.

Enable the network to accumulate:

* entities
* relationships
* evidence
* capabilities
* needs
* opportunities
* assets
* work
* outcomes

from multiple legitimate sources.

The objective is **network usefulness**, not raw record count.

---

## Wave 4 — Composition engine

Implement real opportunity composition.

Forge should be able to identify combinations such as:

```text
need
+
available capability
+
asset
+
data
+
distribution
+
existing infrastructure
→
potential useful outcome
```

and evaluate them before action.

---

## Wave 5 — Autonomous capability expansion

Forge identifies capability gaps and:

* researches
* builds
* acquires
* integrates
* tests
* activates
* reuses

capabilities.

---

## Wave 6 — Product generation

Forge identifies sufficiently supported opportunities to create:

* products
* services
* marketplaces
* APIs
* workflows
* internal tools
* information products

using the existing network.

---

## Wave 7 — Economic engine

Continuously optimize legitimate value creation across multiple domains and business models.

The objective is not one successful marketplace.

It is a reusable system capable of discovering and executing many forms of legitimate value creation.

---

## Wave 8 — Replication

Geography becomes configuration rather than architecture.

Nepal is a bootstrap geography, not a boundary.

A successful capability should be portable across:

* cities
* countries
* industries
* domains

without rewriting the substrate.

---

# Launch definition

Forge Nepal is considered meaningfully operational when it is:

> **a continuously updating, evidence-backed network of real-world signals, needs, capabilities, opportunities, resources, people, relationships, and outcomes, with machinery capable of transforming that network into useful actions, products, services, and economic value.**

A first transaction is valuable evidence that the machine works.

It is not the definition of the machine.

The stronger measure is whether the system can repeatedly:

```text
discover
→ understand
→ connect
→ compose
→ act
→ verify
→ learn
→ create more value
```

with progressively less manual intervention.

---

# Design test for every proposed feature

Before implementation, every agent must ask:

> **Does this make Forge more general, more composable, more autonomous, more data-aware, more capable of discovering value, or easier for a user to benefit from?**

Prefer:

| Build this                             | Instead of this                  |
| -------------------------------------- | -------------------------------- |
| entity discovery + evidence            | manual listing entry             |
| generic matching capability            | one provider matcher             |
| reusable research capability           | one research page                |
| opportunity composition                | one hard-coded opportunity       |
| network traversal                      | one category feed                |
| reusable transaction/outcome machinery | one payment page                 |
| source adapters                        | manually copied records          |
| capability propagation                 | vertical-specific implementation |
| simple user intention                  | complex user workflow            |
| product generation infrastructure      | one hard-coded marketplace       |
| evidence-backed recommendations        | fabricated recommendations       |

A feature that merely makes one page prettier is not automatically bad.

But it should not consume architectural attention that belongs to general capability unless the product need justifies it.

---

# Constitutional boundaries

Open-world does not mean unconstrained.

ForgeOS must never violate:

### Truth

Do not pretend something happened.

### Authorization

Do not act through permissions Forge does not possess.

### Law

Do not violate applicable law.

### Terms

Do not use information or systems contrary to applicable contractual/source restrictions.

### Privacy

Do not expose or exploit private information without appropriate authorization.

### Security

Do not weaken safeguards to gain capability.

### Ownership/IP

Do not treat another party's protected assets as Forge's own.

### Risk

Do not execute high-risk actions merely because they are theoretically profitable.

### Economic discipline

Evaluate expected value against execution cost, transaction cost, compute cost, risk, and opportunity cost.

---

# Review protocol

Every agent touching ForgeOS reads this document first.

The workflow is:

1. Read this blueprint.
2. Read `docs/CAPABILITY_QUEUE.md`.
3. Query the live `type_registry`.
4. Read `STATUS.md`.
5. Inspect the existing implementation.
6. Claim the exact scope.
7. Implement the smallest general solution.
8. Test it.
9. Record evidence.
10. Update the claim.
11. Report exact verification commands/results.

If an agent conflicts with this document, this document wins.

If an implementation reveals a flaw in this document, the agent must document the conflict rather than silently inventing a parallel architecture.

---

# What ForgeOS ultimately becomes

ForgeOS is not defined as:

* a property marketplace
* a service marketplace
* a job board
* an AI assistant
* a social network
* a directory
* a research tool
* a trading system
* a CRM
* a workflow engine

It may contain or generate all of those.

The deeper abstraction is:

> **ForgeOS is a universal network and capability engine that structures legitimate knowledge about the world, connects entities and opportunities, discovers useful relationships, composes available resources and capabilities, executes authorized actions, learns from outcomes, and continuously creates new useful products, services, opportunities, and economic value.**

The world supplies information, needs, capabilities, resources, relationships, and possibilities.

Forge structures them.

Evidence constrains what Forge may believe.

Capabilities determine what Forge can do.

Composition determines what Forge can create from what it knows and can access.

Actions create outcomes.

Outcomes create learning.

Learning improves the network.

The network creates new possibilities.

And the cycle continues without a predefined final state.

> **ForgeOS is therefore not finished when its feature list is complete. It is successful when its ability to discover, connect, compose, act, learn, and create useful value keeps expanding.**
