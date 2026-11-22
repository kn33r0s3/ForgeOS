# Hami Media Next Architecture

Status: experimental direction from 2026-11-21; evidence reconciled
2026-11-23.

## Evidence chronology

An earlier report recorded a 20-publisher / 5,000-viewer run with:

- 5,000/5,000 viewer peers connected.
- 4,691/5,000 viewers passed every latency gate.
- 309/5,000 failed only the p99 <= 150 ms guardrail.
- 0 RTP queue drops, 0 intentional sheds, and 0 RTP write errors.
- Peak Go HeapAlloc 2.423 GiB and peak 175,796 goroutines.

These are historical reported measurements, not a passing 5,000-viewer result;
the active repository does not link their raw run artifact or source SHA.

A later, separately pre-registered local TEST run used 10 publishers x 500
viewers on 2026-11-23. The host watchdog aborted it while pacing viewer 2,801
after memory pressure reached level 2. It exited 1 without `measurement_pass`,
a completed viewer set, cleanup/forwarding/latency results, or a usable packet
loss result. Its raw evidence is under
`/Users/nirojpaudyal/hami/work/capacity-run/out-amended-20261123-003638/`.
This aborted run does not supersede or validate the earlier run's metrics;
the harness, run conditions, and verdicts are distinct.

At the 2026-11-23 01:39 +0545 host check, pressure was 2 and free swap was
871.88 MiB. No media/load run is safe under the existing preflight; do not
lower the gate or infer a new viewer ceiling. The 5,000-viewer ceiling remains
NOT MEASURABLE from the latest run.

After repository tests at 01:50 +0545, pressure remained 2 and free swap was
378.44 MiB. This lower headroom is another host preflight blocker, not media
evidence; no load was started.

## Architecture

Hami media will use four planes:

1. **Control plane**: signaling, auth, membership epochs, worker assignment,
   health, and evidence ingestion.
2. **Publisher plane**: one receive/ingress worker per publisher; RTP decode
   and packet-cache work stay bounded to that source.
3. **Egress plane**: fixed-size, four-lane egress shards. Each lane owns a
   stable subset of subscribers, a bounded FIFO, and a small worker pool.
   Pion remains responsible for peer ICE/DTLS-SRTP state.
4. **Recovery plane**: PLI/FIR coalescing, NACK deduplication, retransmission
   caps, and keyframe state. Recovery feedback is never on the RTP write loop.

The first implementation is an opt-in egress prototype selected by
`HAMI_SFU_EGRESS_SHARDS`. The default is `0`, preserving the baseline. Values
above `0` enable stable hash membership across bounded FIFO workers. The
prototype is not promoted until its evidence is better than the matched
baseline.

## Reduction rule

Reduce goroutines, queue count, and global locks before adding capacity:

- Publisher ingress creates no subscriber goroutines.
- A shard worker owns a subscriber epoch, not a peer connection.
- Viewer control feedback stays on its Pion RTCP reader.
- Membership changes update shard maps under an epoch, never under the RTP
  hot-path lock.
- No subscriber queue overflow is silently accepted.
- PLI/FIR upstream writes are coalesced by publisher/layer.
- NACK work has both per-viewer and process-wide budgets.

As of 2026-11-22, the implementation adds a process-wide NACK budget of
2,048 pending entries. The router refuses additional recovery jobs once the
budget is full and exports `hami_sfu_nack_process_pending` plus
`hami_sfu_nack_process_dropped_total`. This is a bounded-memory safety
mechanism; it does not change PLI/FIR semantics or per-viewer exact feedback
counts.

## First proof ladder

The initial proof sequence is:

1. 20 publishers x 25 viewers (500) baseline vs 4 shards.
2. 20 publishers x 50 viewers (1,000) matched repeat.
3. 20 publishers x 75 viewers (1,500) frame integrity.
4. Only after the 1,500 rung passes, 20 publishers x 250 viewers (5,000).

Each rung requires matched control/treatment runs, held-out no-change reruns,
and the existing gates:

- all publisher/viewer peers connected;
- only requested tracks received;
- 300 frames per subscriber;
- p95 <= 100 ms for every subscriber;
- p99 <= 150 ms for every subscriber;
- zero RTP queue drops, write errors, or pending latency frames;
- NACK/PLI/FIR counts match the viewer count;
- cleanup verified.

The comparison metric is the complete gate set, not average latency.

## Current prototype result

At 20 publishers x 25 viewers:

- Single-lane control failed viewer 17's NACK retransmission gate.
- Four-lane treatment failed viewer 16's NACK retransmission gate.
- Both runs produced no RTP queue drops.

This matched pair rejects the shard prototype as a proven improvement. It is
retained only as an instrumented experiment, not the default architecture.

At 20 publishers x 25 viewers with shard-per-NACK recovery:

- The 500-viewer rung failed RTCP forwarding at viewer 1.
- Goroutines remained in the existing 18k-class range.
- No complete viewer/latency result was produced.

This rejects shard-per-NACK recovery and prevents it from becoming the default.

## Next splice

The next method is a no-change baseline followed by a recovery-plane isolate:

1. remove synthetic feedback timing from the media hot-path comparison;
2. measure Pion RTP ingress, shard queue wait, shard write duration, RTCP
   receive, and UDP write duration separately;
3. test a PLI/FIR/NACK coalescing change under one source;
4. promote only a change that clears matched 500/1,000/1,500 rungs.

No live 5,000 run is allowed until a smaller matched rung passes twice.

## Neural and layer-selection gate

The current proof path sends one H.264 encoding per publisher track; it does
not negotiate three simulcast layers or select a source encoding per viewer.
RFC 8853 defines simulcast as simultaneous, differently encoded RTP streams
with RTP/SDP identification and signaling. Relabeling one encoding cannot
create those layers.

The current evidence also contains no completed, held-out per-viewer network
traces for training or evaluating a neural estimator. Keep adaptation
deterministic until real layers and reliable feedback/arrival measurements
exist. A future model must first run in shadow mode against that deterministic
baseline on held-out traces from at least two distinct network conditions;
it must preserve hard safety bounds and be rejected if it does not improve
the pre-registered media gates. Do not train from the host-aborted run.

The next HLS experiment is likewise a transport integration, not a neural
optimization: RFC 8216 requires media playlists and valid media segments, while
Pion's `TrackRemote.ReadRTP` supplies RTP packets. The existing synthetic
FFmpeg smoke does not prove Pion ingest. A local bridge must explicitly
handle codec packetization, timestamps, segment/keyframe boundaries, and
cleanup before claiming Hami-to-HLS playback.

Research sources:

- [RFC 8853 — Using Simulcast in SDP and RTP Sessions](https://www.rfc-editor.org/rfc/rfc8853)
- [RFC 8216 — HTTP Live Streaming](https://www.rfc-editor.org/rfc/rfc8216)
- [RFC 8888 — RTCP Feedback for Congestion Control](https://www.rfc-editor.org/rfc/rfc8888)
- [Pion WebRTC v4.2.26 TrackRemote source](https://github.com/pion/webrtc/blob/v4.2.26/track_remote.go)
