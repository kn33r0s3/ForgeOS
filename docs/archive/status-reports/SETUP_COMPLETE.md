# 🚀 ForgeOS — Initial Setup Complete

**Status:** ✅ LIVE AND OPERATIONAL  
**Date:** September 11, 2026  
**Location:** `/Users/nirojpaudyal/Downloads/ForgeOS`

---

## 🌐 Access Your ForgeOS System

### Dashboard & UI
**👉 http://localhost:3000**
- Full ForgeOS interface with opportunities, execution, revenue tracking
- Real-time signal processing
- AI-powered analysis

### Backend API
**Direct access:** http://localhost:8000  
**Via proxy:** http://localhost:3000/api  
**API Documentation:** http://localhost:8000/docs

---

## 📡 Key API Endpoints

### Health & Status
```bash
# Check backend health
curl http://localhost:3000/api/health

# Check AI provider status
curl http://localhost:3000/api/ai/status
```

### Signals (Raw Observations)
```bash
# Get all signals
curl http://localhost:3000/api/signals | jq .

# Get first 10 with details
curl http://localhost:3000/api/signals | jq '.[0:10]'
```

### Opportunities
```bash
# Get discovered opportunities
curl http://localhost:3000/api/opportunities | jq .

# Filter by confidence
curl http://localhost:3000/api/opportunities | jq '.[] | select(.confidence_score > 75)'
```

### Background Worker
```bash
# Get active worker tasks
curl http://localhost:3000/api/workers | jq .

# Watch for new worker tasks
watch -n 5 "curl -s http://localhost:3000/api/workers | jq length"
```

### Intelligence Cycles
```bash
# Get execution outcomes
curl http://localhost:3000/api/executions | jq .
```

---

## 🐳 Docker Stack

### Services Running
| Service | Role | Status | Port |
|---------|------|--------|------|
| **backend** | FastAPI/Uvicorn | Healthy ✅ | 8000 |
| **frontend** | Next.js Dashboard | Running ✅ | 3000 (via Caddy) |
| **worker** | Background Tasks | Running ✅ | Background |
| **caddy** | Reverse Proxy | Running ✅ | 3000 |

### Container Commands
```bash
# View all containers
docker compose ps

# View live logs
docker compose logs -f backend    # Backend only
docker compose logs -f frontend   # Frontend only
docker compose logs -f worker     # Worker only
docker compose logs -f            # All services

# Stop all services
docker compose down

# Restart a service
docker compose restart backend

# View container shell
docker exec -it forgeos-backend bash
docker exec -it forgeos-frontend bash
```

---

## 💾 Database

### SQLite Database
**Path:** `/Users/nirojpaudyal/Downloads/ForgeOS/storage/forge.db`  
**Size:** 32 MB (with historical data)  
**Backend:** FastAPI/SQLAlchemy (Python)  
**Persistence:** Bind mount in docker-compose.yml

### Query Database Directly
```bash
# From Mac (native)
sqlite3 /Users/nirojpaudyal/Downloads/ForgeOS/storage/forge.db

# Interactive SQL
sqlite3 storage/forge.db
> SELECT COUNT(*) FROM signals;
> SELECT COUNT(*) FROM opportunities;
> SELECT * FROM signals LIMIT 5;

# One-off query
sqlite3 storage/forge.db "SELECT COUNT(*) FROM signals;"
```

### Key Tables
- **signals** — Raw observations from collectors
- **opportunities** — Detected business opportunities
- **beliefs** — Hypotheses about the world
- **decisions** — Recommended actions
- **executions** — Outcomes of actions taken
- **experiments** — Tests to validate beliefs
- **workers** — Background task queue

---

## 🧠 AI & Ollama

### Current Configuration
- **Provider:** Ollama (local, on your Mac)
- **Model:** `qwen3-coder:latest`
- **Host:** `http://host.docker.internal:11434`
- **Cost:** $0 (runs locally, no API keys)

### Verify Ollama
```bash
# From container
docker exec forgeos-backend curl http://host.docker.internal:11434/api/tags | jq .

# List available models
docker exec forgeos-backend curl http://host.docker.internal:11434/api/tags | jq '.models[] | .name'

# Test a completion
curl -s http://host.docker.internal:11434/api/generate -d '{
  "model": "qwen3-coder:latest",
  "prompt": "What is ForgeOS?",
  "stream": false
}' | jq .response
```

### Switch Models
Edit `backend/.env`:
```bash
OLLAMA_MODEL=qwen2.5-coder:3b
QWEN_MODEL_NAME=qwen2.5-coder:3b
```
Restart backend: `docker compose restart backend`

---

## 🔧 Configuration Files

### Backend Environment
**File:** `backend/.env`
```
AI_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434          # Overridden by docker-compose.yml
OLLAMA_MODEL=qwen3-coder:latest
EMBEDDING_PROVIDER=hash
DATABASE_URL=sqlite:///../storage/forge.db
```

### Frontend Environment
**File:** `frontend/.env.local`
```
NEXT_PUBLIC_API_URL=/api
```

### Docker Compose Overrides
**File:** `docker-compose.yml` (environment section)
```yaml
environment:
  - DATABASE_URL=sqlite:////app/storage/forge.db
  - OLLAMA_HOST=http://host.docker.internal:11434
  - OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
```

---

## 🎯 Common Tasks

### View Real-Time Backend Logs
```bash
docker compose logs -f backend
```

### Test Frontend Communication
```bash
# Load test page
open http://localhost:3000

# Check API proxy
curl http://localhost:3000/api/signals | head -c 200
```

### Reset Database (Wipe All Data)
```bash
# WARNING: This deletes everything
rm storage/forge.db

# Recreate empty database
docker compose restart backend
```

### Run Backend Tests
```bash
cd backend
python -m pytest tests/ -v

# Or in container
docker exec forgeos-backend python -m pytest tests/ -v
```

### Edit Code and See Changes Immediately
1. Edit `backend/app/main.py` (or any backend file)
2. Backend will auto-reload (uvicorn --reload)
3. No need to rebuild Docker image

Same for frontend (Next.js dev server watches for changes)

---

## 📊 System Status Check

Run this command anytime to verify everything is working:
```bash
/tmp/forgeos_live_status.sh
```

Or check manually:
```bash
# All containers running?
docker compose ps

# Backend healthy?
curl http://localhost:8000/health

# Frontend loads?
curl http://localhost:3000/ | head -c 100

# Ollama reachable?
docker exec forgeos-backend curl http://host.docker.internal:11434/api/tags | jq .
```

---

## 🚨 Troubleshooting

### Backend won't start
```bash
# Check logs
docker compose logs backend | tail -50

# Restart
docker compose restart backend
```

### Frontend shows "Reading Forge memory..."
- Backend API might be slow — give it 10 seconds
- Check: `curl http://localhost:3000/api/signals`

### Ollama not reachable
- Ensure Ollama is running on Mac: `ollama serve`
- Check model: `ollama ls`
- From container: `docker exec forgeos-backend curl http://host.docker.internal:11434/api/tags`

### Database errors
- Check permissions: `ls -l storage/forge.db`
- Check Docker mount: `docker exec forgeos-backend ls -l /app/storage/`

### Port 3000 already in use
```bash
# Find what's using it
lsof -i :3000

# Or use different port in docker-compose.yml
# ports: ["3001:3000"]  # Then access http://localhost:3001
```

---

## 📚 What's Inside

### Frontend (`frontend/`)
- Next.js 14 (React 18)
- Tailwind CSS styling
- Real-time API client
- Pages: Dashboard, Opportunities, Execution, Revenue, World, Knowledge

### Backend (`backend/`)
- FastAPI (Python)
- SQLAlchemy ORM with SQLite
- Modular services:
  - `observer_engine` — Signal collection
  - `pattern_engine` — Pattern detection
  - `belief_engine` — Hypothesis formation
  - `decision_engine` — Action planning
  - `execution_engine` — Outcome tracking
  - `learning_engine` — Belief updates
- AI integration (Ollama, OpenAI optional)

### Worker (`backend/worker.py`)
- Autonomous background processor
- Runs every 1800 seconds (30 min)
- Default collectors: GitHub, RSS, Reddit, Arx Χiv
- Processes discoveries into opportunities
- Tracks outcomes and learns

---

## ✅ Verification Checklist

- [x] All containers running
- [x] Backend healthy (`/health` returns 200)
- [x] Frontend loads (HTTP 200)
- [x] API proxy working (`/api/health` works)
- [x] Database exists and writable
- [x] Ollama reachable from container
- [x] Worker processing tasks
- [x] Hot-reload working (edit = instant reload, no rebuild)
- [x] All data persisted across restarts

---

## 🎓 Next Steps

1. **Explore the Dashboard** — http://localhost:3000
2. **Check API Docs** — http://localhost:8000/docs
3. **Monitor Worker** — `docker compose logs -f worker`
4. **Make Code Changes** — Edit and save, auto-reloads
5. **Query Database** — `sqlite3 storage/forge.db`
6. **Read README.md** — Philosophy and architecture

---

## 📞 Quick Reference

| Command | Purpose |
|---------|---------|
| `docker compose up` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose logs -f` | View live logs |
| `docker compose ps` | Check status |
| `docker compose restart backend` | Restart one service |
| `curl http://localhost:3000/api/health` | Health check |
| `sqlite3 storage/forge.db` | Access database |

---

**🎉 You're all set! ForgeOS is live and ready to observe, analyze, and execute.**

**Questions?** Check the README.md in the main directory.

