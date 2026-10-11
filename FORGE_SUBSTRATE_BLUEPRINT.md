# Hami — Universal Economic Intelligence & Action System

## Authoritative Blueprint & Implementation Contract

**Status:** Authoritative
**Product:** Hami
**Architecture:** Universal Substrate
**Primary operating environment:** Nepal-first, globally portable
**Principle:** One system, one architecture, continuously improved from verified evidence

---

# 1. PURPOSE

Hami is a universal economic intelligence and action system.

Its purpose is to observe legitimate information about the world, understand demand and opportunity, research what is unknown, connect needs with capabilities and resources, take authorized actions, observe real-world outcomes, and learn from those outcomes.

Hami is not defined as:

* a repair-shop application
* a service directory
* a booking application
* a chatbot
* a generic AI assistant
* a generic SaaS dashboard
* a marketplace
* a single industry product
* a single pilot
* a single business model

Those may become surfaces, applications, experiments, or commercial wedges built on Hami.

They are not Hami's ontology.

The long-term system is intended to become capable of discovering and pursuing legitimate economic opportunities across many domains, including services, businesses, work, skills, products, resources, logistics, procurement, property, and other authorized economic activity.

Hami must expand from evidence and demonstrated capability rather than from uncontrolled feature proliferation.

---

# 2. THE OPERATING PRINCIPLE

The central Hami loop is:

WORLD / PUBLIC / AUTHORIZED SIGNALS
→ DEMAND
→ RESEARCH
→ EVIDENCE
→ QUALIFIED OPPORTUNITY
→ CAPABILITY MATCH
→ AUTHORIZED ACTION
→ REAL RESPONSE
→ TRANSACTION / NO TRANSACTION
→ OUTCOME EVIDENCE
→ LEARNING
→ BETTER DISCOVERY

The system must continuously improve this loop.

Hami does not need to possess all information in advance.

Hami needs the ability to determine:

> What do I need to know, where can I legitimately find it, what evidence would establish it, what can I do about it, and what happened afterward?

That is the core intelligence/action problem.

---

# 3. PRODUCT IDENTITY

The active product identity is:

**Hami**

ForgeOS and Sanipops are legacy implementation/history unless specific artifacts from those systems are deliberately retained or migrated into Hami.

There must be one active product.

There must not be competing active identities such as:

Hami frontend + ForgeOS backend

or:

Hami + Sanipops as separate applications performing overlapping work.

Historical names may remain inside migrations, historical commits, compatibility identifiers, archives, or provenance where changing them would be unsafe.

User-facing active surfaces should use Hami.

---

# 4. ONE SYSTEM RULE

Hami is one system.

There is one authoritative:

* ontology
* substrate
* database truth model
* evidence model
* capability model
* action model
* research engine
* worker/task architecture
* network projection
* feed projection
* frontend
* backend

Applications and surfaces may differ.

The underlying semantic system must not.

No implementation may introduce a competing architecture merely because the existing one is incomplete.

When existing infrastructure can be extended safely, extend it.

When a legacy implementation contains valuable capabilities, migrate the capabilities into Hami.

When code is genuinely obsolete, archive or remove it after classification.

---

# 5. UNIVERSAL SUBSTRATE

The Hami Universal Substrate contains exactly six logical primitives:

1. ENTITY
2. RELATION
3. EVENT
4. EVIDENCE
5. CAPABILITY
6. ACTION

No seventh top-level semantic primitive may be introduced.

These six primitives are the foundation for all domains.

---

# 6. ENTITY

ENTITY represents an identifiable thing.

Examples may include:

* person
* business
* organization
* website
* source
* place
* asset
* product
* project
* opportunity
* capability-bearing organization
* event-related object

New entity types must be registered through the authoritative type registry.

An entity's identity lifecycle is:

CANDIDATE
→ CORROBORATED
→ CANONICAL

No silent fuzzy merging is permitted.

Potentially matching entities must remain distinct until identity is adequately corroborated.

---

# 7. RELATION

RELATION represents a supported connection between entities or other canonical objects where the schema permits it.

Examples:

business HAS_CAPABILITY capability

business LOCATED_AT place

demand REQUIRES capability

source PRODUCES signal

entity RELATED_TO entity

Relations must have appropriate evidence or provenance where required by their semantic meaning.

A relation must never be created simply because it appears plausible.

---

# 8. EVENT

EVENT records something that happened or a meaningful system transition.

Events are central to temporal truth.

Examples:

* signal observed
* research task created
* retrieval executed
* evidence recorded
* truth state changed
* capability tested
* action authorized
* action executed
* external response received
* booking requested
* booking confirmed
* booking declined
* transaction completed
* revenue verified
* experiment changed
* experiment archived

Meaningful state transitions must leave an event trail.

Events must not fabricate external reality.

---

# 9. EVIDENCE

EVIDENCE records the basis for knowledge.

Evidence must preserve appropriate provenance.

Depending on the source and use, provenance may include:

* source identity
* retrieval time
* retrieval method
* source location/reference
* content or derived representation where storage is permitted
* extraction method
* relevant fragment
* integrity information
* actor/system
* transformation history

Evidence supports claims.

Evidence does not automatically make every interpretation true.

---

# 10. TRUTH STATE

Knowledge must move only through:

POSSIBLE
→ HYPOTHESIZED
→ TESTED
→ SUPPORTED

A claim becomes SUPPORTED only when appropriate evidence and provenance exist.

No unsupported claim may be presented as established fact.

When evidence is insufficient:

`INSUFFICIENT_EVIDENCE`

must remain a valid result.

When evidence conflicts materially:

the contradiction must remain visible rather than being silently resolved.

---

# 11. CAPABILITY

CAPABILITY represents something an entity or system can do, provide, access, perform, or reliably support.

Examples:

* commercial refrigeration repair
* software development
* translation
* transport capacity
* construction
* procurement
* data retrieval
* research
* communication
* booking
* payment processing

A capability is not automatically available merely because an entity appears capable of it.

Availability, authorization, capacity, price, timing, geography, willingness, and other conditions remain separate facts.

Capabilities must be supported by appropriate evidence where required.

Active capabilities may require a passing `test_ref` or equivalent verification defined by the authoritative implementation.

---

# 12. ACTION

ACTION represents an operation Hami can propose or execute.

Action lifecycle:

PROPOSED
→ AUTHORIZED
→ EXECUTING
→ COMPLETED

with appropriate failure, cancellation, expiry, or equivalent states supported by the implementation.

No action requiring authorization may execute without authorization.

Examples:

* retrieve permitted public information
* create a research task
* send an approved message
* make an authorized booking request
* submit an authorized form
* invoke an approved API
* perform an authorized external operation

Authorization must be explicit where required.

---

# 13. TYPE REGISTRY

`type_registry.schema_json` is authoritative for semantic types.

New registry status transitions must follow the existing activation process:

PROPOSED
→ ACTIVE

No code may silently invent active semantic types outside the authoritative registry.

No new top-level domain tables may be created simply because a domain has not yet been modeled.

Existing vertical tables may remain during additive migration.

---

# 14. OPERATIONAL STATE EXCEPTION — D1

Operational state required to make workflows reliable may be represented through narrow `op_` tables.

This is an implementation exception, not a new semantic ontology.

`op_` tables may represent current execution/workflow state such as:

* queue state
* retries
* leases
* execution locks
* orchestration state
* temporary workflow state
* integration execution state
* bounded task state

They must not become the canonical semantic source of truth.

They must not redefine:

ENTITY
RELATION
EVENT
EVIDENCE
CAPABILITY
ACTION

Every meaningful semantic transition must produce the appropriate canonical EVENT.

Where practical, operational state must be reconstructable, reconciled, expired, or otherwise related back to canonical state.

The D1 exception must be documented in `STATUS.md`.

---

# 15. NO PARALLEL DOMAIN ARCHITECTURE

The following are prohibited as independent semantic systems:

* a separate research ontology
* a separate source ontology
* a separate opportunity ontology
* a separate network database
* a separate feed database
* a second evidence model
* a second capability model
* a second action model

A feature may have a specialized implementation internally, but its canonical meaning must remain represented through the six primitives.

---

# 16. FEED

Hami Feed is a projection.

It is not canonical storage.

Feed entries are generated from current canonical entities, relations, events, evidence, capabilities, actions, signals, opportunities, and outcomes.

Feed must not become a second database of truth.

Feed should help users discover what matters now.

A future global Hami Feed may expose:

* opportunities
* demand
* relevant entities
* capabilities
* research results
* actions
* outcomes
* changes
* emerging patterns

Only facts supported by the underlying system may be surfaced as factual claims.

---

# 17. NETWORK

Hami Network is a projection/traversal over the substrate.

It represents relationships among:

* entities
* capabilities
* demand
* opportunities
* evidence
* events
* actions
* resources

Network is not canonical storage.

It should allow exploration of what Hami knows and how things connect.

No graph nodes may be fabricated for visual appearance.

---

# 18. USER INTERFACE

The primary navigation should clearly separate:

HOME
NETWORK
RESEARCH
OPPORTUNITIES
ACTIONS

Home and Network must never redirect to one another.

HOME answers:

> What is Hami doing, and what matters right now?

It should present real system state.

Possible information:

* current signals
* research activity
* qualified opportunities
* authorized actions
* outcomes
* blockers
* system status

No fake metrics.

NETWORK answers:

> What entities, capabilities, relationships, and opportunities does Hami know about?

RESEARCH answers:

> What is Hami investigating and what has it learned?

OPPORTUNITIES answers:

> What economic needs or possibilities has Hami identified?

ACTIONS answers:

> What can Hami do, what has been authorized, and what happened?

---

# 19. VISUAL IDENTITY

Hami must have a distinct visual identity.

It must not simply inherit:

* old ForgeOS styling
* old Sanipops styling
* generic enterprise admin aesthetics
* generic AI-purple interfaces
* crypto-dashboard aesthetics
* repair-shop dashboard aesthetics

The visual system should communicate:

* intelligence
* trust
* energy
* human usability
* network scale
* economic purpose
* clarity

Avoid excessive gradients, neon overload, visual noise, and scattered hardcoded colors.

Use centralized semantic theme tokens.

At minimum:

* background
* surface
* surface-elevated
* foreground
* muted
* border
* primary
* primary-foreground
* secondary
* success
* warning
* danger
* info
* focus

One styling architecture only.

---

# 20. RESEARCH AUTONOMY

The central missing capability is not access to information.

The world already contains enormous amounts of publicly accessible information and many APIs, datasets, websites, feeds, maps, government records, business pages, scientific resources, and other sources.

However:

PUBLIC
does not mean:

UNRESTRICTED API
or:
UNRESTRICTED BULK STORAGE
or:
UNRESTRICTED AUTOMATED COLLECTION.

Hami must distinguish these concepts.

The research engine's job is to transform legitimate information access into evidence-backed knowledge.

---

# 21. RESEARCH LOOP

The canonical research process is:

RESEARCH QUESTION
→ INFORMATION REQUIRED
→ SOURCE DISCOVERY
→ SOURCE SELECTION
→ ACCESS/POLICY CHECK
→ RETRIEVAL
→ EXTRACTION
→ EVIDENCE
→ TRUTH UPDATE
→ UNKNOWN / CONTRADICTION ANALYSIS
→ NEXT RESEARCH TASK
→ STOP

The loop must be bounded.

Hami must not browse forever merely to appear autonomous.

---

# 22. RESEARCH QUESTIONS

For any research task Hami should identify:

1. What is already known?
2. What is unknown?
3. What exact fact is needed?
4. What would establish that fact?
5. Which sources could establish it?
6. Which source is currently appropriate?
7. How can the source legitimately be accessed?
8. What constraints apply?
9. What happens if the source fails?
10. What is the next useful step?
11. When should research stop?

This decision structure is more important than building a huge framework.

---

# 23. SOURCE REPRESENTATION

A source is represented through the existing substrate.

Typically:

SOURCE
= ENTITY of an appropriate registered type

Relationships describe what it provides or relates to.

Evidence records what was obtained from it.

Capabilities describe what Hami can do with it.

Actions represent permitted retrieval/interaction operations.

Do not introduce a top-level `sources` domain table merely to make source management convenient if the existing substrate already provides the necessary representation.

---

# 24. SOURCE INVENTORY

Hami should maintain knowledge about usable sources including, where schema permits:

* source identity
* source type
* accessibility
* geographic relevance
* signal classes
* access method
* authentication requirement
* freshness
* reliability
* permitted use
* storage constraints
* attribution requirements
* rate limits
* cost
* provenance requirements
* last successful retrieval
* failure state

This information must be represented within the authoritative architecture.

---

# 25. SOURCE POLICY ENFORCEMENT

Source constraints must be executable.

They must not exist only as documentation.

Where known and applicable, the retrieval layer must enforce:

* access restrictions
* authentication requirements
* rate limits
* storage restrictions
* attribution requirements
* robots/access controls
* request budgets
* paid-call restrictions
* provenance requirements

If an operation violates a known constraint:

DO NOT EXECUTE IT.

Record the blocked/failed path and pursue an allowed alternative where available.

Public visibility alone is not sufficient evidence of permission for unrestricted automated use.

Third-party terms, API quotas, pricing, and restrictions must be verified from current authoritative sources before Hami depends on them.

---

# 26. FIRST RESEARCH IMPLEMENTATION

Do not build a giant abstract research framework before proving the loop.

First identify existing:

* collectors
* source inventory
* research planner
* workers
* task system
* retrieval code
* evidence system
* provenance
* retry logic

Then extend the strongest existing path into one operational research loop.

The first real implementation should work against approximately two or three legitimate sources.

Prefer existing sources already integrated into the repository.

The purpose is to prove the complete loop, not maximum source coverage.

---

# 27. RESEARCH FAILURE CLASSES

Hami must distinguish:

### NOT PUBLIC

The required information cannot be established through legitimate publicly available sources.

### PUBLIC BUT RESTRICTED

The information may be visible publicly, but automated access, storage, or other processing is restricted.

### FRAGMENTED

The required conclusion requires multiple sources.

### UNAUTHORIZED

The next action requires credentials, authorization, or permission that Hami does not possess.

### ORCHESTRATION FAILURE

The necessary information or capability may be available, but the system failed to determine or execute an appropriate research path.

This vocabulary must appear in operational reporting where appropriate.

---

# 28. RESEARCH STOPPING CONDITIONS

Research ends when one of the following is true:

`RESEARCH_COMPLETE`

Required facts have sufficient evidence.

`INSUFFICIENT_EVIDENCE`

Legitimate research paths cannot establish the required fact.

`BLOCKED`

Required access, credentials, payment, or authorization is unavailable.

`CONTRADICTION_UNRESOLVED`

Evidence materially conflicts and cannot yet be safely reconciled.

`NO_ACTIONABLE_NEXT_STEP`

Additional research would not materially improve the decision.

---

# 29. SOURCE FALLBACK

A source failure must not automatically terminate research.

Where alternatives exist:

SOURCE A
→ failure/inaccessibility/insufficient evidence
→ SOURCE B
→ failure/insufficient evidence
→ SOURCE C
→ final state

Every attempted path should retain provenance.

A fallback may not bypass a restriction merely by using an alternative mechanism that still violates the original constraint.

---

# 30. COST OF INFORMATION

Cost-aware source selection is useful but should not be overbuilt initially.

The first implementation should establish:

* bounded request budgets
* zero-cost/public-source preference
* no paid calls without authorization
* recording of actual known retrieval cost

Do not introduce sophisticated expected-value purchasing until the basic research loop works.

Eventually Hami may reason:

EXPECTED INFORMATION VALUE
versus
INFORMATION ACQUISITION COST

but this is a later optimization layer.

---

# 31. DEMAND DISCOVERY

Hami must discover demand rather than merely wait for users to provide complete requests.

Legitimate signal classes may include:

* public requests
* procurement notices
* tenders
* RFPs
* hiring requirements
* business announcements
* service requests
* event requirements
* authorized inbound channels
* public business information
* open datasets
* other legitimate economic signals

Private information must not be collected merely because technical access exists.

---

# 32. DEMAND MODEL

A demand signal should be researched for:

1. exact request
2. current/active status
3. requester or requesting entity
4. capability required
5. location
6. urgency
7. constraints
8. supporting evidence
9. plausible capability candidates
10. unknown information
11. next legitimate research action

Unknown remains unknown.

---

# 33. OPPORTUNITY QUALIFICATION

A qualified opportunity requires:

REAL SIGNAL
AND
CURRENT/RELEVANT
AND
IDENTIFIABLE NEED
AND
PLAUSIBLE CAPABILITY
AND
ACTIONABLE NEXT STEP

Possible outcomes include:

QUALIFIED
REJECTED
INSUFFICIENT_EVIDENCE
BLOCKED

No system component should be forced to classify an opportunity positively when evidence does not support it.

---

# 34. CAPABILITY MATCHING

Capability matching uses:

ENTITY
+
RELATION
+
CAPABILITY
+
EVIDENCE

Example:

ENTITY:
Business A

CAPABILITY:
Commercial refrigeration repair

RELATION:
Business A HAS_CAPABILITY refrigeration_repair

EVIDENCE:
specific evidence establishing that relationship

Do not invent:

* availability
* pricing
* experience
* geography
* current capacity
* willingness
* customer intent

unless supported.

---

# 35. AUTHORIZED ACTION

The action system bridges intelligence and the real world.

An action must have:

* action identity
* target
* purpose
* authorization status
* actor
* execution state
* result
* evidence/provenance where applicable

No external action may be represented as successful merely because Hami intended to perform it.

---

# 36. REAL-WORLD TRUTH

These distinctions are mandatory:

REQUESTED ≠ BOOKED

BOOKED ≠ COMPLETED

ESTIMATED ≠ ACTUAL

POSSIBLE ≠ QUALIFIED

QUALIFIED ≠ CONVERTED

CONTACTED ≠ RESPONSE

RESPONSE ≠ TRANSACTION

TRANSACTION ≠ VERIFIED REVENUE

TEST ≠ REAL CUSTOMER

INTERNAL SIMULATION ≠ EXTERNAL OUTCOME

These distinctions must survive into databases, APIs, UI, reports, and RESULT cards.

---

# 37. REVENUE TRUTH

Revenue is real only when verified.

A pipeline may legitimately record:

* opportunity identified
* provider identified
* provider contacted
* response received
* customer accepted
* transaction pending
* transaction completed
* verified revenue

Any of these may still equal:

`$0 revenue`

Estimated opportunity value must remain separate from actual revenue.

Hami must never manufacture traction.

---

# 38. FOUNDING COMMERCIAL ENGINE

The first commercial objective is not to sell software for its own sake.

The objective is to prove:

Hami finds real opportunities and helps convert qualified opportunities into real conversations and transactions.

Initial market:

Nepal

But Nepal is an operating environment, not a different architecture.

The system must remain portable.

---

# 39. FOUNDING REVENUE PILOT

The initial commercial experiment may use:

**Hami Founding Revenue Pilot**

The starting offer should minimize buyer risk.

Possible economics:

* qualified opportunity fee
* successful introduction fee
* outcome/success fee
* hybrid structure

The exact pricing model must be learned from actual customer behavior.

Do not assume that a particular price, conversion rate, or ROI is acceptable before evidence exists.

---

# 40. HAMl OPERATOR

A later product surface is:

**Hami Operator**

Example founding implementation:

**$249 one-time**

This is a productized deployment of Hami capabilities around an organization's real inbound workflow.

It is not the definition of Hami.

Possible capabilities:

* inbound opportunity capture
* approved immediate responses
* structured qualification
* consent handling
* bounded follow-ups
* booking requests
* owner confirmation
* outcome tracking
* evidence/provenance
* daily summaries
* leakage identification

The buyer purchases working operational capability rather than:

* a PDF
* prompts
* generic consulting
* a promise
* an unverifiable AI story

---

# 41. OPERATOR WORKFLOW

Canonical workflow:

INBOUND LEAD
→ CONSENT / INTAKE
→ HONEST INITIAL RESPONSE
→ QUALIFICATION
→ FOLLOW-UP 1
→ FOLLOW-UP 2
→ BOOKING REQUEST
→ OWNER CONFIRMATION
→ BOOKED / DECLINED / EXPIRED
→ OUTCOME
→ EVIDENCE / MEASUREMENT

Maximum follow-up behavior must be bounded.

Owner confirmation must remain available.

Permanent opt-out must be respected.

---

# 42. PILOT HONESTY

The pilot must not promise:

* guaranteed leads
* guaranteed bookings
* guaranteed revenue
* guaranteed ROI
* specific conversion rate
* complete autonomy
* unlimited messaging
* universal industry support

Success means producing reliable evidence about operational and/or economic value.

---

# 43. HUMAN INVOLVEMENT

Human involvement is allowed during the founding period when Hami lacks safe automation.

The system should identify actor type where possible:

* Hami automation
* human operator
* external party

Human work should increasingly become:

HUMAN + HAMI
→ REPEATABLE PATTERN
→ AUTOMATED HAMI CAPABILITY
→ HUMAN SUPERVISES EXCEPTIONS

Humans remain an authority boundary where required.

---

# 44. FIRST ECONOMIC MILESTONE

The first meaningful milestone is not a polished SaaS UI.

It is:

> Hami discovers a legitimate real-world demand signal, researches it, identifies a capable provider, executes an authorized introduction or action, receives a real response, and records the actual outcome without fabrication.

Revenue may still be `$0`.

Verified payment is a subsequent milestone.

---

# 45. EXPERIMENT LOGIC

Experiments should follow:

RESEARCH_COMPLETED
→ EXPERIMENT_PROPOSED
→ EXPERIMENT_AUTHORIZED
→ EXPERIMENT_EXECUTED
→ HUMAN_RESPONSE_RECEIVED
→ REVENUE $0 OR VERIFIED AMOUNT
→ EVIDENCE_GENERATED
→ NEXT_DECISION_UPDATED

No step may be claimed without evidence.

---

# 46. METRICS

Research metrics include:

* signals observed
* signals researched
* research completion rate
* evidence coverage
* unresolved questions
* source failures
* research cost

Opportunity metrics include:

* qualified opportunities
* rejected opportunities
* rejection reasons
* capability matches
* authorization rate

Economic metrics include:

* introductions
* responses
* accepted opportunities
* completed transactions
* verified revenue
* verified `$0` outcomes
* revenue per opportunity
* operator minutes per real transaction

System metrics include:

* automation percentage
* retries
* failures
* evidence coverage
* unsupported-claim violations
* unauthorized-action attempts
* task latency

---

# 47. KILL / CHANGE RULES

Experiments must be evaluated from evidence.

Allowed decision states:

CONTINUE
CHANGE
NARROW
EXPAND
ARCHIVE

Do not continue an experiment merely because time has already been invested.

Do not manufacture traction to avoid killing an experiment.

---

# 48. INITIAL MARKET EXPANSION

The strategy is:

ONE CATEGORY
→ ONE CITY
→ MULTIPLE CITIES
→ MULTIPLE CATEGORIES
→ MULTIPLE BUSINESS MODELS
→ MULTIPLE MARKETS
→ GLOBAL HAMI NETWORK

The architecture must not hardcode around the first category or customer type.

The initial wedge should be selected using:

* economic value
* legitimate signal availability
* provider identifiability
* response speed
* verifiability
* existing Hami capability
* low operating cost

The category is an experiment, not the ontology.

---

# 49. DATA AS A COMPOUNDING ASSET

Hami's durable value should accumulate through:

* verified evidence
* provenance
* entity resolution
* capability verification
* relation history
* real response history
* action history
* outcome history
* research performance
* source reliability
* economic results

Code can be copied.

A verified history of what worked, what failed, under which conditions, with what evidence, is harder to recreate.

Therefore the data model must protect provenance and historical truth.

---

# 50. TRUST

Trust is an operational capability.

Hami must preserve:

* honest replies
* explicit consent
* opt-out
* bounded follow-up
* owner control
* evidence-backed claims
* clear booking semantics
* clear revenue semantics
* transparent failures

The system must never compensate for poor results by exaggerating them.

---

# 51. SURVIVABILITY

Hami must be inexpensive and portable enough to survive low-revenue periods.

Priorities include:

* low fixed costs
* legitimate free-tier usage where appropriate
* minimal paid dependencies
* portable infrastructure
* backups
* restore capability
* reproducible deployment
* no unnecessary vendor lock-in

A restore drill is a real capability, not documentation theater.

---

# 52. LEGACY CONSOLIDATION

The environment may contain:

* Hami
* ForgeOS
* Sanipops
* experiments
* duplicate frontends
* duplicate backends
* abandoned services
* old deployments
* stale documentation

These must be treated as historical implementation material until classified.

Every significant artifact must be classified:

ACTIVE
AUTHORITATIVE
LEGACY-BUT-VALUABLE
MIGRATION-CANDIDATE
EXPERIMENT
DUPLICATE
ABANDONED
GENERATED
UNKNOWN

---

# 53. CONSOLIDATION METHOD

Do not delete first.

Inspect first.

For each project/folder determine:

* purpose
* stack
* repository
* remote
* relevant history
* entrypoint
* dependencies
* runtime
* tests
* database ownership
* deployment
* consumers
* unique functionality

Then classify.

Recover valuable functionality into Hami.

Archive historical material.

Delete only clearly safe dead weight.

---

# 54. FORGEOS

ForgeOS should be inspected for valuable historical implementation, including:

* Universal Substrate
* research
* evidence
* capabilities
* actions
* opportunity logic
* public API
* frontend work
* security/privacy tests
* migrations
* scheduled tasks
* source collectors
* deployment infrastructure
* documentation

Valuable code should be migrated into Hami where appropriate.

ForgeOS must not remain a second active architecture.

---

# 55. SANIPOPS

Sanipops should be inspected for:

* unique functionality
* useful components
* reusable frontend work
* backend/API work
* data/schema work
* deployment configuration
* integration work
* tests

Useful capabilities may be migrated.

Redundant or obsolete material should be archived or removed after classification.

Sanipops must not remain an overlapping active product by accident.

---

# 56. REPOSITORY STRUCTURE

The final environment should have one comprehensible active center:

HAMI

with clearly identified:

* frontend
* backend
* database
* substrate
* research
* evidence
* opportunities
* capabilities
* actions
* network
* feed
* workers
* scheduled tasks
* tests
* deployment
* documentation

Historical code belongs in a clearly separated archival strategy where appropriate.

Archives must not participate in builds, imports, runtime, or deployments.

---

# 57. DEPLOYMENT AUTHORITY

There must be one clearly identified active deployment path for Hami.

Deployment inspection must determine:

* active Vercel project
* active GitHub repository
* production domain
* preview behavior
* cron jobs
* environment variables
* backend hosting
* database hosting
* deployment ownership

Obsolete ForgeOS/Sanipops deployments should be documented as:

KEEP
MIGRATE
RETIRE
UNKNOWN

Irreversible external deletion requires authorization.

---

# 58. RESEARCH SOURCE STRATEGY

Hami should treat the public world as a distributed information environment.

Potential source classes include:

* government data
* procurement notices
* public web pages
* business websites
* public APIs
* maps/geospatial sources
* public datasets
* job postings
* institutional announcements
* regulatory information
* public feeds
* authorized customer data

No single provider is assumed to contain everything.

Hami should become capable of combining evidence across sources while respecting the restrictions of each source.

---

# 59. SOURCE-AGNOSTIC, NOT SOURCE-ABSTRACTED

The research engine should be source-agnostic at the architectural level but grounded in real integrations.

Do not build dozens of interfaces before one working path exists.

Build the first complete loop from real sources.

Then generalize the abstractions that the working implementations actually require.

Architecture should emerge from validated behavior.

---

# 60. WORLD RESEARCH CAPABILITY

The research engine must eventually be able to reason:

What do I need to know?

Where could that information exist?

Which sources are candidates?

Which source is best under current constraints?

Can I legitimately access it?

What evidence did I obtain?

What does that evidence support?

What remains unknown?

What should I investigate next?

Is additional research worth its cost?

What action can be taken?

What authorization is missing?

What happened?

What did Hami learn?

This is the intelligence layer that turns access to information into economic capability.

---

# 61. SECURITY

No credentials may be fabricated.

No authorization may be assumed.

No secrets may be written into source control.

No private information may be collected merely because it is technically accessible.

No action may be executed merely because it would be beneficial.

Authorization must remain explicit.

External systems must be treated as untrusted boundaries.

---

# 62. PRIVACY

Publicly accessible data still requires responsible handling.

Hami must minimize unnecessary personal information.

Requester information must not leak through unrelated public surfaces.

Booking state must not disclose private requester details.

Public APIs must expose only information appropriate for the public surface.

Historical data must retain provenance without creating unnecessary exposure.

---

# 63. NO FABRICATION

The following are forbidden:

* fabricated customers
* fabricated users
* fabricated providers
* fabricated demand
* fabricated evidence
* fabricated external responses
* fabricated transactions
* fabricated bookings
* fabricated revenue
* fabricated testimonials
* fabricated pilot results
* fabricated research completion

Simulations and tests must be unmistakably identified as such.

---

# 64. TESTING PHILOSOPHY

The system must be verified through execution.

A valid engineering cycle is:

INSPECT
→ IMPLEMENT
→ TEST
→ RUN
→ VERIFY
→ FIX
→ RERUN
→ DOCUMENT RESULT

Plans alone are not completion.

Tests alone are not runtime verification.

A successful build does not prove a feature works in production.

---

# 65. REQUIRED RESEARCH TEST CASES

The research engine must eventually test:

successful source retrieval

failed source

restricted source

source constraint violation

insufficient evidence

contradictory evidence

fallback source

retry

bounded stopping

unauthorized paid call

provenance preservation

truth-state correctness

duplicate/identity handling

task recovery

worker failure

---

# 66. FRONTEND VERIFICATION

At minimum verify:

Home → Network

Network → Home

Home → Research

Research → Home

Home → Opportunities

Opportunities → Home

Home → Actions

Actions → Home

Also verify:

* direct refresh
* browser back
* browser forward
* mobile layout
* tablet layout
* desktop layout
* keyboard navigation
* accessible focus states
* console errors
* backend connectivity
* empty states
* loading states
* error states

Home and Network must remain separate experiences.

---

# 67. PUBLIC PRODUCT

The public surface should gradually expose Hami's legitimate value.

It may eventually include:

* discovery
* network
* opportunities
* services
* businesses
* research-derived information
* authorized interactions

Public exposure must remain governed by evidence, privacy, and authorization rules.

Internal operational data must not leak through public routes.

---

# 68. API DESIGN

APIs must respect the Universal Substrate.

Public APIs should expose projections appropriate for the public user.

Internal APIs may expose more operational detail where authorized.

No API should create a semantic model that contradicts the canonical substrate.

---

# 69. WORKERS AND AUTONOMY

Existing worker/task infrastructure should be reused.

Workers should be able to:

* receive bounded tasks
* retrieve permitted information
* create evidence
* update task state
* generate follow-up tasks
* retry failures
* stop on explicit conditions
* report exact results

Worker autonomy does not mean unrestricted action.

Autonomy must remain bounded by:

* source policy
* authorization
* budget
* safety
* truth requirements
* stopping conditions

---

# 70. ACTION WITHOUT AUTHORIZATION

If Hami reaches an action that requires something unavailable:

* credentials
* payment
* account authorization
* human approval
* third-party permission

Hami must complete all safe preceding work.

Then record:

ACTIONABLE
but
BLOCKED_BY_AUTHORIZATION

Do not pretend the action happened.

---

# 71. LEARNING

Learning is grounded in outcome evidence.

Examples:

A provider did not respond.

A requester declined.

A source repeatedly failed.

A capability was successfully verified.

A demand pattern recurred.

A previously useful source became stale.

A specific research path consistently produced high-quality evidence.

These become evidence and events from which future decisions may improve.

Learning is not an excuse to invent conclusions.

---

# 72. NO “COMPETITOR” ARCHITECTURE

Existing companies, databases, search engines, maps, marketplaces, AI products, and platforms may be studied for:

* factual market context
* user expectations
* interoperability
* infrastructure
* public source availability
* technical patterns
* constraints

Hami must not define itself through competitive ranking or imitation.

The design objective is unique economic value.

---

# 73. COMMERCIAL LEARNING

Customer and market learning must come from actual interactions.

The system should discover:

* what customers already do
* where demand leaks
* what information they cannot easily obtain
* which opportunities have value
* which capabilities are hard to connect
* which workflows can be automated
* what customers will actually pay for

The customer's stated request is not necessarily the complete underlying need.

Hami's research function exists partly to understand the gap between requested and actual need.

---

# 74. DEVELOPMENT DISCIPLINE

Every significant development command should require:

1. repository inspection
2. architecture inspection
3. implementation
4. focused tests
5. broader tests where appropriate
6. runtime verification
7. correction of failures
8. final factual reporting

Copilot should continue autonomously unless a real stopping condition is reached.

---

# 75. REPORTING

All implementation reports must distinguish:

IMPLEMENTED
VERIFIED
UNVERIFIED
BLOCKED
UNKNOWN

Do not use language that turns intention into fact.

Every RESULT card should cite:

* commands
* tests
* runtime output
* relevant logs
* deployment verification

where applicable.

---

# 76. STATUS DOCUMENTATION

The repository should maintain:

`STATUS.md`

and:

`docs/HAMI_SYSTEM_MAP.md`

and:

`docs/LEGACY_INVENTORY.md`

and:

`docs/CAPABILITY_QUEUE.md`

The capability queue is the claim/capability ledger.

These files must reflect actual system state.

---

# 77. HAMI SYSTEM MAP

`docs/HAMI_SYSTEM_MAP.md` must answer:

What is Hami?

Where is the authoritative repository?

What is the frontend?

What is the backend?

What is the database?

Where is the Universal Substrate?

Where is research?

Where is evidence?

Where are opportunities?

Where are capabilities?

Where are actions?

How are Network and Feed implemented?

Where are workers?

Where are deployments?

What is archived?

What remains legacy?

What scripts start Hami?

Which tests validate it?

What must never be rebuilt as a parallel system?

---

# 78. LEGACY INVENTORY

`docs/LEGACY_INVENTORY.md` must classify major historical artifacts.

Each entry should identify:

STATUS

REASON

DESTINATION

DEPENDENCIES

DELETION SAFETY

MIGRATION STATUS

This prevents historical code from silently becoming active architecture.

---

# 79. CAPABILITY QUEUE

`docs/CAPABILITY_QUEUE.md` remains the claim/capability ledger.

Every capability claim should be traceable to:

* evidence
* implementation
* test
* authorization where applicable

An unverified capability is not an active promise.

---

# 80. G0 REPORTING

Before broad implementation, the system may perform a report-only G0 inspection that records:

G0.1 repository/environment inventory

G0.2 active/legacy application inventory

G0.3 architecture/substrate inventory

G0.4 research/collector/source inventory

G0.5 database/runtime/deployment inventory

G0.6 duplicate/parallel architecture detection

G0.7 blockers and migration candidates

G0.8 authoritative Hami system map

G0 reporting is evidence collection, not a replacement for implementation.

---

# 81. CONSOLIDATION EXIT CONDITION

Consolidation is complete only when:

* one active Hami root is identified
* active frontend is known
* active backend is known
* active database authority is known
* legacy systems are classified
* valuable functionality has migration status
* abandoned code is isolated
* deployments are understood
* runtime ownership is understood
* duplicated architectures are identified
* research seed implementation is identified
* source inventory is identified
* no accidental parallel application remains active

---

# 82. RESEARCH ENGINE EXIT CONDITION

The first research implementation is complete only when:

* one end-to-end loop works
* at least two legitimate sources are usable
* retrieval is real
* evidence is persisted
* provenance is persisted
* truth-state transitions are correct
* failures are represented
* constraints are enforced
* fallback works where available
* stopping works
* no fake research results exist

Do not declare completion because abstractions or interfaces exist.

---

# 83. COMMERCIAL EXIT CONDITION

A commercial experiment has produced usable evidence only when actual external behavior has occurred.

Examples:

* actual response
* actual decline
* actual meeting
* actual booking
* actual transaction
* verified `$0`
* verified revenue

A dashboard showing potential value does not count as actual economic outcome.

---

# 84. EXPANSION PRINCIPLE

Expansion should be evidence-driven.

Expand when the system demonstrates:

* repeatability
* economic value
* reliable research
* reliable capability matching
* manageable operating cost
* trustworthy outcomes

Do not expand because an architecture document contains more ideas.

---

# 85. ECONOMIC NORTH STAR

Hami ultimately seeks to increase legitimate economic value creation through:

DISCOVERY
→ UNDERSTANDING
→ CONNECTION
→ ACTION
→ OUTCOME
→ LEARNING

The important system question is not:

> How many features do we have?

It is:

> How much real, verified value can Hami discover and help create with the resources and authorization available to it?

---

# 86. TIME / MONEY / CUSTOMER REALITY

No architecture can guarantee permanence.

Hami must earn durability through:

USAGE
+
ACCUMULATED VERIFIED KNOWLEDGE
+
TRUST
+
SURVIVABILITY
+
LEARNING

The system must be optimized to reach real use before uncontrolled expansion consumes time and money.

A smaller system that is actually used is more valuable than a massive system that is not.

---

# 87. THE FIRST CUSTOMER MATTERS MORE THAN THE NEXT FEATURE

The early system should seek real use.

The first meaningful validation is:

A real organization relies on Hami for a real workflow.

That creates:

* operational evidence
* user feedback
* economic evidence
* failure evidence
* product learning

This is more valuable than building dozens of speculative surfaces.

---

# 88. 29-DAY FOUNDING PERIOD

A founding deployment may use approximately a 29-day operating period where appropriate.

The exact calendar duration is less important than real event volume and evidence.

The period should be used to measure:

* actual demand
* workflow reliability
* operator effort
* customer response
* outcome conversion
* evidence quality
* economic value
* automation potential

At the end of the evaluation, the evidence determines:

CONTINUE
CHANGE
NARROW
EXPAND
ARCHIVE

---

# 89. NO FEATURE ACCUMULATION FOR ITS OWN SAKE

Every new feature must answer at least one of:

Does it improve discovery?

Does it improve research?

Does it improve evidence?

Does it improve capability matching?

Does it improve authorized action?

Does it improve outcome measurement?

Does it improve learning?

Does it improve trust/survivability?

If not, it should not automatically become part of the active system.

---

# 90. PORTABILITY

Nepal is the first operating environment.

Hami's architecture must not make Nepal-specific concepts the ontology.

Country-specific implementation should be represented as:

* source
* geography
* jurisdiction
* entity
* relationship
* evidence
* capability
* action
* policy

The same core can later operate elsewhere.

---

# 91. GLOBAL EXTENSION

The eventual Hami network may support many categories and markets.

The expansion sequence remains:

ONE CATEGORY
→ ONE CITY
→ MULTIPLE CITIES
→ MULTIPLE CATEGORIES
→ MULTIPLE BUSINESS MODELS
→ MULTIPLE MARKETS
→ GLOBAL

The system must expand by adding capabilities and evidence, not by creating separate architectures.

---

# 92. DEVELOPMENT RULE

When a desired capability does not currently exist:

FIRST:

inspect whether an existing capability can be extended.

SECOND:

inspect whether an existing legacy implementation can be migrated.

THIRD:

add the smallest new capability necessary.

FOURTH:

integrate it with the six-primitives substrate.

NEVER:

create a parallel architecture simply because it seems easier locally.

---

# 93. BLOCKER HANDLING

When a blocker occurs:

1. complete all safe work
2. identify exact blocker
3. record evidence
4. identify available fallback
5. continue where possible
6. stop only where human authorization is genuinely required

Examples:

CREDENTIAL_REQUIRED

AUTHORIZATION_REQUIRED

PAID_ACCESS_REQUIRES_APPROVAL

EXTERNAL_DELETION_REQUIRES_APPROVAL

DATA_CONFLICT_REQUIRES_DECISION

SECURITY_BOUNDARY_AMBIGUOUS

A blocker must not become an excuse to stop unrelated safe work.

---

# 94. NO FALSE AUTONOMY

Hami should be increasingly autonomous.

But autonomy means:

the system independently selects and executes legitimate next steps within its authorization and capability boundaries.

It does not mean:

pretending actions occurred,
pretending evidence exists,
pretending humans responded,
or pretending revenue happened.

Truth is more important than the appearance of autonomy.

---

# 95. IMPLEMENTATION PRINCIPLE

The preferred engineering pattern is:

DISCOVER
→ UNDERSTAND
→ IMPLEMENT
→ VERIFY
→ LEARN

The preferred system pattern is:

OBSERVE
→ RESEARCH
→ EVIDENCE
→ DECIDE
→ ACT
→ OBSERVE
→ LEARN

These two loops reinforce one another.

---

# 96. AUTHORITATIVE COMMAND CONTRACT

When a coding agent is instructed to modify Hami, the command should require:

* inspect the current repository
* preserve the six-primitives architecture
* reuse existing implementations
* implement rather than only plan
* test
* run
* verify
* fix
* rerun
* document actual results

The agent must not stop merely because the task is large.

It should stop only at concrete technical, security, authorization, credential, or destructive-action boundaries.

---

# 97. REQUIRED RESULT CARD

Each significant implementation effort must append a RESULT card containing:

## RESULT

Repository/root:

Date:

Objective:

Files/components inspected:

Implementation performed:

Tests executed:

Build/typecheck:

Runtime verification:

Deployment verification:

Data/migration verification:

Research verification:

External action verification:

Actual outcomes:

Revenue:

Customers:

Known blockers:

Remaining unknowns:

The RESULT must never contain invented outcomes.

---

# 98. FINAL SYSTEM MODEL

Hami can be understood as:

WORLD
↓
SIGNALS
↓
DEMAND
↓
RESEARCH
↓
EVIDENCE
↓
KNOWLEDGE
↓
RELATIONSHIPS
↓
CAPABILITIES
↓
OPPORTUNITIES
↓
AUTHORIZED ACTION
↓
EXTERNAL RESPONSE
↓
OUTCOME
↓
LEARNING
↓
BETTER DISCOVERY

The six primitives are the persistent semantic foundation beneath this loop.

---

# 99. FINAL ARCHITECTURAL INVARIANTS

The following are non-negotiable:

1. Exactly six semantic primitives:
   ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION.

2. `type_registry.schema_json` is authoritative.

3. Registry activation is explicit.

4. Truth progresses only:
   possible → hypothesized → tested → supported.

5. Supported claims require evidence/provenance.

6. Identity progresses:
   candidate → corroborated → canonical.

7. No silent fuzzy merges.

8. Feed is a projection.

9. Network is a projection/traversal.

10. `op_` tables are operational state only and never a competing ontology.

11. Meaningful transitions generate EVENTS.

12. No unsupported claims.

13. No unauthorized action.

14. No fabricated humans, customers, transactions, evidence, responses, bookings, or revenue.

15. No destructive semantic deletion where archive/merge preserves truth.

16. Historical implementations must not silently become competing active architectures.

17. Real research must be verified against real sources.

18. Source constraints must be enforced, not merely documented.

19. Research must have explicit stopping conditions.

20. Unknown must remain unknown.

21. Estimated value must remain distinct from actual value.

22. Hami is one system.

23. Hami is the active product identity.

24. Expansion follows evidence rather than feature-count anxiety.

---

# 100. IMMEDIATE IMPLEMENTATION ORDER

The implementation should follow the single coherent progression:

**Understand the existing system.**

**Consolidate Hami / ForgeOS / Sanipops.**

**Identify the real research/collector/worker seed.**

**Make one end-to-end research loop work against real legitimate sources.**

**Verify evidence, provenance, truth transitions, constraints, fallback, and stopping.**

**Fix Home/Network/product navigation and establish the Hami visual identity.**

**Connect research to opportunities and capability matching.**

**Connect qualified opportunities to authorized actions.**

**Connect actions to real response/outcome recording.**

**Run the founding commercial experiment.**

**Learn from actual evidence.**

**Only then expand.**

---

# 101. ULTIMATE OBJECTIVE

Hami does not exist to demonstrate how much software can be built.

Hami exists to become increasingly capable of:

**finding what matters, understanding what is true, connecting needs with capabilities, taking legitimate authorized action, and learning from the world.**

The world is already full of information.

The opportunity is to build the system that can responsibly turn that information into verified economic intelligence and action.

Hami therefore begins small deliberately.

It does not remain small by architecture.

It grows by evidence.

**ONE SYSTEM.
ONE TRUTH MODEL.
ONE RESEARCH LOOP.
ONE ACTION LOOP.
ONE LEARNING LOOP.
REAL WORLD EVIDENCE ABOVE EVERYTHING.**
