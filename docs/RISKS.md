# Standing risks

**Updated:** 2026-10-04. Review whenever the project's shape changes.

- **R1 — Deploy key on the driver VM.** A write-scoped deploy key for this
  repo lives on musa's VM (added 2026-10-04). Scope: this repo only. If the
  VM were compromised, an attacker could push to main and Vercel would
  auto-deploy it. Mitigation: revoke anytime at repo Settings → Deploy keys;
  rotate periodically. The owner knows where it is.
- **R2 — Vercel Hobby commercial use.** Hobby bans commercial use and
  enforcement is suspend-first. Currently compliant ($0 revenue, intake
  closed, no ads). Before the first paid pilot: move to Pro or migrate the
  frontend. No spend without owner approval.
- **R3 — No production monitoring.** A broken deploy would go unnoticed — the
  owner has opted out of watching. Proposed: failure-only health watchdog
  (driver checks on a schedule; owner hears only on failure). Awaiting owner
  approval.
- **R4 — Multiple writers, one branch.** Commits land from Copilot batches
  (owner's Mac), the driver (deploy key), and the owner. Rule: one writer at
  a time; pull before starting local work. The suspected second window was
  investigated 2026-10-04: no concurrent window found — the commits in
  question were Copilot batch work and the driver's own pushes.
- **R5 — Verification labels.** Locally-run tests are not CI. A pattern grep
  is not a history audit. An inference is not an observation. Claims keep
  their labels permanently; caveats must survive retelling.
