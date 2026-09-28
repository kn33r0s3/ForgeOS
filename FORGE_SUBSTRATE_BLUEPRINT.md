# ForgeOS Blueprint — Amendment 2026-09-28: Demand-First + Reuse-First

**Nature:** narrow, additive amendment to the CURRENT authoritative Universal Substrate blueprint. Not a parallel blueprint. It does not touch the 2026-09-25 six-primitive amendment, which stays in force unchanged.

**How to apply:** Part A is inserted verbatim as a new section immediately after the "Implementation amendment — 2026-09-25 / Logical primitives and physical records" section (before "# 0. Universal Product Model"). Part B is a list of anchored in-place edits (find the quoted anchor text, apply the change). Part C is the status table. Where older wording conflicts, this amendment governs.

---

# PART A — Insert as new section

## Implementation amendment — 2026-09-28: Demand-first, reuse-first

### A.1 Economic objective

> ForgeOS does not exist to endlessly hunt signals, collect data, or reinvent solved problems.
>
> ForgeOS exists to understand the world's unmet demand and mobilize existing authorized capabilities to create value — researching or inventing only when existing capability is insufficient.

Higher-level objective:

> Discover what people, organizations, and markets are trying to obtain, understand the unmet need, and connect that need to existing authorized capabilities wherever possible.

**Principle:**

> **Reuse before research. Research before invention. Invention only when necessary.**

This is not blind copying. Reuse or adaptation must remain within applicable law, licenses, contracts, permissions, privacy/IP constraints, platform terms, and explicit economic authorization. Signal collection, data accumulation, and research are subordinate mechanisms; none is an objective.

### A.2 Operating hierarchy (mandatory ordering)

1. **Observe / identify possible demand**
2. **Understand the actual need**
3. **Search existing knowledge, patterns, capabilities, suppliers, services, software, infrastructure, marketplaces, algorithms, logistics, payment rails, and other authorized resources**
4. **Reuse or adapt** an existing proven solution when one exists
5. **Test / validate** the fit and economics
6. **Take authorized action**
7. **Observe** the real-world result
8. **Learn**
9. **Only if existing capability is insufficient:** research the unknown
10. **Only when genuinely necessary:** develop or invent a new capability

Steps 9–10 are reachable only through a recorded capability gap (A.6). Planners, agents, and schedulers must not enter them by default.

### A.3 Do not over-categorize the world

- Raw observations may originate anywhere and may initially be uncategorized. No fixed taxonomy (product / service / job / B2B / consumer / agriculture / manufacturing / …) is required before a possible need can be observed.
- Categories are **derived projections**, never prerequisites for observation or ingestion.
- Demand-shaped observations the system should be able to recognize include: requests, unmet needs, complaints, searches, procurement needs, unavailable products, unavailable services, recurring work, shortages, price/availability gaps, capability gaps, emerging demand, customization requests, requests for suppliers/providers, and other economically meaningful demand signals.
- The canonical substrate remains exactly the six primitives: `ENTITY`, `RELATION`, `EVENT`, `EVIDENCE`, `CAPABILITY`, `ACTION`. **No new top-level primitive is added.**

**Representation of a need.** The existing blueprint already lists `Need` as a registered entity type (see mapping table). That remains the only formal representation. Specifically:

- A raw observation is an `EVENT` (with `EVIDENCE` and provenance) that may reference `ENTITY` rows and `RELATION`s, and may be stored **before** any need type is assigned.
- A `need` `ENTITY` is a *derived, hypothesis-grade projection* created only when the observation is understood well enough to type it. It is not required for observation.
- Need types and any refinements go through `type_registry` (`schema_json` authoritative; new rows `proposed`; explicit `proposed → active`).
- Category labels (housing, procurement, repair, …) are attributes or projections over needs and must not gate ingestion.

### A.4 Demand is not automatically truth

A demand signal is not automatically:

- a verified customer
- a validated market
- an opportunity
- a supported claim
- evidence of willingness to pay
- evidence that fulfillment is possible

ForgeOS must keep observation, hypothesis, evidence, validation, and real-world outcome distinct. The truth progression is unchanged:

`possible → hypothesized → tested → supported`

Supported claims still require stored evidence with preserved provenance. No application path may assign `supported` directly. Willingness to pay and fulfillability are separate claims, each needing its own evidence.

### A.5 Existing-capability utilization

ForgeOS should preferentially use the capability already present in the world, where legally and technically authorized, including:

- existing software and APIs
- known algorithms and mathematical methods
- established business models
- manufacturers, suppliers, service providers, workers, and professionals
- marketplaces
- logistics networks and payment systems
- communication infrastructure
- public and licensed datasets
- established scientific and technical knowledge
- existing production infrastructure and distribution channels

ForgeOS's value is therefore often in **connecting and orchestrating** existing capabilities around unmet demand rather than recreating them. Modeling: these are `CAPABILITY` and `ENTITY` records distinguished by the existing states (known / accessible / authorized / available / owned / controlled / partner-provided / externally hosted / merely possible). Discovering that a resource exists never implies Forge may use it.

### A.6 Capability gap (evidence-based)

A **capability gap** is a recorded finding that a search of existing authorized capabilities (A.2 step 3) did not yield an adequate match for a specific need. It must be stored as `EVENT` + `EVIDENCE` (what was searched, when, what was found, why insufficient) linked to the need and any candidate capabilities. A gap may not be asserted from assumption. Only a recorded gap authorizes bounded research or capability creation. Each gap still requires a `docs/CAPABILITY_QUEUE.md` claim before implementation.

### A.7 Demand → capability → value loop

**Default path (existing capability suffices):**

```text
WORLD
  → OBSERVATION
  → POSSIBLE NEED
  → NEED UNDERSTANDING
  → EXISTING-CAPABILITY SEARCH
  → SOLUTION MATCH
  → ECONOMIC VALIDATION
  → AUTHORIZED OFFER/ACTION
  → REAL-WORLD RESPONSE
  → FULFILLMENT
  → PAYMENT/OUTCOME
  → EVIDENCE
  → LEARNING
  → NEXT DEMAND
```

**Exception path (no adequate existing capability):**

```text
WORLD
  → NEED
  → EXISTING-CAPABILITY SEARCH
  → CAPABILITY GAP
  → BOUNDED RESEARCH/DISCOVERY
  → TEST
  → NEW/ACTIVATED CAPABILITY
  → ACTION
```

The second path is the exception, not the default. It is bounded by the need it serves.

### A.8 Research system role

Research is a mechanism, not the objective. It is invoked only when:

- the need is insufficiently understood,
- existing capabilities cannot be identified,
- existing evidence is insufficient,
- a capability must be validated,
- an economic assumption needs testing, or
- genuinely new knowledge or capability is required.

The research planner's governing question is, eventually:

> **What do we need to know or obtain next to resolve this economically meaningful need?**

not "What source can we query next?" Every research task should therefore reference the need (or gap) it serves and the decision it would unblock. The capability-discovery work already in progress is preserved; its purpose is resolving genuine capability gaps, not indiscriminate web crawling.

### A.9 Demand-first (inventory-light) commerce

Value creation may begin with demand, not inventory. ForgeOS does not inherently require inventory ownership before demand is discovered. Where legally and contractually permitted, an operator or business may:

1. identify genuine demand,
2. determine a credible fulfillment path,
3. make an accurate offer,
4. receive an order,
5. procure / manufacture / source afterward,
6. fulfill, or
7. cancel/refund according to disclosed terms if fulfillment genuinely fails.

This is **not** permission to fabricate availability, pretend to possess inventory, misrepresent shipping or lead times, or accept orders with no credible fulfillment path. A credible fulfillment path must exist as stored `EVIDENCE` (supplier/provider identified, terms, lead time, cost basis) before any offer `ACTION` is authorized, and offers must disclose terms accurately. The invariant is unchanged:

> **No unsupported claim and no unauthorized action.**

### A.10 Status vocabulary

Every capability referenced in future work under this amendment must be labeled **CURRENTLY IMPLEMENTED**, **TARGET ARCHITECTURE**, or **FUTURE CAPABILITY** (see Part C). Nothing is "currently implemented" without literal verification evidence (Invariant 7).

### A.11 Contradictions resolved

- "Discovery" of signals/data as a goal → discovery serves need identification; signal/data accumulation is never an objective.
- Research/build/find offered as peer options to reuse → reuse is strictly first; research/invention require a recorded gap.
- Taxonomy-implying vertical framing → categories are projections only.
- Implicit inventory-before-demand assumptions → demand may precede inventory under A.9.

---

# PART B — Anchored in-place edits

**B1. Authority header.** After the sentence beginning "This is the authoritative Universal Substrate specification," add:
> A second dated amendment (2026-09-28, Demand-first, reuse-first) follows the 2026-09-25 amendment. Both govern; the North Star is unchanged and is realized through demand-first, reuse-first operation.

**B2. Core operating thesis** (the blockquote beginning "The world already contains enormous amounts…"). Append one sentence:
> ForgeOS's economic purpose is to find unmet demand and connect it to that existing capability; it collects information only in service of that purpose.

**B3. §0 Universal Product Model.** Item 5 "an **opportunity engine** identifying potentially valuable combinations" → "an **opportunity engine** identifying unmet demand and potentially valuable combinations of existing capability". Add after the item list: "These are means to demand-first value creation, not ends."

**B4. §0.1 "The world is already full of supply."** After "connect Forge to useful existing information and allow the network to grow through many lawful sources and participants." add: "The same holds for capability and fulfillment: the world already contains manufacturers, suppliers, providers, software, logistics, and payment rails. Forge connects to them before building anything."

**B5. §0.3 core loop.** The diagram beginning `WORLD → DATA / SIGNALS → STRUCTURE …` is retained as the *knowledge-side* view. Immediately after it add: "The action-side operating loop is the demand→capability→value loop (2026-09-28 amendment A.7). `DATA / SIGNALS` denotes raw observations that may include demand signals; structuring exists to identify unmet demand and match existing capability." In the "Discovery" definition add: "Discovery is primarily discovery of unmet demand and of existing capability able to meet it."

**B6. §0.3 Composition.** Add: "Composition begins by searching existing authorized capabilities. Composing from existing capability is the default; creating a capability is the exception (A.6)."

**B7. §0.4 (composition evaluation list).** Add two items: "* existence of an adequate existing capability (reuse over invention)" and "* credible fulfillment path where an offer is contemplated".

**B8. §0.7 Guest-to-Engine diagram.** Replace the `DISCOVERS → RESEARCHES → CONNECTS → COMPOSES` segment with `UNDERSTANDS THE NEED → FINDS EXISTING CAPABILITY → RESEARCHES ONLY IF NEEDED → CONNECTS → COMPOSES`.

**B9. §0.8 Data is an economic input.** Add: "Data is collected or retained to the extent it helps resolve an identified need, validate a capability match, or evidence an outcome. Volume of data is not a goal."

**B10. §0.10 Economic flywheel.** No structural change. Add: "The flywheel is driven by resolved demand (need → capability → outcome), not by ingestion volume."

**B11. Composition lifecycle.** Before `candidate combination` insert `need understood → existing-capability search`. Under "Direct opportunities `need ↔ capability`" add: "This is the default and is attempted first. Composed opportunities apply when no single existing capability suffices."

**B12. Capability propagation.** Add: "Propagation is one form of reuse: a verified capability is applied to a new need before a new capability is built."

**B13. Marketplace pattern.** Add: "A marketplace may be initiated by demand before supply is onboarded, subject to A.9 (no fabricated availability)."

**B14. Non-negotiable invariants.** Add:
> **11. Reuse before research; research before invention.** Agents and planners must record an existing-capability search before proposing research or capability creation for a need. Capability creation without a recorded gap is reverted.
>
> **12. Demand is not truth, and no offer without a credible fulfillment path.** Demand observations remain `possible`/`hypothesized` until evidenced. No offer/order action without stored fulfillment-path evidence and accurate disclosed terms.
>
> **13. Categories are projections.** No ingestion or need recognition path may require a fixed taxonomy.

Also amend Invariant 10 "No narrow vertical capture": add "Needs must not be modeled through vertical-specific need tables."

**B15. Mapping table.** Change the `Signal` row to: `ENTITY(signal)` + ingestion `EVENT` (a raw observation; may or may not indicate demand). Change the `Need` row to: registered entity type — derived, hypothesis-grade projection of observed demand (A.3). Add row: `Capability gap` → `EVENT` + `EVIDENCE` linked to need and candidate capabilities (A.6). Add row: `Demand observation` → `EVENT` + `EVIDENCE` (+ optional `RELATION`s); no new primitive. Change `ResearchQuestion` note: "serves a need or capability gap".

**B16. Feed and Network philosophy.** No change to authority (projection only). Add to the Feed list: "needs (unmet demand) and matched existing capability are first-class feed content".

**B17. Product generation.** Replace step 2 "research it" with "search existing capability and solutions for it; research only remaining unknowns" and step 5 "acquire/build/test those capabilities" with "reuse, integrate, or (only for recorded gaps) acquire/build/test those capabilities".

**B18. Economic engine.** Add to the list: "demand-first commerce under A.9". Add: "Reusing and orchestrating existing authorized capability is the preferred route to revenue over building new capability."

**B19. Autonomous capability creation loop.** In the diagram, change `Can Forge solve it?` to `Can existing authorized capability solve it? (search first)`. Change the `no` branch label to `recorded capability gap`. Change `research / build / find` to `find existing → bounded research → build (in that order)`. Add below: "Every capability gap becomes a `CAPABILITY_QUEUE.md` claim before implementation" (existing sentence) — and "must reference the need and recorded search evidence".

**B20. Sequencing.** Wave 3: replace "**network usefulness**, not raw record count" with "**resolved demand and network usefulness**, not raw record count". Wave 4: add "existing-capability search precedes composition". Wave 5: add "only for recorded gaps; existing capability is reused first". Wave 6: add "demand-first, reuse-first". No wave is added or removed.

**B21. Design-test table.** Add rows: `demand understanding + existing-capability search` **instead of** `blind signal collection`; `capability reuse/adaptation` **instead of** `reinvention`. Add to the design test question: "…or reduce collection/reinvention by connecting demand to existing capability?"

**B22. Launch definition.** Add after the quoted definition: "Meaningful operation includes resolving real unmet demand using existing capability at least once with evidence."

**B23. Review protocol.** Add step: "Before proposing research or capability work for a need, confirm the existing-capability search is recorded."

**B24. "What ForgeOS ultimately becomes."** Append the two A.1 quoted sentences.

---

# PART C — Status table (labels must be verified against the repo before finalizing)

| Item | Status | Basis |
|---|---|---|
| Six logical primitives, `type_registry` validation, proposed→active | CURRENTLY IMPLEMENTED (per 2026-09-25 amendment; verify) | Blueprint; not independently verified here |
| Signal → Pattern → Belief → Opportunity path as Wave 1 adapter source | CURRENTLY IMPLEMENTED (existing tables) | Blueprint; Phase 1 forced cycle previously hit a SQLite `disk I/O error`, so end-to-end status unverified |
| Truth-transition service, identity/merge, Feed/Network projections | TARGET ARCHITECTURE unless verified | Blueprint Wave 1 requirements |
| `docs/CAPABILITY_QUEUE.md` claim ledger | CURRENTLY IMPLEMENTED as a convention (verify file) | Blueprint |
| Capability discovery (in progress) | IN PROGRESS; re-scoped to gap resolution | This amendment A.8 |
| Existing-capability search step preceding research | TARGET ARCHITECTURE | A.2/A.6 |
| Capability-gap records (`EVENT`+`EVIDENCE`) | TARGET ARCHITECTURE | A.6 |
| Need-centred research planner | TARGET ARCHITECTURE | A.8 |
| Demand-first offer/order flow with fulfillment-path evidence | FUTURE CAPABILITY | A.9 |
| Autonomous orchestration of suppliers/logistics/payments | FUTURE CAPABILITY | A.5 |
| Autonomous capability invention | FUTURE CAPABILITY | A.2 step 10 |

---

# PART D — Immutable under this amendment

Exactly six logical primitives; `type_registry.schema_json` authoritative; proposed → active explicit activation; Feed is a projection; Network is traversal/projection; no unsupported claims; no action without authorization; no fabricated humans, transactions, evidence, sources, or outcomes; no silent fuzzy identity merges; no destructive deletes (archive/merge); provenance mandatory; existing vertical tables remain during additive migration; existing useful capabilities not degraded; additive evolution only; no parallel architecture.