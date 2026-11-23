// Tests for the layered packet division in the hami-media router:
// classify before
// rememberPacket/enqueueRTP, NACK cache for layers 0-1 only, queue sheds
// layer 2 first under pressure.
package main

import (
	"testing"
	"time"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

func layerTestPacket(sequence uint16, payload []byte) *rtp.Packet {
	return &rtp.Packet{
		Header:  rtp.Header{SequenceNumber: sequence},
		Payload: payload,
	}
}

func TestClassifyPacketLayerMedia(t *testing.T) {
	tests := []struct {
		name    string
		codec   string
		payload []byte
		want    packetLayer
	}{
		{name: "opus audio", codec: webrtc.MimeTypeOpus, payload: []byte{0x01, 0x02}, want: layerBase},
		{name: "PCMU audio", codec: webrtc.MimeTypePCMU, payload: []byte{0x01}, want: layerBase},
		{name: "H264 SPS", codec: webrtc.MimeTypeH264, payload: []byte{0x67, 0x42, 0x00, 0x1e}, want: layerBase},
		{name: "H264 PPS", codec: webrtc.MimeTypeH264, payload: []byte{0x68, 0xce, 0x38, 0x80}, want: layerBase},
		{name: "H264 STAP-A SPS+PPS", codec: webrtc.MimeTypeH264, payload: []byte{0x78, 0, 2, 0x67, 0x01, 0, 2, 0x68, 0x02}, want: layerBase},
		{name: "H264 IDR single NAL", codec: webrtc.MimeTypeH264, payload: []byte{0x65, 0x88, 0x84, 0x00}, want: layerKey},
		{name: "H264 IDR STAP-A", codec: webrtc.MimeTypeH264, payload: []byte{0x78, 0, 2, 0x67, 0x01, 0, 2, 0x65, 0x02}, want: layerKey},
		{name: "H264 IDR FU-A start", codec: webrtc.MimeTypeH264, payload: []byte{0x7c, 0x85}, want: layerKey},
		{name: "H264 non-IDR single NAL", codec: webrtc.MimeTypeH264, payload: []byte{0x41, 0x9a, 0x00, 0x00}, want: layerDelta},
		{name: "H264 FU-A continuation", codec: webrtc.MimeTypeH264, payload: []byte{0x7c, 0x45}, want: layerDelta},
		{name: "H264 FU-A start non-IDR", codec: webrtc.MimeTypeH264, payload: []byte{0x7c, 0x81}, want: layerDelta},
		{name: "H264 empty payload", codec: webrtc.MimeTypeH264, payload: []byte{}, want: layerDelta},
		{name: "VP8 keyframe", codec: "video/VP8", payload: []byte{0x10, 0x00, 0x00}, want: layerKey},
		{name: "VP8 interframe", codec: "video/VP8", payload: []byte{0x10, 0x01, 0x00}, want: layerDelta},
		{name: "VP9 unknown video", codec: "video/VP9", payload: []byte{0x01}, want: layerDelta},
		{name: "unknown codec safe default", codec: "application/octet-stream", payload: []byte{0x01}, want: layerBase},
		{name: "empty codec safe default", codec: "", payload: []byte{0x01}, want: layerBase},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			packet := &rtp.Packet{Payload: test.payload}
			if got := classifyPacketLayer(test.codec, packet); got != test.want {
				t.Fatalf("classifyPacketLayer(%q, %x) = %d, want %d", test.codec, test.payload, got, test.want)
			}
		})
	}
	t.Run("nil packet", func(t *testing.T) {
		if got := classifyPacketLayer(webrtc.MimeTypeH264, nil); got != layerDelta {
			t.Fatalf("classifyPacketLayer(H264, nil) = %d, want layerDelta", got)
		}
	})
}

func TestPacketLayerClassifierKeepsFragmentedFramesTogether(t *testing.T) {
	t.Run("H264 IDR FU-A", func(t *testing.T) {
		classifier := packetLayerClassifier{}
		packets := []struct {
			payload []byte
			want    packetLayer
		}{
			{payload: []byte{0x7c, 0x85}, want: layerKey},
			{payload: []byte{0x7c, 0x05}, want: layerKey},
			{payload: []byte{0x7c, 0x45}, want: layerKey},
			{payload: []byte{0x7c, 0x87}, want: layerBase},
			{payload: []byte{0x7c, 0x07}, want: layerBase},
			{payload: []byte{0x7c, 0x47}, want: layerBase},
		}
		for i, packet := range packets {
			rtpPacket := &rtp.Packet{
				Header:  rtp.Header{Timestamp: 42 + uint32(i/3), Marker: i%3 == 2},
				Payload: packet.payload,
			}
			if got := classifier.classify(webrtc.MimeTypeH264, rtpPacket); got != packet.want {
				t.Fatalf("H264 fragment %d layer = %d, want %d", i, got, packet.want)
			}
		}
	})

	t.Run("VP8 key and inter frames", func(t *testing.T) {
		classifier := packetLayerClassifier{}
		packets := []struct {
			timestamp uint32
			payload   []byte
			marker    bool
			want      packetLayer
		}{
			{timestamp: 1, payload: []byte{0x10, 0x00, 0x00}, want: layerKey},
			{timestamp: 1, payload: []byte{0x00, 0x11}, marker: true, want: layerKey},
			{timestamp: 2, payload: []byte{0x10, 0x01, 0x00}, want: layerDelta},
			{timestamp: 2, payload: []byte{0x00, 0x11}, marker: true, want: layerDelta},
			{timestamp: 3, payload: []byte{0x00, 0x11}, marker: true, want: layerDelta},
		}
		for i, packet := range packets {
			rtpPacket := &rtp.Packet{
				Header:  rtp.Header{Timestamp: packet.timestamp, Marker: packet.marker},
				Payload: packet.payload,
			}
			if got := classifier.classify("video/VP8", rtpPacket); got != packet.want {
				t.Fatalf("VP8 packet %d layer = %d, want %d", i, got, packet.want)
			}
		}
	})
}

func TestRememberPacketCachesEveryH264IDRFragment(t *testing.T) {
	track := &sfuPublishedTrack{packetCache: make(map[uint16]*rtp.Packet)}
	classifier := packetLayerClassifier{}
	packets := []*rtp.Packet{
		{Header: rtp.Header{SequenceNumber: 1, Timestamp: 42}, Payload: []byte{0x7c, 0x85}},
		{Header: rtp.Header{SequenceNumber: 2, Timestamp: 42}, Payload: []byte{0x7c, 0x05}},
		{Header: rtp.Header{SequenceNumber: 3, Timestamp: 42, Marker: true}, Payload: []byte{0x7c, 0x45}},
	}
	for _, packet := range packets {
		track.rememberPacket(packet, classifier.classify(webrtc.MimeTypeH264, packet))
	}

	if got := track.packetCachePackets.Load(); got != int64(len(packets)) {
		t.Fatalf("cached packets = %d, want all %d IDR fragments", got, len(packets))
	}
	cached, missing := track.cachedPackets([]uint16{1, 2, 3})
	if len(cached) != len(packets) || len(missing) != 0 {
		t.Fatalf("IDR fragment lookup = %d cached, missing %v; want all fragments cached",
			len(cached), missing)
	}
}

// TestRememberPacketSkipsDeltaLayer measures the NACK-cache reduction
// from a real run: the same 100-packet stream (10 audio + 10 keyframes +
// 80 deltas) is remembered once the old way (everything cached) and once
// the layered way (layers 0-1 only). The numbers are asserted exactly.
func TestRememberPacketSkipsDeltaLayer(t *testing.T) {
	audioPayload := make([]byte, 100)
	keyPayload := append([]byte{0x65, 0x88}, make([]byte, 1198)...)
	deltaPayload := append([]byte{0x41, 0x9a}, make([]byte, 1198)...)

	before := &sfuPublishedTrack{packetCache: make(map[uint16]*rtp.Packet)}
	after := &sfuPublishedTrack{packetCache: make(map[uint16]*rtp.Packet)}
	for sequence := uint16(1); sequence <= 100; sequence++ {
		var codec string
		var payload []byte
		switch (sequence - 1) % 10 {
		case 0:
			codec, payload = webrtc.MimeTypeOpus, audioPayload
		case 1:
			codec, payload = webrtc.MimeTypeH264, keyPayload
		default:
			codec, payload = webrtc.MimeTypeH264, deltaPayload
		}
		packet := layerTestPacket(sequence, payload)
		before.rememberPacket(packet, layerBase)
		after.rememberPacket(packet, classifyPacketLayer(codec, packet))
	}

	if got := before.packetCachePackets.Load(); got != 100 {
		t.Fatalf("before: cached packets = %d, want 100", got)
	}
	if got, want := before.packetCachePayloadBytes.Load(), int64(10*100+90*1200); got != want {
		t.Fatalf("before: cached payload bytes = %d, want %d", got, want)
	}
	if got := after.packetCachePackets.Load(); got != 20 {
		t.Fatalf("after: cached packets = %d, want 20 (10 audio + 10 keyframes)", got)
	}
	if got, want := after.packetCachePayloadBytes.Load(), int64(10*100+10*1200); got != want {
		t.Fatalf("after: cached payload bytes = %d, want %d", got, want)
	}
	if got := after.layerDeltaCacheSkipped.Load(); got != 80 {
		t.Fatalf("after: skipped deltas = %d, want 80", got)
	}
	if got := after.latestSequence(); got != 100 {
		t.Fatalf("after: latest sequence = %d, want 100 (sequence still advances through deltas)", got)
	}
	// A NACK for a delta sequence comes back missing (the existing miss
	// path); a NACK for a keyframe sequence is served from the cache.
	if _, missing := after.cachedPackets([]uint16{3}); len(missing) != 1 || missing[0] != 3 {
		t.Fatalf("cachedPackets([3]) missing = %v, want [3]", missing)
	}
	if packets, missing := after.cachedPackets([]uint16{2}); len(missing) != 0 || len(packets) != 1 {
		t.Fatalf("cachedPackets([2]) = %d packets, missing %v, want 1 packet and no missing", len(packets), missing)
	}
	t.Logf("NACK cache: before 100 packets / 109000 bytes, after 20 packets / 13000 bytes (80%% fewer packets, 88%% fewer bytes)")
}

func TestEnqueueRTPDropsDeltaFirst(t *testing.T) {
	queue := make(chan queuedRTP, 2)
	subscription := &sfuSubscription{active: true, h264Video: true, rtpQueue: queue}
	delta := []byte{0x41, 0x9a}
	key := []byte{0x65, 0x88}

	// Fill the queue with two deltas.
	for _, sequence := range []uint16{1, 2} {
		if dropped, err := subscription.enqueueRTP(layerTestPacket(sequence, delta), layerDelta, time.Now()); dropped || err != nil {
			t.Fatalf("enqueue delta %d: dropped=%v err=%v, want clean enqueue", sequence, dropped, err)
		}
	}
	// A keyframe arriving at the full queue must get in by evicting the
	// OLDEST delta — not by losing the keyframe, and not by dropping the
	// newer delta.
	dropped, err := subscription.enqueueRTP(layerTestPacket(3, key), layerKey, time.Now())
	if err != nil {
		t.Fatalf("enqueue keyframe: %v", err)
	}
	if !dropped {
		t.Fatal("enqueue keyframe at full queue: dropped=false, want true (a delta was evicted)")
	}
	if got := len(queue); got != 2 {
		t.Fatalf("queue depth = %d, want 2", got)
	}
	if got := subscription.rtpQueueDropped.Load(); got != 1 {
		t.Fatalf("queue drop count = %d, want 1", got)
	}
	if subscription.keyframeNeededAt.Load() == 0 {
		t.Fatal("keyframe recovery was not flagged after a delta was evicted")
	}
	want := []uint16{2, 3}
	for _, sequence := range want {
		entry := <-queue
		if got := entry.packet.SequenceNumber; got != sequence {
			t.Fatalf("queued sequence = %d, want %d (oldest delta must go first)", got, sequence)
		}
	}

	// Refill with two deltas, then a delta arriving at the full queue
	// is shed at once — the queue contents must not change.
	for _, sequence := range []uint16{4, 5} {
		if dropped, err := subscription.enqueueRTP(layerTestPacket(sequence, delta), layerDelta, time.Now()); dropped || err != nil {
			t.Fatalf("enqueue delta %d: dropped=%v err=%v, want clean enqueue", sequence, dropped, err)
		}
	}
	dropped, err = subscription.enqueueRTP(layerTestPacket(6, delta), layerDelta, time.Now())
	if err != nil {
		t.Fatalf("enqueue delta at full queue: %v", err)
	}
	if !dropped {
		t.Fatal("enqueue delta at full queue: dropped=false, want true (incoming delta shed)")
	}
	if got := len(queue); got != 2 {
		t.Fatalf("queue depth = %d, want 2", got)
	}
	for _, sequence := range []uint16{4, 5} {
		entry := <-queue
		if got := entry.packet.SequenceNumber; got != sequence {
			t.Fatalf("queued sequence = %d, want %d (shed delta must not displace queued packets)", got, sequence)
		}
	}
	if got := subscription.rtpQueueDropped.Load(); got != 2 {
		t.Fatalf("queue drop count = %d, want 2", got)
	}
	t.Logf("queue: keyframe evicted oldest delta (seq 1), incoming delta shed at once (seq 6 never queued = 1 WriteRTP avoided)")
}

func TestEnqueueRTPFallsBackToOldestWhenNoDelta(t *testing.T) {
	queue := make(chan queuedRTP, 2)
	subscription := &sfuSubscription{active: true, rtpQueue: queue}
	// A queue with no delta in it keeps the old behaviour exactly:
	// the oldest packet is dropped so the new base packet gets in.
	for _, sequence := range []uint16{1, 2} {
		if dropped, err := subscription.enqueueRTP(layerTestPacket(sequence, []byte{0x67}), layerBase, time.Now()); dropped || err != nil {
			t.Fatalf("enqueue base %d: dropped=%v err=%v, want clean enqueue", sequence, dropped, err)
		}
	}
	dropped, err := subscription.enqueueRTP(layerTestPacket(3, []byte{0x67}), layerBase, time.Now())
	if err != nil {
		t.Fatalf("enqueue base at full queue: %v", err)
	}
	if !dropped {
		t.Fatal("enqueue base at full queue: dropped=false, want true (oldest evicted)")
	}
	for _, sequence := range []uint16{2, 3} {
		entry := <-queue
		if got := entry.packet.SequenceNumber; got != sequence {
			t.Fatalf("queued sequence = %d, want %d", got, sequence)
		}
	}
}

func TestShardEnqueueDropsDeltaFirst(t *testing.T) {
	router := &sfuRouter{}
	subscription := &sfuSubscription{viewerID: "viewer-1", active: true, h264Video: true}
	shard := &sfuEgressShard{
		subscriptions: map[string]*sfuSubscription{subscription.viewerID: subscription},
		queue:         make(chan sfuEgressJob, 2),
		router:        router,
	}
	delta := []byte{0x41, 0x9a}
	key := []byte{0x65, 0x88}

	for _, sequence := range []uint16{1, 2} {
		shard.enqueue(layerTestPacket(sequence, delta), layerDelta, time.Now())
	}
	if got := len(shard.queue); got != 2 {
		t.Fatalf("shard queue depth = %d, want 2", got)
	}
	// A keyframe job at the full shard queue evicts the oldest delta.
	shard.enqueue(layerTestPacket(3, key), layerKey, time.Now())
	if got := len(shard.queue); got != 2 {
		t.Fatalf("shard queue depth = %d, want 2", got)
	}
	for _, sequence := range []uint16{2, 3} {
		job := <-shard.queue
		if got := job.packet.SequenceNumber; got != sequence {
			t.Fatalf("shard job sequence = %d, want %d (oldest delta must go first)", got, sequence)
		}
		if job.layer != layerDelta && sequence == 2 {
			t.Fatal("shard job lost its layer")
		}
	}

	// Refill with deltas; an incoming delta at the full shard queue is
	// shed and never reaches a subscriber.
	for _, sequence := range []uint16{4, 5} {
		shard.enqueue(layerTestPacket(sequence, delta), layerDelta, time.Now())
	}
	before := router.rtpQueueDropped.Load()
	shard.enqueue(layerTestPacket(6, delta), layerDelta, time.Now())
	if got := router.rtpQueueDropped.Load(); got != before+1 {
		t.Fatalf("router drop count = %d, want %d (incoming delta shed)", got, before+1)
	}
	if got := subscription.rtpQueueDropped.Load(); got != router.rtpQueueDropped.Load() {
		t.Fatalf("subscription drop count = %d, router drop count = %d", got, router.rtpQueueDropped.Load())
	}
	if subscription.keyframeNeededAt.Load() == 0 {
		t.Fatal("shard-queue drop did not request keyframe recovery")
	}
	if got := router.rtpQueueDropShed.Load(); got != router.rtpQueueDropped.Load() ||
		router.rtpIntentionalShed.Load() != router.rtpQueueDropped.Load() {
		t.Fatalf("shard drop accounting: queue=%d overlap=%d intentional=%d",
			router.rtpQueueDropped.Load(), router.rtpQueueDropShed.Load(),
			router.rtpIntentionalShed.Load())
	}
	for _, sequence := range []uint16{4, 5} {
		job := <-shard.queue
		if got := job.packet.SequenceNumber; got != sequence {
			t.Fatalf("shard job sequence = %d, want %d (shed delta must not displace queued jobs)", got, sequence)
		}
	}
	t.Logf("shard queue: keyframe evicted oldest delta (seq 1), incoming delta shed at once (seq 6 never queued)")
}

// TestLayeredStreamStaysInOrder pins the ordering rule: classification
// never reorders packets — base, key and delta leave the queue in the
// exact order they entered.
func TestLayeredStreamStaysInOrder(t *testing.T) {
	queue := make(chan queuedRTP, 8)
	subscription := &sfuSubscription{active: true, rtpQueue: queue}
	packets := []struct {
		sequence uint16
		payload  []byte
		layer    packetLayer
	}{
		{1, []byte{0x67}, layerBase},
		{2, []byte{0x65, 0x88}, layerKey},
		{3, []byte{0x41, 0x9a}, layerDelta},
		{4, []byte{0x41, 0x9a}, layerDelta},
		{5, []byte{0x65, 0x88}, layerKey},
		{6, []byte{0x41, 0x9a}, layerDelta},
	}
	for _, packet := range packets {
		if dropped, err := subscription.enqueueRTP(layerTestPacket(packet.sequence, packet.payload), packet.layer, time.Now()); dropped || err != nil {
			t.Fatalf("enqueue %d: dropped=%v err=%v, want clean enqueue", packet.sequence, dropped, err)
		}
	}
	for _, want := range packets {
		entry := <-queue
		if got := entry.packet.SequenceNumber; got != want.sequence {
			t.Fatalf("queued sequence = %d, want %d (order must not change)", got, want.sequence)
		}
		if entry.layer != want.layer {
			t.Fatalf("queued sequence %d layer = %d, want %d", want.sequence, entry.layer, want.layer)
		}
	}
}

func BenchmarkClassifyPacketLayerMedia(b *testing.B) {
	packet := &rtp.Packet{Payload: []byte{0x41, 0x9a, 0x00, 0x00, 0x00, 0x00}}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = classifyPacketLayer(webrtc.MimeTypeH264, packet)
	}
}
