package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/pion/webrtc/v4"
)

func TestSFUTURNConfigFromEnv(t *testing.T) {
	t.Setenv("HAMI_SFU_TURN_URL", "turn:127.0.0.1:3478")
	t.Setenv("HAMI_SFU_TURN_USERNAME", "alice")
	t.Setenv("HAMI_SFU_TURN_PASSWORD", "s3cret-turn-password")
	t.Setenv("HAMI_SFU_TURN_REALM", "hami-test")
	t.Setenv("HAMI_SFU_TURN_PASSWORD_FILE", "")
	config, configured, err := sfuTURNConfigFromEnv()
	if err != nil {
		t.Fatalf("sfuTURNConfigFromEnv: %v", err)
	}
	if !configured {
		t.Fatal("TURN config reported not configured with username+password set")
	}
	if config.URL != "turn:127.0.0.1:3478" || config.Username != "alice" || config.Realm != "hami-test" {
		t.Fatalf("TURN config mismatch: %+v", config)
	}
	iceConfig := sfuTURNICEConfiguration(config, true)
	if len(iceConfig.ICEServers) != 1 || iceConfig.ICEServers[0].URLs[0] != "turn:127.0.0.1:3478" {
		t.Fatalf("ICE config mismatch: %+v", iceConfig)
	}
	if iceConfig.ICETransportPolicy != webrtc.ICETransportPolicyRelay {
		t.Fatalf("ICE transport policy = %v, want relay", iceConfig.ICETransportPolicy)
	}

	t.Setenv("HAMI_SFU_TURN_USERNAME", "")
	if _, configured, err := sfuTURNConfigFromEnv(); err != nil {
		t.Fatalf("sfuTURNConfigFromEnv without username: %v", err)
	} else if configured {
		t.Fatal("TURN config reported configured without a username")
	}
}

func TestSFUTURNWrongCredentialsRejected(t *testing.T) {
	// A TURN server must reject an unknown user / wrong password at
	// allocation time. The client side of that is a relay-only peer
	// that can never gather a relay candidate; here we prove the
	// server side directly by attempting an allocation with the
	// wrong password through a relay-only peer and asserting no
	// relay candidate appears (gathering completes with none).
	turnServer, username, _ := testSFUTURNServer(t, "hami-test")
	defer func() { _ = turnServer.Close() }()

	api := webrtc.NewAPI()
	peer, err := api.NewPeerConnection(sfuTURNICEConfiguration(sfuTURNConfig{
		URL:      turnServer.URL(),
		Username: username,
		Password: "definitely-the-wrong-password",
		Realm:    "hami-test",
	}, true))
	if err != nil {
		t.Fatalf("create peer: %v", err)
	}
	defer func() { _ = peer.Close() }()
	if _, err := peer.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo); err != nil {
		t.Fatalf("add transceiver: %v", err)
	}
	offer, err := peer.CreateOffer(nil)
	if err != nil {
		t.Fatalf("create offer: %v", err)
	}
	gathered := webrtc.GatheringCompletePromise(peer)
	if err := peer.SetLocalDescription(offer); err != nil {
		t.Fatalf("set local description: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	select {
	case <-gathered:
	case <-ctx.Done():
		t.Fatal("gathering did not complete with wrong TURN credentials")
	}
	// With wrong credentials the peer must have no relay candidate.
	report := peer.GetStats()
	for _, stats := range report {
		if candidate, ok := stats.(webrtc.ICECandidateStats); ok {
			if candidate.CandidateType == webrtc.ICECandidateTypeRelay {
				t.Fatalf("peer gathered a relay candidate with wrong TURN credentials: %+v", candidate)
			}
		}
	}
}

// testSFUTURNServer starts a TURN server on an ephemeral loopback port
// with one random-password user. It returns the server, the username,
// and the (test-only) password.
func testSFUTURNServer(t *testing.T, realm string) (*sfuTURNServer, string, string) {
	t.Helper()
	var passwordBytes [16]byte
	if _, err := rand.Read(passwordBytes[:]); err != nil {
		t.Fatalf("random TURN password: %v", err)
	}
	password := hex.EncodeToString(passwordBytes[:])
	username := "part3-turn-user"
	server, err := startSFUTURNServer("127.0.0.1:0", realm, map[string]string{username: password})
	if err != nil {
		t.Fatalf("start TURN server: %v", err)
	}
	t.Cleanup(func() { _ = server.Close() })
	return server, username, password
}

// TestSFUTURNRelayCarriesMedia is the Part 3 relay proof: a relay-only
// publisher and a relay-only viewer connect through the TURN server,
// the nominated pair on both client PeerConnections is a relay pair,
// and H.264 frames flow publisher -> router -> viewer.
func TestSFUTURNRelayCarriesMedia(t *testing.T) {
	fixture, err := base64.StdEncoding.DecodeString(testH264AccessUnit)
	if err != nil {
		t.Fatal(err)
	}
	frames, err := readH264Frames(bytes.NewReader(fixture))
	if err != nil {
		t.Fatalf("read embedded H.264 test frame: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	turnServer, username, password := testSFUTURNServer(t, "hami-test")
	relayConfig := sfuTURNICEConfiguration(sfuTURNConfig{
		URL:      turnServer.URL(),
		Username: username,
		Password: password,
		Realm:    "hami-test",
	}, true)
	t.Logf("part3 TURN server: url=%s realm=hami-test", turnServer.URL())

	// Router side: loopback API + mux, as in the other SFU proofs.
	routerSettings, routerMux, err := loopbackSettings(true, 0)
	if err != nil {
		t.Fatalf("router loopback settings: %v", err)
	}
	defer func() {
		if closeErr := routerMux.Close(); closeErr != nil {
			t.Logf("close router mux: %v", closeErr)
		}
	}()
	routerAPI := webrtc.NewAPI(webrtc.WithSettingEngine(routerSettings))
	router, err := newSFURouter(routerAPI)
	if err != nil {
		t.Fatalf("newSFURouter: %v", err)
	}
	defer func() { _ = router.close() }()

	// Publisher client: plain API, relay-only via TURN.
	publisherAPI := webrtc.NewAPI()
	publisherClient, err := publisherAPI.NewPeerConnection(relayConfig)
	if err != nil {
		t.Fatalf("create publisher client: %v", err)
	}
	defer func() { _ = publisherClient.Close() }()
	videoTrack, err := webrtc.NewTrackLocalStaticSample(webrtc.RTPCodecCapability{
		MimeType:    webrtc.MimeTypeH264,
		ClockRate:   90000,
		SDPFmtpLine: "level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42001f",
	}, "hami-video", "hami-turn-relay")
	if err != nil {
		t.Fatalf("create publisher video track: %v", err)
	}
	audioTrack, err := webrtc.NewTrackLocalStaticSample(webrtc.RTPCodecCapability{
		MimeType:  webrtc.MimeTypePCMU,
		ClockRate: audioSampleRate,
		Channels:  1,
	}, "hami-audio", "hami-turn-relay")
	if err != nil {
		t.Fatalf("create publisher audio track: %v", err)
	}
	videoSender, err := publisherClient.AddTrack(videoTrack)
	if err != nil {
		t.Fatalf("add publisher video track: %v", err)
	}
	audioSender, err := publisherClient.AddTrack(audioTrack)
	if err != nil {
		t.Fatalf("add publisher audio track: %v", err)
	}
	drainRTCP(videoSender)
	drainRTCP(audioSender)

	routerPublisherPeer, err := router.registerPublisher(routerAPI, "turn-relay-publisher")
	if err != nil {
		t.Fatalf("register publisher: %v", err)
	}
	if err := negotiateLoopbackPeers(ctx, "turn-relay publisher", publisherClient, routerPublisherPeer, "m=audio", "m=video"); err != nil {
		t.Fatalf("negotiate publisher pair: %v", err)
	}
	key := sfuTrackKey{PublisherID: "turn-relay-publisher", TrackID: "hami-video"}
	source := sfuMediaSource{key: key, track: videoTrack}
	if err := videoTrack.WriteSample(frames[0]); err != nil {
		t.Fatalf("register publisher track: %v", err)
	}
	if err := router.waitForTracks(ctx, []sfuMediaSource{source}); err != nil {
		t.Fatalf("wait for publisher track: %v", err)
	}

	// Viewer client: plain API, relay-only via TURN, recvonly video.
	viewerAPI := webrtc.NewAPI()
	viewerClient, err := viewerAPI.NewPeerConnection(relayConfig)
	if err != nil {
		t.Fatalf("create viewer client: %v", err)
	}
	defer func() { _ = viewerClient.Close() }()
	var receivedAudio, receivedVideo streamCounter
	trackErrors := make(chan error, 2)
	viewerClient.OnTrack(func(track *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		counter := &receivedVideo
		if strings.EqualFold(track.Codec().MimeType, webrtc.MimeTypePCMU) {
			counter = &receivedAudio
		}
		if err := counter.bind(track.Codec().MimeType, uint32(track.SSRC()), uint8(track.PayloadType())); err != nil {
			select {
			case trackErrors <- err:
			default:
			}
			return
		}
		go func() {
			for {
				packet, _, err := track.ReadRTP()
				if err != nil {
					if ctx.Err() == nil && !errors.Is(err, io.EOF) {
						select {
						case trackErrors <- fmt.Errorf("read viewer RTP: %w", err):
						default:
						}
					}
					return
				}
				counter.record(packet.SequenceNumber, packet.Timestamp, len(packet.Payload))
			}
		}()
	})
	if _, err := viewerClient.AddTransceiverFromKind(
		webrtc.RTPCodecTypeVideo,
		webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly},
	); err != nil {
		t.Fatalf("add viewer receive transceiver: %v", err)
	}
	routerViewerPeer, err := routerAPI.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("create router viewer peer: %v", err)
	}
	if err := router.registerViewer("turn-relay-viewer", routerViewerPeer); err != nil {
		t.Fatalf("register viewer: %v", err)
	}
	if err := router.authorizeSubscription("turn-relay-viewer", key); err != nil {
		t.Fatalf("authorize viewer: %v", err)
	}
	if err := router.subscribe("turn-relay-viewer", key); err != nil {
		t.Fatalf("subscribe viewer: %v", err)
	}
	if err := negotiateLoopbackPeers(ctx, "turn-relay viewer", viewerClient, routerViewerPeer, "m=video"); err != nil {
		t.Fatalf("negotiate viewer pair: %v", err)
	}

	// Send media for 2s. The viewer is video-only (one recvonly
	// video transceiver, subscribed to the video track), so wait for
	// video RTP only — audio is published but never subscribed to,
	// and waitForReceivedMedia would wait forever for audio packets
	// that can never arrive.
	sendContext, cancelSend := context.WithTimeout(ctx, 2*time.Second)
	sendDone := make(chan sendResult, 1)
	go func() {
		counts, sendErr := sendMedia(sendContext, audioTrack, videoTrack, frames)
		sendDone <- sendResult{counts: counts, err: sendErr}
	}()
	<-sendContext.Done()
	cancelSend()
	sent := <-sendDone
	if sent.err != nil {
		t.Fatalf("write publisher media: %v", sent.err)
	}
	videoReceived := uint64(0)
	mediaDeadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(mediaDeadline) {
		videoReceived = receivedVideo.snapshotResult().PacketsReceived
		if videoReceived > 0 {
			break
		}
		select {
		case err := <-trackErrors:
			t.Fatalf("viewer track error: %v", err)
		case <-time.After(100 * time.Millisecond):
		case <-ctx.Done():
			t.Fatalf("viewer media wait canceled: %v", ctx.Err())
		}
	}
	videoSnapshot := receivedVideo.snapshotResult()
	if videoSnapshot.PacketsReceived == 0 {
		t.Fatal("viewer received no video RTP through the TURN relay")
	}

	// Relay proof: the nominated pair on BOTH client PCs must be relay.
	for name, peer := range map[string]*webrtc.PeerConnection{
		"publisher": publisherClient,
		"viewer":    viewerClient,
	} {
		localType, remoteType, diagnostics, ok := sfuRelayPairTypes(peer)
		t.Logf("part3 TURN relay pair: %s %s", name, diagnostics)
		fmt.Fprintf(os.Stderr, "part3 TURN relay pair: %s %s\n", name, diagnostics)
		if !ok {
			t.Fatalf("%s client has no nominated succeeded ICE pair", name)
		}
		if localType != webrtc.ICECandidateTypeRelay {
			t.Fatalf("%s client local candidate type = %s, want relay (%s)", name, localType, diagnostics)
		}
		if remoteType != webrtc.ICECandidateTypeHost {
			t.Fatalf("%s client remote candidate type = %s, want host (%s)", name, remoteType, diagnostics)
		}
	}
	t.Logf("part3 TURN relay proof: video frames sent=%d video packets received=%d",
		sent.counts.videoFrames, videoSnapshot.PacketsReceived)
}
