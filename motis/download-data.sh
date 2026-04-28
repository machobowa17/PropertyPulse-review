#!/bin/bash
# Download GB transit data for MOTIS
# Run this on the Hetzner server before first import

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"

mkdir -p "$DATA_DIR"

echo "=== Downloading GB GTFS (all modes: rail, bus, metro, tram, ferry) ==="
echo "Source: aubin.app combined feed (~1 GB)"
curl -L -o "$DATA_DIR/great_britain_gtfs.zip" \
  "https://beta.aubin.app/gtfs/great_britain_gtfs.zip"
echo "Done: $(ls -lh "$DATA_DIR/great_britain_gtfs.zip" | awk '{print $5}')"

echo ""
echo "=== Downloading GB OSM PBF (~2.1 GB) ==="
echo "Source: Geofabrik"
curl -L -o "$DATA_DIR/great-britain-latest.osm.pbf" \
  "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf"
echo "Done: $(ls -lh "$DATA_DIR/great-britain-latest.osm.pbf" | awk '{print $5}')"

echo ""
echo "=== Downloads complete ==="
ls -lh "$DATA_DIR/"
echo ""
echo "Next: docker compose --profile import up motis-import"
