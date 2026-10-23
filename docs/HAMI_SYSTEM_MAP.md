# Hami system map

This file records how existing routes and engines form one Hami system. It is a map of implemented surfaces and their boundaries, not a promise that every subsystem is already operational.

## Foundational scope: value itself

**North star:** Hami's domain is value itself—in every form, state, context, and possible transformation—investigated without artificial boundary, claimed only with evidence, and acted upon only when governed and viable.

Hami is an open-ended system for discovering, understanding, transforming, and realizing value. Its scope is not confined to one product, market, industry, geography, resource type, or predefined operation. Examples of value and transformation are illustrations, never an exhaustive taxonomy. New domains, categories, relations, and operations remain discoverable; existing architecture should represent them through the shared substrate rather than requiring a new parallel Hami.

Hami examines what value exists or could exist; who or what needs, holds, enables, blocks, or loses it; which relationships and capabilities could change the situation; what transformation might help; what it costs and affects; and what evidence would confirm or refute the hypothesis. Value can be economic, physical, informational, human, social, ecological, operational, potential, or something not yet classified. Money is one possible outcome and measurement, not the definition or boundary of value.

The shared semantic primitives remain canonical:

- **ENTITY** — the thing, actor, resource, need, condition, or possibility under consideration.
- **RELATION** — how entities depend on, exchange with, enable, constrain, transform, or affect one another.
- **EVENT** — what happened and how a state changed.
- **EVIDENCE** — provenance-bearing support, contradiction, or uncertainty about a claim.
- **CAPABILITY** — a transformation or action that can be performed, with its preconditions and limits.
- **ACTION** — a governed attempt to change the world or test a claim.

Use the existing substrate and operational projections. Do not create a new top-level semantic primitive or parallel value engine to represent a newly discovered domain.

### Value and truth states

Keep these states distinct: **possible → hypothesized → tested → supported → realized**. The sequence is not automatic; evidence may weaken a claim, a test may fail, and an apparent opportunity may be rejected. “Tested” means a test actually ran and its result is recorded. “Supported” requires relevant evidence and still allows uncertainty. “Realized” requires an observed outcome at the appropriate verification level. A deployed route, model output, score, policy ALLOW, synthetic fixture, payment callback, or proposed action does not by itself prove value was realized.

Every consequential path must preserve provenance, scope (REAL / TEST / MOCK / HYPOTHESIS), costs, risks, rights/permission, and authorization. Hami's investigative scope can remain open-ended while each action stays bounded by law, safety, privacy, permissions, viability, and explicit execution capability. It may recommend not acting when the evidence or expected result does not justify action.

### The value loop

The existing system loop is one connected process, not a mandate to build separate products:

`OBSERVE → VERIFY → UNDERSTAND → DECIDE → ACT → MEASURE → LEARN → repeat`

Viewed through value, that process means **discover → understand → identify or test a transformation → realize or reject it → measure consequences → learn**. Existing Findings, Unknowns, Evidence, Experiments, Opportunities, Decisions, Actions, Outcomes, and Learning are connected views/states of this process. A particular seller experiment or revenue path is one instance, not Hami's identity or limit.

Future work must ask: What value exists or could exist? What prevents its realization? Which relation or transformation could change that? What evidence would discriminate between alternatives? What is the cheapest authorized, safe, falsifiable next action? What actual benefit, loss, cost, and externality resulted? Prefer work that improves this loop across domains, and report uncertainty honestly.

### Mapping the five current homepage capabilities

The five capability labels are the current operating instruments, not a taxonomy of value and not five separate subsystems. Keep their implementation statuses honest in the UI.

| Current capability | Role in the open-ended value loop | Truth boundary |
| --- | --- | --- |
| **Observe** | Discover candidate value, needs, resources, events, and conditions from permitted sources. | The current five governed source adapters describe today's implementation, not the outer limit of sources or domains Hami may investigate. Every new source needs its own access, provenance, policy, and quality checks. |
| **Preserve** | Carry evidence, provenance, source/scope, and uncertainty across discovery and later reasoning so value is not detached from its basis. | Recording an observation does not establish that its interpretation is true or that value exists. |
| **Investigate** | Turn observations into unknowns, hypotheses, and tests; understand constraints and compare possible transformations. | General background, a heuristic score, or an inferred need is not proof of demand, feasibility, or benefit. A test must actually run and its result must be recorded. |
| **Act** | Attempt a justified transformation or intervention that could realize value. | Requires a real capability, legal/safe context, permission and policy authorization. A proposal or policy ALLOW is not proof that an action executed or succeeded. Current Act status remains gated. |
| **Learn** | Measure actual changes, costs, losses, benefits, and unintended consequences; preserve the outcome and revise understanding; reopen discovery. | Do not mark economic value realized without appropriately verified real-world outcome evidence. The current public status remains “Not yet validated” until such an outcome is established. |

Operationally, Observe and Preserve support **Discover**; Preserve spans every stage; Investigate primarily supports **Understand** and the selection/testing of transformations; Act supports **Transform / attempt to Realize**; Learn verifies whether value was actually realized and feeds that result back into the next Discover cycle. The mapping is many-to-many, not a rigid pipeline: a finding can return to investigation, a test can disconfirm a hypothesis, and inaction can be the right result.

## One product, one navigation source

- `src/lib/hami-system.ts` owns the public top navigation (`NAV`), footer groups (`FOOTER_GROUPS`), page-to-page paths (`SYSTEM_PATHWAYS`), and the path inventory guarded by tests (`PUBLIC_SYSTEM_PATHS`).
- `src/components/layout/hami-pathways.tsx` renders contextual links into the same product loop.
- `GroupAreaGrid` is the single renderer for group-area cards on `/group` and `/group/businesses`; every strategic direction points to an existing Hami route without claiming a separate company.
- Each `/services/$slug` page uses the canonical `services` data to link to its sibling services and back to `/services`. The contextual CTA component distinguishes Hami's own catalogue from the separate external-provider directory.
- `features.json` is the route/API lifecycle registry. `public/features.schema.json` defines its public schema. Every implemented top-level route must have an explicit registry state.
- The header, footer, pathways, sitemap, and registry are checked together by `src/lib/features.test.ts`. A new page is not complete just because its file exists. Tests now check both directions: every navigation/pathway target must exist, and every live page must have a deliberate entry path or an explicit workflow-only role. Technology, Ventures and provider-request status also return to shared pathways. Terms no longer advertise the closed contact route.

## The two connected flows

### Understanding loop

`/discoveries` (observations) → `/feed` (connected public records) → `/unknowns` (unanswered world questions) → `/experiments` (real logged tests) → `/opportunities` (hypotheses with evidence) → `/actions` (what the system has recorded as waiting or running).

Links are navigation, not evidence. A public feed relation is not proof. An opportunity hypothesis is not demand. An action summary is not authorization to execute.

### Work and value loop

`/needs` is the broad public entry for needs, offers, reciprocal exchanges, and the ways Hami can currently contribute; it is not tied to one market hypothesis. `/domain` reuses the existing `DomainRecord` and `terms` fields for public needs/jobs, offers, and trades. The ten known economic terms are now shown through the public projection after contact-detail sanitization; incomplete terms remain visible as a proposal but cannot pass the existing acceptance gate. `/services` remains Hami's own bounded catalogue and `/providers` remains the separate verified-provider path. `/requests/$id` shows an actual provider request and never treats pending as acceptance.

The earlier missed-inquiry sprint remains an experiment hypothesis, not Hami's identity or boundary. Keep each path's record types and permissions distinct. Never infer acceptance, fulfillment, or payment from a post, match, or booking request.

## Surface lifecycle

- **Live** — an existing route or endpoint has a real defined purpose and is reachable through an appropriate Hami path.
- **Hidden** — retained, but not advertised as a normal public destination: owner controls, test/demo routes, closed intake, or contact while no owner-provided email exists.
- **Archived** — compatibility routes kept for old links and redirected to the canonical surface: `/climb`, `/what-we-learned`, `/work`, and `/request-a-project`.
- **Planned** — a future capability that has no implemented route/endpoint yet.

Hidden does not mean delete. Archived does not mean create another page. A page must not be marked live simply because a route responds.

## Operator and authorization boundary

`/owner` is a noindex cockpit for readiness, inquiry evidence, ForgeBot, intelligence/research, products and payments visibility, operating model, scouting, and buyer-side journey records. `/operations` is a separate noindex console for economic state, action records and explicitly initiated operations. The pages themselves are directly addressable and are not secret URLs; privileged API calls must enforce the owner-key boundary. The owner console links to Operations after the owner has unlocked it, and Operations links back; neither belongs in public navigation. Traced operations money/action reads check the key; deployed middleware fails closed for protected mutations and private substrate/contact reads when the key is missing. Production key presence, deployed SHA and end-to-end owner access still require independent verification. Their existence does not make action execution, outreach, intake, payment collection, or revenue live.

Before changing those boundaries, trace the existing endpoints and key/authentication behavior. Preserve owner approval, action envelopes, daily caps, source clearance, provenance, and evidence labels. Do not make the app automatically execute merely to make a control appear active.

### Global value frontier (current owner-only implementation)

The existing private `/owner` console's Orchestrator & intelligence section reads `GET /forge/substrate/discovery/frontier` with the owner API key. The endpoint is a read-only projection over existing records: dynamic-kind discovery findings, unresolved unknown-map Claim projections, open/planned research questions, unfinished research tasks, proposed/building/tested capabilities, and failed/disputed outcomes. It interleaves lanes instead of comparing unlike value dimensions on a single score, exposes bounded-scan warnings, and explicitly states that its records do not enumerate total world value.

This is a **visibility and integration seam**, not autonomous discovery or action. It does not trigger discovery, promote a question, create a task, execute an action or validate a hypothesis. An item must proceed through its existing evidence, source-clearance, planning, authorization, action and outcome contracts. The unknowns markdown registry remains authoritative; its database Claim rows are a projection. The current frontier sees only recorded state and the inputs already ingested by Hami, so broader real-world awareness still requires additional permitted source capabilities.

The frontier now also surfaces explicit cross-type/cross-domain `WorldRelation` records and bounded two-edge `possibility_path` hypotheses. These paths are composed only from recorded, directionally valid relations; their state is always `hypothesized`, source references include every entity and relation in the chain, and they are not treated as proof of value, an offer, consent, or authorization. The owner view displays the chain and each relation's recorded state. This is the first path-composition slice, not yet an end-to-end possibility-to-outcome engine: it does not yet identify missing capabilities for a path, propose a cost-bounded experiment, or link a completed action back to a verified outcome automatically.

## Required integration rule for future work

Before adding a service/page/engine:

1. Find the existing route, API, component, registry row and data loader before creating a replacement.
2. Extend or connect the canonical implementation rather than start a parallel one.
3. Give every route a registry state, intent, and provenance; public paths must resolve to live entries.
4. If it is a public journey, wire it through the shared navigation or contextual pathway and, where applicable, the sitemap.
5. Add regression coverage for the route, data source, state/permission boundary, and any relationship claimed by the UI.
6. Report implemented, hidden, unavailable, TEST, and planned states exactly. Never fabricate evidence, users, bookings, payment, actions, or revenue.
