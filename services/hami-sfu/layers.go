// layers.go — layered packet sender for hami-sfu.
//
// Niroj's idea (22 Nov 2026): cut CPU / infrastructure cost by dividing
// media packets into layers, sending them layer by layer, one by one, to
// users, then clearing each layer after it is sent — nothing held, nothing
// buffered.
//
// One packet belongs to exactly one layer. Packets stay in arrival /
// sequence order — reordering across layers would break RTP playback, so
// "layer one by one" means classification + masked fan-out + clear, not
// reordering. The saving is: (a) a packet is written only to the
// subscribers whose layer mask includes it, (b) the forwarder retains zero
// bytes between packets, (c) writes happen outside the track lock.
//
// Layer 0 BASE: audio packets + video parameter sets — every subscriber.
// Layer 1 KEY: video keyframes — video subscribers, to (re)sync.
// Layer 2 DELTA: video non-keyframes — video subscribers only, first to drop.
package main

import (
	"encoding/binary"
	"strings"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

// layer is one division of the packet stream. Lower is more essential.
type layer int

const (
	layerBase  layer = 0 // audio + video parameter sets
	layerKey   layer = 1 // video keyframes
	layerDelta layer = 2 // video non-keyframes
	layerCount       = 3
)

// layerMask is a bitmask of the layers a subscriber wants.
type layerMask uint8

const (
	layerMaskBase  layerMask = 1 << layerBase
	layerMaskKey   layerMask = 1 << layerKey
	layerMaskDelta layerMask = 1 << layerDelta
	layerMaskAll   layerMask = layerMaskBase | layerMaskKey | layerMaskDelta
	// layerMaskAudio is for audio-only listeners: base layer only.
	layerMaskAudio layerMask = layerMaskBase
	// layerMaskKeyframesOnly is the low-bandwidth video mode: audio +
	// keyframes, no delta packets.
	layerMaskKeyframesOnly layerMask = layerMaskBase | layerMaskKey
)

func (m layerMask) includes(l layer) bool {
	return m&(1<<uint(l)) != 0
}

// packetSink is anything one RTP packet can be written to.
// *webrtc.TrackLocalStaticRTP satisfies it; tests use a recording fake.
type packetSink interface {
	WriteRTP(*rtp.Packet) error
}

// layerSub is one subscriber binding in the layered sender: a sink plus
// the layers it wants.
type layerSub struct {
	sink packetSink
	mask layerMask
}

// classifyPacket decides which layer an RTP packet belongs to.
// codec is the track codec, e.g. "audio/opus", "video/H264", "video/VP8".
// Audio is always the base layer. Unknown codecs fall back to the base
// layer — safe default, every subscriber gets the packet.
func classifyPacket(codec string, pkt *rtp.Packet) layer {
	if pkt == nil {
		return layerDelta
	}
	if hasPrefixFold(codec, "audio/") {
		return layerBase
	}
	if strings.EqualFold(codec, "video/H264") {
		if isH264ParameterSet(pkt.Payload) {
			return layerBase
		}
		if isH264IDRStart(pkt.Payload) {
			return layerKey
		}
		return layerDelta
	}
	if strings.EqualFold(codec, "video/VP8") {
		if isVP8Keyframe(pkt.Payload) {
			return layerKey
		}
		return layerDelta
	}
	if hasPrefixFold(codec, "video/") {
		return layerDelta
	}
	return layerBase
}

// hasPrefixFold is strings.HasPrefix without allocating: EqualFold on a
// short prefix does not allocate, while strings.ToLower would allocate a
// new string on every packet. The classifier runs on the hot path.
func hasPrefixFold(s, prefix string) bool {
	if len(s) < len(prefix) {
		return false
	}
	return strings.EqualFold(s[:len(prefix)], prefix)
}

// isH264IDRStart reports whether payload starts a keyframe.
// Ported from services/hami-media's isH264IDRStart (same algorithm):
// single NAL type 5, STAP-A (24) containing a type-5 NAL, or FU-A (28/29)
// start fragment of type 5.
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

// isH264ParameterSet reports whether payload is only H264 parameter sets
// (SPS type 7 / PPS type 8), in any packetization the sender uses.
// Ported from services/hami-media's isH264RecoveryConfig (same algorithm).
func isH264ParameterSet(payload []byte) bool {
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

// isVP8Keyframe reports whether a VP8 payload is a keyframe.
// VP8 payload descriptor first byte, bit 0: 0 = keyframe, 1 = interframe.
func isVP8Keyframe(payload []byte) bool {
	if len(payload) == 0 {
		return false
	}
	return payload[0]&0x01 == 0
}

// clearPacket releases every byte the forwarder holds for pkt. After this
// the packet is dead — it must not be written or read again.
func clearPacket(pkt *rtp.Packet) {
	if pkt == nil {
		return
	}
	pkt.Payload = nil
	pkt.Raw = nil
	pkt.Header = rtp.Header{}
}

// layerFanout sends pkt to exactly the subscribers whose mask includes
// the packet's layer, one by one, then clears the packet so the sender
// retains nothing. It returns how many subscribers received it; the first
// write error is returned, but sending continues to the rest.
func layerFanout(pkt *rtp.Packet, l layer, subs []layerSub) (sent int, err error) {
	for _, sub := range subs {
		if !sub.mask.includes(l) {
			continue
		}
		if werr := sub.sink.WriteRTP(pkt); werr != nil {
			if err == nil {
				err = werr
			}
			continue
		}
		sent++
	}
	clearPacket(pkt)
	return sent, err
}

// fanoutDirect is the pre-layer behaviour, kept as the benchmark
// before-state: one packet to every subscriber, no classification, no
// mask, no clear.
func fanoutDirect(pkt *rtp.Packet, subs []layerSub) (sent int, err error) {
	for _, sub := range subs {
		if werr := sub.sink.WriteRTP(pkt); werr != nil {
			if err == nil {
				err = werr
			}
			continue
		}
		sent++
	}
	return sent, err
}

// snapshotLayerSubs returns the track's subscribers as a snapshot with
// their layer masks. Subscribers without an explicit mask get all layers.
// The snapshot is taken under a short read-lock; the caller writes to the
// sinks without holding the track lock.
func (t *track) snapshotLayerSubs() []layerSub {
	t.mu.RLock()
	defer t.mu.RUnlock()
	out := make([]layerSub, 0, len(t.subs))
	for local := range t.subs {
		mask, ok := t.subLayers[local]
		if !ok {
			mask = layerMaskAll
		}
		out = append(out, layerSub{sink: local, mask: mask})
	}
	return out
}

// setSubLayerMask changes one subscriber binding's layer mask. A
// subscriber that had no explicit mask keeps the full mask until this is
// called; unknown bindings are ignored.
func (t *track) setSubLayerMask(local *webrtc.TrackLocalStaticRTP, mask layerMask) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if _, ok := t.subs[local]; !ok {
		return
	}
	if t.subLayers == nil {
		t.subLayers = make(map[*webrtc.TrackLocalStaticRTP]layerMask)
	}
	t.subLayers[local] = mask
}

// addSubWithMask registers a subscriber binding with an explicit layer
// mask. addSub keeps the old behaviour (full mask).
func (t *track) addSubWithMask(local *webrtc.TrackLocalStaticRTP, mask layerMask) {
	t.mu.Lock()
	t.subs[local] = struct{}{}
	if t.subLayers == nil {
		t.subLayers = make(map[*webrtc.TrackLocalStaticRTP]layerMask)
	}
	t.subLayers[local] = mask
	t.mu.Unlock()
}

// forwardLayered is the layered send path: read one packet, classify it
// into a layer, pass it to exactly the subscribers whose mask includes
// that layer, then clear it so nothing is held between packets.
func (t *track) forwardLayered() {
	codec := t.remote.Codec().RTPCodecCapability.MimeType
	for {
		pkt, _, err := t.remote.ReadRTP()
		if err != nil {
			return
		}
		l := classifyPacket(codec, pkt)
		subs := t.snapshotLayerSubs()
		_, _ = layerFanout(pkt, l, subs)
	}
}

// forwardDirect is the pre-layer send path, kept for benchmarking:
// one packet to every subscriber under the track read-lock.
func (t *track) forwardDirect() {
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
