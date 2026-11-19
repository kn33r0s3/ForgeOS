# Hami / ForgeOS Docker commands

The canonical web interface is the root Vite app on port 8080. Compose runs the
FastAPI backend (port 8000) and optional workers; it does not start the
archived Next.js dashboard by default.

## Recommended combined startup

```bash
FORGEOS_USE_DOCKER=true ./start.sh
# Canonical Hami UI: http://localhost:8080
# Backend docs: http://localhost:8000/docs
```

## Backend-only Compose startup

```bash
docker compose up --build -d
curl http://localhost:8000/health
```

## Optional local profiles

```bash
# Existing scheduler/maintenance process
docker compose --profile worker up --build -d

# Archived Next.js dashboard (not canonical Hami); loopback only
docker compose --profile legacy-frontend up --build

# For local x402 testing, add explicit X402_RESOURCE_URL and X402_PAY_TO values
# to an uncommitted .env file; EVIDENCE_TRIAGE_URL is a separate proxy setting.
# X402_RESOURCE_URL must name the actual x402 endpoint (for local tests only):
# X402_RESOURCE_URL=http://127.0.0.1:8787/triage
# X402_PAY_TO=<authorized-wallet-address>
# EVIDENCE_TRIAGE_URL=http://evidence-triage:8787
docker compose --profile paid-triage up --build
```

## Optional local LiveKit proving ground

This profile is separate from normal Hami startup. It uses a local-only development
key/secret and binds host ports to `127.0.0.1`; it is not a production deployment
and must not be exposed to a LAN or the public internet.

The smoke uses nine separate CLI publisher containers, each publishing LiveKit's
synthetic demo video to the same room, plus 25 simulated subscribers by default
(or more via `LIVEKIT_TEST_SUBSCRIBERS`) for 30 seconds. The local profile and
CI default to `--layout speaker`: each simulated subscriber models one video
at high quality plus five at low quality (six video subscriptions). This is the
lower-subscription speaker-view workload. `LIVEKIT_TEST_LAYOUT=3x3` is an
explicit heavier alternative with nine medium-quality video subscriptions per
simulated subscriber; use it only when testing a nine-tile grid. These are TEST
participants and synthetic media, not real streamers or viewers.

```bash
# Start the local SFU (normal Hami services are not started by this command).
docker compose --profile livekit-local up -d livekit

# Start nine independent demo publishers in the same logical room.
docker compose --profile livekit-local up -d --scale livekit-publisher=9 livekit-publisher

# Run the 30-second / 25-subscriber smoke and print the CLI summary (default).
docker compose --profile livekit-local run --rm livekit-load-test

# CI-equivalent: nine publishers + 100 subscribers using the tuned speaker-view workload.
LIVEKIT_TEST_LAYOUT=speaker LIVEKIT_TEST_SUBSCRIBERS=100 docker compose --profile livekit-local run --rm livekit-load-test

# Optional heavier nine-tile grid workload (nine medium-quality subscriptions per subscriber).
LIVEKIT_TEST_LAYOUT=3x3 LIVEKIT_TEST_SUBSCRIBERS=100 docker compose --profile livekit-local run --rm livekit-load-test

# Inspect service state and publisher/SFU logs.
docker compose --profile livekit-local ps -a
docker compose --profile livekit-local logs --tail 80 livekit
docker compose --profile livekit-local logs --tail 80 livekit-publisher

# Stop only the LiveKit services; leave the rest of Hami's stack untouched.
docker compose --profile livekit-local stop livekit-publisher livekit
```

`stop` leaves exited containers and their logs behind. Check `docker ps` for
active workload and `docker compose --profile livekit-local ps -a` for stopped
containers; preserve the latter's logs until test evidence has been reviewed.

For larger tests, run the load generator on separate machine(s), raise its file
descriptor limit as LiveKit documents (`ulimit -n 65535`), and record actual
publisher/subscriber counts, track layout, bitrate(s), CPU/RAM, egress,
receiver inbound RTP loss deltas, jitter, reconnects, frame/decode/render
statistics and capture-to-render latency percentiles. LiveKit's
[WebRTC stats guide](https://docs.livekit.io/robotics/media/performance/stats/)
says per-track inbound `packets_lost` is cumulative since subscription start;
compare two readings to measure an interval. The CLI's `Pkt. Loss` field counts
`SampleBuilder` drop-callback events, not RTP transport loss. A local smoke does
not establish 4,000-viewer capacity or a 100 ms glass-to-glass guarantee. Each
self-hosted room must fit on one SFU node, and load testing consumes cloud-plan
allowances when run on cloud infrastructure. Capture-to-render latency also
requires timestamped frames and render-side measurement. The local
250-subscriber run recorded 212 callback events, not a valid transport-loss
percentage; see [CAPABILITY_QUEUE.md](./docs/CAPABILITY_QUEUE.md) before
increasing the load.

**Important: pinned CLI v2.19.4 counter semantics.** In
[loadtester.go](https://github.com/livekit/livekit-cli/blob/v2.19.4/pkg/loadtester/loadtester.go#L398-L424),
the CLI increments `dropped` from the SampleBuilder dropped-frame callback,
once per dropped frame, while `packets` counts RTP packets returned by
`PopPackets`. Its [percentage formatter](https://github.com/livekit/livekit-cli/blob/v2.19.4/pkg/loadtester/util.go#L34-L40)
divides those unlike units. The saved 250-subscriber run's 212 is therefore
212 frame-drop callback events, **not 212 RTP packets**; its displayed 0.005%
is not a valid network packet-loss percentage. The 38 nonzero subscriber rows
and zero subscriber errors remain TEST observations; the cause of each event
is unknown. The exact-head CI 100-subscriber smoke had zero such callbacks and
zero subscriber errors, but neither result establishes production capacity.
Do not increase load until actual receiver-side metrics and stop conditions are
defined. A local smoke does not establish 4,000-viewer capacity or a 100 ms
glass-to-glass guarantee.

**Cloud harness remains blocked.** The separate
`docker-compose.livekit-scale.yml` targets LiveKit Cloud. The previous
defaults (10,000 subscribers and 100 joins/second) exceeded the current
published limits. LiveKit's [Cloud load-testing documentation](https://docs.livekit.io/reference/developer-tools/livekit-cli/perf/)
allows at most 50 video publishers, 50 audio publishers and 50 subscribers;
test traffic counts against plan allowances. The CLI's `--num-per-second`
option is documented up to 10 participants/second; that is a CLI option
limit, not a separate Cloud allowance. The Cloud Compose defaults are now
50 subscribers, 10 joins/second and 30 seconds, but this does not authorize
a Cloud run.

Both Cloud services now require the `manual-cloud-opt-in` Compose profile
and a non-empty `LIVEKIT_CLOUD_MANUAL_OPT_IN` value. The supported
`scripts/livekit-scale-test.sh start` and `test` commands fail closed;
only `stop` and `status` are exposed. The variable/profile are a
self-attested manual override, not proof of owner authorization. Direct
Compose can still be invoked deliberately with both; do not do so without
explicit owner authorization and LiveKit's written approval/approved
procedure. No Cloud test or spend occurred.

The local CI `room_matches` helper now prints only allowlisted room name,
participant count and publisher count. The previous full Room JSON included
an ephemeral `turnPassword` in a local test log; no production credential
exposure is established. The regression prevents full-object logging.
Do not use `docker compose down -v` or delete `storage/forge.db` as routine
cleanup; those commands can destroy local data. The root `start.sh` uses
non-destructive shutdown.
# Detailed view
docker compose ps -a

# Watch continuously
watch -n 2 "docker compose ps"
```

### View Logs

#### All services
```bash
# Latest 50 lines
docker compose logs --tail 50

# Follow live
docker compose logs -f
```

#### Specific service
```bash
# Backend logs
docker compose logs -f backend

# Legacy frontend logs (only after --profile legacy-frontend is enabled)
docker compose --profile legacy-frontend logs -f frontend

# Worker logs
docker compose logs -f worker

# Legacy Caddy logs (only after --profile legacy-frontend is enabled)
docker compose --profile legacy-frontend logs -f caddy
```

#### Last N lines
```bash
docker compose logs --tail 100 backend
```

#### Timestamp in logs
```bash
docker compose logs --timestamps -f backend
```

---

## Managing Services

### Restart Service
```bash
# Restart one service
docker compose restart backend

# Restart all services
docker compose restart
```

### Stop Service
```bash
docker compose stop backend
```

### Start Service
```bash
docker compose start backend
```

### Rebuild Images
```bash
# Rebuild all
docker compose build

# Rebuild one service
docker compose build backend

# Rebuild without cache
docker compose build --no-cache backend
```

---

## Container Shell Access

### Bash into Container
```bash
# Backend
docker exec -it forgeos-backend bash

# Legacy frontend (only when the legacy-frontend profile is running)
docker exec -it forgeos-frontend bash

# Worker
docker exec -it forgeos-worker bash
```

### Run Command in Container
```bash
# Python command
docker exec forgeos-backend python -c "from app.config import settings; print(settings.HAMI_MODEL_HOST)"

# List files
docker exec forgeos-backend ls -la /app/backend

# Check Python version
docker exec forgeos-backend python --version
```

---

## Database Access

### Query Database in Container
```bash
# Using Python/SQLAlchemy (fastest)
docker exec forgeos-backend python << 'EOF'
from app.database import SessionLocal
db = SessionLocal()
signals_count = db.query(__import__('app.models', fromlist=['Signal']).Signal).count()
print(f"Total signals: {signals_count}")
db.close()
EOF
```

### View Database File
```bash
# Check size
du -h storage/forge.db

# Check last modified
stat storage/forge.db

# Copy for backup
cp storage/forge.db storage/forge.db.backup
```

---

## Health Checks

### From Mac
```bash
# Backend health
curl http://localhost:8000/health

# Legacy frontend proxy (only with --profile legacy-frontend)
curl http://127.0.0.1:3000/api/health

# Optional legacy frontend (only with --profile legacy-frontend)
curl http://127.0.0.1:3000/ | head -c 100
```

### From Container
```bash
# Backend from inside
docker exec forgeos-backend curl http://localhost:8000/health

# Hami-model gateway connectivity (an "unauthorized" reply still
# proves the gateway answers; add -H "X-Hami-Key: $HAMI_CHAT_KEY"
# inside the container for the full status)
docker exec forgeos-backend curl http://host.docker.internal:11435/api/hami-llm/status | jq .

# Frontend from inside
docker exec forgeos-frontend curl http://forgeos-caddy:3000/ | head -c 100
```

---

## Debugging & Troubleshooting

### Inspect Container
```bash
docker inspect forgeos-backend

# Just IP address
docker inspect forgeos-backend | jq '.[0].NetworkSettings.IPAddress'
```

### Check Network
```bash
# List networks
docker network ls

# Inspect network
docker network inspect forgeos_default
```

### Check Resource Usage
```bash
# Live stats
docker stats --no-stream

# Specific container
docker stats forgeos-backend --no-stream
```

### View Events
```bash
# Watch docker events in real-time
docker events --filter 'container=forgeos-*'
```

---

## Image Management

### List Images
```bash
docker images | grep forgeos
```

### Remove Images
```bash
# Remove unused images
docker image prune

# Force remove image
docker rmi forgeos-backend
```

### Build Image Manually
```bash
cd backend
docker build -t forgeos-backend .
```

---

## Volume & Mount Management

### List Volumes
```bash
docker volume ls | grep forgeos
```

### Inspect Volume
```bash
docker volume inspect forgeos_default
```

### Check Mounts in Container
```bash
docker inspect forgeos-backend | jq '.[0].Mounts'
```

### Copy Files From Container
```bash
# Copy logs
docker cp forgeos-backend:/app/backend/app/main.py ./main.py.bak
```

---

## Network Troubleshooting

### Test Network Connectivity
```bash
# Backend to Hami-model gateway
docker exec forgeos-backend ping host.docker.internal

# Frontend to Backend
docker exec forgeos-frontend curl -s http://forgeos-backend:8000/health

# Check DNS
docker exec forgeos-backend nslookup host.docker.internal
```

### Check Open Ports
```bash
# On Mac
lsof -i :3000
lsof -i :8000

# List all container ports
docker compose port
```

---

## Development Workflow

### Hot Reload Testing
1. Edit `backend/app/main.py`
2. Watch logs: `docker compose logs -f backend`
3. Save file → backend auto-reloads (watch for "Reloading")
4. No rebuild needed!

### Rebuild on Changes
```bash
# Rebuild when requirements.txt changes
docker compose build backend
docker compose up backend

# Or with one command
docker compose up --build backend
```

### Check Frontend Changes
```bash
# Watch frontend logs (Next.js auto-compiles)
docker compose logs -f frontend

# Edit file in docs/archive/legacy-frontend/
# Save → check browser at http://localhost:3000
```

---

## Cleanup & Maintenance

### Remove All Stopped Containers
```bash
docker container prune
```

### Remove Unused Images
```bash
docker image prune
```

### Clean Everything
```bash
# WARNING: Removes ALL unused images, containers, networks, volumes
docker system prune -a --volumes
```

### Check Disk Usage
```bash
docker system df
```

---

## One-Liners

### Quick Status
```bash
docker compose ps --format="table {{.Service}}\t{{.Status}}"
```

### Show All Environment Variables in Backend
```bash
docker exec forgeos-backend env | sort
```

### Restart Everything After Code Change
```bash
docker compose restart backend && sleep 2 && curl http://localhost:3000/api/health
```

### Watch Worker Activity
```bash
watch -n 5 "docker compose logs --tail 20 worker"
```

### Count All Records by Type
```bash
for table in signals opportunities beliefs decisions executions; do
  count=$(docker exec forgeos-backend python -c "from app.database import SessionLocal; from app import models; db = SessionLocal(); print(getattr(db.query(getattr(models, [x for x in dir(models) if x.lower() == '$table'][0])), 'count', lambda: 0)())" 2>/dev/null || echo "?")
  echo "$table: $count"
done
```

---

## Emergency Commands

### Kill All ForgeOS Containers
```bash
docker compose kill
```

### Force Remove Containers
```bash
docker compose rm -f
```

### Reset Everything (WARNING: Deletes data!)
```bash
docker compose down -v
rm -rf storage/forge.db
docker compose build
docker compose up
```

---

## Performance Tips

- Use `-d` flag to run in background: `docker compose up -d`
- Use `-f` flag to follow logs without blocking: `docker compose logs -f`
- Use `--no-build` to skip building: `docker compose up --no-build`
- Monitor with `watch`: `watch docker compose ps`

---

## Quick Links

- **Canonical Hami:** http://localhost:8080
- **Optional legacy dashboard:** http://127.0.0.1:3000 (profile only)
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **API Proxy:** http://localhost:3000/api

---

**Need help?** Run `docker compose --help` or check `docker --help`
