# ETL Pipeline

## Architecture

All authoritative data for PropertyPulse lives in PostgreSQL `core_*` tables.
No API endpoint queries source files, CSV, or external APIs directly.

```
Source data files
       │
       ▼
etl/sources/*.py     — 29 source modules (raw data → core_* tables)
etl/derived/*.py     — 4 derived modules (core_* × core_* → new core_* tables)
       │
       ▼
core_* PostgreSQL tables
       │
       ▼
FastAPI backend (query only via session_key → JOIN keys)
       │
       ▼
React frontend
```

The pipeline orchestrator is `etl/pipeline.py`.
It handles dependency ordering, run tracking, Redis cache invalidation, and row-count validation.

---

## Running the Pipeline

### First-time setup
```bash
cd etl
python3 pipeline.py --schedule foundation   # Runs 5 foundation sources in order
```

### Monthly update (Land Registry, HPI, crime, EPC, transactions)
```bash
cd etl
python3 pipeline.py --schedule monthly
```

### Quarterly update (EPC-LSOA, OSM, EV chargers, governance, mobile)
```bash
cd etl
python3 pipeline.py --schedule quarterly
```

### Annual update (price/sqm, rents, earnings, broadband, AQ, NHS, etc.)
```bash
cd etl
python3 pipeline.py --schedule annual
```

### One-time ingestion (Census, IMD)
```bash
cd etl
python3 pipeline.py --schedule one_time
```

### Run all sources in topological order
```bash
cd etl
python3 pipeline.py --all
```

### Run a single source
```bash
cd etl
python3 pipeline.py --source land_registry
```

### Dry run (shows execution order without running anything)
```bash
cd etl
python3 pipeline.py --dry-run --all
```

### List all sources
```bash
cd etl
python3 pipeline.py --list
```

### Check run status
```bash
cd etl
python3 pipeline.py --status
```

---

## Execution Order (Topological Sort)

```
 1. postcodes                 [foundation]  — no deps
 2. boundaries                [foundation]  — postcodes
 3. lad_county_lookup         [foundation]  — postcodes
 4. place_names               [foundation]  — postcodes
 5. place_boundaries          [foundation]  — boundaries
 6. land_registry_full        [monthly]     — postcodes
 7. hpi                       [monthly]     — boundaries
 8. crime                     [monthly]     — boundaries
 9. schools                   [monthly]     — postcodes
10. epc_domestic              [monthly]     — none
11. epc_lsoa                  [quarterly]   — none
12. osm_amenities             [quarterly]   — none
13. ev_chargers               [quarterly]   — none
14. governance                [quarterly]   — boundaries
15. mobile_coverage           [quarterly]   — none
16. voa_rents                 [annual]      — none
17. ashe                      [annual]      — none
18. broadband                 [annual]      — none
19. air_quality               [annual]      — boundaries
20. flood                     [annual]      — none
21. green_space               [annual]      — none
22. nhs                       [annual]      — postcodes
23. naptan                    [annual]      — none
24. council_tax               [annual]      — none
25. water                     [annual]      — boundaries
26. cycling_ptal              [annual]      — none
27. census                    [one_time]    — none
28. imd                       [one_time]    — none
29. place_lsoa_mapping        [annual]      — place_names, boundaries
30. nhs_lsoa                  [annual]      — nhs, boundaries
31. price_by_bedrooms         [monthly]     — land_registry_full
```

> **Cleanup note (session 9):** `transactions_epc`, `price_sqm`, and `land_registry` (old incremental)
> modules were moved to `etl/legacy/` — their target tables were dropped in Phase 13 Steps 2–3.
> `land_registry_full` is now the canonical Land Registry ingest module. `price_by_bedrooms`
> was rewritten to query the master table directly (EPC columns absorbed in Step 2).

---

## Schedule Definitions

| Schedule | Constant | Typical Run |
|----------|----------|-------------|
| `foundation` | `SCHEDULE_FOUNDATION` | Once at setup; re-run when ONS publishes new postcode/boundary data |
| `monthly` | `SCHEDULE_MONTHLY` | After each monthly Land Registry / HPI / crime release |
| `quarterly` | `SCHEDULE_QUARTERLY` | After each quarterly EPC / EV charger update |
| `annual` | `SCHEDULE_ANNUAL` | Annually after Ofcom / NHS / census-derived data releases |
| `one_time` | `SCHEDULE_ONE_TIME` | Run once; data does not change (Census 2021, IMD 2025) |

---

## Module Interface

Every source module in `etl/sources/` and derived module in `etl/derived/` must implement:

```python
METADATA = {
    "name":               str,          # unique key, matches SOURCE_REGISTRY
    "description":        str,          # human-readable one-liner
    "schedule":           str,          # one of SCHEDULE_* constants
    "depends_on":         list[str],    # other source names that must run first
    "tables_written":     list[str],    # core_* table names written/truncated
    "cache_key_patterns": list[str],    # Redis key patterns to invalidate on success
    "expected_row_range": (int, int),   # (min, max) for validation
}

def run(db_url: str) -> int:
    """Ingest data into core_* tables. Returns final row count."""
    ...
```

The pipeline runner (`run_source` in pipeline.py):
1. Records start in `core_pipeline_runs` (status = 'running')
2. Calls `module.run(db_url)` → gets `rows_after`
3. Validates `rows_after` is in `expected_row_range`
4. Invalidates Redis key patterns using `SCAN` + `DEL` (never `FLUSHDB`)
5. Updates `core_pipeline_runs` with status ('success', 'failed', or 'validation_failed'), `rows_after`, `finished_at`

---

## Adding a New Source Module

1. Create `etl/sources/<name>.py` implementing the module interface above.
2. Add to `SOURCE_REGISTRY` in `etl/pipeline.py`:
   ```python
   "my_source": {
       "module": "sources.my_source",
       "schedule": SCHEDULE_MONTHLY,
       "depends_on": ["postcodes"],
       "description": "...",
       "tables_written": [TABLE_NAMES["my_table"]],
       "cache_key_patterns": [],
       "expected_row_range": (1_000, 100_000),
   }
   ```
3. Add `"my_table": "core_my_table"` to `TABLE_NAMES` in `etl/constants.py`.
4. Create a schema migration in `etl/migrations/NNN_my_table.sql` and run `python3 migrate.py`.
5. If the new table needs to be queried by the API, update the relevant tab service file and `SESSION_CONTRACT.md`.

---

## Adding a New Derived Module

Same as a source module, but:
- Place the file in `etl/derived/` instead of `etl/sources/`
- Set `"depends_on"` to the source modules whose tables this derives from
- Derived modules never download files — they only query existing `core_*` tables

---

## Schema Migrations

Schema changes are managed via numbered SQL files in `etl/migrations/`:
```
etl/migrations/
  001_pipeline_runs.sql
  002_schema_migrations.sql
  ...
```

Run all pending migrations:
```bash
cd etl
python3 migrate.py
```

`migrate.py` is idempotent: each migration is recorded in `schema_migrations` and will not run twice.

---

## Run Tracking

Pipeline runs are recorded in `core_pipeline_runs`:
```sql
SELECT source_name, status, rows_after, finished_at
FROM core_pipeline_runs
ORDER BY finished_at DESC;
```

Or via the CLI:
```bash
python3 pipeline.py --status
```

The API exposes this at `GET /api/v1/data-freshness`.

---

## Redis Cache Invalidation

After a successful run, the pipeline invalidates Redis keys matching each pattern in
`cache_key_patterns`. Patterns use `*` glob syntax (Redis `SCAN` + `DEL`).

Common patterns:
- `area:*` — all tab data caches
- `pois:*` — map POI caches (used by `transactions_epc`)
- `price_history:*` — price history caches

The pipeline never calls `FLUSHDB`. Only declared key patterns are invalidated.

---

## Session Key Contract

See `backend/SESSION_CONTRACT.md` for the full contract between the ETL tables
and the API session fields (lsoa_codes, lad_code, ward_code, etc.).

---

## Rules

1. **Always use `TABLE_NAMES["key"]`** from `constants.py` — never hardcode table names.
2. **Always use `SCHEDULE_*` constants** — never hardcode schedule strings.
3. **No raw property type literals** — use `PRICE_TYPES` or `PROPERTY_TYPES` from `constants.py`.
4. **Source modules must not call each other** — declare dependencies in `METADATA.depends_on`.
5. **Derived modules must not download files** — only query `core_*` tables.
6. **Expected row ranges must be realistic** — too-narrow ranges cause false failures.
7. **HAVING COUNT(*) >= 3** or similar suppression for aggregated tables (privacy / data quality).
