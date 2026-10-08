# Hami Architecture

**Status:** Proposed canonical authority; becomes accepted repository
architecture only after owner review and commit to `main`.

This document records current direction and verified repository boundaries. It
does not claim that planned capabilities exist or authorize external actions.
Historical plans and reports remain preserved; they are not automatically
current architecture.

## 1. Authority & Governance

- `main` is the canonical accepted repository state. Until this document is
  accepted and committed there, it is a proposal, not an authority override.
- After acceptance, this file is the single current architecture authority.
  Agent conversations, other documents, and implementation suggestions are
  proposals unless incorporated here and committed to `main`.
- Before significant implementation, identify the applicable section here.
  For a conflict, report the existing rule, proposed change, and exact section
  requiring amendment; do not silently change architecture or implementation.
- Agents execute owner-approved work. Preserve history and existing behavior;
  classify before migration or removal. Production access, external contact,
  publication, spending, deployment, destructive changes, and migrations need
  their own explicit authorization.
- `docs/CAPABILITY_QUEUE.md` remains the capability/claim ledger;
  `docs/REVENUE_LOG.md` remains the commercial evidence ledger.

## 2. Hami Purpose

Hami is a real-world system centered on **REAL WORK, COMMUNITY, and ECONOMY**.
It discovers and helps realize value through people, capabilities, resources,
relationships, authorized actions, and outcomes. AI is a means, not the
destination. What Hami discovers matters more than the technology used to
discover it.

AI and model-building are not Hami's core product. External models, agents,
APIs, people, specialists, machines, and software are replaceable capabilities
that Hami may use within authorization, evidence, privacy, legal, and cost
boundaries. Hami evolves the existing ForgeOS system in place; it is not a
second architecture.

## 3. Permanent Invariants

- Preserve one Hami system and one semantic truth model.
- Do not fabricate people, customers, demand, evidence, research results,
  external responses, bookings, transactions, outcomes, or revenue.
- Do not make unsupported claims or execute an action without its required
  authorization and external permission.
- Keep `REAL`, `TEST`, `MOCK`, and `HYPOTHESIS` distinct. Tests and simulations
  are never customer, revenue, or real-world evidence.
- Preserve meaningful historical truth. Prefer archive, correction, or
  evidence-backed merge over destructive deletion.
- Price is not revenue; an opportunity is not an outcome; a plan is not
  execution; a report is not evidence.
- No new paid software or infrastructure before first real customer revenue
  except a verified legal, security, payment, or critical-execution need.
  Forge Bot runs natively in ForgeOS; n8n is not a dependency.

## 4. Six-Primitives Substrate

There are exactly six canonical logical primitives; there is no seventh
semantic primitive.

| Primitive  | Meaning                                                             |
| ---------- | ------------------------------------------------------------------- |
| ENTITY     | An identifiable thing.                                              |
| RELATION   | A typed connection whose meaning and support are preserved.         |
| EVENT      | Something observed or a meaningful system transition.               |
| EVIDENCE   | The sourced, provenance-bearing basis for a claim.                  |
| CAPABILITY | Something an entity or system can do, access, or reliably provide.  |
| ACTION     | An operation that may be proposed or executed within authorization. |

`type_registry.schema_json` is authoritative for registered semantic types.
Type registration and activation follow the existing explicit lifecycle.
Operational tables may support queues, retries, leases, locks, and workflow
execution; they do not create additional semantic primitives or replace
canonical events for meaningful transitions.

Feed is a projection. Network is a projection and traversal. Neither is
canonical storage.

## 5. Truth / Identity / Provenance

Truth progresses only through:

`possible → hypothesized → tested → supported`

Supported claims require stored evidence and provenance. Material
contradictions and insufficient evidence remain visible; unsupported
interpretation does not become fact through repetition, model output, or a
score.

Identity progresses only through:

`candidate → corroborated → canonical`

No silent fuzzy merge is permitted. A merge must preserve the identities'
history and evidence.

Use these labels precisely: **observed, verified, reported, inferred,
hypothesized, unknown**. Retain source, time, method, and transformation
provenance appropriate to the record. Meaningful semantic transitions produce
canonical events.

## 6. Human & Authorization Boundaries

Keep four scopes distinct:

- **Public world:** information explicitly eligible for public projection.
- **Private human context:** user-controlled personal context, scoped to its
  owner and not automatically projected.
- **Authorized shared context:** information or action shared only for its
  recorded purpose, scope, parties, and duration.
- **System internal state:** operational tasks, diagnostics, and private
  reasoning that are not public facts.

Private human context does not automatically become public world data, Feed or
Network content, or evidence about external reality. Authentication identifies
or establishes a session; authorization separately determines what that
identity may do. A policy `ALLOW` is not proof an action executed.

External actions require explicit authorization where required, plus a
configured capability and external permission. Standing authorization, if
introduced, is limited to its recorded action, purpose, scope, spend, rate,
privacy, counterparty, exclusions, expiry, and evidence requirements. Never
contact a person, publish an offer, spend money, or simulate prospect
conversations without explicit owner authorization.

## 7. Real Work / Community / Economy

The system's real-world loop is:

`need or signal → research and evidence → capability connection → authorized
action → external response → outcome → learning`

Community is currently an **outcome**, not a separate active product. Do not
build social features to manufacture activity; trust and community should
emerge from real participants doing real work and contributing to real
outcomes.

Recognize customer, transaction, and revenue states only from attributable
evidence. Measure `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` only from
verified real transactions; if none exist, report **NOT MEASURABLE**, not zero.

## 8. Commercial focus and selection boundary

`docs/ORIGIN.md` is the source of Hami's mission: **expand the frontier of
what can be understood, discovered, created, coordinated, and accomplished
in reality.** No commercial segment, product category, or revenue ranker
narrows that mission. Candidate unknowns and experiments are compared at the
existing Bet/unknown seam; commercial opportunity and money rankers remain
scoped to exploitation after an owner has chosen a commercial question.

`AGENTS.md` governs active-segment claims where earlier architecture wording
conflicts with it. The first commercial work remains owner-run discovery for
one real customer and one real paid outcome. No category, offer, price, or
willingness to pay is assumed in advance. Education-abroad and
foreign-employment consultancies remain hypotheses until the owner reports
five real conversations; work only with licensed agencies if supported, and
foreign employment requires separate regulatory and reputation review.
No outreach, offer, contact, spend, or external experiment is authorized by
this document.

**Historical proposal, retained for provenance (superseded 2026-10-08):**
an earlier proposed version of this document called Forge Bot v0 reaching a
paying consultancy the active commercial Bet, named education-abroad
consultancies as the opening segment hypothesis, and set a 30-day paid-outcome
kill rule starting at the first owner-run discovery conversation. That text
was a proposal, not verified customer evidence or authorization, and is not
the current selection mandate. The slow-reply/social-seller material remains
historical; its probe is paused, not killed or deleted, and it receives no
special selection priority.

## 9. Parked commercial work

- Forge Bot and seller/inbox material are capabilities or historical probes
  inside ForgeOS/Hami, not Hami's mission, a separate product, or a fixed
  strategic frontier.
- Community is an outcome, not an active product bet.
- Premium frontend work remains parked unless required for correctness,
  security, or an owner-selected outcome-oriented pilot.
- No segment, product, offer, or pivot becomes active merely because it is
  easy to formulate, monetize, or test. Any future commercial focus must
  follow the global candidate-selection and owner-authorization boundaries.

## 10. Data / World-Scale Principles

Hami does not need to copy every fact about the world into its database.
Distinguish canonical persistent state, external information, evidence and
provenance, on-demand research, bounded working sets, caches, indexes, and
real-world events. Optimize for legitimate world-scale availability and useful
retrieval, not indiscriminate replication.

Retain external data only within applicable access, license, privacy, storage,
attribution, and retention rules. Prefer bounded, permitted retrieval; record
what was obtained and what remains unknown.

## 11. Runtime Architecture

Repository configuration and current documentation identify the root
TanStack/Vite application as the current web surface and FastAPI under
`backend/` as the business API. `vercel.json` routes `/api/auth/*` to the web
service, other `/api/*` requests to FastAPI, and remaining paths to the web
service. The separate Next.js application, archived at
`docs/archive/legacy-frontend/`, remains a legacy/local surface used by the
Compose configuration; it is not the root Vercel web service.

The backend has a local SQLite path and supports a configured database URL.
The web authentication/private-context layer has a PGLite fallback and uses a
configured PostgreSQL URL when supplied. These are distinct application
runtime paths; do not assume one database or a particular production
configuration without current evidence.

Existing vertical ORM models and substrate adapters remain during migration.
The substrate is the canonical semantic direction, but the repository has not
completed a single-model migration. Extend existing paths; do not introduce a
competing domain, feed, network, research, capability, or action store.

## 12. Frontend Direction

Premium frontend development is parked under Section 9. Future work, when its
trigger is met, should use an original Hami visual language: premium, immersive,
polished, responsive, real-data-driven, and Nepal-rooted without stereotype.
BabyDoge or other sites may inform broad craft and quality only; do not copy
branding, assets, layouts, wording, identity, or exact animations.

Until the trigger, make only UI changes required by the active bet or by
correctness and security. This does not authorize a redesign.

## 13. Legal / Product Boundaries

Under the current owner-specified Nepal operating assumption, virtual-asset and
cryptocurrency activity is prohibited for Hami. This is an operating boundary,
not independent legal advice or a substitute for qualified counsel.

**Hami token/currency is OUT OF SCOPE.** It is not a deferred bet or roadmap
item and must not be designed, implemented, promoted, or integrated. Do not
route around this boundary through foreign exchanges, VPNs, offshore
infrastructure, or other mechanisms. Reconsideration requires a material
change in applicable law/regulation and qualified legal review.

Preserve consent, privacy, applicable licensing, and regulatory review.
Foreign-employment activity is not in the active bet and requires separate
regulatory and reputation review.

## 14. Current Repository Reality

- The repository is `kn33r0s3/ForgeOS`; Hami is the product identity evolving
  this codebase. Historical ForgeOS/Sanipops names remain in code and records
  for compatibility and history.
- `services/forge-bot/SPEC.md` and `services/forge-bot/state/MAPPING.md` are
  design/contract documents. Local code implements a gated private
  `ForgeBotLeadContact` record, owner-only summary, internal digest path, and
  registered privacy-minimized intake/opt-out/erasure events. Intake and
  customer-facing messaging remain disabled by default and unimplemented,
  respectively; code presence does not authorize outbound contact. There is no
  standalone `services/forge-bot/state/schema.sql`; deployed settings and
  real-world use remain unverified by repository state.
- The commercial evidence ledger is `docs/REVENUE_LOG.md`. It currently
  contains no commercial evidence entries; that is not a claim about
  uninspected external systems.
- Architecture descriptions conflict in preserved documents:
  `README.md` identifies the root Vite app as current;
  `docs/archive/legacy-docs/FINAL_ARCHITECTURE.md` describes FastAPI + Next.js
  + SQLite as current; `docs/archive/legacy-docs/FEATURE_INVENTORY.md` contains
  historical Express/in-memory and restoration claims. Use Section 11 for the
  repository configuration observed here; preserve the conflicting documents
  as history.
- The repository documents an outcome-first, owner-run discovery gate. Section
  8 operationalizes the 30-day kill rule as one verified real paid consultancy
  outcome by day 30 after the first recorded owner-run discovery conversation;
  this threshold was not found verbatim in the earlier inspected materials.
- Production database, active production project/hosting plan, channel
  permissions, authorized consultancy, current pricing, and current real-world
  customer evidence are environment-dependent and are not established by this
  document.

## 15. Change-Control Rules

Before significant work, identify the relevant section and verify the current
code/runtime boundary. If a proposal conflicts with this document, stop at the
conflict and report:

```text
CONFLICT:
<existing architectural rule>

PROPOSED CHANGE:
<new proposal>

REQUIRED DOCUMENT CHANGE:
<exact section>
```

Wait for explicit owner authorization before treating a conflicting proposal
as accepted architecture. Once approved, update this document and commit the
change to `main`; do not rewrite history. Keep historical documents intact
unless a separate cleanup task authorizes changes. Report implemented,
verified, unverified, blocked, and unknown states distinctly.
