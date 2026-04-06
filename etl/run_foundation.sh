#!/bin/bash
# PropertyPulse Foundation Data Pipeline
# Run once at initial setup; re-run when ONS publishes new postcode or boundary data.
# See etl/PIPELINE.md for prerequisites.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/foundation_$(date +%Y%m%d_%H%M%S).log"

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/ukproperty}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "=============================="
log "PropertyPulse Foundation Pipeline"
log "=============================="

cd "${SCRIPT_DIR}"
python3 pipeline.py --schedule foundation 2>&1 | tee -a "${LOG_FILE}"

log "=============================="
log "Foundation Pipeline Complete"
log "Log: ${LOG_FILE}"
log "=============================="
