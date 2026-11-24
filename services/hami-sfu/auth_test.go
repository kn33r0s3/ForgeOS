// Stage 2 tests: per-user HMAC tokens + room API.
//
// Written BEFORE the implementation (auth.go / main.go changes) so the
// fail-before run proves each test fails without the fix: the tests
// reference symbols that do not exist in the Stage 1 tree, so `go test`
// fails to build there. After the fix lands they must all pass.
//
// Rejection cases covered (each is its own test):
//   - wrong key, expired token, wrong room, wrong role, malformed token,
//     tampered payload, missing token.
package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/pion/webrtc/v4"
)

var (
	testHMACKey      = []byte("0123456789abcdef0123456789abcdef") // exactly 32 bytes
	testHMACKeyOther = []byte("fedcba9876543210fedcba9876543210") // exactly 32 bytes
)

// mustVerifier builds a verifier with the test key or fails the test.
func mustVerifier(t *testing.T) *authVerifier {
	t.Helper()
	v, err := newAuthVerifier(testHMACKey)
	if err != nil {
		t.Fatalf("newAuthVerifier: %v", err)
	}
	return v
}

// craftToken signs arbitrary claims with the given key, bypassing mint's
// validation, so tests can build expired / wrong-room tokens.
func craftToken(t *testing.T, key []byte, claims tokenClaims) string {
	t.Helper()
	payload, err := json.Marshal(claims)
	if err != nil {
		t.Fatalf("marshal claims: %v", err)
	}
	return signTokenPayload(key, payload)
}

func TestMintAndVerifyRoundTrip(t *testing.T) {
	v := mustVerifier(t)
	tok, err := v.mint("demo", "alice", []string{tokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint: %v", err)
	}
	claims, err := v.authorize(tok, "demo", tokenRolePublish)
	if err != nil {
		t.Fatalf("authorize: %v", err)
	}
	if claims.Room != "demo" || claims.Subject != "alice" {
		t.Fatalf("claims = %+v, want room=demo sub=alice", claims)
	}
	if len(claims.Roles) != 1 || claims.Roles[0] != tokenRolePublish {
		t.Fatalf("claims roles = %v, want [publish]", claims.Roles)
	}
	if claims.Exp <= time.Now().Unix() {
		t.Fatalf("claims exp = %d, want in the future", claims.Exp)
	}
}

func TestVerifyRejectsWrongKey(t *testing.T) {
	v := mustVerifier(t)
	other, err := newAuthVerifier(testHMACKeyOther)
	if err != nil {
		t.Fatalf("newAuthVerifier(other): %v", err)
	}
	tok, err := other.mint("demo", "alice", []string{tokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint with other key: %v", err)
	}
	if _, err := v.authorize(tok, "demo", tokenRolePublish); err != errAuthBadSignature {
		t.Fatalf("authorize with wrong-key token: err = %v, want errAuthBadSignature", err)
	}
}

func TestVerifyRejectsExpiredToken(t *testing.T) {
	v := mustVerifier(t)
	tok := craftToken(t, testHMACKey, tokenClaims{
		Room: "demo", Roles: []string{tokenRolePublish}, Subject: "alice",
		Exp: time.Now().Add(-time.Hour).Unix(),
	})
	if _, err := v.authorize(tok, "demo", tokenRolePublish); err != errAuthExpired {
		t.Fatalf("authorize expired token: err = %v, want errAuthExpired", err)
	}
}

func TestVerifyRejectsWrongRoom(t *testing.T) {
	v := mustVerifier(t)
	tok, err := v.mint("demo", "alice", []string{tokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint: %v", err)
	}
	if _, err := v.authorize(tok, "other-room", tokenRolePublish); err != errAuthWrongRoom {
		t.Fatalf("authorize wrong-room token: err = %v, want errAuthWrongRoom", err)
	}
}

func TestVerifyRejectsWrongRole(t *testing.T) {
	v := mustVerifier(t)
	tok, err := v.mint("demo", "alice", []string{tokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint: %v", err)
	}
	if _, err := v.authorize(tok, "demo", tokenRoleSubscribe); err != errAuthWrongRole {
		t.Fatalf("authorize publish-only token for subscribe: err = %v, want errAuthWrongRole", err)
	}
}

func TestVerifyRejectsMalformedToken(t *testing.T) {
	v := mustVerifier(t)
	bad := []string{
		"",
		"no-dot-at-all",
		"a.b.c",
		"!!!.!!!",
		"eyJyb29tIjoiZGVtbyJ9.!!!",
		strings.Repeat("x", tokenMaxLength+1),
	}
	for _, tok := range bad {
		if _, err := v.authorize(tok, "demo", tokenRolePublish); err == nil {
			t.Fatalf("authorize(%q): got nil error, want rejection", tok)
		}
	}
}

func TestVerifyRejectsMissingToken(t *testing.T) {
	v := mustVerifier(t)
	if _, err := v.authorize("", "demo", tokenRolePublish); err != errAuthMissingToken {
		t.Fatalf("authorize empty token: err = %v, want errAuthMissingToken", err)
	}
}

func TestVerifyRejectsTamperedPayload(t *testing.T) {
	v := mustVerifier(t)
	tok, err := v.mint("demo", "alice", []string{tokenRolePublish}, time.Hour)
	if err != nil {
		t.Fatalf("mint: %v", err)
	}
	parts := strings.Split(tok, ".")
	if len(parts) != 2 {
		t.Fatalf("minted token has %d parts, want 2", len(parts))
	}
	// Flip the room inside the payload: re-encode claims for another room
	// but keep the original signature — the signature must not match.
	tampered := craftToken(t, testHMACKey, tokenClaims{
		Room: "other", Roles: []string{tokenRolePublish}, Subject: "alice",
		Exp: time.Now().Add(time.Hour).Unix(),
	})
	tamperedParts := strings.Split(tampered, ".")
	forged := tamperedParts[0] + "." + parts[1]
	if _, err := v.authorize(forged, "other", tokenRolePublish); err != errAuthBadSignature {
		t.Fatalf("authorize tampered token: err = %v, want errAuthBadSignature", err)
	}
}

func TestMintRejectsBadInput(t *testing.T) {
	v := mustVerifier(t)
	cases := []struct {
		name    string
		room    string
		subject string
		roles   []string
		ttl     time.Duration
	}{
		{"empty subject", "demo", "", []string{tokenRolePublish}, time.Hour},
		{"no roles", "demo", "alice", nil, time.Hour},
		{"unknown role", "demo", "alice", []string{"admin"}, time.Hour},
		{"zero ttl", "demo", "alice", []string{tokenRolePublish}, 0},
		{"negative ttl", "demo", "alice", []string{tokenRolePublish}, -time.Hour},
		{"ttl over max", "demo", "alice", []string{tokenRolePublish}, 25 * time.Hour},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if _, err := v.mint(c.room, c.subject, c.roles, c.ttl); err == nil {
				t.Fatalf("mint(%+v): got nil error, want rejection", c)
			}
		})
	}
}

func TestNewAuthVerifierRejectsShortKey(t *testing.T) {
	if _, err := newAuthVerifier([]byte("too-short")); err == nil {
		t.Fatal("newAuthVerifier(short key): got nil error, want rejection")
	}
}

func TestReadHMACKeyFileMode(t *testing.T) {
	dir := t.TempDir()
	loose := filepath.Join(dir, "loose.key")
	if err := os.WriteFile(loose, testHMACKey, 0o644); err != nil {
		t.Fatalf("write loose key file: %v", err)
	}
	if _, err := readHMACKeyFile(loose); err == nil {
		t.Fatal("readHMACKeyFile(0644): got nil error, want mode rejection")
	}
	strict := filepath.Join(dir, "strict.key")
	if err := os.WriteFile(strict, append(append([]byte(nil), testHMACKey...), '\n'), 0o600); err != nil {
		t.Fatalf("write strict key file: %v", err)
	}
	key, err := readHMACKeyFile(strict)
	if err != nil {
		t.Fatalf("readHMACKeyFile(0600): %v", err)
	}
	if !bytes.Equal(key, testHMACKey) {
		t.Fatalf("readHMACKeyFile(0600): key mismatch (trailing newline must be trimmed)")
	}
}

func TestLoadHMACKeySources(t *testing.T) {
	dir := t.TempDir()
	keyFile := filepath.Join(dir, "k.key")
	if err := os.WriteFile(keyFile, testHMACKey, 0o600); err != nil {
		t.Fatalf("write key file: %v", err)
	}

	t.Run("flag file wins", func(t *testing.T) {
		t.Setenv("HAMI_SFU_HMAC_KEY_FILE", "")
		t.Setenv("HAMI_SFU_HMAC_KEY", "")
		key, err := loadHMACKey(keyFile)
		if err != nil {
			t.Fatalf("loadHMACKey(flag): %v", err)
		}
		if !bytes.Equal(key, testHMACKey) {
			t.Fatal("loadHMACKey(flag): key mismatch")
		}
	})
	t.Run("env file", func(t *testing.T) {
		t.Setenv("HAMI_SFU_HMAC_KEY_FILE", keyFile)
		t.Setenv("HAMI_SFU_HMAC_KEY", "")
		key, err := loadHMACKey("")
		if err != nil {
			t.Fatalf("loadHMACKey(env file): %v", err)
		}
		if !bytes.Equal(key, testHMACKey) {
			t.Fatal("loadHMACKey(env file): key mismatch")
		}
	})
	t.Run("env key", func(t *testing.T) {
		t.Setenv("HAMI_SFU_HMAC_KEY_FILE", "")
		t.Setenv("HAMI_SFU_HMAC_KEY", string(testHMACKey))
		key, err := loadHMACKey("")
		if err != nil {
			t.Fatalf("loadHMACKey(env key): %v", err)
		}
		if !bytes.Equal(key, testHMACKey) {
			t.Fatal("loadHMACKey(env key): key mismatch")
		}
	})
	t.Run("both env sources rejected", func(t *testing.T) {
		t.Setenv("HAMI_SFU_HMAC_KEY_FILE", keyFile)
		t.Setenv("HAMI_SFU_HMAC_KEY", string(testHMACKey))
		if _, err := loadHMACKey(""); err == nil {
			t.Fatal("loadHMACKey(both env): got nil error, want rejection")
		}
	})
	t.Run("no source rejected", func(t *testing.T) {
		t.Setenv("HAMI_SFU_HMAC_KEY_FILE", "")
		t.Setenv("HAMI_SFU_HMAC_KEY", "")
		if _, err := loadHMACKey(""); err == nil {
			t.Fatal("loadHMACKey(none): got nil error, want rejection")
		}
	})
}

// ---- HTTP-level auth tests (httptest, no real WebRTC needed) ----

// newAuthTestServer builds a server with a verifier and the production
// routes, using a default (non-networked) WebRTC API: handlers that pass
// auth fail later at SDP parsing, which is enough to prove auth passed.
func newAuthTestServer(t *testing.T) (*server, *authVerifier, *httptest.Server) {
	t.Helper()
	v := mustVerifier(t)
	api := webrtc.NewAPI()
	s := &server{
		api:            api,
		auth:           v,
		maxRooms:       8,
		maxPublishers:  8,
		maxSubscribers: 50,
		rooms:          make(map[string]*room),
	}
	srv := httptest.NewServer(s.routes())
	t.Cleanup(srv.Close)
	return s, v, srv
}

func mintFor(t *testing.T, v *authVerifier, room, sub string, roles []string) string {
	t.Helper()
	tok, err := v.mint(room, sub, roles, time.Hour)
	if err != nil {
		t.Fatalf("mint: %v", err)
	}
	return tok
}

func postReq(t *testing.T, client *http.Client, url, token, body string) *http.Response {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, url, strings.NewReader(body))
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
	return resp
}

func readBody(t *testing.T, resp *http.Response) string {
	t.Helper()
	defer resp.Body.Close()
	b, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	return string(b)
}

func TestPublishRejectsBadToken(t *testing.T) {
	_, _, srv := newAuthTestServer(t)
	resp := postReq(t, srv.Client(), srv.URL+"/api/publish/demo", "this.is.not.a.token", "bad-sdp")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("publish with bad token: status %d, want 401: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

func TestPublishRejectsNoToken(t *testing.T) {
	_, _, srv := newAuthTestServer(t)
	resp := postReq(t, srv.Client(), srv.URL+"/api/publish/demo", "", "bad-sdp")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("publish with no token: status %d, want 401: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

func TestPublishRejectsWrongRoleToken(t *testing.T) {
	_, v, srv := newAuthTestServer(t)
	tok := mintFor(t, v, "demo", "alice", []string{tokenRoleSubscribe})
	resp := postReq(t, srv.Client(), srv.URL+"/api/publish/demo", tok, "bad-sdp")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("publish with subscribe-only token: status %d, want 401: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

func TestPublishRejectsExpiredToken(t *testing.T) {
	_, _, srv := newAuthTestServer(t)
	tok := craftToken(t, testHMACKey, tokenClaims{
		Room: "demo", Roles: []string{tokenRolePublish}, Subject: "alice",
		Exp: time.Now().Add(-time.Hour).Unix(),
	})
	resp := postReq(t, srv.Client(), srv.URL+"/api/publish/demo", tok, "bad-sdp")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("publish with expired token: status %d, want 401: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

// TestPublishAcceptsValidToken proves auth passed: a valid token with a
// garbage SDP reaches SDP parsing and fails there with 400, not 401.
func TestPublishAcceptsValidToken(t *testing.T) {
	_, v, srv := newAuthTestServer(t)
	tok := mintFor(t, v, "demo", "alice", []string{tokenRolePublish})
	resp := postReq(t, srv.Client(), srv.URL+"/api/publish/demo", tok, "not-an-sdp-offer")
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("publish with valid token + bad SDP: status %d, want 400: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

func TestSubscribeRejectsBadToken(t *testing.T) {
	_, _, srv := newAuthTestServer(t)
	resp := postReq(t, srv.Client(), srv.URL+"/api/subscribe/demo", "garbage", "bad-sdp")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("subscribe with bad token: status %d, want 401: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

// A valid subscribe token for the room, but the room does not exist, must
// reach the handler and fail with 404 — proving auth passed.
func TestSubscribeAcceptsValidToken(t *testing.T) {
	_, v, srv := newAuthTestServer(t)
	tok := mintFor(t, v, "demo", "bob", []string{tokenRoleSubscribe})
	resp := postReq(t, srv.Client(), srv.URL+"/api/subscribe/demo", tok, "bad-sdp")
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("subscribe with valid token to missing room: status %d, want 404: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

// Auth runs before the publisher slot is taken: a flood of bad-token
// publishes must not burn the one publisher slot.
func TestBadTokenDoesNotBurnPublisherSlot(t *testing.T) {
	v := mustVerifier(t)
	api := webrtc.NewAPI()
	s := &server{
		api: api, auth: v, maxRooms: 8, maxPublishers: 1, maxSubscribers: 50,
		rooms: make(map[string]*room),
	}
	srv := httptest.NewServer(s.routes())
	defer srv.Close()
	client := srv.Client()
	for i := 0; i < 3; i++ {
		resp := postReq(t, client, srv.URL+"/api/publish/demo", "garbage", "bad-sdp")
		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("bad-token publish %d: status %d, want 401", i, resp.StatusCode)
		}
		_ = readBody(t, resp)
	}
	tok := mintFor(t, v, "demo", "alice", []string{tokenRolePublish})
	resp := postReq(t, client, srv.URL+"/api/publish/demo", tok, "not-an-sdp-offer")
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("valid publish after bad-token flood: status %d, want 400 (slot free): %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

// ---- Room limits + room API ----

// TestMaxRoomsEnforced: a publish (even one that later fails SDP parsing)
// creates its room, so a second room past the cap is refused with 503.
func TestMaxRoomsEnforced(t *testing.T) {
	v := mustVerifier(t)
	api := webrtc.NewAPI()
	s := &server{
		api: api, auth: v, maxRooms: 1, maxPublishers: 8, maxSubscribers: 50,
		rooms: make(map[string]*room),
	}
	srv := httptest.NewServer(s.routes())
	defer srv.Close()
	client := srv.Client()
	tokA := mintFor(t, v, "room-a", "alice", []string{tokenRolePublish})
	resp := postReq(t, client, srv.URL+"/api/publish/room-a", tokA, "not-an-sdp-offer")
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("publish room-a: status %d, want 400: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
	tokB := mintFor(t, v, "room-b", "alice", []string{tokenRolePublish})
	resp = postReq(t, client, srv.URL+"/api/publish/room-b", tokB, "not-an-sdp-offer")
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("publish room-b past cap: status %d, want 503: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

func getReq(t *testing.T, client *http.Client, url, token string) *http.Response {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	return resp
}

func TestListRoomsRequiresToken(t *testing.T) {
	_, v, srv := newAuthTestServer(t)
	client := srv.Client()
	resp := getReq(t, client, srv.URL+"/api/rooms", "")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("list rooms with no token: status %d, want 401", resp.StatusCode)
	}
	_ = readBody(t, resp)
	tok := mintFor(t, v, "demo", "alice", []string{tokenRoleSubscribe})
	resp = getReq(t, client, srv.URL+"/api/rooms", tok)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("list rooms with valid token: status %d, want 200: %s", resp.StatusCode, readBody(t, resp))
	}
	body := readBody(t, resp)
	if strings.TrimSpace(body) != "[]" {
		t.Fatalf("list rooms empty server: body %q, want []", body)
	}
}

func TestCloseRoomUnknownRoom(t *testing.T) {
	_, v, srv := newAuthTestServer(t)
	client := srv.Client()
	tok := mintFor(t, v, "nope", "alice", []string{tokenRolePublish})
	req, err := http.NewRequest(http.MethodDelete, srv.URL+"/api/rooms/nope", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+tok)
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("DELETE: %v", err)
	}
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("close unknown room: status %d, want 404: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

func TestKickUnknownRoomOrUser(t *testing.T) {
	_, v, srv := newAuthTestServer(t)
	client := srv.Client()
	tok := mintFor(t, v, "nope", "alice", []string{tokenRolePublish})
	resp := postReq(t, client, srv.URL+"/api/rooms/nope/kick", tok, `{"user":"alice"}`)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("kick in unknown room: status %d, want 404: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
	resp = postReq(t, client, srv.URL+"/api/rooms/demo/kick", mintFor(t, v, "demo", "alice", []string{tokenRoleSubscribe}), `{"user":"alice"}`)
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("kick with subscribe-only token: status %d, want 401: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

// TestKickClosesParticipantReal exercises the full kick path with real (but
func TestKickClosesParticipantReal(t *testing.T) {
	v := mustVerifier(t)
	api := webrtc.NewAPI()
	s := &server{
		api: api, auth: v, maxRooms: 8, maxPublishers: 8, maxSubscribers: 50,
		rooms: make(map[string]*room),
	}
	rm := &room{
		tracks:      make(map[string]*track),
		publishers:  make(map[*publisher]struct{}),
		subscribers: make(map[*subscriber]struct{}),
	}
	s.rooms["demo"] = rm
	srv := httptest.NewServer(s.routes())
	defer srv.Close()
	client := srv.Client()

	pcAlice, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("alice PC: %v", err)
	}
	pcBob, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("bob PC: %v", err)
	}
	aliceClosed, bobClosed := false, false
	alice := &subscriber{pc: pcAlice, subject: "alice", room: rm, release: func() { aliceClosed = true }}
	bob := &subscriber{pc: pcBob, subject: "bob", room: rm, release: func() { bobClosed = true }}
	rm.addSubscriber(alice)
	rm.addSubscriber(bob)

	tok := mintFor(t, v, "demo", "op", []string{tokenRolePublish})
	resp := postReq(t, client, srv.URL+"/api/rooms/demo/kick", tok, `{"user":"alice"}`)
	body := readBody(t, resp)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("kick alice: status %d, want 200: %s", resp.StatusCode, body)
	}
	if !aliceClosed {
		t.Fatal("kick alice: alice's release was not called (participant not closed)")
	}
	if bobClosed {
		t.Fatal("kick alice: bob was closed too")
	}
	if n := len(rm.snapshotSubscribers()); n != 1 {
		t.Fatalf("room subscribers after kick = %d, want 1", n)
	}
	// Kicking the same user again now finds nobody.
	resp = postReq(t, client, srv.URL+"/api/rooms/demo/kick", tok, `{"user":"alice"}`)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("kick alice again: status %d, want 404: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
}

// TestCloseRoomClosesParticipants: DELETE closes every participant and
// drops the room, while other rooms are untouched.
func TestCloseRoomClosesParticipants(t *testing.T) {
	v := mustVerifier(t)
	api := webrtc.NewAPI()
	s := &server{
		api: api, auth: v, maxRooms: 8, maxPublishers: 8, maxSubscribers: 50,
		rooms: make(map[string]*room),
	}
	rm := &room{
		tracks:      make(map[string]*track),
		publishers:  make(map[*publisher]struct{}),
		subscribers: make(map[*subscriber]struct{}),
	}
	other := &room{
		tracks:      make(map[string]*track),
		publishers:  make(map[*publisher]struct{}),
		subscribers: make(map[*subscriber]struct{}),
	}
	s.rooms["demo"] = rm
	s.rooms["other"] = other
	srv := httptest.NewServer(s.routes())
	defer srv.Close()
	client := srv.Client()

	pc, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("publisher PC: %v", err)
	}
	closed := false
	pub := &publisher{pc: pc, subject: "alice", room: rm, release: func() { closed = true }}
	rm.addPublisher(pub)

	tok := mintFor(t, v, "demo", "op", []string{tokenRolePublish})
	req, err := http.NewRequest(http.MethodDelete, srv.URL+"/api/rooms/demo", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+tok)
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("DELETE: %v", err)
	}
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("close room: status %d, want 204: %s", resp.StatusCode, readBody(t, resp))
	}
	_ = readBody(t, resp)
	if !closed {
		t.Fatal("close room: publisher's release was not called")
	}
	if _, ok := s.rooms["demo"]; ok {
		t.Fatal("close room: room still in server map")
	}
	if _, ok := s.rooms["other"]; !ok {
		t.Fatal("close room: unrelated room was removed")
	}
}

// TestListRoomsShowsParticipants: a room registered with participants
// appears in GET /api/rooms with their subjects.
func TestListRoomsShowsParticipants(t *testing.T) {
	v := mustVerifier(t)
	api := webrtc.NewAPI()
	s := &server{
		api: api, auth: v, maxRooms: 8, maxPublishers: 8, maxSubscribers: 50,
		rooms: make(map[string]*room),
	}
	rm := &room{
		tracks:      make(map[string]*track),
		publishers:  make(map[*publisher]struct{}),
		subscribers: make(map[*subscriber]struct{}),
	}
	s.rooms["demo"] = rm
	pc, err := webrtc.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		t.Fatalf("PC: %v", err)
	}
	defer pc.Close()
	rm.addPublisher(&publisher{pc: pc, subject: "alice", room: rm, release: func() {}})
	srv := httptest.NewServer(s.routes())
	defer srv.Close()

	tok := mintFor(t, v, "demo", "op", []string{tokenRolePublish})
	resp := getReq(t, srv.Client(), srv.URL+"/api/rooms", tok)
	body := readBody(t, resp)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("list rooms: status %d, want 200: %s", resp.StatusCode, body)
	}
	var rooms []roomInfo
	if err := json.Unmarshal([]byte(body), &rooms); err != nil {
		t.Fatalf("list rooms: bad JSON %q: %v", body, err)
	}
	if len(rooms) != 1 || rooms[0].Name != "demo" {
		t.Fatalf("list rooms: %+v, want one room named demo", rooms)
	}
	if len(rooms[0].Publishers) != 1 || rooms[0].Publishers[0] != "alice" {
		t.Fatalf("list rooms publishers = %v, want [alice]", rooms[0].Publishers)
	}
}
