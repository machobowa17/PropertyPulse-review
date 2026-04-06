# PropertyPulse — Complete Handover Document

**Date:** 2026-04-06
**Branch:** `redesign/premium-ui`
**Status:** Production-ready for England (42+ metrics, 5 tabs, persona engine, interactive map)

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [How to Run](#4-how-to-run)
5. [Architecture](#5-architecture)
6. [Database](#6-database)
7. [Backend API](#7-backend-api)
8. [Frontend](#8-frontend)
9. [ETL Pipeline](#9-etl-pipeline)
10. [Testing](#10-testing)
11. [Known Issues & Data Gaps](#11-known-issues--data-gaps)
12. [Work Queue](#12-work-queue)
13. [Inviolable Rules](#13-inviolable-rules)
14. [Session History](#14-session-history)

---

## 1. What This Is

PropertyPulse is a UK property data portal. A user enters a postcode, place name, ward, LAD (local authority), or county, and gets a comprehensive data dashboard across 5 tabs:

1. **Property & Market** — prices, transactions, tenure, new builds, rents, yields
2. **Lifestyle & Connectivity** — amenities, transport, broadband, EV chargers, commute
3. **Environment & Safety** — crime, flood, air quality, green space, EPC, noise
4. **Community & Education** — demographics, schools, NHS, deprivation, census data
5. **Local Governance** — council tax, political control, water company, financial health

Each metric shows a local value, a parent comparison value (county/region), a colour-coded persona-aware takeaway ("So What" / "Watch Out"), and expandable detail panels with charts, tables, and maps.

There's also a persona engine (Family Buyer, Young Professional, Investor, Retired, Student, Expat) that weights each metric per persona and produces a 0-100 fit score.

The interactive map shows boundary outlines, sold price markers (clustered), school/station/charger POIs, isochrone walking rings, and choropleth heatmaps (avg price, price per sqft, EPC score).

A PDF report generator (`/api/v1/report`) produces a downloadable report for any search.

---

## 2. Tech Stack

| Layer | Tech | Version |
|-------|------|---------|
| Backend | FastAPI + Uvicorn | Python 3.11+ |
| Database | PostgreSQL 16 + PostGIS | ~20 GB |
| Cache | Redis | Default config |
| Frontend | React 19 + TypeScript 5.9 | Vite 8 dev server |
| Charts | Recharts 3.8 | |
| Map | MapLibre GL 5.21 + Supercluster 8.0 | |
| CSS | Tailwind 4.2 | |
| Icons | Lucide React 1.7 | |
| Animations | Framer Motion 12.38 | |
| Testing | Playwright 1.58 (Python bindings) | |
| ETL | Python scripts + psycopg2 (sync) | |
| PDF | ReportLab | |

---

## 3. Project Structure

```
backend/
  app/
    main.py              — FastAPI app, CORS, rate limiting, exception handler
    config.py            — DATABASE_URL, REDIS_URL, ALLOWED_ORIGINS, RATE_LIMIT
    database.py          — AsyncSession via SQLAlchemy asyncpg
    cache.py             — Redis async pool, cache_get/set/del with TTL
    constants.py         — PRICE_TYPES, TABLE_NAMES, TYPE_NAMES, EPC_COLOURS, etc.
    errors.py            — http_error() helper
    routers/
      resolve.py         — GET /resolve, GET /search/suggest
      area.py            — GET /area, /price-history, /price-by-type, /transactions,
                           /aq-history, /comparable, /map-pois, /boundary, /map-choropleth
      commute.py         — GET /commute
      report.py          — GET /report (PDF)
      health.py          — GET /health
      data_freshness.py  — GET /data-freshness
    services/
      geo_resolver.py    — Search resolution (postcode/place/ward/LAD/county)
      helpers.py         — Session creation, LSOA expansion, parent LAD lookup
      tab_property.py    — Property & Market metrics (10 metrics)
      tab_lifestyle.py   — Lifestyle & Connectivity metrics
      tab_environment.py — Environment & Safety metrics
      tab_community.py   — Community & Education metrics
      tab_governance.py  — Local Governance metrics
      comparable_areas.py — Similar LAD finder (Euclidean distance on z-scored features)
  SESSION_CONTRACT.md    — Session → table JOIN key mapping

etl/
  pipeline.py            — Orchestrator: dependency sort, run tracking, cache invalidation
  migrate.py             — Schema migration runner
  constants.py           — TABLE_NAMES, SCHEDULE_* constants (mirrors backend constants)
  sources/               — 29 source modules (each has METADATA + run(db_url))
  derived/               — 4 derived modules (query core_* → new core_* tables)
  legacy/                — Superseded modules (kept for reference, NOT used)
  migrations/            — Numbered SQL migration files (001-007+)
  data/                  — Local data files (CSVs, ZIPs, GeoJSON, etc.)
  DATA_SOURCES.md        — Every data source with URL, license, table, expected rows
  PIPELINE.md            — Pipeline architecture, execution order, module interface

frontend/
  src/
    pages/
      Home.tsx           — Dark cinematic landing page
      Results.tsx        — Main dashboard (tabs, metrics, map, calculators)
      Attribution.tsx    — Data sources and licenses
    components/
      SearchBox.tsx      — Debounced search with dropdown suggestions
      MetricCard.tsx     — THE core component — renders any metric with expanded details
      MapView.tsx        — MapLibre GL map with POIs, boundaries, choropleths
      MapLayerControl.tsx — Toggle map layers
      PersonaSelector.tsx — Persona dropdown
      TransactionTable.tsx — Paginated, sortable transaction table
      CommuteEstimator.tsx — Commute time estimator
      ComparableAreas.tsx — Similar LADs panel
      MortgageCalculator.tsx, RentalYieldCalculator.tsx
      DistrictPriceHistoryChart.tsx, NewBuildTrendChart.tsx, AmenityRadarChart.tsx,
      AirQualityChart.tsx, EpcRatingChart.tsx, PriceByTypeChart.tsx, etc.
    api/client.ts        — All fetch functions + TypeScript interfaces
    types/index.ts       — ResolveResponse, Metric, AreaResponse, TabName, PersonaId
    utils/
      tabs.ts            — TABS config, formatValue(value, unit), METRIC_ICONS
      personas.ts        — 6 personas, getTakeaway() engine (252 rules), weight matrix

sql/
  001_schema.sql         — Original schema (historical; some tables since dropped)
  002_remaining_tables.sql
  003_transactions.sql

sessions/                — Session notes from all 10 development sessions
QUEUE.md                 — Pending work queue
```

---

## 4. How to Run

### Prerequisites
- PostgreSQL 16 with PostGIS extension (`ukproperty` database)
- Redis server
- Node.js 18+ (for frontend)
- Python 3.11+ with pip

### Backend
```bash
cd backend
pip install -r requirements.txt  # fastapi, uvicorn, sqlalchemy[asyncpg], psycopg2, redis, reportlab, slowapi
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev          # Starts Vite on port 5173, proxies /api → localhost:8000
```

### Production frontend build
```bash
cd frontend
npm run build        # Output in dist/ (2,010 kB JS, 127 kB CSS)
# Serve with nginx using frontend/nginx.conf
```

### ETL
```bash
cd etl
python3 pipeline.py --dry-run --all     # Show execution order
python3 pipeline.py --schedule monthly  # Run monthly sources
python3 pipeline.py --source crime      # Run single source
python3 pipeline.py --status            # Check run history
python3 migrate.py                      # Run pending SQL migrations
```

### URLs
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/v1/
- Health check: http://localhost:8000/api/v1/health

---

## 5. Architecture

### The Session Key Pattern

This is the single most important architectural concept. **Every API endpoint takes a `session_key` as its only meaningful input.** No hardcoded values, no additional search parameters.

Flow:
1. User searches "CR5 1RA" → `GET /api/v1/resolve?q=CR5+1RA`
2. Backend resolves postcode → LSOA code, ward, LAD, coordinates
3. `make_lsoa_session()` expands to full LSOA set, computes parent LADs, generates deterministic session key (SHA256), stores in Redis (TTL 24h)
4. Returns `session_key` to frontend
5. **All subsequent calls** use only this key: `/area?session_key=X&tab=Property`, `/price-history?session_key=X`, etc.
6. Backend retrieves session from Redis, unpacks lsoa_codes/parent_lads/etc., queries DB

See `backend/SESSION_CONTRACT.md` for the full session schema, field usage per endpoint, and JOIN key mapping.

### Search Modes

| User Input | boundary_source | search_mode | LSOA Expansion |
|-----------|-----------------|-------------|----------------|
| Full postcode (CR5 1RA) | ward_lsoa | postcode | Single LSOA from postcode |
| District postcode (SW1A) | lad | area | All LSOAs in dominant LAD |
| LAD name (Manchester) | lad | area | All LSOAs in LAD |
| County name (Surrey) | county | area | All LADs in county → all LSOAs |
| Place name (Didsbury) | place | area | LSOAs from Voronoi mapping |
| Ward name | ward | area | All LSOAs in ward |

### Metric Structure

Every metric across all 5 tabs follows the same shape:
```json
{
  "id": "avg_price",
  "name": "Average Sale Price (last 12m)",
  "local_value": 662346,
  "parent_value": 550000,
  "unit": "GBP",
  "comparison_flag": "higher_than_parent",
  "details": { ... }   // Rich data for expanded view
}
```

The `comparison_flag` drives the colour coding in the frontend. The `details` object varies per metric (charts, lists, breakdowns, etc.).

### Parent Comparison

For every search, the backend identifies "parent LADs" — all LADs sharing the same county/region. For example, CR5 1RA is in Croydon → parent is "Greater London" → 33 London boroughs. Parent values are computed across these LADs for comparison context.

### Caching

Redis caches at multiple levels:
- `lsoa_sess:{key}` — session data (24h)
- `area:{key}:{tab}` — tab metrics (1h)
- `resolve:{query}` — resolve results (24h)
- `price_history:{key}`, `boundary:{source}:{id}`, etc. (24h)

The ETL pipeline invalidates relevant cache patterns after successful runs. Cache is never flushed entirely.

---

## 6. Database

**Database:** `ukproperty` on PostgreSQL 16 with PostGIS
**Size:** ~20 GB, ~19 GB disk free
**User:** `postgres` (no password, local socket auth)

### Key Tables

| Table | Rows | Size | Purpose |
|-------|------|------|---------|
| `core_property_transactions` | 28.9M | 14 GB | **THE master table** — Land Registry PPD + EPC columns + 12 lsoa_month_* aggregates |
| `core_postcodes` | ~2.5M | 1 GB | ONSPD postcode directory (lat/lon/lsoa/ward/lad/county) |
| `core_crime_lsoa` | ~6M | 896 MB | Monthly crime by LSOA and type |
| `core_lsoa_boundaries` | 33,755 | ~50 MB | LSOA polygons (geometry + lad_code) |
| `core_census_lsoa` | 33,755 | ~5 MB | Consolidated wide census table (~30 columns) |
| `core_schools` | ~28K | ~15 MB | Schools with Ofsted ratings + KS2/KS4 |
| `core_osm_amenities` | ~200K | ~30 MB | POIs (cafes, parks, pubs, etc.) |
| `core_imd_lsoa` | ~33K | ~5 MB | Index of Multiple Deprivation (7 domains) |
| `core_hpi_lad` | ~120K | ~15 MB | House Price Index by LAD |
| `core_epc_lsoa` | 33,755 | ~3 MB | Pre-aggregated EPC distribution |
| `core_nhs_facilities` | ~20K | ~5 MB | GP/hospital/dentist locations |
| `core_nhs_lsoa` | ~33K | ~3 MB | Pre-computed NHS count within 2km per LSOA |

### Master Table Columns (core_property_transactions)

The 40 columns include:
- **Land Registry fields:** transaction_id, price, date_of_transfer, postcode, property_type (D/S/T/F/O), old_new (Y/N), duration (F/L/U), paon, saon, street, locality, town, latitude, longitude, geom, lsoa_code, lad_code, district, county, ppd_category
- **EPC-matched fields:** epc_certificate_number, epc_match_score, floor_area_sqm, habitable_rooms, bedrooms_estimated, epc_rating, price_per_sqm, price_per_sqft
- **Pre-computed lsoa_month_* columns (12):** avg_price, median_price, min_price, max_price, transaction_count, new_build_count, freehold_count, leasehold_count, avg_freehold_price, avg_leasehold_price, avg_ppsm, avg_ppsft

### Key Indexes
- `idx_transactions_lsoa_date_type` on (lsoa_code, date_of_transfer, property_type) — THE primary query index
- `idx_transactions_lad` on (lad_code)
- `idx_transactions_postcode` on (postcode)
- Various spatial GiST indexes on geometry columns

### Materialized Views
- `mv_parent_yearly_price_stats` — yearly price aggregates by LAD (for parent comparison)
- `mv_parent_rolling_price_stats` — rolling 12m price aggregates by LAD
- These should be refreshed weekly (can be done via `REFRESH MATERIALIZED VIEW CONCURRENTLY`)

### Dropped Tables (historical — DO NOT recreate)
- core_transactions_epc (absorbed into master table)
- core_property_prices_lsoa, core_property_prices_lad, core_property_prices_district (replaced by raw queries on master)
- core_price_sqm_lsoa, core_price_sqm_lad (replaced by price_per_sqm/sqft on master)
- core_census_demographics_lsoa, core_census_housing_lsoa, core_census_hh_size_lsoa, core_census_commute_lsoa, core_census_extra_lsoa (consolidated into core_census_lsoa)

### Empty Tables (data never ingested)
- `core_noise` — schema exists (postcode, road_noise_db, rail_noise_db, air_noise_db, noise_band) but zero rows. Would need DEFRA strategic noise map data.
- `core_epc_domestic` — was dropped after EPC absorption. Would need re-download from MHCLG (see Known Issues).

---

## 7. Backend API

### Endpoints

| Method | Path | Params | Returns |
|--------|------|--------|---------|
| GET | `/api/v1/resolve` | `q` (search string) | session_key, resolved_codes, coordinates, type |
| GET | `/api/v1/search/suggest` | `q` (partial, 2+ chars) | suggestions[] (up to 8) |
| GET | `/api/v1/area` | `session_key`, `tab` | metrics[] (id, name, local_value, parent_value, unit, details) |
| GET | `/api/v1/price-history` | `session_key` | local[], regional[], by_bedrooms[] |
| GET | `/api/v1/price-by-type` | `session_key` | by_type{}, parent_by_type{} |
| GET | `/api/v1/transactions` | `session_key`, `page`, `page_size`, `sort_by`, `sort_dir`, `property_type` | transactions[], total, page, total_pages |
| GET | `/api/v1/aq-history` | `session_key` | local[], national[] (PM2.5, NO2, PM10) |
| GET | `/api/v1/comparable` | `session_key` | target{}, comparable[] (top 5 similar LADs) |
| GET | `/api/v1/commute` | `session_key`, `destination` | modes{driving, transit, cycling, walking} |
| GET | `/api/v1/map-pois` | `session_key`, `tab` | GeoJSON FeatureCollection |
| GET | `/api/v1/boundary` | `session_key` | GeoJSON Feature/FeatureCollection |
| GET | `/api/v1/map-choropleth` | `session_key`, `layer` | GeoJSON + quantile metadata |
| GET | `/api/v1/report` | `session_key` | PDF file |
| GET | `/api/v1/health` | — | {status, db, redis} |
| GET | `/api/v1/data-freshness` | — | sources[] with last_success, rows, status |

### Tab Service Function Signatures

All 5 tab service functions share the same signature:
```python
async def fetch_<tab>(
    db: AsyncSession,
    *,
    lad_code: str,
    ward_code: str,
    lsoa_codes: list[str],
    centroid_lat: float | None,
    centroid_lon: float | None,
    search_mode: str,
    local_lads: list[str],
    parent_lads: list[str],
    parent_name: str,
    boundary_source: str,
) -> list[dict]:
```

They return a list of metric dicts built with `helpers.metric()`.

### Error Handling
- `http_error(status, error_code, detail)` — raises HTTPException with structured body
- Common codes: 400 SESSION_KEY_REQUIRED, 410 SESSION_EXPIRED, 400 INVALID_TAB, 404 NOT_FOUND
- Rate limiting: 60 req/min per IP (429 on exceed)

### Config
```python
DATABASE_URL = "postgresql+asyncpg://postgres@localhost:5432/ukproperty"
DATABASE_URL_SYNC = "postgresql://postgres@localhost:5432/ukproperty"
REDIS_URL = "redis://localhost:6379/0"
ALLOWED_ORIGINS = "http://localhost:5173,http://localhost:3001"
RATE_LIMIT = "60/minute"
```

---

## 8. Frontend

### Pages
- **Home.tsx** — Dark cinematic landing page with SearchBox, feature cards, attribution strip
- **Results.tsx** — Main dashboard. On search: resolves → fetches all 5 tabs → renders active tab with metrics + map
- **Attribution.tsx** — 30 data sources with licenses

### Key Components
- **MetricCard.tsx** — THE core renderer. Takes a metric + persona, renders value, parent comparison, colour-coded takeaway, and expandable detail panel (charts, tables, lists, gauges). This is the most complex component.
- **MapView.tsx** — MapLibre GL map with Supercluster POI clustering, boundary outlines, choropleth heatmaps, isochrone rings, sold price popups
- **SearchBox.tsx** — Debounced typeahead with 7-stage suggestion ranking
- **TransactionTable.tsx** — Paginated, sortable, filterable transaction table
- **PersonaSelector.tsx** — Dropdown for 6 personas
- **DistrictPriceHistoryChart.tsx** — Multi-line price trend chart (local vs regional vs by-type vs by-bedrooms)
- Various other chart/gauge components (see project structure above)

### Data Flow
```
User search → resolveSearch(q) → sessionKey
  → fetchAreaTab(sessionKey, "Property & Market") → metrics[]
  → fetchPriceHistory(sessionKey) → charts
  → fetchBoundary(sessionKey) → map outline
  → fetchMapPois(sessionKey, tab) → POI markers
  → Pre-fetch remaining 4 tabs in background
```

### Persona Engine
`utils/personas.ts` contains 252 rules mapping (metric_id × persona × comparison direction) → {soWhat, watchOut, colour}. A weight matrix scores each metric per persona to produce a 0-100 fit score displayed in PersonaScoreCard.

### Key Dependencies
React 19, React Router 7, TanStack React Query 5, Recharts 3.8, MapLibre GL 5.21, Supercluster 8, Framer Motion 12, Lucide React, Tailwind 4.2

### Vite Config
```js
server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } }
```

### Nginx Config (production)
- Proxies `/api/` → `http://api:8000/api/`
- SPA fallback: `try_files $uri $uri/ /index.html`
- Security headers: X-Frame-Options DENY, CSP, no server_tokens
- Asset caching: 1 year for static files

---

## 9. ETL Pipeline

### Architecture
31 source/derived modules, topologically sorted by dependencies. Each module implements:
```python
METADATA = {
    "name": "land_registry_full",
    "schedule": SCHEDULE_MONTHLY,
    "depends_on": ["postcodes"],
    "tables_written": ["core_property_transactions"],
    "cache_key_patterns": ["area:*", "price_history:*"],
    "expected_row_range": (20_000_000, 40_000_000),
}

def run(db_url: str) -> int:
    # Ingest data, return row count
```

### Execution Order (31 modules)
```
Foundation (5): postcodes → boundaries → lad_county_lookup → place_names → place_boundaries
Monthly (5): land_registry_full → hpi → crime → schools → epc_domestic
Quarterly (5): epc_lsoa → osm_amenities → ev_chargers → governance → mobile_coverage
Annual (12): voa_rents → ashe → broadband → air_quality → flood → green_space → nhs →
             naptan → council_tax → water → cycling_ptal → place_lsoa_mapping → nhs_lsoa
One-time (2): census → imd
Derived (2): price_by_bedrooms
```

### Running
```bash
cd etl
python3 pipeline.py --schedule monthly    # Run monthly sources
python3 pipeline.py --source crime        # Run single source
python3 pipeline.py --dry-run --all       # Show order without running
python3 pipeline.py --status              # Check run history
python3 migrate.py                        # Run SQL migrations
```

### Data Sources
See `etl/DATA_SOURCES.md` for the complete list of 31 data sources with URLs, licenses, file locations, and expected row counts. All sources are UK government open data (OGL v3.0), except OSM amenities (ODbL) and water boundaries (CC-BY 4.0).

### Legacy Modules (in etl/legacy/ — do NOT run)
- `land_registry.py` — old incremental ingest, superseded by `land_registry_full.py`
- `transactions_epc.py` — Jaccard address-match EPC → transactions. Target table dropped. **This is the script needed for the EPC backfill (see Known Issues).**
- `price_sqm.py` — UCL price-per-sqm data. Target tables dropped.
- `import_epc.py` — older EPC import

---

## 10. Testing

### Playwright Browser Tests
- **Main suite:** `test_playwright_comprehensive.py` — **123/123 passing**
  - 10 sections: all 5 tabs × 3 search types, charts, map, null handling, tab switching, responsive, errors, navigation
- **Map tests:** `test_map_e2e.py` (needs 8s wait for sold markers), `test_map_edge_cases.py`
- **Isochrone:** `test_map_isochrone.py`

### API E2E Tests
- **Deep suite:** `/tmp/deep_e2e_test.py` — **890/891 passing**
  - 15 search scenarios × 9 test sections (resolve, property, cross-validation, all tabs, charts, maps, edge cases, commute, health)
  - 1 known gap: Whitby missing median_rent (new unitary authority data mapping)

### Running Tests
```bash
# Ensure backend (port 8000) and frontend (port 5173) are running
python3 test_playwright_comprehensive.py    # Browser tests
python3 /tmp/deep_e2e_test.py               # API tests (pace: 60 req/min limit)
python3 test_map_e2e.py                     # Map marker tests
```

### Key Playwright Patterns
- MetricCard selector: `[class*="border-l-"][class*="rounded-2xl"]`
- Tab buttons: `button[data-tab="Property & Market"]`
- LsoaContextBlurb: only renders for postcode/ward/district/county/place, NOT for `lad` type
- Recharts renders values in SVG, not DOM text (use SVG path assertions, not text content)

---

## 11. Known Issues & Data Gaps

### Critical: EPC Floor Area Data Only Covers 2024-2025

**Impact:** The price per sqft combined average chart lines only show data for 2024-2025. Historical years show null.

**Root Cause:** `core_epc_domestic` (the raw 23M EPC certificate table) does not exist in the database. It was dropped after only 2024-2025 transactions were matched with EPC records (~1.49M of 28.9M). The migration file (`005b_epc_update.sql`) noted: "After the full EPC re-ingest, run transactions_epc.py to match older transactions too." This was never done.

**Fix Required:**
1. Download the MHCLG domestic EPC bulk ZIP (~4-5 GB) from https://epc.opendatacommunities.org/downloads/domestic (requires registration)
2. Place at `etl/data/domestic-csv.zip`
3. Run `python3 pipeline.py --source epc_domestic` to load ~23M certificates
4. Move `etl/legacy/transactions_epc.py` back to `etl/derived/` and run it to Jaccard address-match ALL 28.9M transactions (not just recent ones)
5. Run `etl/migrations/absorb_epc.py` to copy matched floor areas to master table
6. Recompute `lsoa_month_avg_ppsm` and `lsoa_month_avg_ppsft` aggregates

The `transactions_epc.py` script is already written and working — it processes postcodes in batches of 500, doing Jaccard similarity matching between transaction addresses and EPC certificate addresses (threshold ≥ 0.5).

### Empty Tables

| Table | Issue | Data Source |
|-------|-------|-------------|
| `core_noise` | Zero rows. Schema exists but data never ingested. | DEFRA strategic noise maps (road, rail, aviation dB levels). Not yet downloaded. |
| `core_epc_domestic` | Does not exist. Needed for historical EPC matching. | MHCLG bulk EPC download (requires registration). |
| `_epc_staging` | Empty staging table. Artifact from previous work. | N/A |

### Data Gaps (Not Code Bugs)
- **Whitby/North Yorkshire:** E06000065 missing VOA rent data (new unitary authority since April 2023; VOA still uses old Scarborough LAD code)
- **Scotland/Wales:** No postcode-level data (England-only postcode table in core_postcodes)
- **LS1 Terraced:** No "Last 12m" data (no recent terraced sales in Leeds city centre)
- **Land Registry new-build flag:** Unreliable for house-to-flat conversions. Solicitors often mark conversions as "not new build" (old_new = 'N'). A caveat note is displayed on the new_build_proportion metric.
- **Guildford:** "Guilford" typo in `core_place_names` data (data fix, not code bug)

### Parent Comparisons Not Yet Implemented (Spatial Metrics)
These metrics return `parent_value: null` because computing them across thousands of parent-region LSOAs is too expensive at query time:
- `nearest_station`, `nearest_park`, `parks_1km`, `green_cover`, `sports_recreation`
- Fix would require pre-computed per-LSOA aggregate tables (similar pattern to `core_nhs_lsoa`)

---

## 12. Work Queue

### High Priority
- [ ] **EPC full re-ingest** — Download domestic-csv.zip, load core_epc_domestic, run transactions_epc.py for ALL years, absorb into master. This fixes the price-per-sqft chart data gap.

### Medium Priority
- [ ] **INSPIRE Index Polygons** — 318 LA zips in ~/Downloads/inspire_polygons/ but 286 are 0 bytes (download failure). Need re-download from Land Registry. Architecture: separate `core_inspire_parcels` table for address-level property search.
- [ ] **Census Extra LSOA CSVs** — `_ingest_extra()` in census.py is ready; needs LSOA-level CSVs from ONS/Nomis: TS037 (health), TS045 (car), TS066 (economic), TS067 (qualifications), TS004 (born abroad). Data already in DB from migration 007 — only needed for future ETL re-runs.
- [ ] **Noise data ingest** — core_noise is empty. Need DEFRA strategic noise map data.
- [ ] **Spatial parent comparisons** — Pre-compute per-LSOA aggregates for nearest_station, green_cover, parks_1km, sports_recreation, nearest_park to enable parent comparisons.

### Low Priority
- [ ] Guildford → "Guilford" typo fix in core_place_names data
- [ ] LLC (Local Land Charges) — 137 zips in ~/Downloads/llc/ — parked
- [ ] Census TS027 (national identity), TS031 (religion) — low priority

### Parked
- INSPIRE polygons — user said "keep in queue, we'll get back to it"
- LLC data — deferred

---

## 13. Inviolable Rules

These rules were established across 10 sessions and must NEVER be violated:

1. **Session key is the ONLY input** to all API endpoints. No hardcoded values anywhere.
2. **PRICE_TYPES = ('D','S','T','F')** — always exclude 'O' (Other/commercial) in ALL price queries.
3. **`habitable_rooms` ≠ bedrooms** — always label as "N bed (est.)" with footnote. Never "N bed".
4. **No hardcoded values** — use constants from `backend/app/constants.py` and `etl/constants.py`.
5. **TABLE_NAMES dict** — never write table name strings inline. Always import from constants.
6. **Legacy modules stay in etl/legacy/** — never delete them, they serve as reference.
7. **Source modules must not call each other** — use depends_on in METADATA.
8. **Derived modules never download files** — they only query existing core_* tables.
9. **HAVING COUNT(*) >= 3** or similar suppression for aggregated tables (privacy/data quality).
10. **Tab services never access the session directly** — they receive unpacked params from area.py.
11. **Session fields are additive only** — never rename or remove. Add new ones safely with sess.get().
12. **GMP_LAD_CODES** — 10 Greater Manchester Police LADs have crime data gaps in the national bulk file; handled separately via Police.uk API.
13. **EPC_COLOURS and PROPERTY_TYPE_COLOURS** must stay in sync between `constants.py` and `MapView.tsx`.

---

## 14. Session History

### Session 1 — Baseline Build
Built the entire portal from scratch: FastAPI + React + PostgreSQL + Redis. 5 tabs, 42+ metrics, persona engine, ward boundary map. Session key architecture established.

### Session 2 — Bug Fixes + ETL Consolidation
ETL unified into pipeline.py (29 sources + 4 derived). 38 legacy scripts moved. Shared constants. County LSOA expansion optimized (4s → 111ms). 326/337 browser tests passing.

### Session 3 — Charts, EPC/Bedrooms, Headline Metrics
DistrictPriceHistoryChart with 4 toggle pills. EPC/bedrooms logic (habitable_rooms - 1). Headline metrics from raw PERCENTILE_CONT (not avg-of-averages). LSOA context blurb.

### Session 4 — Phase 13 Step 1: Master Table Expansion
Migration 004: added district, county, ppd_category columns. Created land_registry_full.py for full historical ingest.

### Sessions 5-6 — Phase 13 Steps 1-3 Complete
Loaded 28.9M rows from pp-complete.csv. Absorbed 1.5M EPC matches. Added 12 lsoa_month_* columns. Rewrote all price queries to use master table. Dropped 5 old tables. Performance optimized (Manchester: 117s → <10s).

### Session 7 — E2E Testing + Performance
Deep E2E test: 890/891 pass. 4 performance fixes (UK median query 50s→7s). Frontend production build clean.

### Session 8 — Playwright Tests + Staleness Cleanup
123/123 Playwright browser tests. Port updates. 5 documentation files cleaned.

### Session 9 — Census Consolidation + Stale ETL Cleanup
5 census tables → 1 wide table (core_census_lsoa). Stale ETL modules moved to legacy/. Pipeline dry-run: 31 sources, all clean.

### Session 10 — Exhaustive Audit
99+ files read line-by-line. 2 bugs found and fixed (census.py missing _ingest_extra, cycling_ptal.py writing to dropped column). All tests passing.

### Session 11 (current) — Parent Comparisons + Transaction Table
Added /LSOA suffix to transaction volume. Built paginated transaction table endpoint + frontend component. Added parent comparisons to: freehold_leasehold, new_build_proportion, amenities_15min, crime_trend, noise, nhs_facilities. Fixed price-per-sqft chart combined average lines. Added new build trend chart. Added new build caveat note. Identified EPC data gap (floor_area_sqm only covers 2024-2025).

---

## Appendix: Important File Locations

| What | Path |
|------|------|
| Backend entry point | `backend/app/main.py` |
| Backend config | `backend/app/config.py` |
| Shared constants (backend) | `backend/app/constants.py` |
| Shared constants (ETL) | `etl/constants.py` |
| Session contract | `backend/SESSION_CONTRACT.md` |
| ETL orchestrator | `etl/pipeline.py` |
| Data source docs | `etl/DATA_SOURCES.md` |
| Pipeline docs | `etl/PIPELINE.md` |
| Work queue | `QUEUE.md` |
| Session notes | `sessions/session1-8.txt`, `sessions/session9.txt`, `sessions/session10.txt` |
| Frontend API client | `frontend/src/api/client.ts` |
| Metric card component | `frontend/src/components/MetricCard.tsx` |
| Persona engine | `frontend/src/utils/personas.ts` |
| Tab config + formatValue | `frontend/src/utils/tabs.ts` |
| Playwright tests | `test_playwright_comprehensive.py` (123/123) |
| API E2E tests | `/tmp/deep_e2e_test.py` (890/891) |
| Nginx production config | `frontend/nginx.conf` |
| SQL migrations | `etl/migrations/` |
| Legacy ETL scripts | `etl/legacy/` |
| Data files | `etl/data/` |
