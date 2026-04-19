#!/usr/bin/env bash
# PropertyPulse — Deploy update (run after git pull)
#
# Usage:
#   cd /opt/propertypulse && git pull && ./deploy/update.sh

set -euo pipefail

APP_DIR="/opt/propertypulse"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

cd "$APP_DIR"

echo "=== PropertyPulse — Deploying update ==="
echo ""

# Rebuild images (--no-cache for frontend to avoid stale JS bundles)
echo "[1/3] Building updated images..."
$COMPOSE build --no-cache frontend
$COMPOSE build api

# Rolling restart (db + redis stay up, api + frontend restart)
echo "[2/3] Restarting services..."
$COMPOSE up -d --no-deps api frontend

# Verify
echo "[3/3] Verifying..."
sleep 5
$COMPOSE ps
echo ""
echo "Health checks:"
$COMPOSE exec db pg_isready -U ukproperty && echo "  PostgreSQL: OK" || echo "  PostgreSQL: FAIL"
$COMPOSE exec redis redis-cli ping | grep -q PONG && echo "  Redis: OK" || echo "  Redis: FAIL"
curl -sf http://localhost:8000/api/docs > /dev/null && echo "  API: OK" || echo "  API: waiting..."
curl -sf http://localhost/nginx-health > /dev/null && echo "  Nginx: OK" || echo "  Nginx: waiting..."

echo ""
echo "=== Update deployed ==="
