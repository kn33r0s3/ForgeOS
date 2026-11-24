// Hami SFU TURN support (Part 3).
//
// coturn is NOT installed on the Mac (checked 22 Nov 2026: no
// turnserver binary, not in Homebrew), so the SFU uses pion/turn
// (already a dependency of this module: github.com/pion/turn/v5) for a
// local UDP relay proof with long-term credentials (RFC 8656). This
// implementation is not production-deployment evidence.
//
// Two ways to run it:
//
//  1. In-process (tests and the harness): startSFUTURNServer.
//  2. Standalone: `hami-media -mode=turn-server` (see main.go). It
//     listens on HAMI_SFU_TURN_LISTEN (default 127.0.0.1:3478) until
//     killed and serves the single configured user.
//
// Credentials come from the environment or a file ONLY — never
// hardcoded, never logged, never printed:
//
//	HAMI_SFU_TURN_URL            turn: URL clients use (default turn:127.0.0.1:3478)
//	HAMI_SFU_TURN_USERNAME       TURN username
//	HAMI_SFU_TURN_PASSWORD       TURN password (or HAMI_SFU_TURN_PASSWORD_FILE)
//	HAMI_SFU_TURN_PASSWORD_FILE  path to a file holding the password
//	HAMI_SFU_TURN_REALM          TURN realm (default "hami")
//	HAMI_SFU_TURN_LISTEN         listen address for -mode=turn-server
//
// How clients use it: a client behind NAT builds its PeerConnection
// with sfuTURNICEConfiguration(cfg, true) — ICEServers pointing at the
// TURN URL with the username/credential above and
// ICETransportPolicyRelay, so every candidate is a relay candidate and
// all media flows through the TURN server. The SFU side keeps its
// loopback host candidates; the relayed client candidate pairs with
// the SFU host candidate, so no SFU-side TURN config is needed for
// the relay path to work.
//
// Proof (TestSFUTURNRelayCarriesMedia in turn_test.go): a relay-only
// publisher and a relay-only viewer connect through the TURN server;
// the test asserts the nominated pair's local candidate type is
// "relay" on both client PeerConnections and that RTP frames flow
// publisher -> router -> viewer.

package main

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"syscall"

	"github.com/pion/turn/v5"
	"github.com/pion/webrtc/v4"
)

// sfuTURNDefaultURL is the TURN URL used when HAMI_SFU_TURN_URL is unset.
const sfuTURNDefaultURL = "turn:127.0.0.1:3478"

// sfuTURNDefaultRealm is the TURN realm used when HAMI_SFU_TURN_REALM is unset.
const sfuTURNDefaultRealm = "hami"

// sfuTURNDefaultListen is the listen address for -mode=turn-server.
const sfuTURNDefaultListen = "127.0.0.1:3478"

// sfuTURNRelayMinPort / sfuTURNRelayMaxPort bound relay allocations.
// 10,000 ports (49152-59152): one relay port per concurrent
// TURN-relayed client, so the 20x10000 target is not capped at 1,000
// relayed clients by the port range.
const (
	sfuTURNRelayMinPort = 49152
	sfuTURNRelayMaxPort = 59152
)

// sfuTURNConfig is everything a client (or the standalone server) needs
// to use the TURN server. Password is never logged.
type sfuTURNConfig struct {
	URL      string
	Username string
	Password string
	Realm    string
}

// loadSFUTURNPassword reads the TURN password from
// HAMI_SFU_TURN_PASSWORD_FILE (preferred) or HAMI_SFU_TURN_PASSWORD.
func loadSFUTURNPassword() (string, error) {
	if path := strings.TrimSpace(os.Getenv("HAMI_SFU_TURN_PASSWORD_FILE")); path != "" {
		// POLISH-001: the password file must be a regular file readable
		// only by its owner — the same rule as readSFUKeyFile in auth.go.
		// A group- or world-readable credential file is refused instead
		// of silently used.
		info, err := os.Stat(path)
		if err != nil {
			return "", fmt.Errorf("stat TURN password file: %w", err)
		}
		if !info.Mode().IsRegular() {
			return "", errors.New("TURN password file path must be a regular file")
		}
		if runtime.GOOS != "windows" && info.Mode().Perm()&0o077 != 0 {
			return "", fmt.Errorf("TURN password file mode is %04o; it must not be readable by group or others (run chmod 600)", uint32(info.Mode().Perm()))
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			return "", fmt.Errorf("read TURN password file: %w", err)
		}
		password := strings.TrimSpace(string(raw))
		if password == "" {
			return "", errors.New("TURN password file is empty")
		}
		return password, nil
	}
	if password := strings.TrimSpace(os.Getenv("HAMI_SFU_TURN_PASSWORD")); password != "" {
		return password, nil
	}
	return "", errors.New("no TURN password configured: set HAMI_SFU_TURN_PASSWORD_FILE or HAMI_SFU_TURN_PASSWORD")
}

// sfuTURNConfigFromEnv builds the TURN config from the environment. It
// reports configured=false when no username/password is set, so callers
// can run without TURN. The URL and realm always have defaults.
func sfuTURNConfigFromEnv() (sfuTURNConfig, bool, error) {
	config := sfuTURNConfig{
		URL:   strings.TrimSpace(os.Getenv("HAMI_SFU_TURN_URL")),
		Realm: strings.TrimSpace(os.Getenv("HAMI_SFU_TURN_REALM")),
	}
	if config.URL == "" {
		config.URL = sfuTURNDefaultURL
	}
	if config.Realm == "" {
		config.Realm = sfuTURNDefaultRealm
	}
	config.Username = strings.TrimSpace(os.Getenv("HAMI_SFU_TURN_USERNAME"))
	if config.Username == "" {
		return config, false, nil
	}
	password, err := loadSFUTURNPassword()
	if err != nil {
		return config, false, err
	}
	config.Password = password
	return config, true, nil
}

// sfuTURNICEConfiguration returns the WebRTC configuration a client
// uses with this TURN server. With relayOnly=true the client gathers
// relay candidates only, so all media flows through the TURN server.
func sfuTURNICEConfiguration(config sfuTURNConfig, relayOnly bool) webrtc.Configuration {
	iceConfig := webrtc.Configuration{
		ICEServers: []webrtc.ICEServer{
			{
				URLs:       []string{config.URL},
				Username:   config.Username,
				Credential: config.Password,
			},
		},
	}
	if relayOnly {
		iceConfig.ICETransportPolicy = webrtc.ICETransportPolicyRelay
	}
	return iceConfig
}

// sfuTURNServer is a running pion/turn server.
type sfuTURNServer struct {
	server *turn.Server
	conn   net.PacketConn
	addr   net.Addr
	realm  string
}

// startSFUTURNServer starts a UDP TURN server on addr (use
// "127.0.0.1:0" for an ephemeral test port) serving realm with the
// given username->password map. Relay allocations are confined to
// sfuTURNRelayMinPort..sfuTURNRelayMaxPort on the listen IP.
func startSFUTURNServer(addr, realm string, users map[string]string) (*sfuTURNServer, error) {
	if realm == "" {
		return nil, errors.New("TURN realm is required")
	}
	if len(users) == 0 {
		return nil, errors.New("TURN server needs at least one user")
	}
	conn, err := net.ListenPacket("udp", addr)
	if err != nil {
		return nil, fmt.Errorf("listen TURN UDP %s: %w", addr, err)
	}
	listenAddr, ok := conn.LocalAddr().(*net.UDPAddr)
	if !ok {
		_ = conn.Close()
		return nil, fmt.Errorf("TURN listen address %s is not UDP", conn.LocalAddr())
	}
	relayIP := listenAddr.IP
	if relayIP == nil {
		relayIP = net.ParseIP("127.0.0.1")
	}
	server, err := turn.NewServer(turn.ServerConfig{
		Realm: realm,
		AuthHandler: func(ra *turn.RequestAttributes) (string, []byte, bool) {
			password, exists := users[ra.Username]
			if !exists {
				return "", nil, false
			}
			return ra.Username, turn.GenerateAuthKey(ra.Username, ra.Realm, password), true
		},
		PacketConnConfigs: []turn.PacketConnConfig{
			{
				PacketConn: conn,
				RelayAddressGenerator: &turn.RelayAddressGeneratorPortRange{
					RelayAddress: relayIP,
					Address:      "0.0.0.0",
					MinPort:      sfuTURNRelayMinPort,
					MaxPort:      sfuTURNRelayMaxPort,
				},
			},
		},
	})
	if err != nil {
		_ = conn.Close()
		return nil, fmt.Errorf("start TURN server: %w", err)
	}
	return &sfuTURNServer{server: server, conn: conn, addr: conn.LocalAddr(), realm: realm}, nil
}

// URL returns the turn: URL clients use for this server.
func (s *sfuTURNServer) URL() string {
	return "turn:" + s.addr.String()
}

// Addr returns the server's listen address.
func (s *sfuTURNServer) Addr() string {
	return s.addr.String()
}

// Close stops the TURN server. turn.Server.Close also closes the
// listener PacketConn, so there is nothing else to close.
func (s *sfuTURNServer) Close() error {
	return s.server.Close()
}

// runTURNServer implements -mode=turn-server: run a standalone TURN
// server on HAMI_SFU_TURN_LISTEN until the process is killed. It logs
// only the listen address and realm — never credentials.
func runTURNServer(listenAddr string) (returnErr error) {
	config, configured, err := sfuTURNConfigFromEnv()
	if err != nil {
		return err
	}
	if !configured {
		return errors.New("TURN server needs HAMI_SFU_TURN_USERNAME and HAMI_SFU_TURN_PASSWORD_FILE (or HAMI_SFU_TURN_PASSWORD)")
	}
	if listenAddr == "" {
		listenAddr = strings.TrimSpace(os.Getenv("HAMI_SFU_TURN_LISTEN"))
	}
	if listenAddr == "" {
		listenAddr = sfuTURNDefaultListen
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	server, err := startSFUTURNServer(listenAddr, config.Realm, map[string]string{config.Username: config.Password})
	if err != nil {
		return err
	}
	defer func() {
		if err := server.Close(); err != nil {
			returnErr = errors.Join(returnErr, fmt.Errorf("close TURN server: %w", err))
		}
	}()
	fmt.Fprintf(os.Stderr, "hami TURN server: listening=%s realm=%s url=%s\n", server.Addr(), config.Realm, server.URL())
	<-ctx.Done()
	return nil
}

// sfuRelayPairTypes inspects a PeerConnection's stats and returns the
// local/remote candidate types of its nominated, succeeded ICE pair
// (e.g. webrtc.ICECandidateTypeRelay / webrtc.ICECandidateTypeHost),
// plus the human-readable diagnostics. It reports ok=false when no
// nominated succeeded pair exists yet.
func sfuRelayPairTypes(peer *webrtc.PeerConnection) (localType, remoteType webrtc.ICECandidateType, diagnostics string, ok bool) {
	report := peer.GetStats()
	candidates := make(map[string]webrtc.ICECandidateStats)
	for _, stats := range report {
		if candidate, is := stats.(webrtc.ICECandidateStats); is {
			candidates[candidate.ID] = candidate
		}
	}
	for _, stats := range report {
		pair, is := stats.(webrtc.ICECandidatePairStats)
		if !is || !pair.Nominated {
			continue
		}
		if pair.State != webrtc.StatsICECandidatePairStateSucceeded {
			continue
		}
		local := candidates[pair.LocalCandidateID]
		remote := candidates[pair.RemoteCandidateID]
		diagnostics = fmt.Sprintf("pair=%s state=%s local=%s remote=%s",
			pair.ID, pair.State,
			formatICECandidate(local), formatICECandidate(remote))
		return local.CandidateType, remote.CandidateType, diagnostics, true
	}
	return webrtc.ICECandidateTypeUnknown, webrtc.ICECandidateTypeUnknown, "", false
}
