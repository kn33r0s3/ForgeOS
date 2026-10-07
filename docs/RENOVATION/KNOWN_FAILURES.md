# Known failures (baseline 2026-10-08, origin/main @ 7008111)

Rule: from now on no NEW failures are allowed.

## Baseline results

- Backend pytest: 883 passed, 2 skipped — **none failed**.
- `npm run typecheck`: PASS, 0 errors.
- `npm run build`: PASS.
- `npm run lint`: 0 errors, 1 pre-existing warning
  (`react-refresh/only-export-components` in
  `src/components/experiments/experiment-card.tsx`).

## Known failures

none
