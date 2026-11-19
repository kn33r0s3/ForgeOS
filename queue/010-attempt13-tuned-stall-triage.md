# Next order — after 009: attempt 13 TUNED re-run stalls identically (GC fix ruled out)

## Follow-up — 2026-11-19 17:27 +0545: v3 stats path delayed; v4 bounded retry running

v3 trace-off send stayed active through 120,005ms (14,947 frames, no stale);
it briefly had 55 stale publishers at 109,222ms and recovered by 110,003ms.
Feedback failed at 380/3,000. The 2-second stats request was accepted at
17:25:34.267, but its viewer-map snapshot took 532ms and ended with canceled
context before querying feedback counters.

The existing local stats timeout is now 5 seconds with client start/elapsed
logs. v4 uses the same local-only 3,000/3,000 trace-off run. Await its
feedback snapshot and phase timing before selecting another intervention.
The exact cause of missing PLI/FIR remains unknown; M7-H is not accepted.

## Follow-up — 2026-11-19 17:18 +0545: v2 partial stall; stats timing instrumented

The v2 trace-off 3,000/3,000 run sent 14,992 frames with no stale publishers
at 108,005ms, then 5,717 frames/1,562 stale at 109,005ms. At 110,004ms it
sent 7,638/1,372 stale; 813 publishers stayed stale through 120,007ms, with
the oldest last send 11.815s old. The zero-frame/all-stale reading at
121,012ms was post-deadline.

Feedback failed after 5m at 396/3,000 (`nackZero=1565`, `pliZero=2604`,
`firZero=2604`, `maxN=99`, `maxP=1`, `maxF=1`). Injection ran all 3,000
calls without errors or skips, but the sampled SFU viewer received/
forwarded NACK 283/246 and no PLI/FIR. Pion's NACK responder does not consume
PLI/FIR, so the drop boundary is still unknown.

The 2s `/stats` request expired; per-viewer counters appeared near SFU
shutdown. The existing handler now checks cancellation early, releases the
viewer-map lock before router snapshots, and logs per-phase timings. Go tests,
vet, npm test (295), and gates passed. The updated v3 local 3,000-peer run is
in progress; inspect its phase log before selecting the next intervention.
M7-H is not accepted. The v3 send phase briefly had 55 stale publishers at
109,222ms but recovered by 110,003ms and was still sending at 120,005ms;
all-stale at 121,003ms was post-deadline. Feedback timeout and stats timing
remain pending.

## Follow-up — 2026-11-19 17:05 +0545: repeat trace-off run narrows feedback loss

A second 120-second trace-off 3,000/3,000 run again sent through the media
deadline; zero frames/all stale appeared at 121,007ms. Feedback failed at
355/3,000. The SFU later logged NACK received/forwarded on five sampled
incomplete subscriptions but no PLI/FIR, with no RTP queue drops, write
errors, or router errors. The response to the first timeout stats request
missed its 2-second deadline; candidate-pair details were not captured.

The feedback-timeout path now logs injection attribution, selects one
incomplete viewer, emits per-viewer SFU counters before candidate stats, and
checks HTTP request cancellation before doing more expensive candidate
collection. A revised same-condition local run is in progress. This remains
diagnostic evidence only; M7-H is not accepted. At the 17:10 check, that
run had a pre-deadline partial send stall: about 15,000 frames/s through
108,005ms, then 5,717 frames/1,562 stale at 109,005ms, with 813 publishers
still stale at 120,007ms (oldest send 11.815s old). Final timeout evidence
is pending; no cause is established.

## Follow-up — 2026-11-19 16:48 +0545: compare trace-off send and preserve feedback evidence

The callback-state logging change is now opt-in. With tracing disabled, the
local 3,000/3,000 run remained active at elapsed 104,003ms
(`frames=14998`, `staleOver500ms=0`) and the harness log was
2,356,879 bytes / 9,830 lines, versus 11,217,950 bytes / 78,810 lines in
the preceding traced run. The earlier 104,004ms active-send stall did not
recur in that window. This supports investigating log contention, not
claiming a fix; the trace-off run still had severe jitter near 120 seconds
and timed out feedback at 261/3,000.

The next local run is exercising a new bounded feedback-timeout snapshot:
partial publisher counts plus SFU-side per-viewer feedback, ICE candidate
pairs, socket aggregates, queue drops, and forwarding-error count for at
most five incomplete viewers. p95/p99 remain **NOT MEASURABLE**; M7-H is
not accepted.

## Follow-up — 2026-11-19 16:30 +0545: active-send run profiles and logger contention

A later, distinct local 3,000/3,000 run used a 120-second send window and
reached `frames=0, staleOver500ms=3000` at elapsed 104,004ms, before the
deadline; the SFU also reached `packets=0, staleOver500ms=3000`. It timed out
feedback at 356/3,000 and did not establish M7-H acceptance. Harness profiles
are `/tmp/hami-media-011-on-demand-ice-stats-profile-harness-stall.pprof` and
`/tmp/hami-media-011-on-demand-ice-stats-profile-harness-stall-plus-30s.pprof`.
The second profile is roughly five minutes after the trigger, not +30s.

The first profile shows Pion SRTP reads, ICE connectivity checks, DTLS
handshake waits and UDP write-lock waits. The later profile shows 2,977
goroutines blocked at `os.Stderr` writes in `attachPCStateLogging`; this is
evidence of later callback-log contention, not proof of the initial stall's
cause. The SFU profile transfer failed and produced no SFU file. See the
newest `docs/CAPABILITY_QUEUE.md` entry and `queue/011` follow-up. The
attempt-13 historical send deadlines remain unreconciled; this later run does
not retroactively prove the earlier attempts' interpretations.

## Correction — 2026-11-19 15:53 +0545: reconcile every run with its send deadline

Source and a controlled local run now confirm that `-duration` is the
media-send lifetime. When its `sendContext` expires, `frames=0` and all
publishers becoming stale are expected; they are not evidence of a shared
runtime block. A 3,000/3,000 run sent 14,956 frames at elapsed 65,003ms and
reported zero frames/all stale at 66,004ms, with no profile trigger after
the active-send guard. See the latest `docs/CAPABILITY_QUEUE.md` entry and
`/tmp/hami-media-011-active-send65-harness.log`.

The run commands and configured durations for the historical attempt-13
observations are not recorded here, so this evidence does not establish
whether each attempt-13 last-send time preceded its own configured deadline.
Until that is reconciled from raw evidence, the statements below that the
stall was deterministic, that a common block was proven, or that GC was
ruled out are **unsupported**. Do not use the post-deadline 65-second
profiles as evidence for the mux, UDP, or NACK causal candidates.

## Historical report (interpretation superseded; raw observations retained)

Feed to Copilot the moment its 009 turn ends. Do NOT feed while 009 is still running.
Supersedes /tmp/next-order-after-009-attempt13-stall-triage.md (19:25) — the tuned re-run has now produced new evidence.

## UPDATE 19:39 +0545 — TUNED2 re-run ALSO stalls identically (third stall, same signature)

- Started 19:36:25 +0545: /tmp/hami-media-m7h-attempt13-tuned2-run.log — "m7h split process: role=harness pid=69493 sfuPid=69496 address=127.0.0.1:58821". Heap pprof files written 19:36:35.
- Samples 19:39:06–19:39:14 (elapsed 151–159 s): publishers=3000, frames=0, staleOver500ms=3000, maxLastSendAgeMs 86,202 → 94,202 and growing. Oldest publisher hami-m7h-publisher-2901 last sent 19:37:40.215794 +0545 — NO publisher has sent a frame since, ~75 s into the run.
- Goroutines FROZEN at exactly 101,179 across samples; cpuCores=0.000; schedP95UpperMs ~0.049 ms; gcCycles=0 (harness-side). Scheduler idle, not overloaded.
- Mass PC disconnect wave in progress 19:39:06–19:39:07 (publisher-1493/1216/0143/0911/0223/0323/0261/0247/1034/1327/2170/0269/1036/1507 ...).
- Run STILL LIVE at 19:39:14 (log 79,970 lines / 10.6 MB, still growing); verdict JSON /tmp/hami-media-m7h-attempt13-tuned2-run.json still 0 bytes.
- UPDATE 19:42 +0545 — TUNED2 RUN HAS FINISHED (teardown complete, log final: 15,516,199 B / 111,479 lines). Verdict in the log tail: "feedback wait timed out after 5m0s: 171/3000 tracks complete; nackZero=2753 pliZero=2703 firZero=2712 maxN=1 maxP=1 maxF=1". Attribution: connectedThenDied=6000, survived=0, currentlyConnected=0; median died lifetime 90,010 ms (publishers 89,085 ms, viewers 178,334 ms). totalWrites=2,020,855, deadWrites=0. ALL 6,000 connections died — same as the tuned run, only the track count differs (171 vs 60). Verdict JSON is STILL 0 bytes — verdict logged but never written to JSON, same bug as the tuned run; that is a second defect to fix. Three completed stalls now (profile, tuned 60/3000, tuned2 171/3000): the stall is deterministic.
- THIRD stall, same ~1-min signature: profile ~66 s, tuned ~54 s, tuned2 ~75 s. The stall is DETERMINISTIC, not a one-off, and the GC heap is ruled out twice over. Do NOT re-run the same binary a fourth time expecting a different result.

## Verified evidence (read directly from the raw logs, not from a summary)

- Fresh binary built 19:28:10 +0545: /tmp/hami-media-m7h-attempt13 (18,236,306 B). Heap pprof files written 19:28:33.
- TUNED re-run started 19:28:22 +0545: /tmp/hami-media-m7h-attempt13-tuned-run.log — "m7h split process: role=harness pid=45083 sfuPid=45086 address=127.0.0.1:58550". Header confirms mux enabled, both socket counters on, 4 MB receive buffers.
- UPDATE 19:34:07 +0545 — TUNED RUN HAS FINISHED (teardown complete, log final: 15,685,560 B / 112,675 lines). Verdict is IN THE LOG TAIL: "feedback wait timed out after 5m0s: 60/3000 tracks complete; nackZero=2859 pliZero=2781 firZero=2802 maxN=1 maxP=1 maxF=1". Verdict JSON /tmp/hami-media-m7h-attempt13-tuned-run.json is STILL 0 bytes — the verdict was logged but never written to JSON.
- Harness samples 19:29:49–19:30:01: publishers=3000, frames=0, staleOver500ms=3000, maxLastSendAgeMs 33,193 → 44,191 and growing. Oldest publisher hami-m7h-publisher-0043 last sent 19:29:16.502756 +0545 — NO publisher has sent a frame since.
- Goroutines FROZEN at exactly 105,241 across samples; cpuCores=0.000; schedP95UpperMs ~0.049 ms; gcCycles=0 (harness-side). The scheduler is idle, not overloaded.
- Mass PC failure wave 19:29:49–19:29:50: dozens of publisher + viewer PCs failed/disconnected within ~1 s (e.g. publisher-1813/1300/2452/2052, viewer-2065/2996/426/272/2309/1187).
- Comparison with the profile run: profile run stalled ~66 s in (last send 19:10:59, log silent from 19:22:46); tuned run stalled ~54 s in (last send 19:29:16). SAME signature, SAME ~1-minute mark.
- Final attribution (19:34:07): connectedThenDied=6000, survived=0, currentlyConnected=0; median died lifetime 108,532 ms (publishers 107,177 ms, viewers 193,801 ms). ALL 3,000 publishers + ALL 3,000 viewers died. totalWrites=2,469,203, deadWrites=0. Only 60/3,000 tracks ever completed feedback.

## Diagnosis change

- The 009 GC heap fix did NOT prevent the stall. Do NOT re-run the same binary expecting a different result.
- The cause is something SHARED that stops ALL 3,000 publishers' send ticks at once ~1 min in. Hunt the common cause at 19:29:16, not per-PC failures (those are fallout).
- Candidates to check with evidence, not guesses: the send ticker / shared lock or channel all publishers share; the SFU-side send path; a resource that exhausts at ~1 min (file descriptors, ports, memory — read the counts). A frozen goroutine count + idle scheduler points at a block, not overload.

## Ask

1. The tuned run has finished (teardown 19:34:07, verdict in the log tail, verdict JSON still 0 bytes). Confirm the process exit code and why the verdict JSON was never written. Read the raw tails of /tmp/hami-media-m7h-attempt13-tuned-run.log and /tmp/hami-media-m7h-attempt13-tuned-sfu.log yourself.
2. Find the single common cause of the simultaneous send stop at 19:29:16. Name the exact code path (file + line).
3. Minimal fix, then a SMALL-scale repro first (e.g. 100 publishers) to prove the fix holds past the ~1-min mark before another 3,000-publisher run.
4. Report back with file paths and line numbers.

## Item 2 (separate, after the stall work) — ledger page landed but tsc fails

- src/routes/ledger.tsx EXISTS: 6,658 B / 185 lines, written 19:26 +0545. It uses only ledger.ts exports (canRender, latestStateChange, publicClaims, renderValueLabel + types) — verified by grep in /tmp/ledger-page-verify.log.
- BUT `tsc --noEmit` FAILS: src/routes/ledger.tsx(12,38): error TS2345: Argument of type '"/ledger"' is not assignable to parameter of type 'keyof FileRoutesByPath | undefined'.
- Root cause: src/routeTree.gen.ts is STALE (27,520 B, dated Nov 16 15:38) — no /ledger in it. The vite build that regenerates it FAILED: `[with-app-env] failed to run vite: spawn vite ENOENT`, build_exit=127.
- Fix: regenerate the route tree (run vite via npx or node_modules/.bin/vite — fix the PATH in the build script), then re-run `tsc --noEmit` until it passes. Evidence logs: /tmp/ledger-build-verify.log, /tmp/ledger-page-verify.log, /tmp/ledger-routetree.log, /tmp/ledger-livestrip-grep.log.

## Item 3 (Niroj 19:47 +0545 — home-site links: DO NOT BUILD, already delegated)

- Niroj's order (19:47): everything must be accessible from the public home site — nothing dormant, nothing un-deployed. Build it, link it from the home site, deploy it, verify it live. A page built but not linked and not deployed is dormant, and dormant is not allowed.
- VERIFIED by self-watch 19:48-19:50 from the repo (index.tsx + __root.tsx read directly): the home page has NO link to /ledger, /build-log, /hami-methodology.html, or /hami-systems-map.html. Its only nav links are /about (x4), /unknowns, /needs, /experiments, /discoveries. __root.tsx has no nav links to them either. index.tsx imports ledger.ts and renders ledger content inline, but never links to the /ledger route.
- Four dormant items, all uncommitted/unpushed (not deployed): public/hami-methodology.html (21,561 B), public/hami-systems-map.html (18,052 B), src/routes/ledger.tsx (6,658 B), src/routes/build-log.tsx (9,590 B, TSC_OK + BUILD_OK).
- DO NOT build the home-page links yourself: builder b48f62c9 is already adding the "Explore Hami" section to src/routes/index.tsx (links to /ledger, /build-log, /hami-systems-map.html, /hami-methodology.html, /meet-hami). Do NOT edit index.tsx for links — two workers on one file will collide. Parent owns the selective commit + push and the live verification after the links land.
- Your part, after the stall work: if the links builder has landed, run tsc + Vite build to confirm the home page still passes, and report the result. Do NOT commit/push — the standing rule stands for you.
- Context, not an ask: /api/health on Vercel (crawled 19:36) returns {"status":"degraded","ready":false,"db":"not_configured"} — the site responds; degraded = DB not configured on Vercel (standing state, not a new outage).

## Rules that never change

- Protected settings unchanged: mux ENABLED, both socket counters ON, 60 s per-pair timeout, RTP queue fix, NACK queue fix (512/5/512), RTCP chunking (253), 5 fps. No commit/push. Do NOT touch docs/UNKNOWN_MAP.md.
