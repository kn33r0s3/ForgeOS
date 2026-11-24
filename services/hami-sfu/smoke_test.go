//go:build smoke

// Smoke tests for the hami-sfu loopback path: real publishers and
// subscribers, both Pion clients, talking to the server over 127.0.0.1.
// The publisher sends fake H.264 RTP packets; the test passes only if the
// subscriber receives them through the SFU.
//
// TestSmokeLoopback runs with no auth (auth == nil, as in Stage 1).
// TestSmokeAuth runs with per-user HMAC tokens: bad token, wrong-role
// token and no token must all fail 401, and a real publish + subscribe
// with valid tokens must move frames.
//
// Build-tagged `smoke` because the VM blocks UDP loopback — run only on
// the Mac: go test -tags smoke -count=1 -v ./...
package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

// postSDPWithToken POSTs an SDP offer with an optional Bearer token and
// requires the given status. With wantStatus 200 it returns the SDP
// answer; otherwise it returns the error body.
func postSDPWithToken(t *testing.T, client *http.Client, url, offer, token string, wantStatus int) string {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, url, strings.NewReader(offer))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read answer from %s: %v", url, err)
	}
	if resp.StatusCode != wantStatus {
		t.Fatalf("POST %s: status %d, want %d: %s", url, resp.StatusCode, wantStatus, strings.TrimSpace(string(body)))
	}
	return string(body)
}

// offerWithCandidates creates an offer and waits for ICE gathering so the
// offer carries its host candidates (there is no trickle channel here).
func offerWithCandidates(t *testing.T, pc *webrtc.PeerConnection) string {
	t.Helper()
	offer, err := pc.CreateOffer(nil)
	if err != nil {
		t.Fatalf("CreateOffer: %v", err)
	}
	if err := pc.SetLocalDescription(offer); err != nil {
		t.Fatalf("SetLocalDescription: %v", err)
	}
	gathered := webrtc.GatheringCompletePromise(pc)
	select {
	case <-gathered:
	case <-time.After(10 * time.Second):
		t.Fatal("ICE gathering timed out")
	}
	return pc.LocalDescription().SDP
}

// waitConnected polls until the PeerConnection reaches Connected, or fails.
func waitConnected(t *testing.T, name string, pc *webrtc.PeerConnection) {
	t.Helper()
	deadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(deadline) {
		if pc.ConnectionState() == webrtc.PeerConnectionStateConnected {
			t.Logf("%s connected", name)
			return
		}
		if pc.ConnectionState() == webrtc.PeerConnectionStateFailed ||
			pc.ConnectionState() == webrtc.PeerConnectionStateClosed {
			t.Fatalf("%s connection failed/closed (state %s)", name, pc.ConnectionState())
		}
		time.Sleep(100 * time.Millisecond)
	}
	t.Fatalf("%s never connected (state %s)", name, pc.ConnectionState())
}

// smokeFlow runs one full publish -> subscribe flow against baseURL/room.
// pubToken/subToken are the Bearer tokens to use; "" sends no header
// (no-auth server). It passes only if the subscriber receives at least
// wantReceived frames.
func smokeFlow(t *testing.T, client *http.Client, baseURL, room, pubToken, subToken string, wantReceived int) {
	t.Helper()

	// ---- Publisher: one H.264 video track. ----
	pubPC, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("publisher PC: %v", err)
	}
	defer pubPC.Close()
	videoTrack, err := webrtc.NewTrackLocalStaticRTP(
		webrtc.RTPCodecCapability{MimeType: webrtc.MimeTypeH264, ClockRate: 90000},
		"smoke-video", "smoke-stream",
	)
	if err != nil {
		t.Fatalf("video track: %v", err)
	}
	if _, err := pubPC.AddTrack(videoTrack); err != nil {
		t.Fatalf("AddTrack: %v", err)
	}
	pubOffer := offerWithCandidates(t, pubPC)
	pubAnswer := postSDPWithToken(t, client, baseURL+"/api/publish/"+room, pubOffer, pubToken, http.StatusOK)
	if err := pubPC.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeAnswer, SDP: pubAnswer}); err != nil {
		t.Fatalf("publisher SetRemoteDescription: %v", err)
	}
	waitConnected(t, "publisher", pubPC)

	// ---- Publisher sends frames continuously until the test ends. ----
	// The server only creates the track entry when the first RTP packet
	// arrives (Pion fires OnTrack on first packet), so sending must
	// start BEFORE waiting for the room listing. An IDR goes out every
	// 30th frame so a late subscriber can sync.
	stopSend := make(chan struct{})
	defer close(stopSend)
	go func() {
		seq := uint16(1)
		ts := uint32(0)
		sent := 0
		for {
			select {
			case <-stopSend:
				t.Logf("publisher sent %d frames", sent)
				return
			default:
			}
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
			time.Sleep(30 * time.Millisecond)
		}
	}()

	// Wait until the server lists the published track.
	deadline := time.Now().Add(10 * time.Second)
	for {
		req, err := http.NewRequest(http.MethodGet, baseURL+"/api/rooms/"+room, nil)
		if err != nil {
			t.Fatalf("new request: %v", err)
		}
		if subToken != "" {
			req.Header.Set("Authorization", "Bearer "+subToken)
		}
		resp, err := client.Do(req)
		if err == nil {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK && strings.Contains(string(body), "smoke-video") {
				t.Logf("server lists track: %s", strings.TrimSpace(string(body)))
				break
			}
		}
		if time.Now().After(deadline) {
			t.Fatal("server never listed the published track")
		}
		time.Sleep(200 * time.Millisecond)
	}

	// ---- Subscriber: one recvonly video transceiver, count packets. ----
	var received atomic.Int64
	subPC, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("subscriber PC: %v", err)
	}
	defer subPC.Close()
	subPC.OnTrack(func(remote *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		t.Logf("subscriber OnTrack: %s %s", remote.Kind(), remote.Codec().MimeType)
		go func() {
			for {
				if _, _, err := remote.ReadRTP(); err != nil {
					return
				}
				received.Add(1)
			}
		}()
	})
	if _, err := subPC.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo,
		webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionRecvonly}); err != nil {
		t.Fatalf("AddTransceiver: %v", err)
	}
	subOffer := offerWithCandidates(t, subPC)
	subAnswer := postSDPWithToken(t, client, baseURL+"/api/subscribe/"+room, subOffer, subToken, http.StatusOK)
	if err := subPC.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeAnswer, SDP: subAnswer}); err != nil {
		t.Fatalf("subscriber SetRemoteDescription: %v", err)
	}
	waitConnected(t, "subscriber", subPC)

	// Wait for at least wantReceived frames at the subscriber.
	deadline = time.Now().Add(30 * time.Second)
	for {
		if n := received.Load(); n >= int64(wantReceived) {
			t.Logf("SMOKE PASS: subscriber received %d frames (wanted >= %d)", n, wantReceived)
			return
		}
		if time.Now().After(deadline) {
			t.Fatalf("SMOKE FAIL: subscriber received only %d frames after 30s (wanted >= %d)", received.Load(), wantReceived)
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func TestSmokeLoopback(t *testing.T) {
	// Server under test: same wiring as main(), no auth (auth == nil),
	// loopback UDP. Uses s.routes() so the smoke test exercises the
	// production route table.
	api, err := newAPI(17501, false)
	if err != nil {
		t.Fatalf("newAPI: %v", err)
	}
	s := &server{
		api:            api,
		auth:           nil,
		maxRooms:       8,
		maxPublishers:  8,
		maxSubscribers: 50,
		rooms:          make(map[string]*room),
	}
	httpSrv := httptest.NewServer(s.routes())
	defer httpSrv.Close()
	smokeFlow(t, httpSrv.Client(), httpSrv.URL, "smoke", "", "", 20)
}

func TestSmokeAuth(t *testing.T) {
	// Server under test: same wiring as main(), WITH per-user HMAC auth.
	key := []byte("0123456789abcdef0123456789abcdef")
	v, err := newAuthVerifier(key)
	if err != nil {
		t.Fatalf("newAuthVerifier: %v", err)
	}
	api, err := newAPI(17502, false)
	if err != nil {
		t.Fatalf("newAPI: %v", err)
	}
	s := &server{
		api:            api,
		auth:           v,
		maxRooms:       8,
		maxPublishers:  8,
		maxSubscribers: 50,
		rooms:          make(map[string]*room),
	}
	httpSrv := httptest.NewServer(s.routes())
	defer httpSrv.Close()
	client := httpSrv.Client()

	pubTok, err := v.mint("authroom", "alice", []string{tokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint publish token: %v", err)
	}
	subTok, err := v.mint("authroom", "bob", []string{tokenRoleSubscribe}, time.Hour)
	if err != nil {
		t.Fatalf("mint subscribe token: %v", err)
	}

	// ---- Rejection probes, before any real publish. ----
	// A throwaway PC just to produce a well-formed SDP offer.
	probePC, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("probe PC: %v", err)
	}
	defer probePC.Close()
	if _, err := probePC.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo,
		webrtc.RTPTransceiverInit{Direction: webrtc.RTPTransceiverDirectionSendonly}); err != nil {
		t.Fatalf("probe AddTransceiver: %v", err)
	}
	probeOffer := offerWithCandidates(t, probePC)
	postSDPWithToken(t, client, httpSrv.URL+"/api/publish/authroom", probeOffer, "", http.StatusUnauthorized)
	t.Logf("no token -> 401 OK")
	postSDPWithToken(t, client, httpSrv.URL+"/api/publish/authroom", probeOffer, "garbage.token", http.StatusUnauthorized)
	t.Logf("bad token -> 401 OK")
	postSDPWithToken(t, client, httpSrv.URL+"/api/publish/authroom", probeOffer, subTok, http.StatusUnauthorized)
	t.Logf("wrong-role (subscribe) token on publish -> 401 OK")
	postSDPWithToken(t, client, httpSrv.URL+"/api/subscribe/authroom", probeOffer, pubTok, http.StatusUnauthorized)
	t.Logf("wrong-role (publish) token on subscribe -> 401 OK")

	// ---- Real publish + subscribe with valid tokens must move frames. ----
	smokeFlow(t, client, httpSrv.URL, "authroom", pubTok, subTok, 5)
}
