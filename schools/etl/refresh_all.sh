#!/bin/bash
# School data refresh — runs all ETL scripts in order.
#
# Data update frequencies:
# - GIAS (school register):     Live feed, refresh monthly
# - Ofsted inspections:         Monthly MI release
# - Parent View:                Quarterly
# - KS2/KS4/KS5 results:       Annual (check for new dataset IDs)
# - Destinations:               Annual
# - Demographics:               Annual
# - Workforce:                  Annual
# - Finances:                   Annual
# - Admissions:                 Annual
# - Subjects:                   Annual
# - Nurseries (Ofsted):         Monthly
# - SEN:                        Extracted from GIAS
# - Absence:                    Annual
# - Catchment model:            Recompute after admissions update
#
# Usage: run inside the school_api container:
#   docker exec school_api python /app/etl/ingest_gias.py
#
# Or via this script on the host:
#   /opt/schools/etl/refresh_all.sh
#
# Cron: 1st of each month at 04:00 UTC for monthly sources
#   0 4 1 * * /opt/schools/etl/refresh_all.sh >> /var/log/school_refresh.log 2>&1

set -euo pipefail
CONTAINER="school_api"
LOG_PREFIX="[school-refresh]"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $LOG_PREFIX $*"; }

run_etl() {
    local script="$1"
    log "Starting $script..."
    if docker exec "$CONTAINER" python "/app/etl/$script" 2>&1; then
        log "$script completed successfully"
    else
        log "WARNING: $script failed (exit $?), continuing..."
    fi
}

log "=== School data refresh started ==="

# 1. Core register (must run first — other tables FK to institutions)
run_etl ingest_gias.py

# 2. Ofsted inspections (monthly)
run_etl ingest_ofsted.py

# 3. Nurseries (monthly from Ofsted)
run_etl ingest_nurseries.py

# 4. Parent View (quarterly)
run_etl ingest_parent_view.py

# 5. SEN provisions (from GIAS)
run_etl ingest_sen.py

# 6. Absence rates
run_etl ingest_absence.py

# 7. Demographics
run_etl ingest_demographics.py

# 8. Workforce
run_etl ingest_workforce.py

# 9. Finances
run_etl ingest_finances.py

# 10. Admissions
run_etl ingest_admissions.py

# 11. KS2 results
run_etl ingest_ks2.py

# 12. KS4 results
run_etl ingest_ks4.py

# 13. KS5 results
run_etl ingest_ks5.py

# 14. Destinations
run_etl ingest_destinations.py

# 15. Subjects
run_etl ingest_subjects.py

# 16. Recompute catchment model (depends on admissions + GIAS)
run_etl compute_catchment.py

log "=== School data refresh complete ==="
