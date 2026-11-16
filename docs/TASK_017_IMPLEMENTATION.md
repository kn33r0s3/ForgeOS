# Task 017 — Verification Plan (receiver instrumentation)

**Date:** 2026-11-16. **Status:** Task 017 implementation milestone ACCEPTED. Local compilation and vet are authorized; runtime proof is not yet run. No Cloud, no premium tier, and no commit.
**Scope granted by Niroj (owner-delegated, 09:32 +0545):** receiver-instrumentation seam only.
**Architect:** ChatGPT accepted this corrected scope 09:46 +0545 ("Muse2's corrected scope is accepted. Copilot should update its verification plan before proceeding").

## 1. Baseline (verified 16 Nov 2026)

- Repository: `/Users/nirojpaudyal/Downloads/ForgeOS`, branch `main`, HEAD `46ff1894e4e1d2a7bd818a69096e729128905f16`.
- Five protected files — **untouched, must stay untouched:** `HANDOFF.md`, `STATE.md`, `QUEUE.md`, `docs/CAPABILITY_QUEUE.md`, `DOCKER_COMMANDS.md`. Worktree shows exactly those 5 pending changes.
- **Target file ABSENT from this repo:** `pkg/loadtester/loadtester.go` does not exist anywhere in ForgeOS (full 69,365-entry filename search, 0 matches). It lives in the external `livekit-cli` repository (`github.com/livekit/livekit-cli/v2.19.4`). The ForgeOS harness only *runs* the CLI as the container image `livekit/livekit-cli:v2.19.4`.
- **Go toolchain unavailable on this Mac** (not on PATH; `system.which go` fails). No local `go build` / `go vet` is possible until Go is found or installed, or the build is done inside a container.
## 2. Verified mechanism (independent verification, fresh fetch of pinned sources)

Standard `GetStats()` does **NOT** work in this CLI path — it returns **zero `inbound-rtp` entries**. The direct Pion stats getter is the only mechanism that can yield inbound-rtp data, and only after the CLI registers `stats.NewInterceptor` itself.

- `server-sdk-go` v2.19.0 registers **no stats interceptor by default.** `NewPCTransport` builds its own `interceptor.Registry{}` (`transport.go` L339, L442–444); Pion's `NewAPI` only registers its defaults when no registry is supplied (`api.go` L96–110), so that path is skipped. The SDK's own defaults (`registerDefaultInterceptors`, `transport.go` L173–266) are Pacer, NACK generator/responder, RTCP reports, TWCC sender, LimitSize, RTT, RTTFromXR — **no stats interceptor**.
- `NewPCTransport` adds caller interceptors only if `params.Interceptors != nil`, and registers the SDK defaults alongside them **only if `IncludeDefaultInterceptors` is true** (`transport.go` L351–381). Without that flag, custom interceptors drop the SDK defaults.
- Both PCs get the same params (`createPublisherPCLocked` `engine.go` L855; `createSubscriberPCLocked` `engine.go` L1068), settable via `WithInterceptors` (`room.go` L285) and `WithIncludeDefaultInterceptors` (`room.go` L300).
- The CLI passes **neither**: `LoadTester.Start()` joins with only `lksdk.WithAutoSubscribe(false)` (`livekit-cli/v2.19.4/pkg/loadtester/loadtester.go` L233–243). Both PCs get SDK defaults only — no stats interceptor anywhere.
- Pion v4.2.23 `GetStats` (`peerconnection.go` L5545) collects ICE/DTLS/SCTP/codec entries, then calls `receiver.collectStats(statsCollector, pc.statsGetter)` per receiver (L5647–5653). `RTPReceiver.collectStats` **returns immediately if the getter is nil** — no inbound-rtp entry at all (`rtpreceiver.go` L776–782). The getter comes from a package-level map (`interceptor.go` L177–191, L206) whose **only writer is `ConfigureStatsInterceptorWithOptions`** (L151–167), called only from Pion's own `RegisterDefaultInterceptorsWithOptions` (L126) — which the SDK path never invokes.
- If a getter exists, `populateInboundStats` calls `statsGetter.Get(ssrc)` (`rtpreceiver.go` L868–884) and copies exactly **nine fields**: PacketsReceived, PacketsLost, Jitter, BytesReceived, HeaderBytesReceived, LastPacketReceivedTimestamp, FIRCount, PLICount, NACKCount (L889–927). If `Get(ssrc)` returns nil, the entry is a shell with zero counters.
- A bare `stats.NewInterceptor()` in `WithInterceptors` is **not enough**: the factory's `NewInterceptor(id)` only invokes the `OnNewPeerConnection` callback (`pion/interceptor` v0.1.49 `pkg/stats/interceptor.go` L185–189). With no callback set, the recorder data exists but is unreachable, and Pion's global map stays empty. The CLI must set the callback itself to retain the getters, then use the retained getter directly.
- Copilot independently verified the same conclusions from pinned source (09:45 +0545): `stats.NewInterceptor` receives the Pion peer-connection ID and supplies a per-connection Getter; `GetStats()` emits inbound RTP only when a stats.Getter is installed; freeze count is a rendered-frame metric and unset by this path.
## 3. What the implementation must do (when the location question is settled)

1. Create `stats.NewInterceptor()` (`github.com/pion/interceptor/pkg/stats`) and call `OnNewPeerConnection` to retain `(pcID, stats.Getter)` pairs in its own map.
2. Pass the factory via `lksdk.WithInterceptors([]interceptor.Factory{statsFactory})` **plus** `lksdk.WithIncludeDefaultInterceptors(true)` — otherwise the SDK's NACK/RTCP/TWCC defaults are dropped.
3. Match the getter to the subscriber PC by the `peer-connection` entry ID from its own `GetStats()` call (`peerconnection.go` L5610–5629) against the retained map. Do **not** match by creation order (fragile).
4. Per tick, call `getter.Get(ssrc)` for each subscribed track SSRC and record the nine fields above; treat a nil return as "not yet receiving", not as zero loss.
5. `GetStats()` remains usable only for the non-RTP entries (peer-connection, ICE, transport, codec). It cannot be the inbound-rtp source in this path.
6. **Peer-connection identity proof — VERIFIED at source level in pinned Pion (16 Nov 2026):** the ID passed to `interceptor.Factory.NewInterceptor(id)` IS the same identifier as the peer-connection stats entry ID from `GetStats()` — both are `pc.id` (`PeerConnection-<UnixNano>`, assigned once at `peerconnection.go` L219, never modified). Chain: `API.NewPeerConnection` → `interceptorRegistry.Build(pc.id)` (L274) → `Registry.Build` passes it unchanged to every factory (`registry.go` L29, L42) → `InterceptorFactory.NewInterceptor(id)` fires the callback with it (`pkg/stats/interceptor.go` L141, L185–189). `GetStats()` builds `PeerConnectionStats` with `ID: pc.id` (L5610–5626, L5616) and keys the report by it (L5629). No transformation or mapping is needed — key the retained map directly by the callback's `id` and look it up with the subscriber PC's peer-connection entry ID (shortcut: `subscriberPC.ID()` returns the same string, `peerconnection.go` L1242, L1249). Both PCs receive callbacks from the same factory instance (one callback per PC creation, distinct getters, distinct ids); the publisher's getter is the other map entry and must not be used for subscriber inbound-RTP reads. Caveats: the 'statsId' wording in interceptor comments is stale (no such identifier in `peerconnection.go`); `pc.id` is time-based (UnixNano), not a UUID. The implementation must also handle: callback arrival before or after room join; a missing subscriber PC; a getter not yet available; multiple PeerConnections; reconnection / PeerConnection replacement; and invalidation of old SSRC mappings rather than merging them into a new epoch.
## 4. Corrected scope — freeze counts

**Freeze counts are out of scope for this mechanism.** Neither the direct getter nor `GetStats()` can supply them: the interceptor's `InboundRTPStreamStats` has no freeze/frame fields (`pkg/stats/received_stats.go` L49–65), and `populateInboundStats` copies none. Freeze counts must come from the **existing SampleBuilder drop-callback path** (`ts.dropped`, recorded at `consumeTrack`), kept as a **separate source** from the stats-getter fields — or the requirement must be redefined. Do not report freeze count as zero from this path; report it unavailable from the getter and sourced from SampleBuilder.

## 5. Decided — implementation location (ChatGPT ruling, 09:50 +0545, option (a), strict boundary)

The receiver instrumentation belongs in the **external livekit-cli codebase, not in ForgeOS** — the subscriber PeerConnection whose receiver statistics are needed is created and owned there; ForgeOS only launches the CLI container. Option (b) rejected (no receiver instrumentation in any ForgeOS file; ForgeOS may later consume/record telemetry emitted by the instrumented CLI, a different seam). Option (c) rejected (no parallel load-testing subsystem or vendored copy in ForgeOS).
- Checkout: a **directory outside the ForgeOS repo** (sibling to the ForgeOS checkout, e.g. `/Users/nirojpaudyal/Downloads/livekit-cli/`). The exact absolute path is recorded in the implementation report and confirmed outside ForgeOS. (Correction: an earlier draft gave a `~/workspace/...` path — that is a VM path, not a Mac path, and must not be used.) A separate clone with a small patch is enough for the first implementation; no public fork/publication without separate owner approval.
- Build/versioning: reproducible container build with a Go build stage, separately tagged custom CLI image (example tag `hami-livekit-cli:v2.19.4-task017.1` — NOT built yet). Build record must preserve upstream tag and full commit SHA, patch commit SHA, Go toolchain version, go.mod/go.sum state, Dockerfile revision, image digest, and build/test outputs. Do NOT overwrite `livekit/livekit-cli:v2.19.4`; the harness selects the custom image only through a narrow config change later, original stays the baseline/rollback.
- Compile check: a multi-stage container build is the eventual route if Go stays unavailable on the Mac; a successful image build proves compilation ONLY — not that the interceptor attaches, receives inbound RTP, or attributes it correctly. **Do NOT run the container build yet** — a Docker build is still a Docker command and is prohibited.
- **No clone, patch, build, Docker command, image replacement or runtime test starts under this ruling alone.** The implementation location is decided; execution permissions remain bounded by the stated restrictions. ChatGPT reviews this plan against the ruling before any implementation begins.
## 6. Verification checklist (what the reviewer must see)

The three verification levels are kept separate — evidence from one level is never claimed as proof of another:

- **Level 1 — Static/source verification:** interceptor registration (`WithInterceptors` + `WithIncludeDefaultInterceptors(true)`), SDK defaults verifiably still present (NACK/RTCP/TWCC intact), `OnNewPeerConnection` callback set before the Room joins, subscriber-PC association by `peer-connection` entry ID, track-SID ↔ SSRC mapping and lifecycle logic reviewed in source.
- **Level 2 — Compile verification:** `go build` / `go vet` (or the future multi-stage container build, after build permission is granted). Proves compilation only — never claimed as proof that the interceptor attaches, receives inbound RTP, or attributes it correctly.
- **Level 3 — Runtime proof:** a separately authorised test with actual inbound RTP, proving `getter.Get(ssrc)` returns non-nil, non-zero, **increasing** `PacketsReceived` for the same SSRC and connection epoch. Runtime traffic tests, including an in-process Pion pair, must not be silently added — they need an explicit scope decision first.

Checklist:
- [ ] Stats interceptor factory registered via `WithInterceptors` **and** `WithIncludeDefaultInterceptors(true)` set, with SDK defaults verifiably still present (NACK/RTCP/TWCC intact).
- [ ] `OnNewPeerConnection` callback set **before** the Room joins; retained getter map contains one entry per PC.
- [ ] Subscriber PC identified by matching the `peer-connection` entry ID from its own `GetStats()` call against the retained map — not by order or assumption.
- [ ] (Level 3, separately authorised runtime validation — not required for implementation acceptance) A live run shows `getter.Get(ssrc)` returning **non-nil, non-zero, increasing `PacketsReceived`** for a subscribed track that is actually receiving, with the joined track-SID ↔ SSRC mapping demonstrated.
- [ ] The plan explicitly states `GetStats()` inbound-rtp entries are **not** the source (absent in this path); "code compiles and GetStats returns a report" is not accepted as proof.
- [ ] Freeze counts sourced from SampleBuilder drop events, kept separate; never reported as zero from the getter.
- [ ] Exact repo path and HEAD, initial worktree state, and confirmation the five protected files are untouched.
- [ ] Exact diff, `go build` / `go vet` commands and **complete** results, explicit unresolved issues/limitations.
- [ ] Confirmation that **no Docker commands, live-room, load, capacity, or Cloud tests ran**, and no commit was made.

## 7. Acceptance boundaries

Implementation acceptance, compilation, and runtime validation are three separate milestones, reported separately. The instrumentation must never be labelled runtime-verified merely because it passes source review or compiles.
- **Implementation acceptance (within current scope):** the patch is in the external livekit-cli checkout; interceptor registered correctly with SDK defaults preserved; getter callback and subscriber-PC association implemented; SSRC-to-publication mapping and lifecycle handling implemented; compile verification only when a build method is authorised; exact diff and evidence report delivered. No live run is required for implementation acceptance.
- **Runtime validation (separately authorised):** a test with actual inbound RTP proving `getter.Get(ssrc)` returns non-nil, non-zero, increasing `PacketsReceived` for the same SSRC and connection epoch; track attribution demonstrated; observer overhead measured separately. Runtime RTP proof is NOT a prerequisite for implementation acceptance, but remains an outstanding validation requirement until it is done.
- **Compilation (separately authorised):** the compile route must be selected and authorised separately — an available host Go toolchain, or a pinned multi-stage container build (the intended route if Go remains unavailable, but not currently permitted). Compilation is never claimed from source review alone.
- **Build boundary:** no Docker build, image inspection or creation, and no Go installation or system changes unless separately authorised.
- **Status vocabulary:** report each milestone separately as accepted / not yet done / failed — never collapse them into a single 'pass'.
## 8. Pass criteria (implementation acceptance)

The implementation passes when every checklist item above is demonstrated with evidence (file paths, line numbers, command output), except the Level 3 runtime-proof item, which belongs to the separately authorised runtime-validation milestone. 'It compiles' alone is not a pass. 'GetStats returns a report' alone is not a pass. A live run is not required for implementation acceptance.
## 9. Hard limits (unchanged, plus build boundary)

No edits to the five protected files. No Docker commands. No Docker build, image inspection or creation. No Go installation or system changes unless separately authorised. No live room, load test, capacity test, or Cloud test. No commit. Compile check only (`go build` / `go vet`) once a Go toolchain is available and authorised. Never claim compilation from source review alone.

## 10. Sources (all pinned, public, fetched 2026-11-16)

- `github.com/livekit/server-sdk-go/v2.19.0/transport.go`, `engine.go`, `room.go`, `signalling/interfaces.go`
- `github.com/livekit/livekit-cli/v2.19.4/pkg/loadtester/loadtester.go`
- `github.com/pion/webrtc/v4.2.23/peerconnection.go`, `rtpreceiver.go`, `interceptor.go`, `api.go`, `stats.go`
- `github.com/pion/interceptor/v0.1.49/pkg/stats/interceptor.go`, `pkg/stats/received_stats.go`

## 11. Local-only execution

- **Owner direction (2026-11-16):** Task 017 implementation milestone is ACCEPTED. No LiveKit Cloud and no premium tier.
- **Single local instance:** Everything runs on this Mac: the local LiveKit server via Docker Desktop, local publishers and viewers, local compilation, and local runtime proof. No external runtime services, Cloud, or paid tier.
- **Compilation approach:** Use a Go toolchain installed locally on this Mac. Compile the patched CLI locally with `go build ./...` and run `go vet ./pkg/loadtester/`. Go modules may be fetched from the configured module source when they are not cached; these are build-time dependencies, not runtime services.
- **Runtime proof approach:** Use the local LiveKit server and patched CLI with local publishers and viewers; runtime proof remains separate from compilation and must be obtained locally.
- **Local compile result (2026-11-16):** Go 1.27.4 was installed with Homebrew. `go build ./...` failed because `pkg/portaudio/portaudio.go:11:10` could not find `portaudio.h`, and `pkg/loadtester/loadtester.go:788:29` has an ambiguous `stats.PacketsReceived` selector. `go vet ./pkg/loadtester/` failed on the same ambiguous selector. The build downloaded Go modules; this did not contact LiveKit Cloud or start runtime services.
- **Current boundary:** Local Go installation, build, and vet are authorized. No live-room, load, capacity, or Cloud tests have run in this step. This section supersedes the compilation/toolchain restriction in Section 9 only for local Go installation, build, and vet; all other limits remain.
