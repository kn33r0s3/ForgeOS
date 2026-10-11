# PROJECT STATE — Hami

> Current operating snapshot: 2026-10-11 (Nepal time). Branch `main`; read `git rev-parse HEAD` for the exact current commit.
> Do not infer current backend or commercial readiness from a successful frontend deployment.

## Product and integration state

- **One product:** Hami is the user-facing system. ForgeOS remains the repository/technical lineage; no replacement architecture or parallel app is being created.
- **Production frontend:** [haminp.vercel.app](https://haminp.vercel.app). Vercel reports the Hami production alias READY and assigned to the latest successful `main` deployment. This verifies deployment state and alias assignment, not runtime/API or database readiness.
- **Canonical route registry:** `features.json` has 36 entries: 25 live, 7 hidden, 4 archived, and 0 planned. Duplicate IDs/routes are not present in the current registry. Historical creation date/commit are preserved for existing route rows.
- **One navigation/pathway source:** `src/lib/hami-system.ts` defines `NAV`, `FOOTER_GROUPS`, `SYSTEM_PATHWAYS` and `PUBLIC_SYSTEM_PATHS`. Header, footer, contextual pathways and sitemap are checked by frontend regression tests.
- **Connected public paths:** findings, network records, unknowns, experiments, opportunity hypotheses, action state, Hami services, provider directory, public work board, group context, process, technology and ventures. Group offer cards link to canonical service details or Hami's shared process instead of creating duplicate service pages.
- **Indexable sitemap:** 23 unique public URLs, all registered as live. Closed Contact and Request pages, owner/private tools, TEST-only demos, redirects, and Terms/Privacy pages marked `noindex` are omitted.
- **Surface lifecycle is intentional:** hidden pages are retained where auth, testing or owner readiness requires it; archived URLs remain redirects for compatibility. No page should be marked live merely because it responds.

## Public route groups

**Core understanding loop:** `/` → `/discoveries` → `/feed` → `/unknowns` → `/experiments` → `/opportunities` → `/actions`.

**Work and value:** `/services` → canonical `/services/$slug` detail; separate `/providers` for verified external providers; `/domain` for public work; `/needs` for the proposed field test, not a live intake channel; `/requests/$id` for an actual provider request record, where pending is not acceptance.

**Group and direction:** `/group`, `/group/businesses`, `/process`, `/technology`, `/ventures` are linked into the same service/work/evidence model. Technology and Ventures are strategic directions, not claims of operating subsidiaries.

**Personal context:** `/system` is explicitly private context. It must not be merged into public network/discovery data without explicit authorization.

## Operational and commercial boundaries

- `docs/REVENUE_LOG.md` has no recorded commercial evidence at this snapshot. There is no verified customer/payment/revenue entry in that ledger. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.
- Contact and anonymous request intake remain closed; no owner-provided `SITE.email` is configured. The public offer cards route to relevant service detail pages, while the shared top-level CTA remains truthful about intake being closed.
- Forge Bot intake/demo, the prototype inbox, and owner controls remain hidden/noindex. Hidden is not deleted or claimed to be live.
- `/owner` is the key-protected noindex cockpit for inquiry evidence, ForgeBot, intelligence/research, products/payments visibility, operating model and buyer-side records. `/operations` is a separate key-protected noindex surface for economic state/action records and explicitly initiated operations. A page or panel does not authorize external execution.
- No automatic outreach, consequential action or payment collection is enabled by these UI integrations. Preserve owner approval, action envelopes, daily caps, source clearance, privacy minimization, provenance and evidence labels.
- **Backend readiness remains a separate verification task.** Historical status reports flag production database durability/readiness, scheduled-job credentials and remaining route-contract/security review as unverified or blocked. Do not call these solved based on a frontend deployment. Check `STATUS.md` and `docs/CAPABILITY_QUEUE.md` for dated evidence.
- The first seller and first real outcome remain owner-gated. No seller contact, booking, payment or revenue result is implied by this integration pass.

## Current build/integration rule

Reuse → extend → connect → recover. Before adding a route/service/engine, inspect its existing record, route, component, API, loader, authorization, history and tests. A new public surface must have one registry row, correct state/provenance, a canonical navigation/pathway and regression coverage. Never fabricate users, evidence, bookings, payments, external actions or revenue.

## Reference documents

- [Hami system map](HAMI_SYSTEM_MAP.md)
- [Feature registry](../features.json)
- [Capability queue and remaining technical gaps](CAPABILITY_QUEUE.md)
- [Revenue evidence log](REVENUE_LOG.md)
- [Operator guide](OPERATOR_GUIDE.md)

## Last 10 decisions

1. 2026-10-05 — Doctrine v1.0 frozen; single file docs/ORIGIN.md (owner).
2. 2026-10-05 — Experiment cards carry five fields; constraint = hypothesis until evidenced (owner).
3. 2026-10-05 — Owner console gate: one active human-involving intervention max (owner).
4. 2026-10-05 — Nav gets quick-action Home; Join Hami gets btn-wipe animation (owner).
5. 2026-10-05 — Branch + PR for doctrine/project-memory work; owner approves merge (owner).
6. 2026-10-05 — User's name is Niroj (owner).
7. 2026-10-04 — Direct-to-main restored after one PR experiment (owner).
8. 2026-10-04 — Intake STAYS CLOSED; readiness checklist has owner-side FAILs (musa, delegated).
9. 2026-10-04 — Whop is not the revenue path; haminp.vercel.app is the live surface (owner).
10. 2026-10-04 — Canonical domain haminp.vercel.app (musa, delegated).

Full log: `DECISIONS.md`.

## Open owner decisions / gates

- [ ] Name the first seller and separately authorize first contact; this gates Experiment 1.
- [ ] Decide whether/when to open online intake only after readiness, consent, safety, legal and response-path checks pass.
- [ ] Verify business registration/PAN and an authorized merchant/provider path before enabling payments.
- [ ] Independently verify production database durability/readiness and scheduled-job credentials/heartbeat before claiming production intelligence readiness.
- [ ] Complete the remaining individual route-contract/security review in `docs/CAPABILITY_QUEUE.md`.

