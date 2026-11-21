# M1-H Measurement Harness — Integration

Built on the VM (Go 1.27.4, the same version as the Mac) so it is ready
to place the moment the single-node SFU router lands. No LiveKit in the
path; no new dependencies.

## Drop-in files

Copy into `services/hami-media/` (ForgeOS repo, on the Mac):

- `latency.go` — FrameClock, LatencyRecorder, Summary, Percentile.
  Package `main`, standard library only. No go.mod change needed.
- `latency_test.go` — unit tests + synthetic end-to-end simulations.

`go.mod` in this folder is for testing on the VM only. Do NOT copy it
into `services/hami-media/` (that module already has its own go.mod).

Verified here before handoff: `gofmt -l`, `go vet ./...`,
`go test -race -count=1 ./...` — all passing on Go 1.27.4 linux/amd64.

## The three call sites in main.go

### 1. Publisher — stamp each frame at capture

One `FrameClock` per publisher, shared with its subscribers (same
process, same monotonic clock domain).

```go
clock := NewFrameClock()
if err := clock.SetExpectedConsumers(viewerCount); err != nil {
    return err
}
// ... when a video frame is created, before it is sent:
clock.CaptureNow(frameID) // frameID = the frame's RTP timestamp (uint64)
```

Frame identity is the RTP timestamp: one video frame = one RTP
timestamp, fragments of a frame share it. Audio uses a distinct
`AudioFrameClock`, keyed by the audio RTP timestamp; never pass an audio
frame through the video `FrameClock`.
The clock keeps a capture until all expected subscriber recorders match
it. `Pending()` reports captures still missing one or more subscriber
matches; report the count even when every subscriber's latency percentiles
pass.

### 2. Subscriber — record each frame at the event

One `LatencyRecorder` per subscriber. Create it in receive mode until a
real decoder + render callback exists:

```go
rec := NewLatencyRecorder(ModeReceive) // honest label, NOT capture-to-render
// ... when a full video frame is assembled (marker received and every
// sequence from the known frame start through the marker is present; packets
// may arrive out of order within the frame, while late packets from older
// timestamps are ignored):
rec.RecordNow(frameID, clock)
```

When a real decoder + render callback exists, call the same `Record`
at the render callback instead, and create the recorder with
`ModeRender`. The mode is carried in every JSONL record and in the
summary — receive must never be reported as capture-to-render.

Audio uses `NewAudioFrameClock()` and `RecordAudio`/`RecordAudioNow`, only
after an Opus decoder has produced PCM for the local render sink. An
`OnTrack`/`ReadRTP` callback is receive latency, not render latency. A
subprocess decoder fed by RTP/UDP must be stopped through its context: the
RTP input has no EOF when a publisher stops.

### 3. Proof runner — M1-H (1 publisher, 10 viewers)

- 1 publisher, 10 subscribers through Hami's own router.
- Each viewer subscribes to the 1 stream (selective subscription).
- Run >= 60 s, >= 300 frames per subscriber.
- Per subscriber: `rec.Summary()` must have `Pass == true`
  (p95 <= 100 ms, p99 <= 150 ms, frames >= 300, duration >= 60 s).
  EVERY subscriber passes independently — one failing subscriber fails
  the proof.
- Evidence per subscriber: write `rec.SamplesJSONL()` to
  `subscriber-N.jsonl` and the summary alongside it.
- Also report `clock.Pending()` — frames captured but never matched
  (a loss signal). A high pending count with a passing p95 is still a
  problem; report it, do not hide it.

## Local Opus audio rung (TEST only)

The `audio-rung1` mode uses Hami's existing Pion SFU router, local
PeerConnections, and FFmpeg/libopus. It requires no LiveKit service, Cloud,
Docker, paid service, new database table, or product UI. The default first
rung is 10 Opus speakers × 100 listeners in one room, and a single invocation
runs both server mixing and selective forwarding sequentially:

```sh
go run . -mode audio-rung1 -duration 65s
```

For a bounded local smoke before the full rung, use a smaller topology and
short duration:

```sh
go run . -mode audio-rung1 -duration 3s \
  -audio-speakers 2 -audio-listeners 2
```

The smoke is TEST evidence only; it does not meet the 60-second/300-frame
measurement limits. The full 10×100 run stops before setup when macOS reports
less than 2 GiB free swap. The harness uses local FFmpeg/libopus for Opus
encoding, server mixing, and decoded-PCM rendering. The reconnect smoke runs
during active media and keeps the same listener and logical subscription IDs.
Its hand-raise grant and decline are local TEST event traces, not writes to a
production event store.

Each mode emits a JSON result with per-listener capture-to-render summaries,
per-stream loss/jitter/reconnect counters, pending audio-clock captures,
heap/swap observations, and the hand-raise/reconnect event traces. Selective
forwarding counters are measured at each listener's speaker-track RTP input.
For server mixing, upstream loss/jitter are measured once on the shared mixer
input and identified as shared; downstream loss/jitter are per listener on
the mixed output. The inherited M1-H p95/p99 thresholds are reported by the
recorder but are not audio-specific acceptance thresholds. No distribution
mode is selected by this harness.

## Single-PC SFU scale proof (no LiveKit service)

The existing `sfu-single` mode starts the simulated publisher, Hami's Pion
router, and viewers inside one process on loopback. It does not need LiveKit
Cloud, a LiveKit server, Docker, credentials, or a paid service. Results are
local `TEST` evidence, not production capacity or multi-machine routing.

Requirements are Go (the module declares Go 1.24 or newer), the pinned Pion
modules, and a local Annex-B H.264 file. A first build may need to download
the modules; once cached, this pure-Go build works offline:

```sh
cd services/hami-media
CGO_ENABLED=0 GOTOOLCHAIN=local GOPROXY=off go build -o hami-media .
```

Run any publisher/fan-out shape with the same existing proof path:

```sh
./hami-media -mode sfu-single -duration 61s \
  -video-file /path/to/local-source.h264 \
  -sfu-publishers 20 -sfu-viewers-per-publisher 5 \
  -max-heap-bytes 2147483648
```

Scoring is strict by default: every subscriber must meet the existing latency,
frame-count and duration gates, with zero unmatched or pending frames. For
scale diagnosis, opt in to dissolve scoring:

```sh
./hami-media -mode sfu-single -duration 61s \
  -video-file /path/to/local-source.h264 \
  -sfu-publishers 20 -sfu-viewers-per-publisher 5 \
  -sfu-score-mode dissolve -sfu-max-p99 150ms -sfu-max-dissolved 0.01
```

The JSON retains each viewer's delivered-frame p50/p95/p99. Dissolve mode
requires every viewer's p99 to meet `-sfu-max-p99` and the overall
`dissolved_fraction` to meet `-sfu-max-dissolved`; routing, authorization,
RTCP, write-error, and cleanup checks remain required. The numerator counts
unmatched events and pending frame deliveries, plus intentional-shed and
queue-dropped RTP packets. Queue drops that are also counted as intentional
sheds are de-duplicated. Because the last two components are packet counts,
this is an operational observation fraction, not a claim that every packet
corresponds to one lost frame.

`-nack-max-queue-age` sets the stale queued-RTP age (default `500ms`) and is
included in the proof JSON. It must be positive.

Every `sfu-single` run first checks macOS pressure (must be NORMAL/1), free
swap (at least 2,048 MiB), and free disk (at least 10 GiB). A failing or
unavailable preflight is logged and retried every 10 minutes; the proof does
not start until the readings pass. The disk floor is a conservative default
because the existing scale ledger had no disk threshold. During a run the host
watchdog samples those values plus `vm_stat` Swapouts and Pageouts once per
second; a failed stop condition cancels the proof and reports
`ABORTED-BY-HOST`, not a capacity verdict.

Unless explicitly set, `sfu-single` also arms a Go-heap cap of 2× the
estimated 0.5 MB per viewer, with a 256 MiB minimum for small proofs.
`-max-heap-bytes` overrides that default; explicitly passing `0` disables the
heap guard. It is checked before peer setup and sampled every 100 ms while the
proof runs. This is **not** an operating-system RSS limit and does not include
socket buffers or other processes. When enabled, stderr records the configured
budget and HeapAlloc/HeapInuse/HeapSys/GC/goroutine samples at startup and once
per second; the proof JSON remains on stdout.

For split-process M7-H runs, the same limit is passed to the SFU child and
enforced independently in the harness and SFU processes; it is not an
aggregate two-process limit. `-m7h-heap-profile <temporary-prefix>` captures
connected and post-media profiles as before, and adds harness/SFU pairs at
60, 90, and 120 seconds when the configured run duration leaves at least
30 seconds for each capture to complete. These profiles are diagnostic
artifacts, not proof of a universal memory ceiling.

For a 100-viewer layout sweep, vary only the last two values:

| Publishers | Viewers per publisher | Total viewers |
| ---: | ---: | ---: |
| 1 | 100 | 100 |
| 5 | 20 | 100 |
| 10 | 10 | 100 |
| 20 | 5 | 100 |
| 50 | 2 | 100 |
| 100 | 1 | 100 |

On one Apple Silicon Mac, a six-layout 61-second sweep passed the existing
per-viewer latency, track-isolation, NACK, PLI/FIR, and cleanup checks. An
earlier snapshot of a same-host 50 × 2 run appeared to fail fast because it
was checked before the 61-second run finished; the completed same-path run
and a unique-path rerun both passed. This is a repeatable starting matrix,
not a promise that every PC can sustain the same load. Start low and use the
emitted JSON to verify each viewer. The 5,000-viewer
configuration is accepted by the harness but has not passed a runtime proof;
do not jump to it without host-specific rungs and a conservative memory
budget. Darwin, Linux, and Windows cross-builds now pass; Windows runtime
support is still not established.

### Opt-in selected-frame diagnostics

The default proof remains unchanged. To trace a bounded set of RTP timestamps
in `sfu-single`, provide a new JSONL output path; the file is created
exclusively with mode `0600`. Each selected packet records viewer/track,
sequence number, RTP timestamp, marker, assembler state before and after the
packet, changed fields, and any completed frame ID. The result JSON includes
the selected IDs, output path, record count, and whether the hard cap was hit.
Writer errors fail the capture instead of silently dropping evidence.

```sh
./hami-media -mode sfu-single -duration 61s \
  -video-file /path/to/local-source.h264 \
  -sfu-publishers 20 -sfu-viewers-per-publisher 75 \
  -sfu-frame-diagnostic-output /tmp/sfu-frame-diagnostics.jsonl \
  -sfu-frame-diagnostic-ids 271462960,271468360,271457560 \
  -sfu-frame-diagnostic-max-records 50000
```

The timestamp list defaults to the three reconciled IDs and permits at most
64 distinct uint32 values; the record cap is limited to 1–100,000. Run only
after the existing free-swap safety floor is satisfied. This instrumentation
has not yet been run against the 20×75 topology, so it localizes no cause and
does not establish capacity.

## M7-H goroutine-profile timing diagnostics

When `-m7h-goroutine-profile` is enabled, correlate the client HTTP trace
(`get-conn`, `got-conn`, `wrote-request`, and `first-response-byte`) with the
SFU's goroutine-profile handler timestamps. The handler logs entry before
authorization, authorization completion, and the start/completion duration of
profile serialization and file writing. A delay before handler entry is
upstream of authorization and profile writing; a long profile-write interval
localizes cost to that operation. These timings help place the delay but do
not prove its cause or establish M7-H acceptance. Run a 3,000-pair diagnostic
only after the existing free-swap floor is satisfied.

## Local process-separated SFU cascade proof (TEST only)

The bounded `sfu-cascade` mode launches two separate local M7-H SFU processes
and routes one H.264 publisher through worker 1 to an authorized viewer on
worker 2. It denies an unauthorized subscription, relays RTP between workers,
and requires a downstream NACK retransmission to be observed by the viewer,
PLI/FIR to reach the original publisher, and both workers to clean up
successfully. It is local protocol/correctness evidence only; it does not
establish horizontal capacity, a viewer limit, or a 5,000-viewer result.

```sh
cd services/hami-media
go run . -mode sfu-cascade -duration 3s \
  -video-file /path/to/local-source.h264
```

The JSON identifies the run as local `TEST` evidence and reports the two
worker process IDs, relay/viewer track identities, RTP counts, viewer-observed
NACK retransmission, PLI/FIR delivery, and cleanup status. The in-process
router regression separately checks NACK handling and RTCP translation; the
strict viewer-retransmission gate for this topology is the process-separated
mode and `TestLocalSFURoutesAuthorizedStreamsAndRTCP`.

## Local HLS transport smoke (TEST only)

This bounded test validates local HLS encoding, playlist/segment serving, and
HTTP readability. It uses FFmpeg's synthetic test pattern; it does **not**
ingest a webcam or exercise Hami's Pion publisher/router. The existing
`m7hRemoteSFUServer.handlePublisher` endpoint is private-token signaling for
the split local proof, not a browser camera API. Keep this smoke separate from
real-ingest and viewer-capacity claims.

Install FFmpeg once if it is missing. Python's standard-library HTTP server
is sufficient; nginx is not required:

```sh
brew install ffmpeg
mkdir -p /tmp/hami-hls
ffmpeg -hide_banner -loglevel warning -re \
  -f lavfi -i 'testsrc=duration=20:size=640x360:rate=15' \
  -f lavfi -i 'sine=frequency=1000:duration=20' -t 20 \
  -pix_fmt yuv420p -c:v libx264 -preset ultrafast -tune zerolatency \
  -g 30 -keyint_min 30 -sc_threshold 0 \
  -c:a aac -b:a 64k \
  -hls_time 2 -hls_list_size 5 \
  -hls_flags delete_segments+omit_endlist \
  -hls_segment_filename /tmp/hami-hls/segment_%03d.ts \
  -f hls /tmp/hami-hls/live.m3u8
```

In another terminal, serve only on loopback (choose an unused port):

```sh
python3 -m http.server 18080 --bind 127.0.0.1 --directory /tmp/hami-hls
```

Verify the playlist and both encoded streams over HTTP:

```sh
curl --fail --head http://127.0.0.1:18080/live.m3u8
ffprobe -v error \
  -show_entries stream=codec_type,codec_name,width,height,r_frame_rate \
  -of json http://127.0.0.1:18080/live.m3u8
```

On macOS, Safari can open the same `.m3u8` URL using native HLS support. Do
not load an HLS player from a CDN for this local-only test. A playlist-fetch
load test is control-plane/request evidence only; it is not 10,000 video
streams, video egress, or a capacity result. Check host memory and swap before
any high-concurrency HTTP test.

Verified locally with FFmpeg 9.0.2_1: the 20-second test produced a five-entry
two-second playlist; `curl` returned HTTP 200 with
`application/x-mpegurl`, and `ffprobe` read H.264 640×360@15 plus AAC over
loopback. This is TEST-only evidence. Pion-to-FFmpeg ingest and browser
playback still require separate verification.

## M2-H local multi-publisher proof

The `m2h` runner uses ten distinct publisher PeerConnections and tracks,
with five selectively authorized viewers per track. Each publisher has
its own `FrameClock`; each viewer has its own `LatencyRecorder` in
`ModeReceive`. The runner sends NACK, PLI and FIR feedback from every
viewer and records per-viewer forwarding/retransmission counts plus
per-publisher upstream counts.

Run locally with a duration of at least 60 seconds:

```sh
go run . -mode m2h -duration 65s -video-file /path/to/local-source.h264
```

The result must show all 50 viewers connected and receiving only their
requested track, at least 300 receive-mode frames per viewer, passing
latency thresholds per viewer, and complete NACK/PLI/FIR forwarding.
These are local TEST results, not capacity claims. Receive-mode latency
is not capture-to-render latency.

## M3-H local 50-publisher proof

The `m3h` runner uses 50 publisher PeerConnections and 100 viewers, with
two selectively authorized viewers per publisher track. It uses the same
per-publisher frame clocks, per-viewer receive-mode recorders and per-viewer
NACK/PLI/FIR verification as M2-H. Run locally for at least 60 seconds:

```sh
go run . -mode m3h -duration 65s -video-file /path/to/local-source.h264
```

Require at least 300 matched frames and 60 seconds for every viewer,
passing latency thresholds, and exact requested-track isolation. This
remains local TEST evidence, not a capacity claim or capture-to-render
measurement.

## M4-H local 100-publisher proof

The `m4h` runner uses 100 publisher PeerConnections and 500 viewers, with
five selectively authorized viewers per publisher track. Each publisher
has its own frame clock; each viewer has an independent receive-mode
recorder and RTCP accounting. Run locally for at least 60 seconds:

```sh
go run . -mode m4h -duration 65s -video-file /path/to/local-source.h264
```

Verify every viewer's requested-track isolation, latency thresholds,
frame count, duration and NACK/PLI/FIR handling independently. This is
local TEST evidence, not a capacity or capture-to-render claim.

## M5-H local 500-publisher proof

The `m5h` runner uses 500 publisher PeerConnections and 1,000 viewers,
with two selectively authorized viewers per publisher track. It reuses
the same per-publisher frame clocks, per-viewer receive-mode recorders,
and per-viewer RTCP verification. Publisher frame starts are distributed
across one frame interval to avoid a synchronized send burst. Run locally
for at least 60 seconds:

```sh
go run . -mode m5h -duration 65s -video-file /path/to/local-source.h264
```

Verify requested-track isolation, latency thresholds, frame count,
duration and NACK/PLI/FIR handling for every viewer. These are local TEST
results only, not a general capacity or capture-to-render claim.

## M6-H local 1,000-publisher proof

The `m6h` runner uses 1,000 publisher PeerConnections and 2,000 viewers,
with two selectively authorized viewers per publisher track. Publisher
starts remain phase-spread; each publisher has its own frame clock and
each viewer has an independent receive-mode recorder and RTCP accounting.
To keep aggregate local transport load bounded, M6-H sends at 1 frame per
second per publisher and measures for 310 seconds, giving more than 300
frames per viewer. Run locally:

```sh
go run . -mode m6h -duration 310s -video-file /path/to/local-source.h264
```

Verify every viewer's track isolation, frame count, duration, latency
thresholds and NACK/PLI/FIR handling independently. This is local TEST
evidence, not a general capacity or capture-to-render claim.

### M6-H setup negotiation guard

The proof runner negotiates publisher/router pairs first, then viewer/router
pairs, with at most 32 negotiations active in each phase. Each pair has a
30-second deadline. A failed pair reports its phase index/identity and both
PeerConnection states; a timeout closes that pair and cancels the phase so
setup fails with a bounded, actionable error instead of waiting for the
overall M6-H context deadline. This is setup protection only and does not
constitute an M6-H runtime pass.

After setup, the first-packet checks share the media sender's duration-limited
context. If a viewer receives no RTP, the proof reports the missing packets
when the send window ends instead of waiting through the remaining setup
allowance.

Router-side PeerConnections are sharded across up to 32 ICE UDP muxes bound
to loopback; simulated client PeerConnections retain distinct local sockets
so both ends of each local ICE pair have different addresses. This limits
router-side socket pressure and distributes UDP traffic while keeping the
proof local-only.

## Attempt 11 — bounded feedback and local metrics

The existing router now keeps at most 64 NACK messages per subscription.
If the queue fills, it drops the oldest message and retains the newest
loss report; NACKs older than 500 ms are discarded by the worker because
their retransmissions are unlikely to help real-time playback. For each
NACK, the worker deduplicates sequence numbers, prioritizes the closest
sequences to the latest RTP packet, serves at most 128, and separately
counts duplicates and sequences skipped by the cap. The PLI/FIR reader
remains independent from retransmission work.

Run the existing 500-publisher/1,000-viewer local proof with the optional
loopback-only Prometheus endpoint:

```sh
go run . -mode m5h -duration 65s \
  -video-file /path/to/local-source.h264 \
  -metrics-listen 127.0.0.1:9464
```

In another terminal on the same Mac, scrape `http://127.0.0.1:9464/metrics`.
Capture the current Go heap profile after a GC with
`curl -fsS 'http://127.0.0.1:9464/debug/pprof/heap?gc=1' -o heap.pprof`,
then inspect retained objects with `go tool pprof -top -inuse_space
./hami-media heap.pprof`. This route is available only on the same loopback
metrics listener.
The endpoint reports active tracks/viewers/subscriptions; RTP forwarding
call-latency histogram, forwarded packets and write errors; NACK received,
retransmitted, deduplicated, capped, queued, stale-dropped and queue-full
counters; queue depth; current source NACK-cache packet count and RTP payload
bytes; Go runtime CPU time, heap/system memory and goroutine count. The cache
byte gauge excludes packet/header and map overhead, subscriber queues, and
Pion's separate responder, so it is not total retained heap. It is an optional
in-process diagnostic endpoint for this local proof harness, not a deployed
service monitor. It accepts loopback IPs only, and its values reset when the
process exits.

Run the module's focused/full regression suite and static checks locally:

```sh
go test -race -count=1 ./...
go vet ./...
go build ./...
```

### Impairment-test boundary

The current proof runner puts publisher, router and viewers in one process
and negotiates loopback PeerConnections. `tc netem` on a host interface
would not impair that loopback path; applying `tc` to the Mac's active
interface would affect unrelated traffic and is not an acceptable test.
Therefore this runner does not yet provide a valid 5% loss / 50 ms jitter
test, and no such result should be claimed. A real `tc netem` proof first
needs separate publisher/viewer processes routed through a dedicated,
isolated Linux veth or network namespace; impairment must be verified on
that exact path before its results count.

### Explicitly not implemented

- **Simulcast/SVC:** the harness sends one H.264 encoding per publisher
  track. It has neither a three-layer encoder/RID negotiation path nor
  scalable-codec dependency metadata and a decoder. Duplicating this
  single encoded stream under three labels would not be simulcast or SVC.
- **Multi-machine routing:** publisher, track, viewer, authorization and
  subscription state are process-local maps and all current proof peers
  are loopback. There is no node ownership, cross-node signaling or RTP
  transport. This is not a multi-machine-ready or production deployment.

## What NOT to do

- Do not relabel `ModeReceive` results as capture-to-render.
- Do not average latencies and report the average — p95 is the gate.
- Do not use the publisher PeerConnection's stats for subscriber reads.
- Do not drop unmatched frames silently — `Unmatched` and `Pending`
  are part of the result.
- Do not shorten the run to fit a fast result — 60 s and 300 frames
  are minimums, not targets.
