# Correction — 2026-11-19 15:53 +0545: send deadline is not a stall

The order's `-duration 65s` controls the local media-send lifetime. The
existing `sendContext` expires when that duration ends. A post-deadline
`frames=0, staleOver500ms=3000` sample is therefore expected and must not
trigger a stall diagnosis.

The corrected local 3,000/3,000 run used the existing binary
`/tmp/hami-media-011-active-send` (its diagnostic linker flags were checked
with `go version -m`) and `-duration 65s`. It still sent 14,956 frames at
elapsed 65,003ms. The last observed send was
`2026-11-19T15:47:32.998470+05:45`; the zero-frame/all-stale sample appeared
at 66,004ms. No profile trigger was logged and no profile files were
created, confirming the active-send guard. Run logs:

- `/tmp/hami-media-011-active-send65-harness.log`
- `/tmp/hami-media-011-active-send65-sfu.log`

Earlier 65-second zero-frame samples and their profiles were post-send and
cannot establish an active-stream stall or its blocking path. In particular,
do not use those profiles to support the prior mux/UDP/NACK causal candidate.
The corrected run still failed its feedback wait at 353/3,000; p95/p99 are
**NOT MEASURABLE**, and M7-H is not accepted. Three 120-second retries failed
viewer negotiation at different viewers (702, 1271, 1351) before sending.

Two further instrumented retries followed: viewer 912 ended with
`candidatePairs=[]` (not proof candidates were absent); viewer 1450 showed
2 local and 2 remote candidates and a nominated, succeeded loopback host
pair (10 packets sent, 5 received). Client and SFU states briefly reached
connected, then disconnected; SFU connected duration was 17.276s. At elapsed
20–26 seconds, SFU samples showed about 80k goroutines and scheduler p95
upper bounds of 235–1,342ms, with a 3,758ms maximum. These measurements are
correlated; they do not prove scheduler delay caused the ICE loss.

Next: capture SFU-side candidate-pair and per-peer socket counters at ICE
connected/disconnected transitions. Capture stall profiles only if the
trigger fires while the send context is active. The root cause of any genuine
active-send stall remains UNKNOWN.

---

# 011 — Capture a goroutine profile at the 3,000-peer stall (diagnose, then confirm)

Status: DIAGNOSTIC RUN COMPLETE; M7-H FAILED, ROOT CAUSE OPEN (updated 2026-11-19 14:58 +0545).

## Follow-up — 2026-11-19 17:27 +0545: v3 stats request canceled before feedback snapshot

The v3 trace-off 3,000/3,000 run stayed active through 120,005ms
(14,947 frames, zero stale); a brief 109,222ms sample with 55 stale
recovered by 110,003ms. All-stale at 121,003ms was post-deadline. Feedback
timed out at 380/3,000 (`nackZero=611`, `pliZero=2620`, `firZero=2620`,
`maxN=146`, `maxP=1`, `maxF=1`); all 6,000 peers connected then died,
median 184,932ms.

The two-second `/stats` request expired. The server accepted at
17:25:34.267, then the viewer-map snapshot finished at 17:25:34.800 after
532ms with canceled context; the feedback-snapshot phase never started. v4
extends the local-only diagnostic deadline to five seconds and logs client
start/elapsed time. Its 3,000-peer run is active. Check whether feedback
snapshot and candidate pairs complete before drawing any transport
conclusion. M7-H remains unaccepted; p95/p99 **NOT MEASURABLE**.

## Follow-up — 2026-11-19 17:18 +0545: v2 partial stall; v3 stats timing in progress

The completed v2 trace-off 3,000/3,000 run exposed a partial active-send
stall before its 120s deadline. At 108,005ms it sent 14,992 frames with no
stale publishers; at 109,005ms it sent 5,717 with 1,562 stale; at 110,004ms
it sent 7,638 with 1,372 stale. Then 813 publishers remained stale through
120,007ms, with the oldest last send 11.815s old. The all-stale reading at
121,012ms was post-deadline.

The 5-minute feedback wait failed at 396/3,000
(`nackZero=1565`, `pliZero=2604`, `firZero=2604`, `maxN=99`, `maxP=1`,
`maxF=1`); all 6,000 peers connected then died (median 176,409ms). All 3,000
injection calls returned without errors or skipped peers, but the sampled
SFU subscription saw NACK received/forwarded 283/246 and PLI/FIR received/
forwarded 0. Pion's NACK responder passes the original RTCP batch and does
not consume PLI/FIR, leaving the transport/read boundary unresolved.

The 2s `/stats` call expired; the SFU printed one viewer's feedback near
shutdown without candidate-pair evidence. The handler now logs request,
viewer-map, and feedback-snapshot phases, checks cancellation early, and
avoids nesting the server map read lock with router feedback locks. Go tests,
vet, `npm test` (295), gates, and diff checks passed. Updated v3 3,000-peer
run is in progress to measure the delay boundary; M7-H remains unaccepted
and p95/p99 **NOT MEASURABLE**. Its 17:23 interim send phase recovered from
55 stale publishers at 109,222ms and continued sending through 120,005ms;
all-stale at 121,003ms was post-deadline. The five-minute feedback wait and
stats phase timing remain pending.

## Follow-up — 2026-11-19 17:05 +0545: trace-off send replicated; PLI/FIR absent at sampled SFU subscriptions

A second local 3,000/3,000 run with `M7H_TRACE_PC_STATE=0` continued sending
at elapsed 104,006ms (15,001 frames, no stale publishers) and 120,007ms
(14,860 frames, no stale publishers). The first zero-frame/all-stale sample
was at 121,007ms, after the send deadline. A 117,007ms jitter spike recovered
by 118,008ms. This confirms the earlier 104-second full stall did not recur
in two trace-off runs, not that callback logging was its proven cause.

Feedback timed out at 355/3,000. At wait-end, all 6,000 PCs had connected
then died; median lifetime was 243,756ms. The SFU eventually logged five
sampled incomplete subscriptions: NACK received 3,179 / forwarded 2,932,
PLI/FIR received and forwarded 0, RTP queue drops 0, RTP write errors 0,
router errors 0. This is evidence that PLI/FIR did not reach those sampled
SFU subscriptions; it does not establish why. The 2-second stats request
timed out and candidate-pair details were not returned.

The timeout path now captures injection attribution, selects one incomplete
viewer, logs its feedback before candidate stats, and stops candidate
collection if the HTTP request is canceled. The revised 3,000-peer run is
in progress. Its 17:10 harness check showed a partial active-send stall:
about 15,000 frames/s through 108,005ms, then 5,717 frames with 1,562 stale
at 109,005ms, and 813 publishers still stale at 120,007ms (oldest send
11.815s old). This preceded the 120-second deadline; the cause is unknown.
Keep M7-H unaccepted and p95/p99 **NOT MEASURABLE**.

## Follow-up — 2026-11-19 16:48 +0545: trace-off run and feedback timeout diagnostics

A 120-second local 3,000/3,000 run with per-peer callback tracing disabled
was still sending 14,998 frames at elapsed 104,003ms, with no publishers
stale; the preceding traced run reached zero frames/all stale at 104,004ms.
This is one comparison, not proof the log writes caused the earlier stall.
The new harness log was 2,356,879 bytes / 9,830 lines, versus 11,217,950
bytes / 78,810 lines before log suppression. Near 119,232ms, the trace-off
run still had 4,659 ticks >50ms and 52 >1s; at 120,004ms it continued to
send. The zero-frame/all-stale samples followed the 120-second send deadline.

Feedback still timed out at 261/3,000 (`nackZero=514`, `pliZero=2739`,
`firZero=2739`, `maxN=304`, `maxP=1`, `maxF=1`). p95/p99 are
**NOT MEASURABLE** and M7-H is not accepted. The existing feedback waiter now
returns partial counts, and the failure path queries SFU-side feedback,
candidate-pair, socket, queue, and forwarding-error stats for up to five
incomplete viewers. A same-condition local run is in progress to exercise
that diagnostic; inspect its logs before selecting a transport fix.

The current proof already uses a 32-worker feedback-injection pool, one
viewer per publisher track, and a bounded 64-packet RTP queue that drops its
oldest packet. Peer relaying remains untested and unjustified by these
measurements.

Read the diagnosis first: /tmp/hami-media-3000-peer-diagnosis.md — it has all the evidence (log excerpts, line numbers, the socket-counters solution).

## The situation (from the diagnosis)

- Attempt 13 stalled x3 identically at ~1 min: tuned 60/3000 tracks, tuned2 171/3000. Goroutines FROZEN (~101k-105k), cpuCores=0.000 — a BLOCK, not overload. GC heap fix ruled out twice.
- The SFU receives 0 packets for ~6 s (elapsedMs 6042-11000) while the harness is still sending 10k-16k frames per interval. The SFU's ReadRTP stops returning for ALL 3,000 tracks at once. The harness's sends then back up (UDP backpressure) and every publisher goroutine parks in WriteSample.
- The block is at or below Pion's ICE layer, NOT in the forward/queue code (the receive counter is incremented before any lock, main.go line 4365). The exact line inside Pion is UNKNOWN — that is what this order finds.
- The socket-counters question is SOLVED: the triage binary was built with a plain `go build` (no ldflags, counters default disabled); the tuned binaries were built with the ldflags (counters enabled). There is no build script that sets these flags. See the diagnosis, section 5.

## Task

1. Add a goroutine-profile endpoint to the SFU server AND to the harness, mirroring the existing heap-profile handler (main.go line 4127, `pprof.Lookup("heap")`). `runtime/pprof` is already imported (line 21). The endpoint must write a `pprof.Lookup("goroutine")` profile to a file (same pattern as the heap-profile handler: `writeM7HHeapProfile` / `captureHeapProfile`). Name it `/goroutine-profile` on the SFU and the equivalent on the harness. Keep the change MINIMAL — mirror the existing handler, nothing else.
2. Build with the EXACT tuned ldflags (the same build as the stalling runs, so the experiment is apples-to-apples). Record the exact build command in this queue entry. The ldflags are:
   `-ldflags="-X main.routerSocketWriteMode=enabled -X main.clientSocketReadMode=enabled -X main.clientSocketReadBufferSize=4194304"`
   Verify with `go version -m` on the built binary that the ldflags line is present BEFORE running. If it is absent, stop and fix the build command — do not run with a plain `go build` (that is how the triage counters got silently disabled).
   - Verified build command: `cd /Users/nirojpaudyal/Downloads/ForgeOS/services/hami-media && go build -ldflags="-X main.routerSocketWriteMode=enabled -X main.clientSocketReadMode=enabled -X main.clientSocketReadBufferSize=4194304" -o /tmp/hami-media-011-goroutine .`
   - Result: build succeeded with Go 1.27.4 (`darwin/arm64`).
   - Verification: `go version -m /tmp/hami-media-011-goroutine` reports `build -ldflags="-X main.routerSocketWriteMode=enabled -X main.clientSocketReadMode=enabled -X main.clientSocketReadBufferSize=4194304"`.
   - The first invocation from the repository root failed because no `go.mod` exists there; rerunning from the service module directory succeeded.
3. Run the SAME 3,000-publisher / 3,000-viewer M7-H test as attempt 13 (tuned config). Do NOT change any protected constant (nack 512/5s/512, RTCP 253, 60 s timeout, RTP queue 64, 5 fps, mDNS disabled, mux enabled, 4 MB buffer, 32 shards).
4. While the run is in progress, watch the harness log for the stall signature: send samples showing frames=0 and staleOver500ms=3000 (expected at ~1 min). The moment it appears, capture a goroutine profile from BOTH the harness and the SFU via the new endpoint. Capture a SECOND profile from both processes 30 seconds later, to confirm the park locations are stable and not transient.
5. Let the run finish (or stop it after the second profile if the feedback wait is still running — the profiles are the deliverable, not the verdict).
6. Read both profiles and report the top 10 parked goroutine locations (function + file:line) for EACH process, and name the blocking code path in plain words: where the goroutines are parked, on what (mux read loop, WriteSample, ReadRTP, a mutex, a channel, a syscall), and whether it is the same path in both processes.
7. Write the result to `/tmp/hami-media-011-goroutine-profile.md` on the Mac: the build command used (with the `go version -m` verification), the two profile file paths, the top-10 parked locations per process, the named blocking code path, and the next step it points to. If the profile implicates the ICE UDP mux, the next step is the mux-off 3,000-peer confirmation run (`-X main.routerUDPMuxMode=disabled` plus the same counter ldflags, with the fd limit raised — `ulimit -n 65536` — because per-connection sockets need ~12,000 fds). If it points elsewhere, name that path and the fix it suggests.
8. Record the socket-counters fix in this queue entry: the exact build command (with ldflags) is now the recorded build for every hami-media run, so the counters are ON in every future build.

## Exact output file

`/tmp/hami-media-011-goroutine-profile.md` on the Mac, plus the two goroutine profile files it names. Report back the profile file paths, the top parked locations, and the named blocking code path.

## Verify command

- `go version -m` on the built binary shows the ldflags line (counters enabled) before the run starts.
- After the run: `grep -c` the stall signature in the harness log (frames=0, staleOver500ms=3000) and confirm both goroutine profile files exist and are non-empty.
- `go tool pprof` (or a plain text read) of each profile lists the parked goroutine locations; the top 10 are in the output file.

## Blocked action

Do not commit, push, or deploy. Do not change any protected constant. Do not run a 100-publisher repro as the proof — it already passes and cannot reproduce this stall; the experiment runs at 3,000 scale. Do not claim the cause is the mux (or anything else) unless the profile shows it — report what the profile shows, and name UNKNOWN honestly if it does not settle it.

## Gates

Evidence first: every claim in the output file cites a file path + line number or a log excerpt. Nothing invented. The goroutine profile is the evidence; the named blocking path must match what it shows.

## Surpass Pion if needed (owner's direction, 18 Nov ~23:10)

Pion is the measuring stick, not the ceiling. We are AI and we are ahead with our gates — we never stop without achieving, then advancing to infinity. If the profile names a blocking path INSIDE Pion (its ICE layer, its mux, its read loop), the fix is not just to work around it: the next step after this order is to DESIGN THE SURPASS — Hami's own media path that goes beyond Pion's limit. Staged: (1) this order names the exact blocking path; (2) the mux-off confirmation run (if the mux is implicated) proves whether the mux is the cause; (3) then the surpass design: either patch/fork the blocking Pion code, or replace that layer with Hami's own implementation from first principles — whichever the profile evidence points to. Pion's limit is never Hami's limit. Record the surpass design as the next order, with the profile evidence it builds on.

## Latest run result — 2026-11-19 14:24 +0545

The timed mux-off run returned all four profiles but did not pass M7-H:
feedback timed out after 5 minutes at 32/3,000 tracks (exit 1). The harness
reproduced `frames=0, staleOver500ms=3000`; SFU samples reproduced
`packets=0, staleOver500ms=3000`. p95/p99 are **NOT MEASURABLE**.

The exact build command, `go version -m` evidence, run command, profile paths,
top parked stacks, and timing are in the existing
`/tmp/hami-media-011-sfu-starvation-result` and
`/tmp/hami-media-011-sfu-starvation-pprof.md`; no separate report file was
created because these existing records carry this diagnostic lineage.

The first SFU profile took 59.638s end-to-end. The second took 2m29.798s, with
2m29.282s between the client request log and the current handler-start log.
The second profile timestamp is about 3m29s after the trigger, not +30s;
`stall-plus-30s` is a stage name, not a measured interval. The SFU snapshots
show 7,487 then 9,617 goroutines waiting on UDP `fdMutex.rwlock` through
`WriteToInet4` and Pion ICE `candidateBase.writeTo` / `CandidatePair.Write`;
the first includes `ResponderInterceptor.resendPackets`. This remains
correlation, not a demonstrated root cause.

Next: instrument request arrival before authorization and mark profile-write
start/finish separately. Then test the SFU-side UDP write/NACK candidate with
one controlled intervention. Preserve the local-only boundary and do not
claim M7-H acceptance or causality.

## Follow-up — client trace and isolated-connection attempt (2026-11-19 14:58 +0545)

The existing profile endpoint and client were instrumented in
`services/hami-media/main.go`: client `httptrace` phases, handler entry,
profile-write start/completion, SFU `Serve` return, and child-process exit.
No protected tuning constant changed.

The valid local run used Go 1.27.4 / darwin/arm64, the exact mux-off and
socket-counter ldflags, the existing harness-publisher NACK bypass, and
`ulimit -n 65536`. Keep the harness and SFU logs separate:

- Harness: `/tmp/hami-media-011-profile-httptrace2-harness.log`
- SFU: `/tmp/hami-media-011-profile-httptrace2-sfu.log`
- Profiles: `/tmp/hami-media-011-profile-httptrace2-profile-harness-stall.pprof`,
  `/tmp/hami-media-011-profile-httptrace2-profile-sfu-stall.pprof`,
  `/tmp/hami-media-011-profile-httptrace2-profile-harness-stall-plus-30s.pprof`,
  `/tmp/hami-media-011-profile-httptrace2-profile-sfu-stall-plus-30s.pprof`

Harness stall at elapsed 67,009ms: `frames=0, staleOver500ms=3000`. SFU also
reached `packets=0, staleOver500ms=3000`. Four profiles were captured; feedback
timed out after 5m at 55/3,000 tracks (exit 1), so this is not acceptance and
p95/p99 are **NOT MEASURABLE**.

The first request's HTTP connection and request write callbacks were
immediate; handler entry was +11.877s, profile generation 0.597s, and first
response byte +15.819s. The second request began exactly +30s after trigger.
Its initial connection/write callbacks were within 0.121ms, but the trace then
showed another connection/write sequence at +2m15.831s. The SFU handler
entered +2m16.368s; profile generation was 0.378s; the client copied the
profile at +2m18.931s. This localizes delay across the request/response path
more narrowly but does not prove stale connection reuse, SFU scheduling, or
another cause. The latest SFU profiles retain NACK / ICE candidate write /
UDP `WriteToInet4` frames, but the filtered full traces from these two
profiles do not show `fdMutex`/`rwlock`; earlier profiles did. The harness
does not share the SFU's UDP-writer frames.

A first run used the same file for shell and SFU output and produced
concatenated lines; do not use it for precise timing. A subsequent fresh
profile transport with keep-alives disabled was built and verified, but its
3,000-peer run failed during publisher negotiation at publisher 2862 before
profile capture. It produced no profiles and did not test that intervention.

Verification after the source change: `cd services/hami-media && go test ./...`
and `cd services/hami-media && go vet ./...` passed; `gofmt -d` and
`git diff --check` were clean. Both diagnostic binaries built, and
`go version -m` showed the exact linker flags. `npm test` passed (168 script
and 295 TypeScript tests); `npm run gates` was GREEN. Full exact results and
pprof output are appended to `/tmp/hami-media-011-sfu-starvation-result` and
`/tmp/hami-media-011-sfu-starvation-pprof.md`.

Next: retry the fresh-connection isolation only after the local peer
negotiation path completes, with separate log files. Keep M7-H root cause
open; do not claim acceptance or causality.

## Fresh-connection retry — 2026-11-19 15:08 +0545

Rebuilt `/tmp/hami-media-011-profile-freshconn-retry2` with Go 1.27.4
(`darwin/arm64`) and verified the exact mux-off/socket-counter linker flags
using `go version -m`. Ran the same local M7-H 3,000/3,000 command with
`ulimit -n 65536`, the existing 65-second duration, and distinct harness/SFU
logs:

- `/tmp/hami-media-011-profile-freshconn-retry2-harness.log`
- `/tmp/hami-media-011-profile-freshconn-retry2-sfu.log`

The run exited 1 before profile capture: `hami-sfu-viewer-25` timed out
connecting (`context deadline exceeded`). At SFU elapsed 21,000ms, the log
showed `publishers=3000 packets=0 staleOver500ms=3000`; the harness did not
reach its `frames=0` stall signature. No profile files were produced. This
does not test the keep-alive-disabled transport under the target stall.

The SFU peer entered checking/connecting at 15:06:43.263876
(`...retry2-sfu.log:12333-12334`), its socket closed still checking at
15:07:13.395281 (`:22794`) and it failed at 15:07:14.302713 (`:22952-22953`).
The harness peer callbacks appeared at 15:07:27.132558
(`...retry2-harness.log:16984-16985`), 43.869s after the SFU's first state
event. This narrows the timing but does not identify the delayed request or
ICE phase. Next: trace existing `/viewer` request/response timing against
these state callbacks before retrying profile capture.

Verification command and exact flags:

```sh
go version -m /tmp/hami-media-011-profile-freshconn-retry2
ulimit -n 65536
M7H_SFU_LOG=/tmp/hami-media-011-profile-freshconn-retry2-sfu.log \
  /tmp/hami-media-011-profile-freshconn-retry2 -mode m7h -duration 65s \
  -video-file /tmp/test-video.h264 \
  -m7h-goroutine-profile /tmp/hami-media-011-profile-freshconn-retry2-profile \
  > /tmp/hami-media-011-profile-freshconn-retry2-harness.log 2>&1
```

An initial metadata grep expected a space where Go 1.27.4 prints a tab
between `build` and `-ldflags`; it stopped before running. Matching the exact
`-ldflags="..."` substring then verified the flags before the run. Next:
diagnose early remote-viewer negotiation and retry only after full
negotiation succeeds. Root cause and M7-H acceptance remain open.
# Correction — 2026-11-19 15:53 +0545: send deadline is not a stall
