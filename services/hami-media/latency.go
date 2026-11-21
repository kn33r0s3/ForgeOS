// Hami media latency harness — M1-H proof support.
//
// Measures per-subscriber capture-to-render (or receive) latency for
// Hami's own media engine. Drop latency.go + latency_test.go into
// services/hami-media/ (package main, standard library only, no new
// dependencies) and wire the three call sites in main.go — see
// INTEGRATION.md.
//
// Honest labelling is the point: without a real render callback the
// result is "receive" latency, NOT "capture-to-render". The mode is
// carried in every record and in the summary so it can never be misread.
//
// Metric: L = T_event - T_capture, same machine, monotonic clock.
// Video frame identity is its RTP timestamp (fragments of a frame share it).
// Audio measurements use AudioFrameClock keyed by the audio RTP timestamp.
// The publisher stamps each frame at capture; the subscriber matches the
// event to the same identity.
//
// Acceptance (Task 017 metric plan): p95 <= 100 ms (primary), p99 <=
// 150 ms (guardrail), >= 300 frames per subscriber, >= 60 s, EVERY
// subscriber passes independently. No averaging — p95 is the gate.
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"sync"
	"time"
)

// Acceptance thresholds for the M1-H proof.
const (
	LatencyP95Max = 100 * time.Millisecond // primary gate
	LatencyP99Max = 150 * time.Millisecond // guardrail
	MinFrames     = 300                    // >= 300 rendered frames per subscriber
	MinDuration   = 60 * time.Second       // >= 60 s measurement
)

// Modes. ModeRender requires a real decode + render callback.
// ModeReceive is frame receipt only and must never be reported as
// capture-to-render latency.
const (
	ModeRender  = "capture-to-render"
	ModeReceive = "receive"
)

type captureClockState struct {
	mu                 sync.Mutex
	captures           map[uint64]time.Time
	remainingConsumers map[uint64]int
	expectedConsumers  int
	capturesStarted    bool
}

func newCaptureClockState() captureClockState {
	return captureClockState{
		captures:           make(map[uint64]time.Time),
		remainingConsumers: make(map[uint64]int),
		expectedConsumers:  1,
	}
}

// FrameClock records capture instants for video frames. One clock per
// publisher, shared with its subscribers (same process, same monotonic clock).
type FrameClock struct {
	captureClockState
}

// AudioFrameClock records capture instants for audio frames. It is a distinct
// type so audio measurements cannot accidentally use the video clock.
type AudioFrameClock struct {
	captureClockState
}

// NewFrameClock returns an empty video frame clock.
func NewFrameClock() *FrameClock {
	return &FrameClock{captureClockState: newCaptureClockState()}
}

// NewAudioFrameClock returns an empty audio frame clock.
func NewAudioFrameClock() *AudioFrameClock {
	return &AudioFrameClock{captureClockState: newCaptureClockState()}
}

// SetExpectedConsumers configures how many subscriber recorders share each
// capture. It must be called before the first frame is captured.
func (c *captureClockState) SetExpectedConsumers(consumers int) error {
	if consumers < 1 {
		return fmt.Errorf("expected consumers must be positive")
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.capturesStarted {
		return fmt.Errorf("cannot change expected consumers after capture begins")
	}
	c.expectedConsumers = consumers
	return nil
}

// Capture records the capture instant for a frame. t must come from the
// same machine's monotonic clock as the render/receive instant.
func (c *captureClockState) Capture(frameID uint64, t time.Time) {
	c.mu.Lock()
	c.captures[frameID] = t
	c.remainingConsumers[frameID] = c.expectedConsumers
	c.capturesStarted = true
	c.mu.Unlock()
}

// CaptureNow stamps a frame with the current time.
func (c *captureClockState) CaptureNow(frameID uint64) {
	c.Capture(frameID, time.Now())
}

// Lookup returns the capture instant for a frame, if it was recorded.
func (c *captureClockState) Lookup(frameID uint64) (time.Time, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	t, ok := c.captures[frameID]
	return t, ok
}

// Forget explicitly drops a frame's capture record.
func (c *captureClockState) Forget(frameID uint64) {
	c.mu.Lock()
	delete(c.captures, frameID)
	delete(c.remainingConsumers, frameID)
	c.mu.Unlock()
}

// consume releases a capture after all expected subscribers match it.
func (c *captureClockState) consume(frameID uint64) {
	c.mu.Lock()
	defer c.mu.Unlock()
	remaining := c.remainingConsumers[frameID]
	if remaining <= 1 {
		delete(c.captures, frameID)
		delete(c.remainingConsumers, frameID)
		return
	}
	c.remainingConsumers[frameID] = remaining - 1
}

// Pending returns how many captures still await one or more subscriber
// matches. A nonzero value is a frame-delivery loss signal for the proof.
func (c *captureClockState) Pending() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.captures)
}

func (c *captureClockState) PendingDeliveries() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	pending := 0
	for _, remaining := range c.remainingConsumers {
		pending += remaining
	}
	return pending
}

// Sample is one matched frame: capture instant, event instant, latency.
type Sample struct {
	FrameID uint64        `json:"frame_id"`
	Capture time.Time     `json:"capture"`
	Event   time.Time     `json:"event"`
	Latency time.Duration `json:"latency_ns"`
	Mode    string        `json:"mode"`
}

// LatencyRecorder collects matched samples for one subscriber.
type LatencyRecorder struct {
	mu        sync.Mutex
	mode      string
	samples   []time.Duration
	unmatched int // events with no capture record (frame never stamped)
	first     time.Time
	last      time.Time
	jsonl     []Sample // full records, for the evidence file
}

// NewLatencyRecorder returns a recorder for one subscriber. Any mode
// other than ModeRender falls back to ModeReceive — never silently
// claim capture-to-render.
func NewLatencyRecorder(mode string) *LatencyRecorder {
	if mode != ModeRender {
		mode = ModeReceive
	}
	return &LatencyRecorder{mode: mode}
}

// Mode returns the recorder's honest mode label.
func (r *LatencyRecorder) Mode() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.mode
}

// Record matches an event (render or receive) to its capture instant and
// stores the latency. Returns false when the frame was never stamped.
func (r *LatencyRecorder) Record(frameID uint64, clock *FrameClock, tEvent time.Time) bool {
	return r.record(frameID, clock, tEvent)
}

// RecordAudio matches a rendered audio frame to an audio capture instant.
func (r *LatencyRecorder) RecordAudio(frameID uint64, clock *AudioFrameClock, tEvent time.Time) bool {
	return r.record(frameID, clock, tEvent)
}

func (r *LatencyRecorder) record(frameID uint64, clock interface {
	Lookup(uint64) (time.Time, bool)
	consume(uint64)
}, tEvent time.Time) bool {
	cap, ok := clock.Lookup(frameID)
	if !ok {
		r.mu.Lock()
		r.unmatched++
		r.mu.Unlock()
		return false
	}
	lat := tEvent.Sub(cap)
	r.mu.Lock()
	r.samples = append(r.samples, lat)
	r.jsonl = append(r.jsonl, Sample{FrameID: frameID, Capture: cap, Event: tEvent, Latency: lat, Mode: r.mode})
	if r.first.IsZero() || tEvent.Before(r.first) {
		r.first = tEvent
	}
	if tEvent.After(r.last) {
		r.last = tEvent
	}
	r.mu.Unlock()
	clock.consume(frameID)
	return true
}

// RecordNow is Record with tEvent = time.Now().
func (r *LatencyRecorder) RecordNow(frameID uint64, clock *FrameClock) bool {
	return r.Record(frameID, clock, time.Now())
}

// RecordAudioNow is RecordAudio with tEvent = time.Now().
func (r *LatencyRecorder) RecordAudioNow(frameID uint64, clock *AudioFrameClock) bool {
	return r.RecordAudio(frameID, clock, time.Now())
}

// Summary is the per-subscriber proof result.
type Summary struct {
	Mode         string        `json:"mode"`
	Frames       int           `json:"frames"`
	Unmatched    int           `json:"unmatched"`
	Duration     time.Duration `json:"duration_ns"`
	P50          time.Duration `json:"p50_ns"`
	P95          time.Duration `json:"p95_ns"`
	P99          time.Duration `json:"p99_ns"`
	Max          time.Duration `json:"max_ns"`
	PassP95      bool          `json:"pass_p95"`
	PassP99      bool          `json:"pass_p99"`
	PassFrames   bool          `json:"pass_frames"`
	PassDuration bool          `json:"pass_duration"`
	Pass         bool          `json:"pass"`
}

// Percentile returns the p-th percentile (0 < p <= 100) by the
// nearest-rank method. Returns 0 for an empty slice.
func Percentile(durs []time.Duration, p float64) time.Duration {
	if len(durs) == 0 {
		return 0
	}
	sorted := make([]time.Duration, len(durs))
	copy(sorted, durs)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i] < sorted[j] })
	rank := int(math.Ceil(p / 100.0 * float64(len(sorted))))
	if rank < 1 {
		rank = 1
	}
	if rank > len(sorted) {
		rank = len(sorted)
	}
	return sorted[rank-1]
}

// Summary computes the proof result. Pass requires every threshold.
func (r *LatencyRecorder) Summary() Summary {
	r.mu.Lock()
	defer r.mu.Unlock()
	s := Summary{Mode: r.mode, Frames: len(r.samples), Unmatched: r.unmatched}
	if len(r.samples) == 0 {
		return s
	}
	s.P50 = Percentile(r.samples, 50)
	s.P95 = Percentile(r.samples, 95)
	s.P99 = Percentile(r.samples, 99)
	max := r.samples[0]
	for _, d := range r.samples {
		if d > max {
			max = d
		}
	}
	s.Max = max
	if !r.first.IsZero() && !r.last.IsZero() {
		s.Duration = r.last.Sub(r.first)
	}
	s.PassP95 = s.P95 <= LatencyP95Max
	s.PassP99 = s.P99 <= LatencyP99Max
	s.PassFrames = s.Frames >= MinFrames
	s.PassDuration = s.Duration >= MinDuration
	s.Pass = s.PassP95 && s.PassP99 && s.PassFrames && s.PassDuration
	return s
}

// SamplesJSONL returns one JSON object per matched sample, for the
// evidence file (one file per subscriber).
func (r *LatencyRecorder) SamplesJSONL() ([]byte, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	var out []byte
	for _, s := range r.jsonl {
		b, err := json.Marshal(s)
		if err != nil {
			return nil, err
		}
		out = append(out, b...)
		out = append(out, '\n')
	}
	return out, nil
}

// String renders the result in one human-readable block.
func (s Summary) String() string {
	return fmt.Sprintf("mode=%s frames=%d unmatched=%d duration=%s p50=%s p95=%s p99=%s max=%s pass=%v (p95<=100ms:%v p99<=150ms:%v frames>=300:%v duration>=60s:%v)",
		s.Mode, s.Frames, s.Unmatched, s.Duration, s.P50, s.P95, s.P99, s.Max, s.Pass, s.PassP95, s.PassP99, s.PassFrames, s.PassDuration)
}
