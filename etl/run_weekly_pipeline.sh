#!/bin/bash
# PropertyPulse Monthly Data Pipeline
# Run after each monthly Land Registry / HPI / crime / EPC release.
# Cron: 0 2 1 * * /path/to/etl/run_weekly_pipeline.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/pipeline_$(date +%Y%m%d_%H%M%S).log"

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/ukproperty}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "=============================="
log "PropertyPulse Monthly Pipeline"
log "=============================="

cd "${SCRIPT_DIR}"
python3 pipeline.py --schedule monthly 2>&1 | tee -a "${LOG_FILE}"

log "=============================="
log "Pipeline Complete"
log "Log: ${LOG_FILE}"
log "=============================="
