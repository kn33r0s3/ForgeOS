package main

import (
	"encoding/json"
	"sync"
	"testing"
	"time"
)

func TestPercentile(t *testing.T) {
	durs := []time.Duration{
		10 * time.Millisecond, 20 * time.Millisecond, 30 * time.Millisecond,
		40 * time.Millisecond, 50 * time.Millisecond, 60 * time.Millisecond,
		70 * time.Millisecond, 80 * time.Millisecond, 90 * time.Millisecond,
		100 * time.Millisecond,
	}
	// nearest-rank, N=10: p50 rank 5 -> 50ms, p95 rank 10 -> 100ms.
	if got := Percentile(durs, 50); got != 50*time.Millisecond {
		t.Fatalf("p50 = %v, want 50ms", got)
	}
	if got := Percentile(durs, 95); got != 100*time.Millisecond {
		t.Fatalf("p95 = %v, want 100ms", got)
	}
	if got := Percentile(durs, 99); got != 100*time.Millisecond {
		t.Fatalf("p99 = %v, want 100ms", got)
	}
	if got := Percentile(durs, 100); got != 100*time.Millisecond {
		t.Fatalf("p100 = %v, want 100ms", got)
	}
	if got := Percentile(nil, 95); got != 0 {
		t.Fatalf("empty percentile = %v, want 0", got)
	}
	// Unsorted input must not change the result.
	shuffled := []time.Duration{
		100 * time.Millisecond, 10 * time.Millisecond, 50 * time.Millisecond,
		90 * time.Millisecond, 20 * time.Millisecond, 60 * time.Millisecond,
		30 * time.Millisecond, 70 * time.Millisecond, 40 * time.Millisecond,
		80 * time.Millisecond,
	}
	if got := Percentile(shuffled, 50); got != 50*time.Millisecond {
		t.Fatalf("shuffled p50 = %v, want 50ms", got)
	}
}

func TestFrameClock(t *testing.T) {
	c := NewFrameClock()
	now := time.Now()
	c.Capture(7, now)
	got, ok := c.Lookup(7)
	if !ok || !got.Equal(now) {
		t.Fatalf("lookup(7) = %v, %v, want %v, true", got, ok, now)
	}
	if _, ok := c.Lookup(8); ok {
		t.Fatalf("lookup(8) should miss")
	}
	if n := c.Pending(); n != 1 {
		t.Fatalf("pending = %d, want 1", n)
	}
	c.Forget(7)
	if _, ok := c.Lookup(7); ok {
		t.Fatalf("lookup(7) should miss after Forget")
	}
	if n := c.Pending(); n != 0 {
		t.Fatalf("pending = %d, want 0", n)
	}
}

func TestFrameClockSharedSubscribers(t *testing.T) {
	c := NewFrameClock()
	if err := c.SetExpectedConsumers(2); err != nil {
		t.Fatal(err)
	}
	capturedAt := time.Now()
	c.Capture(17, capturedAt)

	first := NewLatencyRecorder(ModeReceive)
	if !first.Record(17, c, capturedAt.Add(10*time.Millisecond)) {
		t.Fatal("first subscriber should match the frame")
	}
	if _, ok := c.Lookup(17); !ok || c.Pending() != 1 {
		t.Fatal("capture should remain until the second subscriber matches")
	}

	second := NewLatencyRecorder(ModeReceive)
	if !second.Record(17, c, capturedAt.Add(20*time.Millisecond)) {
		t.Fatal("second subscriber should match the shared frame")
	}
	if _, ok := c.Lookup(17); ok || c.Pending() != 0 {
		t.Fatal("capture should be released after all subscribers match")
	}
	if err := c.SetExpectedConsumers(1); err == nil {
		t.Fatal("expected consumer count must not change after capture has started")
	}
}

func TestRecorderModeFallback(t *testing.T) {
	if r := NewLatencyRecorder(ModeRender); r.Mode() != ModeRender {
		t.Fatalf("mode = %q, want %q", r.Mode(), ModeRender)
	}
	if r := NewLatencyRecorder(ModeReceive); r.Mode() != ModeReceive {
		t.Fatalf("mode = %q, want %q", r.Mode(), ModeReceive)
	}
	// Any unknown mode must fall back to receive, never claim render.
	if r := NewLatencyRecorder("capture-to-render-latency"); r.Mode() != ModeReceive {
		t.Fatalf("unknown mode = %q, want %q", r.Mode(), ModeReceive)
	}
}

func TestRecorderMatchedAndUnmatched(t *testing.T) {
	c := NewFrameClock()
	r := NewLatencyRecorder(ModeReceive)
	base := time.Now()
	c.Capture(1, base)
	if !r.Record(1, c, base.Add(72*time.Millisecond)) {
		t.Fatalf("Record(1) should match")
	}
	if r.Record(2, c, base.Add(80*time.Millisecond)) {
		t.Fatalf("Record(2) should miss (never stamped)")
	}
	s := r.Summary()
	if s.Frames != 1 || s.Unmatched != 1 {
		t.Fatalf("frames=%d unmatched=%d, want 1, 1", s.Frames, s.Unmatched)
	}
	if s.P95 != 72*time.Millisecond {
		t.Fatalf("p95 = %v, want 72ms", s.P95)
	}
}

// simulate runs a synthetic publisher/subscriber pair: frames stamped at
// the given interval for the given span, each event delayed by lat().
// No sleeping — timestamps are synthesized.
func simulate(t *testing.T, mode string, interval time.Duration, span time.Duration, lat func(i int) time.Duration) Summary {
	t.Helper()
	c := NewFrameClock()
	r := NewLatencyRecorder(mode)
	base := time.Now()
	n := int(span / interval)
	for i := 0; i < n; i++ {
		id := uint64(i + 1)
		cap := base.Add(time.Duration(i) * interval)
		c.Capture(id, cap)
		if !r.Record(id, c, cap.Add(lat(i))) {
			t.Fatalf("frame %d should match", id)
		}
	}
	return r.Summary()
}

func TestSimulatedPass(t *testing.T) {
	// ~16.7 fps (like the M0-H pair: 50 frames / 3 s) for 65 s, ~72 ms
	// latency with jitter and an occasional 90 ms spike. Must pass.
	s := simulate(t, ModeReceive, 60*time.Millisecond, 65*time.Second, func(i int) time.Duration {
		switch i % 10 {
		case 0:
			return 90 * time.Millisecond
		case 5:
			return 75 * time.Millisecond
		default:
			return 70 * time.Millisecond
		}
	})
	if !s.Pass {
		t.Fatalf("simulated good run should pass: %s", s)
	}
	if s.Frames < MinFrames {
		t.Fatalf("frames = %d, want >= %d", s.Frames, MinFrames)
	}
	if s.P95 > LatencyP95Max {
		t.Fatalf("p95 = %v, want <= %v", s.P95, LatencyP95Max)
	}
}

func TestSimulatedFailHighLatency(t *testing.T) {
	s := simulate(t, ModeReceive, 60*time.Millisecond, 65*time.Second, func(i int) time.Duration {
		return 120 * time.Millisecond
	})
	if s.Pass {
		t.Fatalf("120 ms run should fail: %s", s)
	}
	if s.PassP95 {
		t.Fatalf("p95 gate should fail at 120 ms")
	}
}

func TestSimulatedFailTooFewFrames(t *testing.T) {
	s := simulate(t, ModeReceive, 60*time.Millisecond, 6*time.Second, func(i int) time.Duration {
		return 70 * time.Millisecond
	})
	if s.Pass {
		t.Fatalf("6 s run should fail: %s", s)
	}
	if s.PassFrames {
		t.Fatalf("frames gate should fail at %d frames", s.Frames)
	}
}

func TestSimulatedFailTooShort(t *testing.T) {
	// 400 frames but only 10 s of them — frames pass, duration fails.
	s := simulate(t, ModeReceive, 25*time.Millisecond, 10*time.Second, func(i int) time.Duration {
		return 70 * time.Millisecond
	})
	if s.Pass {
		t.Fatalf("10 s run should fail: %s", s)
	}
	if s.PassDuration {
		t.Fatalf("duration gate should fail at %v", s.Duration)
	}
	if !s.PassFrames {
		t.Fatalf("frames gate should pass at %d frames", s.Frames)
	}
}

func TestSamplesJSONL(t *testing.T) {
	c := NewFrameClock()
	r := NewLatencyRecorder(ModeRender)
	base := time.Now()
	for i := 1; i <= 3; i++ {
		id := uint64(i)
		c.Capture(id, base.Add(time.Duration(i)*time.Second))
		r.Record(id, c, base.Add(time.Duration(i)*time.Second+72*time.Millisecond))
	}
	b, err := r.SamplesJSONL()
	if err != nil {
		t.Fatalf("SamplesJSONL: %v", err)
	}
	var rows []Sample
	for _, line := range splitLines(b) {
		var s Sample
		if err := json.Unmarshal(line, &s); err != nil {
			t.Fatalf("bad JSONL line %q: %v", line, err)
		}
		if s.Mode != ModeRender {
			t.Fatalf("sample mode = %q, want %q", s.Mode, ModeRender)
		}
		rows = append(rows, s)
	}
	if len(rows) != 3 {
		t.Fatalf("rows = %d, want 3", len(rows))
	}
}

func splitLines(b []byte) [][]byte {
	var out [][]byte
	start := 0
	for i, ch := range b {
		if ch == '\n' {
			out = append(out, b[start:i])
			start = i + 1
		}
	}
	return out
}

func TestRecorderConcurrent(t *testing.T) {
	c := NewFrameClock()
	r := NewLatencyRecorder(ModeReceive)
	base := time.Now()
	var wg sync.WaitGroup
	for w := 0; w < 4; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			for i := 0; i < 250; i++ {
				id := uint64(w*1000 + i + 1)
				c.Capture(id, base)
				r.Record(id, c, base.Add(72*time.Millisecond))
			}
		}(w)
	}
	wg.Wait()
	if s := r.Summary(); s.Frames != 1000 {
		t.Fatalf("frames = %d, want 1000", s.Frames)
	}
}
