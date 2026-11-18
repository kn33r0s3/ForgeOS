# 006 — Explain the pending-changes count (was 27, now 47)

- **Finding:** VS Code Source Control showed 27 pending changes, then dropped to 21 around 01:45 on 18 Nov, with no commit recorded in between. The cause of that drop is unexplained. Since then the count has grown to 47 (18:00, 18 Nov) — mostly new files from the gates work (ledger, gates tests, gates scripts, CI, WHO-DID-WHAT) plus Copilot's queue/007 edits.
- **Owner:** Copilot
- **Input:** git status + git reflog + the VS Code git log for 18 Nov 01:30-02:00 (for the 27→21 drop) + git status now (for the growth to 47)
- **Output:** an explanation recorded in docs/CAPABILITY_QUEUE.md (what changed, which files, what caused it — separately for the 27→21 drop and the growth to 47)
- **Verify:** the explanation names specific files and the git evidence (reflog entries or stash/drop records) that supports it
- **If blocked:** if the cause cannot be established from the logs, record it as UNKNOWN with the evidence checked, and move on; do not invent a cause
