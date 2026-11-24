package main

import (
	"errors"
	"sync"
	"testing"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

// recordingSink records every packet it is handed. It copies the packet
// struct on receipt because layerFanout clears the original after the pass.
type recordingSink struct {
	mu       sync.Mutex
	received []*rtp.Packet
	err      error
}

func (s *recordingSink) WriteRTP(pkt *rtp.Packet) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.err != nil {
		return s.err
	}
	cp := *pkt
	s.received = append(s.received, &cp)
	return nil
}

func (s *recordingSink) count() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.received)
}

func (s *recordingSink) sequences() []uint16 {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]uint16, 0, len(s.received))
	for _, pkt := range s.received {
		out = append(out, pkt.SequenceNumber)
	}
	return out
}

// countingSink counts writes without recording — for benchmarks.
type countingSink struct {
	n int64
}

func (s *countingSink) WriteRTP(_ *rtp.Packet) error {
	s.n++
	return nil
}

func testPacket(seq uint16, payload []byte) *rtp.Packet {
	return &rtp.Packet{
		Header:  rtp.Header{SequenceNumber: seq, Timestamp: uint32(seq) * 3000, PayloadType: 96},
		Payload: payload,
	}
}

func TestClassifyPacket(t *testing.T) {
	// H264 payloads: NAL header byte first.
	sps := []byte{0x67, 0x42, 0x00, 0x1e}
	pps := []byte{0x68, 0xce, 0x38, 0x80}
	idrSingle := []byte{0x65, 0x88, 0x84, 0x00}
	nonIDR := []byte{0x41, 0x9a, 0x00, 0x00}
	// STAP-A (0x18): 2-byte length + NAL.
	stapIDR := []byte{0x18, 0x00, 0x03, 0x65, 0xaa, 0xbb}
	stapNonIDR := []byte{0x18, 0x00, 0x03, 0x41, 0xaa, 0xbb}
	stapSPSPPS := []byte{0x18, 0x00, 0x02, 0x67, 0x42, 0x00, 0x02, 0x68, 0xce}
	// FU-A (0x7c): second byte start-bit + NAL type.
	fuIDRStart := []byte{0x7c, 0x85, 0xaa, 0xbb}
	fuIDRCont := []byte{0x7c, 0x05, 0xaa, 0xbb}
	fuNonIDRStart := []byte{0x7c, 0x81, 0xaa, 0xbb}
	// VP8: first byte bit 0 clear = keyframe.
	vp8Key := []byte{0x10, 0x00, 0x00}
	vp8Inter := []byte{0x11, 0x00, 0x00}

	cases := []struct {
		name    string
		codec   string
		payload []byte
		want    layer
	}{
		{"opus audio", "audio/opus", []byte{0x01, 0x02}, layerBase},
		{"audio empty payload", "audio/opus", []byte{}, layerBase},
		{"h264 SPS", "video/H264", sps, layerBase},
		{"h264 PPS", "video/H264", pps, layerBase},
		{"h264 STAP-A SPS+PPS", "video/H264", stapSPSPPS, layerBase},
		{"h264 IDR single NAL", "video/H264", idrSingle, layerKey},
		{"h264 IDR STAP-A", "video/H264", stapIDR, layerKey},
		{"h264 IDR FU-A start", "video/H264", fuIDRStart, layerKey},
		{"h264 non-IDR", "video/H264", nonIDR, layerDelta},
		{"h264 STAP-A non-IDR", "video/H264", stapNonIDR, layerDelta},
		{"h264 FU-A continuation", "video/H264", fuIDRCont, layerDelta},
		{"h264 FU-A start non-IDR", "video/H264", fuNonIDRStart, layerDelta},
		{"h264 empty payload", "video/H264", []byte{}, layerDelta},
		{"vp8 keyframe", "video/VP8", vp8Key, layerKey},
		{"vp8 interframe", "video/VP8", vp8Inter, layerDelta},
		{"vp9 unknown video codec", "video/VP9", []byte{0x10}, layerDelta},
		{"unknown codec safe default", "", []byte{0x01}, layerBase},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := classifyPacket(tc.codec, testPacket(1, tc.payload))
			if got != tc.want {
				t.Fatalf("classifyPacket(%q) = %d, want %d", tc.codec, got, tc.want)
			}
		})
	}
	if got := classifyPacket("video/H264", nil); got != layerDelta {
		t.Fatalf("classifyPacket(nil packet) = %d, want %d", got, layerDelta)
	}
}

func TestLayerFanoutSendsOnlyMaskedLayers(t *testing.T) {
	full := &recordingSink{}
	keyOnly := &recordingSink{}
	audioOnly := &recordingSink{}
	subs := []layerSub{
		{sink: full, mask: layerMaskAll},
		{sink: keyOnly, mask: layerMaskKeyframesOnly},
		{sink: audioOnly, mask: layerMaskAudio},
	}

	audio := testPacket(1, []byte{0x01})
	if sent, err := layerFanout(audio, layerBase, subs); err != nil || sent != 3 {
		t.Fatalf("audio fanout: sent=%d err=%v, want sent=3 err=nil", sent, err)
	}
	key := testPacket(2, []byte{0x65, 0x88})
	if sent, err := layerFanout(key, layerKey, subs); err != nil || sent != 2 {
		t.Fatalf("keyframe fanout: sent=%d err=%v, want sent=2 err=nil", sent, err)
	}
	delta := testPacket(3, []byte{0x41, 0x9a})
	if sent, err := layerFanout(delta, layerDelta, subs); err != nil || sent != 1 {
		t.Fatalf("delta fanout: sent=%d err=%v, want sent=1 err=nil", sent, err)
	}

	if got := full.count(); got != 3 {
		t.Fatalf("full subscriber got %d packets, want 3", got)
	}
	if got := keyOnly.count(); got != 2 {
		t.Fatalf("keyframes-only subscriber got %d packets, want 2", got)
	}
	if got := audioOnly.count(); got != 1 {
		t.Fatalf("audio-only subscriber got %d packets, want 1", got)
	}
	// Order is preserved per subscriber.
	if got := full.sequences(); len(got) != 3 || got[0] != 1 || got[1] != 2 || got[2] != 3 {
		t.Fatalf("full subscriber sequences = %v, want [1 2 3]", got)
	}
	if got := keyOnly.sequences(); len(got) != 2 || got[0] != 1 || got[1] != 2 {
		t.Fatalf("keyframes-only sequences = %v, want [1 2]", got)
	}
	if got := audioOnly.sequences(); len(got) != 1 || got[0] != 1 {
		t.Fatalf("audio-only sequences = %v, want [1]", got)
	}
}

func TestLayerFanoutCompletesStreamForFullMask(t *testing.T) {
	sink := &recordingSink{}
	subs := []layerSub{{sink: sink, mask: layerMaskAll}}
	// A realistic group: audio, SPS, keyframe, 3 deltas, audio.
	packets := []struct {
		seq   uint16
		layer layer
	}{
		{10, layerBase}, {11, layerBase}, {12, layerKey},
		{13, layerDelta}, {14, layerDelta}, {15, layerDelta}, {16, layerBase},
	}
	for _, p := range packets {
		pkt := testPacket(p.seq, []byte{0x01})
		sent, err := layerFanout(pkt, p.layer, subs)
		if err != nil || sent != 1 {
			t.Fatalf("packet %d: sent=%d err=%v, want sent=1", p.seq, sent, err)
		}
	}
	got := sink.sequences()
	want := []uint16{10, 11, 12, 13, 14, 15, 16}
	if len(got) != len(want) {
		t.Fatalf("full-mask subscriber got %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("full-mask subscriber got %v, want %v", got, want)
		}
	}
}

func TestClearPacketRetainsNothing(t *testing.T) {
	sink := &recordingSink{}
	subs := []layerSub{{sink: sink, mask: layerMaskAll}}
	pkt := testPacket(7, []byte{0x01, 0x02, 0x03})
	pkt.Raw = []byte{0x09, 0x09}
	if _, err := layerFanout(pkt, layerBase, subs); err != nil {
		t.Fatalf("fanout err = %v", err)
	}
	if pkt.Payload != nil {
		t.Fatalf("packet Payload not cleared after send: len=%d", len(pkt.Payload))
	}
	if pkt.Raw != nil {
		t.Fatalf("packet Raw not cleared after send: len=%d", len(pkt.Raw))
	}
	if pkt.SequenceNumber != 0 || pkt.Timestamp != 0 {
		t.Fatalf("packet header not cleared after send: seq=%d ts=%d", pkt.SequenceNumber, pkt.Timestamp)
	}
	// The sink recorded the packet before the clear, so the stream is intact.
	if got := sink.count(); got != 1 {
		t.Fatalf("sink recorded %d packets, want 1", got)
	}
}

func TestLayerFanoutContinuesAfterSinkError(t *testing.T) {
	bad := &recordingSink{err: errors.New("sink down")}
	good := &recordingSink{}
	subs := []layerSub{{sink: bad, mask: layerMaskAll}, {sink: good, mask: layerMaskAll}}
	pkt := testPacket(9, []byte{0x01})
	sent, err := layerFanout(pkt, layerBase, subs)
	if err == nil {
		t.Fatalf("fanout err = nil, want the sink error")
	}
	if sent != 1 {
		t.Fatalf("fanout sent = %d, want 1 (good sink still served)", sent)
	}
	if got := good.count(); got != 1 {
		t.Fatalf("good sink got %d packets, want 1", got)
	}
	if pkt.Payload != nil {
		t.Fatalf("packet not cleared after erroring fanout")
	}
}

func TestSnapshotLayerSubsDefaultsAndMask(t *testing.T) {
	rm := &room{tracks: make(map[string]*track)}
	tr := &track{room: rm, subs: make(map[*webrtc.TrackLocalStaticRTP]struct{})}
	localA, err := webrtc.NewTrackLocalStaticRTP(webrtc.RTPCodecCapability{MimeType: "audio/opus"}, "a", "s")
	if err != nil {
		t.Fatalf("NewTrackLocalStaticRTP: %v", err)
	}
	localB, err := webrtc.NewTrackLocalStaticRTP(webrtc.RTPCodecCapability{MimeType: "video/H264"}, "v", "s")
	if err != nil {
		t.Fatalf("NewTrackLocalStaticRTP: %v", err)
	}
	tr.addSub(localA) // default: full mask
	tr.addSubWithMask(localB, layerMaskKeyframesOnly)

	subs := tr.snapshotLayerSubs()
	if len(subs) != 2 {
		t.Fatalf("snapshot has %d subs, want 2", len(subs))
	}
	masks := map[packetSink]layerMask{}
	for _, s := range subs {
		masks[s.sink] = s.mask
	}
	if masks[localA] != layerMaskAll {
		t.Fatalf("default mask = %d, want %d (all)", masks[localA], layerMaskAll)
	}
	if masks[localB] != layerMaskKeyframesOnly {
		t.Fatalf("explicit mask = %d, want %d", masks[localB], layerMaskKeyframesOnly)
	}

	tr.setSubLayerMask(localB, layerMaskAudio)
	subs = tr.snapshotLayerSubs()
	for _, s := range subs {
		if s.sink == packetSink(localB) && s.mask != layerMaskAudio {
			t.Fatalf("after setSubLayerMask mask = %d, want %d", s.mask, layerMaskAudio)
		}
	}

	tr.removeSub(localA)
	if got := len(tr.snapshotLayerSubs()); got != 1 {
		t.Fatalf("after removeSub snapshot has %d subs, want 1", got)
	}
}

// TestLayeredFanoutReducesWrites is the measured reduction: the same
// packets and subscribers, direct vs layered. Mix: 10 subscribers (5 full,
// 3 keyframes-only, 2 audio-only) and one group of 10 packets (1 audio,
// 1 keyframe, 8 delta). Direct writes every packet to every subscriber
// (100 writes). Layered writes audio to 10, the keyframe to 8, each delta
// to 5 (58 writes) — 42% fewer writes.
func TestLayeredFanoutReducesWrites(t *testing.T) {
	buildSubs := func() ([]layerSub, []*countingSink) {
		sinks := make([]*countingSink, 0, 10)
		subs := make([]layerSub, 0, 10)
		add := func(mask layerMask) {
			s := &countingSink{}
			sinks = append(sinks, s)
			subs = append(subs, layerSub{sink: s, mask: mask})
		}
		for i := 0; i < 5; i++ {
			add(layerMaskAll)
		}
		for i := 0; i < 3; i++ {
			add(layerMaskKeyframesOnly)
		}
		for i := 0; i < 2; i++ {
			add(layerMaskAudio)
		}
		return subs, sinks
	}
	packets := []struct {
		seq   uint16
		layer layer
	}{
		{1, layerBase}, {2, layerKey},
		{3, layerDelta}, {4, layerDelta}, {5, layerDelta}, {6, layerDelta},
		{7, layerDelta}, {8, layerDelta}, {9, layerDelta}, {10, layerDelta},
	}
	total := func(sinks []*countingSink) int64 {
		var n int64
		for _, s := range sinks {
			n += s.n
		}
		return n
	}

	directSubs, directSinks := buildSubs()
	for _, p := range packets {
		pkt := testPacket(p.seq, []byte{0x01})
		if _, err := fanoutDirect(pkt, directSubs); err != nil {
			t.Fatalf("direct fanout err = %v", err)
		}
	}
	directWrites := total(directSinks)

	layeredSubs, layeredSinks := buildSubs()
	for _, p := range packets {
		pkt := testPacket(p.seq, []byte{0x01})
		if _, err := layerFanout(pkt, p.layer, layeredSubs); err != nil {
			t.Fatalf("layered fanout err = %v", err)
		}
	}
	layeredWrites := total(layeredSinks)

	if directWrites != 100 {
		t.Fatalf("direct writes = %d, want 100", directWrites)
	}
	if layeredWrites != 58 {
		t.Fatalf("layered writes = %d, want 58", layeredWrites)
	}
	t.Logf("writes: direct=%d layered=%d reduction=%.1f%%", directWrites, layeredWrites,
		100*float64(directWrites-layeredWrites)/float64(directWrites))
}

func mixedGroupSubs() ([]layerSub, []*countingSink) {
	sinks := make([]*countingSink, 0, 10)
	subs := make([]layerSub, 0, 10)
	add := func(mask layerMask) {
		s := &countingSink{}
		sinks = append(sinks, s)
		subs = append(subs, layerSub{sink: s, mask: mask})
	}
	for i := 0; i < 5; i++ {
		add(layerMaskAll)
	}
	for i := 0; i < 3; i++ {
		add(layerMaskKeyframesOnly)
	}
	for i := 0; i < 2; i++ {
		add(layerMaskAudio)
	}
	return subs, sinks
}

func mixedGroupPackets() []*rtp.Packet {
	return []*rtp.Packet{
		testPacket(1, []byte{0x01}),
		testPacket(2, []byte{0x65}),
		testPacket(3, []byte{0x41}), testPacket(4, []byte{0x41}),
		testPacket(5, []byte{0x41}), testPacket(6, []byte{0x41}),
		testPacket(7, []byte{0x41}), testPacket(8, []byte{0x41}),
		testPacket(9, []byte{0x41}), testPacket(10, []byte{0x41}),
	}
}

func mixedGroupLayers() []layer {
	return []layer{layerBase, layerKey,
		layerDelta, layerDelta, layerDelta, layerDelta,
		layerDelta, layerDelta, layerDelta, layerDelta}
}

func BenchmarkFanoutDirect(b *testing.B) {
	subs, _ := mixedGroupSubs()
	packets := mixedGroupPackets()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Fresh packet per iteration, like the layered path gets: in
		// production ReadRTP allocates a new packet per read, and the
		// layered path clears it, so reusing one packet would flatter
		// the direct path.
		src := packets[i%len(packets)]
		pkt := testPacket(src.SequenceNumber, append([]byte(nil), src.Payload...))
		_, _ = fanoutDirect(pkt, subs)
	}
}

func BenchmarkFanoutLayered(b *testing.B) {
	subs, _ := mixedGroupSubs()
	packets := mixedGroupPackets()
	layers := mixedGroupLayers()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Layered clears the packet, so each iteration needs a fresh one.
		src := packets[i%len(packets)]
		pkt := testPacket(src.SequenceNumber, append([]byte(nil), src.Payload...))
		_, _ = layerFanout(pkt, layers[i%len(layers)], subs)
	}
}

func BenchmarkClassifyPacket(b *testing.B) {
	pkt := testPacket(1, []byte{0x65, 0x88, 0x84, 0x00})
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = classifyPacket("video/H264", pkt)
	}
}
