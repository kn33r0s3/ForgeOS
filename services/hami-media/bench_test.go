package main

import (
	"testing"
	"time"

	"github.com/pion/rtp"
)

// BenchmarkCopyRTPPacketWithSharedPayload measures the per-copy cost
// with the sync.Pool. Before the pool, each copy was a fresh heap alloc
// (&packetCopy); after, the struct is recycled.
func BenchmarkCopyRTPPacketWithSharedPayload(b *testing.B) {
	packet := &rtp.Packet{
		Header:  rtp.Header{SSRC: 11, SequenceNumber: 7, CSRC: []uint32{22}},
		Payload: []byte{1, 2, 3, 4, 5, 6, 7, 8},
	}
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		copied := copyRTPPacketWithSharedPayload(packet)
		releaseRTPPacketCopy(copied)
	}
}

// BenchmarkEnqueueRTP measures the per-viewer enqueue cost with a
// single shared timestamp (the forwardTrack path passes one now).
func BenchmarkEnqueueRTP(b *testing.B) {
	subscription := &sfuSubscription{active: true, rtpQueue: make(chan queuedRTP, 1024)}
	packet := &rtp.Packet{
		Header:  rtp.Header{SSRC: 11, SequenceNumber: 7},
		Payload: []byte{1, 2, 3, 4, 5, 6, 7, 8},
	}
	now := time.Now()
	// Drain the queue in the background so enqueue never blocks, and
	// release each copy so the pool is exercised end to end.
	done := make(chan struct{})
	go func() {
		for entry := range subscription.rtpQueue {
			releaseRTPPacketCopy(entry.packet)
		}
		close(done)
	}()
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := subscription.enqueueRTP(packet, layerBase, now); err != nil {
			b.Fatalf("enqueueRTP: %v", err)
		}
	}
	b.StopTimer()
	close(subscription.rtpQueue)
	<-done
}
