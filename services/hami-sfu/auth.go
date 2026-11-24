// Per-user HMAC tokens for hami-sfu.
//
// A client that publishes or subscribes sends a signed token as a Bearer
// token on its signalling request (POST /api/publish/{room} or
// POST /api/subscribe/{room}). A token expires, names one room, names one
// identity (sub), and lists the roles it grants. Only the holder of the
// HMAC key can mint one. The key never appears in a token, a log line,
// or command output.
//
// Token format (standard library only):
//
//	token = base64url(JSON claims) "." base64url(HMAC-SHA256(key, base64url(JSON claims)))
//
// Claims:
//
//		{"room":"demo","roles":["publish"],"sub":"alice","exp":1790000000,"iat":1789996400}
//
//	  - room:  the one room this token is for.
//	  - roles: any of "publish" and "subscribe".
//	  - sub:   required. Recorded on the publisher/subscriber so the room
//	    API can list and kick participants by identity.
//	  - exp:   unix seconds. Rejected at or after exp. No clock-skew allowance.
//	  - iat:   unix seconds the token was minted. Informational only.
//
// Key source (never hardcoded, never logged, never printed). In order:
//   - -hmac-key-file flag, if given.
//   - HAMI_SFU_HMAC_KEY_FILE: path to a file holding the key. Preferred.
//     The file must not be readable by group or other users (chmod 600).
//   - HAMI_SFU_HMAC_KEY: the key itself. Other processes of the same user
//     can read the environment, so prefer the file for real deployments.
//
// The key must be at least 32 bytes. Generate one with: openssl rand -hex 32
//
// Limits: a token cannot be revoked before it expires, so keep TTLs short. A
// 32-byte minimum does not prove randomness; the operator generates the key.
// Tokens travel in an Authorization header, so the server must sit behind TLS
// whenever it is reachable from another machine.
//
// Enforcement: requireRole wraps the publish/subscribe handlers and rejects
// unauthenticated requests with 401 before any PeerConnection is created
// and before any publisher/subscriber slot is taken. A server built by
// main() always has a verifier and refuses to start without a key, so it
// fails closed. A nil verifier (auth == nil) passes requests through; only
// servers built by hand in unit-test fixtures and the smoke test take that
// path.
//
// Operator minting: `hami-sfu token --room demo --user alice --role publish
// --ttl 1h` prints one token to stdout. It never prints the key.
//
// Ported from services/hami-media/auth.go (sfuAuthVerifier); the verifier
// here is not bound to one room because hami-sfu serves many rooms — the
// room is checked per request instead.
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
	"os"
	"runtime"
	"strings"
	"time"
)

const (
	tokenRolePublish   = "publish"
	tokenRoleSubscribe = "subscribe"

	// tokenMaxTTL is the longest lifetime a minted token may carry.
	tokenMaxTTL = 24 * time.Hour

	// tokenMinKeyBytes is the minimum HMAC key length in bytes.
	tokenMinKeyBytes = 32

	// tokenMaxLength bounds a token's size before any decoding.
	tokenMaxLength = 8 << 10
)

var (
	errAuthNoKey        = errors.New("auth verifier has no key")
	errAuthMissingToken = errors.New("missing token")
	errAuthMalformed    = errors.New("malformed token")
	errAuthBadSignature = errors.New("token signature mismatch")
	errAuthExpired      = errors.New("token expired")
	errAuthWrongRoom    = errors.New("token is not for this room")
	errAuthWrongRole    = errors.New("token does not grant the required role")
)

// tokenClaims is the signed payload of a token.
type tokenClaims struct {
	Room    string   `json:"room"`
	Roles   []string `json:"roles"`
	Subject string   `json:"sub"`
	Exp     int64    `json:"exp"`
	Iat     int64    `json:"iat,omitempty"`
}

// authVerifier mints and verifies tokens with one HMAC key.
type authVerifier struct {
	key []byte
}

// validTokenRole reports whether role is one the server grants.
func validTokenRole(role string) bool {
	return role == tokenRolePublish || role == tokenRoleSubscribe
}

// newAuthVerifier builds a verifier. The key is copied so the caller cannot
// change it afterwards.
func newAuthVerifier(key []byte) (*authVerifier, error) {
	if len(key) < tokenMinKeyBytes {
		return nil, fmt.Errorf("HMAC key is %d bytes, want at least %d", len(key), tokenMinKeyBytes)
	}
	return &authVerifier{key: append([]byte(nil), key...)}, nil
}

// readHMACKeyFile reads the key from a file that only its owner can read.
func readHMACKeyFile(path string) ([]byte, error) {
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

// loadHMACKey returns the HMAC key from the -hmac-key-file flag (when
// given), else exactly one configured environment source. Error messages
// never include the key.
func loadHMACKey(keyFileFlag string) ([]byte, error) {
	if strings.TrimSpace(keyFileFlag) != "" {
		return readHMACKeyFile(strings.TrimSpace(keyFileFlag))
	}
	keyFile := strings.TrimSpace(os.Getenv("HAMI_SFU_HMAC_KEY_FILE"))
	keyEnv := strings.TrimSpace(os.Getenv("HAMI_SFU_HMAC_KEY"))
	if keyFile != "" && keyEnv != "" {
		return nil, errors.New("set only one of HAMI_SFU_HMAC_KEY_FILE and HAMI_SFU_HMAC_KEY")
	}
	var key []byte
	switch {
	case keyFile != "":
		fileKey, err := readHMACKeyFile(keyFile)
		if err != nil {
			return nil, err
		}
		key = fileKey
	case keyEnv != "":
		key = []byte(keyEnv)
	default:
		return nil, errors.New("no HMAC key configured: set -hmac-key-file, HAMI_SFU_HMAC_KEY_FILE (preferred) or HAMI_SFU_HMAC_KEY")
	}
	if len(key) < tokenMinKeyBytes {
		return nil, fmt.Errorf("HMAC key is %d bytes, want at least %d", len(key), tokenMinKeyBytes)
	}
	return key, nil
}

// signTokenPayload returns base64url(payload) "." base64url(HMAC-SHA256(key,
// base64url(payload))).
func signTokenPayload(key, payload []byte) string {
	payloadB64 := base64.RawURLEncoding.EncodeToString(payload)
	mac := hmac.New(sha256.New, key)
	_, _ = mac.Write([]byte(payloadB64))
	return payloadB64 + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

// mint signs claims. It refuses claims that would not verify: no subject, no
// roles or an unknown role, an expiry that is not in the future, or a
// lifetime longer than tokenMaxTTL.
func (v *authVerifier) mintClaims(claims tokenClaims) (string, error) {
	if v == nil || len(v.key) == 0 {
		return "", errAuthNoKey
	}
	now := time.Now()
	if strings.TrimSpace(claims.Subject) == "" {
		return "", errors.New("token must name a subject")
	}
	if len(claims.Roles) == 0 {
		return "", errors.New("token must grant at least one role")
	}
	for _, role := range claims.Roles {
		if !validTokenRole(role) {
			return "", fmt.Errorf("unknown token role %q", role)
		}
	}
	if claims.Exp <= now.Unix() {
		return "", fmt.Errorf("token expiry %d is not in the future", claims.Exp)
	}
	if time.Unix(claims.Exp, 0).Sub(now) > tokenMaxTTL {
		return "", fmt.Errorf("token lifetime exceeds %s", tokenMaxTTL)
	}
	if claims.Iat == 0 {
		claims.Iat = now.Unix()
	}
	payload, err := json.Marshal(claims)
	if err != nil {
		return "", fmt.Errorf("encode token claims: %w", err)
	}
	return signTokenPayload(v.key, payload), nil
}

// mint mints a token for one room and subject, with the given roles,
// valid for ttl from now.
func (v *authVerifier) mint(room, subject string, roles []string, ttl time.Duration) (string, error) {
	return v.mintClaims(tokenClaims{
		Room:    room,
		Roles:   roles,
		Subject: subject,
		Exp:     time.Now().Add(ttl).Unix(),
	})
}

// verify checks, in order: size and shape, strict base64, signature
// (constant time), claim JSON, and expiry. It returns the claims on success.
// It does NOT check room or role; authorize does that.
func (v *authVerifier) verify(token string) (*tokenClaims, error) {
	if v == nil || len(v.key) == 0 {
		return nil, errAuthNoKey
	}
	token = strings.TrimSpace(token)
	if token == "" {
		return nil, errAuthMissingToken
	}
	if len(token) > tokenMaxLength {
		return nil, errAuthMalformed
	}
	parts := strings.Split(token, ".")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return nil, errAuthMalformed
	}
	payload, err := base64.RawURLEncoding.Strict().DecodeString(parts[0])
	if err != nil {
		return nil, errAuthMalformed
	}
	sig, err := base64.RawURLEncoding.Strict().DecodeString(parts[1])
	if err != nil {
		return nil, errAuthMalformed
	}
	mac := hmac.New(sha256.New, v.key)
	_, _ = mac.Write([]byte(parts[0]))
	if subtle.ConstantTimeCompare(sig, mac.Sum(nil)) != 1 {
		return nil, errAuthBadSignature
	}
	var claims tokenClaims
	dec := json.NewDecoder(bytes.NewReader(payload))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&claims); err != nil {
		return nil, errAuthMalformed
	}
	if !time.Now().Before(time.Unix(claims.Exp, 0)) {
		return nil, errAuthExpired
	}
	return &claims, nil
}

// authorize verifies a token and checks it is for this room and grants at
// least one of the allowed roles. With no allowed roles given, any role in
// the token passes (still checks signature, expiry, and room).
func (v *authVerifier) authorize(token, room string, roles ...string) (*tokenClaims, error) {
	claims, err := v.verify(token)
	if err != nil {
		return nil, err
	}
	if claims.Room != room {
		return nil, errAuthWrongRoom
	}
	if len(roles) == 0 {
		return claims, nil
	}
	for _, role := range roles {
		if !validTokenRole(role) {
			return nil, errAuthWrongRole
		}
		for _, granted := range claims.Roles {
			if granted == role {
				return claims, nil
			}
		}
	}
	return nil, errAuthWrongRole
}
