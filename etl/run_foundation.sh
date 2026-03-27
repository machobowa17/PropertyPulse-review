#!/bin/bash
# Run the Phase 0 Foundation ETL pipeline in order
# Prerequisites: Docker containers running (docker compose up -d)

set -e

cd "$(dirname "$0")"

echo "========================================="
echo "Phase 0: Foundation Data Ingestion"
echo "========================================="

echo ""
echo "[1/5] Ingesting ONSPD → core_postcodes..."
python3 ingest_postcodes.py

echo ""
echo "[2/5] Ingesting Boundaries → core_lsoa/ward/lad_boundaries..."
python3 ingest_boundaries.py

echo ""
echo "[3/5] Ingesting OS Open Names → core_place_names..."
python3 ingest_place_names.py

echo ""
echo "[4/5] Building LAD-to-county lookup..."
python3 ingest_lad_county_lookup.py

echo ""
echo "[5/5] Ingesting Land Registry Price Paid → core_property_prices..."
python3 ingest_land_registry.py

echo ""
echo "========================================="
echo "Foundation ingestion complete!"
echo "========================================="
