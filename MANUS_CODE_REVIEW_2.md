# Manus Code Review — Round 2 (2026-04-13)

Reviewed by: Claude (session 18, working on batty's local codebase)
Branch reviewed: `manus/main` at commit `613e44c`
Compared against: `redesign/premium-ui` (local working branch)

---

## CRITICAL (P0) — Must Fix Before Shipping

### 1. `personalization.ts:121` — Runtime crash on `metric.registry.section_id`

The backend sends flat metric objects (`id`, `name`, `local_value`, `parent_value`, etc.). The frontend `Metric` type declares `registry: MetricRegistryMeta` as **required** (not optional), and `personalization.ts` accesses it without optional chaining:

```typescript
// personalization.ts line 121
function getMetricSection(metric: Metric): string {
  const sectionId = metric.registry.section_id;  // TypeError: Cannot read properties of undefined
}

// personalization.ts line 143
const aPriority = a.metric.registry.display_priority ?? 999;
const bPriority = b.metric.registry.display_priority ?? 999;
```

Since the backend does NOT send a `registry` sub-object, calling any persona function (`selectPersonaKeySignals`, `buildPersonaFitSummary`, `rankSectionsForPersona`) produces a `TypeError` at runtime.

This is the **single most dangerous bug** in the frontend. It crashes the moment persona features are used, and because there is **no React Error Boundary** anywhere in the app (see P1 #8), the entire Results page white-screens with no recovery.

**Fix:** Make `registry`, `headline`, `comparison`, `trend`, `map_binding` all optional (`?:`) in the `Metric` interface in `types/index.ts`, and add `?.` everywhere they're accessed. Or add a transform layer in `client.ts` that wraps the flat backend fields into the nested sub-objects the frontend expects.

---

### 2. SQL injection surface in `resolve.py` suggest endpoint

When `is_partial_district` is true, user input (`compact`) is interpolated directly into SQL via f-strings:

```python
# resolve.py, suggest endpoint, postcode district branch (~lines 95-130)
sql = sa_text(f"""
    WITH candidates AS (
        SELECT
            SUBSTRING(postcode_compact FROM 1 FOR {dist_len}) AS label,
            CASE WHEN postcode_compact SIMILAR TO '{compact}[A-Z]%' THEN 0 ELSE 1 END AS pref,
            ...
        FROM core_postcodes
        WHERE postcode_compact SIMILAR TO '{compact}[A-Z0-9]%'
        GROUP BY 1, 2, lad_name
    ),
    ...
""")
```

There is an `isalnum()` guard earlier, which limits the attack surface. But the principle is violated — user-controlled strings should never be interpolated into SQL, only bind parameters. This should use parameterised queries exclusively.

**Severity:** Medium (mitigated by `isalnum()` guard, but the pattern is wrong).

---

### 3. Crime rate annualisation mismatch in `tab_environment.py`

Local crime comes from a **single month** (`AND month = :month`) and is then multiplied by 12:

```python
local_rate = round(local_total / local_pop * 1000 * 12, 1)
```

But the parent comparison uses a **rolling 12-month window** and divides by `months_count`:

```python
parent_rate = round(parent_crimes / parent_months / parent_pop * 1000 * 12, 1)
```

This is apples-to-oranges. A single bad month locally (festival, one-off incident) gets amplified 12x while the parent rate is smoothed over 12 months. The local rate should also use a 12-month rolling window.

---

### 4. `latest_month.replace(year=latest_month.year - 1)` will crash on Feb 29

**File:** `backend/app/services/tab_environment.py`, multiple locations.

If `latest_month` is `2024-02-29` (leap year), calling `.replace(year=2023)` raises `ValueError` because Feb 29 doesn't exist in 2023. Use `dateutil.relativedelta(years=1)` instead.

---

## HIGH (P1) — Serious Issues

### 5. `area.py` is 1,956 lines — unmaintainable god-file

This single router contains: tab data endpoint, price history, price by type, transactions (paginated), AQ history, comparable areas, map POIs (with per-tab branching), boundaries (5 types), choropleth (30+ layers). Each is a distinct concern. The choropleth handler alone is ~300 lines.

**Recommendation:** Split into `area_tabs.py`, `area_map.py`, `area_boundary.py`, `area_choropleth.py`, `area_reports.py`.

---

### 6. `metric_registry.py` is 87KB of hardcoded Python

A massive `METRIC_REGISTRY` dictionary with entries for every metric. This duplicates data that belongs in a database table or YAML config file. At 87KB, it is too large to maintain manually and will inevitably drift from the actual metrics emitted by tab services.

**Recommendation:** Either move to a YAML/JSON config loaded at startup, or generate it from the actual metric output.

---

### 7. Comparable areas runs 330 correlated subqueries against 28.9M rows

**File:** `backend/app/services/comparable_areas.py`, `FEATURES_SQL`

```sql
SELECT lb.lad_code, lb.lad_name,
    (SELECT AVG(price) FROM core_property_transactions
     WHERE lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = lb.lad_code)
       AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
       AND property_type = ANY(:price_types)
    ) AS avg_price,
    ...
FROM core_lad_boundaries lb
```

Each of 330 LADs runs a correlated subquery scanning `core_property_transactions` (30.4M rows) with a nested subquery. This is O(330 × expensive scan).

**Fix:** Use a single aggregated CTE or a pre-materialised view.

---

### 8. No React Error Boundary anywhere in the app

**File:** `frontend/src/App.tsx`

There's a `<Suspense>` boundary for lazy loading, but no `<ErrorBoundary>`. If any component throws during rendering (like the P0 crash in personalization.ts), the entire application white-screens with an unrecoverable React error.

**Fix:** Add `<ErrorBoundary>` around at least the Results page.

---

### 9. 860 lines of static config inline in Results.tsx

`CHOROPLETH_KEYS` (33 keys), `TAB_EXPLAINERS`, `TAB_SOURCE_GROUPS`, `MAP_LAYER_PRIORITY`, `MAP_METRIC_LINKS` (~30 objects), `METRIC_MAP_BINDINGS` (~50 objects) — all defined inside the Results module at lines 34-892.

**Fix:** Extract to `resultsConstants.ts`.

---

### 10. Choropleth key arrays duplicated 3 times

`CHOROPLETH_KEYS` is defined once as a constant at line 34, then the **same 33 keys** are copy-pasted as inline string arrays at lines 978 and 991 (inside `useEffect` callbacks). Adding a new choropleth layer requires updating all three locations.

---

### 11. 20+ tables have no DDL — schema not reconstructible from SQL files

The following tables are created inline by their ETL source modules but have **no authoritative CREATE TABLE** in any SQL file or migration:

`core_crime_lsoa`, `core_census_ethnicity_ward`, `core_county_boundaries`, `core_place_boundaries`, `core_place_lsoa_mapping`, `core_place_lsoa_mapping_town`, `core_earnings_lad`, `core_price_sqm_lad`, `core_price_sqm_lsoa`, `core_price_by_bedrooms_lad`, `core_nhs_lsoa`, `core_broadband_lad`, `core_mobile_coverage_lad`, `core_ptal_lsoa`, `core_cycling_lsoa`, `core_flood_lsoa`, `core_air_quality_lad`, `core_council_control_lad`, `core_s114_notices`, `core_water_company_lad`

A fresh `psql -f sql/*.sql` will NOT create these tables.

**Fix:** Add a `sql/004_etl_tables.sql` (or similar) with CREATE TABLE IF NOT EXISTS for all ETL-managed tables.

---

### 12. `003_transactions.sql` missing columns needed by ETL

Creates `core_property_transactions` with only 16 columns, but the ETL writes `lad_code`, `district`, `county`, `ppd_category`, `floor_area_sqm`, `bedrooms_estimated`, `epc_rating`, `price_per_sqm`, `price_per_sqft`, and `lsoa_month_*` columns that only exist after migrations 003-006 run.

A **fresh deployment** using `sql/003_transactions.sql` followed by an immediate ETL run will fail unless migrations are applied first. This is a race condition on first deploy.

---

### 13. `006_populate_aggregates.py` table swap without transaction

```python
conn.autocommit = True
cur.execute("ALTER TABLE core_property_transactions RENAME TO core_property_transactions_old")
cur.execute("ALTER TABLE core_property_transactions_new RENAME TO core_property_transactions")
cur.execute("DROP TABLE core_property_transactions_old")
```

Three separate transactions with `autocommit = True`. If the process dies between the first RENAME and the second, the table `core_property_transactions` doesn't exist and the application is down.

**Fix:** Wrap in a single transaction (set `autocommit = False`, execute all three, then `conn.commit()`).

---

## MEDIUM (P2) — Should Fix

### 14. GMP LAD codes hardcoded in two places

Defined as a `frozenset` in `backend/app/constants.py` AND as an inline `set` literal in `backend/app/services/tab_environment.py`. The tab_environment.py version does NOT import from constants. If boundary codes change, one copy will be missed.

---

### 15. County parent comparison fetches ALL ~300+ England LADs

**File:** `backend/app/services/helpers.py`, `make_lsoa_session()`

When a county is searched, ALL England LAD codes are fetched and passed as `parent_lad_codes`. Every subsequent tab handler passes 300+ codes to `WHERE lad_code = ANY(:parent_lads)`, which degrades PostgreSQL's ability to use indexes. The planner often falls back to sequential scans.

---

### 16. Welsh/Scottish country detection is metadata theater

`infer_country_from_geo_codes()` correctly detects country from code prefixes (W=Wales, S=Scotland) and sets status to "partial"/"planned". But every actual data query in all 5 tab services queries tables that contain England-only data (or in some cases no Welsh data at all). The detection tells the frontend "Wales partial" but then returns empty results.

**Note:** The DB dump we're uploading to Google Drive includes Welsh data for postcodes, boundaries, census, HPI, governance, land registry (1.45M Welsh transactions), and crime (302K Welsh rows). This should help close the gap.

---

### 17. Ethnicity metric uses ward_code only — breaks for area searches

**File:** `backend/app/services/tab_community.py`, ethnicity section.

```python
ethnicity_local = await db.execute(
    text("SELECT AVG(pct_white) ... FROM core_census_ethnicity_ward WHERE ward_code = :ward"),
    {"ward": ward_code},
)
```

For LAD/county/place searches, `ward_code` is `"_"`, so this returns nothing. Ethnicity data is silently dropped for all non-postcode searches.

---

### 18. CommuteEstimator bypasses React Query

**File:** `frontend/src/components/CommuteEstimator.tsx`, lines 155-170.

Uses raw `useEffect` + `fetch` instead of `useQuery`. Results.tsx already fetches the same Lifestyle tab via React Query. This duplicates the API call — the same request fires twice, wasting the 60 req/min rate limit budget.

**Fix:** Use `useQuery` with the same cache key pattern, or accept the tab data as a prop from Results.tsx.

---

### 19. 40+ unsafe `as` casts in MetricCard.tsx

**File:** `frontend/src/components/MetricCard.tsx`, lines 519-798.

`metric.details` is typed as `Record<string, unknown> | null` but values are immediately cast without runtime validation:

```typescript
(details.schools as Record<string, unknown>[]).map(...)
details.decile as number
details.flood_level as string
details.band as string
```

~40 unsafe casts. If the backend changes a field's type, these silently produce wrong UI or NaN.

---

### 20. Hardcoded credentials in docker-compose.yml

```yaml
POSTGRES_PASSWORD: ukproperty_dev
DATABASE_URL: postgresql+asyncpg://ukproperty:ukproperty_dev@db:5432/ukproperty
```

Also in `airflow/docker-compose.airflow.yml`:
- `AIRFLOW__WEBSERVER__EXPOSE_CONFIG: 'true'` — exposes ALL Airflow config (including secrets) via the web UI
- `--username admin --password admin` — default admin credentials

**Fix:** Move to `.env` file (add `.env.example` for docs), set `EXPOSE_CONFIG: 'false'`.

---

### 21. Hardcoded DSN in migration scripts

`etl/migrations/006_populate_aggregates.py` line 15 and `etl/migrations/absorb_epc.py` line 12 both have:

```python
DSN = "dbname=ukproperty user=postgres"
```

These bypass env-var-based credential management. The `migrate.py` runner correctly uses `os.environ.get("DATABASE_URL", ...)` but these standalone scripts do not.

---

### 22. nginx `connect-src 'self'` blocks MapLibre tile fetching

**File:** `frontend/nginx.conf`

The Content-Security-Policy `connect-src 'self'` directive blocks all outbound `fetch()` calls. MapLibre fetches tiles via `fetch()`, which is governed by `connect-src` (not `img-src`). Tile requests to OpenStreetMap / CartoCDN will be blocked.

**Fix:**
```
connect-src 'self' https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com;
```

---

### 23. No database connection pooling configuration

**File:** `backend/app/database.py`

```python
engine = create_async_engine(settings.DATABASE_URL, echo=False)
```

No `pool_size`, `max_overflow`, `pool_timeout`, or `pool_recycle`. SQLAlchemy defaults to `pool_size=5`, which is too small for concurrent users hitting PostGIS spatial queries.

**Fix:** Set `pool_size=20, max_overflow=10, pool_timeout=30, pool_recycle=1800`.

---

### 24. Cache layer silently swallows ALL errors

**File:** `backend/app/cache.py`

```python
async def cache_get(key: str):
    ...
    except Exception:
        return None

async def cache_set(key: str, value, ttl: int = 3600):
    ...
    except Exception:
        pass
```

Every Redis error is silently swallowed. Cache corruption, serialization failures, and connectivity issues all go unlogged.

**Fix:** Add `logger.warning("Redis error in cache_get: %s", e)` at minimum.

---

### 25. Air quality spatial joins unbounded for parent comparisons

**File:** `backend/app/services/tab_environment.py`

```sql
SELECT AVG(a.no2_ugm3), AVG(a.pm25_ugm3)
FROM core_air_quality a
JOIN core_lad_boundaries l ON ST_Intersects(l.geom, a.geom)
WHERE l.lad_code = ANY(:parent_lads)
```

For 300 parent LADs, this joins the entire air quality grid with all LSOA boundaries. Very expensive even with a GiST index.

**Fix:** Pre-compute LSOA-level air quality aggregates (we have `core_air_quality_lad` for this).

---

### 26. `boundaries.py` TRUNCATEs before API fetch

Each boundary function does `TRUNCATE TABLE ... CASCADE` **before** fetching from the ArcGIS API. If the API fails after TRUNCATE, the table is empty and the app shows no boundaries.

**Fix:** Fetch first, validate response, then truncate+insert in one transaction.

---

### 27. `land_registry_full.py` TRUNCATEs without safety net

TRUNCATE is committed separately before the COPY begins. If the COPY fails mid-stream (disk full, connection drop, corrupt CSV row), the 30M-row table is empty and the application is down. No rollback possible since TRUNCATE already committed.

**Fix:** Use a temp table approach: COPY into `_tmp`, then swap tables in a single transaction.

---

### 28. OSM amenities only fetches England bbox

**File:** `etl/sources/osm_amenities.py`

Uses `ENGLAND_BBOX` from constants despite the codebase claiming Wales is "partial". The `supported_overpass_bboxes()` function exists in constants but is not used here. Welsh amenity searches would return nothing from this table.

**Note:** Our local DB already has Welsh amenity data because we previously ran with a UK-wide bbox. The dump we're uploading includes this data.

---

### 29. dbt models reference nonexistent columns

- `mart_comparable_lad.sql` uses `hpi_yoy`, `year_month` — neither exists in `core_hpi_lad`
- `mart_lad_summary.sql` uses `c.total_crimes` — doesn't exist in `core_crime_lsoa` (table stores per-type counts)
- `mart_broadband_lad.sql` and others hardcode `WHERE lad_code LIKE 'E%'`

These models would fail if actually executed against the database.

---

### 30. Boundary endpoint returns inconsistent shapes

**File:** `backend/app/routers/area.py`, `/boundary`

- `ward_lsoa` returns `{"type": "FeatureCollection", "features": [...]}`
- `lad`, `county`, `place`, `ward` return a single `{"type": "Feature", ...}`

The frontend must handle both FeatureCollection and Feature at the same endpoint.

**Fix:** Always return FeatureCollection (wrap single Features).

---

### 31. Monolithic state management in Results.tsx

The `Results()` function contains 20+ `useState`, 9 `useQuery`, 15+ `useMemo`, 10+ `useCallback`, 5+ `useEffect`. Sub-components were extracted for rendering but ALL state, data fetching, and derived computations remain in the parent with 25+ props drilled down to `ResultsPageShell`.

**Fix:** Use React context or a lightweight state manager (zustand/jotai) to decouple sub-components.

---

## LOW (P3) — Nice to Fix

### 32. `data_freshness` endpoint has no auth
Exposes internal ETL pipeline status (source names, timestamps, row counts, error statuses) to any unauthenticated user.

### 33. Commute endpoint returns 503 permanently
Should be removed from the router or return 501 (Not Implemented). 503 implies temporary unavailability and may trigger monitoring alerts.

### 34. Session helper functions duplicated across `area.py` and `report.py`
`_geo(sess)`, `_geo_comparison_scope(sess)`, `_session_centroid(sess)`, etc. defined identically in both files.

### 35. `_Rows` hack object in area.py
Creates a fake SQLAlchemy result wrapper to merge two query results. Should merge into a list directly.

### 36. No CI/CD pipeline
No GitHub Actions, GitLab CI, or any automated testing/deployment.

### 37. No TLS configuration in nginx
Listens on port 80 only. No HTTPS, no redirect, no certificate handling.

### 38. Redis has no persistence volume
All cached sessions lost on container restart. Every restart forces all users to re-resolve.

### 39. Frontend Dockerfile uses `npm ci` but project may use pnpm
Session 30 handoff references `pnpm build`. Lockfile format mismatch possible.

### 40. `framer-motion` (~35KB gzipped) used only for expand/collapse animation
Could be replaced with native CSS `max-height` transitions or `<details>` element.

### 41. `esc()` in MapView.tsx doesn't escape single quotes
Missing `.replace(/'/g, '&#39;')`. Low risk since data comes from our backend, but the pattern is fragile.

### 42. Manus sandbox hostname in `vite.config.ts` `allowedHosts`
Dead config pointing to `4173-iip7rtorujtgf7qd7355k-a901cf2e.us2.manus.computer`.

### 43. `CoverageMetadata` type defined in two places
Both `client.ts` and `types/index.ts` define the same interface. Only `client.ts` version is imported.

### 44. Home page preview card shows hardcoded fake data
Always shows "Coulsdon, CR5" with score 78 regardless of reality.

---

## What Manus Did Well

To be fair, there are genuinely good decisions in this codebase:

- **Session-key architecture** is solid. Deriving everything once at `/resolve` time and storing it in Redis eliminates redundant DB work.
- **Commute estimator withdrawn honestly** rather than shipping heuristic garbage. Good editorial judgment.
- **Section 114 metric withheld** with a clear note about why.
- **Crime Welsh LSOA crosswalk** — genuinely sophisticated proportional allocation with largest-remainder method for split LSOAs.
- **Census upsert strategy** — per-domain ON CONFLICT DO UPDATE allows partial re-runs without data loss.
- **Pipeline orchestrator** (`pipeline.py`) — topological sort, dependency tracking, schedule tiers, dry-run mode.
- **Adaptive geometry simplification** in choropleth handler (`ST_Simplify` threshold based on LSOA count).
- **Cache versioning** (`AREA_CACHE_VERSION = "v8"`) prevents stale cache hits after schema changes.
- **Security headers middleware** with CSP, X-Frame-Options, fingerprint removal.
- **Lazy-loaded chart components** — 7 chart types loaded on demand via `React.lazy()`.
- **Vite manual chunk splitting** — maplibre, recharts, framer-motion, spatial-index separated into vendor chunks.
- **Scroll-to-metric sync** — rAF throttled with passive scroll listener. Correct high-performance pattern.
- **Coverage metadata** on every resolve/suggest response — honest "partial coverage" warnings.
- **GMP crime gap handling** — honest "data unavailable" message rather than misleading zeroes.

---

## Database Dump — Restore Instructions

A complete PostgreSQL dump of the `ukproperty` database is available on Google Drive at:

```
gdrive:PropertyPulse/ukproperty_20260413.dump     (4.24 GB, pg_dump custom format)
gdrive:PropertyPulse/ukproperty_20260413_v2.dump   (will appear after EPC backfill completes)
```

### How to Restore

```bash
# 1. Create the database (if it doesn't exist)
createdb -U postgres ukproperty

# 2. Enable PostGIS
psql -U postgres -d ukproperty -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 3. Restore the dump (this creates ALL tables, indexes, views, materialized views)
pg_restore -U postgres -d ukproperty --no-owner --no-privileges --jobs=4 ukproperty_20260413.dump
```

This gives you the **exact same database** we have — every table, every row, every index, every materialized view. No need to run any ETL scripts or download any source data files.

### What's In the Dump

| Table | Rows | Description |
|-------|------|-------------|
| core_postcodes | 1,746,552 | E=1.49M, W=92K, S=162K — postcode → LSOA/LAD/lat/lon |
| core_lsoa_boundaries | 35,672 | E=33,755, W=1,917 — LSOA polygons |
| core_ward_boundaries | 7,943 | Ward polygons (E+W) |
| core_lad_boundaries | 350 | LAD polygons (E+W) |
| core_county_boundaries | 42 | County polygons |
| core_census_lsoa | 35,672 | ALL columns populated (demographics, housing, commute, health, cars, economic activity, qualifications, born abroad) |
| core_census_ethnicity_ward | ~7,900 | Ethnicity breakdown by ward |
| core_hpi_lad | 122,533 | House Price Index — 22 Welsh LADs included |
| core_property_transactions | 30,411,775 | E=28.96M, W=1.45M — ALL Land Registry sales 1995–present |
| core_crime_lsoa | 5,958,276 | E=5.66M (33,828 LSOAs), W=302K (1,917 LSOAs) — 36 months |
| core_schools | ~25,000 | GIAS + Ofsted + KS2/KS4 (England only — DfE data) |
| core_imd_lsoa | ~33,000 | IMD 2019 all domains (England only — MHCLG data) |
| core_epc_domestic | 29,200,000 | Full EPC register (6.5 GB — needed for backfill matching) |
| core_epc_lsoa | ~33,000 | Aggregated EPC stats per LSOA |
| core_council_control_lad | 350 | Political control — 22 Welsh councils included |
| core_s114_notices | ~10 | Section 114 notices |
| core_broadband_postcode | 1,730,000 | FTTP + superfast percentages |
| core_broadband_lad | ~350 | LAD-level broadband aggregates |
| core_osm_amenities | ~500,000 | UK-wide POIs (shops, restaurants, GP surgeries, etc.) — Welsh data included |
| core_transport_stops | ~400,000 | NaPTAN stops — 47K Welsh stops included |
| core_nhs_facilities | ~20,000 | UK-wide — 3.3K Welsh facilities included |
| core_ev_chargers | ~50,000 | UK-wide OZEV registry |
| core_flood_zones | varies | UK-wide EA flood data |
| core_green_space | varies | UK-wide green space |
| core_air_quality | varies | Air quality grid |
| core_voa_rents_lad | ~350 | VOA private rental market statistics |
| core_earnings_lad | ~350 | ASHE annual earnings |
| core_council_tax_lad | ~350 | Council tax bands |
| core_noise | varies | Road/rail noise (if populated) |
| core_water_company_lad | ~350 | Water company coverage |
| mv_parent_yearly_price_stats | — | Materialized view for parent price comparisons |
| mv_parent_rolling_price_stats | — | Materialized view for rolling price comparisons |

**v2 dump** (uploaded after EPC backfill completes) will additionally have `floor_area_sqm`, `bedrooms_estimated`, `epc_rating`, `price_per_sqm`, `price_per_sqft` populated on ~14M rows in `core_property_transactions`.

---

## Code Changes Needed to Use Welsh Data

The dump has Welsh data, but your code has several England-only filters that prevent it from being served. Here are the specific changes needed:

### Fix 1: `tab_environment.py` — Crime queries already work for Welsh LSOAs
No change needed — crime queries use `lsoa_code = ANY(:codes)` which works for both E and W prefixed codes. The dump includes 302K Welsh crime rows.

### Fix 2: `tab_community.py` — Census queries already work for Welsh LSOAs
No change needed — census queries use `lsoa_code = ANY(:codes)` against `core_census_lsoa` which now has all 1,917 Welsh rows with all columns populated.

### Fix 3: `tab_community.py` — Ethnicity breaks for area searches (item #17)
The ethnicity query only works for postcode searches (uses `ward_code`). For LAD/county/place searches, it should aggregate across all wards in the area:

```python
# INSTEAD OF:
#   WHERE ward_code = :ward
# USE:
#   WHERE ward_code = ANY(:ward_codes)
# where ward_codes comes from the session's ward list
```

### Fix 4: `tab_property.py` — Price queries already work for Welsh postcodes
No change needed — property queries use `lsoa_code = ANY(:codes)` which works for Welsh LSOAs. The dump includes 1.45M Welsh transactions.

### Fix 5: `tab_governance.py` — Council queries already work for Welsh LADs
No change needed — governance queries use `lad_code` which works for W-prefixed codes. The dump includes 22 Welsh councils.

### Fix 6: `tab_lifestyle.py` — Amenity queries already work for Welsh areas
No change needed — OSM amenity queries use spatial joins (`ST_DWithin` / `ST_Intersects`) which work regardless of country. The dump includes Welsh amenity data.

### Fix 7: `imd.py` (ETL) — England-only by design
IMD is an England-only dataset from MHCLG. Welsh deprivation uses a completely different methodology (WIMD from Welsh Government). For now, Welsh LSOAs will correctly show "no deprivation data available". To support Welsh deprivation, you'd need to:
1. Download WIMD data from StatsWales
2. Create a new ETL source `wimd.py`
3. Either extend `core_imd_lsoa` or create a separate `core_wimd_lsoa` table
4. Modify `tab_community.py` to query the appropriate table based on country

### Fix 8: `schools.py` (ETL) — England-only filter at line 237
```python
# Line 237: currently filters to England only
if not lad_code.startswith("E"):
    continue
```
This is actually **correct** — GIAS/Ofsted/KS2/KS4 data comes from DfE which only covers England. Welsh school data comes from Estyn (inspections) and PLASC (pupil census). To add Welsh schools, you'd need:
1. Download Estyn inspection data from `estyn.gov.wales`
2. Download school locations from `gov.wales/address-list-of-schools`
3. Create a parallel ingest path in `schools.py` for Welsh data
4. The dump's `core_schools` table already has the right schema to hold Welsh schools

### Fix 9: `osm_amenities.py` (ETL) — England bbox only (item #28)
```python
# Currently uses ENGLAND_BBOX from constants
# Change to use a wider bbox that includes Wales:
# ENGLAND_BBOX = "49.9,-6.5,55.9,2.0"  (England only)
# UK_BBOX      = "49.9,-8.2,60.9,2.0"  (includes Wales + Scotland)
```
**Note:** The dump already has Welsh amenity data (loaded from a previous UK-wide run), so this only matters if you re-run the OSM ingest.

### Fix 10: `comparable_areas.py` — Include Welsh LADs
The comparable areas feature vector query only returns data for LADs that have transactions, HPI, and earnings data. Welsh LADs now have transactions and HPI in the dump. If `core_earnings_lad` and `core_voa_rents_lad` also have Welsh rows (they should — ASHE and VOA are UK-wide), Welsh LADs will automatically appear in comparable area results.

### Fix 11: `helpers.py` — Country detection already works
`infer_country_from_geo_codes()` correctly detects Welsh codes (W prefix) and returns `"partial"` status. No change needed — but as you fix the data gaps above, you can upgrade Wales from `"partial"` to `"live"`.

---

## Summary: What Works Immediately After Restore

| Feature | England | Wales | Notes |
|---------|---------|-------|-------|
| Property prices / charts | Yes | **Yes** | 1.45M Welsh transactions in dump |
| Crime rates / trends | Yes | **Yes** | 302K Welsh crime rows in dump |
| Census demographics | Yes | **Yes** | All columns for 1,917 Welsh LSOAs |
| House Price Index | Yes | **Yes** | 22 Welsh LADs |
| Council political control | Yes | **Yes** | 22 Welsh councils |
| Schools + Ofsted | Yes | No | DfE data is England-only; need Estyn for Wales |
| IMD deprivation | Yes | No | MHCLG is England-only; need WIMD for Wales |
| Amenities (OSM) | Yes | **Yes** | UK-wide data in dump |
| Transport stops | Yes | **Yes** | 47K Welsh stops in dump |
| NHS facilities | Yes | **Yes** | 3.3K Welsh facilities in dump |
| EV chargers | Yes | **Yes** | UK-wide in dump |
| Flood zones | Yes | **Yes** | UK-wide in dump |
| Broadband speeds | Yes | Partial | Depends on postcode coverage |
| Council tax | Yes | No | Need Welsh data from StatsWales |
| EPC ratings | Yes | Partial | EPC register is E+W but backfill matching ongoing |
| Comparable areas | Yes | **Yes** | If VOA/ASHE have Welsh rows |
| Map boundaries | Yes | **Yes** | 1,917 Welsh LSOA + ward + LAD boundaries |

**Bottom line:** After restoring the dump, ~70% of features work for Wales immediately. Schools, IMD, and council tax are the main gaps requiring separate Welsh data sources.
