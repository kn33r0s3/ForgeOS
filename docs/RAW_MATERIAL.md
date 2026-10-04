# Raw Material

**Date:** 2026-10-05
**Principle:** Nothing is waste. Every dry well, blocked path, reverted change,
dormant component, and contradiction is raw material. Trash is where reality
left a mark.

This document inventories what the project has discarded, blocked, or failed
at — and extracts what each item teaches. Update it whenever something is
reverted, blocked, or hits a dry well.

---

## 1. Dry wells → findings

Dry wells were logged as failures. They are findings.

| Dry well | What it actually revealed |
|----------|---------------------------|
| X public search → zero genuine owner voices | Nepali owners don't talk on English-language forums. The listening surface is not Reddit/HN — it's TikTok comments, FB groups, Viber. This maps where listening is *impossible*, which is as valuable as where it works. |
| r/Nepal, r/Kathmandu, r/Nepali → no substantive struggle threads | The English-speaking Nepali internet is not where business struggle is discussed. The real discourse is in Nepali, on platforms opaque to search. |
| Nepali FB/Viber groups opaque to search | The conversational layer is walled. Broadcast is visible (bios, stats), conversation is not. Any listening strategy must account for this wall. |

**Material value:** These three dry wells together define the *listening boundary*.
Hami cannot listen where it cannot see. The next listening attempt must be in
Nepali, on TikTok/FB, by a human — or it will hit the same wall.

---

## 2. Blocked items → boundary map

Blocked unknowns are not dead. They trace exactly where Hami's access ends.
That boundary *is* the shape of the next move.

| Blocked | What the boundary teaches |
|---------|---------------------------|
| A1: Does production owner email deliver? | The owner-notice path is unverified. Every alert Hami sends might be theater. The boundary is *owner action* — only the owner can confirm receipt. |
| A2: What env vars exist in production? | Hami cannot see its own production config. The boundary is *credential procedure* — no authorized path exists to look. |
| A8: Current heartbeat/readiness state? | The readiness checklist has a hole. The boundary is the same: owner-key access. |
| D8: Returnee-skill pathway | May resolve with 3+3 human interviews. The boundary is *human conversations*, not data. |
| D9: Voiceless-founder population | Likely permanently blocked for direct contact. The boundary teaches: measure via proxy ("who do you know who wanted to start but didn't?"). |

**Material value:** Three of five blocked items share one boundary: *owner action*.
This is not five separate problems — it's one. The owner unlocking credential
access unblocks A1, A2, A8 together.

---

## 3. Reverted work → patterns

| Reverted | Pattern extracted |
|----------|-------------------|
| SystemFlow homepage sections (invented, then removed 2026-10-04) | The repo already had the answer. The instinct to invent rather than reuse is the failure mode. **Pattern:** search the repo first, build second. |
| text-paper/text-ink bug (shipped invisible text) | Design tokens have misleading names. `text-paper` sounds like "paper color" (light) but is the dark background. **Pattern:** verify visual output, never trust token names. |
| Orphaned routes (6+ routes indexed but unlinked) | Routes were added without connection. **Pattern:** the CI orphan check now prevents this — the failure became infrastructure. |

**Material value:** Each revert became a guard. The bug became a visual-check habit.
The orphans became a CI script. Failures that produce guards are the highest-value
material.

---

## 4. Dormant components → future material

| Dormant | Why it waits | What it's worth |
|---------|--------------|-----------------|
| `src/components/pages/project-form.tsx` | Intake is closed by owner order | A complete intake form, tested, ready. When the owner opens intake, this is day-one material — not a new build. |
| `/prototype/inbox` | TEST-only, no real seller | The week-log and reply-timer UI exists. When Experiment 1 starts, the measurement tool is already built. |
| `src/lib/unknowns-api.ts` | Replaced by markdown-parsed API | The engine-substrate approach. If Hami ever moves unknowns into the DB, this is the reference implementation — not trash, a prototype. |
| Inbox prototype footer link (TEST-only) | No seller yet | Keeps the tool visible but honest. The label "TEST-only" is itself material — it models how to show unfinished work without lying. |

**Material value:** Dormant ≠ dead. Each item has a named unblock condition. When
the condition arrives, the work is already done.

---

## 5. Zero contradictions → signal

93 unknowns. **0 contradicted.**

This is not a clean record. It's a smell. It means reality hasn't pushed back
yet — we're not testing hard enough, or we're not recording the pushes.

**Material value:** The empty category is the most informative one. The next
discovery round should *seek* contradiction, not just bank questions. A
contradicted unknown is worth ten confirmed ones because it revises the map.

---

## Rules

1. Before discarding anything, extract what it teaches. Write it here.
2. A dry well is a finding about where *not* to look. Record the boundary.
3. A blocked item is a map of the access edge. Record what unblocks it.
4. A revert is a pattern. Record the guard it should become.
5. Dormant code gets a named unblock condition, not a delete.
6. Seek contradiction. The empty CONTRADICTED column is a failing grade.
