# Forge Network Feed: architecture audit and first implementation

The feed is a public projection over canonical records. It does not store a second copy of signals, needs, opportunities, providers, or outcomes.

## Shared world/value graph

The feed is one surface over Forge's shared world/value graph, not its data
model. Canonical records stay in their existing tables. `NetworkConnection` is
the first relation record to generalize: it should gain open relation
predicates, evidence and provenance, context, and time while keeping its
match/action lifecycle distinct from whether a relation is believed. Do not
add a second entity registry or copy provider, signal, opportunity, action, or
outcome records into another store.

Public projection is narrower than internal relation storage. Every endpoint
must qualify under its canonical record's existing visibility rules before a
relation can appear. An edge cannot promote a private or missing endpoint. The
feed omits internal strength, confidence, scores, evidence IDs, and private
context.

## Audit

| Network concept | Existing canonical records | Current limitation |
|---|---|---|
| Signal | `Signal`, `Evidence`, `Claim`, `EvidenceRelationship` | Public only when an external signal with a canonical URL supports a public-state claim. |
| Need / work | `DomainRecord`, `ResearchQuestion` | `DomainRecord.kind` is limited to job/offer/trade; research questions are private unless tied to a public claim. |
| Opportunity | `Opportunity`, `OpportunityEvent`, `RareSignalAssessment` | Opportunity is a hypothesis model without an explicit public flag; feed requires a public evidence claim and labels it as a hypothesis. |
| Capability | `ServiceListing`, `Product`, `EarningOffer` | Only active, public listings under verified providers are public capabilities today. |
| Actor / organization | `Provider`, `Customer` | No general actor or organization identity; organization is implicit in provider fields. Customer records stay private. |
| Resource | `RevenueSource`, `Option`, `ServiceListing` | No general resource model; these records cover distinct existing workflows. |
| Relation | `NetworkConnection` over canonical records | The matching workflow exists; general relation predicates and richer evidence/time semantics are the next relation-model task. A full actor identity record is not justified yet. |
| Action | `Action`, `Experiment`, `WorkerTask`, `IntegrationDelivery` | Internal execution records; public contact/action remains authorization-gated. |
| Outcome | `Outcome`, `CustomerEvent`, booking/domain lifecycle events | No universal public-visibility flag; the feed only follows the already public outcome-source contract and excludes sandbox rows. |

The smallest useful public network object is a typed reference to a canonical record (`entity_type`, `entity_id`) plus a feed projection that carries its public title, change time, epistemic state, provenance, and typed relations. Existing records remain authoritative; add a shared identity record only when evidence shows that current canonical references cannot safely represent a real cross-record identity.

## Current data path

External source candidates are selected through the source/research task machinery. `collector_runner` dispatches only governed collectors; collected material becomes a `Signal`, then evidence and linked claims can be processed into patterns, beliefs, research questions, and opportunity hypotheses. `scripts/run_daily_cycle.py` is the canonical runner: it executes the Forge intelligence cycle, performs bounded collection (`FORGEOS_COLLECT_LIMIT`), then runs the autonomy/action cycle. The scheduler only wraps that runner.

The pipeline remains deliberately bounded at source and action boundaries: source execution uses reviewed clearances, and contact/transaction actions need authorized adapters or operator approval. Relation generalization must preserve that boundary and must not convert a possibility into a fact. Outcome learning still requires an actual recorded response.

## First implementation

`GET /public/feed` (also reachable through the existing `/api` alias) returns a chronological `PublicFeedItem` projection over existing records. Each entry retains the source entity type and ID, epistemic label, source reference, and typed relations. It includes evidence-linked claims, research questions tied to those claims, linked patterns/beliefs/opportunity hypotheses, verified public actors/capabilities, open work items, public connections whose endpoints also pass visibility checks, and real outcomes already in public source categories. It does not publish private contact fields, sandbox outcomes, confidence/popularity scores, or unlinked internal signals.

The root route enters `/feed`; the feed is a public surface distinct from operator cockpit views. Feed links now open a scoped network context using the same visibility-gated projection.

## Governed source expansion

`source_clearance_registry` validates exact HTTPS targets, reviewed evidence references, geography/category scope, robots and terms locations, current review windows, and an explicit redirect allowlist. A persistent database gate enforces per-source request intervals across worker/API instances. Task dispatch, the tool adapter, the smoke CLI, and collector entry points use this policy; collector implementations with no active registry entries fail before network access. Only the exact GovInfo notice is cleared, and its clearance expires at the recorded UTC day boundary. Additional source categories and geographies use the same record shape after their policy review; uncertain sources remain disabled.

S11 and S12 complete the feed projection and context navigation. S13 completed governed discovery expansion. S14 moved source-address repair, evidence-to-claim linking, and candidate-connection discovery into the canonical cycle; when bounded collection creates signals, the scheduler performs one internal follow-up pass so those signals can reach patterns, beliefs, opportunities, and the feed during the same run. The opportunity feed projection follows its existing Evidence-to-Signal-to-Claim relations, not a duplicate identity table. The current serial work follows `docs/SERIAL_PATH.md` and the 2026-09-25 Build Path.
