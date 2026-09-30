# ForgeOS Frontend Inspection Report

## Existing architecture

ForgeOS uses **Next.js 15.5.24 with React 18 and TypeScript**, using the App Router. The frontend is located in `frontend/` and is styled with **Tailwind CSS 3.4.9 plus a small global CSS layer**. There is no frontend state-management library; screen state is held in React components and shared fetching behavior is provided by `lib/useForgeQuery.ts`.

The frontend entry point is `app/layout.tsx`, which imports `app/globals.css`, renders the shared `Nav` component, and places each route inside a centered responsive `<main>` shell. The dashboard entry route is `app/page.tsx`.

## Routing and major files

| Area | Files | Role |
|---|---|---|
| App shell | `app/layout.tsx`, `app/globals.css` | Metadata, navigation shell, global theme and utility classes |
| Core dashboard | `app/page.tsx` | Aggregated system state, truth audit, money engine, recommendation, activity, autonomy, commands |
| Product areas | `app/earn/page.tsx`, `opportunities/page.tsx`, `products/page.tsx`, `flow/page.tsx`, `execution/page.tsx`, `revenue/page.tsx`, `world/page.tsx`, `knowledge/page.tsx`, `analyze/page.tsx` | Existing ForgeOS functionality by domain |
| Navigation | `components/Nav.tsx` | Primary and secondary route navigation |
| Shared surfaces | `components/GlassPanel.tsx`, `StatCard.tsx`, `OpportunityCard.tsx`, `StatusPill.tsx`, `ConfidenceBar.tsx`, `ImportanceBadge.tsx` | Reusable cards, statuses, opportunity presentation, confidence indicators |
| Query states | `components/QueryStateView.tsx`, `lib/useForgeQuery.ts` | Loading, offline, error, and empty states |
| Data layer | `lib/api.ts` | Single typed API client mirroring backend schemas and endpoints |

## API/data-fetching mechanism

`lib/api.ts` is the single typed client. The core dashboard uses `Promise.allSettled` to load real backend resources including stats, observer data, money dashboard, recommendations, beliefs, signals, actions, policy, revenue breakdown, blocked actions, and runtime state. It distinguishes offline, partial failure, and successful states using `ForgeApiError`. The shared `useForgeQuery` hook provides the same state-machine pattern to secondary screens. No duplicate API client or fabricated frontend data is needed.

## Existing design system

The current design system is a dark, glassmorphism-inspired Tailwind theme with purple/cyan/emerald accents, Inter for display text, and JetBrains Mono for tabular values. `GlassPanel` provides the main surface treatment; `section-label`, `action`, `field`, glow-border variants, responsive grids, and reduced-motion rules live in `globals.css` and Tailwind config.

## Current dashboard behavior

The current core screen is information-rich and already exposes the important truth-oriented data: live telemetry, Truth & Reality epistemic labels, worker/loop state, verified revenue, recommended next action, activity, autonomy policy, and cycle commands. The main shortcomings are **hierarchy and interpretation**: most content is presented as similarly weighted dashboard panels, the dominant money block can visually compete with more important system state, the Forge loop is not yet a clear visual narrative, and labels such as loading/error/action lifecycle states are too implementation-oriented for a first-time user.

## Existing loading and error states

The initial dashboard uses `QueryStateView` for generic loading/offline states. Secondary screens use the shared hook and view. The generic loading copy currently says “Reading Forge memory…” and error cards expose a raw message directly. These are restyling targets: they can be made more product-readable and actionable without changing API behavior.

## Components that can be restyled rather than replaced

The safest incremental path is to retain the existing routes, API client, hooks, data models, and page-level functionality while restyling `layout.tsx`, `globals.css`, `Nav.tsx`, `GlassPanel.tsx`, `QueryStateView.tsx`, and the composition of `app/page.tsx`. Existing opportunity, confidence, status, and stat components can remain compatible and inherit the improved visual language. No backend, database, business logic, autonomy logic, execution logic, or economic-intelligence code needs to change.

## KneeRose.rocks reference inspection

The repository is public and its GitHub landing page confirms a compact frontend structure centered on `src/` and `public/`. Direct cloning from the sandbox failed because of a TLS handshake error, but the public repository metadata was accessible. The visual direction requested by the brief is translated into ForgeOS as the following implementation patterns: **strong editorial hierarchy instead of uniform admin cards; generous whitespace; compact, calm navigation; rounded surfaces with restrained borders; clear typographic scale; prominent section introductions; responsive stacking; deliberate empty/loading states; and interactive buttons with clear active/hover treatment**. ForgeOS will adapt these patterns to an evidence-oriented intelligence product rather than copying KneeRose functionality or content.

## Implementation boundary

Only frontend presentation and UX copy/state framing will change. Existing API contracts, route structure, database data, historical records, backend services, worker/autonomy behavior, economic calculations, and execution behavior will remain unchanged.
