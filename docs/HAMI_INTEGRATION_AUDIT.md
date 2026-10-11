# Hami / ForgeOS integration audit

**Audit date:** 2026-10-11  
**Repository:** `kn33r0s3/ForgeOS`  
**Lineage:** direct commits to `main`; no branch or force-push workflow.

This is a living, repository-grounded audit, not a claim that every capability is deployed or operational. It separates code connections, tests, production configuration, and real-world outcomes.

## Inventory and method

A recursive Git tree read found **919 tracked tree entries**, including **38 frontend route files**, **25 backend API modules**, **113 backend service modules**, and **146 files under `docs/`**. These are file counts, not proof every route or service is active. The pass traced the canonical navigation map, route lifecycle registry, sitemap, orphan-route scanner, route components/loaders, FastAPI router registrations, authorization middleware, owner/operations consoles, payment adapters, Better Auth and preview-specific identity/connectors, relevant tests/CI, and the commercial evidence log.

Canonical constraints remain in force:
- One product and one data substrate: reuse `ENTITY`, `RELATION`, `EVENT`, `EVIDENCE`, `CAPABILITY`, and `ACTION` through `type_registry.schema_json`.
- Reuse → extend → connect → recover before adding. A route, endpoint, test, or status tile is not proof that a user journey reaches a canonical record and verified outcome.
- A proposed action is not authorization; authorization is not execution; execution is not an evidence-backed outcome.
- Keep `REAL`, `TEST`, `MOCK`, and `HYPOTHESIS` separate. These fixes create no customer, payment, booking, or revenue evidence.
- Preserve owner approval, action envelopes, daily caps, source clearance, provenance, and production gates.

## Changes made during this pass

- `cf70b412` — repaired stale navigation typing and made the branding check independent of the removed Grok PWA helper.
- `1b609f55` — aligned navigation and experiment-state tests with the canonical Hami map.
- `27cb0a94` — made eSewa browser-return verification read-only, signature-checked and cross-checked against provider transaction status/amount/merchant; no order, fulfilment or revenue is written.
- `85942607` — aligned the footer contract test with its actual scope and canonical path source.
- `fbb5e1e0` — corrected invalid offer links to the registered `/services/$slug` route with a typed slug.
- `622b79a0` — stopped inferring Grok workspace preview solely from a missing project ID when Vercel/production markers exist.
- `77193680` — made deployed protected mutations/private substrate/contact reads fail closed when the owner key is not configured; explicit public write exceptions remain.
- `996fa6c5` — corrected outdated owner-console and public-navigation contracts without adding private pages to public navigation.
- `e30e2c36` — excluded submitted private-request records from deployed public signal projections when no authorized owner key is presented/configured.
- `86515524` — added a live-route entry-path contract and recorded group/service integration.
- `03a01597` — removed a direct public Businesses-page link to the hidden, closed intake route; the page now routes to live service/process/work surfaces.

Always inspect CI against the exact latest `main` SHA after a commit. A commit existing is not a test result; build success or a deployment badge alone is not proof every active job or runtime path is green.

## Connections confirmed

1. **Public navigation and lifecycle:** `src/lib/hami-system.ts` is the canonical nav/footer/pathway source; `features.json` and `public/features.schema.json` carry lifecycle states; sitemap/feature tests validate the public route surface. The live-page entry contract is bidirectional at the page level, including an explicit workflow-only exception for request-status routes.
2. **Hami service catalogue vs external providers:** Hami offers remain backed by `src/lib/content.ts` and link through real dynamic service details. External providers remain a separate directory/verification workflow. The Businesses page no longer advertises a closed intake route.
3. **Owner/operations console boundary:** both consoles connect contextually but remain outside public navigation. They are noindex pages, not secret URLs. Traced money/execution-action reads check an owner key; the page-level noindex metadata is not authorization. Production key presence and full deployed owner access are not established.
4. **Deployed write boundary:** the global API middleware now distinguishes local development from deployed runtime when deciding whether privileged non-allowlisted writes/private reads require a key. The separate signal helper also excludes private user-request rows if deployment lacks an authorized key.
5. **Payment return boundary:** a payment provider's browser redirect cannot present Hami's private key. eSewa return handling is therefore public and read-only, but only returns verified status after signed-field and provider-status checks. It does not persist an order or fulfill anything.
6. **Grok PWA identity:** the production manifest names Hami, and the PWA injector/install shell were removed and guarded by branding tests. A repository text search found no exact source phrase “Open with Grok app”. This is source-level evidence, not proof that a CDN/cache or each deployed client has refreshed.

## Prioritized remaining work

### P0 — prove the production authorization boundary

- Verify deployed SHA and configuration presence for `FORGE_API_KEY` through the authorized owner-readiness path. Do not retrieve or expose the key. The capability ledger records that current Vercel connector scope returned 403, and production owner access remains unverified.
- Continue endpoint-by-endpoint authorization review. Middleware is a backstop, not a substitute for handler-level tests. Preserve an explicit allowlist for public writes and prove private projections do not leak records when auth is absent.
- Check all jobs on the exact current SHA. Recent CI has exposed stale assertions/type errors despite successful builds and smoke checks; do not call the full system green based on a partial job set.
- Owner-side credential hygiene is still a dependency: `docs/CAPABILITY_QUEUE.md` records a Twilio credential rotation requirement. No credential was read or rotated here; rotate with the provider and replace the value using authorized access.

### P1 — close the economic transaction loop

- eSewa callback verification now checks provider status, but it is not an order/payment ledger. Khalti initiation/lookup does not itself complete a purchase journey.
- Connect existing product/offer → durable order identity → provider initiation → signed callback/server lookup → idempotent final status → authorized fulfillment → evidence-backed outcome. Reconcile amount/currency/merchant/transaction ID, duplicates and replay.
- Only after delivery and payment are verifiably real should commercial evidence be recorded. `docs/REVENUE_LOG.md` has no commercial entries; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### P1 — make private intelligence safely inspectable

- Collection, research tasks, substrate discoveries, evidence/pattern/belief engines and action/outcome state exist, but public pages are projections rather than a complete owner research workbench.
- Connect existing IDs and provenance through a server-side, owner-authorized read model with purpose-limited DTOs. Never ship `FORGE_API_KEY` to browser code or create a parallel state store/schema.
- Keep a successful empty source retrieval distinct from unavailable/failed access; ranking/selection is not authorization to research or act.

### P1 — verify Better Auth deployment configuration

- `.env.example` now documents names already consumed by code: `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET`; no values are included.
- `src/lib/auth/server.ts` falls back to a process-local random signing secret when no stable secret is configured. With multiple deployment instances, session signing consistency and trusted/canonical origins must be verified before claiming stable account/session behavior.
- Do not turn on real signup, change providers, or invalidate sessions merely to complete this audit. Verify environment presence via authorized deployment metadata or an owner-controlled test.

### P1 — establish scheduler and worker evidence

- Scheduled endpoints, worker processes, collection runners and owner digest code are distinct execution paths. Source presence and `/api/health` do not prove successful cadence, source access, queue drainage or SMTP delivery.
- Add observability to the existing owner read model: actual run IDs, timestamps, duration, last result, source-access status, retry counts and safe error summaries. Preserve CRON authentication/idempotency and keep customer messaging disabled absent separate authorization.

### P2 — connect code across layers automatically

- Extend static checks beyond URL links to map route → UI data loader → API endpoint → handler auth → service → canonical record/event → evidence/outcome → tests.
- Report dynamic/unresolved links as candidates for review; a text match is not proof of runtime wiring.
- Keep preview-only Gate identity, popup OAuth, connector host detection and `GROK_*` variables separate from Hami's deployed auth/data. Removing the entire bridge without an identity/session migration may break workspace preview; it is distinct from the removed PWA install shell.
- Preserve archived routes and historical `.grok/` tooling until each dependency has been classified. Do not mass-delete based on directory name.

## Verification boundary

This review uses source, diffs, tests and CI metadata available through the GitHub connection. It does not independently establish live production SHA, credentials, database contents, worker cadence, SMTP delivery, user behavior, or a commercial outcome. No production write, owner-key retrieval, customer contact, intake opening, purchase, payment or fulfillment was performed.
