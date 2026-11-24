// hami-sfu is a small self-hosted WebRTC selective forwarding unit (SFU).
//
// POST /api/publish/{room}    SDP offer -> SDP answer (Bearer per-user token, publish role)
// GET  /api/rooms/{room}      track list (Bearer per-user token, either role)
// POST /api/subscribe/{room}  SDP offer -> SDP answer (Bearer per-user token, subscribe role)
// GET  /api/rooms             room list (any valid Bearer token)
// DELETE /api/rooms/{room}    close a room (Bearer per-user token, publish role)
// POST /api/rooms/{room}/kick kick a participant by identity (Bearer per-user token, publish role)
//
// Tokens are HMAC-signed per user (auth.go). Mint one with:
// hami-sfu token --room demo --user alice --role publish --ttl 1h
package main

import (
	"context"
	_ "embed"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"runtime/debug"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/pion/ice/v4"
	"github.com/pion/interceptor"
	"github.com/pion/interceptor/pkg/nack"
	"github.com/pion/rtcp"
	"github.com/pion/webrtc/v4"
)

//go:embed index.html
var indexHTML []byte

type reject struct {
	code int
	msg  string
}

func (r *reject) Error() string { return r.msg }

func fail(w http.ResponseWriter, err error) {
	var rj *reject
	if errors.As(err, &rj) {
		http.Error(w, rj.msg, rj.code)
		return
	}
	log.Printf("request failed: %v", err)
	http.Error(w, "internal error", http.StatusInternalServerError)
}

type room struct {
	mu     sync.RWMutex
	tracks map[string]*track
	// Participants, by identity (token subject). Room close and kick walk
	// these maps; participants remove themselves when they close.
	publishers  map[*publisher]struct{}
	subscribers map[*subscriber]struct{}
}

func (rm *room) add(t *track) {
	rm.mu.Lock()
	rm.tracks[t.remote.ID()] = t
	rm.mu.Unlock()
}

func (rm *room) remove(t *track) {
	rm.mu.Lock()
	if rm.tracks[t.remote.ID()] == t {
		delete(rm.tracks, t.remote.ID())
	}
	rm.mu.Unlock()
}

func (rm *room) snapshot() []*track {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	out := make([]*track, 0, len(rm.tracks))
	for _, t := range rm.tracks {
		out = append(out, t)
	}
	return out
}

func (rm *room) addPublisher(p *publisher) {
	rm.mu.Lock()
	rm.publishers[p] = struct{}{}
	rm.mu.Unlock()
}

func (rm *room) removePublisher(p *publisher) {
	rm.mu.Lock()
	delete(rm.publishers, p)
	rm.mu.Unlock()
}

func (rm *room) addSubscriber(s *subscriber) {
	rm.mu.Lock()
	rm.subscribers[s] = struct{}{}
	rm.mu.Unlock()
}

func (rm *room) removeSubscriber(s *subscriber) {
	rm.mu.Lock()
	delete(rm.subscribers, s)
	rm.mu.Unlock()
}

func (rm *room) snapshotPublishers() []*publisher {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	out := make([]*publisher, 0, len(rm.publishers))
	for p := range rm.publishers {
		out = append(out, p)
	}
	return out
}

func (rm *room) snapshotSubscribers() []*subscriber {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	out := make([]*subscriber, 0, len(rm.subscribers))
	for s := range rm.subscribers {
		out = append(out, s)
	}
	return out
}

// closeAll closes every participant in the room. It snapshots first and
// closes outside the lock: close() removes the participant from this room,
// which takes the lock again.
func (rm *room) closeAll() {
	pubs := rm.snapshotPublishers()
	subs := rm.snapshotSubscribers()
	for _, p := range pubs {
		p.close()
	}
	for _, s := range subs {
		s.close()
	}
}

type track struct {
	room    *room
	remote  *webrtc.TrackRemote
	pub     *webrtc.PeerConnection
	lastPLI atomic.Int64

	mu   sync.RWMutex
	subs map[*webrtc.TrackLocalStaticRTP]struct{}
	// subLayers is the layer mask per subscriber binding (layers.go).
	// A binding missing from this map gets the full mask.
	subLayers map[*webrtc.TrackLocalStaticRTP]layerMask
}

func (t *track) forward() {
	defer t.room.remove(t)
	t.forwardLayered()
}

func (t *track) addSub(local *webrtc.TrackLocalStaticRTP) {
	t.addSubWithMask(local, layerMaskAll)
}

func (t *track) removeSub(local *webrtc.TrackLocalStaticRTP) {
	t.mu.Lock()
	delete(t.subs, local)
	delete(t.subLayers, local)
	t.mu.Unlock()
}

func (t *track) requestKeyframe() {
	now := time.Now().UnixNano()
	last := t.lastPLI.Load()
	if now-last < int64(time.Second) {
		return
	}
	if !t.lastPLI.CompareAndSwap(last, now) {
		return
	}
	_ = t.pub.WriteRTCP([]rtcp.Packet{
		&rtcp.PictureLossIndication{MediaSSRC: uint32(t.remote.SSRC())},
	})
}

type publisher struct {
	pc      *webrtc.PeerConnection
	release func()
	once    sync.Once
	// subject is the token identity that published; "" when auth is off.
	subject string
	room    *room
}

func (p *publisher) close() {
	p.once.Do(func() {
		if p.room != nil {
			p.room.removePublisher(p)
		}
		_ = p.pc.Close()
		p.release()
	})
}

type binding struct {
	src   *track
	local *webrtc.TrackLocalStaticRTP
}

type subscriber struct {
	pc      *webrtc.PeerConnection
	release func()
	once    sync.Once
	// subject is the token identity that subscribed; "" when auth is off.
	subject string
	room    *room

	mu       sync.Mutex
	closed   bool
	bindings []binding
}

func (s *subscriber) attach(rm *room, slots map[string]int) error {
	for _, src := range rm.snapshot() {
		kind := src.remote.Kind().String()
		if slots[kind] <= 0 {
			continue
		}
		local, err := webrtc.NewTrackLocalStaticRTP(
			src.remote.Codec().RTPCodecCapability,
			src.remote.ID(),
			src.remote.StreamID(),
		)
		if err != nil {
			return err
		}
		sender, err := s.pc.AddTrack(local)
		if err != nil {
			return err
		}
		s.mu.Lock()
		if s.closed {
			s.mu.Unlock()
			return errors.New("subscriber closed during setup")
		}
		s.bindings = append(s.bindings, binding{src: src, local: local})
		// Layered send (layers.go): audio bindings want the base layer
		// only — every audio packet is base anyway — video bindings want
		// all layers by default.
		mask := layerMaskAll
		if kind == "audio" {
			mask = layerMaskAudio
		}
		src.addSubWithMask(local, mask)
		s.mu.Unlock()
		slots[kind]--
		go pumpSubscriberRTCP(sender, src)
	}
	return nil
}

func (s *subscriber) requestKeyframes() {
	s.mu.Lock()
	list := append([]binding(nil), s.bindings...)
	s.mu.Unlock()
	for _, b := range list {
		b.src.requestKeyframe()
	}
}

func (s *subscriber) close() {
	s.once.Do(func() {
		if s.room != nil {
			s.room.removeSubscriber(s)
		}
		s.mu.Lock()
		s.closed = true
		list := s.bindings
		s.bindings = nil
		s.mu.Unlock()
		for _, b := range list {
			b.src.removeSub(b.local)
		}
		_ = s.pc.Close()
		s.release()
	})
}

func pumpSubscriberRTCP(sender *webrtc.RTPSender, src *track) {
	for {
		pkts, _, err := sender.ReadRTCP()
		if err != nil {
			return
		}
		for _, p := range pkts {
			switch p.(type) {
			case *rtcp.PictureLossIndication, *rtcp.FullIntraRequest:
				src.requestKeyframe()
			}
		}
	}
}

type server struct {
	api *webrtc.API
	// auth verifies per-user tokens. Nil means no auth is configured:
	// requests pass through. Only servers built by hand in tests and the
	// smoke test take that path; main() always sets it and refuses to
	// start without a key.
	auth           *authVerifier
	maxRooms       int
	maxPublishers  int64
	maxSubscribers int64
	publishers     atomic.Int64
	subscribers    atomic.Int64

	mu    sync.Mutex
	rooms map[string]*room
}

// claimsCtxKey carries the verified token claims into a handler.
type claimsCtxKey struct{}

func claimsFromContext(r *http.Request) *tokenClaims {
	claims, _ := r.Context().Value(claimsCtxKey{}).(*tokenClaims)
	return claims
}

// bearerToken pulls the token from "Authorization: Bearer <token>".
func bearerToken(r *http.Request) string {
	h := r.Header.Get("Authorization")
	tok, ok := strings.CutPrefix(h, "Bearer ")
	if !ok {
		return ""
	}
	return tok
}

// requireRole rejects requests whose Bearer token is not for the room in
// the path and does not grant one of the given roles. When no verifier is
// configured the request passes through. Verified claims are stored in the
// request context for the handler (subject). Auth runs before any slot is
// taken, so unauthenticated requests cannot burn publisher/subscriber
// capacity.
func (s *server) requireRole(roles ...string) func(http.HandlerFunc) http.HandlerFunc {
	return func(next http.HandlerFunc) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			if s.auth != nil {
				claims, err := s.auth.authorize(bearerToken(r), r.PathValue("room"), roles...)
				if err != nil {
					http.Error(w, "unauthorized", http.StatusUnauthorized)
					return
				}
				r = r.WithContext(context.WithValue(r.Context(), claimsCtxKey{}, claims))
			}
			next(w, r)
		}
	}
}

// requireAnyToken rejects requests without a valid (signed, unexpired)
// Bearer token, regardless of room or role. Used for GET /api/rooms,
// where no single room is in the path.
func (s *server) requireAnyToken(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if s.auth != nil {
			if _, err := s.auth.verify(bearerToken(r)); err != nil {
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
		}
		next(w, r)
	}
}

func validRoomName(name string) bool {
	if len(name) == 0 || len(name) > 64 {
		return false
	}
	for i := 0; i < len(name); i++ {
		c := name[i]
		if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_') {
			return false
		}
	}
	return true
}

func (s *server) roomFor(name string, create bool) (*room, error) {
	if !validRoomName(name) {
		return nil, &reject{code: http.StatusBadRequest, msg: "room name must be 1-64 letters, digits, '-' or '_'"}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if rm, ok := s.rooms[name]; ok {
		return rm, nil
	}
	if !create {
		return nil, &reject{code: http.StatusNotFound, msg: "no such room"}
	}
	if len(s.rooms) >= s.maxRooms {
		return nil, &reject{code: http.StatusServiceUnavailable, msg: "room limit reached"}
	}
	rm := &room{
		tracks:      make(map[string]*track),
		publishers:  make(map[*publisher]struct{}),
		subscribers: make(map[*subscriber]struct{}),
	}
	s.rooms[name] = rm
	return rm, nil
}

func acquire(n *atomic.Int64, limit int64) bool {
	if n.Add(1) > limit {
		n.Add(-1)
		return false
	}
	return true
}

func readOffer(w http.ResponseWriter, r *http.Request) (string, error) {
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 64<<10))
	if err != nil || len(body) == 0 {
		return "", &reject{code: http.StatusBadRequest, msg: "expected an SDP offer body (max 64 KiB)"}
	}
	return string(body), nil
}

func writeSDP(w http.ResponseWriter, sdp string) {
	w.Header().Set("Content-Type", "application/sdp")
	_, _ = io.WriteString(w, sdp)
}

func negotiate(pc *webrtc.PeerConnection, offer string, attach func() error) (string, error) {
	if err := pc.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeOffer, SDP: offer}); err != nil {
		return "", &reject{code: http.StatusBadRequest, msg: "invalid SDP offer"}
	}
	if attach != nil {
		if err := attach(); err != nil {
			return "", err
		}
	}
	answer, err := pc.CreateAnswer(nil)
	if err != nil {
		return "", err
	}
	gathered := webrtc.GatheringCompletePromise(pc)
	if err := pc.SetLocalDescription(answer); err != nil {
		return "", err
	}
	select {
	case <-gathered:
	case <-time.After(5 * time.Second):
		return "", &reject{code: http.StatusGatewayTimeout, msg: "ICE gathering timed out"}
	}
	local := pc.LocalDescription()
	if local == nil {
		return "", errors.New("missing local description")
	}
	return local.SDP, nil
}

func (s *server) handlePublish(w http.ResponseWriter, r *http.Request) {
	if !acquire(&s.publishers, s.maxPublishers) {
		fail(w, &reject{code: http.StatusServiceUnavailable, msg: "publisher limit reached"})
		return
	}
	rm, err := s.roomFor(r.PathValue("room"), true)
	if err != nil {
		s.publishers.Add(-1)
		fail(w, err)
		return
	}
	offer, err := readOffer(w, r)
	if err != nil {
		s.publishers.Add(-1)
		fail(w, err)
		return
	}
	pc, err := s.api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		s.publishers.Add(-1)
		fail(w, err)
		return
	}
	p := &publisher{pc: pc, release: func() { s.publishers.Add(-1) }, room: rm}
	if claims := claimsFromContext(r); claims != nil {
		p.subject = claims.Subject
	}
	rm.addPublisher(p)
	pc.OnTrack(func(remote *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		t := &track{
			room:   rm,
			remote: remote,
			pub:    pc,
			subs:   make(map[*webrtc.TrackLocalStaticRTP]struct{}),
		}
		rm.add(t)
		go t.forward()
	})
	pc.OnConnectionStateChange(func(st webrtc.PeerConnectionState) {
		if st == webrtc.PeerConnectionStateFailed || st == webrtc.PeerConnectionStateClosed {
			go p.close()
		}
	})
	answer, err := negotiate(pc, offer, nil)
	if err != nil {
		p.close()
		fail(w, err)
		return
	}
	writeSDP(w, answer)
}

func (s *server) handleSubscribe(w http.ResponseWriter, r *http.Request) {
	if !acquire(&s.subscribers, s.maxSubscribers) {
		fail(w, &reject{code: http.StatusServiceUnavailable, msg: "subscriber limit reached"})
		return
	}
	rm, err := s.roomFor(r.PathValue("room"), false)
	if err != nil {
		s.subscribers.Add(-1)
		fail(w, err)
		return
	}
	offer, err := readOffer(w, r)
	if err != nil {
		s.subscribers.Add(-1)
		fail(w, err)
		return
	}
	pc, err := s.api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		s.subscribers.Add(-1)
		fail(w, err)
		return
	}
	sub := &subscriber{pc: pc, release: func() { s.subscribers.Add(-1) }, room: rm}
	if claims := claimsFromContext(r); claims != nil {
		sub.subject = claims.Subject
	}
	rm.addSubscriber(sub)
	pc.OnConnectionStateChange(func(st webrtc.PeerConnectionState) {
		switch st {
		case webrtc.PeerConnectionStateConnected:
			go sub.requestKeyframes()
		case webrtc.PeerConnectionStateFailed, webrtc.PeerConnectionStateClosed:
			go sub.close()
		}
	})
	slots := map[string]int{
		"video": strings.Count(offer, "m=video "),
		"audio": strings.Count(offer, "m=audio "),
	}
	answer, err := negotiate(pc, offer, func() error { return sub.attach(rm, slots) })
	if err != nil {
		sub.close()
		fail(w, err)
		return
	}
	writeSDP(w, answer)
}

type trackInfo struct {
	ID   string `json:"id"`
	Kind string `json:"kind"`
}

func (s *server) handleListRoom(w http.ResponseWriter, r *http.Request) {
	rm, err := s.roomFor(r.PathValue("room"), false)
	if err != nil {
		fail(w, err)
		return
	}
	list := []trackInfo{}
	for _, t := range rm.snapshot() {
		list = append(list, trackInfo{ID: t.remote.ID(), Kind: t.remote.Kind().String()})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(list)
}

type roomInfo struct {
	Name        string      `json:"name"`
	Publishers  []string    `json:"publishers"`
	Subscribers []string    `json:"subscribers"`
	Tracks      []trackInfo `json:"tracks"`
}

// handleListRooms lists every room with its participant identities and
// tracks. Any valid token may call it (no single room is in the path).
func (s *server) handleListRooms(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	names := make([]string, 0, len(s.rooms))
	for name := range s.rooms {
		names = append(names, name)
	}
	s.mu.Unlock()
	out := []roomInfo{}
	for _, name := range names {
		s.mu.Lock()
		rm, ok := s.rooms[name]
		s.mu.Unlock()
		if !ok {
			continue // closed between listing and reading
		}
		info := roomInfo{Name: name, Publishers: []string{}, Subscribers: []string{}, Tracks: []trackInfo{}}
		for _, p := range rm.snapshotPublishers() {
			info.Publishers = append(info.Publishers, p.subject)
		}
		for _, sub := range rm.snapshotSubscribers() {
			info.Subscribers = append(info.Subscribers, sub.subject)
		}
		for _, t := range rm.snapshot() {
			info.Tracks = append(info.Tracks, trackInfo{ID: t.remote.ID(), Kind: t.remote.Kind().String()})
		}
		out = append(out, info)
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}

// handleCloseRoom closes every participant in the room and drops the room.
// The room is removed from the map first, so a publish racing the close
// creates a fresh room instead of joining a closing one.
func (s *server) handleCloseRoom(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("room")
	if !validRoomName(name) {
		fail(w, &reject{code: http.StatusBadRequest, msg: "room name must be 1-64 letters, digits, '-' or '_'"})
		return
	}
	s.mu.Lock()
	rm, ok := s.rooms[name]
	if ok {
		delete(s.rooms, name)
	}
	s.mu.Unlock()
	if !ok {
		fail(w, &reject{code: http.StatusNotFound, msg: "no such room"})
		return
	}
	rm.closeAll()
	w.WriteHeader(http.StatusNoContent)
}

type kickRequest struct {
	User string `json:"user"`
}

// handleKick closes every participant in the room whose token identity
// matches the requested user. The publish role is required: kicking is a
// room-operator action.
func (s *server) handleKick(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("room")
	if !validRoomName(name) {
		fail(w, &reject{code: http.StatusBadRequest, msg: "room name must be 1-64 letters, digits, '-' or '_'"})
		return
	}
	var req kickRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<10)).Decode(&req); err != nil || strings.TrimSpace(req.User) == "" {
		fail(w, &reject{code: http.StatusBadRequest, msg: "expected JSON body {\"user\": \"<identity>\"}"})
		return
	}
	s.mu.Lock()
	rm, ok := s.rooms[name]
	s.mu.Unlock()
	if !ok {
		fail(w, &reject{code: http.StatusNotFound, msg: "no such room"})
		return
	}
	kicked := 0
	for _, p := range rm.snapshotPublishers() {
		if p.subject == req.User {
			p.close()
			kicked++
		}
	}
	for _, sub := range rm.snapshotSubscribers() {
		if sub.subject == req.User {
			sub.close()
			kicked++
		}
	}
	if kicked == 0 {
		fail(w, &reject{code: http.StatusNotFound, msg: "no such participant in this room"})
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]int{"kicked": kicked})
}

// routes wires every endpoint. Shared by main() and the tests so the smoke
// test exercises the same table the server runs.
func (s *server) routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write(indexHTML)
	})
	mux.HandleFunc("POST /api/publish/{room}", s.requireRole(tokenRolePublish)(s.handlePublish))
	mux.HandleFunc("POST /api/subscribe/{room}", s.requireRole(tokenRoleSubscribe)(s.handleSubscribe))
	mux.HandleFunc("GET /api/rooms/{room}", s.requireRole(tokenRolePublish, tokenRoleSubscribe)(s.handleListRoom))
	mux.HandleFunc("GET /api/rooms", s.requireAnyToken(s.handleListRooms))
	mux.HandleFunc("DELETE /api/rooms/{room}", s.requireRole(tokenRolePublish)(s.handleCloseRoom))
	mux.HandleFunc("POST /api/rooms/{room}/kick", s.requireRole(tokenRolePublish)(s.handleKick))
	return mux
}

func newAPI(udpPort int, mdns bool) (*webrtc.API, error) {
	mux, err := ice.NewMultiUDPMuxFromPort(
		udpPort,
		ice.UDPMuxFromPortWithNetworks(ice.NetworkTypeUDP4),
		ice.UDPMuxFromPortWithLoopback(),
	)
	if err != nil {
		return nil, err
	}
	se := webrtc.SettingEngine{}
	se.SetICEUDPMux(mux)
	se.SetNetworkTypes([]webrtc.NetworkType{webrtc.NetworkTypeUDP4})
	se.SetIncludeLoopbackCandidate(true)
	mdnsMode := ice.MulticastDNSModeDisabled
	if mdns {
		mdnsMode = ice.MulticastDNSModeQueryOnly
	}
	se.SetICEMulticastDNSMode(mdnsMode)

	m := &webrtc.MediaEngine{}
	if err := m.RegisterDefaultCodecs(); err != nil {
		return nil, err
	}
	reg := &interceptor.Registry{}
	if err := webrtc.RegisterDefaultInterceptorsWithOptions(
		m,
		reg,
		webrtc.WithNackResponderOptions(nack.ResponderSize(256)),
	); err != nil {
		return nil, err
	}
	return webrtc.NewAPI(
		webrtc.WithSettingEngine(se),
		webrtc.WithMediaEngine(m),
		webrtc.WithInterceptorRegistry(reg),
	), nil
}

// runTokenCommand implements `hami-sfu token --room demo --user alice
// --role publish --ttl 1h`. It prints one token to stdout and never
// prints the key.
func runTokenCommand(args []string) error {
	fs := flag.NewFlagSet("token", flag.ContinueOnError)
	room := fs.String("room", "", "room the token is for (required)")
	user := fs.String("user", "", "identity the token names (required)")
	role := fs.String("role", "", "comma-separated roles: publish, subscribe (required)")
	ttl := fs.Duration("ttl", time.Hour, "token lifetime, max 24h")
	keyFile := fs.String("hmac-key-file", "", "HMAC key file (mode 0600); else HAMI_SFU_HMAC_KEY_FILE / HAMI_SFU_HMAC_KEY")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if strings.TrimSpace(*room) == "" {
		return errors.New("--room is required")
	}
	if !validRoomName(*room) {
		return errors.New("--room must be 1-64 letters, digits, '-' or '_'")
	}
	if strings.TrimSpace(*user) == "" {
		return errors.New("--user is required (the publisher or viewer identity)")
	}
	if *ttl <= 0 || *ttl > tokenMaxTTL {
		return fmt.Errorf("--ttl must be above 0 and at most %s", tokenMaxTTL)
	}
	var roles []string
	for _, r := range strings.Split(*role, ",") {
		r = strings.TrimSpace(r)
		if r == "" {
			continue
		}
		if !validTokenRole(r) {
			return fmt.Errorf("unknown token role %q (want %q or %q)", r, tokenRolePublish, tokenRoleSubscribe)
		}
		roles = append(roles, r)
	}
	if len(roles) == 0 {
		return errors.New("--role is required (publish, subscribe, or both)")
	}
	key, err := loadHMACKey(*keyFile)
	if err != nil {
		return err
	}
	v, err := newAuthVerifier(key)
	if err != nil {
		return err
	}
	tok, err := v.mint(*room, *user, roles, *ttl)
	if err != nil {
		return err
	}
	fmt.Println(tok)
	return nil
}

func main() {
	addr := flag.String("addr", ":8080", "HTTP(S) listen address")
	udpPort := flag.Int("udp-port", 7000, "shared UDP port")
	mdns := flag.Bool("mdns", true, "resolve .local LAN candidates")
	maxRooms := flag.Int("max-rooms", 8, "maximum rooms")
	maxPublishers := flag.Int("max-publishers", 8, "maximum publishers")
	maxSubscribers := flag.Int("max-subscribers", 50, "maximum subscribers")
	memMB := flag.Int64("mem-limit-mb", 256, "Go heap limit in MiB")
	hmacKeyFile := flag.String("hmac-key-file", "", "HMAC key file (mode 0600) for per-user tokens; else HAMI_SFU_HMAC_KEY_FILE / HAMI_SFU_HMAC_KEY")
	tlsCert := flag.String("tls-cert", "", "TLS certificate")
	tlsKey := flag.String("tls-key", "", "TLS private key")
	flag.Parse()

	// `hami-sfu token ...` mints a token and exits; it never starts the server.
	if flag.Arg(0) == "token" {
		if err := runTokenCommand(flag.Args()[1:]); err != nil {
			log.Fatalf("token: %v", err)
		}
		return
	}

	if (*tlsCert == "") != (*tlsKey == "") {
		log.Fatal("set both -tls-cert and -tls-key, or neither")
	}
	if *udpPort < 1 || *udpPort > 65535 {
		log.Fatal("-udp-port must be between 1 and 65535")
	}
	if *maxRooms < 1 || *maxPublishers < 1 || *maxSubscribers < 1 {
		log.Fatal("-max-rooms, -max-publishers and -max-subscribers must be at least 1")
	}
	if *memMB > 0 {
		debug.SetMemoryLimit(*memMB << 20)
	}

	// Auth is mandatory in serve mode: refuse to start without a key.
	// (The shared -token flag is gone; per-user tokens replace it.)
	key, err := loadHMACKey(*hmacKeyFile)
	if err != nil {
		log.Fatalf("auth: %v", err)
	}
	verifier, err := newAuthVerifier(key)
	if err != nil {
		log.Fatalf("auth: %v", err)
	}

	api, err := newAPI(*udpPort, *mdns)
	if err != nil {
		log.Fatalf("WebRTC setup failed (is UDP port %d already in use?): %v", *udpPort, err)
	}
	s := &server{
		api:            api,
		auth:           verifier,
		maxRooms:       *maxRooms,
		maxPublishers:  int64(*maxPublishers),
		maxSubscribers: int64(*maxSubscribers),
		rooms:          make(map[string]*room),
	}

	mux := s.routes()

	srv := &http.Server{
		Addr:              *addr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
	}
	log.Printf("hami-sfu: http=%s udp=%d mdns=%t rooms<=%d publishers<=%d subscribers<=%d auth=hmac",
		*addr, *udpPort, *mdns, *maxRooms, *maxPublishers, *maxSubscribers)
	if *tlsCert != "" {
		log.Fatal(srv.ListenAndServeTLS(*tlsCert, *tlsKey))
	}
	log.Fatal(srv.ListenAndServe())
}
