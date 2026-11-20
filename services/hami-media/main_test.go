package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
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

func TestReadH264FramesPreservesNonIDRSlices(t *testing.T) {
	fixture, err := base64.StdEncoding.DecodeString(testH264AccessUnit)
	if err != nil {
		t.Fatal(err)
	}
	idrFrames, err := readH264Frames(bytes.NewReader(fixture))
	if err != nil {
		t.Fatalf("read embedded IDR fixture: %v", err)
	}

	withPFrame := append(append([]byte(nil), fixture...), 0, 0, 0, 1, 0x41, 0x80)
	frames, err := readH264Frames(bytes.NewReader(withPFrame))
	if err != nil {
		t.Fatalf("read H.264 fixture with a non-IDR slice: %v", err)
	}
	if len(frames) != len(idrFrames)+1 {
		t.Fatalf("parsed %d frames, want original %d plus one non-IDR slice",
			len(frames), len(idrFrames))
	}
	if !bytes.HasSuffix(frames[len(frames)-1].Data, []byte{0, 0, 0, 1, 0x41, 0x80}) {
		t.Fatal("last media sample does not retain the non-IDR slice")
	}
}

type stubUDPMuxForTest struct {
	conn       net.PacketConn
	closeCalls int
}

func (m *stubUDPMuxForTest) GetConn(string, net.Addr) (net.PacketConn, error) {
	return m.conn, nil
}

func (m *stubUDPMuxForTest) RemoveConnByUfrag(string) {}

func (m *stubUDPMuxForTest) GetListenAddresses() []net.Addr {
	return []net.Addr{m.conn.LocalAddr()}
}

func (m *stubUDPMuxForTest) Close() error {
	m.closeCalls++
	return nil
}

func TestCountingUDPMuxCountsPeerWritesWithoutClosingSharedMux(t *testing.T) {
	sharedSocket, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		t.Fatal(err)
	}
	effectiveReadBuffer, err := setUDPConnReadBuffer(sharedSocket, 64*1024)
	if err != nil {
		t.Fatal(err)
	}
	if effectiveReadBuffer <= 0 {
		t.Fatalf("effective UDP receive buffer = %d, want positive size", effectiveReadBuffer)
	}
	t.Cleanup(func() {
		if err := sharedSocket.Close(); err != nil {
			t.Errorf("close shared UDP socket: %v", err)
		}
	})
	receiver, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := receiver.Close(); err != nil {
			t.Errorf("close receiver UDP socket: %v", err)
		}
	})

	underlying := &stubUDPMuxForTest{conn: sharedSocket}
	mux := newCountingUDPMux(underlying)
	conn, err := mux.GetConn("viewer", receiver.LocalAddr())
	if err != nil {
		t.Fatal(err)
	}
	if n, err := conn.WriteTo([]byte{1}, receiver.LocalAddr()); err != nil || n != 1 {
		t.Fatalf("write through counting mux: n=%d err=%v", n, err)
	}
	if err := receiver.SetReadDeadline(time.Now().Add(time.Second)); err != nil {
		t.Fatal(err)
	}
	buffer := make([]byte, 1)
	if n, _, err := receiver.ReadFrom(buffer); err != nil || n != 1 {
		t.Fatalf("read through shared socket: n=%d err=%v", n, err)
	}
	if got := mux.conn.nonSTUNPacketsWritten.Load(); got != 1 {
		t.Fatalf("nonSTUNPacketsWritten = %d, want 1", got)
	}
	if err := mux.Close(); err != nil {
		t.Fatal(err)
	}
	if underlying.closeCalls != 0 {
		t.Fatalf("shared mux close calls = %d, want 0", underlying.closeCalls)
	}
}

func TestPacketReadCountingConnCountsDatagrams(t *testing.T) {
	receiver, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		t.Fatal(err)
	}
	counted := &packetReadCountingConn{PacketConn: receiver}
	t.Cleanup(func() {
		if err := counted.Close(); err != nil {
			t.Errorf("close counted UDP socket: %v", err)
		}
	})

	sender, err := net.DialUDP("udp4", nil, receiver.LocalAddr().(*net.UDPAddr))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := sender.Close(); err != nil {
			t.Errorf("close sender UDP socket: %v", err)
		}
	})
	if _, err := sender.Write([]byte{1}); err != nil {
		t.Fatal(err)
	}
	if err := counted.SetReadDeadline(time.Now().Add(time.Second)); err != nil {
		t.Fatal(err)
	}
	buffer := make([]byte, 1)
	if n, _, err := counted.ReadFrom(buffer); err != nil || n != 1 {
		t.Fatalf("read datagram: n=%d err=%v", n, err)
	}
	if got := counted.packetsRead.Load(); got != 1 {
		t.Fatalf("packetsRead = %d, want 1", got)
	}
	if got := counted.nonSTUNPacketsRead.Load(); got != 1 {
		t.Fatalf("nonSTUNPacketsRead = %d, want 1", got)
	}
	if got := counted.stunPacketsRead.Load(); got != 0 {
		t.Fatalf("stunPacketsRead = %d, want 0", got)
	}
	if n, err := counted.WriteTo([]byte{2}, sender.LocalAddr()); err != nil || n != 1 {
		t.Fatalf("write datagram: n=%d err=%v", n, err)
	}
	if got := counted.packetsWritten.Load(); got != 1 {
		t.Fatalf("packetsWritten = %d, want 1", got)
	}
	if got := counted.bytesWritten.Load(); got != 1 {
		t.Fatalf("bytesWritten = %d, want 1", got)
	}
	if got := counted.nonSTUNPacketsWritten.Load(); got != 1 {
		t.Fatalf("nonSTUNPacketsWritten = %d, want 1", got)
	}
	if got := counted.stunPacketsWritten.Load(); got != 0 {
		t.Fatalf("stunPacketsWritten = %d, want 0", got)
	}
	if err := sender.SetReadDeadline(time.Now().Add(time.Second)); err != nil {
		t.Fatal(err)
	}
	nonSTUNBuffer := make([]byte, 1)
	if n, err := sender.Read(nonSTUNBuffer); err != nil || n != 1 {
		t.Fatalf("read non-STUN datagram: n=%d err=%v", n, err)
	}

	stunPacket := []byte{
		0x00, 0x01, 0x00, 0x00, 0x21, 0x12, 0xa4, 0x42,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
	}
	if n, err := counted.WriteTo(stunPacket, sender.LocalAddr()); err != nil || n != len(stunPacket) {
		t.Fatalf("write STUN datagram: n=%d err=%v", n, err)
	}
	if err := sender.SetReadDeadline(time.Now().Add(time.Second)); err != nil {
		t.Fatal(err)
	}
	stunBuffer := make([]byte, len(stunPacket))
	if n, err := sender.Read(stunBuffer); err != nil || n != len(stunPacket) {
		t.Fatalf("read STUN datagram: n=%d err=%v", n, err)
	}
	if got := counted.packetsWritten.Load(); got != 2 {
		t.Fatalf("packetsWritten = %d, want 2", got)
	}
	if got := counted.stunPacketsWritten.Load(); got != 1 {
		t.Fatalf("stunPacketsWritten = %d, want 1", got)
	}
	destination := counted.firstNonSTUNWriteDestination.Load()
	if destination == nil || *destination != sender.LocalAddr().String() {
		t.Fatalf("first non-STUN destination = %v, want %s", destination, sender.LocalAddr())
	}
}

func TestAggregateSFUSocketCountsDeduplicatesSharedRouterSocket(t *testing.T) {
	sharedRouterSocket := &packetReadCountingConn{}
	sharedRouterSocket.packetsWritten.Store(10)
	sharedRouterSocket.stunPacketsWritten.Store(3)
	sharedRouterSocket.nonSTUNPacketsWritten.Store(7)
	otherRouterSocket := &packetReadCountingConn{}
	otherRouterSocket.packetsWritten.Store(5)
	otherRouterSocket.stunPacketsWritten.Store(1)
	otherRouterSocket.nonSTUNPacketsWritten.Store(4)

	clientSockets := []*packetReadCountingConn{
		{},
		{},
		{},
	}
	for index, conn := range clientSockets {
		conn.packetsRead.Store(uint64(index + 2))
		conn.stunPacketsRead.Store(uint64(index + 1))
		conn.nonSTUNPacketsRead.Store(uint64(index + 1))
	}

	totals := aggregateSFUSocketCounts([]viewerEndpoint{
		{routerSocketConn: sharedRouterSocket, socketConn: clientSockets[0]},
		{routerSocketConn: sharedRouterSocket, socketConn: clientSockets[1]},
		{routerSocketConn: otherRouterSocket, socketConn: clientSockets[2]},
	})
	if totals.routerSockets != 2 || totals.routerWrites != 15 ||
		totals.routerSTUNWrites != 4 || totals.routerNonSTUNWrites != 11 {
		t.Fatalf("unexpected router socket aggregates: %+v", totals)
	}
	if totals.clientSockets != 3 || totals.clientReads != 9 ||
		totals.clientSTUNReads != 6 || totals.clientNonSTUNReads != 6 {
		t.Fatalf("unexpected client socket aggregates: %+v", totals)
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

func TestRTPQueueDropsOldestPacketWithoutBlocking(t *testing.T) {
	queue := make(chan queuedRTP, 2)
	subscription := &sfuSubscription{active: true, rtpQueue: queue}
	for sequence := uint16(1); sequence <= 3; sequence++ {
		dropped, err := subscription.enqueueRTP(&rtp.Packet{
			Header: rtp.Header{SequenceNumber: sequence},
		})
		if err != nil {
			t.Fatalf("enqueue RTP sequence %d: %v", sequence, err)
		}
		if dropped != (sequence == 3) {
			t.Fatalf("sequence %d dropped=%v, want %v", sequence, dropped, sequence == 3)
		}
	}
	if got := len(queue); got != cap(queue) {
		t.Fatalf("RTP queue depth = %d, want capacity %d", got, cap(queue))
	}
	if got := subscription.rtpQueueEnqueued.Load(); got != 3 {
		t.Fatalf("RTP enqueued count = %d, want 3", got)
	}
	if got := subscription.rtpQueueDropped.Load(); got != 1 {
		t.Fatalf("RTP queue drop count = %d, want 1", got)
	}
	for _, want := range []uint16{2, 3} {
		entry := <-queue
		if entry.enqueuedAt.IsZero() {
			t.Fatal("queued RTP entry has no enqueue timestamp")
		}
		if got := entry.packet.SequenceNumber; got != want {
			t.Fatalf("queued sequence = %d, want %d", got, want)
		}
	}
}

func TestRTPQueueSharesPayloadAndCopiesMutableHeader(t *testing.T) {
	packet := &rtp.Packet{
		Header: rtp.Header{
			SSRC:           11,
			SequenceNumber: 7,
			CSRC:           []uint32{22},
		},
		Payload: []byte{1, 2, 3},
	}
	if err := packet.Header.SetExtension(1, []byte{4, 5}); err != nil {
		t.Fatalf("set input header extension: %v", err)
	}

	subscriptions := []*sfuSubscription{
		{active: true, rtpQueue: make(chan queuedRTP, 1)},
		{active: true, rtpQueue: make(chan queuedRTP, 1)},
	}
	queued := make([]*rtp.Packet, len(subscriptions))
	for index, subscription := range subscriptions {
		if _, err := subscription.enqueueRTP(packet); err != nil {
			t.Fatalf("enqueue packet for subscription %d: %v", index, err)
		}
		queued[index] = (<-subscription.rtpQueue).packet
	}

	if &queued[0].Payload[0] != &packet.Payload[0] ||
		&queued[1].Payload[0] != &packet.Payload[0] ||
		&queued[0].Payload[0] != &queued[1].Payload[0] {
		t.Fatal("queued subscriptions must share the source payload")
	}

	for index, copy := range queued {
		if &copy.Header.CSRC[0] == &packet.Header.CSRC[0] {
			t.Fatalf("subscription %d shares mutable CSRC storage", index)
		}
		copy.Header.SSRC = uint32(index + 30)
		copy.Header.CSRC[0] = uint32(index + 40)
		if err := copy.Header.SetExtension(1, []byte{byte(index + 60)}); err != nil {
			t.Fatalf("set subscription %d header extension: %v", index, err)
		}
	}
	if packet.Header.SSRC != 11 || packet.Header.CSRC[0] != 22 ||
		!bytes.Equal(packet.Header.GetExtension(1), []byte{4, 5}) {
		t.Fatal("mutating a queued header changed the source header")
	}
	if queued[0].Header.SSRC == queued[1].Header.SSRC ||
		queued[0].Header.CSRC[0] == queued[1].Header.CSRC[0] ||
		bytes.Equal(queued[0].Header.GetExtension(1), queued[1].Header.GetExtension(1)) {
		t.Fatal("subscription headers must be independent")
	}
}

func TestH264IDRDetectionSupportsSingleNALAggregationAndFUStart(t *testing.T) {
	tests := []struct {
		name    string
		payload []byte
		want    bool
	}{
		{name: "IDR single NAL", payload: []byte{0x65, 0x88}, want: true},
		{name: "non-IDR single NAL", payload: []byte{0x41, 0x80}},
		{name: "IDR STAP-A", payload: []byte{0x78, 0, 2, 0x67, 1, 0, 2, 0x65, 2}, want: true},
		{name: "IDR FU-A start", payload: []byte{0x7c, 0x85}, want: true},
		{name: "IDR FU-A continuation", payload: []byte{0x7c, 0x45}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := isH264IDRStart(test.payload); got != test.want {
				t.Fatalf("isH264IDRStart(%x) = %v, want %v", test.payload, got, test.want)
			}
		})
	}
}

func TestKeyframeRecoverySkipsInterFramesButAllowsParameterSetsAndIDR(t *testing.T) {
	subscription := &sfuSubscription{h264Video: true}
	subscription.keyframeNeededAt.Store(1)
	tests := []struct {
		name        string
		payload     []byte
		wantAllowed bool
		wantIDR     bool
	}{
		{name: "non-IDR slice", payload: []byte{0x41, 0x80}},
		{name: "SPS", payload: []byte{0x67, 1}, wantAllowed: true},
		{name: "PPS", payload: []byte{0x68, 1}, wantAllowed: true},
		{name: "IDR start", payload: []byte{0x65, 0x88}, wantAllowed: true, wantIDR: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			allowed, idr := subscription.allowRTPDuringKeyframeRecovery(&rtp.Packet{Payload: test.payload})
			if allowed != test.wantAllowed || idr != test.wantIDR {
				t.Fatalf("recovery decision = (%v, %v), want (%v, %v)",
					allowed, idr, test.wantAllowed, test.wantIDR)
			}
		})
	}
}

func TestStaleRTPIsIntentionallyShedAndMarksKeyframeRecovery(t *testing.T) {
	router := &sfuRouter{}
	subscription := &sfuSubscription{active: true, h264Video: true}
	router.forwardQueuedRTP(subscription, queuedRTP{
		packet:     &rtp.Packet{Payload: []byte{0x41, 0x80}},
		enqueuedAt: time.Now().Add(-nackMaxQueueAge - time.Second),
	})
	if subscription.keyframeNeededAt.Load() == 0 {
		t.Fatal("stale H.264 packet did not mark the subscription as needing a keyframe")
	}
	if router.rtpQueueDropped.Load() != 1 || router.rtpIntentionalShed.Load() != 1 {
		t.Fatalf("stale RTP counters: queueDrops=%d intentionalShed=%d, want 1 each",
			router.rtpQueueDropped.Load(), router.rtpIntentionalShed.Load())
	}
	if router.rtpDropped.Load() != 0 || len(router.errorsSnapshot()) != 0 {
		t.Fatalf("intentional stale shed was recorded as an error: dropped=%d errors=%v",
			router.rtpDropped.Load(), router.errorsSnapshot())
	}
}

func TestKeyframeRecoveryDurationIsRecordedAfterRecovery(t *testing.T) {
	subscription := &sfuSubscription{h264Video: true}
	if !subscription.markNeedsKeyframe() {
		t.Fatal("first keyframe-needed transition was not recorded")
	}
	if subscription.markNeedsKeyframe() {
		t.Fatal("duplicate keyframe-needed transition replaced the recovery start")
	}
	duration, recovered := subscription.completeKeyframeRecovery()
	if !recovered || duration < 0 {
		t.Fatalf("keyframe recovery duration = %s, recovered=%v", duration, recovered)
	}
	router := &sfuRouter{}
	router.recordRTPKeyframeRecovery(duration)
	if router.rtpRecoverySamples.Load() != 1 || router.rtpRecoveryNanos.Load() != uint64(duration) ||
		router.rtpRecoveryMaxNanos.Load() != uint64(duration) {
		t.Fatalf("recovery counters samples=%d totalNs=%d maxNs=%d, duration=%d",
			router.rtpRecoverySamples.Load(), router.rtpRecoveryNanos.Load(),
			router.rtpRecoveryMaxNanos.Load(), duration)
	}
}

func TestRecoveryKeyframeRequestsAreLimitedPerPublisher(t *testing.T) {
	router := &sfuRouter{}
	start := time.Now()
	if !router.allowKeyframeRequest("publisher-a", start) {
		t.Fatal("first keyframe request for publisher was suppressed")
	}
	if router.allowKeyframeRequest("publisher-a", start.Add(time.Second-time.Nanosecond)) {
		t.Fatal("second request inside one second was allowed")
	}
	if !router.allowKeyframeRequest("publisher-a", start.Add(time.Second)) {
		t.Fatal("request at the one-second boundary was suppressed")
	}
	if !router.allowKeyframeRequest("publisher-b", start.Add(time.Millisecond)) {
		t.Fatal("independent publisher request was suppressed")
	}
}

func TestMeasurementPassAllowsIntentionalRTPSheddingButRejectsWriteErrors(t *testing.T) {
	result := sfuProofResult{
		PublisherState:                 peerConnectionConnected,
		UnauthorizedSubscriptionDenied: true,
		CleanupVerified:                true,
		RTPQueueDrops:                  2,
		RTPIntentionalShed:             2,
		Viewers: []sfuViewerResult{{
			Latency:        &Summary{Pass: true},
			OnlyRequested:  true,
			PeerConnection: peerConnectionConnected,
			FeedbackForwarded: sfuFeedbackCounts{
				NACKReceived:      1,
				NACKRetransmitted: 1,
				NACKForwarded:     1,
				PLIForwarded:      1,
				FIRForwarded:      1,
			},
		}},
	}
	if !sfuMeasurementPass(result, 1, true) {
		t.Fatal("measurement pass rejected intentional RTP shedding")
	}
	result.RTPWriteErrors = 1
	if sfuMeasurementPass(result, 1, true) {
		t.Fatal("measurement pass accepted an RTP write error")
	}
}

func TestCachedPacketsSharePayloadAndCopyMutableHeader(t *testing.T) {
	stored := &rtp.Packet{
		Header: rtp.Header{
			SSRC:           11,
			SequenceNumber: 42,
			CSRC:           []uint32{22},
		},
		Payload: []byte{1, 2, 3},
	}
	if err := stored.Header.SetExtension(1, []byte{4, 5}); err != nil {
		t.Fatalf("set stored header extension: %v", err)
	}
	track := &sfuPublishedTrack{
		packetCache: map[uint16]*rtp.Packet{42: stored},
	}

	packets, missing := track.cachedPackets([]uint16{42, 43, 42})
	if len(packets) != 1 || len(missing) != 1 || missing[0] != 43 {
		t.Fatalf("cached packets=%v, missing=%v; want one packet and missing sequence 43",
			packets, missing)
	}
	if packets[0] == stored {
		t.Fatal("cached packet header was not copied")
	}
	if &packets[0].Payload[0] != &stored.Payload[0] {
		t.Fatal("cached retransmission payload was copied")
	}
	if &packets[0].Header.CSRC[0] == &stored.Header.CSRC[0] {
		t.Fatal("cached retransmission shares mutable CSRC storage")
	}
	packets[0].Header.SSRC = 33
	packets[0].Header.CSRC[0] = 44
	if err := packets[0].Header.SetExtension(1, []byte{6, 7}); err != nil {
		t.Fatalf("set returned header extension: %v", err)
	}
	if stored.Header.SSRC != 11 || stored.Header.CSRC[0] != 22 ||
		!bytes.Equal(stored.Header.GetExtension(1), []byte{4, 5}) {
		t.Fatal("mutating a returned header changed the cached packet")
	}
	if !bytes.Equal(packets[0].Payload, []byte{1, 2, 3}) {
		t.Fatalf("cached payload changed: %v", packets[0].Payload)
	}
}

func TestBuildSFUScaleProofConfigSupportsTwentyByTwoHundredFifty(t *testing.T) {
	config, err := buildSFUScaleProofConfig(20, 250)
	if err != nil {
		t.Fatalf("build 20-publisher/250-viewer config: %v", err)
	}
	if got, want := config.proofID, "m6h-scale-p20-vpp250-v5000-fps5"; got != want {
		t.Fatalf("proof ID = %q, want %q", got, want)
	}
	if len(config.tracks) != 20 || len(config.viewerTrackIndexes) != 5000 {
		t.Fatalf("scale config has %d publishers and %d viewers, want 20 and 5000",
			len(config.tracks), len(config.viewerTrackIndexes))
	}
	if config.videoInterval != 200*time.Millisecond {
		t.Fatalf("video interval = %s, want 200ms (5 fps)", config.videoInterval)
	}
	viewersPerTrack := make([]int, len(config.tracks))
	for _, trackIndex := range config.viewerTrackIndexes {
		viewersPerTrack[trackIndex]++
	}
	for index, viewers := range viewersPerTrack {
		if viewers != 250 {
			t.Fatalf("track %d has %d viewers, want 250", index, viewers)
		}
	}
}

func TestBuildSFUScaleProofConfigEnforcesTotalViewerLimit(t *testing.T) {
	if _, err := buildSFUScaleProofConfig(21, 250); err == nil {
		t.Fatal("scale config accepted more than 5000 total viewers")
	}
}

func BenchmarkCachedPackets(b *testing.B) {
	track := &sfuPublishedTrack{
		packetCache: map[uint16]*rtp.Packet{
			42: {
				Header:  rtp.Header{SequenceNumber: 42},
				Payload: make([]byte, 1200),
			},
		},
	}
	sequences := []uint16{42}
	b.ReportAllocs()
	b.SetBytes(int64(len(track.packetCache[42].Payload)))
	for i := 0; i < b.N; i++ {
		packets, missing := track.cachedPackets(sequences)
		if len(packets) != 1 || len(missing) != 0 {
			b.Fatal("cached packet lookup returned an unexpected result")
		}
	}
}

func TestProofFailureIsWrittenAsJSON(t *testing.T) {
	const wantError = "feedback wait timed out"
	var output bytes.Buffer
	if err := writeProofError(&output, errors.New(wantError)); err != nil {
		t.Fatalf("encode proof error: %v", err)
	}

	var got proofErrorResult
	if err := json.Unmarshal(output.Bytes(), &got); err != nil {
		t.Fatalf("decode proof error JSON: %v", err)
	}
	if got.Error != wantError {
		t.Fatalf("proof error = %q, want %q", got.Error, wantError)
	}
}

func TestHeapBudgetMonitorCancelsProofWhenLimitIsReached(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	done := startHeapBudgetMonitor(ctx, 1, cancel)
	select {
	case err := <-done:
		if err == nil || !strings.Contains(err.Error(), "Go heap budget exceeded") {
			t.Fatalf("heap budget result = %v, want explicit budget error", err)
		}
	case <-time.After(time.Second):
		t.Fatal("heap budget monitor did not abort at the exceeded limit")
	}
	if !errors.Is(ctx.Err(), context.Canceled) {
		t.Fatalf("proof context error = %v, want context cancellation", ctx.Err())
	}
}

func TestHeapBudgetCanBeDisabled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	done := startHeapBudgetMonitor(ctx, 0, cancel)
	if err, ok := <-done; ok || err != nil {
		t.Fatalf("disabled monitor result = %v, open=%t; want closed without error", err, ok)
	}
	if ctx.Err() != nil {
		t.Fatalf("disabled monitor canceled proof context: %v", ctx.Err())
	}
}

func TestM7HHeapProfileOffsetsFitRunDuration(t *testing.T) {
	tests := []struct {
		name     string
		duration time.Duration
		want     []time.Duration
	}{
		{
			name:     "short run omits scheduled captures",
			duration: 89 * time.Second,
			want:     nil,
		},
		{
			name:     "one capture with time to complete",
			duration: 90 * time.Second,
			want:     []time.Duration{60 * time.Second},
		},
		{
			name:     "all captures with time to complete",
			duration: 150 * time.Second,
			want:     []time.Duration{60 * time.Second, 90 * time.Second, 120 * time.Second},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := m7hHeapProfileOffsetsForDuration(tt.duration); !reflect.DeepEqual(got, tt.want) {
				t.Fatalf("profile offsets for %s = %v, want %v", tt.duration, got, tt.want)
			}
		})
	}
}

func TestWaitForSFUFeedbackReturnsPartialCountsOnContextTimeout(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
	defer cancel()

	counts, err := waitForSFUFeedback(
		ctx,
		make(chan sfuFeedbackEvent),
		[]sfuMediaSource{{key: sfuTrackKey{TrackID: "track-1"}}},
		nil,
		map[string]uint64{"track-1": 1},
	)
	if err == nil || !strings.Contains(err.Error(), "timed out waiting for translated") {
		t.Fatalf("wait error = %v, want context timeout", err)
	}
	if got := counts["track-1"]; got != (sfuFeedbackCounts{}) {
		t.Fatalf("partial feedback counts = %+v, want the observed zero counts", got)
	}
}

func TestIncompleteM7HViewerIDsSelectsOneUnmetTrack(t *testing.T) {
	viewers := []viewerEndpoint{
		{id: "viewer-1", key: sfuTrackKey{TrackID: "track-1"}},
		{id: "viewer-1-duplicate", key: sfuTrackKey{TrackID: "track-1"}},
		{id: "viewer-2", key: sfuTrackKey{TrackID: "track-2"}},
		{id: "viewer-3", key: sfuTrackKey{TrackID: "track-3"}},
		{id: "viewer-4", key: sfuTrackKey{TrackID: "track-4"}},
		{id: "viewer-5", key: sfuTrackKey{TrackID: "track-5"}},
		{id: "viewer-6", key: sfuTrackKey{TrackID: "track-6"}},
		{id: "viewer-complete", key: sfuTrackKey{TrackID: "track-complete"}},
	}
	expected := map[string]uint64{
		"track-1": 1, "track-2": 1, "track-3": 1, "track-4": 1,
		"track-5": 1, "track-6": 1, "track-complete": 1,
	}
	counts := map[string]sfuFeedbackCounts{
		"track-complete": {NACKForwarded: 1, PLIForwarded: 1, FIRForwarded: 1},
	}

	got := incompleteM7HViewerIDs(viewers, counts, expected)
	want := []string{"viewer-1"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("incomplete viewers = %v, want %v", got, want)
	}
}

func TestM7HStatsHandlerStopsAfterRequestCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	request := httptest.NewRequest(
		http.MethodPost,
		"/stats",
		strings.NewReader(`{"viewer_ids":["viewer-1"],"include_ice_candidate_pairs":true}`),
	).WithContext(ctx)
	request.Header.Set("Authorization", "Bearer test-token")
	response := httptest.NewRecorder()

	router := &sfuRouter{}
	router.mu.Lock()
	server := &m7hRemoteSFUServer{
		router: router,
		viewers: map[string]viewerEndpoint{
			"viewer-1": {id: "viewer-1", key: sfuTrackKey{TrackID: "track-1"}},
		},
	}
	started := make(chan struct{})
	done := make(chan struct{})
	go func() {
		close(started)
		server.handleStats("test-token")(response, request)
		close(done)
	}()
	<-started
	select {
	case <-done:
	case <-time.After(200 * time.Millisecond):
		router.mu.Unlock()
		<-done
		t.Fatal("canceled stats request waited for a router feedback snapshot")
	}
	router.mu.Unlock()
	if response.Body.Len() != 0 {
		t.Fatalf("canceled stats response body = %q, want no response", response.Body.String())
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

func TestNACKExpectedSequenceFilterPreservesOnlyProofRequests(t *testing.T) {
	expected := map[uint16]struct{}{
		0:  {},
		20: {},
	}
	pairs := rtcp.NackPairsFromSequenceNumbers([]uint16{65535, 0, 20, 100})
	if !nackContainsExpectedSequence(pairs, expected) {
		t.Fatal("NACK pair list did not retain expected wrapped and direct sequences")
	}
	if nackContainsExpectedSequence(pairs, map[uint16]struct{}{101: {}}) {
		t.Fatal("NACK pair list matched an unrequested sequence")
	}
	if nackContainsExpectedSequence(pairs, nil) {
		t.Fatal("NACK pair list matched an empty expectation set")
	}
}

func TestNACKRTCPPacketsSplitAtReportLimitWithoutLosingSequences(t *testing.T) {
	sequences := make([]uint16, maxSequencesPerNACK)
	for index := range sequences {
		sequences[index] = uint16(index * 17)
	}

	packets := makeNACKRTCPPackets(1, 2, sequences)
	if len(packets) != 3 {
		t.Fatalf("got %d NACK packets, want 3", len(packets))
	}

	var forwarded []uint16
	compoundSize := 0
	for index, packet := range packets {
		nack, ok := packet.(*rtcp.TransportLayerNack)
		if !ok {
			t.Fatalf("packet %d has type %T, want *rtcp.TransportLayerNack", index, packet)
		}
		if len(nack.Nacks) > maxNACKPairsPerRTCPPacket {
			t.Fatalf("packet %d has %d NACK pairs, limit is %d",
				index, len(nack.Nacks), maxNACKPairsPerRTCPPacket)
		}
		for _, pair := range nack.Nacks {
			forwarded = append(forwarded, pair.PacketList()...)
		}
		raw, err := rtcp.Marshal([]rtcp.Packet{packet})
		if err != nil {
			t.Fatalf("marshal NACK packet %d: %v", index, err)
		}
		if len(raw) >= 1500 {
			t.Fatalf("NACK packet %d is %d bytes, exceeds Pion's 1500-byte read buffer",
				index, len(raw))
		}
		compoundSize += len(raw)
	}
	if len(forwarded) != len(sequences) {
		t.Fatalf("forwarded %d sequences, want %d", len(forwarded), len(sequences))
	}
	for index, sequence := range sequences {
		if forwarded[index] != sequence {
			t.Fatalf("forwarded sequence %d = %d, want %d", index, forwarded[index], sequence)
		}
	}
	if compoundSize <= 1500 {
		t.Fatalf("combined RTCP size = %d bytes, want more than Pion's 1500-byte receive buffer", compoundSize)
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
	router.rtpQueueDropped.Store(4)
	router.rtpIntentionalShed.Store(6)
	router.rtpDropped.Store(2)
	router.rtpRecoverySamples.Store(2)
	router.rtpRecoveryNanos.Store(uint64(500 * time.Millisecond))
	router.rtpRecoveryMaxNanos.Store(uint64(300 * time.Millisecond))
	router.rtpForwardNanos.Store(uint64(25 * time.Millisecond))
	router.rtpForwardSamples.Store(12)

	var output strings.Builder
	if err := router.writePrometheusMetrics(&output); err != nil {
		t.Fatalf("write Prometheus metrics: %v", err)
	}
	for _, metric := range []string{
		"hami_sfu_rtp_forward_seconds_sum",
		"hami_sfu_rtp_forward_errors_total 2",
		"hami_sfu_rtp_queue_dropped_total 4",
		"hami_sfu_rtp_intentional_shed_total 6",
		"hami_sfu_rtp_keyframe_recoveries_total 2",
		"hami_sfu_rtp_keyframe_recovery_seconds_sum 0.5",
		"hami_sfu_rtp_keyframe_recovery_seconds_max 0.3",
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

func TestM7HSFUReceiveStallDetectorRequiresArmedConsecutiveSamples(t *testing.T) {
	detector := m7hSFUReceiveStallDetector{publisherCount: 3000}
	sendCtx := context.Background()

	for sample := 1; sample <= 10; sample++ {
		if detector.observeDuringSend(sendCtx, 0, 3000) {
			t.Fatalf("startup zero-packet sample %d triggered a stall", sample)
		}
	}
	if detector.observeDuringSend(sendCtx, 1, 3000) {
		t.Fatal("packet-bearing sample triggered a stall")
	}
	if detector.observeDuringSend(sendCtx, 0, 2999) {
		t.Fatal("partially stale sample triggered a stall")
	}
	for sample := 1; sample < 5; sample++ {
		if detector.observeDuringSend(sendCtx, 0, 3000) {
			t.Fatalf("starved sample %d triggered before the fifth consecutive sample", sample)
		}
	}
	if !detector.observeDuringSend(sendCtx, 0, 3000) {
		t.Fatal("fifth consecutive zero-packet all-stale sample did not trigger")
	}
}

func TestM7HSFUReceiveStallIgnoresExpiredSendContext(t *testing.T) {
	sendCtx, cancel := context.WithCancel(context.Background())
	detector := m7hSFUReceiveStallDetector{publisherCount: 3000}
	if detector.observeDuringSend(sendCtx, 1, 3000) {
		t.Fatal("packet-bearing sample triggered a stall")
	}
	cancel()

	for sample := 1; sample <= 10; sample++ {
		if detector.observeDuringSend(sendCtx, 0, 3000) {
			t.Fatalf("expired send context triggered on sample %d", sample)
		}
	}
}

func TestM7HPublisherSendStallRequiresActiveSendContext(t *testing.T) {
	sendCtx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if !m7hPublisherSendStallDetected(sendCtx, 3000, 0, 3000) {
		t.Fatal("active all-stale publisher sample did not trigger")
	}
	if m7hPublisherSendStallDetected(sendCtx, 3000, 1, 3000) {
		t.Fatal("publisher sample with active sends triggered a stall")
	}
	if m7hPublisherSendStallDetected(sendCtx, 3000, 0, 2999) {
		t.Fatal("partially stale publisher sample triggered a stall")
	}

	cancel()
	if m7hPublisherSendStallDetected(sendCtx, 3000, 0, 3000) {
		t.Fatal("normal send-context expiry triggered a stall")
	}
}

func TestM7HRemoteSFUGoroutineProfileWritesLocalFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "goroutine.pprof")
	request := httptest.NewRequest(http.MethodGet, "/goroutine-profile", nil)
	request.Header.Set("Authorization", "Bearer test-token")
	request.Header.Set("X-M7H-Goroutine-Profile-Path", path)
	response := httptest.NewRecorder()

	(&m7hRemoteSFUServer{}).handleGoroutineProfile("test-token")(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("profile endpoint status = %d, body = %q", response.Code, response.Body.String())
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat local goroutine profile: %v", err)
	}
	if info.Size() == 0 {
		t.Fatal("local goroutine profile is empty")
	}
	if got := info.Mode().Perm(); got != 0o600 {
		t.Fatalf("local goroutine profile permissions = %04o, want 0600", got)
	}
}

func TestM7HRemoteSFUGoroutineProfileRejectsNonTemporaryPath(t *testing.T) {
	request := httptest.NewRequest(http.MethodGet, "/goroutine-profile", nil)
	request.Header.Set("Authorization", "Bearer test-token")
	request.Header.Set("X-M7H-Goroutine-Profile-Path", "/etc/hami-goroutine.pprof")
	response := httptest.NewRecorder()

	(&m7hRemoteSFUServer{}).handleGoroutineProfile("test-token")(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("profile endpoint status = %d, want %d", response.Code, http.StatusBadRequest)
	}
}

func TestM7HRemoteSFUCPUProfileWritesPrivateLocalFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "cpu.pprof")
	request := httptest.NewRequest(http.MethodGet, "/cpu-profile", nil)
	request.Header.Set("Authorization", "Bearer test-token")
	request.Header.Set("X-M7H-CPU-Profile-Path", path)
	request.Header.Set("X-M7H-CPU-Profile-Duration", "100ms")
	response := httptest.NewRecorder()

	(&m7hRemoteSFUServer{}).handleCPUProfile("test-token")(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("profile endpoint status = %d, body = %q", response.Code, response.Body.String())
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat local CPU profile: %v", err)
	}
	if info.Size() == 0 {
		t.Fatal("local CPU profile is empty")
	}
	if got := info.Mode().Perm(); got != 0o600 {
		t.Fatalf("local CPU profile permissions = %04o, want 0600", got)
	}
}

func TestM7HRemoteSFUCPUProfileRejectsDurationOverLimit(t *testing.T) {
	path := filepath.Join(t.TempDir(), "cpu.pprof")
	request := httptest.NewRequest(http.MethodGet, "/cpu-profile", nil)
	request.Header.Set("Authorization", "Bearer test-token")
	request.Header.Set("X-M7H-CPU-Profile-Path", path)
	request.Header.Set("X-M7H-CPU-Profile-Duration", (m7hCPUProfileMaxWindow + time.Second).String())
	response := httptest.NewRecorder()

	(&m7hRemoteSFUServer{}).handleCPUProfile("test-token")(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("profile endpoint status = %d, want %d", response.Code, http.StatusBadRequest)
	}
	if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("invalid duration created a profile: stat error = %v", err)
	}
}
