# Hami capability and access map

This is a repository-grounded guide to existing Hami capabilities and their
entry points. It is an index, not a new domain model, a promise of runtime
availability, or a substitute for the evidence and authorization already
required by ForgeOS.

## What Hami is

Hami is the user-facing, evidence-led system in ForgeOS. It keeps private
personal context separate from public records, surfaces observations and
discoveries without turning hypotheses into facts, and distinguishes a
proposed action from authorization, execution, and an evidence-backed outcome.

## Reading the status

- **IMPLEMENTED** — a code path exists. This alone does not establish that it
  is deployed, available, or used with real-world evidence.
- **PARTIAL** — some implementation or presentation exists, but the full
  capability or user path is incomplete.
- **TESTED** — named tests exercise the stated behavior. Test records are not
  customer or revenue evidence.
- **UNVERIFIED** — current production operation, data, or permission has not
  been established.
- **BLOCKED** — access, owner authorization, configuration, or another
  prerequisite is missing.
- **HYPOTHESIS** — an unvalidated proposition, never a customer, demand, or
  revenue claim.

Keep **REAL**, **TEST**, **MOCK**, and **HYPOTHESIS** evidence distinct. An
empty or unavailable result is not evidence that the underlying capability
works or that the real world has no relevant records.

## Capability inventory

| Capability | Existing implementation and user surface | Access / current boundary | Status and missing seam |
|---|---|---|---|
| Personal context and possible paths | Home derives possible paths from the System state; [`/system`](../src/routes/system.tsx) edits it. [`use-system.ts`](../src/lib/system/use-system.ts) distinguishes guest-tab context from account-backed context. | Context is private to its owner/account; guest state is local to the tab. It is not a public feed record. | **PARTIAL / TESTED** — path suggestions are not verified real-world outcomes. Cross-device persistence requires an account. |
| Public observations and demand signal | [`/discoveries`](../src/routes/discoveries.tsx) reads public observations and findings. [`/request`](../src/routes/request.tsx) records a demand signal through [`demand-intake-form.tsx`](../src/components/pages/demand-intake-form.tsx) and the redacting public-request path. Backend [`observer.py`](../backend/app/api/observer.py) also exposes `POST /observer/observe`, but it is not a public UI form. | Public-source observations may be shown publicly. The request path does not collect contact details, makes no follow-up promise, and is not a general web-research form. | **PARTIAL** — no user-facing general-purpose source collector; available observations depend on actual collection and storage. |
| Research and collection | Backend [`collector_runner.py`](../backend/app/services/collector_runner.py), [`research_planner.py`](../backend/app/services/research_planner.py), [`research_task_engine.py`](../backend/app/services/research_task_engine.py), [`intelligence.py`](../backend/app/api/intelligence.py), [`workers.py`](../backend/app/api/workers.py), and [`scheduled.py`](../backend/app/api/scheduled.py) provide internal pipeline/worker paths. The scheduled cycle and worker code are separate from the read-only discoveries page. | Internal writes are protected by the configured API-key middleware; the browser does not receive or send that key. | **PARTIAL / UNVERIFIED** — no general public research-run UI; production collection cadence and worker uptime are not established by the page. |
| Persisted discoveries and capability acquisition | [`/discoveries`](../src/routes/discoveries.tsx) presents public-source observations and explicitly does not request persisted substrate findings from the public browser. Backend [`substrate.py`](../backend/app/api/substrate.py) and [`capability_discovery.py`](../backend/app/services/capability_discovery.py) hold the related paths. Opening the page does not run discovery. | `/forge/substrate/*` reads require `X-API-Key` when `FORGE_API_KEY` is configured. Browser code has no server key, so protected findings are not requested or made public. | **PARTIAL / BLOCKED** — [`test_capability_discovery.py`](../backend/tests/test_capability_discovery.py) covers discovery behavior; substrate visibility still requires a deliberately authorized server-side path. |
| Evidence, patterns, and beliefs | Backend [`evidence_graph.py`](../backend/app/services/evidence_graph.py), [`pattern_engine.py`](../backend/app/services/pattern_engine.py), [`belief_engine.py`](../backend/app/services/belief_engine.py), and [`public_epistemics.py`](../backend/app/services/public_epistemics.py) feed public projections and internal operating views. [`/feed`](../src/routes/feed.tsx) is a projection, not a complete evidence workbench. | Only public-projection-safe records belong in the public feed. Private substrate and personal context are not interchangeable with public evidence. | **PARTIAL / TESTED** — [`test_public_feed.py`](../backend/tests/test_public_feed.py) and [`test_public_epistemics.py`](../backend/tests/test_public_epistemics.py) cover projections; there is no complete user-facing evidence/pattern/belief workbench. |
| Opportunity hypotheses | [`/opportunities`](../src/routes/opportunities.tsx) filters public feed items classified as opportunities and shows the current human-validation count when available. Backend paths include [`opportunities.py`](../backend/app/api/opportunities.py) and [`opportunity_engine.py`](../backend/app/services/opportunity_engine.py). | A surfaced possibility is not validated demand, an offer, a buyer, or a sale. | **PARTIAL / TESTED** — no public ranking claim; empty, unknown, and unavailable states are intentionally distinct. |
| Decisions and action state | [`/actions`](../src/routes/actions.tsx) shows aggregate pending-action, queued-task, and running-cycle counts from `/forge/runtime`. Backend [`forge.py`](../backend/app/api/forge.py) also exposes detailed execution-action APIs. | Aggregate status is not approval or execution. The separate `/operations` UI is not linked here because it does not establish an owner identity boundary. | **PARTIAL** — approval controls and individual action records must not be treated as public. See the access blocker below. |
| Operations and approval controls | [`/operations`](../src/routes/operations.tsx) reads detailed execution-action and money records and offers explicit cycle/discovery/approval controls. The page accepts an owner API key in a password field, keeps it in component memory, and sends it to the protected backend endpoints. [`ExperimentOut`](../backend/app/schemas/__init__.py) includes action text, required inputs, estimated cost, and policy details. | Backend [`security.py`](../backend/app/security.py) and [`forge.py`](../backend/app/api/forge.py) require `FORGE_API_KEY` for money and execution-action reads; configured state-changing requests also require the key. The UI makes no private request until the owner submits it. | **IMPLEMENTED / LOCAL CODE VERIFIED; PRODUCTION ACCESS UNVERIFIED** — key configuration remains owner-controlled. Supplying a key does not approve an action by itself; cycle, discovery, and approval remain explicit UI actions. Do not expose or persist the key. |
| Experiments, outcomes, and learning | Backend [`experiment_action_service.py`](../backend/app/services/experiment_action_service.py), [`outcome_learning.py`](../backend/app/services/outcome_learning.py), and [`earn.py`](../backend/app/api/earn.py) provide internal state transitions; runtime and money summaries are shown in operating views. Public feed entries may project attributable outcomes. | An experiment, result note, or policy `ALLOW` does not establish a real transaction, completed delivery, or revenue. | **PARTIAL / UNVERIFIED** — no complete public outcome/learning workflow; commercial claims require traceable REAL evidence. |
| Economic and revenue state | Existing money, offer, earn, and outcome paths include [`money_engine.py`](../backend/app/services/money_engine.py), [`payments.py`](../backend/app/api/payments.py), and [`earn.py`](../backend/app/api/earn.py). [`docs/REVENUE_LOG.md`](./REVENUE_LOG.md) is the commercial evidence record. | Only verified REAL payment/outcome evidence counts. Tests, projections, and hypotheses do not. | **PARTIAL** — no verified paid outcome is recorded in the revenue log. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**, not zero. |
| Public work, providers, and booking requests | [`/domain`](../src/routes/domain.tsx), [`/providers`](../src/routes/providers.tsx), and provider/service pages read or write public paths in backend [`public.py`](../backend/app/api/public.py) and [`world.py`](../backend/app/api/world.py). | Public posts are public; users are warned not to put contact details into public post text. Booking requests apply only to an existing public provider/service listing. | **IMPLEMENTED / PARTIAL** — [`test_public_services_substrate_adapter.py`](../backend/tests/test_public_services_substrate_adapter.py) covers the service projection; availability depends on actual public records, and a request is not a booking or completed transaction. |
| Business information and project inquiry | [`/group/businesses`](../src/routes/group.businesses.tsx) shows current recorded offers and strategic directions. Project contact is a mail-client flow and may be unavailable when the general mailbox is unset. | Strategic directions are not operating subsidiaries or offers. Do not infer buyer demand or publish unapproved offers. | **PARTIAL** — current offer information is visible; general project mailbox availability is configuration-dependent. |
| Forge Bot inquiry | [`/forge-bot-intake`](../src/routes/forge-bot-intake.tsx) displays the existing public contact and booking links and an explicit closed state; the business information page links to it contextually. Backend [`forge_bot.py`](../backend/app/api/forge_bot.py) implements the gated record path; [`forge_bot_owner_notification.py`](../backend/app/api/forge_bot_owner_notification.py) implements the internal digest. | Public config contains only contact/booking settings and intake status. Lead summary is owner-key protected; lead writes also require server configuration and the LIVE gate. The page is `noindex`. | **IMPLEMENTED / BLOCKED** — [`test_forge_bot_api.py`](../backend/tests/test_forge_bot_api.py) and [`test_forge_bot_owner_notification.py`](../backend/tests/test_forge_bot_owner_notification.py) cover the existing paths; intake remains disabled, and this navigation change authorizes no REAL lead or outreach. |
| Workers and scheduler | Backend [`worker.py`](../backend/worker.py), [`workers.py`](../backend/app/api/workers.py), [`scheduled.py`](../backend/app/api/scheduled.py), and [`cycle_scheduler.py`](../backend/app/services/cycle_scheduler.py) implement separate worker/scheduled paths. | The worker is a separate process; Vercel Hobby cron is daily. Internal digest delivery requires SMTP configuration; no customer messaging is enabled. | **PARTIAL / UNVERIFIED** — [`test_scheduled_cycle.py`](../backend/tests/test_scheduled_cycle.py) covers scheduled behavior; code presence is not evidence of reliable continuous worker operation or successful email delivery. No Oracle VM was provisioned or tested. |

## Route and navigation map

| Classification | Current paths | What a visitor can expect |
|---|---|---|
| Global primary navigation | `/`, `/discoveries`, `/feed`, `/opportunities`, `/actions` | System overview; persisted/public discovery views; public stream; hypotheses; aggregate action state. |
| Contextual business entry | Home “Existing paths” section; mobile secondary navigation and footer “For businesses” → `/group/businesses` → `/forge-bot-intake` | Business information and the existing Forge Bot inquiry page, with its closed state intact. Forge Bot is not presented as an active public offer. |
| Other public surfaces | `/request`, `/domain`, `/providers`, `/services/*`, `/about` | Public demand signal, work records, verified provider/service projections, static service information, and explanatory content. Each action retains its own consent, public-posting, or availability boundary. |
| Personal/private surface | `/system`, `/login` | Guest context remains in the guest tab; authenticated context is account-scoped. Authentication is not a reason to expose that context to the public world. |
| Internal or direct-route surfaces | `/operations`, substrate APIs, owner summary APIs | Not promoted as ordinary public destinations. `/operations` asks for an owner key before reading private data; production key configuration and successful owner access remain unverified. |
| Test-only | `/bot-qualification-demo` | Synthetic, browser-local qualification demonstration; it is unavailable in production and never creates REAL lead or revenue evidence. |
| Informational and compatibility | `/contact` is currently unconfigured for a monitored mailbox; `/request-a-project` redirects to `/request`; `/requests/:id` reports an existing provider booking-request status; `/process`, `/technology`, and `/ventures` are explanatory/strategic pages. `/work` redirects to `/domain`. | These are static, redirect, or scoped workflow surfaces—not additional active Hami systems or evidence of an operating business. |
| Legacy source | Archived [`frontend/`](../frontend/) source is not the active root React/TanStack app. | This is not a separate current Hami product or deployment. |

The current primary navigation remains intentionally small. New entry points
connect existing pages rather than creating routes or changing the data model.
Footer wording says “Share a need,” not “privately”: the request is a public
demand signal without submitted contact details, not a private owner-context
record.

## Verification sources

- [`content.test.ts`](../src/lib/content.test.ts) checks the public navigation,
  route contracts, stated privacy boundaries, absence of fabricated public
  claims, and the contextual business-to-inquiry link.
- Backend public contract and projection coverage is in
  [`test_public_contract.py`](../backend/tests/test_public_contract.py),
  [`test_public_feed.py`](../backend/tests/test_public_feed.py), and
  [`test_public_network.py`](../backend/tests/test_public_network.py).
- Forge Bot tests exercise TEST/REAL gating and private owner-summary behavior;
  they are not real inquiries and do not count as commercial evidence.
- Browser checks of the changed navigation confirm rendered links and the
  closed intake state; they do not verify production persistence, worker
  uptime, email delivery, or an economic outcome.

## Orphaned or incomplete capability classes

- **Connected:** System context, public feed, discoveries, opportunities,
  aggregate action state, provider/work records, and business information have
  recognizable entry points.
- **Partial:** Public discoveries do not start research; opportunities are a
  filtered projection; action state is aggregate-only; service pages can be
  static; none imply a completed economic outcome.
- **Backend-only / internal:** source collection, research runs, detailed
  evidence/pattern/belief processing, worker controls, and several economic
  transitions have no general public UI. Internal operations reads are not
  currently owner-authenticated.
- **TEST-only:** synthetic Forge Bot submissions are not real leads. A test
  pass never counts as customer evidence.
- **Blocked:** Forge Bot REAL intake, customer messaging, booking automation,
  protected substrate display in the browser, and detailed operations
  discoverability remain gated by permissions/configuration or missing
  authorization.
- **Legacy:** archived frontend source and redirect-only compatibility routes
  are not live alternatives to the current app.
- **Not established:** real customer demand, repeat usage, paid outcome, owner
  interventions per real transaction, reliable production worker cadence, or
  successful digest delivery.

## Next owner dependency

The navigation change removes the need to manually share the business and
closed inquiry URLs. It does not remove owner-run discovery, decide a market or
price, authorize contact, open intake, or create a transaction. The next
economic evidence still requires owner-run conversations and an attributable
real paid outcome. Before the detailed operations view can be treated as
owner-only, its read path needs an explicit owner authorization boundary. No
real transaction is verified; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION`
remains **NOT MEASURABLE**.
