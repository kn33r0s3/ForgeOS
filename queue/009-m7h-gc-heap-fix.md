# 009 — M7-H attempt 13: fix the GC mark stalls (p99)

- **Finding:** ~/workspace/hami-reports/2026-11-18-m7h-p99-stall-cause-gc.md (Muse, 18 Nov ~17:45). The p99 stalls are heavy concurrent GC marks, NOT stop-the-world pauses and NOT bad viewers. Three marks start 39–118 ms before each stall cluster (12:51:01, 12:51:04, 12:51:17): gc#49 wall 554 ms / CPU 2,919 ms / live 4,660 MB; gc#30 wall 503 ms / CPU 2,517 ms / live 3,856 MB; gc#50 wall 788 ms / CPU 4,103 ms / live 5,702 MB. Max STW is 0.895 ms. Live heap reaches 5,702 MB (goal 9,418 MB). The 17:30 "+25 s / +40 s" bin labels are WRONG (bin epoch is ~20–21.6 s after first capture; real clusters are at 46.6 s, 50.1 s, 63.2 s) and the harness CPU spikes are a red herring.
- **Owner:** Copilot (after queue/007 lands; do not start while 007 is running)
- **Input:** ~/workspace/hami-reports/2026-11-18-m7h-p99-stall-cause-gc.md + services/hami-media/main.go + the r3 run log /tmp/hami-media-m7h-attempt12-r3-run.log + GC trace /tmp/hami-media-m7h-attempt12-r3-gctrace.log
- **Output:** (1) a heap profile (pprof) naming what retains the GBs; (2) the fix — cap or release the retainers + GC tuning (GOMEMLIMIT / GOGC); (3) a re-run of M7-H r3 proving p99 passes; (4) a one-line record in docs/CAPABILITY_QUEUE.md
- **Verify:** re-run M7-H r3 (3,000 pub / 3,000 viewers, 65 s at 5 fps) and show: no concurrent mark >200 ms wall during the window, no heartbeat late >100 ms, p99 per viewer 3,000/3,000 pass. Read the raw numbers from the run JSON + GC trace yourself; do not trust a summary.
- **If blocked:** if the heap profile cannot be taken (no pprof endpoint / no repro), record it as BLOCKED with the exact error and move to the GC-tuning step (GOMEMLIMIT/GOGC) instead. Do not change the NACK constants, the 512/5 s queue, the 253-pair chunking, or the mDNS-disabled setting. Do not commit, push, or deploy.

## Fix order (by leverage)
1. Find what retains the GBs (heap profile, pprof) — per-viewer buffers, NACK queues, recorder state? — and cap or release it. A smaller live heap makes every mark shorter and cheaper.
2. GC tuning: GOMEMLIMIT / GOGC to force earlier, smaller marks; measure whether mark CPU per second falls without hurting throughput.
3. Isolate the marking from the forward path: GOMAXPROCS / CPU pinning, or split SFU and harness onto separate machines/cores so one process's mark cannot starve the other's forward path.
