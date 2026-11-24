//go:build smoke

// Loss-injection tests for hami-sfu (Stage 3): prove the SFU recovers
// lost frames through the NACK retransmit path, with a seeded, repeatable
// packet drop and a fixed frame count.
//
// The drop is injected by a custom Pion interceptor registered FIRST in
// the test client's interceptor registry. Pion's interceptor chain wraps
// in registration order, so the first-registered interceptor is:
//   - inbound: the first to see a packet (before the NACK generator),
//     so a dropped packet looks exactly like wire loss to the receiver;
//   - outbound: the last to see a packet (after the NACK responder has
//     cached it), so a dropped packet is still retransmittable.
//
// That is the faithful wire-loss point on both hops. Dropping inside the
// server's forward path would NOT be faithful: the packet would never
// reach the responder cache and could never be retransmitted.
//
// The publisher sends a fixed burst of N frames after the subscriber is
// connected, plus 30 uncounted trailer packets: a lost packet at the very
// tail of the burst is only revealed as a gap once a later packet
// arrives, so without trailers the tail could never be NACKed.
//
// Pass bar: >= 99% of burst frames received (unique sequence numbers) at
// 5% and 10% loss, on each hop. The no-NACK control proves the test is
// sensitive: the same flow with the NACK generator removed must land near
// the no-recovery expectation (~95% at 5% loss).
package main

import (
	"encoding/binary"
	"io"
	"math/rand"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/pion/interceptor"
	"github.com/pion/rtcp"
	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

// lossInterceptor drops a seeded fraction of RTP packets. It implements
// interceptor.Interceptor by embedding interceptor.NoOp and overriding
// only the two stream bindings. It also counts re-reads of the same
// sequence number: a packet read twice (or more) is a retransmit, so the
// re-read count says exactly how many retransmit attempts reached this
// point — the key evidence when a packet stays missing despite NACKs.
type lossInterceptor struct {
	interceptor.NoOp
	rate    float64
	mu      sync.Mutex
	rng     *rand.Rand
	seen    atomic.Int64
	dropped atomic.Int64
	// readCounts tracks how many times each sequence number was read
	// (inbound only); retransmitReads counts reads of an already-seen seq.
	readCounts      map[uint16]int
	retransmitReads atomic.Int64
}

func newLossInterceptor(rate float64, seed int64) *lossInterceptor {
	return &lossInterceptor{rate: rate, rng: rand.New(rand.NewSource(seed)), readCounts: map[uint16]int{}}
}

// readCount returns how many times seq was read (inbound).
func (l *lossInterceptor) readCount(seq uint16) int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.readCounts[seq]
}

// drop decides (seeded) whether one packet is lost, and counts it.
func (l *lossInterceptor) drop() bool {
	l.mu.Lock()
	lost := l.rng.Float64() < l.rate
	l.mu.Unlock()
	l.seen.Add(1)
	if lost {
		l.dropped.Add(1)
	}
	return lost
}

// BindRemoteStream drops inbound packets before the rest of the chain
// (including the NACK generator) ever sees them: wire loss.
func (l *lossInterceptor) BindRemoteStream(_ *interceptor.StreamInfo, reader interceptor.RTPReader) interceptor.RTPReader {
	return interceptor.RTPReaderFunc(func(b []byte, a interceptor.Attributes) (int, interceptor.Attributes, error) {
		for {
			n, attr, err := reader.Read(b, a)
			if err != nil {
				return n, attr, err
			}
			if n >= 4 {
				seq := binary.BigEndian.Uint16(b[2:4])
				l.mu.Lock()
				if l.readCounts[seq] > 0 {
					l.retransmitReads.Add(1)
				}
				l.readCounts[seq]++
				l.mu.Unlock()
			}
			if l.drop() {
				continue // packet lost on the wire; read the next one
			}
			return n, attr, nil
		}
	})
}

// BindLocalStream drops outbound packets after they passed the NACK
// responder cache, so the responder can still retransmit them.
func (l *lossInterceptor) BindLocalStream(_ *interceptor.StreamInfo, writer interceptor.RTPWriter) interceptor.RTPWriter {
	return interceptor.RTPWriterFunc(func(header *rtp.Header, payload []byte, a interceptor.Attributes) (int, error) {
		if l.drop() {
			return header.MarshalSize() + len(payload), nil
		}
		return writer.Write(header, payload, a)
	})
}

// lossFactory builds one lossInterceptor per PeerConnection and keeps
// them for stats.
type lossFactory struct {
	rate  float64
	seed  int64
	mu    sync.Mutex
	built []*lossInterceptor
}

func (f *lossFactory) NewInterceptor(_ string) (interceptor.Interceptor, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	li := newLossInterceptor(f.rate, f.seed)
	f.built = append(f.built, li)
	return li, nil
}

func (f *lossFactory) stats() (seen, dropped int64) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, li := range f.built {
		seen += li.seen.Load()
		dropped += li.dropped.Load()
	}
	return seen, dropped
}

// retransmitReads totals re-reads of already-seen sequence numbers
// (inbound): how many retransmit attempts reached this interceptor.
func (f *lossFactory) retransmitReads() int64 {
	f.mu.Lock()
	defer f.mu.Unlock()
	var total int64
	for _, li := range f.built {
		total += li.retransmitReads.Load()
	}
	return total
}

// readCount returns how many times seq was read by any interceptor built
// from this factory (inbound).
func (f *lossFactory) readCount(seq uint16) int {
	f.mu.Lock()
	defer f.mu.Unlock()
	total := 0
	for _, li := range f.built {
		total += li.readCount(seq)
	}
	return total
}

// nackCounter counts TransportLayerNack RTCP packets passing through a
// PeerConnection, in both directions, and records how many times each
// sequence number was NACKed. Registered FIRST in the test-client
// registry so it also sees the NACKs the generator loop writes: the loop
// holds the writer the generator was bound with, which is downstream of
// interceptors registered before it, so a counter registered after the
// generator would never see them.
type nackCounter struct {
	interceptor.NoOp
	sentNacks    atomic.Int64 // outgoing NACK packets
	sentNackSeqs atomic.Int64 // total seqs in outgoing NACKs
	recvNacks    atomic.Int64 // incoming NACK packets
	recvNackSeqs atomic.Int64 // total seqs in incoming NACKs
	mu           sync.Mutex
	sentSeqs     map[uint16]int // seq -> times NACKed (outgoing)
	recvSeqs     map[uint16]int // seq -> times NACKed (incoming)
}

func newNackCounter() *nackCounter {
	return &nackCounter{sentSeqs: map[uint16]int{}, recvSeqs: map[uint16]int{}}
}

// NewInterceptor lets the counter be registered directly (one
// PeerConnection per test API, so a shared instance is fine).
func (c *nackCounter) NewInterceptor(_ string) (interceptor.Interceptor, error) {
	return c, nil
}

func (c *nackCounter) recordNack(pkts []rtcp.Packet, outgoing bool) {
	for _, p := range pkts {
		nack, ok := p.(*rtcp.TransportLayerNack)
		if !ok {
			continue
		}
		c.mu.Lock()
		if outgoing {
			c.sentNacks.Add(1)
			for i := range nack.Nacks {
				nack.Nacks[i].Range(func(seq uint16) bool {
					c.sentNackSeqs.Add(1)
					c.sentSeqs[seq]++
					return true
				})
			}
		} else {
			c.recvNacks.Add(1)
			for i := range nack.Nacks {
				nack.Nacks[i].Range(func(seq uint16) bool {
					c.recvNackSeqs.Add(1)
					c.recvSeqs[seq]++
					return true
				})
			}
		}
		c.mu.Unlock()
	}
}

// BindRTCPWriter counts outgoing NACKs (including the generator loop's).
func (c *nackCounter) BindRTCPWriter(writer interceptor.RTCPWriter) interceptor.RTCPWriter {
	return interceptor.RTCPWriterFunc(func(pkts []rtcp.Packet, a interceptor.Attributes) (int, error) {
		c.recordNack(pkts, true)
		return writer.Write(pkts, a)
	})
}

// BindRTCPReader counts incoming NACKs.
func (c *nackCounter) BindRTCPReader(reader interceptor.RTCPReader) interceptor.RTCPReader {
	return interceptor.RTCPReaderFunc(func(b []byte, a interceptor.Attributes) (int, interceptor.Attributes, error) {
		n, attr, err := reader.Read(b, a)
		if err != nil {
			return n, attr, err
		}
		if pkts, perr := attr.GetRTCPPackets(b[:n]); perr == nil {
			c.recordNack(pkts, false)
		}
		return n, attr, nil
	})
}

// nackCount returns how many times seq was NACKed in the given direction.
func (c *nackCounter) nackCount(seq uint16, outgoing bool) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	if outgoing {
		return c.sentSeqs[seq]
	}
	return c.recvSeqs[seq]
}

// lossClientAPI builds a Pion API for a test client whose RTP path drops
// a seeded fraction of packets. The NACK counter is registered FIRST,
// then the drop interceptor, then the default interceptors: that puts
// the counter where it sees the generator's NACKs, and the drop
// interceptor at the wire-loss point on both directions (see the file
// header). With withNack=false the default interceptors (including the
// NACK generator) are left out: the negative control, recovery switched
// off.
func lossClientAPI(rate float64, seed int64, withNack bool) (*webrtc.API, *lossFactory, *nackCounter, error) {
	m := &webrtc.MediaEngine{}
	if err := m.RegisterDefaultCodecs(); err != nil {
		return nil, nil, nil, err
	}
	reg := &interceptor.Registry{}
	counter := newNackCounter()
	reg.Add(counter)
	factory := &lossFactory{rate: rate, seed: seed}
	reg.Add(factory)
	if withNack {
		if err := webrtc.RegisterDefaultInterceptors(m, reg); err != nil {
			return nil, nil, nil, err
		}
	}
	return webrtc.NewAPI(webrtc.WithMediaEngine(m), webrtc.WithInterceptorRegistry(reg)), factory, counter, nil
}

type lossResult struct {
	sent     int
	received int
	missing  []uint16 // first 20 missing seqs, if any
	rawReads int64
	injSeen  int64
	injDrop  int64
	elapsed  time.Duration
	// Publisher's total WriteRTP calls (warm-up + burst + trailers).
	// Retransmit attempts on the publisher hop ~= pubInjSeen - pubSent.
	pubSent int
	// NACK traffic observed at the test clients.
	subNackPkts  int64          // subscriber: outgoing NACK packets (it asks)
	subNackSeqs  int64          // subscriber: total seqs in outgoing NACKs
	pubNackPkts  int64          // publisher: incoming NACK packets (server asks)
	pubNackSeqs  int64          // publisher: total seqs in incoming NACKs
	missingNacks map[uint16]int // NACK count per missing seq, relevant direction
	// Retransmit attempts that reached this side's interceptor (inbound
	// re-reads of an already-seen seq), and per-missing-seq read counts.
	// A stuck packet with read count 1 was resent once (and that resend
	// was dropped); with 0 it was never resent at all.
	retransmitReads int64
	missingReads    map[uint16]int
}

func pct(a, b int) float64 {
	if b == 0 {
		return 0
	}
	return float64(a) * 100 / float64(b)
}

func pct64(a, b int64) float64 {
	if b == 0 {
		return 0
	}
	return float64(a) * 100 / float64(b)
}

// lossClientAPINoReports builds a test-client API without the RTCP
// report interceptors (and without TWCC): the client sends no Receiver
// Reports, so a server NACK responder never learns an RTT from it.
// Diagnostic: if recovery becomes fast without RRs, the responder's
// RTT-gated resend interval is the bottleneck.
func lossClientAPINoReports(rate float64, seed int64) (*webrtc.API, *lossFactory, *nackCounter, error) {
	m := &webrtc.MediaEngine{}
	if err := m.RegisterDefaultCodecs(); err != nil {
		return nil, nil, nil, err
	}
	reg := &interceptor.Registry{}
	counter := newNackCounter()
	reg.Add(counter)
	factory := &lossFactory{rate: rate, seed: seed}
	reg.Add(factory)
	if err := webrtc.ConfigureNackWithOptions(m, reg, nil); err != nil {
		return nil, nil, nil, err
	}
	if err := webrtc.ConfigureStatsInterceptorWithOptions(reg); err != nil {
		return nil, nil, nil, err
	}
	return webrtc.NewAPI(webrtc.WithMediaEngine(m), webrtc.WithInterceptorRegistry(reg)), factory, counter, nil
}

// lossFlow runs one publish -> subscribe flow with packet loss injected
// on one hop. dropSide is "subscriber" (server -> subscriber leg) or
// "publisher" (publisher -> server leg). The publisher sends a fixed
// burst of burstFrames frames once the subscriber is connected, then 30
// uncounted trailer packets. It returns how many of the burst frames the
// subscriber received (unique sequence numbers).
func lossFlow(t *testing.T, roomName string, udpPort int, dropSide string, rate float64, seed int64, withNack bool, burstFrames int, subNoReports bool) lossResult {
	t.Helper()
	started := time.Now()

	api, err := newAPI(udpPort, false)
	if err != nil {
		t.Fatalf("newAPI: %v", err)
	}
	s := &server{api: api, auth: nil, maxRooms: 8, maxPublishers: 8, maxSubscribers: 50, rooms: make(map[string]*room)}
	httpSrv := httptest.NewServer(s.routes())
	defer httpSrv.Close()
	client := httpSrv.Client()

	// ---- Publisher ----
	var pubAPI *webrtc.API
	var pubFactory *lossFactory
	var pubCounter *nackCounter
	if dropSide == "publisher" {
		pubAPI, pubFactory, pubCounter, err = lossClientAPI(rate, seed, true)
		if err != nil {
			t.Fatalf("publisher loss API: %v", err)
		}
	}
	var pubPC *webrtc.PeerConnection
	if pubAPI != nil {
		pubPC, err = pubAPI.NewPeerConnection(webrtc.Configuration{})
	} else {
		pubPC, err = webrtc.NewPeerConnection(webrtc.Configuration{})
	}
	if err != nil {
		t.Fatalf("publisher PC: %v", err)
	}
	defer pubPC.Close()
	videoTrack, err := webrtc.NewTrackLocalStaticRTP(
		webrtc.RTPCodecCapability{MimeType: webrtc.MimeTypeH264, ClockRate: 90000},
		"loss-video", "loss-stream",
	)
	if err != nil {
		t.Fatalf("video track: %v", err)
	}
	if _, err := pubPC.AddTrack(videoTrack); err != nil {
		t.Fatalf("AddTrack: %v", err)
	}
	pubOffer := offerWithCandidates(t, pubPC)
	pubAnswer := postSDPWithToken(t, client, httpSrv.URL+"/api/publish/"+roomName, pubOffer, "", http.StatusOK)
	if err := pubPC.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeAnswer, SDP: pubAnswer}); err != nil {
		t.Fatalf("publisher SetRemoteDescription: %v", err)
	}
	waitConnected(t, "publisher", pubPC)

	// RTCP pump: a sender's RTCP reader chain — including the NACK
	// responder that retransmits on the server's NACKs — only runs while
	// something calls sender.ReadRTCP(). The server pumps its
	// subscribers' RTCP (pumpSubscriberRTCP); a real publisher (browser)
	// pumps its own. Without this pump the server's NACKs sit unread in
	// the publisher's SRTCP buffer and no retransmit ever happens, which
	// is a harness gap, not a server bug: the first publisher-hop runs
	// measured 94%/90% (no recovery) with ZERO NACKs seen, because
	// nothing ever read them.
	senders := pubPC.GetSenders()
	if len(senders) == 0 {
		t.Fatal("publisher has no senders to pump RTCP on")
	}
	pubSender := senders[0]
	go func() {
		for {
			if _, _, err := pubSender.ReadRTCP(); err != nil {
				return
			}
		}
	}()

	// Publisher sends warm-up frames until the burst is signalled, then
	// exactly burstFrames counted frames, then 30 uncounted trailers.
	startBurst := make(chan struct{})
	stopSend := make(chan struct{})
	defer close(stopSend)
	type burstInfo struct {
		start     uint16
		count     int
		totalSent int // warm-up + burst + trailers written by the publisher
	}
	burstDone := make(chan burstInfo, 1)
	go func() {
		seq := uint16(1)
		ts := uint32(0)
		sent := 0
		send := func() {
			nal := byte(0x41) // non-IDR slice
			if sent%30 == 0 {
				nal = 0x65 // IDR slice (type 5)
			}
			payload := []byte{nal, 0x88, 0x84, 0x21, 0xa0, 0x00, 0x00, 0x03, 0x00, 0x80, 0x00, 0x00, 0x19, 0x40}
			pkt := &rtp.Packet{
				Header: rtp.Header{
					Version:        2,
					PayloadType:    102,
					SequenceNumber: seq,
					Timestamp:      ts,
					Marker:         true,
				},
				Payload: payload,
			}
			_ = videoTrack.WriteRTP(pkt)
			sent++
			seq++
			ts += 3000 // 90 kHz / 30 fps
		}
		for {
			select {
			case <-startBurst:
				start := seq
				for i := 0; i < burstFrames; i++ {
					send()
					time.Sleep(30 * time.Millisecond)
				}
				for i := 0; i < 30; i++ { // trailers: reveal a lost tail packet
					send()
					time.Sleep(30 * time.Millisecond)
				}
				burstDone <- burstInfo{start: start, count: burstFrames, totalSent: sent}
				<-stopSend
				return
			case <-stopSend:
				return
			default:
				send()
				time.Sleep(30 * time.Millisecond)
			}
		}
	}()

	// Wait until the server lists the published track.
	deadline := time.Now().Add(10 * time.Second)
	for {
		req, err := http.NewRequest(http.MethodGet, httpSrv.URL+"/api/rooms/"+roomName, nil)
		if err != nil {
			t.Fatalf("new request: %v", err)
		}
		resp, err := client.Do(req)
		if err == nil {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK && strings.Contains(string(body), "loss-video") {
				t.Logf("server lists track: %s", strings.TrimSpace(string(body)))
				break
			}
		}
		if time.Now().After(deadline) {
			t.Fatal("server never listed the published track")
		}
		time.Sleep(200 * time.Millisecond)
	}

	// ---- Subscriber: count unique sequence numbers. ----
	var mu sync.Mutex
	seen := map[uint16]struct{}{}
	var rawReads atomic.Int64
	var subAPI *webrtc.API
	var subFactory *lossFactory
	var subCounter *nackCounter
	if dropSide == "subscriber" {
		if subNoReports {
			subAPI, subFactory, subCounter, err = lossClientAPINoReports(rate, seed)
		} else {
			subAPI, subFactory, subCounter, err = lossClientAPI(rate, seed, withNack)
		}
		if err != nil {
			t.Fatalf("subscriber loss API: %v", err)
		}
	}
	var subPC *webrtc.PeerConnection
	if subAPI != nil {
		subPC, err = subAPI.NewPeerConnection(webrtc.Configuration{})
	} else {
		subPC, err = webrtc.NewPeerConnection(webrtc.Configuration{})
	}
	if err != nil {
		t.Fatalf("subscriber PC: %v", err)
	}
	defer subPC.Close()
	subPC.OnTrack(func(remote *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		t.Logf("subscriber OnTrack: %s %s", remote.Kind(), remote.Codec().MimeType)
		go func() {
			for {
				pkt, _, err := remote.ReadRTP()
				if err != nil {
					return
				}
				rawReads.Add(1)
				mu.Lock()
				seen[pkt.Header.SequenceNumber] = struct{}{}
				mu.Unlock()
			}
		}()
	})
	if _, err := subPC.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo,
		webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly}); err != nil {
		t.Fatalf("AddTransceiver: %v", err)
	}
	subOffer := offerWithCandidates(t, subPC)
	subAnswer := postSDPWithToken(t, client, httpSrv.URL+"/api/subscribe/"+roomName, subOffer, "", http.StatusOK)
	if err := subPC.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeAnswer, SDP: subAnswer}); err != nil {
		t.Fatalf("subscriber SetRemoteDescription: %v", err)
	}
	waitConnected(t, "subscriber", subPC)

	// ---- Burst + drain. ----
	close(startBurst)
	var info burstInfo
	select {
	case info = <-burstDone:
		t.Logf("burst sent: start seq %d, %d frames", info.start, info.count)
	case <-time.After(30 * time.Second):
		t.Fatal("publisher never finished the burst")
	}
	countInRange := func() int {
		mu.Lock()
		defer mu.Unlock()
		got := 0
		for i := 0; i < info.count; i++ {
			if _, ok := seen[info.start+uint16(i)]; ok {
				got++
			}
		}
		return got
	}
	deadline = time.Now().Add(20 * time.Second)
	got := 0
	for {
		got = countInRange()
		if got >= info.count {
			break
		}
		if time.Now().After(deadline) {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	mu.Lock()
	var missing []uint16
	for i := 0; i < info.count && len(missing) < 20; i++ {
		if _, ok := seen[info.start+uint16(i)]; !ok {
			missing = append(missing, info.start+uint16(i))
		}
	}
	mu.Unlock()
	factory := subFactory
	if factory == nil {
		factory = pubFactory
	}
	var injSeen, injDrop int64
	if factory != nil {
		injSeen, injDrop = factory.stats()
	}
	// NACK counts per missing seq, in the direction that matters for this
	// hop: subscriber-outgoing on the subscriber hop (did it keep asking
	// for the stuck packets?), publisher-incoming on the publisher hop
	// (did the server keep asking?).
	missingNacks := map[uint16]int{}
	for _, seq := range missing {
		if dropSide == "subscriber" && subCounter != nil {
			missingNacks[seq] = subCounter.nackCount(seq, true)
		} else if dropSide == "publisher" && pubCounter != nil {
			missingNacks[seq] = pubCounter.nackCount(seq, false)
		}
	}
	var subNackPkts, subNackSeqs, pubNackPkts, pubNackSeqs int64
	if subCounter != nil {
		subNackPkts = subCounter.sentNacks.Load()
		subNackSeqs = subCounter.sentNackSeqs.Load()
	}
	if pubCounter != nil {
		pubNackPkts = pubCounter.recvNacks.Load()
		pubNackSeqs = pubCounter.recvNackSeqs.Load()
	}
	// Retransmit reads per missing seq (inbound side only; the
	// publisher-hop interceptor sits on the outbound path, so its
	// read counts are zero there and the retransmit evidence is
	// injSeen - pubSent instead).
	missingReads := map[uint16]int{}
	var retransmitReads int64
	if factory != nil {
		retransmitReads = factory.retransmitReads()
		for _, seq := range missing {
			missingReads[seq] = factory.readCount(seq)
		}
	}
	return lossResult{
		sent:            info.count,
		received:        got,
		missing:         missing,
		rawReads:        rawReads.Load(),
		injSeen:         injSeen,
		injDrop:         injDrop,
		elapsed:         time.Since(started),
		pubSent:         info.totalSent,
		subNackPkts:     subNackPkts,
		subNackSeqs:     subNackSeqs,
		pubNackPkts:     pubNackPkts,
		pubNackSeqs:     pubNackSeqs,
		missingNacks:    missingNacks,
		retransmitReads: retransmitReads,
		missingReads:    missingReads,
	}
}

func logLossResult(t *testing.T, label string, res lossResult) {
	t.Helper()
	t.Logf("%s: sent=%d received=%d (%.1f%%) rawReads=%d pubSent=%d injector seen=%d dropped=%d (%.1f%%) elapsed=%s missing(first 20)=%v",
		label, res.sent, res.received, pct(res.received, res.sent), res.rawReads, res.pubSent,
		res.injSeen, res.injDrop, pct64(res.injDrop, res.injSeen), res.elapsed, res.missing)
	t.Logf("%s: NACKs sub-out pkts=%d seqs=%d | pub-in pkts=%d seqs=%d | missingNacks=%v",
		label, res.subNackPkts, res.subNackSeqs, res.pubNackPkts, res.pubNackSeqs, res.missingNacks)
	t.Logf("%s: retransmitReads=%d missingReads=%v",
		label, res.retransmitReads, res.missingReads)
}

func TestLossRecoverySubscriber5Pct(t *testing.T) {
	res := lossFlow(t, "loss-sub5", 17511, "subscriber", 0.05, 1, true, 300, false)
	logLossResult(t, "5% loss, subscriber hop", res)
	if res.received*100 < res.sent*99 {
		t.Fatalf("FAIL: recovered only %d/%d frames (%.1f%%), want >= 99%%; missing (first 20): %v",
			res.received, res.sent, pct(res.received, res.sent), res.missing)
	}
}

func TestLossRecoverySubscriber10Pct(t *testing.T) {
	res := lossFlow(t, "loss-sub10", 17512, "subscriber", 0.10, 2, true, 300, false)
	logLossResult(t, "10% loss, subscriber hop", res)
	if res.received*100 < res.sent*99 {
		t.Fatalf("FAIL: recovered only %d/%d frames (%.1f%%), want >= 99%%; missing (first 20): %v",
			res.received, res.sent, pct(res.received, res.sent), res.missing)
	}
}

// TestLossRecoverySubscriber10PctNoReports is the diagnostic for the
// RTT-poisoning hypothesis: the subscriber sends no Receiver Reports, so
// the server responder's RTT estimate stays 0 and its resend interval is
// 5 ms. If this recovers fast and fully, the RRs are the poison.
func TestLossRecoverySubscriber10PctNoReports(t *testing.T) {
	res := lossFlow(t, "loss-sub10nr", 17516, "subscriber", 0.10, 2, true, 300, true)
	logLossResult(t, "10% loss, subscriber hop, no RRs", res)
	if res.received*100 < res.sent*99 {
		t.Fatalf("FAIL: recovered only %d/%d frames (%.1f%%), want >= 99%%; missing (first 20): %v",
			res.received, res.sent, pct(res.received, res.sent), res.missing)
	}
}

func TestLossRecoveryPublisher5Pct(t *testing.T) {
	res := lossFlow(t, "loss-pub5", 17513, "publisher", 0.05, 3, true, 300, false)
	logLossResult(t, "5% loss, publisher hop", res)
	if res.received*100 < res.sent*99 {
		t.Fatalf("FAIL: recovered only %d/%d frames (%.1f%%), want >= 99%%; missing (first 20): %v",
			res.received, res.sent, pct(res.received, res.sent), res.missing)
	}
}

func TestLossRecoveryPublisher10Pct(t *testing.T) {
	res := lossFlow(t, "loss-pub10", 17514, "publisher", 0.10, 4, true, 300, false)
	logLossResult(t, "10% loss, publisher hop", res)
	if res.received*100 < res.sent*99 {
		t.Fatalf("FAIL: recovered only %d/%d frames (%.1f%%), want >= 99%%; missing (first 20): %v",
			res.received, res.sent, pct(res.received, res.sent), res.missing)
	}
}

func TestLossRecoveryNoNackControl(t *testing.T) {
	// Same flow at 5% loss, but the subscriber has no NACK generator:
	// recovery is switched off. This must FAIL the 99% bar and land near
	// the no-recovery expectation (~95%): it proves the test measures
	// NACK recovery and is not vacuous.
	res := lossFlow(t, "loss-ctrl", 17515, "subscriber", 0.05, 1, false, 300, false)
	logLossResult(t, "5% loss, subscriber hop, NO NACK (control)", res)
	if res.received*100 >= res.sent*99 {
		t.Fatalf("CONTROL FAIL: received %d/%d without NACK, expected loss to show (want < 99%%)",
			res.received, res.sent)
	}
	if res.received < res.sent*85/100 || res.received > res.sent*98/100 {
		t.Fatalf("CONTROL UNEXPECTED: received %d/%d without NACK, want the ~95%% no-recovery band (85%%-98%%)",
			res.received, res.sent)
	}
}
