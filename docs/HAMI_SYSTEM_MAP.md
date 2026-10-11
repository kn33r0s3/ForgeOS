# Hami system map

This file records how existing routes and engines form one Hami system. It is a map of implemented surfaces and their boundaries, not a promise that every subsystem is already operational.

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

`/services` contains Hami's own technical/operational offers and links to `/services/$slug`. `/providers` is a separate directory for external providers that meet verification/publication requirements. `/domain` is the public work board. `/needs` remains a truthful record of the proposed missed-inquiry experiment; it is not a live intake channel. `/requests/$id` shows an actual provider request record and never treats pending as acceptance.

The paths share a navigation and evidence model, but their underlying record types and permissions remain distinct. Do not collapse Hami's own services into the external provider registry or infer a completed transaction from a post, match, or request.

## Surface lifecycle

- **Live** — an existing route or endpoint has a real defined purpose and is reachable through an appropriate Hami path.
- **Hidden** — retained, but not advertised as a normal public destination: owner controls, test/demo routes, closed intake, or contact while no owner-provided email exists.
- **Archived** — compatibility routes kept for old links and redirected to the canonical surface: `/climb`, `/what-we-learned`, `/work`, and `/request-a-project`.
- **Planned** — a future capability that has no implemented route/endpoint yet.

Hidden does not mean delete. Archived does not mean create another page. A page must not be marked live simply because a route responds.

## Operator and authorization boundary

`/owner` is the key-protected noindex cockpit for readiness, inquiry evidence, ForgeBot, intelligence/research, products and payments visibility, operating model, scouting, and buyer-side journey records. `/operations` is a separate key-protected noindex surface for economic state, action records and explicitly initiated operations. The owner console links to Operations after the owner has unlocked it, and Operations links back; neither belongs in public navigation. Their existence does not make action execution, outreach, intake, payment collection, or revenue live.

Before changing those boundaries, trace the existing endpoints and key/authentication behavior. Preserve owner approval, action envelopes, daily caps, source clearance, provenance, and evidence labels. Do not make the app automatically execute merely to make a control appear active.

## Required integration rule for future work

Before adding a service/page/engine:

1. Find the existing route, API, component, registry row and data loader before creating a replacement.
2. Extend or connect the canonical implementation rather than start a parallel one.
3. Give every route a registry state, intent, and provenance; public paths must resolve to live entries.
4. If it is a public journey, wire it through the shared navigation or contextual pathway and, where applicable, the sitemap.
5. Add regression coverage for the route, data source, state/permission boundary, and any relationship claimed by the UI.
6. Report implemented, hidden, unavailable, TEST, and planned states exactly. Never fabricate evidence, users, bookings, payment, actions, or revenue.
