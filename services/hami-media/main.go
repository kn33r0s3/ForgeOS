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
	"net/http/httptrace"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	runtimemetrics "runtime/metrics"
	"runtime/pprof"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/pion/ice/v4"
	"github.com/pion/interceptor"
	"github.com/pion/interceptor/pkg/nack"
	"github.com/pion/rtcp"
	"github.com/pion/rtp"
	"github.com/pion/stun/v4"
	"github.com/pion/webrtc/v4"
	"github.com/pion/webrtc/v4/pkg/media"
	"github.com/pion/webrtc/v4/pkg/media/h264reader"
)

const (
	audioFrameDuration             = 20 * time.Millisecond
	videoFrameDuration             = 3 * audioFrameDuration
	audioSampleRate                = 8000
	audioSamplesFrame              = audioSampleRate / 50
	sfuNACKHistoryPackets          = 512
	sfuScaleMaxViewersPerPublisher = 250
	sfuScaleMaxViewers             = 5000
	// NACK aggregation (M6-H attempt 8): a viewer NACKs the same lost
	// sequences on every RTCP interval, and retransmitting each one again
	// drowns the router (16.7M retransmits for 306k NACKs in attempt 7)
	// and starves the subscription's ReadRTCP loop, so PLI/FIR never get
	// read. Remember each retransmitted sequence for this long and skip
	// duplicates inside the window; serve at most this many sequences
	// from one NACK and let the viewer re-NACK the rest.
	// Split forwarded NACKs at Pion's per-report limit below.
	nackAggregationWindow = 500 * time.Millisecond
	maxSequencesPerNACK   = 512
	// Pion's NACK marshaler requires len(Nacks)+2 <= MaxUint8.
	maxNACKPairsPerRTCPPacket  = math.MaxUint8 - 2
	nackQueueSize              = 512
	nackMaxQueueAge            = 500 * time.Millisecond
	sfuRTPQueueSize            = 64
	peerPairNegotiationTimeout = 60 * time.Second
	peerNegotiationConcurrency = 32
	sfuFeedbackPacingInterval  = 5 * time.Millisecond
	// M7-H attempt 9: the parallel injection worker pool. 32 matches the
	// negotiation concurrency; the serial loop's worst single blocking
	// WriteRTCP was 42.6 s, so 32 workers keep the dispatch wall time far
	// inside the 395 s pacing budget.
	injectionWorkerCount                = 32
	sfuFeedbackCompletionGrace          = 30 * time.Second
	sfuFeedbackWaitLimit                = 5 * time.Minute
	rtpForwardLatencyBucketCount        = 9
	m7hReadDurationBucketCount          = 8
	m7hCPUProfileDelay                  = 30 * time.Second
	m7hCPUProfileWindow                 = 5 * time.Second
	m7hCPUProfileMaxWindow              = 10 * time.Second
	sfuInitialVideoTimestamp     uint32 = 0x10203040
	peerConnectionConnected             = "connected"
)

// routerUDPMuxMode is linker-overridable for local transport isolation runs.
var routerUDPMuxMode = "enabled"

// routerSocketWriteMode enables per-viewer router UDP write counts for diagnostics.
var routerSocketWriteMode = "disabled"

// clientSocketReadMode enables per-viewer raw UDP read counts for diagnostics.
var clientSocketReadMode = "disabled"

var clientSocketReadBufferSize = "0"

var rtpMonotonicStart = time.Now()

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

var m7hReadDurationBuckets = [...]time.Duration{
	time.Millisecond,
	10 * time.Millisecond,
	50 * time.Millisecond,
	100 * time.Millisecond,
	400 * time.Millisecond,
	time.Second,
	5 * time.Second,
}

var metricsListenAddress = flag.String(
	"metrics-listen",
	"",
	"optional loopback-only Prometheus endpoint (for example 127.0.0.1:9464)",
)

var m7hHeapProfilePath = flag.String(
	"m7h-heap-profile",
	"",
	"optional local path prefix for connected and post-media M7-H heap profiles",
)

var m7hGoroutineProfilePath = flag.String(
	"m7h-goroutine-profile",
	"",
	"optional local path prefix for M7-H goroutine profiles captured at the stalled send signature",
)

var m7hCPUProfilePath = flag.String(
	"m7h-cpu-profile",
	"",
	"optional temporary-directory path prefix for a bounded M7-H CPU profile captured 30 seconds into streaming",
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
	PLIReceived           uint64 `json:"pli_received"`
	FIRReceived           uint64 `json:"fir_received"`
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
	RTPQueueDrops                  uint64                `json:"rtp_queue_drops"`
	RTPIntentionalShed             uint64                `json:"rtp_intentional_shed"`
	RTPWriteErrors                 uint64                `json:"rtp_write_errors"`
	RTPKeyframeRecoverySamples     uint64                `json:"rtp_keyframe_recovery_samples"`
	RTPKeyframeRecoveryNanos       uint64                `json:"rtp_keyframe_recovery_nanos"`
	RTPKeyframeRecoveryMaxNanos    uint64                `json:"rtp_keyframe_recovery_max_nanos"`
	LatencyMode                    string                `json:"latency_mode,omitempty"`
	LatencyPending                 int                   `json:"latency_pending_frames"`
	LatencyEvidenceDirectory       string                `json:"latency_evidence_directory,omitempty"`
	MeasurementPass                *bool                 `json:"measurement_pass,omitempty"`
}

type proofErrorResult struct {
	Error string `json:"error"`
}

func sfuMeasurementPass(result sfuProofResult, expectedViewers int, exerciseRTCP bool) bool {
	pass := result.LatencyPending == 0 &&
		len(result.Viewers) == expectedViewers &&
		result.PublisherState == peerConnectionConnected &&
		result.UnauthorizedSubscriptionDenied &&
		result.CleanupVerified &&
		result.RTPWriteErrors == 0 &&
		len(result.ForwardingErrors) == 0
	for _, viewer := range result.Viewers {
		if viewer.Latency == nil || !viewer.Latency.Pass || viewer.Latency.Unmatched != 0 ||
			!viewer.OnlyRequested || viewer.PeerConnection != peerConnectionConnected {
			pass = false
		}
		if exerciseRTCP &&
			(viewer.FeedbackForwarded.NACKReceived == 0 ||
				viewer.FeedbackForwarded.NACKRetransmitted == 0 ||
				viewer.FeedbackForwarded.NACKForwarded == 0 ||
				viewer.FeedbackForwarded.PLIForwarded == 0 ||
				viewer.FeedbackForwarded.FIRForwarded == 0) {
			pass = false
		}
	}
	return pass
}

func writeProofError(w io.Writer, err error) error {
	return json.NewEncoder(w).Encode(proofErrorResult{Error: err.Error()})
}

func main() {
	mode := flag.String("mode", "pair", "local proof mode: pair, sfu, sfu-single, m1h, m2h, m3h, m4h, m5h, m6h, or m7h")
	videoPath := flag.String("video-file", "", "local Annex-B H.264 source file")
	duration := flag.Duration("duration", 3*time.Second, "local media send duration")
	sfuPublishers := flag.Int("sfu-publishers", 1, "publisher count for sfu-single mode (1-1000)")
	sfuViewersPerPublisher := flag.Int(
		"sfu-viewers-per-publisher",
		1,
		"viewer count per publisher for sfu-single mode (1-250; total viewers capped at 5000)",
	)
	m7hSFUToken := flag.String("m7h-sfu-token", "", "private token for the local M7-H router process")
	m7hPairs := flag.Int("m7h-viewers", 3000, "M7-H publisher/viewer pair count (1-3000; one viewer per publisher)")
	flag.Parse()
	if *mode == "m7h-sfu" {
		if *m7hSFUToken == "" {
			fail("--m7h-sfu-token is required in m7h-sfu mode")
		}
		if err := runM7HSFUServer(*m7hSFUToken); err != nil {
			fail("run local M7-H SFU process: %v", err)
		}
		return
	}
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
	} else if *mode == "m7h" {
		setupAllowance = 60 * time.Minute
	}
	ctx, cancel := context.WithTimeout(context.Background(), *duration+setupAllowance)
	defer cancel()
	var result any
	switch *mode {
	case "pair":
		result, err = runLocalPair(ctx, videoFrames, *duration)
	case "sfu":
		result, err = runLocalSFUProof(ctx, videoFrames, *duration)
	case "sfu-single":
		if *sfuPublishers == 1 && *sfuViewersPerPublisher == 1 {
			result, err = runLocalSFUSinglePairProof(ctx, videoFrames, *duration)
		} else {
			result, err = runLocalSFUScaleProof(ctx, videoFrames, *duration, *sfuPublishers, *sfuViewersPerPublisher)
		}
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
	case "m7h":
		result, err = runLocalM7HProof(ctx, videoFrames, *duration, *m7hPairs)
	default:
		fail("unsupported --mode %q (want pair, sfu, sfu-single, m1h, m2h, m3h, m4h, m5h, m6h, or m7h)", *mode)
	}
	if err != nil {
		if writeErr := writeProofError(os.Stdout, err); writeErr != nil {
			fail("run local Pion %s proof: %v (write error result: %v)", *mode, err, writeErr)
		}
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
		case h264reader.NalUnitTypeCodedSliceNonIdr:
			if len(frames) == 0 {
				return nil, errors.New("H.264 source contains a non-IDR slice before its first SPS/PPS-backed IDR")
			}
			frame := appendAnnexBNAL(nil, nal.Data)
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

	clientSettings, _, err := loopbackSettings(false, 0)
	if err != nil {
		return proofResult{}, err
	}
	settings, udpMux, err := loopbackSettings(true, 0)
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
		offererICEState, answererICEState := offerer.ICEConnectionState(), answerer.ICEConnectionState()
		offererGatheringState, answererGatheringState := offerer.ICEGatheringState(), answerer.ICEGatheringState()
		offererPairs, answererPairs := iceCandidatePairDiagnostics(offerer), iceCandidatePairDiagnostics(answerer)
		closeErr := errors.Join(offerer.Close(), answerer.Close())
		reason := "per-pair timeout"
		if ctx.Err() != nil {
			reason = "parent context ended"
		}
		timeoutErr := fmt.Errorf(
			"peer pair %s %s (limit=%s offerer=%s/%s gathering=%s pairs=[%s] answerer=%s/%s gathering=%s pairs=[%s]): %w",
			pairName,
			reason,
			timeout,
			offererState,
			offererICEState,
			offererGatheringState,
			offererPairs,
			answererState,
			answererICEState,
			answererGatheringState,
			answererPairs,
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
						if pair.socketConn != nil {
							err = fmt.Errorf(
								"%w (offerer UDP socket reads=%d nonSTUN=%d STUN=%d)",
								err,
								pair.socketConn.packetsRead.Load(),
								pair.socketConn.nonSTUNPacketsRead.Load(),
								pair.socketConn.stunPacketsRead.Load(),
							)
						}
						if pair.answererSocketConn != nil {
							routerDestination := ""
							if destination := pair.answererSocketConn.firstNonSTUNWriteDestination.Load(); destination != nil {
								routerDestination = *destination
							}
							clientSocketLocalAddress := ""
							if pair.socketConn != nil {
								clientSocketLocalAddress = pair.socketConn.LocalAddr().String()
							}
							err = fmt.Errorf(
								"%w (answerer UDP socket writes=%d STUN=%d nonSTUN=%d bytes=%d destination=%s clientSocketLocalAddress=%s)",
								err,
								pair.answererSocketConn.packetsWritten.Load(),
								pair.answererSocketConn.stunPacketsWritten.Load(),
								pair.answererSocketConn.nonSTUNPacketsWritten.Load(),
								pair.answererSocketConn.bytesWritten.Load(),
								routerDestination,
								clientSocketLocalAddress,
							)
						}
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

func loopbackSettings(withUDPMux bool, readBufferSize int) (webrtc.SettingEngine, ice.UDPMux, error) {
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
	// Attempt 32 probe removes the per-agent mDNS Conn; loopback host candidates use IPs.
	settings.SetICEMulticastDNSMode(ice.MulticastDNSModeDisabled)
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
	muxOptions := []ice.UDPMuxFromPortOption{
		ice.UDPMuxFromPortWithNetworks(ice.NetworkTypeUDP4),
		ice.UDPMuxFromPortWithLoopback(),
		ice.UDPMuxFromPortWithInterfaceFilter(func(name string) bool {
			_, ok := loopbackInterfaces[name]
			return ok
		}),
		ice.UDPMuxFromPortWithIPFilter(func(ip net.IP) bool {
			return ip.IsLoopback()
		}),
	}
	if readBufferSize > 0 {
		// Attempt 5: the router's shared muxes receive all viewer feedback
		// (NACK/PLI/FIR from 3,000 viewers) on OS-default receive buffers.
		// Attempt 4 proved the feedback dies before the router app sees it
		// (PLIReceived == PLIForwarded == 868), so give the mux sockets the
		// same buffer the client sockets already have. Pion sets the buffer
		// at socket creation and ignores the error, so the effective value
		// is verified separately after viewer negotiation.
		muxOptions = append(muxOptions, ice.UDPMuxFromPortWithReadBufferSize(readBufferSize))
	}
	udpMux, err := ice.NewMultiUDPMuxFromPort(0, muxOptions...)
	if err != nil {
		return webrtc.SettingEngine{}, nil, fmt.Errorf("create loopback ICE UDP mux: %w", err)
	}
	settings.SetICEUDPMux(udpMux)
	return settings, udpMux, nil
}

// M7-H attempt 6: endpoint-attribution trace (measurement-only, no behaviour
// change). ChatGPT's decisive measurement for the attempt-5 no-socket
// explosion: which process writes the ~29M datagrams that die as kernel
// "no socket" drops, to which destination ports, and what was those
// destinations' socket lifecycle when the datagrams arrived?
// Volume guard: per-destination AGGREGATES only (one entry per destination
// port, updated with atomics on the write path) + one log line per socket
// close + one line per PeerConnection state transition + a bounded sample of
// the first 1,000 dead-destination writes. No per-datagram logging — the log
// would be gigabytes and would perturb the run.

var monoOrigin = time.Now()

type destWriteStats struct {
	count      atomic.Uint64
	rtpCount   atomic.Uint64
	rtcpCount  atomic.Uint64
	stunCount  atomic.Uint64
	deadCount  atomic.Uint64
	firstNanos atomic.Int64
	lastNanos  atomic.Int64
}

type deadWriteSample struct {
	monoNanos int64
	role      string
	destPort  int
	class     string
	size      int
}

var (
	// countingConnRegistry holds every packetReadCountingConn, so the phase
	// snapshots and the attribution print can walk them all.
	countingConnRegistry sync.Map // *packetReadCountingConn -> struct{}
	// closedPorts maps a local UDP port to the monotonic close time (nanos
	// since monoOrigin) of the socket that was bound to it.
	closedPorts sync.Map // int -> int64
	// deadWriteSamples holds the first 1,000 writes to already-closed ports.
	deadWriteSamplesMu   sync.Mutex
	deadWriteSamples     []deadWriteSample
	deadWriteSampleCount atomic.Uint64
	// pcStateCounts counts PeerConnection ICE/connection state transitions.
	pcStateCounts sync.Map // string -> *atomic.Uint64
	// tracePCStateTransitions opts into synchronous per-peer callback logs.
	tracePCStateTransitions = os.Getenv("M7H_TRACE_PC_STATE") == "1"
	// runPhaseName is the current run phase for the attribution snapshots.
	runPhaseName atomic.Value // string
	// destPhaseSnapshots holds per-phase per-destination write counts:
	// phase -> conn role -> dest port -> count (cumulative at snapshot time).
	destPhaseSnapshotsMu sync.Mutex
	destPhaseSnapshots   = make(map[string]map[string]map[int]uint64)
	deadPhaseSnapshots   = make(map[string]map[string]map[int]uint64)
)

// M7-H attempt 7: per-PC connection-lifetime tracking. Updated from the
// ICE/connection state callbacks (Pion goroutines), so everything here is
// lock-free atomics; the map itself is a sync.Map. A "pair" is one
// PeerConnection (publisher-client, router-publisherPeer, router-serverPeer
// or viewer-client) identified by kind:id.
type pcLifetime struct {
	kind           string
	id             string
	everConnected  atomic.Bool
	firstConnected atomic.Int64 // mono nanos of first connected, 0 = never
	connectedStart atomic.Int64 // mono nanos of current connected interval, -1 = not connected
	connectedNanos atomic.Uint64
	transitions    atomic.Uint64
	firstFailed    atomic.Int64 // mono nanos of first failed, 0 = never
	lastICEState   atomic.Value // string
	lastConnState  atomic.Value // string
}

type lifetimeHistogram struct {
	neverConnected     uint64
	connectedThenDied  uint64
	survived           uint64
	currentlyConnected uint64
	medianDiedMs       int64
}

// M7-H attempt 8: one slow injection (a sendViewerFeedback call over
// 50 ms), kept for the bounded slowest-20 list.
type slowInjection struct {
	viewerID string
	ms       int64
	iceState string
}

var (
	pcLifetimes sync.Map // "kind:id" -> *pcLifetime
	// stunPhaseSnapshots holds per-phase STUN request/response counts:
	// phase -> [reqWritten, respWritten, reqRead, respRead].
	stunPhaseSnapshotsMu sync.Mutex
	stunPhaseSnapshots   = make(map[string][4]uint64)
	// lifetimeAtWaitEnd is the lifetime histogram as it stood at wait-end
	// (before teardown closes the pairs again).
	lifetimeAtWaitEndMu sync.Mutex
	lifetimeAtWaitEnd   lifetimeHistogram
	// M7-H attempt 8: per-viewer feedback-injection timing (aggregates only).
	// The attempt-7 serial injection loop ran ~150-200 ms/viewer vs the 5 ms
	// pacer; these separate "WriteRTCP slow on dead PCs" from "readiness
	// gate ate the budget". readinessGateNanos is set once when the gate
	// finishes; the slowest-20 list is bounded and mutex-guarded.
	injectionSendCalls    atomic.Uint64
	injectionSendTotalNs  atomic.Uint64
	injectionSendSlow50ms atomic.Uint64
	readinessGateNanos    atomic.Uint64
	injectionMu           sync.Mutex
	injectionMaxNs        uint64
	slowInjections        []slowInjection // slowest 20, descending by ms
	// M7-H attempt 9: parallel injection — dead-PC skip counters + the
	// worker pool's wall time and max per-worker busy time. The skip
	// counters are atomics (dispatch loop only); maxWorkerBusyNs is
	// guarded by injectionMu like injectionMaxNs.
	injectionSkippedDead         atomic.Uint64
	injectionSkippedDisconnected atomic.Uint64
	injectionPoolWallNanos       atomic.Uint64
	injectionMaxWorkerBusyNs     uint64
)

func pcLifetimeFor(kind, id string) *pcLifetime {
	key := kind + ":" + id
	if v, ok := pcLifetimes.Load(key); ok {
		return v.(*pcLifetime)
	}
	lt := &pcLifetime{kind: kind, id: id}
	lt.connectedStart.Store(-1)
	lt.lastICEState.Store("")
	lt.lastConnState.Store("")
	v, _ := pcLifetimes.LoadOrStore(key, lt)
	return v.(*pcLifetime)
}

// pcLifetimeHistogram aggregates the per-PC lifetimes into the three
// buckets the attempt-7 decision rules need, plus the median lifetime of
// the pairs that connected and then died.
func pcLifetimeHistogram() lifetimeHistogram {
	var h lifetimeHistogram
	var died []int64
	pcLifetimes.Range(func(_, value any) bool {
		lt, ok := value.(*pcLifetime)
		if !ok || lt == nil {
			return true
		}
		if !lt.everConnected.Load() {
			h.neverConnected++
			return true
		}
		if lt.firstFailed.Load() != 0 {
			h.connectedThenDied++
			died = append(died, lt.firstFailed.Load()-lt.firstConnected.Load())
		} else {
			h.survived++
		}
		if lt.connectedStart.Load() >= 0 {
			h.currentlyConnected++
		}
		return true
	})
	if len(died) > 0 {
		sort.Slice(died, func(i, j int) bool { return died[i] < died[j] })
		h.medianDiedMs = died[len(died)/2] / int64(time.Millisecond)
	}
	return h
}

// M7-H attempt 8: per-kind lifetime histogram. The aggregate median hides
// the client-early / router-late split; this buckets died lifetimes by PC
// kind (viewer-client, publisher-client, router-serverPeer,
// router-publisherPeer).
func pcLifetimeHistogramByKind() map[string]lifetimeHistogram {
	byKind := make(map[string]lifetimeHistogram)
	diedByKind := make(map[string][]int64)
	pcLifetimes.Range(func(_, value any) bool {
		lt, ok := value.(*pcLifetime)
		if !ok || lt == nil {
			return true
		}
		h := byKind[lt.kind]
		if !lt.everConnected.Load() {
			h.neverConnected++
			byKind[lt.kind] = h
			return true
		}
		if lt.firstFailed.Load() != 0 {
			h.connectedThenDied++
			diedByKind[lt.kind] = append(diedByKind[lt.kind], lt.firstFailed.Load()-lt.firstConnected.Load())
		} else {
			h.survived++
		}
		if lt.connectedStart.Load() >= 0 {
			h.currentlyConnected++
		}
		byKind[lt.kind] = h
		return true
	})
	for kind, died := range diedByKind {
		if len(died) == 0 {
			continue
		}
		sort.Slice(died, func(i, j int) bool { return died[i] < died[j] })
		h := byKind[kind]
		h.medianDiedMs = died[len(died)/2] / int64(time.Millisecond)
		byKind[kind] = h
	}
	return byKind
}

// logPerKindLifetime prints the per-kind lifetime histogram (one line per
// kind, in a fixed order so runs are comparable).
func logPerKindLifetime() {
	byKind := pcLifetimeHistogramByKind()
	for _, kind := range []string{"viewer-client", "publisher-client", "router-serverPeer", "router-publisherPeer"} {
		h := byKind[kind]
		fmt.Fprintf(os.Stderr, "attribution lifetime kind=%s neverConnected=%d connectedThenDied=%d survived=%d currentlyConnected=%d medianDiedMs=%d\n",
			kind, h.neverConnected, h.connectedThenDied, h.survived, h.currentlyConnected, h.medianDiedMs)
	}
}

// recordInjection records one sendViewerFeedback call's duration for the
// attempt-8 injection-timing aggregates: the max and the bounded slowest-20
// (with the viewer's last ICE state, so a slow call on a dead PC is visible).
func recordInjection(viewerID string, dur time.Duration) {
	iceState := ""
	if v, ok := pcLifetimes.Load("viewer-client:" + viewerID); ok {
		if lt, ok2 := v.(*pcLifetime); ok2 && lt != nil {
			iceState, _ = lt.lastICEState.Load().(string)
		}
	}
	injectionMu.Lock()
	defer injectionMu.Unlock()
	if uint64(dur.Nanoseconds()) > injectionMaxNs {
		injectionMaxNs = uint64(dur.Nanoseconds())
	}
	if dur <= 50*time.Millisecond {
		return
	}
	entry := slowInjection{viewerID: viewerID, ms: dur.Milliseconds(), iceState: iceState}
	// Insert into the slowest-20, descending by ms; drop the 21st.
	inserted := false
	for i, s := range slowInjections {
		if entry.ms > s.ms {
			slowInjections = append(slowInjections, slowInjection{})
			copy(slowInjections[i+1:], slowInjections[i:])
			slowInjections[i] = entry
			inserted = true
			break
		}
	}
	if !inserted && len(slowInjections) < 20 {
		slowInjections = append(slowInjections, entry)
	}
	if len(slowInjections) > 20 {
		slowInjections = slowInjections[:20]
	}
}

// recordWorkerBusy folds the per-worker busy totals into the injection
// max (called once, after the pool drains, so no worker is writing).
func recordWorkerBusy(workerBusyNs []uint64) {
	injectionMu.Lock()
	defer injectionMu.Unlock()
	for _, ns := range workerBusyNs {
		if ns > injectionMaxWorkerBusyNs {
			injectionMaxWorkerBusyNs = ns
		}
	}
}

// logInjectionAttribution prints the attempt-8 injection-timing aggregates
// and the slowest-20 list. Attempt 9 adds the dead-PC skip counts and the
// worker-pool wall time / max per-worker busy time.
func logInjectionAttribution() {
	injectionMu.Lock()
	maxNs := injectionMaxNs
	maxWorkerBusyNs := injectionMaxWorkerBusyNs
	slow := append([]slowInjection(nil), slowInjections...)
	injectionMu.Unlock()
	fmt.Fprintf(os.Stderr, "attribution injection: sendCalls=%d sendTotalMs=%d sendSlow50ms=%d sendMaxMs=%d readinessGateMs=%d skippedDead=%d skippedDisconnected=%d poolWallMs=%d maxWorkerBusyMs=%d\n",
		injectionSendCalls.Load(), injectionSendTotalNs.Load()/uint64(time.Millisecond), injectionSendSlow50ms.Load(),
		maxNs/uint64(time.Millisecond), readinessGateNanos.Load()/uint64(time.Millisecond),
		injectionSkippedDead.Load(), injectionSkippedDisconnected.Load(),
		injectionPoolWallNanos.Load()/uint64(time.Millisecond), maxWorkerBusyNs/uint64(time.Millisecond))
	for i, s := range slow {
		fmt.Fprintf(os.Stderr, "attribution injection slow %d: viewer=%s ms=%d lastICE=%s\n",
			i, s.viewerID, s.ms, s.iceState)
	}
}

// logPacingErrorAttribution snapshots the run state at the moment the
// feedback-injection pacing deadline fires, before teardown closes anything.
// Attempt 7 died here with no snapshot, so the send-phase state was lost.
func logPacingErrorAttribution(viewerID string) {
	snapshotDestStats("pacing-failed")
	snapshotSTUNStats("pacing-failed")
	h := pcLifetimeHistogram()
	fmt.Fprintf(os.Stderr, "attribution pacing-error: viewer=%s\n", viewerID)
	fmt.Fprintf(os.Stderr, "attribution lifetime: neverConnected=%d connectedThenDied=%d survived=%d currentlyConnected=%d medianDiedLifetimeMs=%d\n",
		h.neverConnected, h.connectedThenDied, h.survived, h.currentlyConnected, h.medianDiedMs)
	logPerKindLifetime()
	logInjectionAttribution()
	stunPhaseSnapshotsMu.Lock()
	t := stunPhaseSnapshots["pacing-failed"]
	stunPhaseSnapshotsMu.Unlock()
	fmt.Fprintf(os.Stderr, "attribution stun: phase=pacing-failed reqWritten=%d respWritten=%d reqRead=%d respRead=%d\n",
		t[0], t[1], t[2], t[3])
}

// snapshotLifetimeAtWaitEnd records the lifetime histogram as it stands at
// wait-end, before teardown closes the pairs again.
func snapshotLifetimeAtWaitEnd() {
	h := pcLifetimeHistogram()
	lifetimeAtWaitEndMu.Lock()
	lifetimeAtWaitEnd = h
	lifetimeAtWaitEndMu.Unlock()
}

// pcCloseSummary renders a PC's lifetime at close time for the
// close-initiator attribution: last ICE/connection state, whether it ever
// connected, total connected time, and first-failure time.
func pcCloseSummary(kind, id string) string {
	lt := pcLifetimeFor(kind, id)
	iceState, _ := lt.lastICEState.Load().(string)
	connState, _ := lt.lastConnState.Load().(string)
	firstFailed := lt.firstFailed.Load()
	failedStr := "never"
	if firstFailed != 0 {
		failedStr = strconv.FormatInt(firstFailed, 10)
	}
	return fmt.Sprintf(" lastICE=%s lastConn=%s everConnected=%t connectedMs=%d firstFailed=%s transitions=%d",
		iceState, connState, lt.everConnected.Load(),
		lt.connectedNanos.Load()/uint64(time.Millisecond), failedStr, lt.transitions.Load())
}

func registerCountingConn(c *packetReadCountingConn, role string) {
	if c == nil {
		return
	}
	c.role = role
	countingConnRegistry.Store(c, struct{}{})
}

// recordSocketClose logs a UDP socket close for the attribution trace.
// pcKey is the "kind:id" of the PeerConnection that owns the socket ("" when
// there is none); when present, the close line carries that PC's last
// ICE/connection state and first-failure time, so the initiator of the close
// is visible: a PC whose last ICE state is failed/disconnected was closed by
// its ICE transport failing, not by the app. initiator names an app-side
// close reason (e.g. "app-teardown" for the mux-close defer); "" means the
// close was driven by Pion (ICE failure or PC close).
func recordSocketClose(role, localAddr, pcKey, initiator string) {
	now := time.Now()
	mono := time.Since(monoOrigin).Nanoseconds()
	port := 0
	if _, portStr, err := net.SplitHostPort(localAddr); err == nil {
		port, _ = strconv.Atoi(portStr)
	}
	if port != 0 {
		closedPorts.Store(port, mono)
	}
	extra := ""
	if pcKey != "" {
		kind, id, _ := strings.Cut(pcKey, ":")
		extra = " pcKey=" + pcKey + pcCloseSummary(kind, id)
	}
	if initiator != "" {
		extra += " initiator=" + initiator
	}
	fmt.Fprintf(os.Stderr, "socket closed: role=%s local=%s port=%d at=%s mono=%d%s\n",
		role, localAddr, port, now.Format(time.RFC3339Nano), mono, extra)
}

func destPortOf(addr net.Addr) int {
	if udpAddr, ok := addr.(*net.UDPAddr); ok && udpAddr != nil {
		return udpAddr.Port
	}
	if addr == nil {
		return 0
	}
	_, portStr, err := net.SplitHostPort(addr.String())
	if err != nil {
		return 0
	}
	port, _ := strconv.Atoi(portStr)
	return port
}

// classifyPacket distinguishes STUN / RTCP / RTP on a multiplexed loopback
// socket: STUN by magic cookie, RTCP by payload type 200-207 in the second
// byte (SR 200, RR 201, SDES 202, BYE 203, APP 204, RTPFB 205, PSFB 206,
// XR 207 — NACK is 205, PLI/FIR are 206), anything else is RTP. Retransmit
// vs original RTP cannot be told apart at this layer; the app's own NACK /
// retransmit counters already cover that.
func classifyPacket(buffer []byte) string {
	if len(buffer) == 0 {
		return "unknown"
	}
	if stun.IsMessage(buffer) {
		return "stun"
	}
	if len(buffer) > 1 && buffer[1] >= 200 && buffer[1] <= 207 {
		return "rtcp"
	}
	return "rtp"
}

// classifySTUN splits a STUN message by type: Binding Request (0x0001),
// Binding Success Response (0x0101), Binding Error Response (0x0111). The
// first two bytes are the message type in network byte order. Used to tell
// ICE connectivity checks (requests) from their answers (responses): if
// responses collapse while requests continue, consent is starving.
func classifySTUN(buffer []byte) string {
	if len(buffer) < 2 {
		return "other"
	}
	switch binary.BigEndian.Uint16(buffer[:2]) {
	case 0x0001:
		return "request"
	case 0x0101:
		return "response"
	case 0x0111:
		return "error"
	default:
		return "other"
	}
}

func attachPCStateLogging(peer *webrtc.PeerConnection, kind, id string) {
	if peer == nil {
		return
	}
	peer.OnICEConnectionStateChange(func(state webrtc.ICEConnectionState) {
		key := kind + " ice=" + state.String()
		v, _ := pcStateCounts.LoadOrStore(key, &atomic.Uint64{})
		v.(*atomic.Uint64).Add(1)
		mono := time.Since(monoOrigin).Nanoseconds()
		if tracePCStateTransitions {
			fmt.Fprintf(os.Stderr, "pc ice state: kind=%s id=%s state=%s at=%s mono=%d\n",
				kind, id, state.String(), time.Now().Format(time.RFC3339Nano), mono)
		}
		// M7-H attempt 7: track the PC's lifetime for the
		// close-initiator / lifetime histogram.
		lt := pcLifetimeFor(kind, id)
		lt.transitions.Add(1)
		lt.lastICEState.Store(state.String())
		switch state {
		case webrtc.ICEConnectionStateConnected, webrtc.ICEConnectionStateCompleted:
			lt.everConnected.Store(true)
			lt.firstConnected.CompareAndSwap(0, mono)
			lt.connectedStart.Store(mono)
		case webrtc.ICEConnectionStateDisconnected, webrtc.ICEConnectionStateFailed, webrtc.ICEConnectionStateClosed:
			if start := lt.connectedStart.Load(); start >= 0 {
				lt.connectedNanos.Add(uint64(mono - start))
				lt.connectedStart.Store(-1)
			}
			if state == webrtc.ICEConnectionStateFailed {
				lt.firstFailed.CompareAndSwap(0, mono)
			}
		}
	})
	peer.OnConnectionStateChange(func(state webrtc.PeerConnectionState) {
		key := kind + " conn=" + state.String()
		v, _ := pcStateCounts.LoadOrStore(key, &atomic.Uint64{})
		v.(*atomic.Uint64).Add(1)
		if tracePCStateTransitions {
			fmt.Fprintf(os.Stderr, "pc conn state: kind=%s id=%s state=%s at=%s mono=%d\n",
				kind, id, state.String(), time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds())
		}
		// M7-H attempt 7: track the PC's lifetime (connection state is
		// corroboration; ICE state is the primary lifecycle signal).
		lt := pcLifetimeFor(kind, id)
		lt.transitions.Add(1)
		lt.lastConnState.Store(state.String())
	})
}

func setRunPhase(phase string) {
	runPhaseName.Store(phase)
	snapshotDestStats(phase)
	snapshotSTUNStats(phase)
	if phase == "wait-end" {
		snapshotLifetimeAtWaitEnd()
	}
}

// snapshotSTUNStats records the aggregate STUN request/response counts at a
// phase boundary, so the attribution print can show whether ICE answers
// (responses) collapse while checks (requests) continue — the consent
// starvation signal.
func snapshotSTUNStats(phase string) {
	var totals [4]uint64 // reqWritten, respWritten, reqRead, respRead
	countingConnRegistry.Range(func(key, _ any) bool {
		conn, ok := key.(*packetReadCountingConn)
		if !ok || conn == nil {
			return true
		}
		totals[0] += conn.stunReqWritten.Load()
		totals[1] += conn.stunRespWritten.Load()
		totals[2] += conn.stunReqRead.Load()
		totals[3] += conn.stunRespRead.Load()
		return true
	})
	stunPhaseSnapshotsMu.Lock()
	stunPhaseSnapshots[phase] = totals
	stunPhaseSnapshotsMu.Unlock()
}

func snapshotDestStats(phase string) {
	byRole := make(map[string]map[int]uint64)
	deadByRole := make(map[string]map[int]uint64)
	conns := 0
	countingConnRegistry.Range(func(key, _ any) bool {
		conn, ok := key.(*packetReadCountingConn)
		if !ok || conn == nil {
			return true
		}
		conns++
		role := conn.role
		conn.destStats.Range(func(dkey, dval any) bool {
			port, ok := dkey.(int)
			st, ok2 := dval.(*destWriteStats)
			if !ok || !ok2 || st == nil {
				return true
			}
			if byRole[role] == nil {
				byRole[role] = make(map[int]uint64)
				deadByRole[role] = make(map[int]uint64)
			}
			byRole[role][port] = st.count.Load()
			deadByRole[role][port] = st.deadCount.Load()
			return true
		})
		return true
	})
	destPhaseSnapshotsMu.Lock()
	destPhaseSnapshots[phase] = byRole
	deadPhaseSnapshots[phase] = deadByRole
	destPhaseSnapshotsMu.Unlock()
	fmt.Fprintf(os.Stderr, "attribution snapshot: phase=%s conns=%d roles=%d\n", phase, conns, len(byRole))
}

// portAppearsBounded reports whether port appears in s as ":<port>" followed
// by a non-digit (or end of string), so ":5432" does not match ":54321".
func portAppearsBounded(s string, port int) bool {
	needle := ":" + strconv.Itoa(port)
	for i := 0; i+len(needle) <= len(s); i++ {
		if s[i:i+len(needle)] != needle {
			continue
		}
		end := i + len(needle)
		if end == len(s) || s[end] < '0' || s[end] > '9' {
			return true
		}
	}
	return false
}

// logEndpointAttribution prints the attempt-6 trace: per-phase dead-write
// totals, the top dead destinations with their close times and ICE
// nomination status, the bounded dead-write sample, and the PC state counts.
// It joins app-side writes against app-side socket closes, so a destination
// written after its socket closed is attributed, not guessed.
func logEndpointAttribution(router *sfuRouter, viewers []viewerEndpoint) {
	phases := []string{"streaming", "wait-start", "wait-end"}
	phaseDead := make(map[string]uint64)
	phaseTotal := make(map[string]uint64)
	destPhaseSnapshotsMu.Lock()
	for _, phase := range phases {
		for _, byPort := range deadPhaseSnapshots[phase] {
			for _, n := range byPort {
				phaseDead[phase] += n
			}
		}
		for _, byPort := range destPhaseSnapshots[phase] {
			for _, n := range byPort {
				phaseTotal[phase] += n
			}
		}
	}
	destPhaseSnapshotsMu.Unlock()
	fmt.Fprintf(os.Stderr, "attribution phases: streaming dead=%d total=%d; wait-start dead=%d total=%d; wait-end dead=%d total=%d; dead during wait=%d; dead during streaming=%d\n",
		phaseDead["streaming"], phaseTotal["streaming"],
		phaseDead["wait-start"], phaseTotal["wait-start"],
		phaseDead["wait-end"], phaseTotal["wait-end"],
		phaseDead["wait-end"]-phaseDead["wait-start"],
		phaseDead["wait-start"]-phaseDead["streaming"])

	type deadDest struct {
		port      int
		total     uint64
		dead      uint64
		rtp       uint64
		rtcp      uint64
		stun      uint64
		first     int64
		last      int64
		closedAt  int64
		closed    bool
		role      string
		nominated bool
	}
	byPort := make(map[int]*deadDest)
	var totalWrites, totalDead uint64
	countingConnRegistry.Range(func(key, _ any) bool {
		conn, ok := key.(*packetReadCountingConn)
		if !ok || conn == nil {
			return true
		}
		conn.destStats.Range(func(dkey, dval any) bool {
			port, ok := dkey.(int)
			st, ok2 := dval.(*destWriteStats)
			if !ok || !ok2 || st == nil {
				return true
			}
			d := byPort[port]
			if d == nil {
				d = &deadDest{port: port, first: st.firstNanos.Load(), role: conn.role}
				byPort[port] = d
			}
			c := st.count.Load()
			d.total += c
			d.dead += st.deadCount.Load()
			d.rtp += st.rtpCount.Load()
			d.rtcp += st.rtcpCount.Load()
			d.stun += st.stunCount.Load()
			if f := st.firstNanos.Load(); f != 0 && f < d.first {
				d.first = f
			}
			if l := st.lastNanos.Load(); l > d.last {
				d.last = l
			}
			if c > 0 && conn.role != "" && d.role == "" {
				d.role = conn.role
			}
			totalWrites += c
			totalDead += st.deadCount.Load()
			return true
		})
		return true
	})
	// ICE join: is this destination port the currently nominated remote of
	// any viewer (router side)? If yes the write went to the right place
	// and the socket closed underneath it (lifecycle); if no, the router
	// wrote to a port that is not the current nominated remote (stale/wrong).
	for _, d := range byPort {
		if v, ok := closedPorts.Load(d.port); ok {
			d.closed = true
			d.closedAt, _ = v.(int64)
		}
		for _, viewer := range viewers {
			if viewer.candidatePairs == nil {
				continue
			}
			_, routerPairs := viewer.candidatePairs.load()
			if portAppearsBounded(routerPairs, d.port) {
				d.nominated = true
				break
			}
		}
	}
	dests := make([]*deadDest, 0, len(byPort))
	for _, d := range byPort {
		dests = append(dests, d)
	}
	sort.Slice(dests, func(i, j int) bool { return dests[i].dead > dests[j].dead })
	fmt.Fprintf(os.Stderr, "attribution totals: dests=%d totalWrites=%d deadWrites=%d deadShare=%.1f%%\n",
		len(dests), totalWrites, totalDead, 100*float64(totalDead)/float64(max(totalWrites, 1)))
	shown := 0
	for _, d := range dests {
		if d.dead == 0 || shown >= 20 {
			continue
		}
		shown++
		fmt.Fprintf(os.Stderr, "attribution dead dest: port=%d total=%d dead=%d rtp=%d rtcp=%d stun=%d firstMono=%d lastMono=%d closed=%t closedMono=%d nominated=%t role=%s\n",
			d.port, d.total, d.dead, d.rtp, d.rtcp, d.stun, d.first, d.last, d.closed, d.closedAt, d.nominated, d.role)
	}
	// ICE match summary: for each viewer, does its router write destination
	// match its currently nominated router remote?
	matched, mismatched := 0, 0
	var mismatchExamples []string
	for _, viewer := range viewers {
		if viewer.routerSocketConn == nil || viewer.candidatePairs == nil {
			continue
		}
		_, routerPairs := viewer.candidatePairs.load()
		anyMatch := false
		viewer.routerSocketConn.destStats.Range(func(dkey, _ any) bool {
			if port, ok := dkey.(int); ok && portAppearsBounded(routerPairs, port) {
				anyMatch = true
				return false
			}
			return true
		})
		if anyMatch {
			matched++
		} else {
			mismatched++
			if len(mismatchExamples) < 20 {
				mismatchExamples = append(mismatchExamples, viewer.id)
			}
		}
	}
	fmt.Fprintf(os.Stderr, "attribution ice match: matched=%d mismatched=%d mismatchExamples=%v\n",
		matched, mismatched, mismatchExamples)
	// PC state transition counts.
	pcStateCounts.Range(func(key, value any) bool {
		ks, _ := key.(string)
		ctr, _ := value.(*atomic.Uint64)
		var n uint64
		if ctr != nil {
			n = ctr.Load()
		}
		fmt.Fprintf(os.Stderr, "attribution pc state: %s count=%d\n", ks, n)
		return true
	})
	// Bounded dead-write sample (first 1,000).
	deadWriteSamplesMu.Lock()
	samples := append([]deadWriteSample(nil), deadWriteSamples...)
	deadWriteSamplesMu.Unlock()
	fmt.Fprintf(os.Stderr, "attribution dead sample: total=%d showing=%d\n", deadWriteSampleCount.Load(), min(len(samples), 20))
	for i, s := range samples {
		if i >= 20 {
			break
		}
		fmt.Fprintf(os.Stderr, "attribution dead sample %d: mono=%d role=%s destPort=%d class=%s size=%d\n",
			i, s.monoNanos, s.role, s.destPort, s.class, s.size)
	}
	// M7-H attempt 7: lifetime histogram + STUN phase totals + skipped
	// destination accounting (the attempt-6 destStats total gap).
	h := pcLifetimeHistogram()
	fmt.Fprintf(os.Stderr, "attribution lifetime: neverConnected=%d connectedThenDied=%d survived=%d currentlyConnected=%d medianDiedLifetimeMs=%d\n",
		h.neverConnected, h.connectedThenDied, h.survived, h.currentlyConnected, h.medianDiedMs)
	// M7-H attempt 8: per-kind lifetimes + injection timing.
	logPerKindLifetime()
	logInjectionAttribution()
	var totalSkipped uint64
	countingConnRegistry.Range(func(key, _ any) bool {
		conn, ok := key.(*packetReadCountingConn)
		if !ok || conn == nil {
			return true
		}
		totalSkipped += conn.skippedDestStats.Load()
		return true
	})
	fmt.Fprintf(os.Stderr, "attribution skippedDestStats: total=%d\n", totalSkipped)
	stunPhaseSnapshotsMu.Lock()
	for _, p := range []string{"streaming", "wait-start", "wait-end"} {
		t := stunPhaseSnapshots[p]
		fmt.Fprintf(os.Stderr, "attribution stun: phase=%s reqWritten=%d respWritten=%d reqRead=%d respRead=%d\n",
			p, t[0], t[1], t[2], t[3])
	}
	stunPhaseSnapshotsMu.Unlock()
}

// logTeardownAttribution prints the final attribution totals AFTER the
// teardown closes have run (it is registered first, so it runs last). The
// attempt-6 print ran before teardown, which left the final stretch of
// kernel no-socket unattributed; this print closes that gap. It reads only
// package-level globals, so it needs no router/viewers. It is a no-op when
// the run never reached the wait (early return).
func logTeardownAttribution() {
	phase, _ := runPhaseName.Load().(string)
	// M7-H attempt 8: fire for ANY post-setup phase. Attempt 7 died during
	// pacing with phase "streaming" and the old "wait-end"/"teardown" guard
	// skipped the print, leaving deadDuringTeardown unknown (rule (d)).
	if phase == "" {
		return
	}
	snapshotDestStats("teardown")
	snapshotSTUNStats("teardown")
	h := pcLifetimeHistogram()
	var totalWrites, totalDead, totalSkipped uint64
	countingConnRegistry.Range(func(key, _ any) bool {
		conn, ok := key.(*packetReadCountingConn)
		if !ok || conn == nil {
			return true
		}
		conn.destStats.Range(func(_, dval any) bool {
			st, ok2 := dval.(*destWriteStats)
			if !ok2 || st == nil {
				return true
			}
			totalWrites += st.count.Load()
			totalDead += st.deadCount.Load()
			return true
		})
		totalSkipped += conn.skippedDestStats.Load()
		return true
	})
	destPhaseSnapshotsMu.Lock()
	// M7-H attempt 8: baseline is the last pre-teardown snapshot — "wait-end"
	// when the run reached the wait, "pacing-failed" when it died in injection.
	baselineDead := uint64(0)
	for _, p := range []string{"wait-end", "pacing-failed"} {
		if byRole, ok := deadPhaseSnapshots[p]; ok {
			for _, byPort := range byRole {
				for _, n := range byPort {
					baselineDead += n
				}
			}
			break
		}
	}
	destPhaseSnapshotsMu.Unlock()
	deadDuringTeardown := uint64(0)
	if totalDead >= baselineDead {
		deadDuringTeardown = totalDead - baselineDead
	}
	fmt.Fprintf(os.Stderr, "attribution teardown: totalWrites=%d deadWrites=%d deadDuringTeardown=%d skippedDestStats=%d\n",
		totalWrites, totalDead, deadDuringTeardown, totalSkipped)
	fmt.Fprintf(os.Stderr, "attribution lifetime: neverConnected=%d connectedThenDied=%d survived=%d currentlyConnected=%d medianDiedLifetimeMs=%d\n",
		h.neverConnected, h.connectedThenDied, h.survived, h.currentlyConnected, h.medianDiedMs)
	// M7-H attempt 8: per-kind lifetimes at the final print too.
	logPerKindLifetime()
	lifetimeAtWaitEndMu.Lock()
	we := lifetimeAtWaitEnd
	lifetimeAtWaitEndMu.Unlock()
	fmt.Fprintf(os.Stderr, "attribution lifetime at wait-end: neverConnected=%d connectedThenDied=%d survived=%d currentlyConnected=%d medianDiedLifetimeMs=%d\n",
		we.neverConnected, we.connectedThenDied, we.survived, we.currentlyConnected, we.medianDiedMs)
	stunPhaseSnapshotsMu.Lock()
	for _, p := range []string{"streaming", "send-start", "send-mid", "wait-start", "wait-end", "pacing-failed", "teardown"} {
		t := stunPhaseSnapshots[p]
		fmt.Fprintf(os.Stderr, "attribution stun: phase=%s reqWritten=%d respWritten=%d reqRead=%d respRead=%d\n",
			p, t[0], t[1], t[2], t[3])
	}
	stunPhaseSnapshotsMu.Unlock()
}

type packetReadCountingConn struct {
	net.PacketConn
	// M7-H attempt 6: role identifies the socket for the attribution trace
	// ("viewer-client", "router-shard-N:<viewerID>"); destStats aggregates
	// writes per destination port (key = dest UDP port).
	role                         string
	destStats                    sync.Map // int -> *destWriteStats
	packetsRead                  atomic.Uint64
	nonSTUNPacketsRead           atomic.Uint64
	stunPacketsRead              atomic.Uint64
	packetsWritten               atomic.Uint64
	nonSTUNPacketsWritten        atomic.Uint64
	stunPacketsWritten           atomic.Uint64
	bytesWritten                 atomic.Uint64
	firstNonSTUNWriteDestination atomic.Pointer[string]
	// M7-H attempt 7: pcKey identifies the owning PeerConnection
	// ("kind:id") for close-initiator attribution; the STUN counters split
	// checks (requests) from answers (responses) for consent accounting;
	// skippedDestStats counts writes whose destination port could not be
	// determined (the attempt-6 destStats total gap).
	pcKey            string
	stunReqWritten   atomic.Uint64
	stunRespWritten  atomic.Uint64
	stunReqRead      atomic.Uint64
	stunRespRead     atomic.Uint64
	skippedDestStats atomic.Uint64
	closeOnce        sync.Once
	closeErr         error
}

func (c *packetReadCountingConn) ReadFrom(buffer []byte) (int, net.Addr, error) {
	n, addr, err := c.PacketConn.ReadFrom(buffer)
	if err == nil {
		c.packetsRead.Add(1)
		if stun.IsMessage(buffer[:n]) {
			c.stunPacketsRead.Add(1)
			// M7-H attempt 7: split STUN reads into checks vs answers.
			switch classifySTUN(buffer[:n]) {
			case "request":
				c.stunReqRead.Add(1)
			case "response":
				c.stunRespRead.Add(1)
			}
		} else {
			c.nonSTUNPacketsRead.Add(1)
		}
	}
	return n, addr, err
}

func (c *packetReadCountingConn) WriteTo(buffer []byte, addr net.Addr) (int, error) {
	n, err := c.PacketConn.WriteTo(buffer, addr)
	if err == nil {
		c.packetsWritten.Add(1)
		c.bytesWritten.Add(uint64(n))
		if stun.IsMessage(buffer[:n]) {
			c.stunPacketsWritten.Add(1)
			// M7-H attempt 7: split STUN writes into checks vs answers.
			switch classifySTUN(buffer[:n]) {
			case "request":
				c.stunReqWritten.Add(1)
			case "response":
				c.stunRespWritten.Add(1)
			}
		} else {
			c.nonSTUNPacketsWritten.Add(1)
			if addr != nil && c.firstNonSTUNWriteDestination.Load() == nil {
				destination := addr.String()
				c.firstNonSTUNWriteDestination.CompareAndSwap(nil, &destination)
			}
		}
		// M7-H attempt 6: per-destination write accounting. Aggregates only
		// (one sync.Map entry per destination port); the dead-write check is
		// a single registry lookup per write. No per-datagram logging.
		if destPort := destPortOf(addr); destPort != 0 {
			now := time.Since(monoOrigin).Nanoseconds()
			class := classifyPacket(buffer[:n])
			v, _ := c.destStats.LoadOrStore(destPort, &destWriteStats{})
			st := v.(*destWriteStats)
			st.count.Add(1)
			switch class {
			case "rtp":
				st.rtpCount.Add(1)
			case "rtcp":
				st.rtcpCount.Add(1)
			case "stun":
				st.stunCount.Add(1)
			}
			st.firstNanos.CompareAndSwap(0, now)
			st.lastNanos.Store(now)
			if _, closed := closedPorts.Load(destPort); closed {
				st.deadCount.Add(1)
				if deadWriteSampleCount.Load() < 1000 {
					deadWriteSamplesMu.Lock()
					if len(deadWriteSamples) < 1000 {
						deadWriteSamples = append(deadWriteSamples, deadWriteSample{monoNanos: now, role: c.role, destPort: destPort, class: class, size: n})
						deadWriteSampleCount.Add(1)
					}
					deadWriteSamplesMu.Unlock()
				}
			}
		} else {
			// M7-H attempt 7: count writes whose destination port could
			// not be determined — the attempt-6 destStats total gap.
			c.skippedDestStats.Add(1)
		}
	}
	return n, err
}

func (c *packetReadCountingConn) Close() error {
	c.closeOnce.Do(func() {
		// M7-H attempt 6: record the socket close for the attribution trace
		// (lifecycle half). The router mux conns are closed by the ice mux
		// teardown, not here — those closes are logged at the mux close site.
		// M7-H attempt 7: pass the owning PC key so the close line carries
		// the initiator (the PC's last ICE state).
		if c.PacketConn != nil {
			recordSocketClose(c.role, c.LocalAddr().String(), c.pcKey, "")
		}
		c.closeErr = c.PacketConn.Close()
	})
	return c.closeErr
}

// singlePeerUDPMux provides one dedicated socket directly to one PeerConnection.
type singlePeerUDPMux struct {
	conn *packetReadCountingConn
}

type countingUDPMux struct {
	mux         ice.UDPMux
	mu          sync.Mutex
	conn        *packetReadCountingConn
	initialized bool
}

func newCountingUDPMux(mux ice.UDPMux) *countingUDPMux {
	m := &countingUDPMux{
		mux:  mux,
		conn: &packetReadCountingConn{},
	}
	// M7-H attempt 6: register for the attribution trace; the viewer loop
	// refines the role to "router-shard-N:<viewerID>".
	registerCountingConn(m.conn, "router-shard")
	return m
}

func (m *countingUDPMux) GetConn(ufrag string, addr net.Addr) (net.PacketConn, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.initialized {
		return m.conn, nil
	}
	conn, err := m.mux.GetConn(ufrag, addr)
	if err != nil {
		return nil, err
	}
	m.conn.PacketConn = conn
	m.initialized = true
	return m.conn, nil
}

func (m *countingUDPMux) RemoveConnByUfrag(ufrag string) {
	m.mux.RemoveConnByUfrag(ufrag)
}

func (m *countingUDPMux) GetListenAddresses() []net.Addr {
	return m.mux.GetListenAddresses()
}

func (m *countingUDPMux) Close() error {
	return nil
}

func newSinglePeerUDPMux() (*singlePeerUDPMux, error) {
	conn, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		return nil, fmt.Errorf("open viewer loopback UDP socket: %w", err)
	}
	counting := &packetReadCountingConn{PacketConn: conn}
	// M7-H attempt 6: register for the attribution trace.
	registerCountingConn(counting, "viewer-client")
	return &singlePeerUDPMux{conn: counting}, nil
}

func (m *singlePeerUDPMux) GetConn(string, net.Addr) (net.PacketConn, error) {
	return m.conn, nil
}

func setUDPConnReadBuffer(conn net.PacketConn, requested int) (int, error) {
	udpConn, ok := conn.(*net.UDPConn)
	if !ok {
		return 0, fmt.Errorf("client socket is %T, not *net.UDPConn", conn)
	}
	if err := udpConn.SetReadBuffer(requested); err != nil {
		return 0, fmt.Errorf("set client UDP receive buffer to %d bytes: %w", requested, err)
	}
	rawConn, err := udpConn.SyscallConn()
	if err != nil {
		return 0, fmt.Errorf("get client UDP socket handle: %w", err)
	}
	var actual int
	var socketErr error
	if err := rawConn.Control(func(fd uintptr) {
		actual, socketErr = syscall.GetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_RCVBUF)
	}); err != nil {
		return 0, fmt.Errorf("inspect client UDP receive buffer: %w", err)
	}
	if socketErr != nil {
		return 0, fmt.Errorf("read client UDP SO_RCVBUF: %w", socketErr)
	}
	return actual, nil
}

// readUDPConnReadBuffer returns the effective SO_RCVBUF of a UDP socket
// without changing it. Attempt 5: Pion sets the router mux buffer at socket
// creation and ignores the error, so the requested value alone proves
// nothing — this is the only way to verify the buffer actually took effect.
func readUDPConnReadBuffer(conn net.PacketConn) (int, error) {
	udpConn, ok := conn.(*net.UDPConn)
	if !ok {
		return 0, fmt.Errorf("socket is %T, not *net.UDPConn", conn)
	}
	rawConn, err := udpConn.SyscallConn()
	if err != nil {
		return 0, fmt.Errorf("get UDP socket handle: %w", err)
	}
	var actual int
	var socketErr error
	if err := rawConn.Control(func(fd uintptr) {
		actual, socketErr = syscall.GetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_RCVBUF)
	}); err != nil {
		return 0, fmt.Errorf("inspect UDP receive buffer: %w", err)
	}
	if socketErr != nil {
		return 0, fmt.Errorf("read UDP SO_RCVBUF: %w", socketErr)
	}
	return actual, nil
}

func (m *singlePeerUDPMux) RemoveConnByUfrag(string) {}

func (m *singlePeerUDPMux) GetListenAddresses() []net.Addr {
	return []net.Addr{m.conn.LocalAddr()}
}

func (m *singlePeerUDPMux) Close() error {
	return m.conn.Close()
}

type candidatePairSnapshot struct {
	mu     sync.RWMutex
	client string
	router string
}

func (s *candidatePairSnapshot) update(client, router string) {
	s.mu.Lock()
	if client != "" {
		s.client = client
	}
	if router != "" {
		s.router = router
	}
	s.mu.Unlock()
}

func (s *candidatePairSnapshot) load() (string, string) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.client, s.router
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
			return fmt.Errorf(
				"PeerConnections did not connect (publisher=%s/%s subscriber=%s/%s): %w",
				publisher.ConnectionState(),
				publisher.ICEConnectionState(),
				subscriber.ConnectionState(),
				subscriber.ICEConnectionState(),
				ctx.Err(),
			)
		case <-ticker.C:
		}
	}
}

func iceCandidatePairDiagnostics(peer *webrtc.PeerConnection) string {
	return candidatePairDiagnostics(peer, false)
}

func nominatedICECandidatePairDiagnostics(peer *webrtc.PeerConnection) string {
	return candidatePairDiagnostics(peer, true)
}

func candidatePairDiagnostics(peer *webrtc.PeerConnection, nominatedOnly bool) string {
	var pairs []string
	report := peer.GetStats()
	candidates := make(map[string]webrtc.ICECandidateStats)
	for _, stats := range report {
		if candidate, ok := stats.(webrtc.ICECandidateStats); ok {
			candidates[candidate.ID] = candidate
		}
	}
	for _, stats := range report {
		pair, ok := stats.(webrtc.ICECandidatePairStats)
		if !ok {
			continue
		}
		if nominatedOnly && !pair.Nominated {
			continue
		}
		pairs = append(pairs, fmt.Sprintf(
			"%s:%s nominated=%t local=%s remote=%s sent=%d received=%d req=%d/%d resp=%d/%d",
			pair.ID,
			pair.State,
			pair.Nominated,
			formatICECandidate(candidates[pair.LocalCandidateID]),
			formatICECandidate(candidates[pair.RemoteCandidateID]),
			pair.PacketsSent,
			pair.PacketsReceived,
			pair.RequestsSent,
			pair.RequestsReceived,
			pair.ResponsesReceived,
			pair.ResponsesSent,
		))
	}
	sort.Strings(pairs)
	return strings.Join(pairs, ";")
}

func captureViewerCandidatePairSnapshot(router *sfuRouter, viewer viewerEndpoint) {
	if viewer.candidatePairs == nil {
		return
	}
	clientPairs := nominatedICECandidatePairDiagnostics(viewer.client)
	routerPairs := ""
	if peer := router.viewerPeer(viewer.id); peer != nil {
		routerPairs = nominatedICECandidatePairDiagnostics(peer)
	}
	viewer.candidatePairs.update(clientPairs, routerPairs)
}

func sampleViewerCandidatePairSnapshots(
	ctx context.Context,
	router *sfuRouter,
	viewers []viewerEndpoint,
) {
	if len(viewers) == 0 {
		return
	}
	jobs := make(chan viewerEndpoint)
	workerCount := min(peerNegotiationConcurrency, len(viewers))
	var workers sync.WaitGroup
	workers.Add(workerCount)
	for range workerCount {
		go func() {
			defer workers.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case viewer, ok := <-jobs:
					if !ok {
						return
					}
					captureViewerCandidatePairSnapshot(router, viewer)
				}
			}
		}()
	}
	for _, viewer := range viewers {
		select {
		case <-ctx.Done():
			close(jobs)
			workers.Wait()
			return
		case jobs <- viewer:
		}
	}
	close(jobs)
	workers.Wait()
}

func startCandidatePairSampler(
	ctx context.Context,
	router *sfuRouter,
	viewers []viewerEndpoint,
	sampleM7HReadQueues bool,
) func() {
	samplerCtx, cancel := context.WithCancel(ctx)
	done := make(chan struct{})
	go func() {
		defer close(done)
		startedAt := time.Now()
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		sampleViewerCandidatePairSnapshots(samplerCtx, router, viewers)
		for {
			select {
			case <-samplerCtx.Done():
				if sampleM7HReadQueues {
					sampleM7HReadQueueDiagnostics(router, viewers, time.Since(startedAt))
				}
				return
			case <-ticker.C:
				sampleViewerCandidatePairSnapshots(samplerCtx, router, viewers)
				if sampleM7HReadQueues {
					sampleM7HReadQueueDiagnostics(router, viewers, time.Since(startedAt))
				}
			}
		}
	}()
	var stopOnce sync.Once
	return func() {
		stopOnce.Do(func() {
			cancel()
			<-done
		})
	}
}

func sampleM7HReadQueueDiagnostics(
	router *sfuRouter,
	viewers []viewerEndpoint,
	elapsed time.Duration,
) {
	var readCalls, readErrorReturns, readTotalNanos, readMaxNanos uint64
	var readBuckets [m7hReadDurationBucketCount]uint64
	for _, viewer := range viewers {
		if viewer.capture == nil || viewer.capture.readTiming == nil {
			continue
		}
		snapshot := viewer.capture.readTiming.snapshotAndReset()
		readCalls += snapshot.calls
		readErrorReturns += snapshot.errorReturns
		readTotalNanos += snapshot.totalNanos
		if snapshot.maxNanos > readMaxNanos {
			readMaxNanos = snapshot.maxNanos
		}
		for index, count := range snapshot.buckets {
			readBuckets[index] += count
		}
	}

	subscriptions := make([]*sfuSubscription, 0, len(viewers))
	router.mu.RLock()
	for _, viewer := range viewers {
		if registered := router.viewers[viewer.id]; registered != nil {
			if subscription := registered.subscriptions[viewer.key]; subscription != nil {
				subscriptions = append(subscriptions, subscription)
			}
		}
	}
	router.mu.RUnlock()

	rtpDepths := make([]int, 0, len(subscriptions))
	nackDepths := make([]int, 0, len(subscriptions))
	var rtpNonEmpty, rtpFull, nackNonEmpty, nackFull int
	for _, subscription := range subscriptions {
		rtpDepth, rtpCapacity := 0, 0
		if subscription.rtpQueue != nil {
			rtpDepth, rtpCapacity = len(subscription.rtpQueue), cap(subscription.rtpQueue)
		}
		nackDepth, nackCapacity := 0, 0
		if subscription.nackQueue != nil {
			nackDepth, nackCapacity = len(subscription.nackQueue), cap(subscription.nackQueue)
		}
		rtpDepths = append(rtpDepths, rtpDepth)
		nackDepths = append(nackDepths, nackDepth)
		if rtpDepth > 0 {
			rtpNonEmpty++
		}
		if rtpCapacity > 0 && rtpDepth == rtpCapacity {
			rtpFull++
		}
		if nackDepth > 0 {
			nackNonEmpty++
		}
		if nackCapacity > 0 && nackDepth == nackCapacity {
			nackFull++
		}
	}
	sort.Ints(rtpDepths)
	sort.Ints(nackDepths)
	fmt.Fprintf(
		os.Stderr,
		"m7h read/queue sample: elapsedMs=%d viewers=%d readCalls=%d readErrorReturns=%d readTotalMs=%d readMaxMs=%d readBucketsLe1ms=%d readBucketsLe10ms=%d readBucketsLe50ms=%d readBucketsLe100ms=%d readBucketsLe400ms=%d readBucketsLe1s=%d readBucketsLe5s=%d readBucketsGt5s=%d subscriptions=%d rtpQueueDepthP50=%d rtpQueueDepthP95=%d rtpQueueDepthP99=%d rtpQueueDepthMax=%d rtpQueueNonEmpty=%d rtpQueueFull=%d nackQueueDepthP50=%d nackQueueDepthP95=%d nackQueueDepthP99=%d nackQueueDepthMax=%d nackQueueNonEmpty=%d nackQueueFull=%d\n",
		elapsed.Milliseconds(),
		len(viewers),
		readCalls,
		readErrorReturns,
		readTotalNanos/uint64(time.Millisecond),
		readMaxNanos/uint64(time.Millisecond),
		readBuckets[0],
		readBuckets[1],
		readBuckets[2],
		readBuckets[3],
		readBuckets[4],
		readBuckets[5],
		readBuckets[6],
		readBuckets[7],
		len(subscriptions),
		queueDepthPercentile(rtpDepths, 50),
		queueDepthPercentile(rtpDepths, 95),
		queueDepthPercentile(rtpDepths, 99),
		queueDepthPercentile(rtpDepths, 100),
		rtpNonEmpty,
		rtpFull,
		queueDepthPercentile(nackDepths, 50),
		queueDepthPercentile(nackDepths, 95),
		queueDepthPercentile(nackDepths, 99),
		queueDepthPercentile(nackDepths, 100),
		nackNonEmpty,
		nackFull,
	)
}

type m7hPublisherSendStats struct {
	publisherID       string
	frames            atomic.Uint64
	tickLateOver50ms  atomic.Uint64
	tickLateOver1s    atomic.Uint64
	maxTickLateNanos  atomic.Uint64
	lastSendUnixNanos atomic.Int64
}

type m7hPublisherReceiveStats struct {
	publisherID         string
	packets             atomic.Uint64
	lastPacketUnixNanos atomic.Int64
}

func (stats *m7hPublisherSendStats) record(scheduledAt, sentAt time.Time) {
	if stats == nil {
		return
	}
	late := sentAt.Sub(scheduledAt)
	if late > 50*time.Millisecond {
		stats.tickLateOver50ms.Add(1)
	}
	if late > time.Second {
		stats.tickLateOver1s.Add(1)
	}
	nanos := uint64(max(late, 0))
	for previous := stats.maxTickLateNanos.Load(); nanos > previous; previous = stats.maxTickLateNanos.Load() {
		if stats.maxTickLateNanos.CompareAndSwap(previous, nanos) {
			break
		}
	}
	stats.frames.Add(1)
	stats.lastSendUnixNanos.Store(sentAt.UnixNano())
}

type m7hMetricHistogram struct {
	buckets []float64
	counts  []uint64
}

type m7hRuntimeMetricSnapshot struct {
	gcCycles        uint64
	gcCyclesPresent bool
	scheduler       *m7hMetricHistogram
	gcPauses        *m7hMetricHistogram
}

var m7hRuntimeMetricNames = []string{
	"/sched/latencies:seconds",
	"/gc/pauses:seconds",
	"/gc/cycles/total:gc-cycles",
}

func readM7HRuntimeMetrics(samples []runtimemetrics.Sample) m7hRuntimeMetricSnapshot {
	runtimemetrics.Read(samples)
	var snapshot m7hRuntimeMetricSnapshot
	if samples[0].Value.Kind() == runtimemetrics.KindFloat64Histogram {
		histogram := samples[0].Value.Float64Histogram()
		snapshot.scheduler = &m7hMetricHistogram{
			buckets: append([]float64(nil), histogram.Buckets...),
			counts:  append([]uint64(nil), histogram.Counts...),
		}
	}
	if samples[1].Value.Kind() == runtimemetrics.KindFloat64Histogram {
		histogram := samples[1].Value.Float64Histogram()
		snapshot.gcPauses = &m7hMetricHistogram{
			buckets: append([]float64(nil), histogram.Buckets...),
			counts:  append([]uint64(nil), histogram.Counts...),
		}
	}
	if samples[2].Value.Kind() == runtimemetrics.KindUint64 {
		snapshot.gcCycles = samples[2].Value.Uint64()
		snapshot.gcCyclesPresent = true
	}
	return snapshot
}

func m7hProcessCPUSeconds() (float64, error) {
	var usage syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &usage); err != nil {
		return 0, fmt.Errorf("read process CPU usage: %w", err)
	}
	user := float64(usage.Utime.Sec) + float64(usage.Utime.Usec)/float64(time.Second/time.Microsecond)
	system := float64(usage.Stime.Sec) + float64(usage.Stime.Usec)/float64(time.Second/time.Microsecond)
	return user + system, nil
}

func m7hHistogramDelta(
	previous, current *m7hMetricHistogram,
) (count uint64, p95Upper, maxUpper float64) {
	if previous == nil || current == nil || len(current.buckets) != len(previous.buckets) ||
		len(current.counts) != len(previous.counts) {
		return 0, 0, 0
	}
	for index, currentCount := range current.counts {
		if currentCount > previous.counts[index] {
			count += currentCount - previous.counts[index]
		}
	}
	if count == 0 {
		return 0, 0, 0
	}
	p95Target := uint64(math.Ceil(float64(count) * 0.95))
	var cumulative uint64
	for index, currentCount := range current.counts {
		if currentCount > previous.counts[index] {
			delta := currentCount - previous.counts[index]
			cumulative += delta
			maxUpper = current.buckets[index+1]
			if p95Upper == 0 && cumulative >= p95Target {
				p95Upper = current.buckets[index+1]
			}
		}
	}
	return count, p95Upper, maxUpper
}

func startM7HRuntimeProbe(
	role string,
	publishers []*m7hPublisherSendStats,
	onPublisherSendSample func(frames uint64, stalePublishers int),
) func() {
	startedAt := time.Now()
	samples := make([]runtimemetrics.Sample, len(m7hRuntimeMetricNames))
	for index, name := range m7hRuntimeMetricNames {
		samples[index].Name = name
	}
	previousMetrics := readM7HRuntimeMetrics(samples)
	previousSampleAt := startedAt
	previousCPUSeconds, previousCPUAvailable := 0.0, false
	if cpuSeconds, err := m7hProcessCPUSeconds(); err != nil {
		fmt.Fprintf(os.Stderr, "m7h process CPU sample failed: role=%s stage=start err=%v\n", role, err)
	} else {
		previousCPUSeconds, previousCPUAvailable = cpuSeconds, true
	}
	probeCtx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		defer close(done)
		heartbeat := time.NewTicker(10 * time.Millisecond)
		second := time.NewTicker(time.Second)
		defer heartbeat.Stop()
		defer second.Stop()
		for {
			select {
			case scheduledAt := <-heartbeat.C:
				now := time.Now()
				if lateness := now.Sub(scheduledAt); lateness > 50*time.Millisecond {
					fmt.Fprintf(
						os.Stderr,
						"m7h heartbeat late: role=%s at=%s elapsedMs=%d scheduledAt=%s lateMs=%.3f goroutines=%d\n",
						role,
						now.Format(time.RFC3339Nano),
						now.Sub(startedAt).Milliseconds(),
						scheduledAt.Format(time.RFC3339Nano),
						float64(lateness)/float64(time.Millisecond),
						runtime.NumGoroutine(),
					)
				}
			case <-second.C:
				now := time.Now()
				currentMetrics := readM7HRuntimeMetrics(samples)
				elapsed := now.Sub(previousSampleAt)
				elapsedSinceStart := now.Sub(startedAt)
				cpuCores := 0.0
				cpuSeconds, cpuErr := m7hProcessCPUSeconds()
				cpuAvailable := cpuErr == nil
				if cpuErr != nil {
					fmt.Fprintf(os.Stderr, "m7h process CPU sample failed: role=%s at=%s err=%v\n",
						role, now.Format(time.RFC3339Nano), cpuErr)
				} else if previousCPUAvailable && elapsed > 0 {
					cpuCores = (cpuSeconds - previousCPUSeconds) / elapsed.Seconds()
				}
				schedulerCount, schedulerP95, schedulerMax := m7hHistogramDelta(
					previousMetrics.scheduler,
					currentMetrics.scheduler,
				)
				gcPauseCount, gcPauseP95, gcPauseMax := m7hHistogramDelta(
					previousMetrics.gcPauses,
					currentMetrics.gcPauses,
				)
				gcCycles := uint64(0)
				if previousMetrics.gcCyclesPresent && currentMetrics.gcCyclesPresent &&
					currentMetrics.gcCycles >= previousMetrics.gcCycles {
					gcCycles = currentMetrics.gcCycles - previousMetrics.gcCycles
				}
				var memory runtime.MemStats
				runtime.ReadMemStats(&memory)
				fmt.Fprintf(
					os.Stderr,
					"m7h runtime sample: role=%s at=%s elapsedMs=%d intervalMs=%d processCPUSeconds=%.6f cpuAvailable=%t cpuCores=%.3f heapAllocBytes=%d heapInuseBytes=%d goroutines=%d schedSamples=%d schedP95UpperMs=%.3f schedMaxUpperMs=%.3f gcCycles=%d gcPauseSamples=%d gcPauseP95UpperMs=%.3f gcPauseMaxUpperMs=%.3f\n",
					role,
					now.Format(time.RFC3339Nano),
					elapsedSinceStart.Milliseconds(),
					elapsed.Milliseconds(),
					cpuSeconds,
					cpuAvailable,
					cpuCores,
					memory.HeapAlloc,
					memory.HeapInuse,
					runtime.NumGoroutine(),
					schedulerCount,
					schedulerP95*float64(time.Second)/float64(time.Millisecond),
					schedulerMax*float64(time.Second)/float64(time.Millisecond),
					gcCycles,
					gcPauseCount,
					gcPauseP95*float64(time.Second)/float64(time.Millisecond),
					gcPauseMax*float64(time.Second)/float64(time.Millisecond),
				)
				if len(publishers) != 0 {
					frames, stalePublishers := sampleM7HPublisherSendStats(
						publishers,
						now,
						time.Since(startedAt),
					)
					if onPublisherSendSample != nil {
						onPublisherSendSample(frames, stalePublishers)
					}
				}
				if cpuAvailable {
					previousCPUSeconds, previousCPUAvailable = cpuSeconds, true
				} else {
					previousCPUAvailable = false
				}
				previousMetrics = currentMetrics
				previousSampleAt = now
			case <-probeCtx.Done():
				return
			}
		}
	}()
	var stopOnce sync.Once
	return func() {
		stopOnce.Do(func() {
			cancel()
			<-done
		})
	}
}

func startM7HPublisherReceiveSampler(server *m7hRemoteSFUServer) func() {
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		defer close(done)
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		startedAt := time.Now()
		for {
			select {
			case <-ticker.C:
				now := time.Now()
				server.router.mu.RLock()
				stats := make([]*m7hPublisherReceiveStats, 0, len(server.router.m7hPublisherReceiveStats))
				for _, publisherStats := range server.router.m7hPublisherReceiveStats {
					stats = append(stats, publisherStats)
				}
				server.router.mu.RUnlock()
				var packets uint64
				var stale int
				var oldestPublisher string
				var oldestAt time.Time
				var maxAge time.Duration
				for _, publisherStats := range stats {
					packets += publisherStats.packets.Swap(0)
					lastPacketNanos := publisherStats.lastPacketUnixNanos.Load()
					if lastPacketNanos == 0 {
						stale++
						continue
					}
					lastPacketAt := time.Unix(0, lastPacketNanos)
					age := now.Sub(lastPacketAt)
					if age > 500*time.Millisecond {
						stale++
					}
					if age > maxAge {
						maxAge = age
						oldestPublisher = publisherStats.publisherID
						oldestAt = lastPacketAt
					}
				}
				server.mu.Lock()
				server.recvPublishers = len(stats)
				server.recvPackets = packets
				server.recvStale = stale
				server.mu.Unlock()
				fmt.Fprintf(
					os.Stderr,
					"m7h publisher receive sample: role=sfu at=%s elapsedMs=%d publishers=%d packets=%d staleOver500ms=%d maxLastPacketAgeMs=%.3f oldestPublisher=%s oldestLastPacketAt=%s\n",
					now.Format(time.RFC3339Nano),
					now.Sub(startedAt).Milliseconds(),
					len(stats),
					packets,
					stale,
					float64(maxAge)/float64(time.Millisecond),
					oldestPublisher,
					oldestAt.Format(time.RFC3339Nano),
				)
			case <-ctx.Done():
				return
			}
		}
	}()
	var stopOnce sync.Once
	return func() {
		stopOnce.Do(func() {
			cancel()
			<-done
		})
	}
}

func sampleM7HPublisherSendStats(
	publishers []*m7hPublisherSendStats,
	sampledAt time.Time,
	elapsed time.Duration,
) (uint64, int) {
	var frames, tickLateOver50ms, tickLateOver1s, maxTickLateNanos uint64
	var stalePublishers int
	var oldestPublisher string
	var maxLastSendAge time.Duration
	var oldestLastSendAt time.Time
	for _, stats := range publishers {
		frames += stats.frames.Swap(0)
		tickLateOver50ms += stats.tickLateOver50ms.Swap(0)
		tickLateOver1s += stats.tickLateOver1s.Swap(0)
		if tickLate := stats.maxTickLateNanos.Swap(0); tickLate > maxTickLateNanos {
			maxTickLateNanos = tickLate
		}
		lastSendNanos := stats.lastSendUnixNanos.Load()
		if lastSendNanos == 0 {
			stalePublishers++
			continue
		}
		lastSendAt := time.Unix(0, lastSendNanos)
		lastSendAge := sampledAt.Sub(lastSendAt)
		if lastSendAge > 500*time.Millisecond {
			stalePublishers++
		}
		if lastSendAge > maxLastSendAge {
			maxLastSendAge = lastSendAge
			oldestPublisher = stats.publisherID
			oldestLastSendAt = lastSendAt
		}
	}
	fmt.Fprintf(
		os.Stderr,
		"m7h publisher send sample: role=harness at=%s elapsedMs=%d publishers=%d frames=%d tickLateOver50ms=%d tickLateOver1s=%d maxTickLateMs=%.3f staleOver500ms=%d maxLastSendAgeMs=%.3f oldestPublisher=%s oldestLastSendAt=%s\n",
		sampledAt.Format(time.RFC3339Nano),
		elapsed.Milliseconds(),
		len(publishers),
		frames,
		tickLateOver50ms,
		tickLateOver1s,
		float64(maxTickLateNanos)/float64(time.Millisecond),
		stalePublishers,
		float64(maxLastSendAge)/float64(time.Millisecond),
		oldestPublisher,
		oldestLastSendAt.Format(time.RFC3339Nano),
	)
	return frames, stalePublishers
}

func queueDepthPercentile(sortedDepths []int, percentile int) int {
	if len(sortedDepths) == 0 {
		return 0
	}
	index := (len(sortedDepths)*percentile+99)/100 - 1
	if index < 0 {
		index = 0
	}
	return sortedDepths[index]
}

func formatICECandidate(candidate webrtc.ICECandidateStats) string {
	return fmt.Sprintf("%s:%d/%s/%s", candidate.IP, candidate.Port, candidate.Protocol, candidate.CandidateType)
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
	m7hReceiveStats *m7hPublisherReceiveStats
	firstFrameReady chan struct{}
	firstFrameOnce  sync.Once
	rtpPacketsRead  atomic.Uint64

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
	h264Video  bool
	viewerPeer *webrtc.PeerConnection
	downTrack  *webrtc.TrackLocalStaticRTP
	sender     *webrtc.RTPSender

	mu               sync.RWMutex
	active           bool
	statsMu          sync.Mutex
	feedback         sfuFeedbackCounts
	rtpQueue         chan queuedRTP
	keyframeNeededAt atomic.Int64
	// retransmittedAt records, per RTP sequence number, when this
	// subscription last retransmitted it (NACK aggregation, M6-H
	// attempt 8). Owned by the nackWorker goroutine only — handleNACK's
	// sole caller since attempt 10 — so no lock guards it.
	retransmittedAt map[uint16]time.Time
	nackQueue       chan queuedNACK
	rtpQueueClosed  bool
	// nackQueueClosed records that nackQueue was closed; guarded by mu.
	nackQueueClosed    bool
	rtpQueueEnqueued   atomic.Uint64
	rtpQueueDropped    atomic.Uint64
	rtpIntentionalShed atomic.Uint64
	rtpWriteSucceeded  atomic.Uint64
}

type sfuRouter struct {
	mu                             sync.RWMutex
	publishers                     map[string]*webrtc.PeerConnection
	tracks                         map[sfuTrackKey]*sfuPublishedTrack
	viewers                        map[string]*sfuViewer
	feedbackSenderSSRC             uint32
	closed                         bool
	m7hPublisherReceiveStats       map[string]*m7hPublisherReceiveStats
	lastKeyframeRequestByPublisher map[string]time.Time
	forwardingErrors               []string
	rtpForwarded                   atomic.Uint64
	rtpQueueDropped                atomic.Uint64
	rtpIntentionalShed             atomic.Uint64
	rtpDropped                     atomic.Uint64
	rtpRecoveryNanos               atomic.Uint64
	rtpRecoverySamples             atomic.Uint64
	rtpRecoveryMaxNanos            atomic.Uint64
	rtpForwardNanos                atomic.Uint64
	rtpForwardSamples              atomic.Uint64
	rtpForwardBuckets              [rtpForwardLatencyBucketCount]atomic.Uint64
}

type queuedNACK struct {
	feedback   *rtcp.TransportLayerNack
	enqueuedAt time.Time
}

type queuedRTP struct {
	packet     *rtp.Packet
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
	logRTPPath         bool
	remoteSFU          *m7hRemoteSFUClient
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
	readTiming      *m7hRTPReadTiming
	errors          chan error
	received        chan struct{}
}

type m7hRTPReadTiming struct {
	calls        atomic.Uint64
	errorReturns atomic.Uint64
	totalNanos   atomic.Uint64
	maxNanos     atomic.Uint64
	buckets      [m7hReadDurationBucketCount]atomic.Uint64
}

type m7hRTPReadTimingSnapshot struct {
	calls        uint64
	errorReturns uint64
	totalNanos   uint64
	maxNanos     uint64
	buckets      [m7hReadDurationBucketCount]uint64
}

func (timing *m7hRTPReadTiming) record(duration time.Duration, err error) {
	nanos := uint64(duration)
	timing.calls.Add(1)
	timing.totalNanos.Add(nanos)
	if err != nil {
		timing.errorReturns.Add(1)
	}
	for previous := timing.maxNanos.Load(); nanos > previous; previous = timing.maxNanos.Load() {
		if timing.maxNanos.CompareAndSwap(previous, nanos) {
			break
		}
	}
	bucket := len(m7hReadDurationBuckets)
	for index, upperBound := range m7hReadDurationBuckets {
		if duration <= upperBound {
			bucket = index
			break
		}
	}
	timing.buckets[bucket].Add(1)
}

func (timing *m7hRTPReadTiming) snapshotAndReset() m7hRTPReadTimingSnapshot {
	var snapshot m7hRTPReadTimingSnapshot
	snapshot.calls = timing.calls.Swap(0)
	snapshot.errorReturns = timing.errorReturns.Swap(0)
	snapshot.totalNanos = timing.totalNanos.Swap(0)
	snapshot.maxNanos = timing.maxNanos.Swap(0)
	for index := range timing.buckets {
		snapshot.buckets[index] = timing.buckets[index].Swap(0)
	}
	return snapshot
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
	id               string
	key              sfuTrackKey
	client           *webrtc.PeerConnection
	capture          *sfuViewerCapture
	recorder         *LatencyRecorder
	socketConn       *packetReadCountingConn
	routerSocketConn *packetReadCountingConn
	candidatePairs   *candidatePairSnapshot
}

type peerNegotiationPair struct {
	name               string
	offerer            *webrtc.PeerConnection
	answerer           *webrtc.PeerConnection
	mediaSections      []string
	socketConn         *packetReadCountingConn
	answererSocketConn *packetReadCountingConn
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
		publishers:                     make(map[string]*webrtc.PeerConnection),
		tracks:                         make(map[sfuTrackKey]*sfuPublishedTrack),
		viewers:                        make(map[string]*sfuViewer),
		feedbackSenderSSRC:             senderSSRC,
		lastKeyframeRequestByPublisher: make(map[string]time.Time),
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
	r.mu.RLock()
	m7hReceiveStats := r.m7hPublisherReceiveStats[publisherID]
	r.mu.RUnlock()
	track := &sfuPublishedTrack{
		key:             key,
		remote:          remote,
		subscribers:     make(map[string]*sfuSubscription),
		m7hReceiveStats: m7hReceiveStats,
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
		h264Video:       source.remote.Codec().MimeType == webrtc.MimeTypeH264,
		viewerPeer:      viewer.peer,
		downTrack:       downTrack,
		sender:          sender,
		active:          true,
		retransmittedAt: make(map[uint16]time.Time),
		rtpQueue:        make(chan queuedRTP, sfuRTPQueueSize),
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

type m7hRemoteSFUClient struct {
	baseURL    string
	token      string
	httpClient *http.Client
	cmd        *exec.Cmd
	exited     chan struct{}
	exitMu     sync.Mutex
	exitErr    error
	closeOnce  sync.Once
	closeErr   error
}

type m7hRemoteSDPRequest struct {
	PublisherID string `json:"publisher_id"`
	Offer       string `json:"offer"`
}

type m7hRemoteViewerRequest struct {
	ViewerID                string      `json:"viewer_id"`
	Key                     sfuTrackKey `json:"key"`
	Offer                   string      `json:"offer"`
	CheckUnauthorizedAccess bool        `json:"check_unauthorized_access"`
}

type m7hRemoteSDPResponse struct {
	Answer                   string `json:"answer"`
	UnauthorizedAccessDenied bool   `json:"unauthorized_access_denied"`
}

type m7hRemoteReadyRequest struct {
	Key sfuTrackKey `json:"key"`
}

type m7hRemoteReadyResponse struct {
	LastSequence uint16 `json:"last_sequence"`
}

type m7hRemoteStatsRequest struct {
	ViewerIDs                []string `json:"viewer_ids"`
	IncludeICECandidatePairs bool     `json:"include_ice_candidate_pairs,omitempty"`
}

type m7hRemoteSFUStats struct {
	FeedbackByViewer            map[string]sfuFeedbackCounts `json:"feedback_by_viewer"`
	ICECandidatePairsByViewer   map[string]string            `json:"ice_candidate_pairs_by_viewer,omitempty"`
	RTPQueueDrops               uint64                       `json:"rtp_queue_drops"`
	RTPIntentionalShed          uint64                       `json:"rtp_intentional_shed"`
	RTPWriteErrors              uint64                       `json:"rtp_write_errors"`
	RTPKeyframeRecoverySamples  uint64                       `json:"rtp_keyframe_recovery_samples"`
	RTPKeyframeRecoveryNanos    uint64                       `json:"rtp_keyframe_recovery_nanos"`
	RTPKeyframeRecoveryMaxNanos uint64                       `json:"rtp_keyframe_recovery_max_nanos"`
	ForwardingErrors            []string                     `json:"forwarding_errors"`
	Sockets                     m7hRemoteSocketAggregates    `json:"socket_aggregates"`
}

// m7hRemoteReceiveStats is the SFU's last M7-H publisher receive sample
// (one second of packets + staleness), exposed for the harness-side
// starvation trigger. It reports the sampler's stored values, not a fresh
// counter read, so it never disturbs the sampler's drain.
type m7hRemoteReceiveStats struct {
	Publishers int    `json:"publishers"`
	Packets    uint64 `json:"packets"`
	Stale      int    `json:"stale"`
}

type m7hRemoteSocketAggregates struct {
	RouterSockets           int    `json:"router_sockets"`
	ClientSockets           int    `json:"client_sockets"`
	RouterWrites            uint64 `json:"router_writes"`
	RouterSTUNWrites        uint64 `json:"router_stun_writes"`
	RouterNonSTUNWrites     uint64 `json:"router_non_stun_writes"`
	ClientReads             uint64 `json:"client_reads"`
	ClientSTUNReads         uint64 `json:"client_stun_reads"`
	ClientNonSTUNReads      uint64 `json:"client_non_stun_reads"`
	ClientsZeroReads        uint64 `json:"clients_zero_reads"`
	ClientsZeroNonSTUNReads uint64 `json:"clients_zero_non_stun_reads"`
}

type m7hRemoteCleanupResponse struct {
	TracksRemaining         int  `json:"tracks_remaining"`
	ViewersRemaining        int  `json:"viewers_remaining"`
	SubscriptionsRemaining  int  `json:"subscriptions_remaining"`
	AuthorizationsRemaining int  `json:"authorizations_remaining"`
	CleanupVerified         bool `json:"cleanup_verified"`
}

type m7hRemoteViewerPair struct {
	viewerID                string
	key                     sfuTrackKey
	peer                    *webrtc.PeerConnection
	socketConn              *packetReadCountingConn
	checkUnauthorizedAccess bool
}

func startM7HRemoteSFU(ctx context.Context) (*m7hRemoteSFUClient, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("reserve loopback listener for M7-H SFU process: %w", err)
	}
	tcpListener, ok := listener.(*net.TCPListener)
	if !ok {
		_ = listener.Close()
		return nil, errors.New("M7-H SFU listener is not TCP")
	}
	listenerFile, err := tcpListener.File()
	if err != nil {
		_ = listener.Close()
		return nil, fmt.Errorf("duplicate M7-H SFU listener: %w", err)
	}
	address := listener.Addr().String()
	if err := listener.Close(); err != nil {
		_ = listenerFile.Close()
		return nil, fmt.Errorf("release parent M7-H SFU listener: %w", err)
	}
	var tokenBytes [32]byte
	if _, err := rand.Read(tokenBytes[:]); err != nil {
		_ = listenerFile.Close()
		return nil, fmt.Errorf("create M7-H loopback authorization token: %w", err)
	}
	executable, err := os.Executable()
	if err != nil {
		_ = listenerFile.Close()
		return nil, fmt.Errorf("locate M7-H harness executable: %w", err)
	}
	token := fmt.Sprintf("%x", tokenBytes[:])
	command := exec.CommandContext(
		ctx,
		executable,
		"-mode=m7h-sfu",
		"-m7h-sfu-token="+token,
	)
	command.ExtraFiles = []*os.File{listenerFile}
	command.Stdout = io.Discard
	var sfuLog *os.File
	if logPath := os.Getenv("M7H_SFU_LOG"); logPath != "" {
		sfuLog, err = os.OpenFile(logPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
		if err != nil {
			_ = listenerFile.Close()
			return nil, fmt.Errorf("open M7-H SFU process log %s: %w", logPath, err)
		}
		command.Stderr = sfuLog
	} else {
		command.Stderr = os.Stderr
	}
	if err := command.Start(); err != nil {
		_ = listenerFile.Close()
		if sfuLog != nil {
			_ = sfuLog.Close()
		}
		return nil, fmt.Errorf("start separate M7-H SFU process: %w", err)
	}
	_ = listenerFile.Close()
	if sfuLog != nil {
		_ = sfuLog.Close()
	}
	transport := &http.Transport{
		MaxIdleConns:        peerNegotiationConcurrency,
		MaxIdleConnsPerHost: peerNegotiationConcurrency,
		MaxConnsPerHost:     peerNegotiationConcurrency,
	}
	remote := &m7hRemoteSFUClient{
		baseURL:    "http://" + address,
		token:      token,
		httpClient: &http.Client{Transport: transport},
		cmd:        command,
		exited:     make(chan struct{}),
	}
	go func() {
		remote.exitMu.Lock()
		exitErr := command.Wait()
		remote.exitErr = exitErr
		remote.exitMu.Unlock()
		fmt.Fprintf(
			os.Stderr,
			"m7h split process exited: role=sfu pid=%d at=%s err=%v\n",
			command.Process.Pid,
			time.Now().Format(time.RFC3339Nano),
			exitErr,
		)
		close(remote.exited)
	}()
	fmt.Fprintf(os.Stderr, "m7h split process: role=harness pid=%d sfuPid=%d address=%s\n",
		os.Getpid(), command.Process.Pid, address)
	startupTimeout := time.NewTimer(30 * time.Second)
	defer startupTimeout.Stop()
	poll := time.NewTicker(100 * time.Millisecond)
	defer poll.Stop()
	for {
		if err := remote.request(ctx, http.MethodGet, "/health", nil, nil); err == nil {
			return remote, nil
		}
		select {
		case <-ctx.Done():
			_ = remote.Close()
			return nil, fmt.Errorf("wait for local M7-H SFU process: %w", ctx.Err())
		case <-remote.exited:
			return nil, fmt.Errorf("M7-H SFU process exited during startup: %w", remote.processError())
		case <-startupTimeout.C:
			_ = remote.Close()
			return nil, errors.New("M7-H SFU process did not become ready within 30 seconds")
		case <-poll.C:
		}
	}
}

func (remote *m7hRemoteSFUClient) processError() error {
	remote.exitMu.Lock()
	defer remote.exitMu.Unlock()
	return remote.exitErr
}

func (remote *m7hRemoteSFUClient) request(
	ctx context.Context,
	method string,
	path string,
	input any,
	output any,
) error {
	var body io.Reader
	if input != nil {
		encoded, err := json.Marshal(input)
		if err != nil {
			return fmt.Errorf("encode local SFU request %s: %w", path, err)
		}
		body = bytes.NewReader(encoded)
	}
	request, err := http.NewRequestWithContext(ctx, method, remote.baseURL+path, body)
	if err != nil {
		return fmt.Errorf("create local SFU request %s: %w", path, err)
	}
	request.Header.Set("Authorization", "Bearer "+remote.token)
	if input != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	response, err := remote.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("call local SFU endpoint %s: %w", path, err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		var errorBody struct {
			Error string `json:"error"`
		}
		_ = json.NewDecoder(io.LimitReader(response.Body, 1<<20)).Decode(&errorBody)
		if errorBody.Error == "" {
			errorBody.Error = response.Status
		}
		return fmt.Errorf("local SFU endpoint %s: %s", path, errorBody.Error)
	}
	if output != nil {
		if err := json.NewDecoder(io.LimitReader(response.Body, 32<<20)).Decode(output); err != nil {
			return fmt.Errorf("decode local SFU response %s: %w", path, err)
		}
	}
	return nil
}

func (remote *m7hRemoteSFUClient) captureHeapProfile(ctx context.Context, path string) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, remote.baseURL+"/heap-profile", nil)
	if err != nil {
		return fmt.Errorf("create local SFU heap-profile request: %w", err)
	}
	request.Header.Set("Authorization", "Bearer "+remote.token)
	response, err := remote.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("call local SFU heap-profile endpoint: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		body, readErr := io.ReadAll(io.LimitReader(response.Body, 1<<20))
		if readErr != nil {
			return fmt.Errorf("read local SFU heap-profile error (%s): %w", response.Status, readErr)
		}
		return fmt.Errorf("local SFU heap-profile endpoint: %s: %s", response.Status, strings.TrimSpace(string(body)))
	}
	profile, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create M7-H heap profile %s: %w", path, err)
	}
	_, copyErr := io.Copy(profile, response.Body)
	closeErr := profile.Close()
	if copyErr != nil {
		return errors.Join(fmt.Errorf("write M7-H heap profile %s: %w", path, copyErr), closeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close M7-H heap profile %s: %w", path, closeErr)
	}
	return nil
}

func (remote *m7hRemoteSFUClient) captureGoroutineProfile(ctx context.Context, path string) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, remote.baseURL+"/goroutine-profile", nil)
	if err != nil {
		return fmt.Errorf("create local SFU goroutine-profile request: %w", err)
	}
	request.Header.Set("Authorization", "Bearer "+remote.token)
	request.Header.Set("X-M7H-Goroutine-Profile-Path", path)
	requestStarted := time.Now()
	fmt.Fprintf(os.Stderr, "m7h SFU goroutine-profile request started: at=%s\n", requestStarted.Format(time.RFC3339Nano))
	trace := &httptrace.ClientTrace{
		GetConn: func(hostPort string) {
			fmt.Fprintf(os.Stderr, "m7h SFU profile client phase: phase=get-conn elapsed=%s target=%s\n", time.Since(requestStarted), hostPort)
		},
		GotConn: func(info httptrace.GotConnInfo) {
			fmt.Fprintf(
				os.Stderr,
				"m7h SFU profile client phase: phase=got-conn elapsed=%s reused=%t idle=%s local=%s remote=%s\n",
				time.Since(requestStarted),
				info.Reused,
				info.IdleTime,
				info.Conn.LocalAddr(),
				info.Conn.RemoteAddr(),
			)
		},
		WroteRequest: func(info httptrace.WroteRequestInfo) {
			fmt.Fprintf(os.Stderr, "m7h SFU profile client phase: phase=wrote-request elapsed=%s err=%v\n", time.Since(requestStarted), info.Err)
		},
		GotFirstResponseByte: func() {
			fmt.Fprintf(os.Stderr, "m7h SFU profile client phase: phase=first-response-byte elapsed=%s\n", time.Since(requestStarted))
		},
	}
	request = request.WithContext(httptrace.WithClientTrace(request.Context(), trace))
	profileTransport := &http.Transport{DisableKeepAlives: true}
	defer profileTransport.CloseIdleConnections()
	response, err := (&http.Client{Transport: profileTransport}).Do(request)
	if err != nil {
		return fmt.Errorf("call local SFU goroutine-profile endpoint after %s: %w", time.Since(requestStarted), err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusNoContent {
		body, readErr := io.ReadAll(io.LimitReader(response.Body, 1<<20))
		if readErr != nil {
			return fmt.Errorf("read local SFU goroutine-profile error (%s): %w", response.Status, readErr)
		}
		return fmt.Errorf("local SFU goroutine-profile endpoint: %s: %s", response.Status, strings.TrimSpace(string(body)))
	}
	profile, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("stat M7-H goroutine profile %s: %w", path, err)
	}
	if profile.Size() == 0 {
		return fmt.Errorf("local SFU goroutine-profile endpoint created an empty profile at %s", path)
	}
	fmt.Fprintf(os.Stderr, "m7h SFU goroutine-profile saved locally: path=%s bytes=%d elapsed=%s\n", path, profile.Size(), time.Since(requestStarted))
	return nil
}

func (remote *m7hRemoteSFUClient) captureCPUProfile(
	ctx context.Context,
	path string,
	duration time.Duration,
) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, remote.baseURL+"/cpu-profile", nil)
	if err != nil {
		return fmt.Errorf("create local SFU CPU-profile request: %w", err)
	}
	request.Header.Set("Authorization", "Bearer "+remote.token)
	request.Header.Set("X-M7H-CPU-Profile-Path", path)
	request.Header.Set("X-M7H-CPU-Profile-Duration", duration.String())
	response, err := remote.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("call local SFU CPU-profile endpoint: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusNoContent {
		body, readErr := io.ReadAll(io.LimitReader(response.Body, 1<<20))
		if readErr != nil {
			return fmt.Errorf("read local SFU CPU-profile error (%s): %w", response.Status, readErr)
		}
		return fmt.Errorf("local SFU CPU-profile endpoint: %s: %s", response.Status, strings.TrimSpace(string(body)))
	}
	info, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("stat M7-H SFU CPU profile %s: %w", path, err)
	}
	if info.Size() == 0 {
		return fmt.Errorf("local SFU CPU-profile endpoint created an empty profile at %s", path)
	}
	return nil
}

func writeM7HHeapProfile(path string) error {
	runtime.GC()
	profile := pprof.Lookup("heap")
	if profile == nil {
		return errors.New("Go heap profile is unavailable")
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create M7-H heap profile %s: %w", path, err)
	}
	writeErr := profile.WriteTo(file, 0)
	closeErr := file.Close()
	if writeErr != nil {
		return errors.Join(fmt.Errorf("write M7-H heap profile %s: %w", path, writeErr), closeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close M7-H heap profile %s: %w", path, closeErr)
	}
	return nil
}

func writeM7HGoroutineProfile(path string) error {
	profile := pprof.Lookup("goroutine")
	if profile == nil {
		return errors.New("Go goroutine profile is unavailable")
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create M7-H goroutine profile %s: %w", path, err)
	}
	writeErr := profile.WriteTo(file, 0)
	closeErr := file.Close()
	if writeErr != nil {
		return errors.Join(fmt.Errorf("write M7-H goroutine profile %s: %w", path, writeErr), closeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close M7-H goroutine profile %s: %w", path, closeErr)
	}
	return nil
}

func writeM7HCPUProfile(ctx context.Context, path string, duration time.Duration) error {
	if duration <= 0 || duration > m7hCPUProfileMaxWindow {
		return fmt.Errorf("M7-H CPU profile duration %s is outside (0, %s]", duration, m7hCPUProfileMaxWindow)
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create M7-H CPU profile %s: %w", path, err)
	}
	if err := file.Chmod(0o600); err != nil {
		return errors.Join(fmt.Errorf("restrict M7-H CPU profile %s: %w", path, err), file.Close())
	}
	if err := pprof.StartCPUProfile(file); err != nil {
		return errors.Join(fmt.Errorf("start M7-H CPU profile %s: %w", path, err), file.Close())
	}
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-timer.C:
	case <-ctx.Done():
	}
	pprof.StopCPUProfile()
	closeErr := file.Close()
	if err := ctx.Err(); err != nil {
		return errors.Join(fmt.Errorf("M7-H CPU profile %s ended early: %w", path, err), closeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close M7-H CPU profile %s: %w", path, closeErr)
	}
	info, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("stat M7-H CPU profile %s: %w", path, err)
	}
	if info.Size() == 0 {
		return fmt.Errorf("M7-H CPU profile %s is empty", path)
	}
	return nil
}

func isM7HTemporaryProfilePath(path string) bool {
	if !filepath.IsAbs(path) {
		return false
	}
	cleanPath := filepath.Clean(path)
	profileDir, err := filepath.EvalSymlinks(filepath.Dir(cleanPath))
	if err != nil {
		return false
	}
	if info, err := os.Lstat(cleanPath); err == nil {
		if !info.Mode().IsRegular() {
			return false
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return false
	}
	for _, root := range []string{os.TempDir(), "/tmp"} {
		resolvedRoot, err := filepath.EvalSymlinks(root)
		if err != nil {
			continue
		}
		relative, err := filepath.Rel(resolvedRoot, filepath.Join(profileDir, filepath.Base(cleanPath)))
		if err == nil && relative != "." && relative != ".." &&
			!strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
			return true
		}
	}
	return false
}

func captureM7HHeapProfiles(
	ctx context.Context,
	remote *m7hRemoteSFUClient,
	pathPrefix string,
	stage string,
) error {
	if err := writeM7HHeapProfile(pathPrefix + "-harness-" + stage + ".pprof"); err != nil {
		return err
	}
	if err := remote.captureHeapProfile(ctx, pathPrefix+"-sfu-"+stage+".pprof"); err != nil {
		return err
	}
	return nil
}

func captureM7HGoroutineProfiles(
	ctx context.Context,
	remote *m7hRemoteSFUClient,
	pathPrefix string,
	stage string,
) error {
	errs := make(chan error, 2)
	go func() {
		errs <- writeM7HGoroutineProfile(pathPrefix + "-harness-" + stage + ".pprof")
	}()
	go func() {
		errs <- remote.captureGoroutineProfile(ctx, pathPrefix+"-sfu-"+stage+".pprof")
	}()
	return errors.Join(<-errs, <-errs)
}

func captureM7HCPUProfiles(
	ctx context.Context,
	remote *m7hRemoteSFUClient,
	pathPrefix string,
	stage string,
) error {
	errs := make(chan error, 2)
	go func() {
		errs <- writeM7HCPUProfile(ctx, pathPrefix+"-harness-"+stage+".pprof", m7hCPUProfileWindow)
	}()
	go func() {
		errs <- remote.captureCPUProfile(ctx, pathPrefix+"-sfu-"+stage+".pprof", m7hCPUProfileWindow)
	}()
	return errors.Join(<-errs, <-errs)
}

func startM7HCPUProfileCapture(
	sendCtx context.Context,
	remote *m7hRemoteSFUClient,
	pathPrefix string,
) func() error {
	done := make(chan error, 1)
	go func() {
		timer := time.NewTimer(m7hCPUProfileDelay)
		defer timer.Stop()
		select {
		case <-timer.C:
		case <-sendCtx.Done():
			done <- fmt.Errorf("M7-H CPU profile window was not reached: %w", sendCtx.Err())
			return
		}
		profileCtx, cancel := context.WithTimeout(sendCtx, m7hCPUProfileMaxWindow+10*time.Second)
		defer cancel()
		err := captureM7HCPUProfiles(profileCtx, remote, pathPrefix, "streaming-30s")
		if err != nil {
			done <- fmt.Errorf("capture M7-H CPU profiles: %w", err)
			return
		}
		fmt.Fprintf(
			os.Stderr,
			"m7h CPU profiles captured: prefix=%s stage=streaming-30s window=%s\n",
			pathPrefix,
			m7hCPUProfileWindow,
		)
		done <- nil
	}()
	var waitOnce sync.Once
	var result error
	return func() error {
		waitOnce.Do(func() {
			result = <-done
		})
		return result
	}
}

type m7hSFUReceiveStallDetector struct {
	publisherCount int
	armed          bool
	starvedSamples int
}

func (detector *m7hSFUReceiveStallDetector) observe(packets uint64, stalePublishers int) bool {
	if packets > 0 {
		detector.armed = true
		detector.starvedSamples = 0
		return false
	}
	if !detector.armed || stalePublishers != detector.publisherCount {
		detector.starvedSamples = 0
		return false
	}
	detector.starvedSamples++
	return detector.starvedSamples >= 5
}

func (detector *m7hSFUReceiveStallDetector) observeDuringSend(
	ctx context.Context,
	packets uint64,
	stalePublishers int,
) bool {
	return ctx.Err() == nil && detector.observe(packets, stalePublishers)
}

func m7hPublisherSendStallDetected(
	ctx context.Context,
	publisherCount int,
	frames uint64,
	stalePublishers int,
) bool {
	return ctx.Err() == nil &&
		publisherCount == 3000 &&
		frames == 0 &&
		stalePublishers == publisherCount
}

func startM7HGoroutineProfileCapture(
	sendCtx context.Context,
	remote *m7hRemoteSFUClient,
	pathPrefix string,
	publisherCount int,
) (
	func(frames uint64, stalePublishers int),
	func(packets uint64, stalePublishers int),
	func(),
	func(),
) {
	var captureOnce sync.Once
	captureStarted := make(chan struct{})
	captureDone := make(chan struct{})
	startCapture := func(trigger, firstStage, secondStage string) {
		captureOnce.Do(func() {
			detectedAt := time.Now()
			profileCtx, cancelProfiles := context.WithCancel(context.Background())
			fmt.Fprintf(
				os.Stderr,
				"m7h goroutine profile capture triggered: reason=%s at=%s publishers=%d\n",
				trigger,
				detectedAt.Format(time.RFC3339Nano),
				publisherCount,
			)
			close(captureStarted)
			go func() {
				defer close(captureDone)
				defer cancelProfiles()
				capture := func(stage string) {
					captureCtx, cancel := context.WithTimeout(profileCtx, 5*time.Minute)
					defer cancel()
					if err := captureM7HGoroutineProfiles(captureCtx, remote, pathPrefix, stage); err != nil {
						fmt.Fprintf(os.Stderr, "m7h goroutine profile capture failed: stage=%s err=%v\n", stage, err)
						return
					}
					fmt.Fprintf(
						os.Stderr,
						"m7h goroutine profiles captured: prefix=%s stage=%s\n",
						pathPrefix,
						stage,
					)
				}
				capture(firstStage)
				timer := time.NewTimer(time.Until(detectedAt.Add(30 * time.Second)))
				defer timer.Stop()
				select {
				case <-timer.C:
					capture(secondStage)
				case <-profileCtx.Done():
					fmt.Fprintf(os.Stderr, "m7h second goroutine profile skipped: err=%v\n", profileCtx.Err())
				}
			}()
		})
	}
	onSample := func(frames uint64, stalePublishers int) {
		if !m7hPublisherSendStallDetected(sendCtx, publisherCount, frames, stalePublishers) {
			return
		}
		startCapture("harness-send-stall", "stall", "stall-plus-30s")
	}
	// onSFUReceiveSample fires the same paired capture from the SFU
	// receive sample (packets, stale) instead of the harness send sample.
	// It arms only after one sample with packets > 0, so the healthy
	// startup (all publishers stale, zero packets) cannot trigger it;
	// it requires a live send context, then counts consecutive starved
	// samples and fires at 5.
	sfuStallDetector := m7hSFUReceiveStallDetector{publisherCount: publisherCount}
	onSFUReceiveSample := func(packets uint64, stalePublishers int) {
		if !sfuStallDetector.observeDuringSend(sendCtx, packets, stalePublishers) {
			return
		}
		startCapture("sfu-receive-starvation", "stall", "stall-plus-30s")
	}
	beforeViewerReadinessAbort := func() {
		startCapture("viewer-readiness-abort", "before-viewer-readiness-abort", "viewer-readiness-abort-plus-30s")
	}
	wait := func() {
		select {
		case <-captureStarted:
			<-captureDone
		default:
		}
	}
	return onSample, onSFUReceiveSample, beforeViewerReadinessAbort, wait
}

// startM7HSFUReceivePoll polls the remote SFU's last publisher receive
// sample once a second and feeds it to onSample. It returns a stop func
// that halts the poll and waits for the poll goroutine to exit. When the
// SFU is local (remote == nil) or no callback is wired, it is a no-op.
func startM7HSFUReceivePoll(
	ctx context.Context,
	remote *m7hRemoteSFUClient,
	onSample func(packets uint64, stalePublishers int),
) func() {
	if remote == nil || onSample == nil {
		return func() {}
	}
	pollCtx, cancel := context.WithCancel(ctx)
	done := make(chan struct{})
	go func() {
		defer close(done)
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				stats, err := remote.receiveStats(pollCtx)
				if err != nil {
					fmt.Fprintf(os.Stderr, "m7h sfu receive stats poll failed: err=%v\n", err)
					continue
				}
				onSample(stats.Packets, stats.Stale)
			case <-pollCtx.Done():
				return
			}
		}
	}()
	return func() {
		cancel()
		<-done
	}
}

func (remote *m7hRemoteSFUClient) Close() error {
	remote.closeOnce.Do(func() {
		select {
		case <-remote.exited:
			remote.closeErr = remote.processError()
			return
		default:
		}
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := remote.request(ctx, http.MethodPost, "/shutdown", nil, nil); err != nil {
			remote.closeErr = errors.Join(remote.closeErr, err)
			if signalErr := remote.cmd.Process.Signal(os.Interrupt); signalErr != nil &&
				!errors.Is(signalErr, os.ErrProcessDone) {
				remote.closeErr = errors.Join(remote.closeErr, signalErr)
			}
		}
		select {
		case <-remote.exited:
			remote.closeErr = errors.Join(remote.closeErr, remote.processError())
		case <-ctx.Done():
			remote.closeErr = errors.Join(remote.closeErr, ctx.Err())
			if killErr := remote.cmd.Process.Kill(); killErr != nil &&
				!errors.Is(killErr, os.ErrProcessDone) {
				remote.closeErr = errors.Join(remote.closeErr, killErr)
			}
			<-remote.exited
			remote.closeErr = errors.Join(remote.closeErr, remote.processError())
		}
		remote.httpClient.CloseIdleConnections()
	})
	return remote.closeErr
}

func createM7HLocalOffer(ctx context.Context, peer *webrtc.PeerConnection) (string, error) {
	offer, err := peer.CreateOffer(nil)
	if err != nil {
		return "", fmt.Errorf("create local M7-H offer: %w", err)
	}
	gathered := webrtc.GatheringCompletePromise(peer)
	if err := peer.SetLocalDescription(offer); err != nil {
		return "", fmt.Errorf("set local M7-H offer: %w", err)
	}
	select {
	case <-gathered:
	case <-ctx.Done():
		return "", fmt.Errorf("gather local M7-H offer ICE candidates: %w", ctx.Err())
	}
	local := peer.LocalDescription()
	if local == nil {
		return "", errors.New("local M7-H offer is missing after ICE gathering")
	}
	return local.SDP, nil
}

func (remote *m7hRemoteSFUClient) negotiatePublisher(
	ctx context.Context,
	publisherID string,
	peer *webrtc.PeerConnection,
) error {
	offerCtx, cancel := context.WithTimeout(ctx, peerPairNegotiationTimeout)
	defer cancel()
	offer, err := createM7HLocalOffer(offerCtx, peer)
	if err != nil {
		return err
	}
	var response m7hRemoteSDPResponse
	if err := remote.request(offerCtx, http.MethodPost, "/publisher", m7hRemoteSDPRequest{
		PublisherID: publisherID,
		Offer:       offer,
	}, &response); err != nil {
		return err
	}
	if err := peer.SetRemoteDescription(webrtc.SessionDescription{
		Type: webrtc.SDPTypeAnswer,
		SDP:  response.Answer,
	}); err != nil {
		return fmt.Errorf("set M7-H router publisher answer for %s: %w", publisherID, err)
	}
	if err := waitForConnected(offerCtx, peer, peer); err != nil {
		return fmt.Errorf("wait for remote publisher %s connection: %w", publisherID, err)
	}
	return nil
}

func (remote *m7hRemoteSFUClient) negotiatePublishers(
	ctx context.Context,
	publisherIDs []string,
	peers map[string]*webrtc.PeerConnection,
) error {
	type outcome struct {
		publisherID string
		err         error
	}
	workCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	jobs := make(chan string)
	outcomes := make(chan outcome, len(publisherIDs))
	workers := min(peerNegotiationConcurrency, len(publisherIDs))
	var workerWG sync.WaitGroup
	for range workers {
		workerWG.Add(1)
		go func() {
			defer workerWG.Done()
			for publisherID := range jobs {
				err := remote.negotiatePublisher(workCtx, publisherID, peers[publisherID])
				outcomes <- outcome{publisherID: publisherID, err: err}
				if err != nil {
					cancel()
				}
			}
		}()
	}
	go func() {
		defer close(jobs)
		for _, publisherID := range publisherIDs {
			select {
			case jobs <- publisherID:
			case <-workCtx.Done():
				return
			}
		}
	}()
	workerWG.Wait()
	close(outcomes)
	var errs []error
	for result := range outcomes {
		if result.err != nil {
			errs = append(errs, fmt.Errorf("negotiate publisher %s: %w", result.publisherID, result.err))
		}
	}
	return errors.Join(errs...)
}

func (remote *m7hRemoteSFUClient) waitForFirstFrame(
	ctx context.Context,
	key sfuTrackKey,
) (uint16, error) {
	requestCtx, cancel := context.WithTimeout(ctx, peerPairNegotiationTimeout)
	defer cancel()
	var response m7hRemoteReadyResponse
	if err := remote.request(requestCtx, http.MethodPost, "/publisher/ready",
		m7hRemoteReadyRequest{Key: key}, &response); err != nil {
		return 0, err
	}
	return response.LastSequence, nil
}

func (remote *m7hRemoteSFUClient) negotiateViewers(
	ctx context.Context,
	pairs []m7hRemoteViewerPair,
) (map[string]bool, error) {
	type outcome struct {
		viewerID string
		denied   bool
		err      error
	}
	workCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	jobs := make(chan m7hRemoteViewerPair)
	outcomes := make(chan outcome, len(pairs))
	workers := min(peerNegotiationConcurrency, len(pairs))
	var workerWG sync.WaitGroup
	for range workers {
		workerWG.Add(1)
		go func() {
			defer workerWG.Done()
			for pair := range jobs {
				requestCtx, requestCancel := context.WithTimeout(workCtx, peerPairNegotiationTimeout)
				negotiationStarted := time.Now()
				phase := "create-offer"
				phaseStarted := time.Now()
				offer, err := createM7HLocalOffer(requestCtx, pair.peer)
				offerDuration := time.Since(phaseStarted)
				var requestDuration, answerDuration, connectDuration time.Duration
				var response m7hRemoteSDPResponse
				if err == nil {
					phase = "post-viewer"
					phaseStarted = time.Now()
					err = remote.request(requestCtx, http.MethodPost, "/viewer", m7hRemoteViewerRequest{
						ViewerID:                pair.viewerID,
						Key:                     pair.key,
						Offer:                   offer,
						CheckUnauthorizedAccess: pair.checkUnauthorizedAccess,
					}, &response)
					requestDuration = time.Since(phaseStarted)
				}
				if err == nil {
					phase = "set-answer"
					phaseStarted = time.Now()
					err = pair.peer.SetRemoteDescription(webrtc.SessionDescription{
						Type: webrtc.SDPTypeAnswer,
						SDP:  response.Answer,
					})
					answerDuration = time.Since(phaseStarted)
					if err != nil {
						err = fmt.Errorf("set M7-H router viewer answer for %s: %w", pair.viewerID, err)
					}
				}
				if err == nil {
					phase = "wait-connected"
					phaseStarted = time.Now()
					if connectErr := waitForConnected(requestCtx, pair.peer, pair.peer); connectErr != nil {
						err = fmt.Errorf("wait for remote viewer %s connection: %w", pair.viewerID, connectErr)
					}
					connectDuration = time.Since(phaseStarted)
				}
				requestCancel()
				outcomes <- outcome{viewerID: pair.viewerID, denied: response.UnauthorizedAccessDenied, err: err}
				if err != nil {
					cancel()
					if !errors.Is(err, context.Canceled) {
						if phase == "wait-connected" && errors.Is(err, context.DeadlineExceeded) {
							offerCandidates := strings.Count(offer, "candidate:")
							answerCandidates := strings.Count(response.Answer, "candidate:")
							fmt.Fprintf(os.Stderr,
								"m7h remote viewer ICE diagnostics: viewer=%s connection=%s ice=%s gathering=%s offerCandidates=%d answerCandidates=%d candidatePairs=[%s]\n",
								pair.viewerID,
								pair.peer.ConnectionState(),
								pair.peer.ICEConnectionState(),
								pair.peer.ICEGatheringState(),
								offerCandidates,
								answerCandidates,
								iceCandidatePairDiagnostics(pair.peer),
							)
							if conn := pair.socketConn; conn != nil {
								fmt.Fprintf(os.Stderr,
									"m7h remote viewer client socket snapshot: viewer=%s local=%s reads=%d readSTUN=%d readNonSTUN=%d readReq=%d readResp=%d writes=%d writeSTUN=%d writeNonSTUN=%d writeReq=%d writeResp=%d bytesWritten=%d\n",
									pair.viewerID,
									conn.LocalAddr(),
									conn.packetsRead.Load(),
									conn.stunPacketsRead.Load(),
									conn.nonSTUNPacketsRead.Load(),
									conn.stunReqRead.Load(),
									conn.stunRespRead.Load(),
									conn.packetsWritten.Load(),
									conn.stunPacketsWritten.Load(),
									conn.nonSTUNPacketsWritten.Load(),
									conn.stunReqWritten.Load(),
									conn.stunRespWritten.Load(),
									conn.bytesWritten.Load(),
								)
							}
							statsCtx, cancelStats := context.WithTimeout(context.Background(), 2*time.Second)
							sfuStats, statsErr := remote.stats(statsCtx, []string{pair.viewerID}, true)
							cancelStats()
							if statsErr != nil {
								fmt.Fprintf(os.Stderr,
									"m7h remote viewer SFU stats failed: viewer=%s err=%v\n",
									pair.viewerID,
									statsErr,
								)
							} else {
								fmt.Fprintf(os.Stderr,
									"m7h remote viewer SFU stats: viewer=%s sockets=%+v candidatePairs=%q\n",
									pair.viewerID,
									sfuStats.Sockets,
									sfuStats.ICECandidatePairsByViewer[pair.viewerID],
								)
							}
						}
						fmt.Fprintf(os.Stderr,
							"m7h remote viewer negotiation failed: viewer=%s phase=%s elapsedMs=%d offerMs=%d requestMs=%d setAnswerMs=%d connectMs=%d err=%v\n",
							pair.viewerID,
							phase,
							time.Since(negotiationStarted).Milliseconds(),
							offerDuration.Milliseconds(),
							requestDuration.Milliseconds(),
							answerDuration.Milliseconds(),
							connectDuration.Milliseconds(),
							err,
						)
					}
				} else if elapsed := time.Since(negotiationStarted); elapsed >= time.Second {
					fmt.Fprintf(os.Stderr,
						"m7h remote viewer negotiation slow: viewer=%s elapsedMs=%d offerMs=%d requestMs=%d setAnswerMs=%d connectMs=%d\n",
						pair.viewerID,
						elapsed.Milliseconds(),
						offerDuration.Milliseconds(),
						requestDuration.Milliseconds(),
						answerDuration.Milliseconds(),
						connectDuration.Milliseconds(),
					)
				}
			}
		}()
	}
	go func() {
		defer close(jobs)
		for _, pair := range pairs {
			select {
			case jobs <- pair:
			case <-workCtx.Done():
				return
			}
		}
	}()
	workerWG.Wait()
	close(outcomes)
	unauthorizedDenied := make(map[string]bool, len(pairs))
	var errs []error
	for outcome := range outcomes {
		if outcome.err != nil {
			errs = append(errs, fmt.Errorf("negotiate remote viewer %s: %w", outcome.viewerID, outcome.err))
			continue
		}
		unauthorizedDenied[outcome.viewerID] = outcome.denied
	}
	return unauthorizedDenied, errors.Join(errs...)
}

func (remote *m7hRemoteSFUClient) stats(
	ctx context.Context,
	viewerIDs []string,
	includeICECandidatePairs bool,
) (m7hRemoteSFUStats, error) {
	var stats m7hRemoteSFUStats
	err := remote.request(ctx, http.MethodPost, "/stats", m7hRemoteStatsRequest{
		ViewerIDs:                viewerIDs,
		IncludeICECandidatePairs: includeICECandidatePairs,
	}, &stats)
	return stats, err
}

func (remote *m7hRemoteSFUClient) receiveStats(
	ctx context.Context,
) (m7hRemoteReceiveStats, error) {
	var stats m7hRemoteReceiveStats
	err := remote.request(ctx, http.MethodGet, "/receive-stats", nil, &stats)
	return stats, err
}

func (remote *m7hRemoteSFUClient) cleanup(ctx context.Context) (m7hRemoteCleanupResponse, error) {
	var response m7hRemoteCleanupResponse
	err := remote.request(ctx, http.MethodPost, "/cleanup", nil, &response)
	return response, err
}

type m7hRemotePublisherState struct {
	peer  *webrtc.PeerConnection
	shard int
}

type m7hRemoteSFUServer struct {
	router          *sfuRouter
	apis            []*webrtc.API
	muxes           []ice.UDPMux
	muxByShard      []ice.UDPMux
	settingsByShard []webrtc.SettingEngine
	mu              sync.RWMutex
	// Last M7-H publisher receive sample (written by
	// startM7HPublisherReceiveSampler, read by handleReceiveStats).
	// Guarded by mu.
	recvPublishers     int
	recvPackets        uint64
	recvStale          int
	publishers         map[string]m7hRemotePublisherState
	viewers            map[string]viewerEndpoint
	nextPublisherShard int
	httpServer         *http.Server
}

func runM7HSFUServer(token string) (returnErr error) {
	listenerFile := os.NewFile(3, "m7h-sfu-listener")
	if listenerFile == nil {
		return errors.New("inherited M7-H loopback listener is missing")
	}
	listener, err := net.FileListener(listenerFile)
	if closeErr := listenerFile.Close(); closeErr != nil {
		return errors.Join(err, fmt.Errorf("close inherited M7-H listener descriptor: %w", closeErr))
	}
	if err != nil {
		return fmt.Errorf("adopt inherited M7-H loopback listener: %w", err)
	}
	shardCount := min(peerNegotiationConcurrency, 3000)
	server := &m7hRemoteSFUServer{
		apis:            make([]*webrtc.API, shardCount),
		muxes:           make([]ice.UDPMux, 0, shardCount),
		muxByShard:      make([]ice.UDPMux, shardCount),
		settingsByShard: make([]webrtc.SettingEngine, shardCount),
		publishers:      make(map[string]m7hRemotePublisherState, 3000),
		viewers:         make(map[string]viewerEndpoint, 3000),
	}
	defer func() {
		if server.router != nil {
			if closeErr := server.router.close(); closeErr != nil {
				returnErr = errors.Join(returnErr, closeErr)
			}
		}
		for _, mux := range server.muxes {
			if closeErr := mux.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close M7-H SFU shard mux: %w", closeErr))
			}
		}
		if closeErr := listener.Close(); closeErr != nil && !errors.Is(closeErr, net.ErrClosed) {
			returnErr = errors.Join(returnErr, fmt.Errorf("close M7-H SFU listener: %w", closeErr))
		}
	}()
	clientSocketReadBufferBytes, err := strconv.Atoi(clientSocketReadBufferSize)
	if err != nil {
		return fmt.Errorf("parse M7-H router receive buffer size %q: %w", clientSocketReadBufferSize, err)
	}
	for shard := 0; shard < shardCount; shard++ {
		settings, mux, settingsErr := loopbackSettings(routerUDPMuxMode == "enabled", clientSocketReadBufferBytes)
		if settingsErr != nil {
			return fmt.Errorf("configure M7-H router shard %d: %w", shard, settingsErr)
		}
		server.settingsByShard[shard] = settings
		server.muxByShard[shard] = mux
		server.apis[shard] = webrtc.NewAPI(webrtc.WithSettingEngine(settings))
		if mux != nil {
			server.muxes = append(server.muxes, mux)
		}
	}
	server.router, err = newSFURouter(server.apis[0])
	if err != nil {
		return err
	}
	server.router.m7hPublisherReceiveStats = make(map[string]*m7hPublisherReceiveStats, 3000)
	stopRuntimeProbe := startM7HRuntimeProbe("sfu", nil, nil)
	defer stopRuntimeProbe()
	stopPublisherReceiveSampler := startM7HPublisherReceiveSampler(server)
	defer stopPublisherReceiveSampler()
	mux := http.NewServeMux()
	mux.HandleFunc("/health", server.handleHealth(token))
	mux.HandleFunc("/publisher", server.handlePublisher(token))
	mux.HandleFunc("/publisher/ready", server.handlePublisherReady(token))
	mux.HandleFunc("/viewer", server.handleViewer(token))
	mux.HandleFunc("/stats", server.handleStats(token))
	mux.HandleFunc("/receive-stats", server.handleReceiveStats(token))
	mux.HandleFunc("/heap-profile", server.handleHeapProfile(token))
	mux.HandleFunc("/goroutine-profile", server.handleGoroutineProfile(token))
	mux.HandleFunc("/cpu-profile", server.handleCPUProfile(token))
	mux.HandleFunc("/cleanup", server.handleCleanup(token))
	mux.HandleFunc("/shutdown", server.handleShutdown(token))
	server.httpServer = &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}
	fmt.Fprintf(os.Stderr, "m7h split process: role=sfu pid=%d address=%s muxShards=%d\n",
		os.Getpid(), listener.Addr().String(), shardCount)
	serveErr := server.httpServer.Serve(listener)
	fmt.Fprintf(os.Stderr, "m7h SFU HTTP serve returned: at=%s err=%v\n", time.Now().Format(time.RFC3339Nano), serveErr)
	if serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
		return fmt.Errorf("serve M7-H loopback signaling: %w", serveErr)
	}
	return nil
}

func (server *m7hRemoteSFUServer) authorized(w http.ResponseWriter, r *http.Request, token string) bool {
	if r.Header.Get("Authorization") == "Bearer "+token {
		return true
	}
	writeM7HJSONError(w, http.StatusUnauthorized, errors.New("unauthorized local M7-H request"))
	return false
}

func (server *m7hRemoteSFUServer) handleHealth(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		writeM7HJSON(w, http.StatusOK, map[string]string{"status": "ready"})
	}
}

func decodeM7HJSON(w http.ResponseWriter, r *http.Request, target any) error {
	r.Body = http.MaxBytesReader(w, r.Body, 4<<20)
	if err := json.NewDecoder(r.Body).Decode(target); err != nil {
		return fmt.Errorf("decode local M7-H request: %w", err)
	}
	return nil
}

func writeM7HJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		fmt.Fprintf(os.Stderr, "write M7-H loopback response: %v\n", err)
	}
}

func writeM7HJSONError(w http.ResponseWriter, status int, err error) {
	writeM7HJSON(w, status, map[string]string{"error": err.Error()})
}

func (server *m7hRemoteSFUServer) handlePublisher(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		var request m7hRemoteSDPRequest
		if err := decodeM7HJSON(w, r, &request); err != nil {
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		if request.PublisherID == "" || request.Offer == "" {
			writeM7HJSONError(w, http.StatusBadRequest, errors.New("publisher ID and SDP offer are required"))
			return
		}
		server.mu.Lock()
		if _, exists := server.publishers[request.PublisherID]; exists {
			server.mu.Unlock()
			writeM7HJSONError(w, http.StatusConflict, fmt.Errorf("publisher %q already exists", request.PublisherID))
			return
		}
		shard := server.nextPublisherShard % len(server.apis)
		server.nextPublisherShard++
		server.publishers[request.PublisherID] = m7hRemotePublisherState{shard: shard}
		receiveStats := &m7hPublisherReceiveStats{
			publisherID: request.PublisherID,
		}
		server.mu.Unlock()
		server.router.mu.Lock()
		server.router.m7hPublisherReceiveStats[request.PublisherID] = receiveStats
		server.router.mu.Unlock()
		peer, err := server.router.registerPublisher(server.apis[shard], request.PublisherID)
		if err != nil {
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		attachPCStateLogging(peer, "router-publisherPeer", request.PublisherID)
		server.mu.Lock()
		state := server.publishers[request.PublisherID]
		state.peer = peer
		server.publishers[request.PublisherID] = state
		server.mu.Unlock()
		answer, err := answerM7HRemoteOffer(r.Context(), peer, request.Offer)
		if err != nil {
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		writeM7HJSON(w, http.StatusOK, m7hRemoteSDPResponse{Answer: answer})
	}
}

func answerM7HRemoteOffer(
	ctx context.Context,
	peer *webrtc.PeerConnection,
	sdp string,
) (string, error) {
	if err := peer.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeOffer, SDP: sdp}); err != nil {
		return "", fmt.Errorf("set remote M7-H offer: %w", err)
	}
	answer, err := peer.CreateAnswer(nil)
	if err != nil {
		return "", fmt.Errorf("create M7-H answer: %w", err)
	}
	gathered := webrtc.GatheringCompletePromise(peer)
	if err := peer.SetLocalDescription(answer); err != nil {
		return "", fmt.Errorf("set local M7-H answer: %w", err)
	}
	select {
	case <-gathered:
	case <-ctx.Done():
		return "", fmt.Errorf("gather M7-H answer ICE candidates: %w", ctx.Err())
	}
	local := peer.LocalDescription()
	if local == nil {
		return "", errors.New("local M7-H answer is missing after ICE gathering")
	}
	return local.SDP, nil
}

func (server *m7hRemoteSFUServer) handlePublisherReady(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		var request m7hRemoteReadyRequest
		if err := decodeM7HJSON(w, r, &request); err != nil {
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		key := request.Key
		if key.PublisherID == "" || key.TrackID == "" {
			writeM7HJSONError(w, http.StatusBadRequest, errors.New("publisher and track identity are required"))
			return
		}
		if err := server.router.waitForTracks(r.Context(), []sfuMediaSource{{key: key}}); err != nil {
			writeM7HJSONError(w, http.StatusRequestTimeout, err)
			return
		}
		lastSequence, err := server.router.waitForFirstFrame(r.Context(), key)
		if err != nil {
			writeM7HJSONError(w, http.StatusRequestTimeout, err)
			return
		}
		writeM7HJSON(w, http.StatusOK, m7hRemoteReadyResponse{LastSequence: lastSequence})
	}
}

func (server *m7hRemoteSFUServer) handleViewer(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		requestStarted := time.Now()
		viewerID := ""
		phase := "authorize"
		phaseStarted := requestStarted
		slowestPhase := phase
		slowestPhaseDuration := time.Duration(0)
		finishPhase := func() {
			if duration := time.Since(phaseStarted); duration > slowestPhaseDuration {
				slowestPhase = phase
				slowestPhaseDuration = duration
			}
		}
		setPhase := func(name string) {
			finishPhase()
			phase = name
			phaseStarted = time.Now()
		}
		defer func() {
			finishPhase()
			elapsed := time.Since(requestStarted)
			if elapsed >= time.Second {
				fmt.Fprintf(os.Stderr,
					"m7h remote viewer handler slow: viewer=%s slowestPhase=%s slowestPhaseMs=%d elapsedMs=%d\n",
					viewerID,
					slowestPhase,
					slowestPhaseDuration.Milliseconds(),
					elapsed.Milliseconds(),
				)
			}
		}()
		if !server.authorized(w, r, token) {
			return
		}
		setPhase("decode")
		var request m7hRemoteViewerRequest
		if err := decodeM7HJSON(w, r, &request); err != nil {
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		viewerID = request.ViewerID
		if request.ViewerID == "" || request.Key.PublisherID == "" ||
			request.Key.TrackID == "" || request.Offer == "" {
			writeM7HJSONError(w, http.StatusBadRequest, errors.New("viewer, track identity, and SDP offer are required"))
			return
		}
		setPhase("wait-tracks")
		if err := server.router.waitForTracks(r.Context(), []sfuMediaSource{{key: request.Key}}); err != nil {
			writeM7HJSONError(w, http.StatusRequestTimeout, err)
			return
		}
		setPhase("lookup-publisher")
		server.mu.RLock()
		publisher, exists := server.publishers[request.Key.PublisherID]
		server.mu.RUnlock()
		if !exists {
			writeM7HJSONError(w, http.StatusNotFound, fmt.Errorf("publisher %s is not registered", request.Key.PublisherID))
			return
		}
		setPhase("create-peer")
		var routerSocketConn *packetReadCountingConn
		routerPeerAPI := server.apis[publisher.shard]
		if routerSocketWriteMode == "enabled" {
			sharedMux := server.muxByShard[publisher.shard]
			if sharedMux != nil {
				socketMux := newCountingUDPMux(sharedMux)
				settings := server.settingsByShard[publisher.shard]
				settings.SetICEUDPMux(socketMux)
				routerPeerAPI = webrtc.NewAPI(webrtc.WithSettingEngine(settings))
				routerSocketConn = socketMux.conn
				routerSocketConn.role = fmt.Sprintf("router-shard-%d:%s", publisher.shard, request.ViewerID)
			} else {
				socketMux, err := newSinglePeerUDPMux()
				if err != nil {
					writeM7HJSONError(w, http.StatusInternalServerError, err)
					return
				}
				settings, _, settingsErr := loopbackSettings(false, clientSocketReadBufferBytesValue())
				if settingsErr != nil {
					_ = socketMux.Close()
					writeM7HJSONError(w, http.StatusInternalServerError, settingsErr)
					return
				}
				settings.SetICEUDPMux(socketMux)
				routerPeerAPI = webrtc.NewAPI(webrtc.WithSettingEngine(settings))
				routerSocketConn = socketMux.conn
				routerSocketConn.role = "router-single:" + request.ViewerID
				server.mu.Lock()
				server.muxes = append(server.muxes, socketMux)
				server.mu.Unlock()
			}
			routerSocketConn.pcKey = "router-serverPeer:" + request.ViewerID
		}
		serverPeer, err := routerPeerAPI.NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			writeM7HJSONError(w, http.StatusInternalServerError, err)
			return
		}
		attachPCStateLogging(serverPeer, "router-serverPeer", request.ViewerID)
		setPhase("register-subscribe")
		if err := server.router.registerViewer(request.ViewerID, serverPeer); err != nil {
			_ = serverPeer.Close()
			writeM7HJSONError(w, http.StatusConflict, err)
			return
		}
		unauthorizedDenied := false
		if request.CheckUnauthorizedAccess {
			if err := server.router.subscribe(request.ViewerID, request.Key); !errors.Is(err, errSFUUnauthorized) {
				_ = server.router.removeViewer(request.ViewerID)
				writeM7HJSONError(w, http.StatusInternalServerError,
					fmt.Errorf("unauthorized subscription was not denied: %v", err))
				return
			}
			unauthorizedDenied = true
		}
		if err := server.router.authorizeSubscription(request.ViewerID, request.Key); err != nil {
			_ = server.router.removeViewer(request.ViewerID)
			writeM7HJSONError(w, http.StatusInternalServerError, err)
			return
		}
		if err := server.router.subscribe(request.ViewerID, request.Key); err != nil {
			_ = server.router.removeViewer(request.ViewerID)
			writeM7HJSONError(w, http.StatusInternalServerError, err)
			return
		}
		setPhase("answer-gather")
		answer, err := answerM7HRemoteOffer(r.Context(), serverPeer, request.Offer)
		if err != nil {
			_ = server.router.unsubscribe(request.ViewerID, request.Key)
			_ = server.router.removeViewer(request.ViewerID)
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		server.mu.Lock()
		if _, exists := server.viewers[request.ViewerID]; exists {
			server.mu.Unlock()
			_ = server.router.unsubscribe(request.ViewerID, request.Key)
			_ = server.router.removeViewer(request.ViewerID)
			writeM7HJSONError(w, http.StatusConflict, fmt.Errorf("viewer %q already exists", request.ViewerID))
			return
		}
		server.viewers[request.ViewerID] = viewerEndpoint{
			id:               request.ViewerID,
			key:              request.Key,
			routerSocketConn: routerSocketConn,
		}
		server.mu.Unlock()
		setPhase("write-response")
		writeM7HJSON(w, http.StatusOK, m7hRemoteSDPResponse{
			Answer:                   answer,
			UnauthorizedAccessDenied: unauthorizedDenied,
		})
	}
}

func clientSocketReadBufferBytesValue() int {
	value, _ := strconv.Atoi(clientSocketReadBufferSize)
	return value
}

func (server *m7hRemoteSFUServer) handleStats(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		if r.Context().Err() != nil {
			return
		}
		var request m7hRemoteStatsRequest
		if err := decodeM7HJSON(w, r, &request); err != nil {
			writeM7HJSONError(w, http.StatusBadRequest, err)
			return
		}
		if r.Context().Err() != nil {
			return
		}
		statsStarted := time.Now()
		fmt.Fprintf(os.Stderr, "m7h SFU stats request: phase=accepted at=%s viewers=%d includeCandidatePairs=%t\n",
			statsStarted.Format(time.RFC3339Nano), len(request.ViewerIDs), request.IncludeICECandidatePairs)
		viewersStarted := time.Now()
		server.mu.RLock()
		viewers := make([]viewerEndpoint, 0, len(server.viewers))
		var missingViewerID string
		missingViewer := false
		for _, viewerID := range request.ViewerIDs {
			viewer, exists := server.viewers[viewerID]
			if !exists {
				missingViewerID = viewerID
				missingViewer = true
				break
			}
			viewers = append(viewers, viewer)
		}
		server.mu.RUnlock()
		fmt.Fprintf(os.Stderr, "m7h SFU stats request: phase=viewer-map-snapshot at=%s elapsedMs=%d viewers=%d contextErr=%v\n",
			time.Now().Format(time.RFC3339Nano), time.Since(viewersStarted).Milliseconds(), len(viewers), r.Context().Err())
		if missingViewer {
			writeM7HJSONError(w, http.StatusNotFound, fmt.Errorf("viewer %s is not registered", missingViewerID))
			return
		}
		if r.Context().Err() != nil {
			return
		}
		feedbackStarted := time.Now()
		feedback := make(map[string]sfuFeedbackCounts, len(viewers))
		for _, viewer := range viewers {
			if r.Context().Err() != nil {
				return
			}
			feedback[viewer.id] = server.router.subscriptionFeedback(viewer.id, viewer.key)
		}
		fmt.Fprintf(os.Stderr, "m7h SFU stats request: phase=feedback-snapshot at=%s elapsedMs=%d viewers=%d contextErr=%v\n",
			time.Now().Format(time.RFC3339Nano), time.Since(feedbackStarted).Milliseconds(), len(viewers), r.Context().Err())
		if r.Context().Err() != nil {
			return
		}
		if request.IncludeICECandidatePairs {
			for _, viewer := range viewers {
				fmt.Fprintf(os.Stderr,
					"m7h SFU stats viewer: id=%s track=%s feedback=%+v\n",
					viewer.id, viewer.key.TrackID, feedback[viewer.id])
			}
		}
		if r.Context().Err() != nil {
			return
		}
		logRouterFeedbackDiagnosis(server.router, viewers)
		if r.Context().Err() != nil {
			return
		}
		var candidatePairs map[string]string
		if request.IncludeICECandidatePairs {
			candidatePairs = make(map[string]string, len(viewers))
			for _, viewer := range viewers {
				if r.Context().Err() != nil {
					return
				}
				if peer := server.router.viewerPeer(viewer.id); peer != nil {
					pairs := iceCandidatePairDiagnostics(peer)
					candidatePairs[viewer.id] = pairs
					fmt.Fprintf(os.Stderr, "m7h SFU stats candidate pairs: viewer=%s pairs=[%s]\n",
						viewer.id, pairs)
				}
			}
		}
		stats := m7hRemoteSFUStats{
			FeedbackByViewer:            feedback,
			ICECandidatePairsByViewer:   candidatePairs,
			RTPQueueDrops:               server.router.rtpQueueDropped.Load(),
			RTPIntentionalShed:          server.router.rtpIntentionalShed.Load(),
			RTPWriteErrors:              server.router.rtpDropped.Load(),
			RTPKeyframeRecoverySamples:  server.router.rtpRecoverySamples.Load(),
			RTPKeyframeRecoveryNanos:    server.router.rtpRecoveryNanos.Load(),
			RTPKeyframeRecoveryMaxNanos: server.router.rtpRecoveryMaxNanos.Load(),
			ForwardingErrors:            server.router.errorsSnapshot(),
			Sockets:                     remoteSocketAggregates(viewers),
		}
		writeM7HJSON(w, http.StatusOK, stats)
	}
}

// handleReceiveStats returns the SFU's last M7-H publisher receive sample
// (one second of packets + staleness). It does no feedback work and logs
// nothing, so the harness can poll it once a second during the run.
func (server *m7hRemoteSFUServer) handleReceiveStats(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			writeM7HJSONError(w, http.StatusMethodNotAllowed, errors.New("receive stats requires GET"))
			return
		}
		server.mu.RLock()
		stats := m7hRemoteReceiveStats{
			Publishers: server.recvPublishers,
			Packets:    server.recvPackets,
			Stale:      server.recvStale,
		}
		server.mu.RUnlock()
		writeM7HJSON(w, http.StatusOK, stats)
	}
}

func (server *m7hRemoteSFUServer) handleHeapProfile(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			writeM7HJSONError(w, http.StatusMethodNotAllowed, errors.New("heap profile requires GET"))
			return
		}
		runtime.GC()
		profile := pprof.Lookup("heap")
		if profile == nil {
			writeM7HJSONError(w, http.StatusInternalServerError, errors.New("Go heap profile is unavailable"))
			return
		}
		w.Header().Set("Content-Type", "application/octet-stream")
		if err := profile.WriteTo(w, 0); err != nil {
			fmt.Fprintf(os.Stderr, "write M7-H heap profile response: %v\n", err)
		}
	}
}

func (server *m7hRemoteSFUServer) handleGoroutineProfile(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		entered := time.Now()
		fmt.Fprintf(
			os.Stderr,
			"m7h goroutine-profile handler entered: at=%s method=%s\n",
			entered.Format(time.RFC3339Nano),
			r.Method,
		)
		if !server.authorized(w, r, token) {
			return
		}
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			writeM7HJSONError(w, http.StatusMethodNotAllowed, errors.New("goroutine profile requires GET"))
			return
		}
		path := r.Header.Get("X-M7H-Goroutine-Profile-Path")
		if !isM7HTemporaryProfilePath(path) {
			writeM7HJSONError(w, http.StatusBadRequest, errors.New("goroutine profile path must be under a temporary directory"))
			return
		}
		if err := writeM7HGoroutineProfile(path); err != nil {
			writeM7HJSONError(w, http.StatusInternalServerError, err)
			return
		}
		info, err := os.Stat(path)
		if err != nil {
			writeM7HJSONError(w, http.StatusInternalServerError, fmt.Errorf("stat saved goroutine profile: %w", err))
			return
		}
		if info.Size() == 0 {
			writeM7HJSONError(w, http.StatusInternalServerError, errors.New("saved goroutine profile is empty"))
			return
		}
		fmt.Fprintf(os.Stderr, "m7h goroutine profile saved locally: path=%s bytes=%d\n", path, info.Size())
		w.WriteHeader(http.StatusNoContent)
	}
}

func (server *m7hRemoteSFUServer) handleCPUProfile(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			writeM7HJSONError(w, http.StatusMethodNotAllowed, errors.New("CPU profile requires GET"))
			return
		}
		path := r.Header.Get("X-M7H-CPU-Profile-Path")
		if !isM7HTemporaryProfilePath(path) {
			writeM7HJSONError(w, http.StatusBadRequest, errors.New("CPU profile path must be under a temporary directory"))
			return
		}
		duration, err := time.ParseDuration(r.Header.Get("X-M7H-CPU-Profile-Duration"))
		if err != nil || duration <= 0 || duration > m7hCPUProfileMaxWindow {
			writeM7HJSONError(
				w,
				http.StatusBadRequest,
				fmt.Errorf("CPU profile duration must be in (0, %s]", m7hCPUProfileMaxWindow),
			)
			return
		}
		if err := writeM7HCPUProfile(r.Context(), path, duration); err != nil {
			status := http.StatusInternalServerError
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				status = http.StatusRequestTimeout
			}
			writeM7HJSONError(w, status, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

func (server *m7hRemoteSFUServer) handleCleanup(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		server.mu.RLock()
		viewers := make([]viewerEndpoint, 0, len(server.viewers))
		for _, viewer := range server.viewers {
			viewers = append(viewers, viewer)
		}
		server.mu.RUnlock()
		for _, viewer := range viewers {
			if err := server.router.unsubscribe(viewer.id, viewer.key); err != nil {
				writeM7HJSONError(w, http.StatusInternalServerError, err)
				return
			}
		}
		keys := make([]sfuTrackKey, 0, len(server.publishers))
		server.mu.RLock()
		for publisherID := range server.publishers {
			keys = append(keys, sfuTrackKey{
				PublisherID: publisherID,
				TrackID:     fmt.Sprintf("stream-%04d", publisherIndexFromID(publisherID)),
			})
		}
		server.mu.RUnlock()
		for _, key := range keys {
			if err := server.router.unregisterTrack(key); err != nil {
				writeM7HJSONError(w, http.StatusInternalServerError, err)
				return
			}
		}
		for _, viewer := range viewers {
			if err := server.router.removeViewer(viewer.id); err != nil {
				writeM7HJSONError(w, http.StatusInternalServerError, err)
				return
			}
		}
		tracks, viewerCount, subscriptions, authorizations := server.router.counts()
		writeM7HJSON(w, http.StatusOK, m7hRemoteCleanupResponse{
			TracksRemaining:         tracks,
			ViewersRemaining:        viewerCount,
			SubscriptionsRemaining:  subscriptions,
			AuthorizationsRemaining: authorizations,
			CleanupVerified: tracks == 0 && viewerCount == 0 &&
				subscriptions == 0 && authorizations == 0,
		})
	}
}

func publisherIndexFromID(publisherID string) int {
	var index int
	if _, err := fmt.Sscanf(publisherID, "hami-m7h-publisher-%04d", &index); err != nil {
		return 0
	}
	return index
}

func (server *m7hRemoteSFUServer) handleShutdown(token string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !server.authorized(w, r, token) {
			return
		}
		writeM7HJSON(w, http.StatusOK, map[string]string{"status": "shutting_down"})
		go func() {
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			if err := server.httpServer.Shutdown(ctx); err != nil {
				fmt.Fprintf(os.Stderr, "shut down M7-H signaling server: %v\n", err)
			}
		}()
	}
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
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_queue_dropped_total counter\nhami_sfu_rtp_queue_dropped_total %d\n", r.rtpQueueDropped.Load())
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_intentional_shed_total counter\nhami_sfu_rtp_intentional_shed_total %d\n", r.rtpIntentionalShed.Load())
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_keyframe_recoveries_total counter\nhami_sfu_rtp_keyframe_recoveries_total %d\n", r.rtpRecoverySamples.Load())
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_keyframe_recovery_seconds_sum counter\nhami_sfu_rtp_keyframe_recovery_seconds_sum %g\n",
		float64(r.rtpRecoveryNanos.Load())/float64(time.Second))
	fmt.Fprintf(&output, "# TYPE hami_sfu_rtp_keyframe_recovery_seconds_max gauge\nhami_sfu_rtp_keyframe_recovery_seconds_max %g\n",
		float64(r.rtpRecoveryMaxNanos.Load())/float64(time.Second))
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
	subscriptions := make([]*sfuSubscription, 0)
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
		if source.m7hReceiveStats != nil {
			source.m7hReceiveStats.packets.Add(1)
			source.m7hReceiveStats.lastPacketUnixNanos.Store(time.Now().UnixNano())
		}
		source.rtpPacketsRead.Add(1)
		source.rememberPacket(packet)
		if packet.Marker {
			source.firstFrameOnce.Do(func() { close(source.firstFrameReady) })
		}
		r.mu.RLock()
		if r.closed || r.tracks[source.key] != source {
			r.mu.RUnlock()
			return
		}
		if cap(subscriptions) < len(source.subscribers) {
			subscriptions = make([]*sfuSubscription, 0, len(source.subscribers))
		} else {
			subscriptions = subscriptions[:0]
		}
		for _, subscription := range source.subscribers {
			subscriptions = append(subscriptions, subscription)
		}
		r.mu.RUnlock()

		for _, subscription := range subscriptions {
			dropped, err := subscription.enqueueRTP(packet)
			if dropped {
				r.rtpQueueDropped.Add(1)
				r.recordRTPIntentionalShed(subscription)
				r.requestRecoveryKeyframe(subscription)
			}
			if err != nil && subscription.isActive() {
				r.rtpDropped.Add(1)
				r.recordError(fmt.Errorf("forward track %s to viewer %s: %w",
					source.key.TrackID, subscription.viewerID, err))
			}
		}
		clear(subscriptions)
	}
}

func (t *sfuPublishedTrack) rememberPacket(packet *rtp.Packet) {
	t.packetMu.Lock()
	defer t.packetMu.Unlock()
	sequence := packet.SequenceNumber
	t.lastSequence = sequence
	// TrackRemote.ReadRTP returns an owned packet; forwarding and retransmission
	// paths clone before writing, so retain it directly instead of duplicating its payload.
	if _, exists := t.packetCache[sequence]; exists {
		t.packetCache[sequence] = packet
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
	t.packetCache[sequence] = packet
}

func (t *sfuPublishedTrack) cachedPackets(sequences []uint16) ([]*rtp.Packet, []uint16) {
	t.packetMu.Lock()
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
		packets = append(packets, packet)
	}
	t.packetMu.Unlock()
	for index, packet := range packets {
		packets[index] = copyRTPPacketWithSharedPayload(packet)
	}
	return packets, missing
}

// Pion copies the packet struct before mutating the per-binding RTP header.
func copyRTPPacketWithSharedPayload(packet *rtp.Packet) *rtp.Packet {
	packetCopy := *packet
	packetCopy.Header = packet.Header.Clone()
	packetCopy.Raw = nil
	return &packetCopy
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
	s.rtpWriteSucceeded.Add(1)
	return true, nil
}

func (s *sfuSubscription) enqueueRTP(packet *rtp.Packet) (bool, error) {
	if packet == nil {
		return false, errors.New("RTP packet is required")
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	if !s.active {
		return false, nil
	}
	if s.rtpQueue == nil {
		return false, errors.New("RTP queue is not initialized")
	}

	queued := queuedRTP{
		packet:     copyRTPPacketWithSharedPayload(packet),
		enqueuedAt: time.Now(),
	}
	select {
	case s.rtpQueue <- queued:
		s.rtpQueueEnqueued.Add(1)
		return false, nil
	default:
	}
	droppedOldest := false
	select {
	case <-s.rtpQueue:
		droppedOldest = true
		s.markNeedsKeyframe()
	default:
	}
	select {
	case s.rtpQueue <- queued:
		s.rtpQueueEnqueued.Add(1)
		if droppedOldest {
			s.rtpQueueDropped.Add(1)
		}
		return droppedOldest, nil
	default:
		s.rtpQueueDropped.Add(1)
		return true, errors.New("RTP queue remained full after dropping its oldest packet")
	}
}

func (s *sfuSubscription) markNeedsKeyframe() bool {
	if !s.h264Video {
		return false
	}
	startedAt := time.Since(rtpMonotonicStart).Nanoseconds()
	if startedAt <= 0 {
		startedAt = 1
	}
	return s.keyframeNeededAt.CompareAndSwap(0, startedAt)
}

func (s *sfuSubscription) completeKeyframeRecovery() (time.Duration, bool) {
	startedAt := s.keyframeNeededAt.Swap(0)
	if startedAt == 0 {
		return 0, false
	}
	elapsed := time.Since(rtpMonotonicStart).Nanoseconds() - startedAt
	if elapsed < 0 {
		return 0, false
	}
	return time.Duration(elapsed), true
}

func (s *sfuSubscription) allowRTPDuringKeyframeRecovery(packet *rtp.Packet) (bool, bool) {
	if !s.h264Video || s.keyframeNeededAt.Load() == 0 {
		return true, false
	}
	idrStart := isH264IDRStart(packet.Payload)
	return idrStart || isH264RecoveryConfig(packet.Payload), idrStart
}

func (s *sfuSubscription) stop() {
	s.mu.Lock()
	s.active = false
	if !s.rtpQueueClosed && s.rtpQueue != nil {
		close(s.rtpQueue)
		s.rtpQueueClosed = true
	}
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

// recordPLIReceived counts a PLI packet that arrived at the router socket,
// whether or not translation later accepts it. (M7-H attempt 4: separates
// "never arrived at the app" from "arrived but not forwarded".)
func (s *sfuSubscription) recordPLIReceived() {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.PLIReceived++
}

// recordFIRReceived counts a FIR packet that arrived at the router socket,
// whether or not translation later accepts it. (M7-H attempt 4.)
func (s *sfuSubscription) recordFIRReceived() {
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	s.feedback.FIRReceived++
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
				// (up to 512 WriteRTP calls per NACK, capped by
				// maxSequencesPerNACK) drowned this
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
			// M7-H attempt 4: count PLI/FIR at receipt, before
			// translation. A packet that arrived but was rejected
			// (wrong SSRC) or arrived after deactivation still
			// arrived — that is exactly what "received" must mean,
			// so this counts unconditionally.
			switch packet.(type) {
			case *rtcp.PictureLossIndication:
				subscription.recordPLIReceived()
			case *rtcp.FullIntraRequest:
				subscription.recordFIRReceived()
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
	rtpQueue := subscription.rtpQueue
	nackQueue := subscription.nackQueue
	for rtpQueue != nil || nackQueue != nil {
		select {
		case queued, ok := <-rtpQueue:
			if !ok {
				rtpQueue = nil
				continue
			}
			if !subscription.isActive() {
				return
			}
			r.forwardQueuedRTP(subscription, queued)
			continue
		default:
		}

		select {
		case queued, ok := <-rtpQueue:
			if !ok {
				rtpQueue = nil
				continue
			}
			if !subscription.isActive() {
				return
			}
			r.forwardQueuedRTP(subscription, queued)
		case entry, ok := <-nackQueue:
			if !ok {
				nackQueue = nil
				continue
			}
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
}

func (r *sfuRouter) forwardQueuedRTP(subscription *sfuSubscription, queued queuedRTP) {
	packet := queued.packet
	if packet == nil {
		r.rtpDropped.Add(1)
		r.recordError(fmt.Errorf("forward track %s to viewer %s: queued RTP packet is nil",
			subscription.key.TrackID, subscription.viewerID))
		return
	}
	if time.Since(queued.enqueuedAt) > nackMaxQueueAge {
		subscription.markNeedsKeyframe()
		subscription.rtpQueueDropped.Add(1)
		r.rtpQueueDropped.Add(1)
		r.recordRTPIntentionalShed(subscription)
		r.requestRecoveryKeyframe(subscription)
		return
	}
	needsKeyframe := subscription.keyframeNeededAt.Load() != 0
	allowPacket, idrStart := subscription.allowRTPDuringKeyframeRecovery(packet)
	if !allowPacket {
		r.recordRTPIntentionalShed(subscription)
		return
	}
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
	if sent && needsKeyframe && idrStart {
		if recoveryDuration, recovered := subscription.completeKeyframeRecovery(); recovered {
			r.recordRTPKeyframeRecovery(recoveryDuration)
		}
	}
	if err != nil && subscription.isActive() {
		r.rtpDropped.Add(1)
		r.recordError(fmt.Errorf("forward track %s to viewer %s: %w",
			subscription.key.TrackID, subscription.viewerID, err))
	}
}

func isH264IDRStart(payload []byte) bool {
	if len(payload) == 0 {
		return false
	}
	switch payload[0] & 0x1f {
	case 5:
		return true
	case 24:
		for offset := 1; offset+2 <= len(payload); {
			nalSize := int(binary.BigEndian.Uint16(payload[offset : offset+2]))
			offset += 2
			if nalSize == 0 || offset+nalSize > len(payload) {
				return false
			}
			if payload[offset]&0x1f == 5 {
				return true
			}
			offset += nalSize
		}
	case 28, 29:
		return len(payload) >= 2 && payload[1]&0x80 != 0 && payload[1]&0x1f == 5
	}
	return false
}

func isH264RecoveryConfig(payload []byte) bool {
	if len(payload) == 0 {
		return false
	}
	switch payload[0] & 0x1f {
	case 7, 8:
		return true
	case 24:
		offset := 1
		foundConfig := false
		for offset+2 <= len(payload) {
			nalSize := int(binary.BigEndian.Uint16(payload[offset : offset+2]))
			offset += 2
			if nalSize == 0 || offset+nalSize > len(payload) {
				return false
			}
			nalType := payload[offset] & 0x1f
			if nalType != 7 && nalType != 8 {
				return false
			}
			foundConfig = true
			offset += nalSize
		}
		return foundConfig && offset == len(payload)
	case 28, 29:
		if len(payload) < 2 {
			return false
		}
		nalType := payload[1] & 0x1f
		return nalType == 7 || nalType == 8
	default:
		return false
	}
}

func (r *sfuRouter) recordRTPIntentionalShed(subscription *sfuSubscription) {
	if subscription != nil {
		subscription.rtpIntentionalShed.Add(1)
	}
	r.rtpIntentionalShed.Add(1)
}

func (r *sfuRouter) allowKeyframeRequest(publisherID string, now time.Time) bool {
	if publisherID == "" {
		return false
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.lastKeyframeRequestByPublisher == nil {
		r.lastKeyframeRequestByPublisher = make(map[string]time.Time)
	}
	lastRequestedAt := r.lastKeyframeRequestByPublisher[publisherID]
	if !lastRequestedAt.IsZero() && now.Sub(lastRequestedAt) < time.Second {
		return false
	}
	r.lastKeyframeRequestByPublisher[publisherID] = now
	return true
}

func (r *sfuRouter) requestRecoveryKeyframe(subscription *sfuSubscription) {
	if subscription == nil || !subscription.h264Video || subscription.source == nil ||
		subscription.source.remote == nil || subscription.source.publisherPeer == nil {
		return
	}
	source := subscription.source
	if !r.allowKeyframeRequest(source.key.PublisherID, time.Now()) {
		return
	}
	request := &rtcp.PictureLossIndication{
		SenderSSRC: r.feedbackSenderSSRC,
		MediaSSRC:  uint32(source.remote.SSRC()),
	}
	if err := source.publisherPeer.WriteRTCP([]rtcp.Packet{request}); err != nil {
		r.recordError(fmt.Errorf("request recovery keyframe for publisher %s track %s: %w",
			source.key.PublisherID, source.key.TrackID, err))
	}
}

func (r *sfuRouter) recordRTPKeyframeRecovery(duration time.Duration) {
	if duration < 0 {
		return
	}
	nanos := uint64(duration)
	r.rtpRecoveryNanos.Add(nanos)
	r.rtpRecoverySamples.Add(1)
	for current := r.rtpRecoveryMaxNanos.Load(); nanos > current; current = r.rtpRecoveryMaxNanos.Load() {
		if r.rtpRecoveryMaxNanos.CompareAndSwap(current, nanos) {
			break
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

func makeNACKRTCPPackets(senderSSRC, mediaSSRC uint32, sequences []uint16) []rtcp.Packet {
	pairs := rtcp.NackPairsFromSequenceNumbers(sequences)
	packets := make([]rtcp.Packet, 0, (len(pairs)+maxNACKPairsPerRTCPPacket-1)/maxNACKPairsPerRTCPPacket)
	for start := 0; start < len(pairs); start += maxNACKPairsPerRTCPPacket {
		end := min(start+maxNACKPairsPerRTCPPacket, len(pairs))
		packets = append(packets, &rtcp.TransportLayerNack{
			SenderSSRC: senderSSRC,
			MediaSSRC:  mediaSSRC,
			Nacks:      pairs[start:end],
		})
	}
	return packets
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
		packets := makeNACKRTCPPackets(
			r.feedbackSenderSSRC,
			uint32(subscription.source.remote.SSRC()),
			missing,
		)
		subscription.mu.RLock()
		if subscription.active {
			for _, packet := range packets {
				if err := subscription.source.publisherPeer.WriteRTCP([]rtcp.Packet{packet}); err != nil {
					subscription.mu.RUnlock()
					return fmt.Errorf("forward uncached NACK upstream: %w", err)
				}
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
		if subscription.source.key.TrackID == "stream-0253" {
			for _, entry := range feedback.FIR {
				fmt.Fprintf(
					os.Stderr,
					"FIR SSRC mapping: viewer=%s publisher=%s track=%s carriedMediaSSRC=%d carriedTargetSSRC=%d expectedViewerSSRC=%d mappedPublisherSSRC=%d mappingSource=publisher TrackRemote.SSRC trackRemoteID=%s\n",
					subscription.viewerID,
					subscription.source.key.PublisherID,
					subscription.source.key.TrackID,
					feedback.MediaSSRC,
					entry.SSRC,
					viewerSSRC,
					publisherSSRC,
					subscription.source.remote.ID(),
				)
			}
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

func runLocalSFUSinglePairProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
) (sfuProofResult, error) {
	return runLocalSFUScaleProof(ctx, videoFrames, duration, 1, 1)
}

func runLocalSFUScaleProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
	publisherCount int,
	viewersPerPublisher int,
) (sfuProofResult, error) {
	config, err := buildSFUScaleProofConfig(publisherCount, viewersPerPublisher)
	if err != nil {
		return sfuProofResult{}, err
	}
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("SFU scale duration must be at least %s", MinDuration)
	}
	return runLocalSFUProofWithConfig(ctx, videoFrames, duration, config)
}

func buildSFUScaleProofConfig(publisherCount int, viewersPerPublisher int) (sfuProofConfig, error) {
	if publisherCount < 1 || publisherCount > 3000 {
		return sfuProofConfig{}, fmt.Errorf("SFU scale publisher count must be between 1 and 3000, got %d", publisherCount)
	}
	if viewersPerPublisher < 1 || viewersPerPublisher > sfuScaleMaxViewersPerPublisher {
		return sfuProofConfig{}, fmt.Errorf(
			"SFU scale viewers per publisher must be between 1 and %d, got %d",
			sfuScaleMaxViewersPerPublisher,
			viewersPerPublisher,
		)
	}
	totalViewers := publisherCount * viewersPerPublisher
	if totalViewers > sfuScaleMaxViewers {
		return sfuProofConfig{}, fmt.Errorf(
			"SFU scale total viewer count must not exceed %d, got %d",
			sfuScaleMaxViewers,
			totalViewers,
		)
	}
	tracks := make([]sfuTrackSpec, publisherCount)
	viewerTrackIndexes := make([]int, 0, totalViewers)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m6h-scale-publisher-%04d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%04d", publisherIndex+1),
		}
		for range viewersPerPublisher {
			viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
		}
	}
	return sfuProofConfig{
		proofID:            fmt.Sprintf("m6h-scale-p%d-vpp%d-v%d-fps5", publisherCount, viewersPerPublisher, totalViewers),
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
		videoInterval:      200 * time.Millisecond,
		logRTPPath:         true,
	}, nil
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
		// M6-H acceptance is 5 fps (300 frames in 65 s). The 1 s interval
		// used by the attempt-13 probe sent only ~119 frames in 120 s,
		// so no viewer could reach 300 frames. Attempt 9 failed at 5 fps
		// because NACKs were handled synchronously in the read loop;
		// the nackWorker + bounded queue (attempt 13) fixed that, and
		// the 120 s probe showed 0 queue-full / 0 stale drops, so 5 fps
		// is the correct load to test now.
		videoInterval: 200 * time.Millisecond,
	})
}

func runLocalM7HProof(
	ctx context.Context,
	videoFrames []media.Sample,
	duration time.Duration,
	pairCount int,
) (sfuProofResult, error) {
	if duration < MinDuration {
		return sfuProofResult{}, fmt.Errorf("M7-H duration must be at least %s", MinDuration)
	}
	if pairCount < 1 || pairCount > 3000 {
		return sfuProofResult{}, fmt.Errorf("M7-H viewer count must be between 1 and 3000: %d", pairCount)
	}
	tracks := make([]sfuTrackSpec, pairCount)
	viewerTrackIndexes := make([]int, 0, pairCount)
	for publisherIndex := range tracks {
		tracks[publisherIndex] = sfuTrackSpec{
			publisherID: fmt.Sprintf("hami-m7h-publisher-%04d", publisherIndex+1),
			trackID:     fmt.Sprintf("stream-%04d", publisherIndex+1),
		}
		// M7-H: one viewer per track.
		viewerTrackIndexes = append(viewerTrackIndexes, publisherIndex)
	}
	config := sfuProofConfig{
		proofID:            "m7h",
		tracks:             tracks,
		viewerTrackIndexes: viewerTrackIndexes,
		measureLatency:     true,
		exerciseRTCP:       true,
		// M7-H acceptance is 5 fps, same as M6-H. Explicit 200 ms:
		// the shared proof path defaults an unset interval to
		// videoFrameDuration (60 ms, ~16.7 fps), which would triple
		// the load and break comparability with the M0–M6 ladder.
		videoInterval: 200 * time.Millisecond,
	}
	remoteSFU, err := startM7HRemoteSFU(ctx)
	if err != nil {
		return sfuProofResult{}, err
	}
	config.remoteSFU = remoteSFU
	result, proofErr := runLocalSFUProofWithConfig(ctx, videoFrames, duration, config)
	return result, errors.Join(proofErr, remoteSFU.Close())
}

func newM7HPublisherAPIWithoutNACKResponder(settings webrtc.SettingEngine) (*webrtc.API, error) {
	mediaEngine := &webrtc.MediaEngine{}
	if err := mediaEngine.RegisterDefaultCodecs(); err != nil {
		return nil, fmt.Errorf("register default publisher codecs: %w", err)
	}

	registry := &interceptor.Registry{}
	mediaEngine.RegisterFeedback(webrtc.RTCPFeedback{Type: "nack"}, webrtc.RTPCodecTypeVideo)
	mediaEngine.RegisterFeedback(
		webrtc.RTCPFeedback{Type: "nack", Parameter: "pli"},
		webrtc.RTPCodecTypeVideo,
	)
	generator, err := nack.NewGeneratorInterceptor()
	if err != nil {
		return nil, fmt.Errorf("create NACK generator interceptor: %w", err)
	}
	registry.Add(generator)
	if err := webrtc.ConfigureRTCPReports(registry); err != nil {
		return nil, fmt.Errorf("configure RTCP report interceptors: %w", err)
	}
	if err := webrtc.ConfigureSimulcastExtensionHeaders(mediaEngine); err != nil {
		return nil, fmt.Errorf("configure simulcast headers: %w", err)
	}
	if err := webrtc.ConfigureStatsInterceptor(registry); err != nil {
		return nil, fmt.Errorf("configure stats interceptor: %w", err)
	}
	if err := webrtc.ConfigureTWCCSender(mediaEngine, registry); err != nil {
		return nil, fmt.Errorf("configure TWCC sender: %w", err)
	}

	return webrtc.NewAPI(
		webrtc.WithMediaEngine(mediaEngine),
		webrtc.WithInterceptorRegistry(registry),
		webrtc.WithSettingEngine(settings),
	), nil
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
	// M7-H attempt 7: the teardown attribution print is registered FIRST
	// so it runs LAST (after the peer and mux close defers below) — it
	// captures the writes and closes that happen during teardown, which
	// the attempt-6 print (registered last, ran first) missed.
	defer logTeardownAttribution()
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
	clientSettings, _, err := loopbackSettings(false, 0)
	if err != nil {
		return sfuProofResult{}, err
	}
	if clientSocketReadMode != "disabled" && clientSocketReadMode != "enabled" {
		return sfuProofResult{}, fmt.Errorf(
			"invalid client socket read mode %q (want disabled or enabled)",
			clientSocketReadMode,
		)
	}
	clientSocketReadBufferBytes, err := strconv.Atoi(clientSocketReadBufferSize)
	if err != nil {
		return sfuProofResult{}, fmt.Errorf(
			"invalid client socket receive buffer size %q: %w",
			clientSocketReadBufferSize,
			err,
		)
	}
	if clientSocketReadBufferBytes < 0 {
		return sfuProofResult{}, fmt.Errorf("client socket receive buffer size must not be negative: %d", clientSocketReadBufferBytes)
	}
	if clientSocketReadBufferBytes > 0 && clientSocketReadMode != "enabled" {
		return sfuProofResult{}, errors.New("client socket receive buffer requires client socket read mode to be enabled")
	}
	clientAPI := webrtc.NewAPI(webrtc.WithSettingEngine(clientSettings))
	publisherClientAPI := clientAPI
	if config.proofID == "m7h" {
		// Diagnostic only: bypass Pion's NACK responder on harness publishers.
		publisherClientAPI, err = newM7HPublisherAPIWithoutNACKResponder(clientSettings)
		if err != nil {
			return sfuProofResult{}, err
		}
	}
	if routerUDPMuxMode != "enabled" && routerUDPMuxMode != "disabled" {
		return sfuProofResult{}, fmt.Errorf(
			"invalid router UDP mux mode %q (want enabled or disabled)",
			routerUDPMuxMode,
		)
	}
	if routerSocketWriteMode != "disabled" && routerSocketWriteMode != "enabled" {
		return sfuProofResult{}, fmt.Errorf(
			"invalid router socket write mode %q (want disabled or enabled)",
			routerSocketWriteMode,
		)
	}
	routerUDPMuxEnabled := routerUDPMuxMode == "enabled"
	fmt.Fprintf(os.Stderr, "router ICE UDP mux mode: %s\n", routerUDPMuxMode)
	fmt.Fprintf(os.Stderr, "router socket write counter mode: %s\n", routerSocketWriteMode)
	fmt.Fprintf(os.Stderr, "client socket read counter mode: %s\n", clientSocketReadMode)
	if clientSocketReadBufferBytes > 0 {
		fmt.Fprintf(os.Stderr, "client socket receive buffer requested: %d bytes\n", clientSocketReadBufferBytes)
	}
	if routerUDPMuxEnabled && clientSocketReadBufferBytes > 0 {
		fmt.Fprintf(os.Stderr, "router socket receive buffer requested: %d bytes\n", clientSocketReadBufferBytes)
	}
	routerMuxCount := min(peerNegotiationConcurrency, len(publishers))
	routerMuxes := make([]ice.UDPMux, 0, routerMuxCount)
	routerMuxByShard := make([]ice.UDPMux, routerMuxCount)
	routerSettingsByShard := make([]webrtc.SettingEngine, routerMuxCount)
	routerShardByPublisher := make(map[string]int, len(publishers))
	routerSocketMuxes := make([]*singlePeerUDPMux, 0, len(config.viewerTrackIndexes))
	clientSocketMuxes := make([]*singlePeerUDPMux, 0, len(config.viewerTrackIndexes))
	defer func() {
		for i, udpMux := range routerMuxes {
			// M7-H attempt 6: the router shard mux sockets close here (the
			// counting conns wrapping them are never Close()d directly), so
			// log the close for the attribution trace.
			// M7-H attempt 7: initiator=app-teardown — this close is the
			// app's own teardown, not an ICE failure.
			for _, addr := range udpMux.GetListenAddresses() {
				recordSocketClose(fmt.Sprintf("router-mux-shard-%d", i), addr.String(), "", "app-teardown")
			}
			if closeErr := udpMux.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close loopback ICE UDP mux: %w", closeErr))
			}
		}
		for _, udpMux := range routerSocketMuxes {
			if closeErr := udpMux.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close router loopback UDP socket: %w", closeErr))
			}
		}
		for _, udpMux := range clientSocketMuxes {
			if closeErr := udpMux.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close viewer loopback UDP socket: %w", closeErr))
			}
		}
	}()
	routerAPIs := make([]*webrtc.API, routerMuxCount)
	routerAPIByPublisher := make(map[string]*webrtc.API, len(publishers))
	var router *sfuRouter
	if config.remoteSFU == nil {
		for index, publisherID := range publishers {
			shard := index % routerMuxCount
			if routerAPIs[shard] == nil {
				routerSettings, udpMux, muxErr := loopbackSettings(routerUDPMuxEnabled, clientSocketReadBufferBytes)
				if muxErr != nil {
					return sfuProofResult{}, muxErr
				}
				if udpMux != nil {
					routerMuxes = append(routerMuxes, udpMux)
				}
				routerMuxByShard[shard] = udpMux
				routerSettingsByShard[shard] = routerSettings
				routerAPIs[shard] = webrtc.NewAPI(webrtc.WithSettingEngine(routerSettings))
			}
			routerAPIByPublisher[publisherID] = routerAPIs[shard]
			routerShardByPublisher[publisherID] = shard
		}
		router, err = newSFURouter(routerAPIs[0])
		if err != nil {
			return sfuProofResult{}, err
		}
	}
	publisherSendStats := make(map[string]*m7hPublisherSendStats)
	var publisherSendStatsList []*m7hPublisherSendStats
	if config.proofID == "m7h" {
		for _, publisherID := range publishers {
			stats := &m7hPublisherSendStats{publisherID: publisherID}
			publisherSendStats[publisherID] = stats
			publisherSendStatsList = append(publisherSendStatsList, stats)
		}
	}
	viewers := make([]viewerEndpoint, 0, len(config.viewerTrackIndexes))
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
		for i, peer := range viewerClients {
			// M7-H attempt 6: log the PC close for the attribution trace
			// (Pion may have already closed this PC's socket internally if
			// its ICE transport failed during the wait).
			// M7-H attempt 7: include the PC's lifetime summary so the
			// close initiator is visible (last ICE state, ever connected,
			// first failure).
			id := fmt.Sprintf("viewer-%d", i+1)
			if i < len(viewers) {
				id = viewers[i].id
			}
			fmt.Fprintf(os.Stderr, "pc closed: kind=viewer-client id=%s at=%s mono=%d%s\n",
				id, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("viewer-client", id))
			if closeErr := peer.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr, fmt.Errorf("close viewer client: %w", closeErr))
			}
		}
		for publisherID, peer := range publisherClients {
			fmt.Fprintf(os.Stderr, "pc closed: kind=publisher-client id=%s at=%s mono=%d%s\n",
				publisherID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("publisher-client", publisherID))
			if closeErr := peer.Close(); closeErr != nil {
				returnErr = errors.Join(returnErr,
					fmt.Errorf("close publisher %s client: %w", publisherID, closeErr))
			}
		}
		if router != nil {
			if closeErr := router.close(); closeErr != nil {
				returnErr = errors.Join(returnErr, closeErr)
			}
		}
	}()
	defer func() {
		// M7-H attempt 6: the attribution print runs on every exit (pass
		// or fail) — it is the run's whole point.
		if router != nil {
			logEndpointAttribution(router, viewers)
			if returnErr != nil || config.proofID == "m7h" {
				logRouterFeedbackDiagnosis(router, viewers)
			}
		}
	}()
	if router != nil && *metricsListenAddress != "" {
		metricsServer, err = router.startMetricsServer(*metricsListenAddress)
		if err != nil {
			return sfuProofResult{}, err
		}
	}

	for _, publisherID := range publishers {
		clientPeer, err := publisherClientAPI.NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("create publisher %s client: %w", publisherID, err)
		}
		// M7-H attempt 6: log ICE/connection state transitions — a publisher
		// whose ICE transport fails mid-run has its socket closed by Pion
		// without any app-level Close() call.
		attachPCStateLogging(clientPeer, "publisher-client", publisherID)
		publisherClients[publisherID] = clientPeer
		if router != nil {
			routerPeer, registerErr := router.registerPublisher(routerAPIByPublisher[publisherID], publisherID)
			if registerErr != nil {
				// M7-H attempt 7: log the mid-run app-initiated PC close.
				fmt.Fprintf(os.Stderr, "pc closed: kind=publisher-client id=%s at=%s mono=%d reason=registerPublisher-failed%s\n",
					publisherID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("publisher-client", publisherID))
				_ = clientPeer.Close()
				return sfuProofResult{}, registerErr
			}
			attachPCStateLogging(routerPeer, "router-publisherPeer", publisherID)
			routerPublisherPeers[publisherID] = routerPeer
		}
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
	if router == nil {
		if err := config.remoteSFU.negotiatePublishers(ctx, publishers, publisherClients); err != nil {
			return sfuProofResult{}, fmt.Errorf("negotiate remote publisher pairs: %w", err)
		}
	} else {
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
	}
	for _, source := range sources {
		if err := source.track.WriteSample(videoFrames[0]); err != nil {
			return sfuProofResult{}, fmt.Errorf("register publisher track %s: %w", source.key.TrackID, err)
		}
	}
	if router != nil {
		if err := router.waitForTracks(ctx, sources); err != nil {
			return sfuProofResult{}, err
		}
	}
	firstSequenceByTrack := make(map[sfuTrackKey]uint16, len(sources))
	if config.measureLatency {
		for _, source := range sources {
			var lastSequence uint16
			var err error
			if router != nil {
				lastSequence, err = router.waitForFirstFrame(ctx, source.key)
			} else {
				lastSequence, err = config.remoteSFU.waitForFirstFrame(ctx, source.key)
			}
			if err != nil {
				return sfuProofResult{}, err
			}
			firstSequenceByTrack[source.key] = lastSequence + 1
		}
	}

	viewerPairs := make([]peerNegotiationPair, 0, len(config.viewerTrackIndexes))
	remoteViewerPairs := make([]m7hRemoteViewerPair, 0, len(config.viewerTrackIndexes))
	unauthorizedSubscriptionDenied := false
	for index, sourceIndex := range config.viewerTrackIndexes {
		source := sources[sourceIndex]
		viewerID := fmt.Sprintf("hami-sfu-viewer-%d", index+1)
		if router == nil {
			viewerClientAPI := clientAPI
			var socketConn *packetReadCountingConn
			if clientSocketReadMode == "enabled" {
				socketMux, muxErr := newSinglePeerUDPMux()
				if muxErr != nil {
					return sfuProofResult{}, muxErr
				}
				clientSocketMuxes = append(clientSocketMuxes, socketMux)
				if clientSocketReadBufferBytes > 0 {
					actual, bufferErr := setUDPConnReadBuffer(socketMux.conn.PacketConn, clientSocketReadBufferBytes)
					if bufferErr != nil {
						return sfuProofResult{}, bufferErr
					}
					if index == 0 {
						fmt.Fprintf(os.Stderr, "client socket receive buffer effective: %d bytes\n", actual)
					}
				}
				viewerClientSettings := clientSettings
				viewerClientSettings.SetICEUDPMux(socketMux)
				viewerClientAPI = webrtc.NewAPI(webrtc.WithSettingEngine(viewerClientSettings))
				socketConn = socketMux.conn
				socketConn.pcKey = "viewer-client:" + viewerID
			}
			clientPeer, err := viewerClientAPI.NewPeerConnection(webrtc.Configuration{})
			if err != nil {
				return sfuProofResult{}, fmt.Errorf("create viewer client %s: %w", viewerID, err)
			}
			attachPCStateLogging(clientPeer, "viewer-client", viewerID)
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
				config.proofID == "m7h",
			)
			if _, err := clientPeer.AddTransceiverFromKind(
				webrtc.RTPCodecTypeVideo,
				webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly},
			); err != nil {
				return sfuProofResult{}, fmt.Errorf("add viewer %s receive transceiver: %w", viewerID, err)
			}
			viewers = append(viewers, viewerEndpoint{
				id:             viewerID,
				key:            source.key,
				client:         clientPeer,
				capture:        capture,
				recorder:       recorder,
				socketConn:     socketConn,
				candidatePairs: &candidatePairSnapshot{},
			})
			remoteViewerPairs = append(remoteViewerPairs, m7hRemoteViewerPair{
				viewerID:                viewerID,
				key:                     source.key,
				peer:                    clientPeer,
				socketConn:              socketConn,
				checkUnauthorizedAccess: index == 0,
			})
			continue
		}
		routerPeerAPI := routerAPIByPublisher[source.key.PublisherID]
		var routerSocketConn *packetReadCountingConn
		if routerSocketWriteMode == "enabled" {
			if routerUDPMuxEnabled {
				shard := routerShardByPublisher[source.key.PublisherID]
				sharedMux := routerMuxByShard[shard]
				if sharedMux == nil {
					return sfuProofResult{}, fmt.Errorf(
						"router UDP mux is unavailable for publisher %s",
						source.key.PublisherID,
					)
				}
				socketMux := newCountingUDPMux(sharedMux)
				routerPeerSettings := routerSettingsByShard[shard]
				routerPeerSettings.SetICEUDPMux(socketMux)
				routerPeerAPI = webrtc.NewAPI(webrtc.WithSettingEngine(routerPeerSettings))
				routerSocketConn = socketMux.conn
				// M7-H attempt 6: per-viewer role for the attribution trace.
				routerSocketConn.role = fmt.Sprintf("router-shard-%d:%s", shard, viewerID)
				// M7-H attempt 7: owning PC key for close-initiator attribution.
				routerSocketConn.pcKey = "router-serverPeer:" + viewerID
			} else {
				socketMux, muxErr := newSinglePeerUDPMux()
				if muxErr != nil {
					return sfuProofResult{}, muxErr
				}
				routerSocketMuxes = append(routerSocketMuxes, socketMux)
				routerPeerSettings := clientSettings
				routerPeerSettings.SetICEUDPMux(socketMux)
				routerPeerAPI = webrtc.NewAPI(webrtc.WithSettingEngine(routerPeerSettings))
				routerSocketConn = socketMux.conn
				// M7-H attempt 6: per-viewer role for the attribution trace.
				routerSocketConn.role = "router-single:" + viewerID
				// M7-H attempt 7: owning PC key for close-initiator attribution.
				routerSocketConn.pcKey = "router-serverPeer:" + viewerID
			}
		}
		serverPeer, err := routerPeerAPI.NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("create router endpoint for %s: %w", viewerID, err)
		}
		// M7-H attempt 6: log ICE/connection state transitions.
		attachPCStateLogging(serverPeer, "router-serverPeer", viewerID)
		viewerClientAPI := clientAPI
		var socketConn *packetReadCountingConn
		if clientSocketReadMode == "enabled" {
			socketMux, muxErr := newSinglePeerUDPMux()
			if muxErr != nil {
				// M7-H attempt 7: log the mid-run app-initiated PC close.
				fmt.Fprintf(os.Stderr, "pc closed: kind=router-serverPeer id=%s at=%s mono=%d reason=newSinglePeerUDPMux-failed%s\n",
					viewerID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("router-serverPeer", viewerID))
				_ = serverPeer.Close()
				return sfuProofResult{}, muxErr
			}
			clientSocketMuxes = append(clientSocketMuxes, socketMux)
			if clientSocketReadBufferBytes > 0 {
				actual, bufferErr := setUDPConnReadBuffer(socketMux.conn.PacketConn, clientSocketReadBufferBytes)
				if bufferErr != nil {
					// M7-H attempt 7: log the mid-run app-initiated PC close.
					fmt.Fprintf(os.Stderr, "pc closed: kind=router-serverPeer id=%s at=%s mono=%d reason=setReadBuffer-failed%s\n",
						viewerID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("router-serverPeer", viewerID))
					_ = serverPeer.Close()
					return sfuProofResult{}, bufferErr
				}
				if index == 0 {
					fmt.Fprintf(
						os.Stderr,
						"client socket receive buffer effective: %d bytes\n",
						actual,
					)
				}
			}
			viewerClientSettings := clientSettings
			viewerClientSettings.SetICEUDPMux(socketMux)
			viewerClientAPI = webrtc.NewAPI(webrtc.WithSettingEngine(viewerClientSettings))
			socketConn = socketMux.conn
			// M7-H attempt 7: owning PC key for close-initiator attribution.
			socketConn.pcKey = "viewer-client:" + viewerID
		}
		clientPeer, err := viewerClientAPI.NewPeerConnection(webrtc.Configuration{})
		if err != nil {
			// M7-H attempt 7: log the mid-run app-initiated PC close.
			fmt.Fprintf(os.Stderr, "pc closed: kind=router-serverPeer id=%s at=%s mono=%d reason=create-viewer-client-failed%s\n",
				viewerID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("router-serverPeer", viewerID))
			_ = serverPeer.Close()
			return sfuProofResult{}, fmt.Errorf("create viewer client %s: %w", viewerID, err)
		}
		// M7-H attempt 6: log ICE/connection state transitions.
		attachPCStateLogging(clientPeer, "viewer-client", viewerID)
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
			config.proofID == "m7h",
		)
		if _, err := clientPeer.AddTransceiverFromKind(
			webrtc.RTPCodecTypeVideo,
			webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly},
		); err != nil {
			// M7-H attempt 7: log the mid-run app-initiated PC close.
			fmt.Fprintf(os.Stderr, "pc closed: kind=router-serverPeer id=%s at=%s mono=%d reason=add-transceiver-failed%s\n",
				viewerID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("router-serverPeer", viewerID))
			_ = serverPeer.Close()
			return sfuProofResult{}, fmt.Errorf("add viewer %s receive transceiver: %w", viewerID, err)
		}
		if err := router.registerViewer(viewerID, serverPeer); err != nil {
			// M7-H attempt 7: log the mid-run app-initiated PC close.
			fmt.Fprintf(os.Stderr, "pc closed: kind=router-serverPeer id=%s at=%s mono=%d reason=registerViewer-failed%s\n",
				viewerID, time.Now().Format(time.RFC3339Nano), time.Since(monoOrigin).Nanoseconds(), pcCloseSummary("router-serverPeer", viewerID))
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
		candidatePairs := &candidatePairSnapshot{}
		viewers = append(viewers, viewerEndpoint{
			id:               viewerID,
			key:              source.key,
			client:           clientPeer,
			capture:          capture,
			recorder:         recorder,
			socketConn:       socketConn,
			routerSocketConn: routerSocketConn,
			candidatePairs:   candidatePairs,
		})
		viewerPairs = append(viewerPairs, peerNegotiationPair{
			name:               fmt.Sprintf("viewer[%d] %s -> %s/%s", index, viewerID, source.key.PublisherID, source.key.TrackID),
			offerer:            clientPeer,
			answerer:           serverPeer,
			mediaSections:      []string{"m=video"},
			socketConn:         socketConn,
			answererSocketConn: routerSocketConn,
		})
	}
	if router == nil {
		unauthorizedDenied, err := config.remoteSFU.negotiateViewers(ctx, remoteViewerPairs)
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("negotiate remote viewer pairs: %w", err)
		}
		unauthorizedSubscriptionDenied = unauthorizedDenied[remoteViewerPairs[0].viewerID]
	} else if err := negotiateLoopbackPairsBounded(ctx, viewerPairs, peerNegotiationConcurrency); err != nil {
		return sfuProofResult{}, fmt.Errorf("negotiate viewer pairs: %w", err)
	}
	if config.proofID == "m7h" && config.remoteSFU != nil && *m7hHeapProfilePath != "" {
		if err := captureM7HHeapProfiles(ctx, config.remoteSFU, *m7hHeapProfilePath, "connected"); err != nil {
			return sfuProofResult{}, err
		}
		fmt.Fprintf(
			os.Stderr,
			"m7h heap profiles captured: prefix=%s stage=connected publishers=%d viewers=%d\n",
			*m7hHeapProfilePath,
			len(publishers),
			len(viewers),
		)
	}

	// Attempt 5: verify the router mux receive buffer actually took effect.
	// Pion applies UDPMuxFromPortWithReadBufferSize at socket creation and
	// ignores the error, so the requested value alone proves nothing. The
	// counting mux's conn is initialized on first GetConn during negotiation,
	// so by here it wraps the shard's underlying UDP socket.
	if router != nil && routerUDPMuxEnabled && clientSocketReadBufferBytes > 0 {
		for _, viewer := range viewers {
			if viewer.routerSocketConn == nil || viewer.routerSocketConn.PacketConn == nil {
				continue
			}
			if effective, bufferErr := readUDPConnReadBuffer(viewer.routerSocketConn.PacketConn); bufferErr == nil {
				fmt.Fprintf(os.Stderr, "router socket receive buffer effective: %d bytes\n", effective)
			} else {
				fmt.Fprintf(os.Stderr, "router socket receive buffer effective: unavailable (%v)\n", bufferErr)
			}
			break
		}
	}

	expectedNACKs := make(map[string]map[uint16]struct{}, len(sources))
	var expectedNACKsMu sync.RWMutex
	feedbackEvents := make(chan sfuFeedbackEvent, 16384)
	if config.exerciseRTCP {
		for _, source := range sources {
			go readPublisherFeedback(
				ctx,
				source.key.TrackID,
				source.sender,
				expectedNACKs,
				&expectedNACKsMu,
				feedbackEvents,
			)
		}
	}
	startedAt := time.Now().UTC()
	sendContext, cancelSend := context.WithTimeout(ctx, duration)
	stopCandidatePairSampler := func() {}
	stopM7HRuntimeProbe := func() {}
	captureBeforeViewerReadinessAbort := func() {}
	waitForM7HGoroutineProfileCapture := func() {}
	waitForM7HCPUProfileCapture := func() error { return nil }
	stopSFUReceivePoll := func() {}
	if router != nil && (routerSocketWriteMode == "enabled" || clientSocketReadMode == "enabled") {
		stopCandidatePairSampler = startCandidatePairSampler(
			sendContext,
			router,
			viewers,
			config.proofID == "m7h",
		)
	}
	defer stopCandidatePairSampler()
	if config.proofID == "m7h" {
		var onPublisherSendSample func(frames uint64, stalePublishers int)
		var onSFUReceiveSample func(packets uint64, stalePublishers int)
		if config.remoteSFU != nil && *m7hCPUProfilePath != "" {
			waitForM7HCPUProfileCapture = startM7HCPUProfileCapture(
				sendContext,
				config.remoteSFU,
				*m7hCPUProfilePath,
			)
		}
		if config.remoteSFU != nil && *m7hGoroutineProfilePath != "" {
			onPublisherSendSample, onSFUReceiveSample, captureBeforeViewerReadinessAbort, waitForM7HGoroutineProfileCapture = startM7HGoroutineProfileCapture(
				sendContext,
				config.remoteSFU,
				*m7hGoroutineProfilePath,
				len(publisherSendStatsList),
			)
		}
		stopM7HRuntimeProbe = startM7HRuntimeProbe(
			"harness",
			publisherSendStatsList,
			onPublisherSendSample,
		)
		stopSFUReceivePoll = startM7HSFUReceivePoll(ctx, config.remoteSFU, onSFUReceiveSample)
	}
	defer func() {
		cancelSend()
		stopSFUReceivePoll()
		stopM7HRuntimeProbe()
		waitForM7HGoroutineProfileCapture()
		if err := waitForM7HCPUProfileCapture(); err != nil {
			fmt.Fprintf(os.Stderr, "m7h CPU profile capture ended without a complete profile: %v\n", err)
		}
	}()
	sendDone := make(chan sfuSendResult, 1)
	firstMeasurementTimestamp := sources[0].initialRTPTimestamp + sampleRTPTicks(videoFrames[0], 90000)
	// M7-H attempt 6: phase snapshot — streaming starts here.
	setRunPhase("streaming")
	go func() {
		framesByPublisher, err := sendSFUVideo(
			sendContext,
			sources,
			videoFrames,
			latencyClocks,
			firstMeasurementTimestamp,
			config.videoInterval,
			publisherSendStats,
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
		feedbackContext, cancelFeedback := context.WithTimeout(
			ctx,
			duration+sfuFeedbackCompletionGrace+sfuFeedbackWaitLimit,
		)
		defer cancelFeedback()

		feedbackPacer := time.NewTicker(sfuFeedbackPacingInterval)
		defer feedbackPacer.Stop()
		// M7-H attempt 8: send-phase STUN/dest snapshot (the send is running
		// by now) + time the readiness gate, which shares the 395 s feedback
		// deadline with the injection loop.
		snapshotSTUNStats("send-start")
		snapshotDestStats("send-start")
		readinessGateStart := time.Now()
		// Complete RTP readiness before serial feedback writes consume the
		// shared media deadline for viewers later in the list.
		for _, viewer := range viewers {
			if err := viewer.capture.waitForPackets(sendContext, viewer.key.TrackID, 5); err != nil {
				captureBeforeViewerReadinessAbort()
				stopCandidatePairSampler()
				if router != nil {
					captureViewerCandidatePairSnapshot(router, viewer)
					logViewerRTPPathDiagnosis(router, viewers, viewer)
				}
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("wait for viewer %s RTP: %w", viewer.id, err)
			}
			if _, exists := viewer.capture.snapshot(viewer.key.TrackID); !exists {
				captureBeforeViewerReadinessAbort()
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("viewer %s did not receive its requested track", viewer.id)
			}
		}
		// M7-H attempt 8: the gate is done — record how long it took (it
		// shares the 395 s feedback deadline with the injection loop).
		readinessGateNanos.Store(uint64(time.Since(readinessGateStart).Nanoseconds()))
		snapshotSTUNStats("send-mid")
		snapshotDestStats("send-mid")

		// M7-H attempt 9: parallel injection — the serial loop could not
		// absorb a 43 s blocking WriteRTCP (attempt 8: the top-4 slowest
		// injections were on LIVE, connected viewers). A bounded worker
		// pool runs the blocking calls; the pacer gates dispatch, not the
		// call. Viewers whose last ICE state is failed/disconnected are
		// skipped — a dead PC cannot receive feedback.
		type injectionJob struct {
			viewerID        string
			client          *webrtc.PeerConnection
			snapshot        streamSnapshot
			missingSequence uint16
		}
		type injectionResult struct {
			viewerID        string
			missingSequence uint16
			sentMissing     uint16
			err             error
		}
		jobs := make(chan injectionJob, len(viewers))
		results := make(chan injectionResult, len(viewers))
		var workerWG sync.WaitGroup
		workerBusyNs := make([]uint64, injectionWorkerCount)
		for w := 0; w < injectionWorkerCount; w++ {
			workerWG.Add(1)
			go func(workerIndex int) {
				defer workerWG.Done()
				for job := range jobs {
					sendStart := time.Now()
					sentMissingSequence, err := sendViewerFeedback(job.client, job.snapshot)
					sendDur := time.Since(sendStart)
					workerBusyNs[workerIndex] += uint64(sendDur.Nanoseconds())
					injectionSendCalls.Add(1)
					injectionSendTotalNs.Add(uint64(sendDur.Nanoseconds()))
					if sendDur > 50*time.Millisecond {
						injectionSendSlow50ms.Add(1)
					}
					recordInjection(job.viewerID, sendDur)
					results <- injectionResult{viewerID: job.viewerID, missingSequence: job.missingSequence, sentMissing: sentMissingSequence, err: err}
				}
			}(w)
		}
		poolStart := time.Now()
		dispatched := 0
		for index, viewer := range viewers {
			snapshot, exists := viewer.capture.snapshot(viewer.key.TrackID)
			if !exists {
				close(jobs)
				workerWG.Wait()
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("viewer %s did not receive its requested track", viewer.id)
			}
			// M7-H attempt 9: skip dead PCs before spending a blocking
			// WriteRTCP on them.
			if v, ok := pcLifetimes.Load("viewer-client:" + viewer.id); ok {
				if lt, ok2 := v.(*pcLifetime); ok2 && lt != nil {
					if iceState, _ := lt.lastICEState.Load().(string); iceState == "failed" {
						injectionSkippedDead.Add(1)
						continue
					} else if iceState == "disconnected" {
						injectionSkippedDisconnected.Add(1)
						continue
					}
				}
			}
			missingSequence := snapshot.LastSequenceNumber + 1000
			expectedNACKsMu.Lock()
			if expectedNACKs[viewer.key.TrackID] == nil {
				expectedNACKs[viewer.key.TrackID] = make(map[uint16]struct{})
			}
			expectedNACKs[viewer.key.TrackID][missingSequence] = struct{}{}
			expectedNACKsMu.Unlock()
			// Pace dispatch (the pacer gates dispatch, not the blocking
			// call): one tick between consecutive dispatches.
			if dispatched > 0 {
				select {
				case <-feedbackContext.Done():
					close(jobs)
					workerWG.Wait()
					injectionPoolWallNanos.Store(uint64(time.Since(poolStart).Nanoseconds()))
					recordWorkerBusy(workerBusyNs)
					// M7-H attempt 8: snapshot the run state at the pacing
					// deadline, before teardown closes anything.
					logPacingErrorAttribution(viewer.id)
					cancelSend()
					<-sendDone
					return sfuProofResult{}, fmt.Errorf(
						"feedback deadline ended while pacing viewer %s: %w",
						viewer.id,
						feedbackContext.Err(),
					)
				case <-feedbackPacer.C:
				}
			}
			jobs <- injectionJob{viewerID: viewer.id, client: viewer.client, snapshot: snapshot, missingSequence: missingSequence}
			dispatched++
			if (index+1)%500 == 0 {
				snapshotSTUNStats("send-mid")
				snapshotDestStats("send-mid")
			}
		}
		close(jobs)
		workerWG.Wait()
		injectionPoolWallNanos.Store(uint64(time.Since(poolStart).Nanoseconds()))
		recordWorkerBusy(workerBusyNs)
		// Collect results; fail on the first error / sequence mismatch, as
		// the serial loop did — only deferred until dispatch completes.
		for i := 0; i < dispatched; i++ {
			res := <-results
			if res.err != nil {
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf("send RTCP feedback from %s: %w", res.viewerID, res.err)
			}
			if res.sentMissing != res.missingSequence {
				cancelSend()
				<-sendDone
				return sfuProofResult{}, fmt.Errorf(
					"viewer %s NACK sequence changed: sent %d, expected %d",
					res.viewerID,
					res.sentMissing,
					res.missingSequence,
				)
			}
		}

		viewerKeys := make([]sfuTrackKey, len(viewers))
		for index, viewer := range viewers {
			viewerKeys[index] = viewer.key
		}
		expectedCounts := expectedFeedbackCounts(sources, viewerKeys)
		// M7-H attempt 6: phase snapshot — the feedback wait starts here.
		setRunPhase("wait-start")
		upstreamCounts, err = waitForSFUFeedback(
			feedbackContext,
			feedbackEvents,
			sources,
			expectedNACKs,
			expectedCounts,
		)
		// M7-H attempt 6: phase snapshot — the feedback wait ended here
		// (on both the pass and the timeout paths).
		setRunPhase("wait-end")
		if err != nil {
			cancelSend()
			<-sendDone
			if config.proofID == "m7h" && config.remoteSFU != nil && len(upstreamCounts) > 0 {
				logInjectionAttribution()
				viewerIDs := incompleteM7HViewerIDs(viewers, upstreamCounts, expectedCounts)
				if len(viewerIDs) > 0 {
					statsStarted := time.Now()
					statsContext, cancelStats := context.WithTimeout(ctx, 5*time.Second)
					fmt.Fprintf(os.Stderr,
						"m7h feedback-timeout SFU stats request: phase=started at=%s timeoutMs=5000 viewers=%v\n",
						statsStarted.Format(time.RFC3339Nano), viewerIDs)
					stats, statsErr := config.remoteSFU.stats(statsContext, viewerIDs, true)
					statsElapsed := time.Since(statsStarted)
					cancelStats()
					if statsErr != nil {
						fmt.Fprintf(os.Stderr,
							"m7h feedback-timeout SFU stats failed: at=%s elapsedMs=%d viewers=%v err=%v\n",
							time.Now().Format(time.RFC3339Nano), statsElapsed.Milliseconds(), viewerIDs, statsErr)
					} else {
						fmt.Fprintf(os.Stderr,
							"m7h feedback-timeout SFU stats complete: at=%s elapsedMs=%d viewers=%d rtpQueueDrops=%d rtpIntentionalShed=%d rtpWriteErrors=%d rtpKeyframeRecoverySamples=%d rtpKeyframeRecoveryNanos=%d rtpKeyframeRecoveryMaxNanos=%d forwardingErrors=%d sockets=%+v\n",
							time.Now().Format(time.RFC3339Nano), statsElapsed.Milliseconds(), len(viewerIDs),
							stats.RTPQueueDrops, stats.RTPIntentionalShed, stats.RTPWriteErrors,
							stats.RTPKeyframeRecoverySamples, stats.RTPKeyframeRecoveryNanos,
							stats.RTPKeyframeRecoveryMaxNanos, len(stats.ForwardingErrors), stats.Sockets)
						for _, viewer := range viewers {
							if _, selected := stats.FeedbackByViewer[viewer.id]; !selected {
								continue
							}
							fmt.Fprintf(os.Stderr,
								"m7h feedback-timeout viewer: id=%s track=%s publisherFeedback=%+v sfuFeedback=%+v candidatePairs=[%s]\n",
								viewer.id, viewer.key.TrackID, upstreamCounts[viewer.key.TrackID],
								stats.FeedbackByViewer[viewer.id],
								stats.ICECandidatePairsByViewer[viewer.id])
						}
					}
				}
			}
			if config.proofID == "m7h" && config.remoteSFU != nil && *m7hHeapProfilePath != "" {
				if profileErr := captureM7HHeapProfiles(ctx, config.remoteSFU, *m7hHeapProfilePath, "feedback-timeout"); profileErr != nil {
					err = errors.Join(err, fmt.Errorf("capture M7-H heap profiles after feedback timeout: %w", profileErr))
				}
			}
			return sfuProofResult{}, err
		}
	}
	<-sendContext.Done()
	stopM7HRuntimeProbe()
	cancelSend()
	sent := <-sendDone
	profileErr := waitForM7HCPUProfileCapture()
	if sent.err != nil {
		sendErr := fmt.Errorf("write publisher video: %w", sent.err)
		if profileErr != nil {
			sendErr = errors.Join(sendErr, profileErr)
		}
		return sfuProofResult{}, sendErr
	}
	if profileErr != nil {
		return sfuProofResult{}, profileErr
	}
	if config.proofID == "m7h" && config.remoteSFU != nil && *m7hHeapProfilePath != "" {
		if err := captureM7HHeapProfiles(ctx, config.remoteSFU, *m7hHeapProfilePath, "after-media"); err != nil {
			return sfuProofResult{}, err
		}
	}
	if err := ctx.Err(); err != nil {
		return sfuProofResult{}, fmt.Errorf("local SFU proof context ended: %w", err)
	}
	if config.measureLatency {
		time.Sleep(time.Second)
	} else {
		time.Sleep(100 * time.Millisecond)
	}

	var remoteStats m7hRemoteSFUStats
	if router == nil {
		viewerIDs := make([]string, 0, len(viewers))
		for _, viewer := range viewers {
			viewerIDs = append(viewerIDs, viewer.id)
		}
		remoteStats, err = config.remoteSFU.stats(ctx, viewerIDs, false)
		if err != nil {
			return sfuProofResult{}, fmt.Errorf("collect remote SFU stats: %w", err)
		}
	}
	rtpQueueDrops := uint64(0)
	rtpIntentionalShed := uint64(0)
	rtpWriteErrors := uint64(0)
	rtpKeyframeRecoverySamples := uint64(0)
	rtpKeyframeRecoveryNanos := uint64(0)
	rtpKeyframeRecoveryMaxNanos := uint64(0)
	if router != nil {
		rtpQueueDrops = router.rtpQueueDropped.Load()
		rtpIntentionalShed = router.rtpIntentionalShed.Load()
		rtpWriteErrors = router.rtpDropped.Load()
		rtpKeyframeRecoverySamples = router.rtpRecoverySamples.Load()
		rtpKeyframeRecoveryNanos = router.rtpRecoveryNanos.Load()
		rtpKeyframeRecoveryMaxNanos = router.rtpRecoveryMaxNanos.Load()
	} else {
		rtpQueueDrops = remoteStats.RTPQueueDrops
		rtpIntentionalShed = remoteStats.RTPIntentionalShed
		rtpWriteErrors = remoteStats.RTPWriteErrors
		rtpKeyframeRecoverySamples = remoteStats.RTPKeyframeRecoverySamples
		rtpKeyframeRecoveryNanos = remoteStats.RTPKeyframeRecoveryNanos
		rtpKeyframeRecoveryMaxNanos = remoteStats.RTPKeyframeRecoveryMaxNanos
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
		RTPQueueDrops:                  rtpQueueDrops,
		RTPIntentionalShed:             rtpIntentionalShed,
		RTPWriteErrors:                 rtpWriteErrors,
		RTPKeyframeRecoverySamples:     rtpKeyframeRecoverySamples,
		RTPKeyframeRecoveryNanos:       rtpKeyframeRecoveryNanos,
		RTPKeyframeRecoveryMaxNanos:    rtpKeyframeRecoveryMaxNanos,
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
			if router != nil {
				viewerResult.FeedbackForwarded = router.subscriptionFeedback(viewer.id, viewer.key)
			} else {
				viewerResult.FeedbackForwarded = remoteStats.FeedbackByViewer[viewer.id]
			}
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
	if router != nil {
		result.ForwardingErrors = router.errorsSnapshot()
	} else {
		result.ForwardingErrors = remoteStats.ForwardingErrors
		socketTotals := aggregateSFUSocketCounts(viewers)
		socketTotals.routerSockets = remoteStats.Sockets.RouterSockets
		socketTotals.routerWrites = remoteStats.Sockets.RouterWrites
		socketTotals.routerSTUNWrites = remoteStats.Sockets.RouterSTUNWrites
		socketTotals.routerNonSTUNWrites = remoteStats.Sockets.RouterNonSTUNWrites
		fmt.Fprintf(os.Stderr,
			"m7h split socket totals: routerSockets=%d routerWrites=%d routerSTUNWrites=%d routerNonSTUNWrites=%d clientSockets=%d clientReads=%d clientSTUNReads=%d clientNonSTUNReads=%d clientZeroReads=%d clientZeroNonSTUNReads=%d\n",
			socketTotals.routerSockets, socketTotals.routerWrites, socketTotals.routerSTUNWrites,
			socketTotals.routerNonSTUNWrites, socketTotals.clientSockets, socketTotals.clientReads,
			socketTotals.clientSTUNReads, socketTotals.clientNonSTUNReads,
			socketTotals.clientsZeroReads, socketTotals.clientsZeroNonSTUNReads)
	}
	if config.logRTPPath && router != nil {
		for _, viewer := range viewers {
			logViewerRTPPathDiagnosis(router, viewers, viewer)
		}
	}

	if router == nil {
		cleanup, cleanupErr := config.remoteSFU.cleanup(ctx)
		if cleanupErr != nil {
			return sfuProofResult{}, fmt.Errorf("clean up remote SFU state: %w", cleanupErr)
		}
		result.CleanupVerified = cleanup.CleanupVerified
		if !cleanup.CleanupVerified {
			return sfuProofResult{}, fmt.Errorf(
				"remote SFU cleanup left tracks=%d viewers=%d subscriptions=%d authorizations=%d",
				cleanup.TracksRemaining,
				cleanup.ViewersRemaining,
				cleanup.SubscriptionsRemaining,
				cleanup.AuthorizationsRemaining,
			)
		}
	} else {
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
	}
	if len(result.ForwardingErrors) != 0 {
		return sfuProofResult{}, fmt.Errorf("SFU forwarding errors: %s", strings.Join(result.ForwardingErrors, "; "))
	}
	if config.measureLatency {
		measurementPass := sfuMeasurementPass(result, len(config.viewerTrackIndexes), config.exerciseRTCP)
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
	measureReadTiming bool,
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
	if measureReadTiming {
		capture.readTiming = &m7hRTPReadTiming{}
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
				readStarted := time.Now()
				packet, _, err := track.ReadRTP()
				if capture.readTiming != nil {
					capture.readTiming.record(time.Since(readStarted), err)
				}
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

func (r *sfuRouter) subscriptionPacketPath(
	viewerID string,
	key sfuTrackKey,
) (uint64, uint64, uint64, uint64, uint16) {
	r.mu.RLock()
	viewer := r.viewers[viewerID]
	var subscription *sfuSubscription
	if viewer != nil {
		subscription = viewer.subscriptions[key]
	}
	source := r.tracks[key]
	r.mu.RUnlock()
	if subscription == nil || source == nil {
		return 0, 0, 0, 0, 0
	}
	return source.rtpPacketsRead.Load(),
		subscription.rtpQueueEnqueued.Load(),
		subscription.rtpQueueDropped.Load(),
		subscription.rtpWriteSucceeded.Load(),
		source.latestSequence()
}

func (r *sfuRouter) viewerPeer(viewerID string) *webrtc.PeerConnection {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if viewer := r.viewers[viewerID]; viewer != nil {
		return viewer.peer
	}
	return nil
}

func sendSFUVideo(
	ctx context.Context,
	sources []sfuMediaSource,
	frames []media.Sample,
	clocks map[string]*FrameClock,
	firstFrameTimestamp uint32,
	videoInterval time.Duration,
	publisherSendStats map[string]*m7hPublisherSendStats,
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
				publisherSendStats[publisherID],
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
	sendStats *m7hPublisherSendStats,
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
		case scheduledAt := <-ticker.C:
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
			sendStats.record(scheduledAt, time.Now())
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
	expectedNACKs map[string]map[uint16]struct{},
	expectedNACKsMu *sync.RWMutex,
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
			if event.kind == "nack" {
				// Keep unrelated stack NACKs out of the shared control-evidence channel.
				expectedNACKsMu.RLock()
				relevant := nackContainsExpectedSequence(
					event.nacks,
					expectedNACKs[trackID],
				)
				expectedNACKsMu.RUnlock()
				if !relevant {
					continue
				}
			}
			select {
			case events <- event:
			case <-ctx.Done():
				return
			}
		}
	}
}

func nackContainsExpectedSequence(
	pairs []rtcp.NackPair,
	expected map[uint16]struct{},
) bool {
	for sequence := range expected {
		for _, pair := range pairs {
			if sequence == pair.PacketID {
				return true
			}
			offset := uint16(sequence - pair.PacketID)
			if offset > 0 && offset <= 16 &&
				pair.LostPackets&(1<<(offset-1)) != 0 {
				return true
			}
		}
	}
	return false
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
				if event.trackID == "stream-0253" && sourceSSRCs[event.trackID] == 0 {
					fmt.Fprintf(
						os.Stderr,
						"publisher SSRC baseline: track=%s expectedPublisherSSRC=%d source=first accepted upstream NACK MediaSSRC\n",
						event.trackID,
						event.mediaSSRC,
					)
				}
				sourceSSRCs[event.trackID] = event.mediaSSRC
				current.NACKForwarded++
				counts[event.trackID] = current
			case "pli":
				if event.mediaSSRC == 0 && sourceSSRCs[event.trackID] == 0 {
					// A PLI carrying no SSRC before any baseline exists
					// (same subscribe-time timing as the M7-H attempt-1
					// FIR abort). Skip it; the completeness check still
					// requires a valid PLI after the baseline is set.
					fmt.Fprintf(
						os.Stderr,
						"PLI before SSRC baseline: track=%s (skipped, waiting for baseline)\n",
						event.trackID,
					)
					continue
				}
				if event.mediaSSRC == 0 || sourceSSRCs[event.trackID] != 0 && event.mediaSSRC != sourceSSRCs[event.trackID] {
					return nil, fmt.Errorf("publisher received PLI for wrong SSRC on %s: %d", event.trackID, event.mediaSSRC)
				}
				if event.trackID == "stream-0253" && sourceSSRCs[event.trackID] == 0 {
					fmt.Fprintf(
						os.Stderr,
						"publisher SSRC baseline: track=%s expectedPublisherSSRC=%d source=first accepted upstream PLI MediaSSRC\n",
						event.trackID,
						event.mediaSSRC,
					)
				}
				sourceSSRCs[event.trackID] = event.mediaSSRC
				current.PLIForwarded++
				counts[event.trackID] = current
			case "fir":
				if sourceSSRCs[event.trackID] == 0 {
					// A viewer sends its first FIR (keyframe request) at
					// subscribe, before any NACK/PLI has set this track's
					// SSRC baseline. At 3,000 publishers the feedback
					// timing spreads out and the FIR beats the baseline
					// (stream-1885, M7-H attempt 1). Skipping it is safe:
					// the FIR still reaches the publisher via the router;
					// this loop only measures. The completeness check
					// below still requires a valid FIR after the baseline
					// is set before the proof can pass. Do NOT adopt the
					// FIR target as the baseline — it must come from an
					// upstream NACK/PLI MediaSSRC.
					fmt.Fprintf(
						os.Stderr,
						"FIR before SSRC baseline: track=%s mediaSSRC=%d targets=%v (skipped, waiting for baseline)\n",
						event.trackID,
						event.mediaSSRC,
						event.targets,
					)
					continue
				}
				if event.mediaSSRC != 0 || len(event.targets) != 1 ||
					event.targets[0] != sourceSSRCs[event.trackID] {
					if event.trackID == "stream-0253" {
						fmt.Fprintf(
							os.Stderr,
							"publisher FIR SSRC check: track=%s mediaSSRC=%d carriedTargets=%v expectedPublisherSSRC=%d expectedSource=first accepted upstream NACK/PLI MediaSSRC\n",
							event.trackID,
							event.mediaSSRC,
							event.targets,
							sourceSSRCs[event.trackID],
						)
					}
					return nil, fmt.Errorf(
						"publisher received FIR for wrong SSRC on %s: mediaSSRC=%d targets=%v expectedPublisherSSRC=%d",
						event.trackID,
						event.mediaSSRC,
						event.targets,
						sourceSSRCs[event.trackID],
					)
				}
				current.FIRForwarded++
				counts[event.trackID] = current
			}
		case <-ctx.Done():
			return counts, fmt.Errorf("timed out waiting for translated NACK/PLI/FIR from publisher: %w", ctx.Err())
		case <-ticker.C:
			if time.Since(feedbackStarted) > sfuFeedbackWaitLimit {
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
				return counts, fmt.Errorf("feedback wait timed out after %s: %d/%d tracks complete; nackZero=%d pliZero=%d firZero=%d maxN=%d maxP=%d maxF=%d; incomplete sample: %v",
					sfuFeedbackWaitLimit, completeTracks, len(counts), nackZero, pliZero, firZero, maxNACK, maxPLI, maxFIR, incomplete)
			}
		}
	}
}

type sfuSocketAggregates struct {
	routerSockets           int
	clientSockets           int
	routerWrites            uint64
	routerSTUNWrites        uint64
	routerNonSTUNWrites     uint64
	clientReads             uint64
	clientSTUNReads         uint64
	clientNonSTUNReads      uint64
	clientsZeroReads        uint64
	clientsZeroNonSTUNReads uint64
}

func aggregateSFUSocketCounts(viewers []viewerEndpoint) sfuSocketAggregates {
	var totals sfuSocketAggregates
	seenRouterSockets := make(map[*packetReadCountingConn]struct{}, len(viewers))
	seenClientSockets := make(map[*packetReadCountingConn]struct{}, len(viewers))
	for _, viewer := range viewers {
		if conn := viewer.routerSocketConn; conn != nil {
			// Router mux counters are shared by viewers; count each socket once.
			if _, seen := seenRouterSockets[conn]; !seen {
				seenRouterSockets[conn] = struct{}{}
				totals.routerSockets++
				totals.routerWrites += conn.packetsWritten.Load()
				totals.routerSTUNWrites += conn.stunPacketsWritten.Load()
				totals.routerNonSTUNWrites += conn.nonSTUNPacketsWritten.Load()
			}
		}
		if conn := viewer.socketConn; conn != nil {
			if _, seen := seenClientSockets[conn]; !seen {
				seenClientSockets[conn] = struct{}{}
				totals.clientSockets++
				totals.clientReads += conn.packetsRead.Load()
				totals.clientSTUNReads += conn.stunPacketsRead.Load()
				totals.clientNonSTUNReads += conn.nonSTUNPacketsRead.Load()
				// M7-H attempt 4: a client socket that bound but
				// read nothing is a dead port from the router's
				// point of view — every write to it is a no-socket
				// drop in the kernel counters.
				if conn.packetsRead.Load() == 0 {
					totals.clientsZeroReads++
				}
				if conn.nonSTUNPacketsRead.Load() == 0 {
					totals.clientsZeroNonSTUNReads++
				}
			}
		}
	}
	return totals
}

func remoteSocketAggregates(viewers []viewerEndpoint) m7hRemoteSocketAggregates {
	totals := aggregateSFUSocketCounts(viewers)
	return m7hRemoteSocketAggregates{
		RouterSockets:           totals.routerSockets,
		ClientSockets:           totals.clientSockets,
		RouterWrites:            totals.routerWrites,
		RouterSTUNWrites:        totals.routerSTUNWrites,
		RouterNonSTUNWrites:     totals.routerNonSTUNWrites,
		ClientReads:             totals.clientReads,
		ClientSTUNReads:         totals.clientSTUNReads,
		ClientNonSTUNReads:      totals.clientNonSTUNReads,
		ClientsZeroReads:        totals.clientsZeroReads,
		ClientsZeroNonSTUNReads: totals.clientsZeroNonSTUNReads,
	}
}

// logRouterFeedbackDiagnosis reports per-subscription feedback and whole-run
// socket totals on failure so the diagnosis survives without result JSON.
func logRouterFeedbackDiagnosis(router *sfuRouter, viewers []viewerEndpoint) {
	errs := router.errorsSnapshot()
	var total sfuFeedbackCounts
	socketTotals := aggregateSFUSocketCounts(viewers)
	subsWithPLI, subsWithFIR, subsTotal := 0, 0, 0
	subsWithPLIReceived, subsWithFIRReceived := 0, 0
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
		total.PLIReceived += counts.PLIReceived
		total.FIRReceived += counts.FIRReceived
		if counts.PLIForwarded > 0 {
			subsWithPLI++
		}
		if counts.FIRForwarded > 0 {
			subsWithFIR++
		}
		if counts.PLIReceived > 0 {
			subsWithPLIReceived++
		}
		if counts.FIRReceived > 0 {
			subsWithFIRReceived++
		}
	}
	fmt.Fprintf(os.Stderr, "router feedback diagnosis: subs=%d subsWithPLI=%d subsWithFIR=%d subsWithPLIReceived=%d subsWithFIRReceived=%d totalNACKReceived=%d totalNACKRetransmitted=%d totalNACKDuplicatesSkipped=%d totalNACKSequencesCapped=%d totalNACKEnqueued=%d totalNACKDroppedQueueFull=%d totalNACKDroppedStale=%d nackQueueDepth=%d totalNACKForwarded=%d totalPLIForwarded=%d totalFIRForwarded=%d totalPLIReceived=%d totalFIRReceived=%d rtpQueueDrops=%d rtpWriteErrors=%d routerErrors=%d\n",
		subsTotal, subsWithPLI, subsWithFIR, subsWithPLIReceived, subsWithFIRReceived, total.NACKReceived, total.NACKRetransmitted, total.NACKDuplicatesSkipped, total.NACKSequencesCapped, total.NACKEnqueued, total.NACKDroppedQueueFull, total.NACKDroppedStale, total.NACKQueueDepth, total.NACKForwarded, total.PLIForwarded, total.FIRForwarded, total.PLIReceived, total.FIRReceived, router.rtpQueueDropped.Load(), router.rtpDropped.Load(), len(errs))
	fmt.Fprintf(
		os.Stderr,
		"whole-run socket aggregates: viewers=%d routerSockets=%d totalRouterWrites=%d routerWriteSTUN=%d routerWriteNonSTUN=%d clientSockets=%d totalClientReads=%d clientReadSTUN=%d clientReadNonSTUN=%d clientsZeroReads=%d clientsZeroNonSTUNReads=%d totalNACKs=%d totalRetransmits=%d\n",
		len(viewers),
		socketTotals.routerSockets,
		socketTotals.routerWrites,
		socketTotals.routerSTUNWrites,
		socketTotals.routerNonSTUNWrites,
		socketTotals.clientSockets,
		socketTotals.clientReads,
		socketTotals.clientSTUNReads,
		socketTotals.clientNonSTUNReads,
		socketTotals.clientsZeroReads,
		socketTotals.clientsZeroNonSTUNReads,
		total.NACKReceived,
		total.NACKRetransmitted,
	)
	for i, e := range errs {
		if i >= 10 {
			break
		}
		fmt.Fprintf(os.Stderr, "router error %d: %s\n", i, e)
	}
}

func logViewerRTPPathDiagnosis(router *sfuRouter, viewers []viewerEndpoint, failed viewerEndpoint) {
	for _, viewer := range viewers {
		if viewer.key != failed.key {
			continue
		}
		sourceRead, queued, queueDropped, writeSucceeded, sourceLastSequence :=
			router.subscriptionPacketPath(viewer.id, viewer.key)
		received, exists := viewer.capture.snapshot(viewer.key.TrackID)
		serverPeerStats := "missing"
		if peer := router.viewerPeer(viewer.id); peer != nil {
			serverPeerStats = viewerPeerPacketDiagnostics(peer)
		}
		socketReadPackets := uint64(0)
		socketNonSTUNPackets := uint64(0)
		socketSTUNPackets := uint64(0)
		socketReadCounted := false
		if viewer.socketConn != nil {
			socketReadPackets = viewer.socketConn.packetsRead.Load()
			socketNonSTUNPackets = viewer.socketConn.nonSTUNPacketsRead.Load()
			socketSTUNPackets = viewer.socketConn.stunPacketsRead.Load()
			socketReadCounted = true
		}
		routerSocketWrites := uint64(0)
		routerSocketSTUNWrites := uint64(0)
		routerSocketNonSTUNWrites := uint64(0)
		routerSocketWriteBytes := uint64(0)
		routerSocketDestination := ""
		routerSocketWriteCounted := false
		if viewer.routerSocketConn != nil {
			routerSocketWrites = viewer.routerSocketConn.packetsWritten.Load()
			routerSocketSTUNWrites = viewer.routerSocketConn.stunPacketsWritten.Load()
			routerSocketNonSTUNWrites = viewer.routerSocketConn.nonSTUNPacketsWritten.Load()
			routerSocketWriteBytes = viewer.routerSocketConn.bytesWritten.Load()
			if destination := viewer.routerSocketConn.firstNonSTUNWriteDestination.Load(); destination != nil {
				routerSocketDestination = *destination
			}
			routerSocketWriteCounted = true
		}
		clientSocketLocalAddress := ""
		if viewer.socketConn != nil {
			clientSocketLocalAddress = viewer.socketConn.LocalAddr().String()
		}
		clientCandidatePairs, routerCandidatePairs := "", ""
		if viewer.candidatePairs != nil {
			clientCandidatePairs, routerCandidatePairs = viewer.candidatePairs.load()
		}
		fmt.Fprintf(
			os.Stderr,
			"viewer RTP path: viewer=%s track=%s sourceRead=%d enqueued=%d queueDropped=%d writeSucceeded=%d remoteReceived=%d routerSocketWrites=%d routerSocketWriteSTUN=%d routerSocketWriteNonSTUN=%d routerSocketWriteBytes=%d routerSocketDestination=%s clientSocketLocalAddress=%s routerSocketWriteCounted=%t socketReadPackets=%d socketReadNonSTUN=%d socketReadSTUN=%d socketReadCounted=%t clientCandidatePairsLast=[%s] routerCandidatePairsLast=[%s] trackBound=%t sourceLastSeq=%d remoteLastSeq=%d clientPeerStats={%s} serverPeerStats={%s}\n",
			viewer.id,
			viewer.key.TrackID,
			sourceRead,
			queued,
			queueDropped,
			writeSucceeded,
			received.PacketsReceived,
			routerSocketWrites,
			routerSocketSTUNWrites,
			routerSocketNonSTUNWrites,
			routerSocketWriteBytes,
			routerSocketDestination,
			clientSocketLocalAddress,
			routerSocketWriteCounted,
			socketReadPackets,
			socketNonSTUNPackets,
			socketSTUNPackets,
			socketReadCounted,
			clientCandidatePairs,
			routerCandidatePairs,
			exists,
			sourceLastSequence,
			received.LastSequenceNumber,
			viewerPeerPacketDiagnostics(viewer.client),
			serverPeerStats,
		)
	}
}

func viewerPeerPacketDiagnostics(peer *webrtc.PeerConnection) string {
	var inbound []string
	var pairs []string
	report := peer.GetStats()
	candidates := make(map[string]webrtc.ICECandidateStats)
	for _, stats := range report {
		if candidate, ok := stats.(webrtc.ICECandidateStats); ok {
			candidates[candidate.ID] = candidate
		}
	}
	for _, stats := range report {
		switch stat := stats.(type) {
		case webrtc.InboundRTPStreamStats:
			inbound = append(inbound, fmt.Sprintf(
				"%s packets=%d lost=%d nack=%d",
				stat.ID,
				stat.PacketsReceived,
				stat.PacketsLost,
				stat.NACKCount,
			))
		case webrtc.ICECandidatePairStats:
			pairs = append(pairs, fmt.Sprintf(
				"%s:%s nominated=%t local=%s remote=%s sent=%d received=%d",
				stat.ID,
				stat.State,
				stat.Nominated,
				formatICECandidate(candidates[stat.LocalCandidateID]),
				formatICECandidate(candidates[stat.RemoteCandidateID]),
				stat.PacketsSent,
				stat.PacketsReceived,
			))
		}
	}
	sort.Strings(inbound)
	sort.Strings(pairs)
	return fmt.Sprintf(
		"pc=%s ice=%s inbound=[%s] pairs=[%s]",
		peer.ConnectionState(),
		peer.ICEConnectionState(),
		strings.Join(inbound, ";"),
		strings.Join(pairs, ";"),
	)
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

func incompleteM7HViewerIDs(
	viewers []viewerEndpoint,
	counts map[string]sfuFeedbackCounts,
	expectedCounts map[string]uint64,
) []string {
	const maxViewerDiagnostics = 1
	viewerIDs := make([]string, 0, maxViewerDiagnostics)
	seenTracks := make(map[string]struct{}, maxViewerDiagnostics)
	for _, viewer := range viewers {
		trackID := viewer.key.TrackID
		expected, exists := expectedCounts[trackID]
		if !exists || expected == 0 {
			continue
		}
		current := counts[trackID]
		if current.NACKForwarded >= expected &&
			current.PLIForwarded >= expected &&
			current.FIRForwarded >= expected {
			continue
		}
		if _, seen := seenTracks[trackID]; seen {
			continue
		}
		seenTracks[trackID] = struct{}{}
		viewerIDs = append(viewerIDs, viewer.id)
		if len(viewerIDs) == maxViewerDiagnostics {
			break
		}
	}
	return viewerIDs
}
