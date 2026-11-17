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
timestamp, fragments of a frame share it. Audio uses the sample
timestamp. Do not invent a second identity scheme.
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
The endpoint reports active tracks/viewers/subscriptions; RTP forwarding
call-latency histogram, forwarded packets and write errors; NACK received,
retransmitted, deduplicated, capped, queued, stale-dropped and queue-full
counters; queue depth; Go runtime CPU time, heap/system memory and goroutine
count. It is an optional in-process diagnostic endpoint for this local
proof harness, not a deployed service monitor. It accepts loopback IPs
only, and its values reset when the process exits.

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
