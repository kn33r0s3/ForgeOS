# ForgeOS Overnight Backlog

## P0 runtime blockers
- [DONE] Confirm repo/branch ownership: `kn33r0s3/ForgeOS` on `main`
- [DONE] Confirm the frontend source for Earn is the correct ForgeOS code in [frontend/app/earn/page.tsx](../frontend/app/earn/page.tsx)
- [BLOCKED] Live production deployment is still wrong: stale Sanip Ops site is serving on `https://forge-os-ebon.vercel.app`
- [BLOCKED] Actual Vercel production project must be rebound or reissued to serve the ForgeOS app rather than the stale Sanip Ops alias

## P1 intelligence-loop blockers
- [DONE] Investigate evidence model and collector direction; the collector architecture remains valid
- [IN PROGRESS] Validate research provenance and blocked-source handling without weakening fail-closed behavior
- [PENDING] Audit opportunity generation for false positives and unsupported revenue claims

## P1 deployment problems
- [DONE] Verify GitHub repo is canonical and pushed to `origin/main`
- [BLOCKED] Resolve Vercel domain/project mismatch that still outputs Sanip Ops HTML
- [PENDING] Confirm production route `/earn` renders ForgeOS content after fixing deployment binding

## P1 frontend/backend integration
- [DONE] Confirm the frontend build succeeds in [frontend/package.json](../frontend/package.json)
- [PENDING] Ensure production frontend points to a legitimate reachable backend, not local-only addresses
- [PENDING] Harden backend deployment architecture when backend hosting is needed

## P2 reliability
- [PENDING] Validate browser-runtime behavior on real local route `/earn`
- [PENDING] Add tests covering blocked collector states and falsified opportunity generation

## P2 tests
- [DONE] Confirm local Next.js production build passes
- [PENDING] Run focused front-end runtime smoke tests after the Vercel alias issue is corrected

## P3 UX / docs
- [DONE] Maintain honest engineering docs
- [PENDING] Capture exact deployment truth and remaining blockers in operational docs
