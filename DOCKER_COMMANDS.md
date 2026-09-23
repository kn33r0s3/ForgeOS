# 🐳 ForgeOS Docker Commands Cheat Sheet

**Location:** `/Users/nirojpaudyal/Downloads/ForgeOS`

---

## Starting & Stopping

### Start All Services (Background)
```bash
cd /Users/nirojpaudyal/Downloads/ForgeOS
docker compose up -d
```

### Start All Services (View Logs)
```bash
docker compose up
# Press Ctrl+C to stop and keep containers running
# Or Ctrl+C twice to stop and remove containers
```

### Start All Services (Rebuild Images)
```bash
docker compose up --build
```

### Stop All Services
```bash
docker compose down
```

### Stop All Services & Remove Volumes
```bash
docker compose down -v
```

---

## Viewing Status

### Check Container Status
```bash
# Quick view
docker compose ps

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

# Frontend logs
docker compose logs -f frontend

# Worker logs
docker compose logs -f worker

# Caddy logs
docker compose logs -f caddy
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

# Frontend
docker exec -it forgeos-frontend bash

# Worker
docker exec -it forgeos-worker bash
```

### Run Command in Container
```bash
# Python command
docker exec forgeos-backend python -c "from app.config import settings; print(settings.OLLAMA_HOST)"

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

# Backend via proxy
curl http://localhost:3000/api/health

# Frontend
curl http://localhost:3000/ | head -c 100
```

### From Container
```bash
# Backend from inside
docker exec forgeos-backend curl http://localhost:8000/health

# Ollama connectivity
docker exec forgeos-backend curl http://host.docker.internal:11434/api/tags | jq .

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
# Backend to Ollama
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

# Edit file in frontend/
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

- **Dashboard:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **API Proxy:** http://localhost:3000/api

---

**Need help?** Run `docker compose --help` or check `docker --help`

