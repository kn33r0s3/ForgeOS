// Hami SFU token authentication.
//
// A client that publishes or subscribes sends a signed token in the "token"
// field of its signalling request (POST /publisher or POST /viewer). A token
// expires, names one room, names one identity, and lists the roles it grants.
// Only the holder of the HMAC key can mint one. The key never appears in a
// token, a log line, or command output.
//
// Token format (standard library only):
//
//	token = base64url(JSON claims) "." base64url(HMAC-SHA256(key, base64url(JSON claims)))
//
// Claims:
//
//	{"room":"default","roles":["publish"],"sub":"pub-1","exp":1790000000,"iat":1789996400}
//
//   - room:  the one room this SFU process serves (HAMI_SFU_ROOM, default "default").
//   - roles: any of "publish" and "subscribe".
//   - sub:   required. The request must name the same ID: publisher_id for a
//     publish request, viewer_id for a subscribe request.
//   - exp:   unix seconds. Rejected at or after exp. There is no clock-skew allowance.
//   - iat:   unix seconds the token was minted. Informational only.
//
// Key source (never hardcoded, never logged, never printed). Set exactly one:
//
//   - HAMI_SFU_HMAC_KEY_FILE: path to a file holding the key. Preferred. The
//     file must not be readable by group or other users (chmod 600).
//   - HAMI_SFU_HMAC_KEY: the key itself. Other processes of the same user can
//     read the environment, so prefer the file for real deployments.
//
// The key must be at least 32 bytes. Generate one with: openssl rand -hex 32
//
// Limits: a token cannot be revoked before it expires, so keep TTLs short. A
// 32-byte minimum does not prove randomness; the operator generates the key.
// Tokens travel in the request body, so the SFU must sit behind TLS whenever
// it is reachable from another machine.
//
// Enforcement: authorizeToken is called by the publish and subscribe handlers
// in main.go after the bearer check and before any PeerConnection is created.
// A server started by runM7HSFUServer always has a verifier and sets
// requireAuth, so a missing verifier there fails closed.
//
// Operator minting: main.go -mode=mint-token prints one token to stdout.
// It never prints the key.

package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"runtime"
	"strings"
	"time"
)

const (
	sfuTokenRolePublish   = "publish"
	sfuTokenRoleSubscribe = "subscribe"

	// sfuTokenMaxTTL is the longest lifetime a minted token may carry.
	sfuTokenMaxTTL = 24 * time.Hour

	// sfuTokenMinKeyBytes is the minimum HMAC key length in bytes.
	sfuTokenMinKeyBytes = 32

	// sfuTokenMaxLength bounds a token's size before any decoding.
	sfuTokenMaxLength = 8 << 10
)

var (
	errSFUAuthNoKey        = errors.New("SFU auth verifier has no key")
	errSFUAuthMissingToken = errors.New("missing token")
	errSFUAuthMalformed    = errors.New("malformed token")
	errSFUAuthBadSignature = errors.New("token signature mismatch")
	errSFUAuthExpired      = errors.New("token expired")
	errSFUAuthWrongRoom    = errors.New("token is not for this room")
	errSFUAuthWrongRole    = errors.New("token does not grant the required role")
	errSFUAuthWrongSubject = errors.New("token is not for this identity")
)

// sfuTokenClaims is the signed payload of an SFU token.
type sfuTokenClaims struct {
	Room    string   `json:"room"`
	Roles   []string `json:"roles"`
	Subject string   `json:"sub"`
	Exp     int64    `json:"exp"`
	Iat     int64    `json:"iat,omitempty"`
}

// sfuAuthVerifier mints and verifies SFU tokens for one room with one key.
type sfuAuthVerifier struct {
	key  []byte
	room string
}

// validSFURole reports whether role is one the SFU grants.
func validSFURole(role string) bool {
	return role == sfuTokenRolePublish || role == sfuTokenRoleSubscribe
}

// newSFUAuthVerifier builds a verifier for one room. The key is copied so the
// caller cannot change it afterwards.
func newSFUAuthVerifier(key []byte, room string) (*sfuAuthVerifier, error) {
	if len(key) < sfuTokenMinKeyBytes {
		return nil, fmt.Errorf("HMAC key is %d bytes, want at least %d", len(key), sfuTokenMinKeyBytes)
	}
	if strings.TrimSpace(room) == "" {
		return nil, errors.New("SFU room is required")
	}
	return &sfuAuthVerifier{key: append([]byte(nil), key...), room: room}, nil
}

// readSFUKeyFile reads the key from a file that only its owner can read.
func readSFUKeyFile(path string) ([]byte, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("stat HMAC key file: %w", err)
	}
	if !info.Mode().IsRegular() {
		return nil, errors.New("HMAC key path must be a regular file")
	}
	if runtime.GOOS != "windows" && info.Mode().Perm()&0o077 != 0 {
		return nil, fmt.Errorf("HMAC key file mode is %04o; it must not be readable by group or others (run chmod 600)", uint32(info.Mode().Perm()))
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read HMAC key file: %w", err)
	}
	return []byte(strings.TrimSpace(string(raw))), nil
}

// loadSFUAuthKey returns the HMAC key from exactly one configured source.
// Error messages never include the key.
func loadSFUAuthKey() ([]byte, error) {
	keyFile := strings.TrimSpace(os.Getenv("HAMI_SFU_HMAC_KEY_FILE"))
	keyEnv := strings.TrimSpace(os.Getenv("HAMI_SFU_HMAC_KEY"))
	if keyFile != "" && keyEnv != "" {
		return nil, errors.New("set only one of HAMI_SFU_HMAC_KEY_FILE and HAMI_SFU_HMAC_KEY")
	}
	var key []byte
	switch {
	case keyFile != "":
		fileKey, err := readSFUKeyFile(keyFile)
		if err != nil {
			return nil, err
		}
		key = fileKey
	case keyEnv != "":
		key = []byte(keyEnv)
	default:
		return nil, errors.New("no HMAC key configured: set HAMI_SFU_HMAC_KEY_FILE (preferred) or HAMI_SFU_HMAC_KEY")
	}
	if len(key) < sfuTokenMinKeyBytes {
		return nil, fmt.Errorf("HMAC key is %d bytes, want at least %d", len(key), sfuTokenMinKeyBytes)
	}
	return key, nil
}

// sfuAuthRoom returns the room this SFU process serves: HAMI_SFU_ROOM, or
// "default" when unset.
func sfuAuthRoom() string {
	if room := strings.TrimSpace(os.Getenv("HAMI_SFU_ROOM")); room != "" {
		return room
	}
	return "default"
}

// loadSFUAuthVerifier builds the verifier for this process from the
// environment. runM7HSFUServer calls it at startup and refuses to start on error.
func loadSFUAuthVerifier() (*sfuAuthVerifier, error) {
	key, err := loadSFUAuthKey()
	if err != nil {
		return nil, err
	}
	return newSFUAuthVerifier(key, sfuAuthRoom())
}

// sfuChildEnv returns this process's environment with any inherited SFU key
// and room removed, plus the exact key and room for a child SFU process. The
// harness uses it so the child verifies tokens minted with the same key.
func sfuChildEnv(keyText string) []string {
	env := make([]string, 0, len(os.Environ())+2)
	for _, kv := range os.Environ() {
		if strings.HasPrefix(kv, "HAMI_SFU_HMAC_KEY") || strings.HasPrefix(kv, "HAMI_SFU_ROOM=") {
			continue
		}
		env = append(env, kv)
	}
	return append(env, "HAMI_SFU_HMAC_KEY="+keyText, "HAMI_SFU_ROOM=default")
}

// signSFUPayload returns base64url(payload) "." base64url(HMAC-SHA256(key, base64url(payload))).
func signSFUPayload(key, payload []byte) string {
	payloadB64 := base64.RawURLEncoding.EncodeToString(payload)
	mac := hmac.New(sha256.New, key)
	_, _ = mac.Write([]byte(payloadB64))
	return payloadB64 + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

// mint signs claims. It refuses claims that would not verify: no subject, no
// roles or an unknown role, an expiry that is not in the future, or a lifetime
// longer than sfuTokenMaxTTL. An empty room defaults to the verifier's room.
func (v *sfuAuthVerifier) mint(claims sfuTokenClaims) (string, error) {
	if v == nil || len(v.key) == 0 {
		return "", errSFUAuthNoKey
	}
	now := time.Now()
	if claims.Room == "" {
		claims.Room = v.room
	}
	if strings.TrimSpace(claims.Subject) == "" {
		return "", errors.New("token must name a subject")
	}
	if len(claims.Roles) == 0 {
		return "", errors.New("token must grant at least one role")
	}
	for _, role := range claims.Roles {
		if !validSFURole(role) {
			return "", fmt.Errorf("unknown token role %q", role)
		}
	}
	if claims.Exp <= now.Unix() {
		return "", fmt.Errorf("token expiry %d is not in the future", claims.Exp)
	}
	if time.Unix(claims.Exp, 0).Sub(now) > sfuTokenMaxTTL {
		return "", fmt.Errorf("token lifetime exceeds %s", sfuTokenMaxTTL)
	}
	if claims.Iat == 0 {
		claims.Iat = now.Unix()
	}
	payload, err := json.Marshal(claims)
	if err != nil {
		return "", fmt.Errorf("encode token claims: %w", err)
	}
	return signSFUPayload(v.key, payload), nil
}

// mintSFUToken mints a token for one room and subject, with the given roles,
// valid for ttl from now.
func (v *sfuAuthVerifier) mintSFUToken(room, subject string, roles []string, ttl time.Duration) (string, error) {
	return v.mint(sfuTokenClaims{
		Room:    room,
		Roles:   roles,
		Subject: subject,
		Exp:     time.Now().Add(ttl).Unix(),
	})
}

// verify checks, in order: size and shape, strict base64, signature (constant
// time), claim JSON, expiry, room, and role. It returns the claims on success.
// The caller must still check the subject; authorizeToken does that.
func (v *sfuAuthVerifier) verify(token, role string) (*sfuTokenClaims, error) {
	if v == nil || len(v.key) == 0 {
		return nil, errSFUAuthNoKey
	}
	token = strings.TrimSpace(token)
	if token == "" {
		return nil, errSFUAuthMissingToken
	}
	if len(token) > sfuTokenMaxLength {
		return nil, errSFUAuthMalformed
	}
	parts := strings.Split(token, ".")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return nil, errSFUAuthMalformed
	}
	payload, err := base64.RawURLEncoding.Strict().DecodeString(parts[0])
	if err != nil {
		return nil, errSFUAuthMalformed
	}
	sig, err := base64.RawURLEncoding.Strict().DecodeString(parts[1])
	if err != nil {
		return nil, errSFUAuthMalformed
	}
	mac := hmac.New(sha256.New, v.key)
	_, _ = mac.Write([]byte(parts[0]))
	if subtle.ConstantTimeCompare(sig, mac.Sum(nil)) != 1 {
		return nil, errSFUAuthBadSignature
	}
	var claims sfuTokenClaims
	dec := json.NewDecoder(bytes.NewReader(payload))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&claims); err != nil {
		return nil, errSFUAuthMalformed
	}
	if !time.Now().Before(time.Unix(claims.Exp, 0)) {
		return nil, errSFUAuthExpired
	}
	if claims.Room != v.room {
		return nil, errSFUAuthWrongRoom
	}
	if !validSFURole(role) {
		return nil, errSFUAuthWrongRole
	}
	for _, granted := range claims.Roles {
		if granted == role {
			return &claims, nil
		}
	}
	return nil, errSFUAuthWrongRole
}

// runMintToken implements -mode=mint-token. It prints one token to stdout and
// never prints the key. The room must be this SFU's room.
func runMintToken(room, rolesFlag, subject string, ttl time.Duration) error {
	verifier, err := loadSFUAuthVerifier()
	if err != nil {
		return err
	}
	if room == "" {
		room = verifier.room
	}
	if room != verifier.room {
		return fmt.Errorf("room %q is not this SFU's room %q", room, verifier.room)
	}
	if strings.TrimSpace(subject) == "" {
		return errors.New("-token-subject is required (the publisher or viewer ID)")
	}
	if ttl <= 0 || ttl > sfuTokenMaxTTL {
		return fmt.Errorf("-token-ttl must be above 0 and at most %s", sfuTokenMaxTTL)
	}
	var roles []string
	for _, role := range strings.Split(rolesFlag, ",") {
		role = strings.TrimSpace(role)
		if role == "" {
			continue
		}
		if !validSFURole(role) {
			return fmt.Errorf("unknown token role %q (want %q or %q)", role, sfuTokenRolePublish, sfuTokenRoleSubscribe)
		}
		roles = append(roles, role)
	}
	token, err := verifier.mintSFUToken(room, subject, roles, ttl)
	if err != nil {
		return err
	}
	fmt.Println(token)
	return nil
}

// authorizeToken is called by the publish and subscribe handlers after their
// bearer check and before any PeerConnection is created. It returns false, after
// writing a 401, unless the token grants role to identity. Every rejection
// returns the same generic message.
//
// When no verifier is set and requireAuth is false, it allows the request.
// Only servers built by hand in unit-test fixtures take that path. A server
// built by runM7HSFUServer sets requireAuth, so it fails closed.
func (server *m7hRemoteSFUServer) authorizeToken(w http.ResponseWriter, token, role, identity string) bool {
	if server.auth == nil {
		if server.requireAuth {
			writeM7HJSONError(w, http.StatusUnauthorized, errors.New("invalid or expired token"))
			return false
		}
		return true
	}
	claims, err := server.auth.verify(token, role)
	if err == nil && (strings.TrimSpace(identity) == "" || claims.Subject != identity) {
		err = errSFUAuthWrongSubject
	}
	if err != nil {
		writeM7HJSONError(w, http.StatusUnauthorized, errors.New("invalid or expired token"))
		return false
	}
	return true
}
