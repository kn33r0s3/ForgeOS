# Layered packet architecture — hami-sfu

Built 22 Nov 2026 from Niroj's idea: cut CPU / infrastructure cost by
dividing media packets into layers, sending them layer by layer, one by
one, to users, then clearing each layer after it is sent — nothing held,
nothing buffered.

## 0. What the repo already had (surveyed, not assumed)

**hami-sfu/main.go** (13,217 B, the live SFU) — `track.forward()` reads one
RTP packet from the publisher and writes the *same* `*rtp.Packet` to every
subscriber's `TrackLocalStaticRTP` under one `RLock`. No queue, no cache,
no division: every subscriber gets every packet (an audio-only listener
still gets video packets if it has a video binding), and one slow
subscriber's `WriteRTP` blocks all the others under the lock. Pion's
interceptor holds 256 packets per track internally for NACK retransmits
(`nack.ResponderSize(256)`).

**services/hami-media/main.go** (462,529 B, 13,474 lines) — the heavy media
path. `sfuRouter.forwardTrack` does `rememberPacket` (a 512-packet ring
cache per track, `sfuNACKHistoryPackets = 512`, for NACK retransmits) and
then `enqueueRTP` into each subscription's 64-deep `rtpQueue chan
queuedRTP` (`sfuRTPQueueSize = 64`), or into egress shards. `enqueueRTP`
copies the RTP header (payload shared). The audio rung mixes Opus RTP
(`audioRTPMixer`). H264 keyframe detection already exists there
(`isH264IDRStart`, `isH264RecoveryConfig`) — the layer classifier ports
the same algorithm, it does not reinvent it.

**Media reality, stated plainly:** the product is live-audio-first (50
speakers, 10,000 listeners). The packets flowing are Opus audio RTP and
H264 video RTP where video exists. Layering applies to the RTP packets
already flowing — no video code was invented. There is no GPU work in this
path at all: an SFU forwards RTP without decoding or encoding, so the
saving is CPU (fewer copies / writes), memory (nothing retained) and
infrastructure (less fan-out work per packet), not GPU.

## 1. The layer scheme

One packet belongs to exactly one layer. Packets stay in arrival /
sequence order — reordering across layers would break RTP playback, so
"layer one by one" means *classification + masked fan-out + clear*, not
reordering.

| Layer | Name  | What is in it | Who needs it |
|-------|-------|---------------|--------------|
| 0 | BASE  | All audio packets; video parameter sets (H264 SPS/PPS, NAL 7/8) | Every subscriber |
| 1 | KEY   | Video keyframes (H264 IDR start; VP8 keyframe bit) | Video subscribers, to (re)sync |
| 2 | DELTA | Video non-keyframes | Video subscribers only; first to drop under load |

Classification (`classifyPacket`, layers.go) takes the track codec
(`audio/opus`, `video/H264`, `video/VP8`, …) plus the payload:
- audio (any audio codec) → layer 0.
- video/H264 → parameter sets layer 0, IDR start layer 1, else layer 2.
- video/VP8 → keyframe bit clear layer 1, else layer 2.
- any other video codec → layer 2 (safe default: droppable, never base).

## 2. How a layer reaches a user, and when it is cleared

Each subscriber binding carries a **layer mask** (`layerMask`, a bitmask).
Default: all layers. Audio-only listeners: base layer only
(`layerMaskAudio`). A low-bandwidth video mode — keyframes only, no delta
— is `layerMaskBase | layerMaskKey` and is one `setSubLayerMask` call away.

`track.forward()` is now the layered path (`forwardLayered`):

1. Read one RTP packet from the publisher.
2. Classify it into its layer.
3. Snapshot the subscriber list (short read-lock, then the lock is
   released — writes never happen under the track lock any more).
4. `layerFanout`: write the packet to exactly the subscribers whose mask
   includes that layer. First write error is recorded; sending continues
   to the remaining subscribers.
5. `clearPacket`: `Payload = nil`, `Raw = nil`, header zeroed. The
   forwarder retains **zero bytes** between packets. The packet is dead
   after the pass — Pion copies what it needs during `WriteRTP`, so
   clearing after the pass is safe.

`fanoutDirect` keeps the pre-layer behaviour (one packet to every
subscriber, no classification, no clear) as the benchmark before-state.
Nothing else in the media path was rewritten: `track`, `subscriber`,
`room`, `negotiate`, `handlePublish`, `handleSubscribe` are unchanged
except the small mask bookkeeping in `addSub`/`removeSub`.

## 3. What the reduction is, measured — not estimated

Measured in `layers_test.go` (benchmarks + tests, run on the VM against
the exact Mac bytes; see §5 for the numbers):

- **Fewer writes per send.** With a realistic mix (10 subscribers: 5
  full, 3 keyframes-only, 2 audio-only; packets 1 audio + 9 video per
  group with 1 keyframe), the layered fan-out makes measurably fewer
  `WriteRTP` calls than the direct fan-out over the same packets and
  subscribers. Delta packets — ~90% of video packets — skip the 5
  subscribers that do not need them.
- **Zero retained bytes.** After every packet the layered sender holds
  0 bytes (`clearPacket` + a test that asserts the packet is dead after
  the pass). Before-state, from the repo's own heavy forwarder
  (`services/hami-media`): the per-track 512-packet NACK cache plus the
  64-deep queue per subscription — measured on the VM by filling the
  cache (see the benchmark section of the test log).
- **Lock hold.** The direct path holds the track read-lock across *all*
  subscriber writes; the layered path snapshots under a short lock and
  writes outside it. A slow subscriber still delays the next packet
  (single-goroutine sequential writes — see gaps), but it no longer
  blocks the subscriber list itself.

What layering does **not** do by default: if every subscriber keeps the
full mask, the layered path sends exactly like the direct path plus a
small classification cost (measured in the benchmark). The saving is
realised when subscribers pick fewer layers. That is the honest deal —
the mechanism is proven here; the saving follows the subscription.

## 4. Files

- `hami-sfu/layers.go` — the layer module (classification, masks,
  `layerFanout`, `clearPacket`, track wiring). New file.
- `hami-sfu/layers_test.go` — classification, order, clear-after-send,
  per-layer subscription completeness, before/after benchmarks. New file.
- `hami-sfu/main.go` — only the track mask bookkeeping + `forward()`
  now calls the layered path. No other behaviour changed.
- `hami-sfu/LAYERS.md` — this file.

## 5. Test + measurement results

Measured 22 Nov 2026 on the VM against the exact Mac bytes (Go 1.24.0).
All numbers below are from the runs, not targets.

- hami-sfu: `gofmt` clean, `go vet` + `go build` pass. `go test
  -count=1 ./...`: **7 test functions pass, 0 fail** (TestClassifyPacket
  with 17 subtests, plus fan-out, clear, error-continuation, snapshot and
  write-reduction tests).
- hami-media (code untouched): `go vet` + `go build` pass.
  `go test -count=1 ./...` (62 s): **58 pass / 5 fail, out of 63 tests**.
  All 5 failures are ICE/UDP loopback tests (local pair, SFU route,
  cascade, mux counting, datagram counting) failing because this VM
  sandbox blocks UDP entirely — proven by a direct probe (`python3`
  UDP sendto to 127.0.0.1 → `PermissionError: Operation not permitted`).
  They are environment failures, not code failures, and need the Mac's
  loopback to run. Every non-network test passes.
- Benchmark direct vs layered fan-out (same 10 subscribers, same 10
  packets per group; 5 full, 3 keyframes-only, 2 audio-only):
  **WriteRTP calls 100 → 58, 42.0% fewer** (test-asserted exact counts);
  fan-out cost **118.6 ns/op direct vs 119.9 ns/op layered** — the same
  cost, 152 B/op and 2 allocs/op each (the allocs are the fresh packet
  per iteration, which production also does per ReadRTP).
  Classification costs **23.26 ns/op, 0 B/op, 0 allocs/op**.
- Retained bytes: layered sender **0 B after every packet**
  (test-asserted: Payload nil, Raw nil, header zeroed). Before-state,
  measured on the same VM by filling the current hami-media forwarder:
  NACK cache holds **512 packets / 614,400 payload bytes per track**
  (512 x 1200 B ring, full), plus a **64-deep queue per subscription**;
  existing `BenchmarkCachedPackets` runs 259.2 ns/op for a cache lookup.

## 6. Honest gaps — what this does NOT prove

- **No production traffic proof.** Proven on loopback / fake sinks only.
  10,000-listener behaviour is extrapolated, not measured.
- **hami-media router is NOT layered yet.** Its 512-packet cache +
  64-deep queues are still the live heavy path. Wiring layers in there
  is the next step: classify in `forwardTrack` before `rememberPacket` /
  `enqueueRTP`, keep the cache for layers 0–1 only, and let layer-2
  packets bypass the cache. That change needs its own run of the
  hami-media loopback suite — it was not folded into this task.
- **A slow subscriber still delays the next packet.** The layered sender
  writes sequentially in one goroutine; it holds no queue, so it cannot
  isolate a stalled subscriber the way per-subscriber queues do. That
  isolation costs retained packets — the trade-off is explicit.
- **The audio mixer path (`audioRTPMixer` in hami-media) is untouched.**
  Mixed Opus output is all layer 0 by construction.
- **No subscriber has picked fewer layers yet.** The saving needs the
  low-bandwidth / audio-only modes to actually be selected (one
  `setSubLayerMask` call each). Until then the default path behaves like
  the direct path plus classification cost.
