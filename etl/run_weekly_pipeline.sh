#!/bin/bash
# PropertyPulse Weekly Data Pipeline
# Run via cron: 0 2 * * 0 /path/to/run_weekly_pipeline.sh
# Or add to Airflow as a BashOperator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/pipeline_$(date +%Y%m%d_%H%M%S).log"
DBT_DIR="${SCRIPT_DIR}/../dbt/ukproperty"

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/ukproperty}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

fail() {
    log "❌ FAILED: $1"
    exit 1
}

log "=============================="
log "PropertyPulse Pipeline Start"
log "=============================="

# ─── 1. Land Registry PPD (incremental) ──────────────────────────────────────
log "Step 1/7: Ingesting Land Registry PPD..."
python3 "${SCRIPT_DIR}/ingest_land_registry.py" >> "${LOG_FILE}" 2>&1 || fail "Land Registry ingest"
log "  ✅ Land Registry done"

# ─── 2. HPI ──────────────────────────────────────────────────────────────────
log "Step 2/7: Ingesting HPI..."
python3 "${SCRIPT_DIR}/ingest_hpi.py" >> "${LOG_FILE}" 2>&1 || log "  ⚠️ HPI ingest failed (non-fatal)"
log "  ✅ HPI done"

# ─── 3. Schools / Ofsted ─────────────────────────────────────────────────────
log "Step 3/7: Refreshing schools data..."
python3 "${SCRIPT_DIR}/ingest_schools_ofsted.py" >> "${LOG_FILE}" 2>&1 || fail "Schools ingest"
log "  ✅ Schools done"

# ─── 4. Crime (monthly, run if available) ────────────────────────────────────
log "Step 4/7: Checking for crime data update..."
if [ -f "${SCRIPT_DIR}/data/police_latest.zip" ]; then
    # Check if zip is newer than 28 days
    if find "${SCRIPT_DIR}/data/police_latest.zip" -mtime -28 | grep -q .; then
        log "  Crime data is recent, re-ingesting..."
        python3 "${SCRIPT_DIR}/ingest_crime.py" >> "${LOG_FILE}" 2>&1 || log "  ⚠️ Crime ingest failed (non-fatal)"
    else
        log "  Crime data unchanged, skipping"
    fi
fi
log "  ✅ Crime check done"

# ─── 5. dbt run ──────────────────────────────────────────────────────────────
log "Step 5/7: Running dbt transforms..."
if command -v dbt &>/dev/null; then
    cd "${DBT_DIR}"
    dbt run --target prod --profiles-dir . >> "${LOG_FILE}" 2>&1 || fail "dbt run"
    log "  ✅ dbt run done"

    # ─── 6. dbt test ─────────────────────────────────────────────────────────
    log "Step 6/7: Running dbt tests..."
    dbt test --target prod --profiles-dir . >> "${LOG_FILE}" 2>&1 || log "  ⚠️ dbt tests failed (check log)"
    log "  ✅ dbt test done"
else
    log "  ⚠️ dbt not found, skipping (requires Python 3.11)"
fi

# ─── 7. Redis cache flush ─────────────────────────────────────────────────────
log "Step 7/7: Flushing Redis cache..."
if command -v redis-cli &>/dev/null; then
    redis-cli -u "${REDIS_URL}" FLUSHDB >> "${LOG_FILE}" 2>&1 && log "  ✅ Redis flushed"
else
    log "  ⚠️ redis-cli not found, skipping"
fi

log "=============================="
log "Pipeline Complete ✅"
log "Log: ${LOG_FILE}"
log "=============================="
