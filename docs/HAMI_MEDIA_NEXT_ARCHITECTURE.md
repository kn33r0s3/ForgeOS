# Hami Media Next Architecture

Status: experimental direction, 2026-11-21.

## Failure evidence

The latest 20-publisher / 5,000-viewer run completed with:

- 5,000/5,000 viewer peers connected.
- 4,691/5,000 viewers passed every latency gate.
- 309/5,000 failed only the p99 <= 150 ms guardrail.
- 0 RTP queue drops, 0 intentional sheds, and 0 RTP write errors.
- Peak Go HeapAlloc 2.423 GiB and peak 175,796 goroutines.

This failure pattern shows that repeating the 5,000-viewer shape cannot
discover a transport cause. The next work must isolate hot-path behavior at
bounded scales and preserve the existing control plane.

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
