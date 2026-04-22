#!/bin/bash
# Monthly MOTIS data refresh (1st of month, 3 AM UTC)
# Crontab: 0 3 1 * * /opt/motis/update-data.sh >> /var/log/motis-update.log 2>&1
#
# Downloads fresh GB GTFS, re-imports, restarts server.
# OSM refreshed quarterly (Jan, Apr, Jul, Oct).
# Logs to /var/log/motis-update.log with rotation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
cd "$SCRIPT_DIR"

MONTH=$(date +%m)
LOG_PREFIX="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[$LOG_PREFIX] === Starting monthly MOTIS data update ==="

# ── Download fresh GTFS ──────────────────────────────────────────────────
echo "[$LOG_PREFIX] Downloading fresh GB GTFS..."
if curl -L -f -o "$DATA_DIR/great_britain_gtfs.zip.new" \
  "https://beta.aubin.app/gtfs/great_britain_gtfs.zip"; then
  mv "$DATA_DIR/great_britain_gtfs.zip.new" "$DATA_DIR/great_britain_gtfs.zip"
  echo "[$LOG_PREFIX] GTFS downloaded OK ($(du -h "$DATA_DIR/great_britain_gtfs.zip" | cut -f1))"
else
  echo "[$LOG_PREFIX] ERROR: GTFS download failed. Aborting."
  exit 1
fi

# ── Download fresh OSM quarterly (Jan, Apr, Jul, Oct) ────────────────────
if [[ "$MONTH" == "01" || "$MONTH" == "04" || "$MONTH" == "07" || "$MONTH" == "10" ]]; then
  echo "[$LOG_PREFIX] Quarterly OSM refresh..."
  if curl -L -f -o "$DATA_DIR/great-britain-latest.osm.pbf.new" \
    "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf"; then
    mv "$DATA_DIR/great-britain-latest.osm.pbf.new" "$DATA_DIR/great-britain-latest.osm.pbf"
    echo "[$LOG_PREFIX] OSM downloaded OK ($(du -h "$DATA_DIR/great-britain-latest.osm.pbf" | cut -f1))"
  else
    echo "[$LOG_PREFIX] WARNING: OSM download failed. Continuing with existing data."
  fi
fi

# ── Stop server, re-import, restart ──────────────────────────────────────
echo "[$LOG_PREFIX] Stopping MOTIS server..."
docker compose stop motis

# Remove old import data to force full re-import
docker volume rm motis_motis-data 2>/dev/null || true

echo "[$LOG_PREFIX] Running import (this takes 20-40 min)..."
if docker compose --profile import run --rm motis-import; then
  echo "[$LOG_PREFIX] Import completed OK"
else
  echo "[$LOG_PREFIX] ERROR: Import failed. Attempting to restart with old data..."
  docker compose up -d motis
  exit 1
fi

echo "[$LOG_PREFIX] Starting MOTIS server..."
docker compose up -d motis

# ── Health check with retry ──────────────────────────────────────────────
echo "[$LOG_PREFIX] Waiting for server to start..."
HEALTHY=false
for i in 1 2 3 4 5; do
  sleep 15
  if curl -sf "http://localhost:8080/api/v1/plan?fromPlace=51.5074,-0.1278&toPlace=51.5013,-0.0886&time=$(date -u +%Y-%m-%dT08:00:00Z)&numItineraries=1&mode=TRANSIT,WALK" > /dev/null; then
    HEALTHY=true
    break
  fi
  echo "[$LOG_PREFIX] Health check attempt $i failed, retrying..."
done

if $HEALTHY; then
  echo "[$LOG_PREFIX] Health check: OK"
  echo "[$LOG_PREFIX] === Monthly update completed successfully ==="
else
  echo "[$LOG_PREFIX] ERROR: Server failed health check after 5 attempts!"
  echo "[$LOG_PREFIX] === Monthly update FAILED ==="
  exit 1
fi
