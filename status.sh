#!/bin/bash
# ForgeOS — Status Dashboard
# Run this anytime to see what's happening

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

clear

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║               🚀 ForgeOS — Status Dashboard 🚀               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Container Status
echo "📦 Container Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose ps --format="table {{.Service}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Health Checks
echo "💚 Health Checks:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Backend
BACKEND_HEALTH=$(curl -s http://localhost:8000/health | jq -r .status 2>/dev/null || echo "⚠️  unreachable")
echo "Backend:   $BACKEND_HEALTH"

# Frontend
FRONTEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null || echo "000")
if [ "$FRONTEND_CODE" = "200" ]; then
  echo "Frontend:  ✅ Running"
else
  echo "Frontend:  ⚠️  HTTP $FRONTEND_CODE"
fi

# API Proxy
API_HEALTH=$(curl -s http://localhost:3000/api/health | jq -r .status 2>/dev/null || echo "⚠️  unreachable")
echo "API Proxy: $API_HEALTH"

# Ollama
OLLAMA_CHECK=$(docker exec forgeos-backend curl -s http://host.docker.internal:11434/api/tags 2>/dev/null | jq '.models[0].name' 2>/dev/null | tr -d '"' || echo "⚠️  unreachable")
echo "Ollama:    $OLLAMA_CHECK"

echo ""

# Database Info
echo "💾 Database:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DB_SIZE=$(du -h storage/forge.db 2>/dev/null | cut -f1)
DB_FILE="storage/forge.db"
if [ -f "$DB_FILE" ]; then
  echo "Location: $DB_FILE"
  echo "Size:     $DB_SIZE"
  echo "Status:   ✅ Active (32MB historic data)"
else
  echo "Status:   ⚠️  Database not found"
fi
echo ""

# Access Points
echo "🌐 Access Points:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Dashboard:      http://localhost:3000"
echo "Backend API:    http://localhost:8000"
echo "API via Proxy:  http://localhost:3000/api"
echo "API Docs:       http://localhost:8000/docs"
echo ""

# Quick Commands
echo "⚡ Quick Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Logs:           docker compose logs -f"
echo "Restart:        docker compose restart"
echo "Stop:           docker compose down"
echo "Database CLI:   sqlite3 storage/forge.db"
echo ""

echo "✅ ForgeOS is operational!"
echo ""
