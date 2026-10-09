# Hami Build Book — Session Start Protocol

Every AI session begins here. This is an execution protocol, not a second
architecture: `AGENTS.md`, `docs/ARCHITECTURE.md`, and
`docs/CAPABILITY_QUEUE.md` remain authoritative in that order.

## 1. Establish present truth before proposing work

Read, in order:

1. `AGENTS.md`
2. `docs/ARCHITECTURE.md` Sections 1–10 and 16
3. `docs/OPERATING_MODEL.md`
4. `docs/CAPABILITY_QUEUE.md` (current entries only)
5. `docs/PROJECT_STATE.md` and `STATUS.md` as historical leads, not authority
6. The latest 2–3 `logs/daily_cycle_log.jsonl` entries, if the file exists

Then inspect rather than trust prior reports:

```sh
git status --short
git log --oneline --decorate -12
git log --left-right --cherry-pick --oneline origin/main...HEAD
```

When a deployed surface matters, use only read-only checks until an existing
authorization boundary permits more. Never retrieve credentials, submit test
leads, manufacture records, or change flags merely to make a report look
complete.

## 2. Report the decision frame

Before editing, report:

```text
### Hami Session Frame
- Repository truth: <branch, divergence, dirty/clean state>
- Current live Bet or System Obligation: <one existing record, or none>
- Evidence class: <REAL / TEST / MOCK / HYPOTHESIS>
- Routine owner action still required: <one concrete action, or none>
- Dependency this task removes: <one concrete action>
- Boundary that remains: <authorization, access, privacy, legal, or infrastructure>
- Next smallest safe action: <one existing seam>
```

If the task would create a new file, identify the existing seam and prove why
it cannot carry the behavior before creating anything. Record that proof in
the commit or PR description.

## 3. Build order — follow one rung at a time

1. **Repository truth and safety.** Reconcile reachable history in place;
   protect private/raw records; repair failing contracts; make tests runnable
   on the documented runtime. Do not add capability while this rung is red.
2. **Relevance before volume.** A source record may become a pattern only when
   it is tied to an existing Hami unknown, a declared geography/population,
   an allowed evidence type, and a decision it could change. Metadata is a
   lead, never customer demand.
3. **Map the real system.** Extend existing public projections to show source
   → evidence label → unknown → legitimate next test. Keep owner/private work
   behind the existing owner boundary; do not create another dashboard.
4. **Earn external evidence.** Use an authorized, real-world Bet only after
   its action, purpose, scope, consent, exclusions, expiry, and evidence
   limits are recorded. A proposal, signup, test, or policy `ALLOW` is not an
   outcome.
5. **Repeat only what worked.** Improve the existing capability/action/outcome
   seam after a verified paid outcome. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION`
   stays **NOT MEASURABLE** until then.

Sections 16.1–16.6 of `docs/ARCHITECTURE.md` define the current implementation
program and completion tests for these rungs.

## 4. Verification and handoff

For every change:

1. Trace the seam with `git log --follow`, `git blame`, or `git log -S`.
2. Change that seam in place; preserve old records and history.
3. Run the smallest relevant tests, then the broader suite when the runtime is
   healthy. A runtime mismatch is a blocker to record, not a reason to skip
   verification.
4. Update `docs/CAPABILITY_QUEUE.md` with the owner action removed, remaining
   boundary, verification, metric state, and next dependency.
5. State separately: implemented, verified, unverified, blocked, and unknown.

## Human Quick Commands

- `status` → run Sections 1–2 only
- `next` → select one safe task from the current build rung
- `go` / `approved` → execute the selected task within the existing boundaries
