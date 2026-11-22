# Hami SFU

Standalone Pion WebRTC SFU with one shared UDP port.

## Run locally

```bash
cd /Users/nirojpaudyal/Downloads/ForgeOS/hami-sfu
TOKEN=$(cat /tmp/hami-sfu-token.txt)
./hami-sfu -addr 127.0.0.1:8080 -udp-port 7000 -token "$TOKEN" -mdns=false
```

Open `http://localhost:8080`.

The current local server process uses port 8080 for HTTP and UDP port 7000
for WebRTC. The bearer token is stored with mode `0600` at
`/tmp/hami-sfu-token.txt`.

## Build

```bash
go vet ./...
go build -o hami-sfu .
```

## LAN or HTTPS

For LAN HTTP watching, listen on all interfaces:

```bash
./hami-sfu -addr :8080 -udp-port 7000 -token "$TOKEN" -mdns=false
```

For publishing from another device, use HTTPS with a locally trusted
certificate. Publishing from plain HTTP is blocked by browser media security.
