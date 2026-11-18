# Branch protection vs the hourly discovery push — report

Written 18 Nov 2026 (gates step 6). Facts from the repo scan (docs/GATES_INVENTORY.md §11) and the GitHub API; nothing here is guessed.

## The question

Does the hourly discovery push to main conflict with branch protection on main?

## Facts

1. **No hourly discovery push exists in the repo.** Searched scripts/, .github/, backend/app/api/scheduled.py, backend/app/services/cycle_scheduler.py: no hourly job, no `git push`, no schedule that pushes to main. The push is either run outside this repo (an external cron) or it does not exist. There is nothing in the repo to conflict.
2. **Branch protection on main is UNKNOWN.** `GET /repos/kn33r0s3/ForgeOS/branches/main/protection` returned HTTP 401 (needs auth). The repo itself is public (id 1384205274). Do not use credentials to check without owner direction.
3. **CI runs on direct main pushes too.** Comment in .github/workflows/forgeos-ci.yml:125: "Run on direct main pushes too; main is the canonical integration branch."

## Verdict

**No conflict can be established.** There is no hourly push in the repo to conflict with, and branch protection status is unknown. If branch protection is OFF, a direct push to main works and CI runs on it. If it is ON (requiring a pull request), a direct push to main would be rejected by GitHub.

## Least-change fix, without weakening any gate

If branch protection is ON and an hourly discovery push is needed:

- **Do not** disable branch protection, and **do not** add a bypass for the discovery job. Both weaken a gate.
- **Do this instead:** have the discovery job push to a dated branch (e.g. `discovery/2026-11-18-14`) and open a pull request to main. The existing CI (including the new `gate-checks` job) runs on the PR. The PR merges only when CI is green. That keeps every gate in the path and changes nothing about protection.
- If the discovery job must land without a human in the loop, the merge itself is the gate: auto-merge the PR only after CI passes (GitHub's auto-merge), never a direct push.

## What would settle it

- The owner (or a credentialed check) reading the branch protection setting for main.
- Finding where the hourly discovery push actually runs (if it runs at all), and pointing it at a branch + PR instead of main.
