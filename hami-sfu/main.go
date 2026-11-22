// hami-sfu is a small self-hosted WebRTC selective forwarding unit (SFU).
//
// POST /api/publish/{room}    SDP offer -> SDP answer
// GET  /api/rooms/{room}      track list
// POST /api/subscribe/{room}  SDP offer -> SDP answer
package main

import (
	"crypto/subtle"
	_ "embed"
	"encoding/json"
	"errors"
	"flag"
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

type track struct {
	room    *room
	remote  *webrtc.TrackRemote
	pub     *webrtc.PeerConnection
	lastPLI atomic.Int64

	mu   sync.RWMutex
	subs map[*webrtc.TrackLocalStaticRTP]struct{}
}

func (t *track) forward() {
	defer t.room.remove(t)
	for {
		pkt, _, err := t.remote.ReadRTP()
		if err != nil {
			return
		}
		t.mu.RLock()
		for local := range t.subs {
			_ = local.WriteRTP(pkt)
		}
		t.mu.RUnlock()
	}
}

func (t *track) addSub(local *webrtc.TrackLocalStaticRTP) {
	t.mu.Lock()
	t.subs[local] = struct{}{}
	t.mu.Unlock()
}

func (t *track) removeSub(local *webrtc.TrackLocalStaticRTP) {
	t.mu.Lock()
	delete(t.subs, local)
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
}

func (p *publisher) close() {
	p.once.Do(func() {
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
		src.addSub(local)
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
	api            *webrtc.API
	token          string
	maxRooms       int
	maxPublishers  int64
	maxSubscribers int64
	publishers     atomic.Int64
	subscribers    atomic.Int64

	mu    sync.Mutex
	rooms map[string]*room
}

func (s *server) auth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if s.token != "" {
			want := []byte("Bearer " + s.token)
			got := []byte(r.Header.Get("Authorization"))
			if subtle.ConstantTimeCompare(got, want) != 1 {
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
	rm := &room{tracks: make(map[string]*track)}
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
	p := &publisher{pc: pc, release: func() { s.publishers.Add(-1) }}
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
	sub := &subscriber{pc: pc, release: func() { s.subscribers.Add(-1) }}
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

func main() {
	addr := flag.String("addr", ":8080", "HTTP(S) listen address")
	udpPort := flag.Int("udp-port", 7000, "shared UDP port")
	mdns := flag.Bool("mdns", true, "resolve .local LAN candidates")
	maxRooms := flag.Int("max-rooms", 8, "maximum rooms")
	maxPublishers := flag.Int("max-publishers", 8, "maximum publishers")
	maxSubscribers := flag.Int("max-subscribers", 50, "maximum subscribers")
	memMB := flag.Int64("mem-limit-mb", 256, "Go heap limit in MiB")
	token := flag.String("token", "", "shared bearer token")
	tlsCert := flag.String("tls-cert", "", "TLS certificate")
	tlsKey := flag.String("tls-key", "", "TLS private key")
	flag.Parse()

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

	api, err := newAPI(*udpPort, *mdns)
	if err != nil {
		log.Fatalf("WebRTC setup failed (is UDP port %d already in use?): %v", *udpPort, err)
	}
	s := &server{
		api:            api,
		token:          *token,
		maxRooms:       *maxRooms,
		maxPublishers:  int64(*maxPublishers),
		maxSubscribers: int64(*maxSubscribers),
		rooms:          make(map[string]*room),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write(indexHTML)
	})
	mux.HandleFunc("POST /api/publish/{room}", s.auth(s.handlePublish))
	mux.HandleFunc("POST /api/subscribe/{room}", s.auth(s.handleSubscribe))
	mux.HandleFunc("GET /api/rooms/{room}", s.auth(s.handleListRoom))

	srv := &http.Server{
		Addr:              *addr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
	}
	log.Printf("hami-sfu: http=%s udp=%d mdns=%t rooms<=%d publishers<=%d subscribers<=%d",
		*addr, *udpPort, *mdns, *maxRooms, *maxPublishers, *maxSubscribers)
	if *tlsCert != "" {
		log.Fatal(srv.ListenAndServeTLS(*tlsCert, *tlsKey))
	}
	log.Fatal(srv.ListenAndServe())
}
