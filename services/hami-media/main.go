package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	runtimemetrics "runtime/metrics"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/pion/ice/v4"
	"github.com/pion/rtcp"
	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
	"github.com/pion/webrtc/v4/pkg/media"
	"github.com/pion/webrtc/v4/pkg/media/h264reader"
)

const (
	audioFrameDuration    = 20 * time.Millisecond
	videoFrameDuration    = 3 * audioFrameDuration
	audioSampleRate       = 8000
	audioSamplesFrame     = audioSampleRate / 50
	sfuNACKHistoryPackets = 512
	// NACK aggregation (M6-H attempt 8): a viewer NACKs the same lost
	// sequences on every RTCP interval, and retransmitting each one again
	// drowns the router (16.7M retransmits for 306k NACKs in attempt 7)
	// and starves the subscription's ReadRTCP loop, so PLI/FIR never get
	// read. Remember each retransmitted sequence for this long and skip
	// duplicates inside the window; serve at most this many sequences
	// from one NACK and let the viewer re-NACK the rest.
	// M6-H measurements showed that larger queues and NACK caps increased
	// backlog and oversized RTCP errors without improving PLI/FIR delivery.
	nackAggregationWindow               = 500 * time.Millisecond
	maxSequencesPerNACK                 = 128
	nackQueueSize                       = 64
	nackMaxQueueAge                     = 500 * time.Millisecond
	peerPairNegotiationTimeout          = 30 * time.Second
	peerNegotiationConcurrency          = 32
	sfuFeedbackPacingInterval           = 5 * time.Millisecond
	rtpForwardLatencyBucketCount        = 9
	sfuInitialVideoTimestamp     uint32 = 0x10203040
	peerConnectionConnected             = "connected"
)

var rtpForwardLatencyBuckets = [...]time.Duration{
	time.Millisecond,
	5 * time.Millisecond,
	10 * time.Millisecond,
	20 * time.Millisecond,
	50 * time.Millisecond,
	100 * time.Millisecond,
	250 * time.Millisecond,
	500 * time.Millisecond,
}

var metricsListenAddress = flag.String(
	"metrics-listen",
	"",
	"optional loopback-only Prometheus endpoint (for example 127.0.0.1:9464)",
)

type streamSnapshot struct {
	Codec               string `json:"codec"`
	SSRC                uint32 `json:"ssrc"`
	PayloadType         uint8  `json:"payload_type"`
	PacketsReceived     uint64 `json:"packets_received"`
	BytesReceived       uint64 `json:"bytes_received"`
	FirstSequenceNumber uint16 `json:"first_sequence_number"`
	LastSequenceNumber  uint16 `json:"last_sequence_number"`
	FirstTimestamp      uint32 `json:"first_rtp_timestamp"`
	LastTimestamp       uint32 `json:"last_rtp_timestamp"`
}

type streamCounter struct {
	mu       sync.Mutex
	snapshot streamSnapshot
}

func (c *streamCounter) bind(codec string, ssrc uint32, payloadType uint8) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.snapshot.Codec != "" {
		return fmt.Errorf("received duplicate %s track", codec)
	}
	c.snapshot.Codec = codec
	c.snapshot.SSRC = ssrc
	c.snapshot.PayloadType = payloadType
	return nil
}

func (c *streamCounter) record(sequence uint16, timestamp uint32, payloadBytes int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.snapshot.PacketsReceived == 0 {
		c.snapshot.FirstSequenceNumber = sequence
		c.snapshot.FirstTimestamp = timestamp
	}
	c.snapshot.LastSequenceNumber = sequence
	c.snapshot.LastTimestamp = timestamp
	c.snapshot.PacketsReceived++
	c.snapshot.BytesReceived += uint64(payloadBytes)
}

func (c *streamCounter) snapshotResult() streamSnapshot {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.snapshot
}

type sendCounts struct {
	audioSamples uint64
	videoFrames  uint64
}

type sendResult struct {
	counts sendCounts
	err    error
}

type proofResult struct {
	EvidenceType       string         `json:"evidence_type"`
	LocalOnly          bool           `json:"local_only"`
	PublisherIdentity  string         `json:"publisher_identity"`
	SubscriberIdentity string         `json:"subscriber_identity"`
	PublisherState     string         `json:"publisher_peer_connection_state"`
	SubscriberState    string         `json:"subscriber_peer_connection_state"`
	StartedAt          time.Time      `json:"started_at_utc"`
	CompletedAt        time.Time      `json:"completed_at_utc"`
	MediaDurationMS    int64          `json:"media_duration_ms"`
	AudioSamplesSent   uint64         `json:"audio_samples_sent"`
	VideoFramesSent    uint64         `json:"video_frames_sent"`
	Audio              streamSnapshot `json:"audio_rtp_received"`
	Video              streamSnapshot `json:"video_rtp_received"`
}

type sfuTrackKey struct {
	PublisherID string `json:"publisher_id"`
	TrackID     string `json:"track_id"`
}

type sfuFeedbackCounts struct {
	NACKReceived          uint64 `json:"nack_received"`
	NACKRetransmitted     uint64 `json:"nack_retransmitted_packets"`
	NACKForwarded         uint64 `json:"nack_forwarded_upstream"`
	NACKDuplicatesSkipped uint64 `json:"nack_duplicates_skipped"`
	NACKSequencesCapped   uint64 `json:"nack_sequences_capped"`
	NACKEnqueued          uint64 `json:"nack_enqueued"`
	NACKDroppedQueueFull  uint64 `json:"nack_dropped_queue_full"`
	NACKDroppedStale      uint64 `json:"nack_dropped_stale"`
	NACKQueueDepth        uint64 `json:"nack_queue_depth"`
	PLIForwarded          uint64 `json:"pli_forwarded_upstream"`
	FIRForwarded          uint64 `json:"fir_forwarded_upstream"`
}

type sfuViewerResult struct {
	ViewerID             string            `json:"viewer_id"`
	RequestedTrackID     string            `json:"requested_track_id"`
	ReceivedTrackIDs     []string          `json:"received_track_ids"`
	Received             streamSnapshot    `json:"rtp_received"`
	Latency              *Summary          `json:"latency,omitempty"`
	LatencyJSONLPath     string            `json:"latency_jsonl_path,omitempty"`
	LatencySummaryPath   string            `json:"latency_summary_path,omitempty"`
	RetransmittedPackets uint64            `json:"retransmitted_packets_received"`
	PeerConnection       string            `json:"peer_connection_state"`
	FeedbackForwarded    sfuFeedbackCounts `json:"feedback_handled"`
	OnlyRequested        bool              `json:"only_requested_track_received"`
}

type sfuUpstreamFeedback struct {
	PublisherID string            `json:"publisher_id"`
	TrackID     string            `json:"track_id"`
	Counts      sfuFeedbackCounts `json:"feedback_received_by_publisher"`
}

type sfuProofResult struct {
	EvidenceType                   string                `json:"evidence_type"`
	LocalOnly                      bool                  `json:"local_only"`
	PublisherIdentity              string                `json:"publisher_identity"`
	PublisherIdentities            []string              `json:"publisher_identities,omitempty"`
	PublisherStates                map[string]string     `json:"publisher_peer_connection_states,omitempty"`
	PublisherState                 string                `json:"publisher_peer_connection_state"`
	PublisherTracks                []string              `json:"publisher_track_ids"`
	MediaDurationMS                int64                 `json:"media_duration_ms"`
	VideoFramesSent                uint64                `json:"video_frames_sent,omitempty"`
	PublisherFramesSent            map[string]uint64     `json:"video_frames_sent_per_publisher,omitempty"`
	Viewers                        []sfuViewerResult     `json:"viewers"`
	UpstreamFeedback               []sfuUpstreamFeedback `json:"upstream_feedback"`
	UnauthorizedSubscriptionDenied bool                  `json:"unauthorized_subscription_denied"`
	CleanupVerified                bool                  `json:"cleanup_verified"`
	ForwardingErrors               []string              `json:"forwarding_errors"`
	LatencyMode                    string                `json:"latency_mode,omitempty"`
	LatencyPending                 int                   `json:"latency_pending_frames"`
	LatencyEvidenceDirectory       string                `json:"latency_evidence_directory,omitempty"`
	MeasurementPass                *bool                 `json:"measurement_pass,omitempty"`
}

func main() {
	mode := flag.String("mode", "pair", "local proof mode: pair, sfu, m1h, m2h, m3h, m4h, m5h, or m6h")
	videoPath := flag.String("video-file", "", "local Annex-B H.264 source file")
	duration := flag.Duration("duration", 3*time.Second, "local media send duration")
	flag.Parse()
	if *videoPath == "" {
		fail("--video-file is required")
	}
	if *duration <= 0 {
		fail("--duration must be positive")
	}

	data, err := os.ReadFile(*videoPath)
	if err != nil {
		fail("read local H.264 source: %v", err)
	}
	videoFrames, err := readH264Frames(bytes.NewReader(data))
	if err != nil {
		fail("parse local H.264 source: %v", err)
	}

	setupAllowance := 3 * time.Minute
	if *mode == "m3h" {
		setupAllowance = 10 * time.Minute
	} else if *mode == "m4h" {
		setupAllowance = 20 * time.Minute
	} else if *mode == "m5h" {
		setupAllowance = 30 * time.Minute
	} else if *mode == "m6h" {
		setupAllowance = 45 * time.Minute
	}
	ctx, cancel := context.WithTimeout(context.Background(), *duration+setupAllowance)
	defer cancel()
	var result any
	switch *mode {
	case "pair":
		result, err = runLocalPair(ctx, videoFrames, *duration)
	case "sfu":
		result, err = runLocalSFUProof(ctx, videoFrames, *duration)
	case "m1h":
		result, err = runLocalM1HProof(ctx, videoFrames, *duration)
	case "m2h":
		result, err = runLocalM2HProof(ctx, videoFrames, *duration)
	case "m3h":
		result, err = runLocalM3HProof(ctx, videoFrames, *duration)
	case "m4h":
		result, err = runLocalM4HProof(ctx, videoFrames, *duration)
	case "m5h":
		result, err = runLocalM5HProof(ctx, videoFrames, *duration)
	case "m6h":
		result, err = runLocalM6HProof(ctx, videoFrames, *duration)
	default:
		fail("unsupported --mode %q (want pair, sfu, m1h, m2h, m3h, m4h, m5h, or m6h)", *mode)
	}
	if err != nil {
		fail("run local Pion %s proof: %v", *mode, err)
	}
	if err := json.NewEncoder(os.Stdout).Encode(result); err != nil {
		fail("write proof result: %v", err)
	}
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}

func readH264Frames(source io.Reader) ([]media.Sample, error) {
	reader, err := h264reader.NewReader(source)
	if err != nil {
		return nil, fmt.Errorf("create H.264 reader: %w", err)
	}

	var sps, pps []byte
	var frames []media.Sample
	for {
		nal, err := reader.NextNAL()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read H.264 NAL: %w", err)
		}
		switch nal.UnitType {
		case h264reader.NalUnitTypeSPS:
			sps = append(sps[:0], nal.Data...)
		case h264reader.NalUnitTypePPS:
			pps = append(pps[:0], nal.Data...)
		case h264reader.NalUnitTypeCodedSliceIdr:
			if len(sps) == 0 || len(pps) == 0 {
				return nil, errors.New("H.264 source must provide SPS and PPS before an IDR")
			}
			frame := make([]byte, 0, len(sps)+len(pps)+len(nal.Data)+12)
			frame = appendAnnexBNAL(frame, sps)
			frame = appendAnnexBNAL(frame, pps)
			frame = appendAnnexBNAL(frame, nal.Data)
			frames = append(frames, media.Sample{Data: frame, Duration: videoFrameDuration})
		}
	}
	if len(frames) == 0 {
		return nil, errors.New("H.264 source contains no SPS/PPS-backed IDR frames")
	}
	return frames, nil
}

func appendAnnexBNAL(dst, nal []byte) []byte {
	dst = append(dst, 0, 0, 0, 1)
	return append(dst, nal...)
}

func runLocalPair(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (result proofResult, returnErr error) {
	if len(videoFrames) == 0 {
		return proofResult{}, errors.New("at least one H.264 frame is required")
	}
	if duration <= 0 {
		return proofResult{}, errors.New("media duration must be positive")
	}

	clientSettings, _, err := loopbackSettings(false)
	if err != nil {
		return proofResult{}, err
	}
	settings, udpMux, err := loopbackSettings(true)
	if err != nil {
		return proofResult{}, err
	}
	defer func() {
		if closeErr := udpMux.Close(); closeErr != nil {
			returnErr = errors.Join(returnErr, fmt.Errorf("close loopback ICE UDP mux: %w", closeErr))
		}
	}()
	publisherAPI := webrtc.NewAPI(webrtc.WithSettingEngine(clientSettings))
	subscriberAPI := webrtc.NewAPI(webrtc.WithSettingEngine(settings))
	publisher, err := publisherAPI.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		return proofResult{}, fmt.Errorf("create publisher PeerConnection: %w", err)
	}
	defer publisher.Close()
	subscriber, err := subscriberAPI.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		return proofResult{}, fmt.Errorf("create subscriber PeerConnection: %w", err)
	}
	defer subscriber.Close()

	videoTrack, err := webrtc.NewTrackLocalStaticSample(webrtc.RTPCodecCapability{
		MimeType:    webrtc.MimeTypeH264,
		ClockRate:   90000,
		SDPFmtpLine: "level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42001f",
	}, "hami-video", "hami-local-pair")
	if err != nil {
		return proofResult{}, fmt.Errorf("create H.264 publisher track: %w", err)
	}
	audioTrack, err := webrtc.NewTrackLocalStaticSample(webrtc.RTPCodecCapability{
		MimeType:  webrtc.MimeTypePCMU,
		ClockRate: audioSampleRate,
		Channels:  1,
	}, "hami-audio", "hami-local-pair")
	if err != nil {
		return proofResult{}, fmt.Errorf("create PCMU publisher track: %w", err)
	}

	videoSender, err := publisher.AddTrack(videoTrack)
	if err != nil {
		return proofResult{}, fmt.Errorf("add H.264 publisher track: %w", err)
	}
	audioSender, err := publisher.AddTrack(audioTrack)
	if err != nil {
		return proofResult{}, fmt.Errorf("add PCMU publisher track: %w", err)
	}
	drainRTCP(videoSender)
	drainRTCP(audioSender)

	var receivedAudio, receivedVideo streamCounter
	trackErrors := make(chan error, 2)
	subscriber.OnTrack(func(track *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		codec := track.Codec()
		counter := &receivedVideo
		switch {
		case strings.EqualFold(codec.MimeType, webrtc.MimeTypeH264):
		case strings.EqualFold(codec.MimeType, webrtc.MimeTypePCMU):
			counter = &receivedAudio
		default:
			trackErrors <- fmt.Errorf("unexpected received codec %q", codec.MimeType)
			return
		}
		if err := counter.bind(codec.MimeType, uint32(track.SSRC()), uint8(track.PayloadType())); err != nil {
			trackErrors <- err
			return
		}
		go func() {
			for {
				packet, _, err := track.ReadRTP()
				if err != nil {
					if ctx.Err() == nil && !errors.Is(err, io.EOF) {
						select {
						case trackErrors <- fmt.Errorf("read %s RTP: %w", codec.MimeType, err):
						default:
						}
					}
					return
				}
				counter.record(packet.SequenceNumber, packet.Timestamp, len(packet.Payload))
			}
		}()
	})

	if err := negotiateLoopbackPeers(
		ctx,
		"single publisher/subscriber pair",
		publisher,
		subscriber,
		"m=audio",
		"m=video",
	); err != nil {
		return proofResult{}, err
	}

	startedAt := time.Now().UTC()
	sendContext, cancelSend := context.WithTimeout(ctx, duration)
	sendDone := make(chan sendResult, 1)
	go func() {
		counts, err := sendMedia(sendContext, audioTrack, videoTrack, videoFrames)
		sendDone <- sendResult{counts: counts, err: err}
	}()
	<-sendContext.Done()
	cancelSend()
	sent := <-sendDone
	if sent.err != nil {
		return proofResult{}, fmt.Errorf("write publisher media: %w", sent.err)
	}
	if err := ctx.Err(); err != nil {
		return proofResult{}, fmt.Errorf("local pair context ended: %w", err)
	}
	time.Sleep(100 * time.Millisecond)

	if err := waitForReceivedMedia(ctx, &receivedAudio, &receivedVideo, trackErrors); err != nil {
		return proofResult{}, err
	}
	completedAt := time.Now().UTC()
	return proofResult{
		EvidenceType:       "TEST",
		LocalOnly:          true,
		PublisherIdentity:  "hami-m0h-publisher",
		SubscriberIdentity: "hami-m0h-subscriber",
		PublisherState:     publisher.ConnectionState().String(),
		SubscriberState:    subscriber.ConnectionState().String(),
		StartedAt:          startedAt,
		CompletedAt:        completedAt,
		MediaDurationMS:    completedAt.Sub(startedAt).Milliseconds(),
		AudioSamplesSent:   sent.counts.audioSamples,
		VideoFramesSent:    sent.counts.videoFrames,
		Audio:              receivedAudio.snapshotResult(),
		Video:              receivedVideo.snapshotResult(),
	}, nil
}

func negotiateLoopbackPeers(
	ctx context.Context,
	pairName string,
	offerer, answerer *webrtc.PeerConnection,
	requiredMediaSections ...string,
) error {
	return negotiateLoopbackPeersWithTimeout(
		ctx,
		pairName,
		peerPairNegotiationTimeout,
		offerer,
		answerer,
		requiredMediaSections...,
	)
}

func negotiateLoopbackPeersWithTimeout(
	ctx context.Context,
	pairName string,
	timeout time.Duration,
	offerer, answerer *webrtc.PeerConnection,
	requiredMediaSections ...string,
) error {
	pairCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	result := make(chan error, 1)
	go func() {
		result <- negotiateLoopbackPeersUntil(
			pairCtx,
			offerer,
			answerer,
			requiredMediaSections...,
		)
	}()
	select {
	case err := <-result:
		if err != nil {
			reason := "failed"
			if errors.Is(err, context.DeadlineExceeded) {
				reason = "per-pair timeout"
				if ctx.Err() != nil {
					reason = "parent context ended"
				}
			}
			return fmt.Errorf(
				"peer pair %s %s (limit=%s offerer=%s answerer=%s): %w",
				pairName,
				reason,
				timeout,
				offerer.ConnectionState(),
				answerer.ConnectionState(),
				err,
			)
		}
		return nil
	case <-pairCtx.Done():
		offererState, answererState := offerer.ConnectionState(), answerer.ConnectionState()
		closeErr := errors.Join(offerer.Close(), answerer.Close())
		reason := "per-pair timeout"
		if ctx.Err() != nil {
			reason = "parent context ended"
		}
		timeoutErr := fmt.Errorf(
			"peer pair %s %s (limit=%s offerer=%s answerer=%s): %w",
			pairName,
			reason,
			timeout,
			offererState,
			answererState,
			pairCtx.Err(),
		)
		return errors.Join(timeoutErr, closeErr)
	}
}

func negotiateLoopbackPeersUntil(
	ctx context.Context,
	offerer, answerer *webrtc.PeerConnection,
	requiredMediaSections ...string,
) error {
	offer, err := offerer.CreateOffer(nil)
	if err != nil {
		return fmt.Errorf("create offer: %w", err)
	}
	for _, section := range requiredMediaSections {
		if !strings.Contains(offer.SDP, section) {
			return fmt.Errorf("offer does not contain required media section %q", section)
		}
	}
	offerGathered := webrtc.GatheringCompletePromise(offerer)
	if err := offerer.SetLocalDescription(offer); err != nil {
		return fmt.Errorf("set local offer: %w", err)
	}
	if err := waitForGathering(ctx, offerGathered); err != nil {
		return fmt.Errorf("gather offer ICE candidates: %w", err)
	}
	if err := answerer.SetRemoteDescription(*offerer.LocalDescription()); err != nil {
		return fmt.Errorf("set remote offer: %w", err)
	}
	answer, err := answerer.CreateAnswer(nil)
	if err != nil {
		return fmt.Errorf("create answer: %w", err)
	}
	answerGathered := webrtc.GatheringCompletePromise(answerer)
	if err := answerer.SetLocalDescription(answer); err != nil {
		return fmt.Errorf("set local answer: %w", err)
	}
	if err := waitForGathering(ctx, answerGathered); err != nil {
		return fmt.Errorf("gather answer ICE candidates: %w", err)
	}
	if err := offerer.SetRemoteDescription(*answerer.LocalDescription()); err != nil {
		return fmt.Errorf("set remote answer: %w", err)
	}
	if err := waitForConnected(ctx, offerer, answerer); err != nil {
		return err
	}
	return nil
}

func negotiateLoopbackPairsBounded(
	ctx context.Context,
	pairs []peerNegotiationPair,
	concurrency int,
) error {
	if concurrency < 1 {
		return errors.New("peer negotiation concurrency must be positive")
	}
	if len(pairs) == 0 {
		return nil
	}
	workerCount := min(concurrency, len(pairs))
	workCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	jobs := make(chan peerNegotiationPair)
	var workers sync.WaitGroup
	var firstErr error
	var errMu sync.Mutex
	for range workerCount {
		workers.Add(1)
		go func() {
			defer workers.Done()
			for {
				if workCtx.Err() != nil {
					return
				}
				select {
				case <-workCtx.Done():
					return
				case pair, ok := <-jobs:
					if !ok {
						return
					}
					if err := negotiateLoopbackPeers(
						workCtx,
						pair.name,
						pair.offerer,
						pair.answerer,
						pair.mediaSections...,
					); err != nil {
						errMu.Lock()
						if firstErr == nil {
							firstErr = err
						}
						errMu.Unlock()
						cancel()
						return
					}
				}
			}
		}()
	}
	for _, pair := range pairs {
		if workCtx.Err() != nil {
			break
		}
		select {
		case jobs <- pair:
		case <-workCtx.Done():
		}
	}
	close(jobs)
	workers.Wait()
	errMu.Lock()
	err := firstErr
	errMu.Unlock()
	if err != nil {
		return err
	}
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("peer negotiation phase canceled: %w", err)
	}
	return nil
}

func loopbackSettings(withUDPMux bool) (webrtc.SettingEngine, ice.UDPMux, error) {
	interfaces, err := net.Interfaces()
	if err != nil {
		return webrtc.SettingEngine{}, nil, fmt.Errorf("enumerate local interfaces: %w", err)
	}
	loopbackInterfaces := make(map[string]struct{})
	for _, iface := range interfaces {
		if iface.Flags&net.FlagLoopback != 0 {
			loopbackInterfaces[iface.Name] = struct{}{}
		}
	}
	if len(loopbackInterfaces) == 0 {
		return webrtc.SettingEngine{}, nil, errors.New("no loopback network interface is available")
	}

	settings := webrtc.SettingEngine{}
	settings.SetNetworkTypes([]webrtc.NetworkType{webrtc.NetworkTypeUDP4})
	settings.SetIncludeLoopbackCandidate(true)
	settings.SetInterfaceFilter(func(name string) bool {
		_, ok := loopbackInterfaces[name]
		return ok
	})
	settings.SetIPFilter(func(ip net.IP) bool {
		return ip.IsLoopback()
	})

	if !withUDPMux {
		return settings, nil, nil
	}
	udpMux, err := ice.NewMultiUDPMuxFromPort(
		0,
		ice.UDPMuxFromPortWithNetworks(ice.NetworkTypeUDP4),
		ice.UDPMuxFromPortWithLoopback(),
		ice.UDPMuxFromPortWithInterfaceFilter(func(name string) bool {
			_, ok := loopbackInterfaces[name]
			return ok
		}),
		ice.UDPMuxFromPortWithIPFilter(func(ip net.IP) bool {
			return ip.IsLoopback()
		}),
	)
	if err != nil {
		return webrtc.SettingEngine{}, nil, fmt.Errorf("create loopback ICE UDP mux: %w", err)
	}
	settings.SetICEUDPMux(udpMux)
	return settings, udpMux, nil
}

func drainRTCP(sender *webrtc.RTPSender) {
	go func() {
		buffer := make([]byte, 1500)
		for {
			if _, _, err := sender.Read(buffer); err != nil {
				return
			}
		}
	}()
}

func waitForGathering(ctx context.Context, gathered <-chan struct{}) error {
	select {
	case <-gathered:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func waitForConnected(ctx context.Context, publisher, subscriber *webrtc.PeerConnection) error {
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()
	for {
		if publisher.ConnectionState() == webrtc.PeerConnectionStateConnected &&
			subscriber.ConnectionState() == webrtc.PeerConnectionStateConnected {
			return nil
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("PeerConnections did not connect (publisher=%s subscriber=%s): %w",
				publisher.ConnectionState(), subscriber.ConnectionState(), ctx.Err())
		case <-ticker.C:
		}
	}
}

func sendMedia(
	ctx context.Context,
	audioTrack, videoTrack *webrtc.TrackLocalStaticSample,
	videoFrames []media.Sample,
) (sendCounts, error) {
	ticker := time.NewTicker(audioFrameDuration)
	defer ticker.Stop()
	var counts sendCounts
	for {
		select {
		case <-ctx.Done():
			return counts, nil
		case <-ticker.C:
			audioData := pcmuToneFrame(int(counts.audioSamples))
			if err := audioTrack.WriteSample(media.Sample{Data: audioData, Duration: audioFrameDuration}); err != nil {
				return counts, fmt.Errorf("write PCMU sample: %w", err)
			}
			counts.audioSamples++
			if counts.audioSamples%3 == 0 {
				frame := videoFrames[(counts.videoFrames)%uint64(len(videoFrames))]
				if err := videoTrack.WriteSample(frame); err != nil {
					return counts, fmt.Errorf("write H.264 frame: %w", err)
				}
				counts.videoFrames++
			}
		}
	}
}

func pcmuToneFrame(frameNumber int) []byte {
	payload := make([]byte, audioSamplesFrame)
	for i := range payload {
		sampleIndex := frameNumber*audioSamplesFrame + i
		pcm := int(12000 * math.Sin(2*math.Pi*440*float64(sampleIndex)/audioSampleRate))
		payload[i] = linearToPCMU(int16(pcm))
	}
	return payload
}

func linearToPCMU(sample int16) byte {
	const (
		bias = 0x84
		clip = 32635
	)
	value := int(sample)
	mask := 0xff
	if value < 0 {
		value = -value
		mask = 0x7f
	}
	if value > clip {
		value = clip
	}
	value += bias
	exponent := 7
	for bitMask := 0x4000; exponent > 0 && value&bitMask == 0; bitMask >>= 1 {
		exponent--
	}
	mantissa := (value >> (exponent + 3)) & 0x0f
	return byte((exponent<<4 | mantissa) ^ mask)
}

func waitForReceivedMedia(
	ctx context.Context,
	audio, video *streamCounter,
	trackErrors <-chan error,
) error {
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()
	for {
		if audio.snapshotResult().PacketsReceived > 0 && video.snapshotResult().PacketsReceived > 0 {
			return nil
		}
		select {
		case err := <-trackErrors:
			return err
		case <-ctx.Done():
			return fmt.Errorf("audio/video RTP was not received (audio=%d video=%d): %w",
				audio.snapshotResult().PacketsReceived, video.snapshotResult().PacketsReceived, ctx.Err())
		case <-ticker.C:
		}
	}
}

var errSFUUnauthorized = errors.New("viewer is not authorized for this track")

type sfuPublishedTrack struct {
	key             sfuTrackKey
	remote          *webrtc.TrackRemote
	publisherPeer   *webrtc.PeerConnection
	subscribers     map[string]*sfuSubscription
	firstFrameReady chan struct{}
	firstFrameOnce  sync.Once

	packetMu     sync.Mutex
	packetCache  map[uint16]*rtp.Packet
	packetOrder  [sfuNACKHistoryPackets]uint16
	packetStart  int
	packetCount  int
	lastSequence uint16
}

type sfuViewer struct {
	id            string
	peer          *webrtc.PeerConnection
	allowed       map[sfuTrackKey]struct{}
	subscriptions map[sfuTrackKey]*sfuSubscription
}

type sfuSubscription struct {
	viewerID   string
	key        sfuTrackKey
	source     *sfuPublishedTrack
	viewerPeer *webrtc.PeerConnection
	downTrack  *webrtc.TrackLocalStaticRTP
	sender     *webrtc.RTPSender

	mu       sync.RWMutex
	active   bool
	statsMu  sync.Mutex
	feedback sfuFeedbackCounts
	// retransmittedAt records, per RTP sequence number, when this
	// subscription last retransmitted it (NACK aggregation, M6-H
	// attempt 8). Owned by the nackWorker goroutine only — handleNACK's
	// sole caller since attempt 10 — so no lock guards it.
	retransmittedAt map[uint16]time.Time
	nackQueue       chan queuedNACK
	// nackQueueClosed records that nackQueue was closed; guarded by mu.
	nackQueueClosed bool
}

type sfuRouter struct {
	mu                 sync.RWMutex
	publishers         map[string]*webrtc.PeerConnection
	tracks             map[sfuTrackKey]*sfuPublishedTrack
	viewers            map[string]*sfuViewer
	feedbackSenderSSRC uint32
	closed             bool
	forwardingErrors   []string
	rtpForwarded       atomic.Uint64
	rtpDropped         atomic.Uint64
	rtpForwardNanos    atomic.Uint64
	rtpForwardSamples  atomic.Uint64
	rtpForwardBuckets  [rtpForwardLatencyBucketCount]atomic.Uint64
}

type queuedNACK struct {
	feedback   *rtcp.TransportLayerNack
	enqueuedAt time.Time
}

type sfuMediaSource struct {
	key                 sfuTrackKey
	track               *webrtc.TrackLocalStaticSample
	sender              *webrtc.RTPSender
	initialRTPTimestamp uint32
}

type sfuTrackSpec struct {
	publisherID string
	trackID     string
}

type sfuProofConfig struct {
	proofID            string
	tracks             []sfuTrackSpec
	viewerTrackIndexes []int
	measureLatency     bool
	exerciseRTCP       bool
	videoInterval      time.Duration
}

type sfuSendResult struct {
	frames            uint64
	framesByPublisher map[string]uint64
	err               error
}

type sfuViewerCapture struct {
	mu              sync.Mutex
	tracks          map[string]*streamCounter
	sequenceCounts  map[string]map[uint16]uint64
	duplicates      map[string]uint64
	latencyClock    *FrameClock
	latencyRecorder *LatencyRecorder
	errors          chan error
	received        chan struct{}
}

type videoFrameAssembler struct {
	active                 bool
	timestamp              uint32
	frameSequences         map[uint16]struct{}
	markerSequence         uint16
	markerSeen             bool
	nextFrameFirstSequence uint16
	frameBoundaryKnown     bool
	lastFinalizedTimestamp uint32
	hasFinalizedTimestamp  bool
}

type sfuFeedbackEvent struct {
	trackID   string
	kind      string
	mediaSSRC uint32
	targets   []uint32
	nacks     []rtcp.NackPair
}

type viewerEndpoint struct {
	id       string
	key      sfuTrackKey
	client   *webrtc.PeerConnection
	capture  *sfuViewerCapture
	recorder *LatencyRecorder
}

type peerNegotiationPair struct {
	name          string
	offerer       *webrtc.PeerConnection
	answerer      *webrtc.PeerConnection
	mediaSections []string
}

func newSFURouter(api *webrtc.API) (*sfuRouter, error) {
	if api == nil {
		return nil, errors.New("Pion API is required")
	}
	var senderSSRCBytes [4]byte
	if _, err := rand.Read(senderSSRCBytes[:]); err != nil {
		return nil, fmt.Errorf("create SFU RTCP sender SSRC: %w", err)
	}
	senderSSRC := binary.BigEndian.Uint32(senderSSRCBytes[:])
	if senderSSRC == 0 {
		senderSSRC = 1
	}
	router := &sfuRouter{
		publishers:         make(map[string]*webrtc.PeerConnection),
		tracks:             make(map[sfuTrackKey]*sfuPublishedTrack),
		viewers:            make(map[string]*sfuViewer),
		feedbackSenderSSRC: senderSSRC,
	}
	return router, nil
}

func (r *sfuRouter) registerPublisher(
	api *webrtc.API,
	publisherID string,
) (*webrtc.PeerConnection, error) {
	if api == nil {
		return nil, errors.New("Pion API is required")
	}
	if publisherID == "" {
		return nil, errors.New("publisher identity is required")
	}
	peer, err := api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		return nil, fmt.Errorf("create publisher %s PeerConnection: %w", publisherID, err)
	}
	r.mu.Lock()
	if r.closed {
		r.mu.Unlock()
		_ = peer.Close()
		return nil, errors.New("SFU router is closed")
	}
	if _, exists := r.publishers[publisherID]; exists {
		r.mu.Unlock()
		_ = peer.Close()
		return nil, fmt.Errorf("publisher %q is already registered", publisherID)
	}
	r.publishers[publisherID] = peer
	r.mu.Unlock()

	peer.OnTrack(func(track *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		if err := r.registerTrack(publisherID, track); err != nil {
			r.recordError(fmt.Errorf("register publisher %s track: %w", publisherID, err))
		}
	})
	return peer, nil
}

func (r *sfuRouter) registerTrack(publisherID string, remote *webrtc.TrackRemote) error {
	if remote == nil {
		return errors.New("publisher track is required")
	}
	key := sfuTrackKey{PublisherID: publisherID, TrackID: remote.ID()}
	if key.TrackID == "" {
		return errors.New("publisher track ID is required")
	}
	track := &sfuPublishedTrack{
		key:             key,
		remote:          remote,
		subscribers:     make(map[string]*sfuSubscription),
		firstFrameReady: make(chan struct{}),
		packetCache:     make(map[uint16]*rtp.Packet, sfuNACKHistoryPackets),
	}
	r.mu.Lock()
	if r.closed {
		r.mu.Unlock()
		return errors.New("SFU router is closed")
	}
	track.publisherPeer = r.publishers[publisherID]
	if track.publisherPeer == nil {
		r.mu.Unlock()
		return fmt.Errorf("publisher %q is not registered", publisherID)
	}
	if _, exists := r.tracks[key]; exists {
		r.mu.Unlock()
		return fmt.Errorf("publisher track %q is already registered", key.TrackID)
	}
	r.tracks[key] = track
	r.mu.Unlock()

	go r.forwardTrack(track)
	return nil
}

func (r *sfuRouter) registerViewer(viewerID string, peer *webrtc.PeerConnection) error {
	if viewerID == "" {
		return errors.New("viewer identity is required")
	}
	if peer == nil {
		return errors.New("viewer PeerConnection is required")
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return errors.New("SFU router is closed")
	}
	if _, exists := r.viewers[viewerID]; exists {
		return fmt.Errorf("viewer %q is already registered", viewerID)
	}
	r.viewers[viewerID] = &sfuViewer{
		id:            viewerID,
		peer:          peer,
		allowed:       make(map[sfuTrackKey]struct{}),
		subscriptions: make(map[sfuTrackKey]*sfuSubscription),
	}
	return nil
}

func (r *sfuRouter) authorizeSubscription(viewerID string, key sfuTrackKey) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return errors.New("SFU router is closed")
	}
	viewer, exists := r.viewers[viewerID]
	if !exists {
		return fmt.Errorf("viewer %q is not registered", viewerID)
	}
	if _, exists := r.tracks[key]; !exists {
		return fmt.Errorf("publisher track %q is not registered", key.TrackID)
	}
	viewer.allowed[key] = struct{}{}
	return nil
}

func (r *sfuRouter) subscribe(viewerID string, key sfuTrackKey) error {
	r.mu.Lock()
	if r.closed {
		r.mu.Unlock()
		return errors.New("SFU router is closed")
	}
	viewer, viewerExists := r.viewers[viewerID]
	if !viewerExists {
		r.mu.Unlock()
		return fmt.Errorf("viewer %q is not registered", viewerID)
	}
	if _, allowed := viewer.allowed[key]; !allowed {
		r.mu.Unlock()
		return fmt.Errorf("%w: viewer=%s track=%s", errSFUUnauthorized, viewerID, key.TrackID)
	}
	source, trackExists := r.tracks[key]
	if !trackExists {
		r.mu.Unlock()
		return fmt.Errorf("publisher track %q is not registered", key.TrackID)
	}
	if _, exists := viewer.subscriptions[key]; exists {
		r.mu.Unlock()
		return fmt.Errorf("viewer %q already subscribes to track %q", viewerID, key.TrackID)
	}
	downTrack, err := webrtc.NewTrackLocalStaticRTP(
		source.remote.Codec().RTPCodecCapability,
		source.remote.ID(),
		source.remote.StreamID(),
	)
	if err != nil {
		r.mu.Unlock()
		return fmt.Errorf("create viewer downtrack: %w", err)
	}
	sender, err := viewer.peer.AddTrack(downTrack)
	if err != nil {
		r.mu.Unlock()
		return fmt.Errorf("add viewer downtrack: %w", err)
	}
	subscription := &sfuSubscription{
		viewerID:        viewerID,
		key:             key,
		source:          source,
		viewerPeer:      viewer.peer,
		downTrack:       downTrack,
		sender:          sender,
		active:          true,
		retransmittedAt: make(map[uint16]time.Time),
		nackQueue:       make(chan queuedNACK, nackQueueSize),
	}
	viewer.subscriptions[key] = subscription
	source.subscribers[viewerID] = subscription
	r.mu.Unlock()

	go r.forwardFeedback(subscription)
	go r.nackWorker(subscription)
	return nil
}

func (r *sfuRouter) unsubscribe(viewerID string, key sfuTrackKey) error {
	r.mu.Lock()
	viewer := r.viewers[viewerID]
	if viewer == nil {
		r.mu.Unlock()
		return fmt.Errorf("viewer %q is not registered", viewerID)
	}
	subscription := viewer.subscriptions[key]
	if subscription == nil {
		r.mu.Unlock()
		return fmt.Errorf("viewer %q is not subscribed to track %q", viewerID, key.TrackID)
	}
	delete(viewer.subscriptions, key)
	if source := r.tracks[key]; source != nil {
		delete(source.subscribers, viewerID)
	}
	r.mu.Unlock()

	subscription.stop()
	if err := viewer.peer.RemoveTrack(subscription.sender); err != nil {
		return fmt.Errorf("remove viewer downtrack: %w", err)
	}
	return nil
}

func (r *sfuRouter) unregisterTrack(key sfuTrackKey) error {
	return r.unregisterTrackIfCurrent(key, nil)
}

func (r *sfuRouter) unregisterTrackIfCurrent(key sfuTrackKey, expected *sfuPublishedTrack) error {
	r.mu.Lock()
	source := r.tracks[key]
	if source == nil || (expected != nil && source != expected) {
		r.mu.Unlock()
		return nil
	}
	delete(r.tracks, key)
	subscriptions := make([]*sfuSubscription, 0, len(source.subscribers))
	for _, viewer := range r.viewers {
		delete(viewer.allowed, key)
	}
	for viewerID, subscription := range source.subscribers {
		subscriptions = append(subscriptions, subscription)
		if viewer := r.viewers[viewerID]; viewer != nil {
			delete(viewer.subscriptions, key)
		}
	}
	source.subscribers = make(map[string]*sfuSubscription)
	r.mu.Unlock()

	var errs []error
	if err := source.remote.SetReadDeadline(time.Now()); err != nil {
		errs = append(errs, fmt.Errorf("stop publisher track %s reader: %w", key.TrackID, err))
	}
	for _, subscription := range subscriptions {
		subscription.stop()
		if err := subscription.viewerPeer.RemoveTrack(subscription.sender); err != nil {
			errs = append(errs, fmt.Errorf("remove viewer %s downtrack: %w", subscription.viewerID, err))
		}
	}
	return errors.Join(errs...)
}

func (r *sfuRouter) removeViewer(viewerID string) error {
	r.mu.Lock()
	viewer := r.viewers[viewerID]
	if viewer == nil {
		r.mu.Unlock()
		return fmt.Errorf("viewer %q is not registered", viewerID)
	}
	delete(r.viewers, viewerID)
	subscriptions := make([]*sfuSubscription, 0, len(viewer.subscriptions))
	for key, subscription := range viewer.subscriptions {
		subscriptions = append(subscriptions, subscription)
		if source := r.tracks[key]; source != nil {
			delete(source.subscribers, viewerID)
		}
	}
	viewer.subscriptions = make(map[sfuTrackKey]*sfuSubscription)
	r.mu.Unlock()

	for _, subscription := range subscriptions {
		subscription.stop()
	}
	if err := viewer.peer.Close(); err != nil {
		return fmt.Errorf("close viewer %s PeerConnection: %w", viewerID, err)
	}
	return nil
}

func (r *sfuRouter) close() error {
	r.mu.Lock()
	if r.closed {
		r.mu.Unlock()
		return nil
	}
	r.closed = true
	viewers := make([]*sfuViewer, 0, len(r.viewers))
	subscriptions := make([]*sfuSubscription, 0)
	publishers := make(map[string]*webrtc.PeerConnection, len(r.publishers))
	for publisherID, peer := range r.publishers {
		publishers[publisherID] = peer
	}
	for _, viewer := range r.viewers {
		viewers = append(viewers, viewer)
		for _, subscription := range viewer.subscriptions {
			subscriptions = append(subscriptions, subscription)
		}
	}
	r.viewers = make(map[string]*sfuViewer)
	r.publishers = make(map[string]*webrtc.PeerConnection)
	r.tracks = make(map[sfuTrackKey]*sfuPublishedTrack)
	r.mu.Unlock()

	for _, subscription := range subscriptions {
		subscription.stop()
	}
	var errs []error
	for _, viewer := range viewers {
		if err := viewer.peer.Close(); err != nil {
			errs = append(errs, fmt.Errorf("close viewer %s PeerConnection: %w", viewer.id, err))
		}
	}
	for publisherID, peer := range publishers {
		if err := peer.Close(); err != nil {
			errs = append(errs, fmt.Errorf("close publisher %s PeerConnection: %w", publisherID, err))
		}
	}
	return errors.Join(errs...)
}

func (r *sfuRouter) counts() (tracks, viewers, subscriptions, authorizations int) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	for _, viewer := range r.viewers {
		subscriptions += len(viewer.subscriptions)
		authorizations += len(viewer.allowed)
	}
	return len(r.tracks), len(r.viewers), subscriptions, authorizations
}

func (r *sfuRouter) errorsSnapshot() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return append([]string(nil), r.forwardingErrors...)
}

func (r *sfuRouter) recordError(err error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if !r.closed {
		r.forwardingErrors = append(r.forwardingErrors, err.Error())
	}
}

func (r *sfuRouter) startMetricsServer(address string) (*http.Server, error) {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return nil, fmt.Errorf("invalid metrics listen address %q: %w", address, err)
	}
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		return nil, fmt.Errorf("metrics endpoint must bind to a loopback IP, got %q", host)
	}
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return nil, fmt.Errorf("listen for Prometheus metrics on %s: %w", address, err)
	}
	server := &http.Server{
		Handler:           r.metricsHandler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	server.Addr = listener.Addr().String()
	go func() {
		if err := server.Serve(listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
			r.recordError(fmt.Errorf("serve Prometheus metrics: %w", err))
		}
	}()
	return server, nil
}

func (r *sfuRouter) metricsHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		if err := r.writePrometheusMetrics(w); err != nil {
			fmt.Fprintf(os.Stderr, "write Prometheus metrics: %v\n", err)
		}
	})
	return mux
}

func (r *sfuRouter) writePrometheusMetrics(w io.Writer) error {
	r.mu.RLock()
	tracks := len(r.tracks)
	viewers := len(r.viewers)
	var subscriptions int
	var feedback sfuFeedbackCounts
	for _, viewer := range r.viewers {
		for _, subscription := range viewer.subscriptions {
			subscriptions++
			current := subscription.feedbackSnapshot()
			feedback.NACKReceived += current.NACKReceived
			feedback.NACKRetransmitted += current.NACKRetransmitted
			feedback.NACKForwarded += current.NACKForwarded
			feedback.NACKDuplicatesSkipped += current.NACKDuplicatesSkipped
			feedback.NACKSequencesCapped += current.NACKSequencesCapped
			feedback.NACKEnqueued += current.NACKEnqueued
			feedback.NACKDroppedQueueFull += current.NACKDroppedQueueFull
			feedback.NACKDroppedStale += current.NACKDroppedStale
			feedback.NACKQueueDepth += current.NACKQueueDepth
			feedback.PLIForwarded += current.PLIForwarded
			feedback.FIRForwarded += current.FIRForwarded
		}
	}
	r.mu.RUnlock()

	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	cpuSample := []runtimemetrics.Sample{{Name: "/cpu/classes/total:cpu-seconds"}}
	runtimemetrics.Read(cpuSample)
	var cpuSeconds float64
	if cpuSample[0].Value.Kind() == runtimemetrics.KindFloat64 {
		cpuSeconds = cpuSample[0].Value.Float64()
	}

	var output strings.Builder
	fmt.Fprintf(&output, "# TYPE hami_sfu_tracks gauge\nhami_sfu_tracks %d\n", tracks)
	fmt.Fprintf(&output, "# TYPE hami_sfu_viewers gauge\nhami_sfu_viewers %d\n", viewers)
	fmt.Fprintf(&output, "# TYPE hami_sfu_subscriptions gauge\nhami_sfu_subscriptions %d\n", subscriptions)
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_forwarded_packets_total counter\nhami_sfu_rtp_forwarded_packets_total %d\n", r.rtpForwarded.Load())
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_forward_errors_total counter\nhami_sfu_rtp_forward_errors_total %d\n", r.rtpDropped.Load())
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_forward_seconds histogram\n")
	var cumulative uint64
	for index, bound := range rtpForwardLatencyBuckets {
		cumulative += r.rtpForwardBuckets[index].Load()
		fmt.Fprintf(&output, "hami_sfu_rtp_forward_seconds_bucket{le=\"%g\"} %d\n",
			bound.Seconds(), cumulative)
	}
	cumulative += r.rtpForwardBuckets[len(rtpForwardLatencyBuckets)].Load()
	fmt.Fprintf(&output, "hami_sfu_rtp_forward_seconds_bucket{le=\"+Inf\"} %d\n", cumulative)
	fmt.Fprintf(&output, "hami_sfu_rtp_forward_seconds_sum %g\n", float64(r.rtpForwardNanos.Load())/float64(time.Second))
	fmt.Fprintf(&output, "hami_sfu_rtp_forward_seconds_count %d\n", r.rtpForwardSamples.Load())
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_received_total counter\nhami_sfu_nack_received_total %d\n", feedback.NACKReceived)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_retransmitted_packets_total counter\nhami_sfu_nack_retransmitted_packets_total %d\n", feedback.NACKRetransmitted)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_duplicates_skipped_total counter\nhami_sfu_nack_duplicates_skipped_total %d\n", feedback.NACKDuplicatesSkipped)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_sequences_capped_total counter\nhami_sfu_nack_sequences_capped_total %d\n", feedback.NACKSequencesCapped)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_enqueued_total counter\nhami_sfu_nack_enqueued_total %d\n", feedback.NACKEnqueued)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_dropped_queue_full_total counter\nhami_sfu_nack_dropped_queue_full_total %d\n", feedback.NACKDroppedQueueFull)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_dropped_stale_total counter\nhami_sfu_nack_dropped_stale_total %d\n", feedback.NACKDroppedStale)
	fmt.Fprintf(&output, "# TYPE hami_sfu_nack_queue_depth gauge\nhami_sfu_nack_queue_depth %d\n", feedback.NACKQueueDepth)
	fmt.Fprintf(&output, "# TYPE hami_sfu_pli_forwarded_total counter\nhami_sfu_pli_forwarded_total %d\n", feedback.PLIForwarded)
	fmt.Fprintf(&output, "# TYPE hami_sfu_fir_forwarded_total counter\nhami_sfu_fir_forwarded_total %d\n", feedback.FIRForwarded)
	fmt.Fprintf(&output, "# TYPE hami_process_cpu_seconds_total counter\nhami_process_cpu_seconds_total %g\n", cpuSeconds)
	fmt.Fprintf(&output, "# TYPE go_memstats_heap_alloc_bytes gauge\ngo_memstats_heap_alloc_bytes %d\n", memory.HeapAlloc)
	fmt.Fprintf(&output, "# TYPE go_memstats_sys_bytes gauge\ngo_memstats_sys_bytes %d\n", memory.Sys)
	fmt.Fprintf(&output, "# TYPE go_goroutines gauge\ngo_goroutines %d\n", runtime.NumGoroutine())
	_, err := io.WriteString(w, output.String())
	return err
}

func (r *sfuRouter) forwardTrack(source *sfuPublishedTrack) {
	for {
		packet, _, err := source.remote.ReadRTP()
		if err != nil {
			r.mu.RLock()
			active := !r.closed && r.tracks[source.key] == source
			r.mu.RUnlock()
			if active {
				r.recordError(fmt.Errorf("read publisher track %s RTP: %w", source.key.TrackID, err))
				if unregisterErr := r.unregisterTrackIfCurrent(source.key, source); unregisterErr != nil {
					r.recordError(unregisterErr)
				}
			}
			return
		}
		source.rememberPacket(packet)
		if packet.Marker {
			source.firstFrameOnce.Do(func() { close(source.firstFrameReady) })
		}
		r.mu.RLock()
		if r.closed || r.tracks[source.key] != source {
			r.mu.RUnlock()
			return
		}
		subscriptions := make([]*sfuSubscription, 0, len(source.subscribers))
		for _, subscription := range source.subscribers {
			subscriptions = append(subscriptions, subscription)
		}
		r.mu.RUnlock()

		for _, subscription := range subscriptions {
			started := time.Now()
			sent, err := subscription.writeRTP(packet)
			if sent {
				elapsed := time.Since(started)
				r.rtpForwarded.Add(1)
				r.rtpForwardNanos.Add(uint64(elapsed))
				r.rtpForwardSamples.Add(1)
				bucket := len(rtpForwardLatencyBuckets)
				for index, bound := range rtpForwardLatencyBuckets {
					if elapsed <= bound {
						bucket = index
						break
					}
				}
				r.rtpForwardBuckets[bucket].Add(1)
			}
			if err != nil && subscription.isActive() {
				r.rtpDropped.Add(1)
				r.recordError(fmt.Errorf("forward track %s to viewer %s: %w",
					source.key.TrackID, subscription.viewerID, err))
			}
		}
	}
}

func (t *sfuPublishedTrack) rememberPacket(packet *rtp.Packet) {
	t.packetMu.Lock()
	defer t.packetMu.Unlock()
	sequence := packet.SequenceNumber
	t.lastSequence = sequence
	if _, exists := t.packetCache[sequence]; exists {
		t.packetCache[sequence] = packet.Clone()
		return
	}
	if t.packetCount == len(t.packetOrder) {
		oldest := t.packetOrder[t.packetStart]
		delete(t.packetCache, oldest)
		t.packetOrder[t.packetStart] = sequence
		t.packetStart = (t.packetStart + 1) % len(t.packetOrder)
	} else {
		index := (t.packetStart + t.packetCount) % len(t.packetOrder)
		t.packetOrder[index] = sequence
		t.packetCount++
	}
	t.packetCache[sequence] = packet.Clone()
}

func (t *sfuPublishedTrack) cachedPackets(sequences []uint16) ([]*rtp.Packet, []uint16) {
	t.packetMu.Lock()
	defer t.packetMu.Unlock()
	packets := make([]*rtp.Packet, 0, len(sequences))
	missing := make([]uint16, 0, len(sequences))
	seen := make(map[uint16]struct{}, len(sequences))
	for _, sequence := range sequences {
		if _, exists := seen[sequence]; exists {
			continue
		}
		seen[sequence] = struct{}{}
		packet, exists := t.packetCache[sequence]
		if !exists {
			missing = append(missing, sequence)
			continue
		}
		packets = append(packets, packet.Clone())
	}
	return packets, missing
}

func (t *sfuPublishedTrack) latestSequence() uint16 {
	t.packetMu.Lock()
	defer t.packetMu.Unlock()
	return t.lastSequence
}

func (s *sfuSubscription) writeRTP(packet *rtp.Packet) (bool, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if !s.active {
		return false, nil
	}
	if err := s.downTrack.WriteRTP(packet); err != nil {
		return false, err
	}
	return true, nil
}

func (s *sfuSubscription) stop() {
	s.mu.Lock()
	s.active = false
	// Closing the queue wakes nackWorker; queued retransmissions are no
	// longer useful after unsubscribe and are discarded by the worker.
	if s.nackQueue != nil && !s.nackQueueClosed {
		close(s.nackQueue)
		s.nackQueueClosed = true
	}
	s.mu.Unlock()
}

func (s *sfuSubscription) isActive() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.active
}

func (s *sfuSubscription) recordFeedback(kind string) {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	switch kind {
	case "pli":
		s.feedback.PLIForwarded++
	case "fir":
		s.feedback.FIRForwarded++
	}
}

func (s *sfuSubscription) recordNACKReceived() {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.NACKReceived++
}

func (s *sfuSubscription) recordNACK(retransmitted, forwarded, duplicates, capped uint64) {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.NACKRetransmitted += retransmitted
	s.feedback.NACKForwarded += forwarded
	s.feedback.NACKDuplicatesSkipped += duplicates
	s.feedback.NACKSequencesCapped += capped
}

// recordNACKEnqueued counts a NACK accepted into the worker queue.
func (s *sfuSubscription) recordNACKEnqueued() {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.NACKEnqueued++
}

// recordNACKDroppedQueueFull counts a NACK dropped because the worker
// queue was full (the oldest queued NACK is dropped to make room).
func (s *sfuSubscription) recordNACKDroppedQueueFull() {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.NACKDroppedQueueFull++
}

func (s *sfuSubscription) recordNACKDroppedStale() {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.NACKDroppedStale++
}

// enqueueNACK hands a NACK to the retransmission worker without ever
// blocking the caller. Call only while holding s.mu (read or write):
// stop() closes the queue under mu, so a send here cannot race the
// close. When the queue is full the oldest queued NACK is dropped and
// counted, so the newest loss information is kept.
func (s *sfuSubscription) enqueueNACK(nack *rtcp.TransportLayerNack) {
	s.recordNACKReceived()
	entry := queuedNACK{feedback: nack, enqueuedAt: time.Now()}
	select {
	case s.nackQueue <- entry:
		s.recordNACKEnqueued()
	default:
		select {
		case <-s.nackQueue:
			s.recordNACKDroppedQueueFull()
		default:
		}
		select {
		case s.nackQueue <- entry:
			s.recordNACKEnqueued()
		default:
			s.recordNACKDroppedQueueFull()
		}
	}
}

func (s *sfuSubscription) feedbackSnapshot() sfuFeedbackCounts {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	feedback := s.feedback
	feedback.NACKQueueDepth = uint64(len(s.nackQueue))
	return feedback
}

func (r *sfuRouter) forwardFeedback(subscription *sfuSubscription) {
	for {
		packets, _, err := subscription.sender.ReadRTCP()
		if err != nil {
			if subscription.isActive() {
				r.recordError(fmt.Errorf(
					"read viewer %s RTCP feedback: %w",
					subscription.viewerID,
					err,
				))
			}
			return
		}
		for _, packet := range packets {
			if nack, ok := packet.(*rtcp.TransportLayerNack); ok {
				// M6-H attempt 10: never handle a NACK in the read
				// loop. handleNACK's synchronous retransmit work
				// (up to 128 WriteRTP calls per NACK) drowned this
				// loop at 5 fps and starved PLI/FIR (attempt 9:
				// 132/1,000 tracks). Queue it for the worker and
				// return to ReadRTCP at once.
				subscription.mu.RLock()
				if subscription.active {
					subscription.enqueueNACK(nack)
				}
				subscription.mu.RUnlock()
				continue
			}
			translated, kind, err := r.translateFeedback(subscription, packet)
			if err != nil {
				r.recordError(fmt.Errorf("translate viewer %s feedback: %w", subscription.viewerID, err))
				continue
			}
			if translated == nil {
				continue
			}
			subscription.mu.RLock()
			if !subscription.active {
				subscription.mu.RUnlock()
				return
			}
			err = subscription.source.publisherPeer.WriteRTCP([]rtcp.Packet{translated})
			subscription.mu.RUnlock()
			if err != nil {
				r.recordError(fmt.Errorf("forward viewer %s feedback upstream: %w", subscription.viewerID, err))
				continue
			}
			subscription.recordFeedback(kind)
		}
	}
}

func (r *sfuRouter) nackWorker(subscription *sfuSubscription) {
	for entry := range subscription.nackQueue {
		if !subscription.isActive() {
			return
		}
		if time.Since(entry.enqueuedAt) > nackMaxQueueAge {
			subscription.recordNACKDroppedStale()
			continue
		}
		if err := r.handleNACK(subscription, entry.feedback); err != nil {
			r.recordError(fmt.Errorf("handle viewer %s NACK: %w", subscription.viewerID, err))
		}
	}
}

func selectNACKSequences(
	pairs []rtcp.NackPair,
	lastSequence uint16,
	retransmittedAt map[uint16]time.Time,
	now time.Time,
) ([]uint16, uint64, uint64) {
	sequences := make([]uint16, 0)
	seen := make(map[uint16]struct{})
	var duplicates uint64
	for _, pair := range pairs {
		for _, sequence := range pair.PacketList() {
			if _, exists := seen[sequence]; exists {
				duplicates++
				continue
			}
			seen[sequence] = struct{}{}
			sequences = append(sequences, sequence)
		}
	}
	sort.Slice(sequences, func(i, j int) bool {
		return uint16(lastSequence-sequences[i]) < uint16(lastSequence-sequences[j])
	})
	for sequence, retransmitted := range retransmittedAt {
		if now.Sub(retransmitted) > nackAggregationWindow {
			delete(retransmittedAt, sequence)
		}
	}
	fresh := make([]uint16, 0, min(len(sequences), maxSequencesPerNACK))
	var capped uint64
	for _, sequence := range sequences {
		if retransmitted, exists := retransmittedAt[sequence]; exists &&
			now.Sub(retransmitted) <= nackAggregationWindow {
			duplicates++
			continue
		}
		if len(fresh) == maxSequencesPerNACK {
			capped++
			continue
		}
		fresh = append(fresh, sequence)
	}
	return fresh, duplicates, capped
}

func (r *sfuRouter) handleNACK(subscription *sfuSubscription, feedback *rtcp.TransportLayerNack) error {
	params := subscription.sender.GetParameters()
	if len(params.Encodings) == 0 || params.Encodings[0].SSRC == 0 {
		return errors.New("viewer downtrack SSRC is not bound")
	}
	viewerSSRC := uint32(params.Encodings[0].SSRC)
	if feedback.MediaSSRC != viewerSSRC {
		return fmt.Errorf("NACK targets unexpected viewer SSRC %d", feedback.MediaSSRC)
	}
	if len(feedback.Nacks) == 0 {
		return errors.New("NACK contains no lost-packet entries")
	}
	now := time.Now()
	fresh, duplicates, capped := selectNACKSequences(
		feedback.Nacks,
		subscription.source.latestSequence(),
		subscription.retransmittedAt,
		now,
	)
	cached, missing := subscription.source.cachedPackets(fresh)
	var retransmitted uint64
	for _, packet := range cached {
		sent, err := subscription.writeRTP(packet)
		if err != nil {
			return fmt.Errorf("retransmit cached RTP packet: %w", err)
		}
		if sent {
			retransmitted++
			subscription.retransmittedAt[packet.SequenceNumber] = now
		}
	}
	var forwarded uint64
	if len(missing) != 0 {
		params := &rtcp.TransportLayerNack{
			SenderSSRC: r.feedbackSenderSSRC,
			MediaSSRC:  uint32(subscription.source.remote.SSRC()),
			Nacks:      rtcp.NackPairsFromSequenceNumbers(missing),
		}
		subscription.mu.RLock()
		if subscription.active {
			if err := subscription.source.publisherPeer.WriteRTCP([]rtcp.Packet{params}); err != nil {
				subscription.mu.RUnlock()
				return fmt.Errorf("forward uncached NACK upstream: %w", err)
			}
			forwarded = 1
		}
		subscription.mu.RUnlock()
	}
	subscription.recordNACK(retransmitted, forwarded, duplicates, capped)
	return nil
}

func (r *sfuRouter) translateFeedback(
	subscription *sfuSubscription,
	packet rtcp.Packet,
) (rtcp.Packet, string, error) {
	params := subscription.sender.GetParameters()
	if len(params.Encodings) == 0 || params.Encodings[0].SSRC == 0 {
		return nil, "", errors.New("viewer downtrack SSRC is not bound")
	}
	viewerSSRC := uint32(params.Encodings[0].SSRC)
	publisherSSRC := uint32(subscription.source.remote.SSRC())

	switch feedback := packet.(type) {
	case *rtcp.PictureLossIndication:
		if feedback.MediaSSRC != viewerSSRC {
			return nil, "", fmt.Errorf("PLI targets unexpected viewer SSRC %d", feedback.MediaSSRC)
		}
		return &rtcp.PictureLossIndication{
			SenderSSRC: r.feedbackSenderSSRC,
			MediaSSRC:  publisherSSRC,
		}, "pli", nil
	case *rtcp.FullIntraRequest:
		if len(feedback.FIR) == 0 {
			return nil, "", errors.New("FIR contains no target entries")
		}
		entries := make([]rtcp.FIREntry, 0, len(feedback.FIR))
		for _, entry := range feedback.FIR {
			if entry.SSRC != viewerSSRC {
				return nil, "", fmt.Errorf("FIR targets unexpected viewer SSRC %d", entry.SSRC)
			}
			entries = append(entries, rtcp.FIREntry{
				SSRC:           publisherSSRC,
				SequenceNumber: entry.SequenceNumber,
			})
		}
		return &rtcp.FullIntraRequest{
			SenderSSRC: r.feedbackSenderSSRC,
			MediaSSRC:  0,
			FIR:        entries,
		}, "fir", nil
	default:
		return nil, "", nil
	}
}

func runLocalSFUProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (result sfuProofResult, returnErr error) {
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID: "sfu",
		tracks: []sfuTrackSpec{
			{publisherID: "hami-sfu-publisher", trackID: "stream-red"},
			{publisherID: "hami-sfu-publisher", trackID: "stream-blue"},
		},
		viewerTrackIndexes: []int{0, 1},
		exerciseRTCP:       true,
	})
}

func runLocalM1HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M1-H duration must be at least %s", MinDuration)
	}
	viewerTrackIndexes := make([]int, 10)
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID: "m1h",
		tracks: []sfuTrackSpec{
			{publisherID: "hami-m1h-publisher", trackID: "stream-main"},
		},
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
	})
}

func runLocalM2HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M2-H duration must be at least %s", MinDuration)
	}
	tracks := make([]sfuTrackSpec, 10)
	viewerTrackIndexes := make([]int, 0, 50)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m2h-publisher-%02d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%02d", publisherIndex+1),
		}
		for range 5 {
			viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
		}
	}
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID:            "m2h",
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
	})
}

func runLocalM3HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M3-H duration must be at least %s", MinDuration)
	}
	tracks := make([]sfuTrackSpec, 50)
	viewerTrackIndexes := make([]int, 0, 100)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m3h-publisher-%02d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%02d", publisherIndex+1),
		}
		for range 2 {
			viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
		}
	}
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID:            "m3h",
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
	})
}

func runLocalM4HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M4-H duration must be at least %s", MinDuration)
	}
	tracks := make([]sfuTrackSpec, 100)
	viewerTrackIndexes := make([]int, 0, 500)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m4h-publisher-%03d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%03d", publisherIndex+1),
		}
		for range 5 {
			viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
		}
	}
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID:            "m4h",
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
	})
}

func runLocalM5HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M5-H duration must be at least %s", MinDuration)
	}
	tracks := make([]sfuTrackSpec, 500)
	viewerTrackIndexes := make([]int, 0, 1000)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m5h-publisher-%03d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%03d", publisherIndex+1),
		}
		for range 2 {
			viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
		}
	}
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID:            "m5h",
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
	})
}

func runLocalM6HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M6-H duration must be at least %s", MinDuration)
	}
	tracks := make([]sfuTrackSpec, 1000)
	viewerTrackIndexes := make([]int, 0, 2000)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m6h-publisher-%04d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%04d", publisherIndex+1),
		}
		for range 2 {
			viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
		}
	}
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, sfuProofConfig{
		proofID:            "m6h",
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
		videoInterval:      time.Second,
	})
}

func runLocalSFUProofWithConfig(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
	config sfuProofConfig,
) (result sfuProofResult, returnErr error) {
	if len(videoFrames) == 0 {
		return sfuProofResult{}, errors.New("at least one H.264 frame is required")
	}
	if duration <= 0 {
		return sfuProofResult{}, errors.New("media duration must be positive")
	}
	if len(config.tracks) == 0 || len(config.viewerTrackIndexes) == 0 {
		return sfuProofResult{}, errors.New("SFU proof requires tracks and viewers")
	}
	seenTrackIDs := make(map[string]struct{}, len(config.tracks))
	publishers := make([]string, 0, len(config.tracks))
	publisherSet := make(map[string]struct{}, len(config.tracks))
	for _, spec := range config.tracks {
		if spec.publisherID == "" || spec.trackID == "" {
			return sfuProofResult{}, errors.New("publisher and track identities are required")
		}
		if _, exists := seenTrackIDs[spec.trackID]; exists {
			return sfuProofResult{}, fmt.Errorf("duplicate track ID %q", spec.trackID)
		}
		seenTrackIDs[spec.trackID] = struct{}{}
		if _, exists := publisherSet[spec.publisherID]; !exists {
			publishers = append(publishers, spec.publisherID)
			publisherSet[spec.publisherID] = struct{}{}
		}
	}
	for _, trackIndex := range config.viewerTrackIndexes {
		if trackIndex < 0 || trackIndex >= len(config.tracks) {
			return sfuProofResult{}, fmt.Errorf("viewer references invalid track index %d", trackIndex)
		}
	}
	viewersPerPublisher := make(map[string]int, len(publishers))
	for _, trackIndex := range config.viewerTrackIndexes {
		viewersPerPublisher[config.tracks[trackIndex].publisherID]++
	}
	latencyClocks := make(map[string]*FrameClock, len(publishers))
	if config.measureLatency {
		for _, publisherID := range publishers {
			expected := viewersPerPublisher[publisherID]
			if expected == 0 {
				return sfuProofResult{}, fmt.Errorf("publisher %s has no latency subscribers", publisherID)
			}
			clock := NewFrameClock()
			if err := clock.SetExpectedConsumers(expected); err != nil {
				return sfuProofResult{}, fmt.Errorf("configure %s frame clock: %w", publisherID, err)
			}
			latencyClocks[publisherID] = clock
		}
	}
	clientSettings, _, err := loopbackSettings(false)
	if err != nil {
		return sfuProofResult{}, err
	}
	clientAPI := webrtc.NewAPI(webrtc.WithSettingEngine(clientSettings))
	routerMuxCount := min(peerNegotiationConcurrency, len(publishers))
	routerMuxes := make([]ice.UDPMux, 0, routerMuxCount)
	defer func() {
		for _, udpMux := range routerMuxes {
			if closeErr := udpMux.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close loopback ICE UDP mux: %w", closeErr))
			}
		}
	}()
	routerAPIs := make([]*webrtc.API, routerMuxCount)
	routerAPIByPublisher := make(map[string]*webrtc.API, len(publishers))
	for index, publisherID := range publishers {
		shard := index % routerMuxCount
		if routerAPIs[shard] == nil {
			routerSettings, udpMux, muxErr := loopbackSettings(true)
			if muxErr != nil {
				return sfuProofResult{}, muxErr
			}
			routerMuxes = append(routerMuxes, udpMux)
			routerAPIs[shard] = webrtc.NewAPI(webrtc.WithSettingEngine(routerSettings))
		}
		routerAPIByPublisher[publisherID] = routerAPIs[shard]
	}
	router, err := newSFURouter(routerAPIs[0])
	if err != nil {
		return sfuProofResult{}, err
	}
	var metricsServer *http.Server
	viewerClients := make([]*webrtc.PeerConnection, 0, len(config.viewerTrackIndexes))
	publisherClients := make(map[string]*webrtc.PeerConnection, len(publishers))
	routerPublisherPeers := make(map[string]*webrtc.PeerConnection, len(publishers))
	defer func() {
		if metricsServer != nil {
			shutdownCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			if shutdownErr := metricsServer.Shutdown(shutdownCtx); shutdownErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("shut down metrics endpoint: %w", shutdownErr))
			}
			cancel()
		}
		for _, peer := range viewerClients {
			if closeErr := peer.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close viewer client: %w", closeErr))
			}
		}
		for publisherID, peer := range publisherClients {
			if closeErr := peer.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr,
					fmt.Errorf("close publisher %s client: %w", publisherID, closeErr))
			}
		}
		if closeErr := router.close(); closeErr != nil {
			returnErr = errors.Join(returnErr, closeErr)
		}
	}()
	if *metricsListenAddress != "" {
		metricsServer, err = router.startMetricsServer(*metricsListenAddress)
		if err != nil {
			return sfuProofResult{}, err
		}
	}

	for _, publisherID := range publishers {
		clientPeer, err := clientAPI.NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("create publisher %s client: %w", publisherID, err)
		}
		routerPeer, err := router.registerPublisher(routerAPIByPublisher[publisherID], publisherID)
		if err != nil {
			_ = clientPeer.Close()
			return sfuProofResult{}, err
		}
		publisherClients[publisherID] = clientPeer
		routerPublisherPeers[publisherID] = routerPeer
	}

	sources := make([]sfuMediaSource, 0, len(config.tracks))
	trackIDs := make([]string, 0, len(config.tracks))
	for _, spec := range config.tracks {
		trackID := spec.trackID
		track, err := webrtc.NewTrackLocalStaticSample(webrtc.RTPCodecCapability{
			MimeType:    webrtc.MimeTypeH264,
			ClockRate:   90000,
			SDPFmtpLine: "level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42001f",
		}, trackID, trackID, webrtc.WithRTPTimestamp(sfuInitialVideoTimestamp))
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("create publisher track %s: %w", trackID, err)
		}
		sender, err := publisherClients[spec.publisherID].AddTrack(track)
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("add publisher track %s: %w", trackID, err)
		}
		key := sfuTrackKey{PublisherID: spec.publisherID, TrackID: trackID}
		sources = append(sources, sfuMediaSource{
			key:                 key,
			track:               track,
			sender:              sender,
			initialRTPTimestamp: sfuInitialVideoTimestamp,
		})
		trackIDs = append(trackIDs, trackID)
	}
	publisherPairs := make([]peerNegotiationPair, 0, len(publishers))
	for index, publisherID := range publishers {
		publisherPairs = append(publisherPairs, peerNegotiationPair{
			name:          fmt.Sprintf("publisher[%d] %s -> router", index, publisherID),
			offerer:       publisherClients[publisherID],
			answerer:      routerPublisherPeers[publisherID],
			mediaSections: []string{"m=video"},
		})
	}
	if err := negotiateLoopbackPairsBounded(ctx, publisherPairs, peerNegotiationConcurrency); err != nil {
		return sfuProofResult{}, fmt.Errorf("negotiate publisher pairs: %w", err)
	}
	for _, source := range sources {
		if err := source.track.WriteSample(videoFrames[0]); err != nil {
			return sfuProofResult{}, fmt.Errorf("register publisher track %s: %w", source.key.TrackID, err)
		}
	}
	if err := router.waitForTracks(ctx, sources); err != nil {
		return sfuProofResult{}, err
	}
	firstSequenceByTrack := make(map[sfuTrackKey]uint16, len(sources))
	if config.measureLatency {
		for _, source := range sources {
			lastSequence, err := router.waitForFirstFrame(ctx, source.key)
			if err != nil {
				return sfuProofResult{}, err
			}
			firstSequenceByTrack[source.key] = lastSequence + 1
		}
	}

	viewers := make([]viewerEndpoint, 0, len(config.viewerTrackIndexes))
	viewerPairs := make([]peerNegotiationPair, 0, len(config.viewerTrackIndexes))
	unauthorizedSubscriptionDenied := false
	for index, sourceIndex := range config.viewerTrackIndexes {
		source := sources[sourceIndex]
		viewerID := fmt.Sprintf("hami-sfu-viewer-%d", index+1)
		serverPeer, err := routerAPIByPublisher[source.key.PublisherID].NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("create router endpoint for %s: %w", viewerID, err)
		}
		clientPeer, err := clientAPI.NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			_ = serverPeer.Close()
			return sfuProofResult{}, fmt.Errorf("create viewer client %s: %w", viewerID, err)
		}
		viewerClients = append(viewerClients, clientPeer)
		var recorder *LatencyRecorder
		if config.measureLatency {
			recorder = NewLatencyRecorder(ModeReceive)
		}
		capture := newSFUViewerCapture(
			ctx,
			clientPeer,
			latencyClocks[source.key.PublisherID],
			recorder,
			firstSequenceByTrack[source.key],
		)
		if _, err := clientPeer.AddTransceiverFromKind(
			webrtc.RTPCodecTypeVideo,
			webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly},
		); err != nil {
			_ = serverPeer.Close()
			return sfuProofResult{}, fmt.Errorf("add viewer %s receive transceiver: %w", viewerID, err)
		}
		if err := router.registerViewer(viewerID, serverPeer); err != nil {
			_ = serverPeer.Close()
			return sfuProofResult{}, err
		}
		if index == 0 {
			if err := router.subscribe(viewerID, source.key); !errors.Is(err, errSFUUnauthorized) {
				return sfuProofResult{}, fmt.Errorf(
					"unauthorized subscription was not denied: err=%v",
					err,
				)
			}
			unauthorizedSubscriptionDenied = true
		}
		if err := router.authorizeSubscription(viewerID, source.key); err != nil {
			return sfuProofResult{}, fmt.Errorf("authorize viewer %s: %w", viewerID, err)
		}
		if err := router.subscribe(viewerID, source.key); err != nil {
			return sfuProofResult{}, fmt.Errorf("subscribe viewer %s: %w", viewerID, err)
		}
		viewers = append(viewers, viewerEndpoint{
			id:       viewerID,
			key:      source.key,
			client:   clientPeer,
			capture:  capture,
			recorder: recorder,
		})
		viewerPairs = append(viewerPairs, peerNegotiationPair{
			name:          fmt.Sprintf("viewer[%d] %s -> %s/%s", index, viewerID, source.key.PublisherID, source.key.TrackID),
			offerer:       clientPeer,
			answerer:      serverPeer,
			mediaSections: []string{"m=video"},
		})
	}
	if err := negotiateLoopbackPairsBounded(ctx, viewerPairs, peerNegotiationConcurrency); err != nil {
		return sfuProofResult{}, fmt.Errorf("negotiate viewer pairs: %w", err)
	}

	feedbackEvents := make(chan sfuFeedbackEvent, 8192)
	if config.exerciseRTCP {
		for _, source := range sources {
			go readPublisherFeedback(ctx, source.key.TrackID, source.sender, feedbackEvents)
		}
	}
	startedAt := time.Now().UTC()
	sendContext, cancelSend := context.WithTimeout(ctx, duration)
	sendDone := make(chan sfuSendResult, 1)
	firstMeasurementTimestamp := sources[0].initialRTPTimestamp + sampleRTPTicks(videoFrames[0], 90000)
	go func() {
		framesByPublisher, err := sendSFUVideo(
			sendContext,
			sources,
			videoFrames,
			latencyClocks,
			firstMeasurementTimestamp,
			config.videoInterval,
		)
		var framesSent uint64
		for _, frames := range framesByPublisher {
			framesSent += frames
		}
		sendDone <- sfuSendResult{
			frames:            framesSent,
			framesByPublisher: framesByPublisher,
			err:               err,
		}
	}()

	var upstreamCounts map[string]sfuFeedbackCounts
	if config.exerciseRTCP {
		expectedNACKs := make(map[string]map[uint16]struct{}, len(sources))
		feedbackPacer := time.NewTicker(sfuFeedbackPacingInterval)
		defer feedbackPacer.Stop()
		for index, viewer := range viewers {
			if err := viewer.capture.waitForPackets(sendContext, viewer.key.TrackID, 5); err != nil {
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("wait for viewer %s RTP: %w", viewer.id, err)
			}
			snapshot, exists := viewer.capture.snapshot(viewer.key.TrackID)
			if !exists {
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("viewer %s did not receive its requested track", viewer.id)
			}
			missingSequence, err := sendViewerFeedback(viewer.client, snapshot)
			if err != nil {
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("send RTCP feedback from %s: %w", viewer.id, err)
			}
			if expectedNACKs[viewer.key.TrackID] == nil {
				expectedNACKs[viewer.key.TrackID] = make(map[uint16]struct{})
			}
			expectedNACKs[viewer.key.TrackID][missingSequence] = struct{}{}
			if index+1 < len(viewers) {
				select {
				case <-sendContext.Done():
					err := sendContext.Err()
					cancelSend()
					<-sendDone
					return sfuProofResult{}, fmt.Errorf(
						"media window ended while pacing feedback for viewer %s: %w",
						viewer.id,
						err,
					)
				case <-feedbackPacer.C:
				}
			}
		}

		viewerKeys := make([]sfuTrackKey, len(viewers))
		for index, viewer := range viewers {
			viewerKeys[index] = viewer.key
		}
		upstreamCounts, err = waitForSFUFeedback(
			sendContext,
			feedbackEvents,
			sources,
			expectedNACKs,
			expectedFeedbackCounts(sources, viewerKeys),
		)
		if err != nil {
			logRouterFeedbackDiagnosis(router, viewers)
			cancelSend()
			<-sendDone
			return sfuProofResult{}, err
		}
	}
	<-sendContext.Done()
	cancelSend()
	sent := <-sendDone
	if sent.err != nil {
		return sfuProofResult{}, fmt.Errorf("write publisher video: %w", sent.err)
	}
	if err := ctx.Err(); err != nil {
		return sfuProofResult{}, fmt.Errorf("local SFU proof context ended: %w", err)
	}
	if config.measureLatency {
		time.Sleep(time.Second)
	} else {
		time.Sleep(100 * time.Millisecond)
	}

	publisherStates := make(map[string]string, len(publisherClients))
	publisherState := peerConnectionConnected
	for _, publisherID := range publishers {
		state := publisherClients[publisherID].ConnectionState().String()
		publisherStates[publisherID] = state
		if state != peerConnectionConnected {
			publisherState = "not_connected"
		}
	}
	latencyPending := 0
	for _, clock := range latencyClocks {
		latencyPending += clock.Pending()
	}
	result = sfuProofResult{
		EvidenceType:                   "TEST",
		LocalOnly:                      true,
		PublisherIdentity:              publishers[0],
		PublisherIdentities:            append([]string(nil), publishers...),
		PublisherStates:                publisherStates,
		PublisherState:                 publisherState,
		MediaDurationMS:                time.Since(startedAt).Milliseconds(),
		VideoFramesSent:                sent.frames,
		PublisherFramesSent:            sent.framesByPublisher,
		PublisherTracks:                append([]string(nil), trackIDs...),
		Viewers:                        make([]sfuViewerResult, 0, len(viewers)),
		UnauthorizedSubscriptionDenied: unauthorizedSubscriptionDenied,
	}
	if config.measureLatency {
		result.LatencyMode = ModeReceive
		result.LatencyPending = latencyPending
		result.LatencyEvidenceDirectory, err = os.MkdirTemp("", "hami-media-"+config.proofID+"-")
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("create latency evidence directory: %w", err)
		}
	}
	for _, viewer := range viewers {
		snapshot, exists := viewer.capture.snapshot(viewer.key.TrackID)
		trackIDsReceived := viewer.capture.trackIDs()
		onlyRequested := exists &&
			len(trackIDsReceived) == 1 &&
			trackIDsReceived[0] == viewer.key.TrackID
		viewerResult := sfuViewerResult{
			ViewerID:             viewer.id,
			RequestedTrackID:     viewer.key.TrackID,
			ReceivedTrackIDs:     trackIDsReceived,
			Received:             snapshot,
			RetransmittedPackets: viewer.capture.duplicatePackets(viewer.key.TrackID),
			PeerConnection:       viewer.client.ConnectionState().String(),
			OnlyRequested:        onlyRequested,
		}
		if config.exerciseRTCP {
			viewerResult.FeedbackForwarded = router.subscriptionFeedback(viewer.id, viewer.key)
		}
		if config.measureLatency {
			summary, jsonlPath, summaryPath, evidenceErr := writeLatencyEvidence(
				result.LatencyEvidenceDirectory,
				len(result.Viewers)+1,
				viewer.recorder,
			)
			if evidenceErr != nil {
				return sfuProofResult{}, evidenceErr
			}
			viewerResult.Latency = summary
			viewerResult.LatencyJSONLPath = jsonlPath
			viewerResult.LatencySummaryPath = summaryPath
		}
		result.Viewers = append(result.Viewers, viewerResult)
	}
	if config.exerciseRTCP {
		for _, source := range sources {
			result.UpstreamFeedback = append(result.UpstreamFeedback, sfuUpstreamFeedback{
				PublisherID: source.key.PublisherID,
				TrackID:     source.key.TrackID,
				Counts:      upstreamCounts[source.key.TrackID],
			})
		}
	}
	result.ForwardingErrors = router.errorsSnapshot()

	for _, viewer := range viewers {
		if err := router.unsubscribe(viewer.id, viewer.key); err != nil {
			return sfuProofResult{}, fmt.Errorf("unsubscribe viewer %s: %w", viewer.id, err)
		}
	}
	for _, source := range sources {
		if err := router.unregisterTrack(source.key); err != nil {
			return sfuProofResult{}, fmt.Errorf("unregister publisher track %s: %w", source.key.TrackID, err)
		}
	}
	_, _, _, authorizationsRemaining := router.counts()
	if authorizationsRemaining != 0 {
		return sfuProofResult{}, fmt.Errorf("SFU track unregistration left %d viewer authorizations",
			authorizationsRemaining)
	}
	for _, viewer := range viewers {
		if err := router.removeViewer(viewer.id); err != nil {
			return sfuProofResult{}, err
		}
	}
	if err := router.close(); err != nil {
		return sfuProofResult{}, err
	}
	tracksRemaining, viewersRemaining, subscriptionsRemaining, authorizationsRemaining := router.counts()
	result.CleanupVerified = tracksRemaining == 0 &&
		viewersRemaining == 0 &&
		subscriptionsRemaining == 0 &&
		authorizationsRemaining == 0
	if !result.CleanupVerified {
		return sfuProofResult{}, fmt.Errorf(
			"SFU cleanup left tracks=%d viewers=%d subscriptions=%d authorizations=%d",
			tracksRemaining,
			viewersRemaining,
			subscriptionsRemaining,
			authorizationsRemaining,
		)
	}
	if len(result.ForwardingErrors) != 0 {
		return sfuProofResult{}, fmt.Errorf("SFU forwarding errors: %s", strings.Join(result.ForwardingErrors, "; "))
	}
	if config.measureLatency {
		measurementPass := result.LatencyPending == 0 &&
			len(result.Viewers) == len(config.viewerTrackIndexes) &&
			result.PublisherState == peerConnectionConnected &&
			result.UnauthorizedSubscriptionDenied &&
			result.CleanupVerified &&
			len(result.ForwardingErrors) == 0
		for _, viewer := range result.Viewers {
			if viewer.Latency == nil || !viewer.Latency.Pass || viewer.Latency.Unmatched != 0 ||
				!viewer.OnlyRequested || viewer.PeerConnection != peerConnectionConnected {
				measurementPass = false
			}
			if config.exerciseRTCP &&
				(viewer.FeedbackForwarded.NACKReceived == 0 ||
					viewer.FeedbackForwarded.NACKRetransmitted == 0 ||
					viewer.FeedbackForwarded.NACKForwarded == 0 ||
					viewer.FeedbackForwarded.PLIForwarded == 0 ||
					viewer.FeedbackForwarded.FIRForwarded == 0) {
				measurementPass = false
			}
		}
		result.MeasurementPass = &measurementPass
	}
	for _, viewer := range result.Viewers {
		if !viewer.OnlyRequested || viewer.Received.PacketsReceived == 0 {
			return sfuProofResult{}, fmt.Errorf("viewer %s did not receive only its requested stream", viewer.ViewerID)
		}
		if config.exerciseRTCP {
			if viewer.FeedbackForwarded.NACKForwarded == 0 ||
				viewer.FeedbackForwarded.NACKReceived == 0 ||
				viewer.FeedbackForwarded.NACKRetransmitted == 0 ||
				viewer.FeedbackForwarded.PLIForwarded == 0 ||
				viewer.FeedbackForwarded.FIRForwarded == 0 {
				return sfuProofResult{}, fmt.Errorf("viewer %s RTCP feedback was not fully forwarded", viewer.ViewerID)
			}
			if viewer.RetransmittedPackets == 0 {
				return sfuProofResult{}, fmt.Errorf("viewer %s did not receive a NACK retransmission", viewer.ViewerID)
			}
		}
	}
	return result, nil
}

func writeLatencyEvidence(
	directory string,
	subscriber int,
	recorder *LatencyRecorder,
) (*Summary, string, string, error) {
	summary := recorder.Summary()
	samples, err := recorder.SamplesJSONL()
	if err != nil {
		return nil, "", "", fmt.Errorf("encode subscriber %d latency samples: %w", subscriber, err)
	}
	stem := fmt.Sprintf("subscriber-%02d", subscriber)
	jsonlPath := filepath.Join(directory, stem+".jsonl")
	if err := os.WriteFile(jsonlPath, samples, 0o600); err != nil {
		return nil, "", "", fmt.Errorf("write subscriber %d latency samples: %w", subscriber, err)
	}
	summaryPath := filepath.Join(directory, stem+"-summary.json")
	summaryJSON, err := json.MarshalIndent(summary, "", "  ")
	if err != nil {
		return nil, "", "", fmt.Errorf("encode subscriber %d latency summary: %w", subscriber, err)
	}
	summaryJSON = append(summaryJSON, '\n')
	if err := os.WriteFile(summaryPath, summaryJSON, 0o600); err != nil {
		return nil, "", "", fmt.Errorf("write subscriber %d latency summary: %w", subscriber, err)
	}
	return &summary, jsonlPath, summaryPath, nil
}

func (r *sfuRouter) waitForTracks(ctx context.Context, sources []sfuMediaSource) error {
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()
	for {
		r.mu.RLock()
		registered := 0
		for _, source := range sources {
			if r.tracks[source.key] != nil {
				registered++
			}
		}
		errs := append([]string(nil), r.forwardingErrors...)
		r.mu.RUnlock()
		if len(errs) != 0 {
			return fmt.Errorf("publisher track registration failed: %s", strings.Join(errs, "; "))
		}
		if registered == len(sources) {
			return nil
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("only %d of %d publisher tracks registered: %w", registered, len(sources), ctx.Err())
		case <-ticker.C:
		}
	}
}

func (r *sfuRouter) waitForFirstFrame(ctx context.Context, key sfuTrackKey) (uint16, error) {
	r.mu.RLock()
	source := r.tracks[key]
	r.mu.RUnlock()
	if source == nil {
		return 0, fmt.Errorf("publisher track %s is not registered", key.TrackID)
	}
	select {
	case <-source.firstFrameReady:
		source.packetMu.Lock()
		sequence := source.lastSequence
		source.packetMu.Unlock()
		return sequence, nil
	case <-ctx.Done():
		return 0, fmt.Errorf("wait for initial frame on track %s: %w", key.TrackID, ctx.Err())
	}
}

func newSFUViewerCapture(
	ctx context.Context,
	peer *webrtc.PeerConnection,
	clock *FrameClock,
	recorder *LatencyRecorder,
	firstSequence uint16,
) *sfuViewerCapture {
	capture := &sfuViewerCapture{
		tracks:          make(map[string]*streamCounter),
		sequenceCounts:  make(map[string]map[uint16]uint64),
		duplicates:      make(map[string]uint64),
		latencyClock:    clock,
		latencyRecorder: recorder,
		errors:          make(chan error, 8),
		received:        make(chan struct{}, 64),
	}
	peer.OnTrack(func(track *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		counter := &streamCounter{}
		assembler := &videoFrameAssembler{
			frameBoundaryKnown:     recorder != nil,
			nextFrameFirstSequence: firstSequence,
		}
		codec := track.Codec().MimeType
		if err := counter.bind(codec, uint32(track.SSRC()), uint8(track.PayloadType())); err != nil {
			capture.reportError(err)
			return
		}
		capture.mu.Lock()
		if _, exists := capture.tracks[track.ID()]; exists {
			capture.mu.Unlock()
			capture.reportError(fmt.Errorf("viewer received duplicate track ID %q", track.ID()))
			return
		}
		capture.tracks[track.ID()] = counter
		capture.sequenceCounts[track.ID()] = make(map[uint16]uint64)
		capture.mu.Unlock()
		go func() {
			for {
				packet, _, err := track.ReadRTP()
				if err != nil {
					if ctx.Err() == nil && !errors.Is(err, io.EOF) {
						capture.reportError(fmt.Errorf("read viewer RTP for %s: %w", track.ID(), err))
					}
					return
				}
				capture.mu.Lock()
				if capture.sequenceCounts[track.ID()][packet.SequenceNumber] > 0 {
					capture.duplicates[track.ID()]++
				}
				capture.sequenceCounts[track.ID()][packet.SequenceNumber]++
				capture.mu.Unlock()
				counter.record(packet.SequenceNumber, packet.Timestamp, len(packet.Payload))
				if capture.latencyRecorder != nil && capture.latencyClock != nil {
					if frameID, complete := assembler.push(packet); complete {
						capture.latencyRecorder.RecordNow(frameID, capture.latencyClock)
					}
				}
				select {
				case capture.received <- struct{}{}:
				default:
				}
			}
		}()
	})
	return capture
}

func (a *videoFrameAssembler) push(packet *rtp.Packet) (uint64, bool) {
	// RTP timestamps use serial arithmetic; stale retransmissions must not
	// reset the frame currently being assembled.
	if a.active && packet.Timestamp != a.timestamp &&
		int32(packet.Timestamp-a.timestamp) < 0 {
		return 0, false
	}
	if a.hasFinalizedTimestamp &&
		int32(packet.Timestamp-a.lastFinalizedTimestamp) <= 0 {
		return 0, false
	}

	if a.active && packet.Timestamp != a.timestamp {
		if a.markerSeen {
			a.nextFrameFirstSequence = a.markerSequence + 1
			a.frameBoundaryKnown = true
		} else {
			a.frameBoundaryKnown = false
		}
		a.lastFinalizedTimestamp = a.timestamp
		a.hasFinalizedTimestamp = true
		a.active = false
	}
	if !a.active {
		a.active = true
		a.timestamp = packet.Timestamp
		clear(a.frameSequences)
		a.markerSeen = false
	}
	if a.frameSequences == nil {
		a.frameSequences = make(map[uint16]struct{})
	}
	a.frameSequences[packet.SequenceNumber] = struct{}{}
	if packet.Marker {
		a.markerSequence = packet.SequenceNumber
		a.markerSeen = true
	}
	if !a.markerSeen {
		return 0, false
	}

	if !a.frameBoundaryKnown {
		a.lastFinalizedTimestamp = a.timestamp
		a.hasFinalizedTimestamp = true
		a.nextFrameFirstSequence = a.markerSequence + 1
		a.frameBoundaryKnown = true
		a.active = false
		clear(a.frameSequences)
		return 0, false
	}

	packetSpan := int(uint16(a.markerSequence-a.nextFrameFirstSequence)) + 1
	if len(a.frameSequences) < packetSpan {
		return 0, false
	}
	for offset := 0; offset < packetSpan; offset++ {
		sequence := a.nextFrameFirstSequence + uint16(offset)
		if _, exists := a.frameSequences[sequence]; !exists {
			return 0, false
		}
	}

	frameID := a.timestamp
	a.lastFinalizedTimestamp = a.timestamp
	a.hasFinalizedTimestamp = true
	a.nextFrameFirstSequence = a.markerSequence + 1
	a.active = false
	clear(a.frameSequences)
	return uint64(frameID), true
}

func (c *sfuViewerCapture) reportError(err error) {
	select {
	case c.errors <- err:
	default:
	}
}

func (c *sfuViewerCapture) waitForPackets(ctx context.Context, trackID string, count uint64) error {
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()
	for {
		snapshot, exists := c.snapshot(trackID)
		if exists && snapshot.PacketsReceived >= count {
			return nil
		}
		select {
		case err := <-c.errors:
			return err
		case <-ctx.Done():
			return fmt.Errorf("received %d packets on %s, expected %d: %w",
				snapshot.PacketsReceived, trackID, count, ctx.Err())
		case <-c.received:
		case <-ticker.C:
		}
	}
}

func (c *sfuViewerCapture) snapshot(trackID string) (streamSnapshot, bool) {
	c.mu.Lock()
	counter, exists := c.tracks[trackID]
	c.mu.Unlock()
	if !exists {
		return streamSnapshot{}, false
	}
	return counter.snapshotResult(), true
}

func (c *sfuViewerCapture) trackIDs() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	ids := make([]string, 0, len(c.tracks))
	for id := range c.tracks {
		ids = append(ids, id)
	}
	return ids
}

func (c *sfuViewerCapture) duplicatePackets(trackID string) uint64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.duplicates[trackID]
}

func (r *sfuRouter) subscriptionFeedback(viewerID string, key sfuTrackKey) sfuFeedbackCounts {
	r.mu.RLock()
	viewer := r.viewers[viewerID]
	var subscription *sfuSubscription
	if viewer != nil {
		subscription = viewer.subscriptions[key]
	}
	r.mu.RUnlock()
	if subscription == nil {
		return sfuFeedbackCounts{}
	}
	return subscription.feedbackSnapshot()
}

func sendSFUVideo(
	ctx context.Context,
	sources []sfuMediaSource,
	frames []media.Sample,
	clocks map[string]*FrameClock,
	firstFrameTimestamp uint32,
	videoInterval time.Duration,
) (map[string]uint64, error) {
	if videoInterval <= 0 {
		videoInterval = videoFrameDuration
	}
	sourcesByPublisher := make(map[string][]sfuMediaSource)
	publisherIDs := make([]string, 0)
	for _, source := range sources {
		if _, exists := sourcesByPublisher[source.key.PublisherID]; !exists {
			publisherIDs = append(publisherIDs, source.key.PublisherID)
		}
		sourcesByPublisher[source.key.PublisherID] = append(
			sourcesByPublisher[source.key.PublisherID],
			source,
		)
	}
	type sendResult struct {
		publisherID string
		frames      uint64
		err         error
	}
	sendContext, cancel := context.WithCancel(ctx)
	defer cancel()
	results := make(chan sendResult, len(publisherIDs))
	for publisherIndex, publisherID := range publisherIDs {
		startOffset := time.Duration(publisherIndex) * videoInterval / time.Duration(len(publisherIDs))
		go func(publisherID string, startOffset time.Duration) {
			sent, err := sendPublisherVideo(
				sendContext,
				sourcesByPublisher[publisherID],
				frames,
				clocks[publisherID],
				firstFrameTimestamp,
				startOffset,
				videoInterval,
			)
			results <- sendResult{publisherID: publisherID, frames: sent, err: err}
		}(publisherID, startOffset)
	}

	framesByPublisher := make(map[string]uint64, len(publisherIDs))
	var errs []error
	for range publisherIDs {
		result := <-results
		framesByPublisher[result.publisherID] = result.frames
		if result.err != nil {
			cancel()
			errs = append(errs, fmt.Errorf("send publisher %s video: %w", result.publisherID, result.err))
		}
	}
	return framesByPublisher, errors.Join(errs...)
}

func sendPublisherVideo(
	ctx context.Context,
	sources []sfuMediaSource,
	frames []media.Sample,
	clock *FrameClock,
	firstFrameTimestamp uint32,
	startOffset time.Duration,
	videoInterval time.Duration,
) (uint64, error) {
	timer := time.NewTimer(startOffset)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return 0, nil
	case <-timer.C:
	}

	ticker := time.NewTicker(videoInterval)
	defer ticker.Stop()
	var frameIndex, framesSent uint64
	frameTimestamp := firstFrameTimestamp
	for {
		select {
		case <-ctx.Done():
			return framesSent, nil
		case <-ticker.C:
			frame := frames[frameIndex%uint64(len(frames))]
			ticks := sampleRTPTicks(frame, 90000)
			if ticks == 0 {
				return framesSent, errors.New("video frame duration produces no RTP timestamp ticks")
			}
			if clock != nil {
				clock.CaptureNow(uint64(frameTimestamp))
			}
			for _, source := range sources {
				if err := source.track.WriteSample(frame); err != nil {
					return framesSent, fmt.Errorf("write track %s sample: %w", source.key.TrackID, err)
				}
			}
			frameTimestamp += ticks
			frameIndex++
			framesSent++
		}
	}
}

func sampleRTPTicks(sample media.Sample, clockRate uint32) uint32 {
	if sample.Duration <= 0 || clockRate == 0 {
		return 0
	}
	return uint32(int64(sample.Duration) * int64(clockRate) / int64(time.Second))
}

func sendViewerFeedback(peer *webrtc.PeerConnection, received streamSnapshot) (uint16, error) {
	if received.SSRC == 0 || received.PacketsReceived == 0 {
		return 0, errors.New("viewer has no received RTP identity for feedback")
	}
	missingSequence := received.LastSequenceNumber + 1000
	nacks := rtcp.NackPairsFromSequenceNumbers([]uint16{received.LastSequenceNumber, missingSequence})
	controlPackets := []rtcp.Packet{
		&rtcp.PictureLossIndication{
			SenderSSRC: received.SSRC + 1,
			MediaSSRC:  received.SSRC,
		},
		&rtcp.FullIntraRequest{
			SenderSSRC: received.SSRC + 1,
			MediaSSRC:  0,
			FIR: []rtcp.FIREntry{{
				SSRC:           received.SSRC,
				SequenceNumber: 1,
			}},
		},
	}
	if err := peer.WriteRTCP(controlPackets); err != nil {
		return 0, err
	}
	if err := peer.WriteRTCP([]rtcp.Packet{&rtcp.TransportLayerNack{
		SenderSSRC: received.SSRC + 1,
		MediaSSRC:  received.SSRC,
		Nacks:      nacks,
	}}); err != nil {
		return 0, err
	}
	return missingSequence, nil
}

func readPublisherFeedback(
	ctx context.Context,
	trackID string,
	sender *webrtc.RTPSender,
	events chan<- sfuFeedbackEvent,
) {
	for {
		packets, _, err := sender.ReadRTCP()
		if err != nil {
			return
		}
		for _, packet := range packets {
			event, ok := makeSFUFeedbackEvent(trackID, packet)
			if !ok {
				continue
			}
			select {
			case events <- event:
			case <-ctx.Done():
				return
			}
		}
	}
}

func makeSFUFeedbackEvent(trackID string, packet rtcp.Packet) (sfuFeedbackEvent, bool) {
	event := sfuFeedbackEvent{trackID: trackID}
	switch feedback := packet.(type) {
	case *rtcp.TransportLayerNack:
		event.kind = "nack"
		event.mediaSSRC = feedback.MediaSSRC
		event.nacks = append([]rtcp.NackPair(nil), feedback.Nacks...)
	case *rtcp.PictureLossIndication:
		event.kind = "pli"
		event.mediaSSRC = feedback.MediaSSRC
	case *rtcp.FullIntraRequest:
		event.kind = "fir"
		event.mediaSSRC = feedback.MediaSSRC
		for _, entry := range feedback.FIR {
			event.targets = append(event.targets, entry.SSRC)
		}
	default:
		return sfuFeedbackEvent{}, false
	}
	return event, true
}

func waitForSFUFeedback(
	ctx context.Context,
	events <-chan sfuFeedbackEvent,
	sources []sfuMediaSource,
	nackSequencesByTrack map[string]map[uint16]struct{},
	expectedCounts map[string]uint64,
) (map[string]sfuFeedbackCounts, error) {
	counts := make(map[string]sfuFeedbackCounts, len(sources))
	sourceSSRCs := make(map[string]uint32, len(sources))
	for _, source := range sources {
		counts[source.key.TrackID] = sfuFeedbackCounts{}
		sourceSSRCs[source.key.TrackID] = 0
	}
	seenNACKsByTrack := make(map[string]map[uint16]struct{}, len(sources))
	feedbackStarted := time.Now()
	const feedbackWaitLimit = 5 * time.Minute
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()
	for {
		complete := true
		for trackID, current := range counts {
			expected := expectedCounts[trackID]
			if expected == 0 {
				return nil, fmt.Errorf("publisher track %s has no expected RTCP feedback", trackID)
			}
			if current.NACKForwarded < expected ||
				current.PLIForwarded < expected ||
				current.FIRForwarded < expected {
				complete = false
				break
			}
		}
		if complete && len(sourceSSRCs) > 0 {
			for trackID, count := range counts {
				expected := expectedCounts[trackID]
				if count.NACKForwarded != expected ||
					count.PLIForwarded != expected ||
					count.FIRForwarded != expected {
					return nil, fmt.Errorf(
						"unexpected upstream feedback counts for %s: got %+v, expected %d of each type",
						trackID,
						count,
						expected,
					)
				}
				if len(seenNACKsByTrack[trackID]) != len(nackSequencesByTrack[trackID]) {
					return nil, fmt.Errorf("publisher NACKs for %s did not contain every viewer request", trackID)
				}
			}
			return counts, nil
		}
		select {
		case event := <-events:
			current, exists := counts[event.trackID]
			if !exists {
				return nil, fmt.Errorf("feedback arrived for unregistered publisher track %s", event.trackID)
			}
			switch event.kind {
			case "nack":
				if event.mediaSSRC == 0 || len(event.nacks) == 0 {
					return nil, fmt.Errorf("publisher received malformed NACK for %s", event.trackID)
				}
				expectedNACKs := nackSequencesByTrack[event.trackID]
				found := make(map[uint16]struct{}, len(expectedNACKs))
				for _, pair := range event.nacks {
					for _, sequence := range pair.PacketList() {
						if _, expected := expectedNACKs[sequence]; expected {
							found[sequence] = struct{}{}
						}
					}
				}
				if len(found) == 0 {
					// Extraneous NACK (e.g. genuine loss feedback from the stack at
					// scale) carrying none of the sequences this proof injected.
					// Ignore it and keep waiting for the expected NACKs; the
					// completeness check below still requires every expected
					// sequence to arrive before the proof can pass.
					continue
				}
				seen := seenNACKsByTrack[event.trackID]
				if seen == nil {
					seen = make(map[uint16]struct{}, len(nackSequencesByTrack[event.trackID]))
					seenNACKsByTrack[event.trackID] = seen
				}
				for sequence := range found {
					seen[sequence] = struct{}{}
				}
				if sourceSSRCs[event.trackID] != 0 && sourceSSRCs[event.trackID] != event.mediaSSRC {
					return nil, fmt.Errorf("publisher received NACK for wrong SSRC on %s: %d",
						event.trackID, event.mediaSSRC)
				}
				sourceSSRCs[event.trackID] = event.mediaSSRC
				current.NACKForwarded++
				counts[event.trackID] = current
			case "pli":
				if event.mediaSSRC == 0 || sourceSSRCs[event.trackID] != 0 && event.mediaSSRC != sourceSSRCs[event.trackID] {
					return nil, fmt.Errorf("publisher received PLI for wrong SSRC on %s: %d", event.trackID, event.mediaSSRC)
				}
				sourceSSRCs[event.trackID] = event.mediaSSRC
				current.PLIForwarded++
				counts[event.trackID] = current
			case "fir":
				if event.mediaSSRC != 0 || len(event.targets) != 1 ||
					sourceSSRCs[event.trackID] == 0 ||
					event.targets[0] != sourceSSRCs[event.trackID] {
					return nil, fmt.Errorf("publisher received FIR for wrong SSRC on %s", event.trackID)
				}
				current.FIRForwarded++
				counts[event.trackID] = current
			}
		case <-ctx.Done():
			return nil, fmt.Errorf("timed out waiting for translated NACK/PLI/FIR from publisher: %w", ctx.Err())
		case <-ticker.C:
			if time.Since(feedbackStarted) > feedbackWaitLimit {
				completeTracks := 0
				var incomplete []string
				var nackZero, pliZero, firZero int
				var maxNACK, maxPLI, maxFIR uint64
				for trackID, current := range counts {
					expected := expectedCounts[trackID]
					if current.NACKForwarded == 0 {
						nackZero++
					}
					if current.PLIForwarded == 0 {
						pliZero++
					}
					if current.FIRForwarded == 0 {
						firZero++
					}
					if current.NACKForwarded > maxNACK {
						maxNACK = current.NACKForwarded
					}
					if current.PLIForwarded > maxPLI {
						maxPLI = current.PLIForwarded
					}
					if current.FIRForwarded > maxFIR {
						maxFIR = current.FIRForwarded
					}
					if current.NACKForwarded >= expected &&
						current.PLIForwarded >= expected &&
						current.FIRForwarded >= expected &&
						len(seenNACKsByTrack[trackID]) == len(nackSequencesByTrack[trackID]) {
						completeTracks++
					} else if len(incomplete) < 5 {
						incomplete = append(incomplete, fmt.Sprintf("%s n%d p%d f%d seen%d/%d",
							trackID, current.NACKForwarded, current.PLIForwarded, current.FIRForwarded,
							len(seenNACKsByTrack[trackID]), len(nackSequencesByTrack[trackID])))
					}
				}
				return nil, fmt.Errorf("feedback wait timed out after %s: %d/%d tracks complete; nackZero=%d pliZero=%d firZero=%d maxN=%d maxP=%d maxF=%d; incomplete sample: %v",
					feedbackWaitLimit, completeTracks, len(counts), nackZero, pliZero, firZero, maxNACK, maxPLI, maxFIR, incomplete)
			}
		}
	}
}

// logRouterFeedbackDiagnosis prints where RTCP feedback was lost when the
// upstream wait fails: router errors (translate/reject problems) plus
// aggregate per-subscription counts (what the router actually saw and
// forwarded). It runs only on the failure path and writes to stderr so the
// diagnosis survives even though no result JSON is produced.
func logRouterFeedbackDiagnosis(router *sfuRouter, viewers []viewerEndpoint) {
	errs := router.errorsSnapshot()
	var total sfuFeedbackCounts
	subsWithPLI, subsWithFIR, subsTotal := 0, 0, 0
	for _, viewer := range viewers {
		counts := router.subscriptionFeedback(viewer.id, viewer.key)
		subsTotal++
		total.NACKReceived += counts.NACKReceived
		total.NACKRetransmitted += counts.NACKRetransmitted
		total.NACKForwarded += counts.NACKForwarded
		total.NACKDuplicatesSkipped += counts.NACKDuplicatesSkipped
		total.NACKSequencesCapped += counts.NACKSequencesCapped
		total.NACKEnqueued += counts.NACKEnqueued
		total.NACKDroppedQueueFull += counts.NACKDroppedQueueFull
		total.NACKDroppedStale += counts.NACKDroppedStale
		total.NACKQueueDepth += counts.NACKQueueDepth
		total.PLIForwarded += counts.PLIForwarded
		total.FIRForwarded += counts.FIRForwarded
		if counts.PLIForwarded > 0 {
			subsWithPLI++
		}
		if counts.FIRForwarded > 0 {
			subsWithFIR++
		}
	}
	fmt.Fprintf(os.Stderr, "router feedback diagnosis: subs=%d subsWithPLI=%d subsWithFIR=%d totalNACKReceived=%d totalNACKRetransmitted=%d totalNACKDuplicatesSkipped=%d totalNACKSequencesCapped=%d totalNACKEnqueued=%d totalNACKDroppedQueueFull=%d totalNACKDroppedStale=%d nackQueueDepth=%d totalNACKForwarded=%d totalPLIForwarded=%d totalFIRForwarded=%d routerErrors=%d\n",
		subsTotal, subsWithPLI, subsWithFIR, total.NACKReceived, total.NACKRetransmitted, total.NACKDuplicatesSkipped, total.NACKSequencesCapped, total.NACKEnqueued, total.NACKDroppedQueueFull, total.NACKDroppedStale, total.NACKQueueDepth, total.NACKForwarded, total.PLIForwarded, total.FIRForwarded, len(errs))
	for i, e := range errs {
		if i >= 10 {
			break
		}
		fmt.Fprintf(os.Stderr, "router error %d: %s\n", i, e)
	}
}

func expectedFeedbackCounts(sources []sfuMediaSource, viewerKeys []sfuTrackKey) map[string]uint64 {
	expected := make(map[string]uint64, len(sources))
	for _, source := range sources {
		expected[source.key.TrackID] = 0
	}
	for _, key := range viewerKeys {
		expected[key.TrackID]++
	}
	return expected
}
