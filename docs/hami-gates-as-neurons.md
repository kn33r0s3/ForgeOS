# Hami gates as neurons

Status: direction from Niroj, 20 Nov 2026 ~21:42 +0545. A deterministic
capacity-gate tick now runs inside the existing Forge cycle. This is an
implementation increment, not a fully autonomous or evidence-ingesting neuron
network.

## Core idea

The gate system IS the neural system. No separate neural network is built. Each gate is a neuron, the map is the network, and Hami LLM is the learning rule. Hami work stays on because the network keeps firing on its own; it progresses by itself because progress propagates through the connections; it learns because the LLM reads the network's own states and writes back into it.

## 1. A gate-neuron (on the six primitives — nothing new)

- **Gate = ENTITY** (`entity_type="gate"`). It has criteria (what must be true), a state, and a weight.
- **Inputs = EVIDENCE rows + EVENTs** that bear on it: run results, probe passes, file changes, measurements.
- **State = its evidence state**: UNKNOWN / IN PROGRESS / PROVEN / BLOCKED. This is the neuron's activation level.
- **Weight = confidence from evidence.** One run is weak; a matched pair is stronger; a reproduced result is strongest. Weight is earned, never asserted.
- **Activation = evaluating the gate** against its criteria with current evidence, pass or fail.
- **Output = ACTIONs** (stage the next order, feed Copilot, record a verdict) **+ signals to connected gates** (their inputs change).

## 2. Connections (the network topology is the map)

- Gates connect by **RELATION**: `depends_on` (gate B cannot fire until gate A is PROVEN), `feeds` (gate A's output is gate B's input), `blocks` (gate A BLOCKED holds gate B).
- The map already holds these relations implicitly — the queue order, the handoff chain, the ladder. The work is to make them explicit as RELATION rows, not to invent a new graph store.
- **No new tables. No new primitives.** The six primitives already cover it.

## 3. Firing (always on)

- The network fires on **EVENTs**: a run finishes, a probe passes, a file lands, a measurement arrives. Each event re-evaluates the gates it touches.
- The watch loop (every 2 min) + the heartbeat is the network's clock. It keeps the neurons firing when no new event arrives: each tick re-checks gates whose inputs changed.
- Firing is local: a gate fires only from its own inputs. No central controller decides everything — that is what makes it a neural system instead of a script.

## 4. Learning (Hami LLM is the learning rule)

- The LLM reads the gate graph + evidence. **The map is its input** — the network's own states are its training and feed data, not a separate dataset.
- From what it reads it proposes: **new gates** (a weakness becomes a gate — the weaknesses are our gates), **updated weights** (stronger evidence, higher confidence), **new orders** (the next ACTION).
- Proposals go through the **authorization gate**: nothing that touches the outside world (money, messages, public claims, signing) happens without Niroj. Learning proposes; the gate authorizes.
- The loop closes: gate state → LLM reads → LLM proposes → gates execute → new evidence → gate state changes → LLM reads again. That is self-learning: the system improves from its own experience, in its own terms.

## 5. Self-progress

- Progress propagates: when a gate moves UNKNOWN → PROVEN, every gate that depends on it re-evaluates automatically, and its work starts without anyone pushing. Today's chain already did this by hand (zero-copy BLOCK → seam assessment → audio harness); this design makes it automatic.
- A gate that stays BLOCKED does not stop the network: connected gates route around it (work on what their other inputs allow) and the blocked gate keeps its evidence for the next attempt.

## 6. What this is NOT

- Not a separate neural network library, not a new database, not a new service. Not a copy of anyone else's architecture — generated from Hami's own gates.
- Not unsupervised action: the authorization gate still holds for anything outside.

## Capacity-chain pattern and AI/CNN decision (2026-11-20)

### Evidence that should drive the neurons

- **PROVEN rung:** 20 publishers × 50 subscribers per publisher = 1,000
  subscribers passed the 62-second measurement gate. Peak Go HeapAlloc was
  4,422,783,184 bytes (4.119 GiB); frame-pending count was zero.
- **BLOCKED rung:** 20 × 75 = 1,500 subscribers completed 62 seconds and each
  subscriber passed its individual latency thresholds, but the complete
  measurement failed with 17 pending publisher-frame IDs. Peak HeapAlloc was
  6,339,659,656 bytes (5.904 GiB).
- **New localization lead from the raw subscriber JSONL:** 56 subscribers on
  eight streams missed the same two frame timestamps,
  `271462960` and `271468360`; one subscriber on `stream-0019` missed
  `271457560`. That is 113 missing subscriber-frame matches across only
  three distinct timestamp values. The `FrameClock.Pending()` count is
  exactly 16 (two timestamps in each of eight publisher clocks) + 1 (one
  timestamp in the `stream-0019` clock) = 17. These timestamps also appear
  for complete subscribers on the same streams, so the source did emit them;
  the miss is somewhere in the downstream packet/assembly path for subsets
  of subscribers. The exact point is **not yet proven** because the run did
  not retain per-packet sequence/marker and assembler-transition evidence.
- The raw verdicts and JSONL directories are
  `/tmp/hami-sessionC-20x50-6GiB.json`,
  `/tmp/hami-sessionC-20x75-8GiB.json`,
  `/var/folders/6f/s75p5m_51kx5j4vk6f80k2kr0000gn/T/hami-media-m6h-scale-p20-vpp50-v1000-fps5-1361736729`,
  and `/var/folders/6f/s75p5m_51kx5j4vk6f80k2kr0000gn/T/hami-media-m6h-scale-p20-vpp75-v1500-fps5-3660377157`.
- The Mac has 24 GiB physical RAM. At 23:17, free swap was 1,536.69 MiB
  (below the existing 2,048 MiB scale-test floor), so no further load run was
  started. The highest clean measured rung remains 1,000 subscribers; this is
  not a claim that the Mac's absolute maximum is 1,000.

### Candidate gate network

Use the existing six primitives in
[`models.py`](../backend/app/models.py): `SubstrateEntity` for a gate,
`WorldRelation` for `depends_on` / `feeds` / `blocks`, `WorldEvent` for each
state transition, `Evidence` for the raw run and provenance,
`ForgeCapability` for reusable verification methods, and `Action` for the
next proposed experiment. No new table, primitive, or parallel graph store.

1. `sfu-1000-baseline`: **PROVEN** only for the recorded 20×50 local TEST
   shape, source, settings, and duration; never generalize it to a hardware
   maximum.
2. `sfu-1500-frame-integrity`: **BLOCKED** while `latency_pending_frames` is
   nonzero.
3. `sfu-1500-cause`: **IN PROGRESS** until packet sequence/marker and frame
   assembler transitions account for those exact three timestamps and identify
   where each affected viewer's frame stopped progressing.
4. `sfu-safe-copy-treatment`: **BLOCKED** until a Pion packet-copy reduction
   preserves the existing NACK/PLI/FIR and viewer-retransmission regression.
   The measured Hami ring-expiry candidate had no material matched-run memory
   benefit; the unsafe no-copy/responder-removal probes are not candidates.
5. `sfu-1500-repeat`: **BLOCKED** on frame-cause resolution, a matched
   baseline, and host headroom. It becomes PROVEN only with a clean full gate.
   A higher rung depends on that result and a measured memory budget.

State changes must be computed from explicit gate criteria and evidence. The
LLM may propose a gate or explain a pattern, but cannot turn a probability
into `PROVEN`, bypass a dependency, launch a scale run, or relax a failed
measurement gate. Do not assign numeric confidence weights until repeated
evidence has calibrated what those numbers mean; preserve run count,
environment, provenance, and contradictory results instead.

### CNN and other AI methods

- A 2D image CNN is not indicated by this failure: the failed signal is
  missing RTP-frame matches, not a visual-content classification problem.
  Running video inference in the SFU fast path would compete with forwarding
  for the same Mac CPU and memory without reducing packet fan-out.
- A **small 1D CNN** could later classify short windows of multivariate
  telemetry (`HeapAlloc`, `HeapInuse`, goroutines, scheduler delay, RTP
  packets/loss, queue drops, retransmits, pending frames, and assembler
  transitions). PyTorch's `Conv1d` explicitly operates over sequences shaped
  `(batch, channels, length)`; that makes it a candidate for time-series
  analysis, not evidence that it will improve this system.
- There is currently too little independent labeled data to train or validate
  a CNN: the 20×50 run is a pass and the 20×75 run is one failed condition.
  First collect bounded, provenance-rich run windows; compare a deterministic
  threshold/change-point baseline against any model with whole runs held out.
  Keep the model offline and advisory. Reject it if it does not beat the
  baseline on unseen runs without worsening the resource budget. The existing
  [`pattern_engine.py`](../backend/app/services/pattern_engine.py) is a useful
  prior: cheap, traceable heuristics are preferred over heavy ML without
  evidence of added value.
- The first comparison should be an interpretable threshold/change-point
  detector on frame-pending counts, packet-loss deltas, and queue/resource
  trends. An RNN/Transformer or graph neural network adds parameters and
  compute without solving the missing-label problem; the gate RELATION graph
  is small and should use explicit dependency propagation first. Reinforcement
  learning must not tune a live SFU or capacity climb: there is no validated
  simulator/reward function, and live exploration could degrade real media.
  Reconsider any of these only if held-out run evidence shows the simpler
  method cannot answer a concrete question.
- Optimize the measured resource path, not the word “neural”: current
  20×50/20×75 peaks imply a rough linear 5,000-subscriber projection of
  20.60/19.68 GiB **HeapAlloc**, not RSS or a capacity result. CNN inference
  cannot remove this per-subscriber cost. The next memory experiment remains
  an RTX-safe Pion packet ownership/copy change; do not disable NACK, remove
  the responder, or use `nack.DisableCopy()`.
- For runtime diagnosis, record the existing W3C WebRTC stats (`packetsReceived`,
  `packetsLost`, `jitter`) alongside Hami's exact frame IDs and RTP sequence /
  marker transitions. Use Go CPU, heap, goroutine, block, and trace tools in
  separate runs as appropriate; profiling modes can perturb one another.

Research checked for this plan: [RFC 7667 §3.7](https://www.rfc-editor.org/rfc/rfc7667.html#section-3.7)
describes selective forwarding; the [W3C WebRTC Stats Candidate Recommendation Draft](https://www.w3.org/TR/2025/CRD-webrtc-stats-20250925/)
defines standardized peer-connection statistics; [PyTorch `Conv1d`](https://docs.pytorch.org/docs/2.15/generated/torch.nn.Conv1d.html)
defines the sequence operation; and [Go diagnostics](https://go.dev/doc/diagnostics)
describes profiling and runtime-stat tools. These sources ground the methods,
not Hami's measured capacity.

## 7. First implementation increment

- The existing `world_graph` registry now includes the `gate` entity type,
  `depends_on` relation, and `capacity_gate_result` / `gate_evaluated` event
  types. No table or semantic primitive was added.
- `forge_loop.run_capacity_gate_tick()` ensures the five SFU gates and their
  dependency relations idempotently, then derives each state from local,
  explicitly `TEST` result events. It checks the referenced local artifact's
  SHA-256 and that its JSON metadata agrees with the event. A failed result or
  contradictory run blocks the gate; absent results remain `UNKNOWN`.
- `forge_loop.run_cycle()` invokes the tick through its existing orchestration
  seam. The tick may create only internal `research` ACTION proposals with
  `PROPOSED` status and a `TEST` scope. It never starts an ACTION, launches a
  load run, contacts a person, or spends money. A prerequisite transition
  stages a dependent proposal only when every prerequisite is proven.
- This is cycle-driven, not a two-minute watch loop. The Go runner does not
  yet emit `capacity_gate_result` events, and the tick does not yet interpret
  every SFU proof acceptance field. Therefore the persisted live gate states
  remain unknown until a validated result adapter is connected; unit-test
  fixtures prove only the transition logic.
- The deterministic mechanism is the baseline. The Hami LLM remains advisory,
  and CNN/RNN/Transformer/GNN/RL inference remains deferred until there are
  enough independent, labeled runs for held-out evaluation.

## Acceptance

The isolated regression test verifies idempotent gate/relation creation,
UNKNOWN → PROVEN and contradictory-evidence BLOCKED transitions, and one safe
PROPOSED action per newly eligible dependency. This proves the deterministic
mechanism only. Production evidence ingestion, scheduler-driven progression,
and automatic execution are not established; no capacity gate is claimed
PROVEN from this code change.

## 8. The less-error-more-success gate (Hami LLM training, 21 Nov 2026)

Direction from Niroj, 21 Nov 2026 01:06 +0545: train Hami LLM on all the
failure logs and reasons and successes, starting with hami-media, so it
knows what approaches work in coding. The gate the LLM always follows is:
**prefer the approach with the lowest error / highest success from the
logged evidence, and never repeat an approach that failed before unless the
reason changed.** That is the path to greater successes and less failures.

### Definition (criteria)

- **Evidence**: `failure-success-v1.jsonl` in the SFT project (17 rows as
  of 21 Nov 2026: 12 FAIL / 5 SUCCESS; 12 hami-media / 5 hami-ai). Each
  row is one logged (situation, approach tried, outcome, reason, fix /
  what worked) pair with provenance (source file + date + the actual
  numbers). A reason that is UNKNOWN is recorded as unknown — never
  guessed, never invented.
- **Firing**: when the LLM proposes a coding approach for a situation that
  matches a logged situation, the gate fires on the failure/success
  evidence. The proposal must name the approach the logs prove worked;
  proposing a logged-FAILED approach for the same situation, with the same
  reason, is a gate failure.
- **Criteria**: (a) the proposed approach is the one with the best logged
  outcome for that situation; (b) no approach is repeated after a FAIL
  unless the recorded reason has changed; (c) every claim cites its log
  row (source + date + numbers).

### Evidence state

- The dataset is the evidence state. It grows every cycle: new failures
  and successes from the run logs are harvested into it (the 021 20x5000
  budget-cancel, the stale-binary failure, the loop `timeout` fix, and the
  cycle-2 iter-125 loss spike were added 21 Nov 2026).
- The loop folds the dataset into every next cycle's training data
  (`continuous_upgrade.py`: `failure_success_training_rows`, wired into
  `combine_training()`), so the model trains on the evidence, not just on
  Nepali text.
- The eval probes the gate directly: `FAILURE_SUCCESS_PROBES` in
  `continuous_upgrade.py` give the model a coding situation from the logs
  and check it picks the approach that WORKED, not the one that FAILED
  (NACK 500ms, subscriber-map revert, cost-3000 heap, identity guard).
  Probe results are recorded per cycle in the candidate eval, as a
  diagnostic — the probe is the gate's activation check, and a probe that
  picks the failed approach is the gate failing in the open.

### How it fires, and what it does not do

- Firing is advisory to the model and recorded in the eval: it does not
  by itself block a promotion (the promotion bar is token-F1 + gates +
  identity), because the probe is a first signal on four situations, not a
  held-out benchmark. If the probe keeps failing, the dataset and the
  probe set grow until the lesson is learned.
- The gate never acts on the outside world: it only learns. Money,
  messages, public claims, and signing still go through the authorization
  gate (Niroj).
