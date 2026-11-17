package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/pion/rtcp"
	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

const testH264AccessUnit = "AAAAASdCAAyrgoPyAAAAASjOPIAAAAABJbggH/xx/nigACBHqovX1FcSaPqNPn1Gmn1Gmn1Gnz6jTT6jTT6jT59R" +
	"pp9Rpp9Rp8+o00+o00+o0+fUaafUabwD4Q+eKDrWL140AAQYY4Bn2DGnz4uNNPxpv//5YvX1F6xgChINCSRJzjsS" +
	"Sv4klXslTkq5OSrzkq9kqclXslTkq5OSr2SpyVeyVEuDUBoBgAoSDRyfHYklfzkq///8LxesXrEg0JBoSSLvKTEk" +
	"2lJlJlJlJlJlJlJlJlJlJlJlJiXC4ABFAJBoSDQklXlJiSbf//wvF6xesSNCQaKSTiSdSkqUmyVZKslWSrJVkqyV" +
	"OSr2SrJVkqJcGoBoBI0JBopKsmUlf//wvVReqi8YAoSDRSVOSvTkr1k2SLsmyRdk2SLsmyRdk2SLsmyRcS4XAAIo" +
	"BgChINFJslWSv//6rF69YvriQaEg0UlWTKSrJVkqyVZKslSkykqUmyVKTKSrJUS4NQDQCQaEg0yZSZSf//5axfXW" +
	"LxI0JBopKsmyVZKslWSrJVkqUmJJtZKiSbykykxJOolxIABHiRoSDTJUpKslf//wvWL1i8YAoSGhJN7JslSk2SrJ" +
	"VkqyVZKslTkq9kqyVKTZKiXBqAaAYAoSGjkq9kqyV///UUAAQPdesXr6jAABA+QkAAQUEdSEEaadVGmnVRp86qNN" +
	"OqjTTqo0+dVGmnVRpp1jT51Fxpp1jTTqLjT51jTTqLjTTrGn4wD4D8g+KDrW9eGAEK+GABgABoPPg98Hvjz4ti2L" +
	"YtnWCQ+dVGmnVRpv//5YvX1F6xgChINCSRQ+Ozkr+yVZKnJV5yVcnJV5yVeyVZKnJV7JU5KuTkq85KvEuFwAFAMB" +
	"QkGjki47HZyV/OSv///4Xi9YvWJBoSDRSRTZKslWSrJVkqyVZKslWSrJVkqyVOSr2SolwagaASDQkGjk/ykqyf//" +
	"4Xi9YvWJGhIaEkim85K1ZMSSrykqyVOSr2SrJVkqyVZKslWSrJUS4XAAJoBIaEg0cm9ki5ydf//wvVReqi8YAoSD" +
	"QklXnJ9Ekr0pKsmUmUmUmUmUmUmUmUmUmUmJcLgAEUAwBQkGhJK/WSrJX//9Vi9esX1xINCQaEkq9k2Sokm1kqyV" +
	"ZKslWSrJVkykqyYklXsmJcGoDQCQ0JBo5N5SVOSvf//y1i+usXiRoSDRSZybSk2SpyVeyVZKslWSrJVkqyVZKslT" +
	"krUS4XAAUAkNCQ0cleO2SrJW"

func TestLocalPairReceivesAudioAndVideoRTP(t *testing.T) {
	fixture, err := base64.StdEncoding.DecodeString(testH264AccessUnit)
	if err != nil {
		t.Fatal(err)
	}
	frames, err := readH264Frames(bytes.NewReader(fixture))
	if err != nil {
		t.Fatalf("read embedded H.264 test frame: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	result, err := runLocalPair(ctx, frames, 800*time.Millisecond)
	if err != nil {
		t.Fatalf("run local Pion pair: %v", err)
	}
	if result.EvidenceType != "TEST" || !result.LocalOnly {
		t.Fatalf("result did not identify a local TEST: %+v", result)
	}
	if result.PublisherState != webrtcConnected || result.SubscriberState != webrtcConnected {
		t.Fatalf("PeerConnections not connected: publisher=%s subscriber=%s",
			result.PublisherState, result.SubscriberState)
	}
	if result.Audio.Codec != "audio/PCMU" || result.Audio.PacketsReceived < 10 {
		t.Fatalf("audio RTP not received: %+v", result.Audio)
	}
	if result.Video.Codec != "video/H264" || result.Video.PacketsReceived == 0 {
		t.Fatalf("video RTP not received: %+v", result.Video)
	}
	if result.Audio.FirstTimestamp == result.Audio.LastTimestamp {
		t.Fatalf("audio RTP timestamp did not advance: %+v", result.Audio)
	}
	if result.Video.FirstTimestamp == result.Video.LastTimestamp {
		t.Fatalf("video RTP timestamp did not advance: %+v", result.Video)
	}
}

func TestLocalSFURoutesAuthorizedStreamsAndRTCP(t *testing.T) {
	fixture, err := base64.StdEncoding.DecodeString(testH264AccessUnit)
	if err != nil {
		t.Fatal(err)
	}
	frames, err := readH264Frames(bytes.NewReader(fixture))
	if err != nil {
		t.Fatalf("read embedded H.264 test frame: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	result, err := runLocalSFUProof(ctx, frames, 1500*time.Millisecond)
	if err != nil {
		t.Fatalf("run local SFU proof: %v", err)
	}
	if result.EvidenceType != "TEST" || !result.LocalOnly {
		t.Fatalf("result did not identify a local TEST: %+v", result)
	}
	if result.PublisherState != webrtcConnected {
		t.Fatalf("publisher PeerConnection not connected: %s", result.PublisherState)
	}
	if !result.UnauthorizedSubscriptionDenied {
		t.Fatal("router accepted a viewer subscription without authorization")
	}
	if !result.CleanupVerified {
		t.Fatal("router retained tracks, viewers, or subscriptions after cleanup")
	}
	if len(result.ForwardingErrors) != 0 {
		t.Fatalf("router reported forwarding errors: %v", result.ForwardingErrors)
	}
	if len(result.Viewers) != 2 || len(result.UpstreamFeedback) != 2 {
		t.Fatalf("expected two viewers and two upstream feedback records: %+v", result)
	}

	expectedTracks := []string{"stream-red", "stream-blue"}
	seenSSRCs := make(map[uint32]struct{}, len(result.Viewers))
	for index, viewer := range result.Viewers {
		if viewer.RequestedTrackID != expectedTracks[index] ||
			len(viewer.ReceivedTrackIDs) != 1 ||
			viewer.ReceivedTrackIDs[0] != viewer.RequestedTrackID ||
			!viewer.OnlyRequested {
			t.Fatalf("viewer %s received an unrequested stream: %+v", viewer.ViewerID, viewer)
		}
		if viewer.PeerConnection != webrtcConnected || viewer.Received.PacketsReceived == 0 {
			t.Fatalf("viewer %s did not receive RTP over a connected PeerConnection: %+v",
				viewer.ViewerID, viewer)
		}
		if viewer.Received.SSRC == 0 {
			t.Fatalf("viewer %s received zero SSRC: %+v", viewer.ViewerID, viewer)
		}
		if _, exists := seenSSRCs[viewer.Received.SSRC]; exists {
			t.Fatalf("viewers share an egress SSRC: %+v", result.Viewers)
		}
		seenSSRCs[viewer.Received.SSRC] = struct{}{}
		if viewer.RetransmittedPackets == 0 ||
			viewer.FeedbackForwarded.NACKReceived != 1 ||
			viewer.FeedbackForwarded.NACKRetransmitted == 0 ||
			viewer.FeedbackForwarded.NACKForwarded == 0 ||
			viewer.FeedbackForwarded.PLIForwarded != 1 ||
			viewer.FeedbackForwarded.FIRForwarded != 1 {
			t.Fatalf("viewer %s RTCP feedback/retransmission was incomplete: %+v",
				viewer.ViewerID, viewer)
		}
	}
	for index, feedback := range result.UpstreamFeedback {
		if feedback.TrackID != expectedTracks[index] ||
			feedback.Counts.NACKForwarded != 1 ||
			feedback.Counts.PLIForwarded != 1 ||
			feedback.Counts.FIRForwarded != 1 {
			t.Fatalf("publisher did not receive track-mapped NACK/PLI/FIR: %+v", feedback)
		}
	}
}

const webrtcConnected = "connected"

func TestVideoFrameAssemblerRequiresCompleteContiguousFrame(t *testing.T) {
	assembler := &videoFrameAssembler{}
	push := func(sequence uint16, timestamp uint32, marker bool) (uint64, bool) {
		t.Helper()
		return assembler.push(&rtp.Packet{Header: rtp.Header{
			SequenceNumber: sequence,
			Timestamp:      timestamp,
			Marker:         marker,
		}})
	}

	if _, complete := push(100, 10, false); complete {
		t.Fatal("first frame has no known start boundary and must not be recorded")
	}
	if _, complete := push(101, 10, true); complete {
		t.Fatal("first frame has no known start boundary and must not be recorded")
	}
	if _, complete := push(102, 20, false); complete {
		t.Fatal("frame should not be recorded before its marker packet")
	}
	if frameID, complete := push(103, 20, true); !complete || frameID != 20 {
		t.Fatalf("complete frame = (%d, %v), want (20, true)", frameID, complete)
	}

	if _, complete := push(104, 30, false); complete {
		t.Fatal("frame should not be recorded before its marker packet")
	}
	if _, complete := push(106, 30, true); complete {
		t.Fatal("frame with a sequence gap must not be recorded")
	}
	if frameID, complete := push(107, 40, true); !complete || frameID != 40 {
		t.Fatalf("contiguous frame after gap recovery = (%d, %v), want (40, true)",
			frameID, complete)
	}
	if _, complete := push(107, 40, true); complete {
		t.Fatal("duplicate packet from the completed frame must not create another sample")
	}

	primed := &videoFrameAssembler{
		frameBoundaryKnown:     true,
		nextFrameFirstSequence: 500,
	}
	if _, complete := primed.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 500,
		Timestamp:      50,
	}}); complete {
		t.Fatal("frame should not be recorded before its marker packet")
	}
	if frameID, complete := primed.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 501,
		Timestamp:      50,
		Marker:         true,
	}}); !complete || frameID != 50 {
		t.Fatalf("frame with a verified initial sequence = (%d, %v), want (50, true)",
			frameID, complete)
	}

	reordered := &videoFrameAssembler{
		frameBoundaryKnown:     true,
		nextFrameFirstSequence: 600,
	}
	if _, complete := reordered.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 601,
		Timestamp:      60,
		Marker:         true,
	}}); complete {
		t.Fatal("marker arriving before an earlier fragment must wait for that fragment")
	}
	if frameID, complete := reordered.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 600,
		Timestamp:      60,
	}}); !complete || frameID != 60 {
		t.Fatalf("reordered complete frame = (%d, %v), want (60, true)", frameID, complete)
	}

	wrapped := &videoFrameAssembler{
		frameBoundaryKnown:     true,
		nextFrameFirstSequence: 65535,
	}
	if _, complete := wrapped.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 0,
		Timestamp:      70,
		Marker:         true,
	}}); complete {
		t.Fatal("wrapped marker arriving first must wait for the initial fragment")
	}
	if frameID, complete := wrapped.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 65535,
		Timestamp:      70,
	}}); !complete || frameID != 70 {
		t.Fatalf("wrapped reordered frame = (%d, %v), want (70, true)", frameID, complete)
	}

	lateRetransmission := &videoFrameAssembler{
		frameBoundaryKnown:     true,
		nextFrameFirstSequence: 800,
	}
	if frameID, complete := lateRetransmission.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 800,
		Timestamp:      80,
		Marker:         true,
	}}); !complete || frameID != 80 {
		t.Fatalf("first frame before late retransmission = (%d, %v), want (80, true)",
			frameID, complete)
	}
	if _, complete := lateRetransmission.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 801,
		Timestamp:      90,
	}}); complete {
		t.Fatal("next frame should wait for its marker")
	}
	if _, complete := lateRetransmission.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 800,
		Timestamp:      80,
		Marker:         true,
	}}); complete {
		t.Fatal("late packet from an older frame must be ignored")
	}
	if frameID, complete := lateRetransmission.push(&rtp.Packet{Header: rtp.Header{
		SequenceNumber: 802,
		Timestamp:      90,
		Marker:         true,
	}}); !complete || frameID != 90 {
		t.Fatalf("frame after late retransmission = (%d, %v), want (90, true)",
			frameID, complete)
	}
}

func TestNACKQueueDropsOldestAtCapacity(t *testing.T) {
	subscription := &sfuSubscription{
		nackQueue: make(chan queuedNACK, nackQueueSize),
	}
	for sequence := 1; sequence <= nackQueueSize+1; sequence++ {
		subscription.enqueueNACK(&rtcp.TransportLayerNack{SenderSSRC: uint32(sequence)})
	}

	if got := len(subscription.nackQueue); got != nackQueueSize {
		t.Fatalf("NACK queue depth = %d, want %d", got, nackQueueSize)
	}
	oldest := <-subscription.nackQueue
	if got := oldest.feedback.SenderSSRC; got != 2 {
		t.Fatalf("oldest retained NACK has sequence marker %d, want 2", got)
	}
	counts := subscription.feedbackSnapshot()
	if counts.NACKReceived != uint64(nackQueueSize+1) ||
		counts.NACKEnqueued != uint64(nackQueueSize+1) ||
		counts.NACKDroppedQueueFull != 1 ||
		counts.NACKQueueDepth != uint64(nackQueueSize-1) {
		t.Fatalf("unexpected NACK queue counters after overflow: %+v", counts)
	}
}

func TestNACKWorkerStopsAfterSubscriptionCloses(t *testing.T) {
	subscription := &sfuSubscription{
		active:    true,
		nackQueue: make(chan queuedNACK, 2),
	}
	subscription.nackQueue <- queuedNACK{feedback: &rtcp.TransportLayerNack{}}
	subscription.nackQueue <- queuedNACK{feedback: &rtcp.TransportLayerNack{}}
	subscription.stop()

	router := &sfuRouter{}
	router.nackWorker(subscription)
	if got := len(subscription.nackQueue); got != 1 {
		t.Fatalf("queued NACKs remaining after stop = %d, want 1", got)
	}
}

func TestNACKSelectionDeduplicatesCapsAndPrioritizesRecentSequence(t *testing.T) {
	now := time.Now()
	sequences := make([]uint16, maxSequencesPerNACK+2)
	for index := range sequences {
		sequences[index] = uint16(100 + index)
	}
	pairs := rtcp.NackPairsFromSequenceNumbers(sequences)
	lastSequence := uint16(100 + len(sequences))
	pairs = append(pairs, rtcp.NackPair{PacketID: sequences[len(sequences)-1]})
	retransmittedAt := map[uint16]time.Time{
		lastSequence - 2: now.Add(-100 * time.Millisecond),
		lastSequence - 3: now.Add(-time.Second),
	}

	fresh, duplicates, capped := selectNACKSequences(pairs, lastSequence, retransmittedAt, now)
	if len(fresh) != maxSequencesPerNACK {
		t.Fatalf("selected %d sequences, want %d", len(fresh), maxSequencesPerNACK)
	}
	if duplicates != 2 || capped != 1 {
		t.Fatalf("selection counters duplicates=%d capped=%d, want 2 and 1", duplicates, capped)
	}
	if fresh[0] != lastSequence-1 || fresh[1] != lastSequence-3 {
		t.Fatalf("fresh sequences start %v, want newest then expired-history sequence", fresh[:2])
	}
	if _, exists := retransmittedAt[lastSequence-3]; exists {
		t.Fatal("expired retransmission history was not pruned")
	}
}

func TestPrometheusMetricsExposeForwardingAndResourceSignals(t *testing.T) {
	subscription := &sfuSubscription{
		nackQueue: make(chan queuedNACK, nackQueueSize),
		feedback: sfuFeedbackCounts{
			NACKReceived:         3,
			NACKDroppedQueueFull: 1,
		},
	}
	subscription.nackQueue <- queuedNACK{feedback: &rtcp.TransportLayerNack{}}
	key := sfuTrackKey{PublisherID: "publisher", TrackID: "track"}
	router := &sfuRouter{
		tracks: map[sfuTrackKey]*sfuPublishedTrack{key: {}},
		viewers: map[string]*sfuViewer{
			"viewer": {subscriptions: map[sfuTrackKey]*sfuSubscription{key: subscription}},
		},
	}
	router.rtpForwarded.Store(12)
	router.rtpDropped.Store(2)
	router.rtpForwardNanos.Store(uint64(25 * time.Millisecond))
	router.rtpForwardSamples.Store(12)

	var output strings.Builder
	if err := router.writePrometheusMetrics(&output); err != nil {
		t.Fatalf("write Prometheus metrics: %v", err)
	}
	for _, metric := range []string{
		"hami_sfu_rtp_forward_seconds_sum",
		"hami_sfu_rtp_forward_errors_total 2",
		"hami_sfu_nack_queue_depth 1",
		"hami_sfu_nack_dropped_queue_full_total 1",
		"hami_process_cpu_seconds_total",
		"go_memstats_heap_alloc_bytes",
		"go_memstats_sys_bytes",
	} {
		if !strings.Contains(output.String(), metric) {
			t.Errorf("Prometheus output missing %q", metric)
		}
	}
}

func TestMetricsEndpointIsLoopbackOnlyAndServesPrometheus(t *testing.T) {
	router := &sfuRouter{}
	if _, err := router.startMetricsServer("0.0.0.0:0"); err == nil {
		t.Fatal("metrics endpoint accepted a non-loopback bind")
	}
	server, err := router.startMetricsServer("127.0.0.1:0")
	if err != nil {
		t.Fatalf("start loopback metrics endpoint: %v", err)
	}
	t.Cleanup(func() {
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		if err := server.Shutdown(ctx); err != nil {
			t.Errorf("shut down metrics endpoint: %v", err)
		}
	})
	response, err := http.Get("http://" + server.Addr + "/metrics")
	if err != nil {
		t.Fatalf("scrape local metrics endpoint: %v", err)
	}
	defer response.Body.Close()
	body, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read metrics response: %v", err)
	}
	if response.StatusCode != http.StatusOK ||
		!strings.Contains(string(body), "hami_sfu_nack_queue_depth 0") {
		t.Fatalf("metrics response status=%d body=%q", response.StatusCode, body)
	}
}

func TestPairNegotiationTimeoutNamesPairAndStates(t *testing.T) {
	offerer, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("create offerer: %v", err)
	}
	answerer, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		_ = offerer.Close()
		t.Fatalf("create answerer: %v", err)
	}
	defer offerer.Close()
	defer answerer.Close()

	err = negotiateLoopbackPeersWithTimeout(
		context.Background(),
		"viewer[17] hami-sfu-viewer-18",
		0,
		offerer,
		answerer,
		"m=video",
	)
	if err == nil {
		t.Fatal("negotiation unexpectedly succeeded with an expired per-pair deadline")
	}
	for _, expected := range []string{
		"viewer[17] hami-sfu-viewer-18",
		"per-pair timeout",
		"offerer=",
		"answerer=",
	} {
		if !strings.Contains(err.Error(), expected) {
			t.Errorf("negotiation error %q does not include %q", err, expected)
		}
	}
}
