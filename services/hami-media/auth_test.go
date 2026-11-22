package main

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/pion/ice/v4"
	"github.com/pion/webrtc/v4"
)

const testSFUAuthKey = "part3-test-hmac-key-0123456789abcdef"

func testSFUAuthVerifier(t *testing.T) *sfuAuthVerifier {
	t.Helper()
	verifier, err := newSFUAuthVerifier([]byte(testSFUAuthKey), "default")
	if err != nil {
		t.Fatalf("newSFUAuthVerifier: %v", err)
	}
	return verifier
}

func TestSFUTokenMintVerifyRoundTrip(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	token, err := verifier.mintSFUToken("default", "alice", []string{sfuTokenRolePublish, sfuTokenRoleSubscribe}, time.Hour)
	if err != nil {
		t.Fatalf("mint token: %v", err)
	}
	if token == "" {
		t.Fatal("minted an empty token")
	}
	for _, role := range []string{sfuTokenRolePublish, sfuTokenRoleSubscribe} {
		claims, err := verifier.verify(token, role)
		if err != nil {
			t.Fatalf("verify token for role %s: %v", role, err)
		}
		if claims.Room != "default" || claims.Subject != "alice" {
			t.Fatalf("claims mismatch: %+v", claims)
		}
	}
}

func TestSFUTokenExpiredRejected(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	// mint() refuses a past expiry, so sign an already-expired claim
	// directly with the test helper below.
	token := signSFUTokenClaims(t, verifier, sfuTokenClaims{
		Room:  "default",
		Roles: []string{sfuTokenRolePublish},
		Exp:   time.Now().Add(-time.Hour).Unix(),
		Iat:   time.Now().Add(-2 * time.Hour).Unix(),
	})
	if _, err := verifier.verify(token, sfuTokenRolePublish); err == nil {
		t.Fatal("expired token was accepted")
	} else if !isSFUAuthError(err, errSFUAuthExpired) {
		t.Fatalf("expired token gave %v, want expired", err)
	}
}

// signSFUTokenClaims signs arbitrary claims with the verifier's key,
// bypassing mint()'s future-expiry rule, so tests can build expired
// tokens. It mirrors mint()'s wire format exactly.
func signSFUTokenClaims(t *testing.T, verifier *sfuAuthVerifier, claims sfuTokenClaims) string {
	t.Helper()
	payload, err := json.Marshal(claims)
	if err != nil {
		t.Fatalf("encode claims: %v", err)
	}
	payloadB64 := base64.RawURLEncoding.EncodeToString(payload)
	mac := hmac.New(sha256.New, verifier.key)
	_, _ = mac.Write([]byte(payloadB64))
	return payloadB64 + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func TestSFUTokenWrongKeyRejected(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	token, err := verifier.mintSFUToken("default", "alice", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint token: %v", err)
	}
	other, err := newSFUAuthVerifier([]byte("part3-other-hmac-key-0123456789abc"), "default")
	if err != nil {
		t.Fatalf("newSFUAuthVerifier (other key): %v", err)
	}
	if _, err := other.verify(token, sfuTokenRolePublish); err == nil {
		t.Fatal("token minted under another key was accepted")
	} else if !isSFUAuthError(err, errSFUAuthBadSignature) {
		t.Fatalf("wrong-key token gave %v, want bad signature", err)
	}
}

func TestSFUTokenMissingRejected(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	if _, err := verifier.verify("", sfuTokenRolePublish); err == nil {
		t.Fatal("missing token was accepted")
	} else if !isSFUAuthError(err, errSFUAuthMissingToken) {
		t.Fatalf("missing token gave %v, want missing", err)
	}
}

func TestSFUTokenWrongRoomRejected(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	token, err := verifier.mintSFUToken("other-room", "alice", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint token: %v", err)
	}
	if _, err := verifier.verify(token, sfuTokenRolePublish); err == nil {
		t.Fatal("token for another room was accepted")
	} else if !isSFUAuthError(err, errSFUAuthWrongRoom) {
		t.Fatalf("wrong-room token gave %v, want wrong room", err)
	}
}

func TestSFUTokenWrongRoleRejected(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	token, err := verifier.mintSFUToken("default", "alice", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint token: %v", err)
	}
	if _, err := verifier.verify(token, sfuTokenRoleSubscribe); err == nil {
		t.Fatal("publish-only token was accepted for subscribe")
	} else if !isSFUAuthError(err, errSFUAuthWrongRole) {
		t.Fatalf("wrong-role token gave %v, want wrong role", err)
	}
}

func TestSFUTokenTamperedPayloadRejected(t *testing.T) {
	verifier := testSFUAuthVerifier(t)
	token, err := verifier.mintSFUToken("default", "alice", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint token: %v", err)
	}
	// Flip one character of the payload half; the signature must fail.
	tampered := "A" + token[1:]
	if tampered == token {
		t.Fatal("tamper did not change the token")
	}
	if _, err := verifier.verify(tampered, sfuTokenRolePublish); err == nil {
		t.Fatal("tampered token was accepted")
	} else if !isSFUAuthError(err, errSFUAuthBadSignature) {
		t.Fatalf("tampered token gave %v, want bad signature", err)
	}
}

func TestLoadSFUAuthKeyFromFileAndEnv(t *testing.T) {
	keyPath := filepath.Join(t.TempDir(), "hmac.key")
	if err := os.WriteFile(keyPath, []byte(testSFUAuthKey+"\n"), 0o600); err != nil {
		t.Fatalf("write key file: %v", err)
	}
	t.Setenv("HAMI_SFU_HMAC_KEY_FILE", keyPath)
	t.Setenv("HAMI_SFU_HMAC_KEY", "")
	key, err := loadSFUAuthKey()
	if err != nil {
		t.Fatalf("load key from file: %v", err)
	}
	if string(key) != testSFUAuthKey {
		t.Fatalf("key from file = %q, want the test key", string(key))
	}

	t.Setenv("HAMI_SFU_HMAC_KEY_FILE", "")
	t.Setenv("HAMI_SFU_HMAC_KEY", testSFUAuthKey)
	key, err = loadSFUAuthKey()
	if err != nil {
		t.Fatalf("load key from env: %v", err)
	}
	if string(key) != testSFUAuthKey {
		t.Fatalf("key from env = %q, want the test key", string(key))
	}

	t.Setenv("HAMI_SFU_HMAC_KEY", "too-short")
	if _, err := loadSFUAuthKey(); err == nil {
		t.Fatal("short key was accepted")
	}

	t.Setenv("HAMI_SFU_HMAC_KEY", "")
	if _, err := loadSFUAuthKey(); err == nil {
		t.Fatal("missing key was accepted")
	}
}

// isSFUAuthError reports whether err is (or wraps) the sentinel.
func isSFUAuthError(err, sentinel error) bool {
	for err != nil {
		if err == sentinel {
			return true
		}
		type unwrapper interface{ Unwrap() error }
		u, ok := err.(unwrapper)
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}

// testSFUHTTPServer builds a live signalling server (the same handlers
// runM7HSFUServer registers) backed by a real router, with auth on.
func testSFUHTTPServer(t *testing.T) (*httptest.Server, *sfuAuthVerifier) {
	t.Helper()
	verifier := testSFUAuthVerifier(t)
	settings, mux, err := loopbackSettings(true, 0)
	if err != nil {
		t.Fatalf("loopback settings: %v", err)
	}
	t.Cleanup(func() {
		if mux != nil {
			_ = mux.Close()
		}
	})
	api := webrtc.NewAPI(webrtc.WithSettingEngine(settings))
	router, err := newSFURouter(api)
	if err != nil {
		t.Fatalf("newSFURouter: %v", err)
	}
	// handlePublisher writes into this map; runM7HSFUServer
	// initializes it, so the test server must too.
	router.m7hPublisherReceiveStats = make(map[string]*m7hPublisherReceiveStats)
	t.Cleanup(func() { _ = router.close() })
	server := &m7hRemoteSFUServer{
		apis:            []*webrtc.API{api},
		muxByShard:      []ice.UDPMux{mux},
		settingsByShard: []webrtc.SettingEngine{settings},
		publishers:      make(map[string]m7hRemotePublisherState),
		viewers:         make(map[string]viewerEndpoint),
		auth:            verifier,
	}
	server.router = router
	m := http.NewServeMux()
	m.HandleFunc("/publisher", server.handlePublisher("test-bearer"))
	m.HandleFunc("/viewer", server.handleViewer("test-bearer"))
	httpServer := httptest.NewServer(m)
	t.Cleanup(httpServer.Close)
	return httpServer, verifier
}

func testSFUPostJSON(t *testing.T, url, bearer string, body any) (int, string) {
	t.Helper()
	encoded, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("encode request: %v", err)
	}
	request, err := http.NewRequestWithContext(context.Background(), http.MethodPost, url, bytes.NewReader(encoded))
	if err != nil {
		t.Fatalf("create request: %v", err)
	}
	request.Header.Set("Authorization", "Bearer "+bearer)
	request.Header.Set("Content-Type", "application/json")
	// Bounded client: if the server never answers (e.g. ICE gathering
	// stalls in a sandbox without UDP), fail instead of hanging.
	client := &http.Client{Timeout: 30 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	defer response.Body.Close()
	responseBody, _ := io.ReadAll(response.Body)
	return response.StatusCode, string(responseBody)
}

func testSFUClientOffer(t *testing.T) string {
	t.Helper()
	settings, mux, err := loopbackSettings(false, 0)
	if err != nil {
		t.Fatalf("client loopback settings: %v", err)
	}
	t.Cleanup(func() {
		if mux != nil {
			_ = mux.Close()
		}
	})
	api := webrtc.NewAPI(webrtc.WithSettingEngine(settings))
	peer, err := api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("create client peer: %v", err)
	}
	t.Cleanup(func() { _ = peer.Close() })
	if _, err := peer.AddTransceiverFromKind(webrtc.RTPCodecTypeVideo); err != nil {
		t.Fatalf("add client transceiver: %v", err)
	}
	offer, err := peer.CreateOffer(nil)
	if err != nil {
		t.Fatalf("create client offer: %v", err)
	}
	gathered := webrtc.GatheringCompletePromise(peer)
	if err := peer.SetLocalDescription(offer); err != nil {
		t.Fatalf("set client local description: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	select {
	case <-gathered:
	case <-ctx.Done():
		t.Fatalf("gather client offer: %v", ctx.Err())
	}
	if peer.LocalDescription() == nil {
		t.Fatal("client local description is missing")
	}
	return peer.LocalDescription().SDP
}

func TestSFUHTTPAuthPublisher(t *testing.T) {
	httpServer, verifier := testSFUHTTPServer(t)
	offer := testSFUClientOffer(t)

	// Missing token -> 401.
	status, _ := testSFUPostJSON(t, httpServer.URL+"/publisher", "test-bearer", m7hRemoteSDPRequest{
		PublisherID: "pub-1",
		Offer:       offer,
	})
	if status != http.StatusUnauthorized {
		t.Fatalf("publisher without token: status = %d, want 401", status)
	}

	// Expired token -> 401. mint() refuses a past expiry, so the
	// expired-token unit case lives in TestSFUTokenExpiredRejected;
	// here a wrong-room token is the second rejection case.
	wrongRoom, err := verifier.mintSFUToken("other-room", "alice", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint wrong-room token: %v", err)
	}
	status, _ = testSFUPostJSON(t, httpServer.URL+"/publisher", "test-bearer", m7hRemoteSDPRequest{
		PublisherID: "pub-1",
		Offer:       offer,
		Token:       wrongRoom,
	})
	if status != http.StatusUnauthorized {
		t.Fatalf("publisher with wrong-room token: status = %d, want 401", status)
	}

	// Wrong-role token (subscribe-only) -> 401.
	subscribeOnly, err := verifier.mintSFUToken("default", "alice", []string{sfuTokenRoleSubscribe}, time.Hour)
	if err != nil {
		t.Fatalf("mint subscribe-only token: %v", err)
	}
	status, _ = testSFUPostJSON(t, httpServer.URL+"/publisher", "test-bearer", m7hRemoteSDPRequest{
		PublisherID: "pub-1",
		Offer:       offer,
		Token:       subscribeOnly,
	})
	if status != http.StatusUnauthorized {
		t.Fatalf("publisher with subscribe-only token: status = %d, want 401", status)
	}

	// Valid publish token -> 200 with an SDP answer.
	valid, err := verifier.mintSFUToken("default", "pub-1", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint valid token: %v", err)
	}
	status, body := testSFUPostJSON(t, httpServer.URL+"/publisher", "test-bearer", m7hRemoteSDPRequest{
		PublisherID: "pub-1",
		Offer:       offer,
		Token:       valid,
	})
	if status != http.StatusOK {
		t.Fatalf("publisher with valid token: status = %d, body = %s, want 200", status, body)
	}
	var response m7hRemoteSDPResponse
	if err := json.Unmarshal([]byte(body), &response); err != nil {
		t.Fatalf("decode publisher response: %v", err)
	}
	if response.Answer == "" {
		t.Fatal("publisher response carries no SDP answer")
	}
	fmt.Fprintf(os.Stderr, "part3 auth http test: valid publish accepted, answer bytes=%d\n", len(response.Answer))
}

func TestSFUHTTPAuthViewer(t *testing.T) {
	httpServer, verifier := testSFUHTTPServer(t)
	offer := testSFUClientOffer(t)
	key := sfuTrackKey{PublisherID: "pub-1", TrackID: "track-1"}

	// Missing token -> 401 (rejected before any track wait).
	status, _ := testSFUPostJSON(t, httpServer.URL+"/viewer", "test-bearer", m7hRemoteViewerRequest{
		ViewerID: "viewer-1",
		Key:      key,
		Offer:    offer,
	})
	if status != http.StatusUnauthorized {
		t.Fatalf("viewer without token: status = %d, want 401", status)
	}

	// Publish-only token -> 401 for subscribe.
	publishOnly, err := verifier.mintSFUToken("default", "viewer-1", []string{sfuTokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint publish-only token: %v", err)
	}
	status, _ = testSFUPostJSON(t, httpServer.URL+"/viewer", "test-bearer", m7hRemoteViewerRequest{
		ViewerID: "viewer-1",
		Key:      key,
		Offer:    offer,
		Token:    publishOnly,
	})
	if status != http.StatusUnauthorized {
		t.Fatalf("viewer with publish-only token: status = %d, want 401", status)
	}

	// Wrong-key token -> 401.
	other, _ := newSFUAuthVerifier([]byte("part3-other-hmac-key-0123456789abc"), "default")
	wrongKey, err := other.mintSFUToken("default", "viewer-1", []string{sfuTokenRoleSubscribe}, time.Hour)
	if err != nil {
		t.Fatalf("mint wrong-key token: %v", err)
	}
	status, _ = testSFUPostJSON(t, httpServer.URL+"/viewer", "test-bearer", m7hRemoteViewerRequest{
		ViewerID: "viewer-1",
		Key:      key,
		Offer:    offer,
		Token:    wrongKey,
	})
	if status != http.StatusUnauthorized {
		t.Fatalf("viewer with wrong-key token: status = %d, want 401", status)
	}
}
