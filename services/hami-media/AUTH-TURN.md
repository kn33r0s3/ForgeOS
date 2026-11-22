# Hami SFU: token auth + TURN (Part 3)

## Current auth state (surveyed 22 Nov 2026, before this change)

- The remote SFU process (`-mode=m7h-sfu`) already had a **random
  32-byte Bearer token**, generated per run by `startM7HRemoteSFU`
  and passed to the child via `-m7h-sfu-token`. Every signalling
  endpoint (`/health`, `/publisher`, `/viewer`, `/stats`, …) requires
  it (401 otherwise). It authenticates the *harness to its own local
  child process* — it says nothing about which room or role a client
  has, and it never expires.
- The router has an **authorize/subscribe allow-list**:
  `authorizeSubscription(viewerID, key)` records that a viewer may
  receive a track; `subscribe()` returns `errSFUUnauthorized`
  otherwise. `TestLocalSFURoutesAuthorizedStreamsAndRTCP` proves an
  unauthorized subscription is denied. But `handleViewer`
  auto-authorized every viewer that presented the Bearer token, so
  any Bearer holder could subscribe to any track.
- There was **no room concept, no per-client token, no expiry, and
  no TURN/STUN anywhere**: every `PeerConnection` was created with
  an empty `webrtc.Configuration{}` (no `ICEServer` in the tree).

## Token authentication

**Format** (no external JWT dependency; stdlib only):

```
token = base64url(JSON claims) "." base64url(HMAC-SHA256(key, payload))
{"room":"default","roles":["publish","subscribe"],"sub":"alice","exp":1790000000,"iat":1789996400}
```

- `room`: the SFU room (one room per SFU process).
- `roles`: subset of `["publish", "subscribe"]`.
- `sub`: required publisher/viewer identity; the request ID must match it.
- `exp`: unix seconds; rejected at/after `exp` with no clock-skew allowance.
- `iat`: minted-at unix seconds.

**Key source** (never hardcoded, never logged, never printed):

- `HAMI_SFU_HMAC_KEY_FILE` — path to a file holding the key
  (preferred; 0600), or
- `HAMI_SFU_HMAC_KEY` — the key in the environment.

Minimum 32 characters. The room comes from `HAMI_SFU_ROOM`
(default `"default"`).

**Enforcement point:** the HTTP signalling handlers in `main.go`.

- `POST /publisher` requires a token with role `publish`.
- `POST /viewer` requires a token with role `subscribe`.
- Missing, malformed, expired, wrong-room, wrong-role, or
  wrong-key token → **HTTP 401** `{"error":"invalid or expired
  token"}`. No `PeerConnection` is created and no track is
  authorized on rejection.
- The `m7h-sfu` server **refuses to start without a key**
  (`runM7HSFUServer` fails closed). The in-process harness
  (`startM7HRemoteSFU`) generates a fresh random 32-byte key per
  run, passes it to the child through its environment, and mints
  1-hour tokens for its own publish/subscribe calls — so the
  existing harness works with auth on.
- The router's `authorizeSubscription` allow-list is unchanged and
  still gates `subscribe()` in-process.

**Minting tokens** (operator helper, no key exposure):

```sh
HAMI_SFU_HMAC_KEY_FILE=/path/to/hami-sfu-hmac.key \
  ./hami-media -mode=mint-token -token-room default \
  -token-roles publish,subscribe -token-subject alice -token-ttl 1h
# prints only the token
```

**Tests** (`auth_test.go`): mint/verify round-trip; expired,
wrong-key, missing, wrong-room, wrong-role, tampered-payload
rejections; key loading from file and env; and HTTP-level tests
against the real handlers — publish/viewer without a token → 401,
wrong-room/wrong-role/wrong-key → 401, valid publish token → 200
with an SDP answer.

## TURN

**Server:** coturn is not installed on the Mac (checked 22 Nov
2026: no `turnserver`, not in Homebrew), so the local proof uses
`pion/turn` v5.1.3, an existing module dependency. It exercises UDP
TURN, long-term credentials, and relay allocations confined to ports
49152–50152. This is local/test evidence only; public deployment,
external relay addressing, and production readiness are unverified.

**Running it standalone:**

```sh
HAMI_SFU_TURN_USERNAME=hami-turn \
HAMI_SFU_TURN_PASSWORD_FILE=/path/to/turn-password \
HAMI_SFU_TURN_REALM=hami \
HAMI_SFU_TURN_LISTEN=127.0.0.1:3478 \
  ./hami-media -mode=turn-server
```

**Configuration** (environment / files only, never hardcoded or
logged):

| Variable | Meaning | Default |
|---|---|---|
| `HAMI_SFU_TURN_URL` | `turn:` URL clients use | `turn:127.0.0.1:3478` |
| `HAMI_SFU_TURN_USERNAME` | TURN username | — (TURN off without it) |
| `HAMI_SFU_TURN_PASSWORD` / `HAMI_SFU_TURN_PASSWORD_FILE` | TURN password | — |
| `HAMI_SFU_TURN_REALM` | TURN realm | `hami` |
| `HAMI_SFU_TURN_LISTEN` | listen address for `-mode=turn-server` | `127.0.0.1:3478` |

**Local proof:** build the test `PeerConnection` with
`sfuTURNICEConfiguration(cfg, true)` — `ICEServers` pointing at
the TURN URL with the username/credential, and
`ICETransportPolicyRelay`, so every candidate is a relay candidate
and test media flows through the local TURN server. The SFU side
keeps its loopback host candidates. No public network, Cloud service,
or paid tier was used or evaluated.

**Proof** (`TestSFUTURNRelayCarriesMedia` in `turn_test.go`):
a relay-only publisher and a relay-only viewer connect through
the TURN server; the test asserts the nominated pair's local
candidate type is `relay` on both client `PeerConnection`s and
that H.264 frames flow publisher → router → viewer. The raw
`part3 TURN relay pair:` log lines carry the proof.

**Measured proof (Mac, 22 Nov 2026, go 1.27.4 darwin/arm64):**

- Full suite `82 pass / 0 fail / 0 skip` (20.9 s), including all
  5 UDP loopback tests and the relay test (6.07 s).
- Relay lines from the raw log:
  `part3 TURN relay pair: viewer … state=succeeded
  local=127.0.0.1:49734/udp/relay remote=127.0.0.1:56401/udp/host`
  and `publisher … local=127.0.0.1:49495/udp/relay
  remote=127.0.0.1:56401/udp/host`;
  `part3 TURN relay proof: video frames sent=33 video packets
  received=66`.
- On Linux (this VM, UDP blocked) the same suite is `76 pass /
  6 fail`: the 5 known loopback tests plus the relay test fail
  with `sendto: operation not permitted` on 127.0.0.1 UDP — a
  sandbox artifact, not a code failure.

**Binary-level smoke** (`~/hami/logs/part3-smoke-006.log` and
`part3-smoke-001.log`, 22 Nov 2026):

- `-mode=mint-token` prints a 2-part, 184-char token; a bad role
  is rejected.
- `-mode=m7h-sfu` without a key refuses to start, exit 1:
  `run local M7-H SFU process: load SFU token auth: no HMAC key
  configured: set HAMI_SFU_HMAC_KEY_FILE or HAMI_SFU_HMAC_KEY`.
- `-mode=m7h-sfu` with a key starts (`auth=on room=default`) and
  enforces auth over HTTP: `/health` 401 without Bearer, 200
  `{"status":"ready"}` with it; `POST /publisher` with Bearer
  but no HMAC token → 401 `{"error":"invalid or expired
  token"}`; `POST /shutdown` → 200, process exits 0.
- `-mode=turn-server` listens on `127.0.0.1:13478` (confirmed
  with `lsof`, UDP) and stops cleanly on kill.
- Note for anyone launching `m7h-sfu` by hand: it needs the
  inherited listener on **fd 3**. A launcher must get the socket
  onto fd 3 with *both* `preexec_fn: dup2(fd, 3)` *and*
  `pass_fds=(3,)` — either alone leaves the child without fd 3
  (the loop shell itself holds fd 3, so the socket is fd 4), and
  the child then dies in a Go runtime `netpoll failed` crash
  instead of printing its error. The real harness passes the
  listener via `exec.Cmd.ExtraFiles`, which is correct.

## Files

- `auth.go` — token mint/verify, key loading, `authorizeToken`.
- `auth_test.go` — token + HTTP auth tests.
- `turn.go` — TURN server, TURN env config, relay pair inspection.
- `turn_test.go` — TURN config, wrong-credentials, relay proof.
- `main.go` — wiring only: `Token` on the SDP request structs,
  key generation + token minting in the harness client, mandatory
  key load + 401 enforcement in the server handlers,
  `-mode=mint-token` and `-mode=turn-server`.
- `go.mod` — `go mod tidy`: `pion/turn` (and the other packages
  `main.go` already imported) promoted from `// indirect` to
  direct requires. No version changes; `go.sum` unchanged.
