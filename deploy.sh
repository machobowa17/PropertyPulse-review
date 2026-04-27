#!/bin/bash
set -euo pipefail

cd /opt/propertypulse

echo "=== Pulling latest from GitHub ==="
git pull origin main

echo ""
echo "=== Building frontend ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache frontend

echo ""
echo "=== Restarting services ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo ""
echo "=== Pruning build cache ==="
docker builder prune -f --filter 'until=24h' 2>/dev/null || true

echo ""
echo "=== Deploy complete ==="
git log --oneline -1
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -10
