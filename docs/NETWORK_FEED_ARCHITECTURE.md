# Forge Network Feed: architecture audit and first implementation

The feed is a public projection over canonical records. It does not store a second copy of signals, needs, opportunities, providers, or outcomes.

## Audit

| Network concept | Existing canonical records | Current limitation |
|---|---|---|
| Signal | `Signal`, `Evidence`, `Claim`, `EvidenceRelationship` | Public only when an external signal with a canonical URL supports a public-state claim. |
| Need / work | `DomainRecord`, `ResearchQuestion` | `DomainRecord.kind` is limited to job/offer/trade; research questions are private unless tied to a public claim. |
| Opportunity | `Opportunity`, `OpportunityEvent`, `RareSignalAssessment` | Opportunity is a hypothesis model without an explicit public flag; feed requires a public evidence claim and labels it as a hypothesis. |
| Capability | `ServiceListing`, `Product`, `EarningOffer` | Only active, public listings under verified providers are public capabilities today. |
| Actor / organization | `Provider`, `Customer` | No general actor or organization identity; organization is implicit in provider fields. Customer records stay private. |
| Resource | `RevenueSource`, `Option`, `ServiceListing` | No general resource model; these records cover distinct existing workflows. |
| Connection | `NetworkConnection` | Generic typed edge (`kind` + `id`) with no foreign-key identity registry; an edge must not make private endpoints public. |
| Action | `Action`, `Experiment`, `WorkerTask`, `IntegrationDelivery` | Internal execution records; public contact/action remains authorization-gated. |
| Outcome | `Outcome`, `CustomerEvent`, booking/domain lifecycle events | No universal public-visibility flag; the feed only follows the already public outcome-source contract and excludes sandbox rows. |

The smallest useful public network object today is a typed reference to a canonical record (`entity_type`, `entity_id`) plus a feed projection that carries its public title, change time, epistemic state, provenance, and typed relations. `NetworkConnection` already supplies generic edges. A durable universal node registry is still missing, but creating it before a cross-record identity need is proven would duplicate existing identity and lifecycle systems.

## Current data path

External source candidates are selected through the source/research task machinery. `collector_runner` dispatches only governed collectors; collected material becomes a `Signal`, then evidence and linked claims can be processed into patterns, beliefs, research questions, and opportunity hypotheses. `scripts/run_daily_cycle.py` is the canonical runner: it executes the Forge intelligence cycle, performs bounded collection (`FORGEOS_COLLECT_LIMIT`), then runs the autonomy/action cycle. The scheduler only wraps that runner.

The pipeline narrows at two boundaries: source execution is constrained by the current clearance/allowlist, and public views are split among discoveries, domain work records, verified providers/services, connections, and recorded alerts. The public UI has no combined chronology; opportunities, beliefs, and research questions have no public feed surface. The autonomous loop can structure internal records, but contact/transaction actions still require authorized adapters or operator approval, and outcome learning requires a recorded response.

## First implementation

`GET /public/feed` (also reachable through the existing `/api` alias) returns a chronological `PublicFeedItem` projection over existing records. Each entry retains the source entity type and ID, epistemic label, source reference, and typed relations. It includes evidence-linked claims, research questions tied to those claims, linked patterns/beliefs/opportunity hypotheses, verified public actors/capabilities, open work items, public connections whose endpoints also pass visibility checks, and real outcomes already in public source categories. It does not publish private contact fields, sandbox outcomes, confidence/popularity scores, or unlinked internal signals.

The root route enters `/feed`; the feed is a public surface distinct from operator cockpit views. Feed links now open a scoped network context using the same visibility-gated projection. The next serial work is a scalable, governed source registry. Neither requires fabricated actors or transactions.
