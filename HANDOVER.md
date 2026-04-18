# PropertyPulse — Complete Handover Document

**Date:** 2026-04-17 (session 40)
**Branch:** `main`
**Status:** Production-ready for England + Wales. ALL review phases complete (Phases 1–5). AWS deployed (EC2 t4g.small, eu-west-2). 75 Google AI Studio review items across 5 rounds — all addressed. Live at https://paintedstock.com. Public review repo: https://github.com/machobowa17/PropertyPulse-review.

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
12. [Google AI Studio Review Summary](#12-google-ai-studio-review-summary)
13. [Work Queue](#13-work-queue)
14. [Inviolable Rules](#14-inviolable-rules)
15. [Session History](#15-session-history)

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
| Database | PostgreSQL 16 + PostGIS | ~30+ GB |
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
                           flood_lsoa.py, spatial_lsoa_stats.py, etc.
  legacy/                — Superseded modules (kept for reference, NOT used)
  migrations/            — Numbered SQL migration files (001-007+)
  data/                  — Local data files (CSVs, ZIPs, GeoJSON, etc.)
  DATA_SOURCES.md        — Every data source with URL, license, table, expected rows
  PIPELINE.md            — Pipeline architecture, execution order, module interface

frontend/
  src/
    pages/
      Home.tsx           — Dark cinematic landing page
      Results.tsx        — 2-line re-export of ResultsPage
      ResultsPage.tsx    — Thin layout shell: Provider + sub-components
      Attribution.tsx    — Data sources and licenses
      SavedAreas.tsx     — Saved area collections
    context/
      ResultsContext.tsx — Provider + useResults() hook (ALL shared state + queries)
    hooks/
      useIsDesktop.ts    — Media query hook
      useResultsMap.ts   — All map state, refs, callbacks, scroll-follow
    components/
      results/
        ResultsHeader.tsx    — Sticky nav header
        ResultsHero.tsx      — Area banner + LsoaContextBlurb
        ResultsMapPanel.tsx  — ResultsMobileMap + ResultsDesktopMap exports
        ResultsMetricsPanel.tsx — Metrics grid + supplemental tools
      MetricCard.tsx     — THE core component — renders any metric with expanded details
      MapView.tsx        — MapLibre GL map with POIs, boundaries, choropleths
      MapLayerControl.tsx — Toggle map layers
      PersonaSelector.tsx — Persona dropdown
      TransactionTable.tsx — Paginated, sortable transaction table
      CommuteEstimator.tsx — Commute time estimator
      ComparableAreas.tsx — Similar LADs panel
      ErrorBoundary.tsx  — Wraps ResultsPage in App.tsx
      MortgageCalculator.tsx, RentalYieldCalculator.tsx
      AirQualityChart.tsx, PersonaScoreCard.tsx, etc.
    api/client.ts        — All fetch functions + TypeScript interfaces
    types/index.ts       — ResolveResponse, Metric, AreaResponse, TabName, PersonaId
    utils/
      tabs.ts            — TABS config, formatValue(value, unit), METRIC_ICONS
      personas.ts        — 6 personas, getTakeaway() engine (60 metric branches, full registry coverage)
      personalization.ts — PERSONA_METRIC_WEIGHTS (45 entries), METRIC_TAB, buildPersonaFitSummary()
      resultsConstants.ts — MAP_LAYER_DEFAULTS, CHOROPLETH_LAYERS, etc.
      tabExplainers.ts   — TAB_EXPLAINERS per tab
      sectionSummary.ts  — buildSectionSummary() for metrics panel chip

docker/
  api/Dockerfile         — Backend API Docker image
  frontend/Dockerfile    — Frontend nginx Docker image

deploy/                  — Deployment scripts for EC2

sql/
  001_schema.sql         — Original schema (historical; some tables since dropped)
  002_remaining_tables.sql
  003_transactions.sql

sessions/                — Session notes (sessions 1-10)
QUEUE.md                 — Master work queue (single source of truth)
HANDOVER.md              — This file — cold reader entry point
test_brutal.py           — 447-test brutal stress suite
test_playwright_comprehensive.py — 123 Playwright browser tests
test_metric_refactor.py  — 21 metric refactor tests
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

### Docker Compose (production)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### URLs
- **Local dev:** http://localhost:5173 (frontend), http://localhost:8000/api/v1/ (API)
- **Production:** https://paintedstock.com (EC2 t4g.small, eu-west-2)
- Health check: `/api/v1/health`

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
**Size:** ~30+ GB (SD card at `/Volumes/PropertyPulse/var-16`)
**User:** `postgres` (no password, local socket auth)

### Key Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `core_property_transactions` | 30.4M | **THE master table** — Land Registry PPD + EPC columns + 12 lsoa_month_* aggregates |
| `core_postcodes` | 1.75M | ONSPD postcode directory (E+W+S, lat/lon/lsoa/ward/lad/county) |
| `core_crime_lsoa` | 5.96M | Monthly crime by LSOA and type (E+W) |
| `core_lsoa_boundaries` | 33,755 | LSOA polygons (geometry + lad_code) |
| `core_census_lsoa` | 33,755 | Consolidated wide census table (~30 columns) |
| `core_schools` | ~28K | Schools with Ofsted ratings + KS2/KS4 |
| `core_osm_amenities` | ~200K | POIs (cafes, parks, pubs, etc.) |
| `core_imd_lsoa` | ~33K | Index of Multiple Deprivation (7 domains) |
| `core_hpi_lad` | ~120K | House Price Index by LAD |
| `core_epc_lsoa` | 33,755 | Pre-aggregated EPC distribution |
| `core_nhs_lsoa` | ~33K | Pre-computed NHS count within 2km per LSOA |
| `core_noise` | 1.43M | DEFRA strategic noise map (road/rail/air dB per LSOA) |
| `core_inspire_parcels` | 24,255,962 | OS INSPIRE land parcel polygons (318 authorities) |
| `core_llc_charges` | 7,720,311 | Local Land Charges (141 authorities) |
| `core_flood_zones` | 3,536,992 | EA flood zones (FZ2 82.6%, FZ3 17.4%) |
| `core_flood_lsoa` | 33,755 | Per-LSOA flood zone exposure (in_zone_2, in_zone_3) — derived from core_flood_zones |

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
- core_price_sqm_lsoa, core_price_sqm_lad (dropped — not queried by any endpoint)
- **Note:** `core_price_sqm_lsoa_yearly` is NOT dropped — actively queried by `/price-history` for historical PPSF chart enrichment (3M rows, UCL data)
- core_census_demographics_lsoa, core_census_housing_lsoa, core_census_hh_size_lsoa, core_census_commute_lsoa, core_census_extra_lsoa (consolidated into core_census_lsoa)

### Dropped Tables (no longer needed)
- `core_epc_domestic` — was dropped after EPC absorption into master table. Re-download from MHCLG needed for full historical backfill (see Known Issues). GDrive backup: `gdrive:PropertyPulse/core_epc_domestic.dump`.

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
- **Results.tsx** — 2-line re-export of ResultsPage (session 28 decomp)
- **ResultsPage.tsx** — Thin layout shell: wraps with ResultsProvider, composes sub-components
- **Attribution.tsx** — 30 data sources with licenses
- **SavedAreas.tsx** — Saved area collections

### Architecture: Results Decomposition (session 28)
Results page uses React Context pattern:
- `context/ResultsContext.tsx` — Provider + `useResults()` hook. All shared state, all 9 useQuery calls.
- `hooks/useIsDesktop.ts` — Media query hook
- `hooks/useResultsMap.ts` — ALL map state, refs, callbacks, scroll-follow effect
- `components/results/ResultsHeader.tsx` — Sticky nav header
- `components/results/ResultsHero.tsx` — Area banner + LsoaContextBlurb
- `components/results/ResultsMapPanel.tsx` — `ResultsMobileMap` + `ResultsDesktopMap` exports
- `components/results/ResultsMetricsPanel.tsx` — Metrics grid + all supplemental tools

### Key Components
- **MetricCard.tsx** — THE core renderer. Takes a metric + persona, renders value, parent comparison, colour-coded takeaway, and expandable detail panel (charts, tables, lists, gauges).
- **MapView.tsx** — MapLibre GL map with Supercluster POI clustering, boundary outlines, choropleth heatmaps, isochrone rings, sold price popups
- **SearchBox.tsx** — Debounced typeahead with 7-stage suggestion ranking
- **TransactionTable.tsx** — Paginated, sortable, filterable transaction table
- **PersonaSelector.tsx** — Dropdown for 6 personas

### Metric Registry (session 25-26)
`backend/app/metric_registry.py` — source of truth for 62 metric metadata entries (short_label, value_type, section_id). `helpers.py` `build_metric_contract()` + `enrich_metrics()` post-process at router level. TypeScript types: MetricRegistryMeta, MetricHeadline, MetricComparison, MetricTrend, MetricCapsule.

### Data Flow
```
User search → resolveSearch(q) → sessionKey
  → fetchAreaTab(sessionKey, "Property & Market") → metrics[]
  → fetchPriceHistory(sessionKey) → charts
  → fetchBoundary(sessionKey) → map outline
  → fetchMapPois(sessionKey, tab) → POI markers
  → Pre-fetch remaining 4 tabs in background
All state flows through ResultsContext → sub-components via useResults()
```

### Persona Engine
`utils/personas.ts` — `getTakeaway()` covers 60 metric ID branches (full registry coverage). Fixed: `ptal` → `ptal_score` bug (was silently failing for all PTAL metrics).
`utils/personalization.ts` — `PERSONA_METRIC_WEIGHTS` (45 metric entries × 6 personas), `METRIC_TAB` mapping, `buildPersonaFitSummary()`, `rankSectionsForPersona()`. Produces 0-100 fit score shown in PersonaScoreCard.

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

### AWS Deployment
- **Instance:** EC2 t4g.small (ARM64 Graviton, 2 vCPU, 2 GB RAM), eu-west-2
- **Storage:** 80 GB gp3 EBS
- **IP:** Elastic IP 16.60.67.248
- **Domain:** paintedstock.com (Cloudflare DNS)
- **TLS:** Let's Encrypt (auto-renew via certbot)
- **Stack:** Docker Compose — 4 containers: API (FastAPI/Uvicorn), frontend (nginx), Redis, PostgreSQL (PostGIS)
- **Deployment:** Manual rsync + `docker compose up --build -d` (CI/CD pending)
- Full spec: `memory/deployment.md`

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

### Execution Order (31+ modules)
```
Foundation (5): postcodes → boundaries → lad_county_lookup → place_names → place_boundaries
Monthly (5): land_registry_full → hpi → crime → schools → epc_domestic
Quarterly (5): epc_lsoa → osm_amenities → ev_chargers → governance → mobile_coverage
Annual (12): voa_rents → ashe → broadband → air_quality → flood → green_space → nhs →
             naptan → council_tax → water → cycling_ptal → place_lsoa_mapping → nhs_lsoa
One-time (2): census → imd
Derived (2): price_by_bedrooms
One-time large ingests (complete): inspire_parcels → llc → flood (GeoPackage)
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
- `transactions_epc.py` — old Jaccard address-match → intermediate `core_transactions_epc` table (now dropped). Superseded by Phase 2 of new `epc_domestic.py`.
- `absorb_epc.py` — old step to copy `core_transactions_epc` → master. Superseded by Phase 2 of new `epc_domestic.py`.
- `price_sqm.py` — UCL price-per-sqm data. Target tables dropped.
- `import_epc.py` — older EPC import

---

## 10. Testing

### Playwright Browser Tests
- **Main suite:** `test_playwright_comprehensive.py` — **117/123 passing** (4 pre-existing: 1 Scotland, 1 chart toggle, 2 Governance timing; 2 warnings — 0 regressions)
  - 10 sections: all 5 tabs × 3 search types, charts, map, null handling, tab switching, responsive, errors, navigation
- **Metric refactor suite:** `test_metric_refactor.py` — **21/21 passing**
- **Brutal test suite:** `test_brutal.py` — **447/447 passing** (13 sections: adversarial inputs, math correctness, boundary integrity, ethnicity accuracy, choropleth layers, report PDF, cross-search consistency, 5×5 tab×search matrix, Playwright UI)
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

### EPC Floor Area Coverage — Pending Full Run

**Impact:** `price_per_sqft` chart lines only show data for 2024-2025 (the ~4.2M rows matched in sessions 17-18). Historical years show null.

**Status:** `epc_domestic.py` has been fully rewritten (session 29) — a single pipeline run now handles everything end-to-end.

**Fix (one command):**
1. Download the MHCLG domestic EPC bulk ZIP (~4-5 GB) from https://epc.opendatacommunities.org/downloads/domestic (requires free registration)
2. Place at `etl/data/domestic-csv.zip` (or set `EPC_ZIP_PATH` env var)
3. Run: `python3 pipeline.py --source epc_domestic`

The pipeline module (`etl/sources/epc_domestic.py`) handles all 4 phases automatically:
- Load 9-col `core_epc_domestic` (~23M rows)
- SQL TRANSLATE address-match → UPDATE `core_property_transactions` (floor_area_sqm, habitable_rooms, epc_rating, price_per_sqm, price_per_sqft)
- Recompute `lsoa_month_avg_ppsm` + `lsoa_month_avg_ppsft` aggregates
- Verify coverage by year + DROP `core_epc_domestic`

### Dropped/Missing Tables

| Table | Issue | Data Source |
|-------|-------|-------------|
| `core_epc_domestic` | Does not exist (dropped after absorption). Needed for full historical EPC matching (price_per_sqft pre-2024). | MHCLG bulk EPC download (requires registration). `epc_domestic.py` handles full 4-phase re-ingest. |

### Tables Fully Ingested (not in original handover)
- `core_noise` — 1,430,534 rows ✓ (DEFRA 367/367 tiles, session 22)
- `core_inspire_parcels` — 24,255,962 rows ✓ (318 authorities, session 25-26)
- `core_llc_charges` — 7,720,311 rows ✓ (141 authorities, session 25-26)
- `core_flood_zones` — 3,536,992 rows ✓ (EA GeoPackage, FZ2/FZ3 bug fixed, session 27)

### Data Gaps (Not Code Bugs)
- **Whitby/North Yorkshire:** E06000065 missing VOA rent data (new unitary authority since April 2023; VOA still uses old Scarborough LAD code). Also not in `core_place_boundaries_union` — Playwright tests skip Whitby null section.
- **Scotland/Wales:** No postcode-level data (England-only postcode table in core_postcodes). Wales transactions + crime are ingested but no census/EPC/schools data.
- **LS1 Terraced:** No "Last 12m" data (no recent terraced sales in Leeds city centre)
- **Land Registry new-build flag:** Unreliable for house-to-flat conversions. Solicitors often mark conversions as "not new build" (old_new = 'N'). A caveat note is displayed on the new_build_proportion metric.
- **financial_health / S114 metric:** Registry entry exists but no tab service wired. Needs provenance-backed data source.
- **Commute estimator:** Returns 501 Not Implemented. No local data source — would need TfL/Google Maps APIs.
- Full data gap inventory (28 items, 8 categories): `memory/data_gaps.md`

### Spatial Parent Comparisons — COMPLETE
Previously `nearest_station`, `nearest_park`, `parks_1km`, `green_cover`, `sports_recreation` returned `parent_value: null`. Now pre-computed via `etl/derived/spatial_lsoa_stats.py` → `core_lsoa_green_space` + `core_lsoa_transport` tables. All 5 spatial metrics have parent comparisons.

---

## 12. Google AI Studio Review Summary

The codebase underwent 5 rounds of professional code review via Google AI Studio. All 75 actionable items addressed.

| Round | Session | Items | Fixed | Already done | Deferred | Not fixing |
|-------|---------|-------|-------|-------------|----------|-----------|
| Round 1 (G1-G11) | 33 | 11 | 11 | 0 | 0 | 0 |
| Round 2 (C1-C4) | 34 | 4 | 4 | 0 | 0 | 0 |
| Round 3 (H1-H16, B1-B2) | 35 | 18 | 18 | 0 | 0 | 0 |
| Round 4 (L1-L5) | 38 | 34 | 5 | 29 | 0 | 0 |
| Round 5 (G5-1 to G5-8) | 39-40 | 31 | 8 | 22 | 0 | 5 |

**5 "not fixing" items (justified):**
1. PostGIS `geom::geography` index — ST_DWithin uses GiST for bounding box pre-filter
2. Pagination OFFSET — max ~1000 rows per query
3. Overpass API rate limits — ETL-only, already ingested
4. EPC backfill index bloat — one-time script, already run
5. Query consolidation (5 queries) — different column sets, not a bug

---

## 13. Work Queue

**See `QUEUE.md` — the single source of truth for all task tracking.**

Current state: Phases 1–5 ALL COMPLETE. AWS deployed. 75 Google review items across 5 rounds addressed. Remaining: CI/CD automation (#19), isochrone school catchments (R15).

---

## 14. Inviolable Rules

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

## 15. Session History

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

### Session 11 — Parent Comparisons + Transaction Table
Added /LSOA suffix to transaction volume. Built paginated transaction table endpoint + frontend component. Added parent comparisons to: freehold_leasehold, new_build_proportion, amenities_15min, crime_trend, noise, nhs_facilities. Identified EPC data gap (floor_area_sqm only covers 2024-2025).

### Sessions 12-18 — EPC Re-ingest + Backfill
Full re-ingest of 29.2M EPC certificates. Jaccard address-match of all 28.9M transactions. absorb_epc.py copied floor_area_sqm/habitable_rooms/epc_rating to master table. core_epc_domestic subsequently dropped to free disk (backed up to GDrive). lsoa_month_avg_ppsm/ppsft recomputed.

### Sessions 19-22 — Spatial Parent Comparisons + Noise + Census Extra
All spatial metrics now have parent comparisons via pre-computed tables (core_lsoa_green_space, core_lsoa_transport). Noise data ingested (1,427,115 rows). Census extra TS topics ingested into core_census_lsoa.

### Sessions 23-24 — AWS Spec + DB Migration to SD Card
AWS deployment spec finalized (memory/deployment.md). Postgres migrated to SD card. METRICS.md rewritten from code truth (60 metrics, 48 with parent).

### Sessions 25-26 — INSPIRE/LLC/Flood Ingests + Metric Registry Refactor
INSPIRE parcels (24,255,962 rows, 318 authorities), LLC (7,720,311 rows, 141 authorities), Flood GeoPackage (3,536,992 rows) all ingested. Metric registry refactor complete (S1-S2-S7-S5): metric_registry.py, build_metric_contract(), enrich_metrics(), TypeScript nested types.

### Session 27 — Flood Bug Fix + Backup Start
Flood zone bug found+fixed (was labelling all FZ3 due to wrong column read). Re-ingested with correct FZ2/FZ3 split. 3 rclone backup processes started (INSPIRE/LLC/Flood raw to GDrive).

### Sessions 31-32 — Phase 2 Review Fixes ALL COMPLETE
22 items across security, backend, infra, and frontend. Key changes:
- **Security (R16-R20):** Nginx CSP `unsafe-inline` removed; `secrets.compare_digest` for API key; Uvicorn `--proxy-headers`; Redis AOF + localhost bind; ReportLab XML escape.
- **Backend (R7, R9, R12, R13, R4, R21):** FastAPI CSP middleware removed; choropleth `null` sentinel; spatial thinning (PARTITION BY lsoa_code); quantile dedup; `core_place_boundaries_union` pre-computed; all 27 ETL sources converted to blue/green swap (new `etl/utils.py`).
- **Infra (R22, R24):** postgresql.conf tuning documented in `memory/deployment.md`; Sentry APM in backend + frontend (conditional on DSN).
- **Frontend (R11, R10, R25, R2, R14, R3, R8, R1):** ResizeObserver + map.resize() for mobile grid; sold price marker rebuild guard; Vite manualChunks (vendor/map/charts); choropleth URL → MapLibre off-thread parse; `SessionExpiredError` + 410 silent re-resolve; `React.lazy()` for 13 chart components; Zod v4 validation for /area response (`frontend/src/schemas/area.ts`); ResultsContext split into `ResultsDataContext` + `ResultsUIContext` (backward compat `useResults()` kept).
- **tsc -b 0 errors, vite build clean** throughout.

### Session 30 — Personas.ts + Personalization.ts Overhaul (S4) Complete
Fixed active bug: `ptal` → `ptal_score` (PTAL takeaways were silently falling through to default fallback for every search). `getTakeaway()` expanded from 42 → 60 metric ID branches — full registry coverage including: connectivity_index, stations_in_area, wfh, noise, green_cover, green_spaces, parks_1km, sports_recreation, median_earnings, good_health, economically_active, degree_educated, no_car, born_abroad, household_size, ethnicity, demographics_overview. `PERSONA_METRIC_WEIGHTS` expanded from 23 → 45 entries. `METRIC_TAB` cleaned: removed phantom `ptal`, added stations_in_area, connectivity_index, household_size, ethnicity, wfh. tsc -b 0 errors.

### Session 33 — Phase 2.5 AI Studio Review Fixes (G1-G11) Complete
11 fixes from Google AI Studio code review, all verified. Key changes:
- **G1:** Crime trend 0-is-falsy — `is not None` checks in `tab_environment.py`
- **G2:** LsoaContextBlurb missing `lad` type — added `|| type === 'lad'` in `ResultsHero.tsx`
- **G3:** flood_lsoa ETL missing — created `etl/derived/flood_lsoa.py` (ST_Intersects derivation)
- **G4:** Schools ST_Within perf — removed spatial join from 4 parent queries, use `s.lad_code` directly
- **G5:** Suggest rate limit lockout — `@limiter.exempt` on suggest endpoint (superseded by C3 in session 34: replaced with `300/minute`)
- **G6:** "London" → wrong entity — `'greater ' || :q` match in geo_resolver + suggest county query
- **G7:** Map POI flash-blank — `placeholderData: (prev) => prev` on mapPois useQuery
- **G8:** Mobile map auto-open — removed `setShowMap(true)` from `handleMetricMapFocus`
- **G9:** localStorage cross-tab — `storage` event listener in `ResultsContext.tsx`
- **G10:** MetricCard scroll-into-view — `transitionend` + `scrollIntoView` on mobile expand
- **G11:** Comparable null imputation — `None` instead of `0.0` for missing dims; skip in `_distance()`
- Deferred: G12 (DecisionMode wiring — done in session 34 as C1)
- Public GitHub repo created: `machobowa17/PropertyPulse-review`
- Codebase uploaded to GDrive: `gdrive:PropertyPulse/codebase_review_20260416/` (344 files)
- **Testing:** tsc -b 0 errors, vite build clean, 21/21 metric + 117/121 comprehensive (1 pre-existing Scotland, 3 timing/rate-limit)

### Session 35 — H14-H16 + Brutal Test Suite + 13 AI Studio Hardening Fixes (H1-H13) Complete

**Phase 2.8:** 3 deferred AI Studio items resolved + 2 bugs found by brutal test suite:
- **H14:** Stagger tab prefetch — 4 tabs fired simultaneously on page load, potential request burst on t4g.small. Staggered: tab 0 at 0ms, tab 1 at 2s, tab 2 at 4s, tab 3 at 6s. Cleanup function clears timers.
- **H15:** `ST_SimplifyPreserveTopology` for boundaries — LAD (0.0002), place (0.0003), county (0.0005). Also choropleth in `area_map.py`. `ST_Simplify` produced invalid geometry on 100% of counties tested — `PreserveTopology` verified correct on all.
- **H16:** Ethnicity LSOA→ward derivation — place searches now derive distinct ward_codes from session's LSOA set via `core_postcodes`, avoiding entire-LAD averaging. Verified: Brixton ethnicity (50.59%) differs from Lambeth LAD (55.04%).
- **B1:** Null bytes in `/resolve` caused 500 — input sanitisation strips `\x00` + validates length post-strip.
- **B2:** Place boundary 500 when `core_place_boundaries_union` table missing — try/except + `db.rollback()` falls through to live `ST_Union`.
- **Brutal test suite:** `test_brutal.py` — 13 sections, 447 tests covering adversarial inputs, math correctness, boundary integrity, ethnicity accuracy, choropleth layers, report PDF, cross-search consistency, 5×5 tab×search matrix, Playwright UI. All 447 pass.
- **Testing:** tsc -b 0 errors, vite build clean, 21/21 metric refactor, 117/123 comprehensive (0 regressions), 447/447 brutal.

**Phase 2.7 (earlier in session 35):**
13 fixes from third-round AI Studio review (31+10 items triaged; 16 already fixed in sessions 31-34, 3 deferred). All verified:
- **H1:** PDF `_build_pdf()` blocks ASGI loop — wrapped with `await asyncio.to_thread()` in `report.py`
- **H2:** DB pool exhaustion (pool_size=20 × 4 workers > max_connections=100) — reduced to `pool_size=5, max_overflow=5` in `database.py`
- **H3:** MSOA crime rate population mismatch — `used_msoa_fallback` flag → query MSOA-level population instead of single-LSOA (prevents 500% inflation) in `tab_environment.py`
- **H4:** HPI parent drops lagging LADs — `DISTINCT ON (lad_code) ORDER BY date DESC` in `tab_property.py`
- **H5:** Council tax parent unweighted average — population-weighted CTE in `tab_governance.py`
- **H6:** GZipMiddleware burns CPU — removed from `main.py` (Nginx handles compression)
- **H7:** Rate limiter per-process in-memory — `storage_uri=settings.REDIS_URL` in `rate_limit.py`
- **H8:** `set()` created inside loop — moved outside in `comparable_areas.py`
- **H9:** localStorage.setItem crash (Safari private) — try/catch in `SearchBox.tsx`
- **H10:** localStorage.setItem crash (savedAreas) — try/catch in `savedAreas.ts`
- **H11:** `getLeaves(Infinity)` DOM freeze — capped at 30 in `MapView.tsx`
- **H12:** Collapsed content in keyboard focus order — `visibility: hidden` on `CollapsibleSection.tsx`, `MetricCard.tsx`, `ResultsMapPanel.tsx`
- **H13:** DHE-RSA cipher Logjam vulnerability — removed from `nginx-ssl.conf`
- **Testing:** tsc -b 0 errors, vite build clean, 21/21 metric refactor, 117/123 comprehensive (0 regressions; 4 pre-existing: 1 Scotland, 1 chart toggle, 2 Governance timing).

### Session 34 — 4 AI Studio Critical Fixes (C1-C4) Complete
4 critical flaws from second-round AI Studio review, all fixed and tested:
- **C1:** DecisionMode placebo toggle — added `DECISION_MODE_MULTIPLIERS` matrix in `personalization.ts`; threaded `decisionMode` through all scoring functions (`buildSignal`, `collectPersonaSignals`, `buildPersonaFitSummary`, `rankSectionsForPersona`); updated `PersonaScoreCard` + `ResultsMetricsPanel` call sites. Buy/Rent/Invest now meaningfully changes persona scores.
- **C2:** Postcode district substring truncation — replaced Python `dist_len` heuristic with Postgres regex `SUBSTRING(postcode_compact FROM '^[A-Z]{1,2}[0-9][A-Z]?')` in `resolve.py` suggest endpoint. Verified: CR5→CR5 ✓, SW1→SW1A/SW1E ✓, E1→E1/E1W ✓.
- **C3:** Suggest endpoint DoS vector — replaced `@limiter.exempt` with `@limiter.limit("300/minute")` + `request: Request` param. 5x default limit for typeahead UX, still protected against abuse.
- **C4:** ETL `INCLUDING ALL` bottleneck — created `create_staging_table()` (UNLOGGED, no indexes) + `recreate_indexes()` (from pg_indexes) in `etl/utils.py`. Converted 5 large-table modules: land_registry_full (30M), inspire_parcels (24M), llc (7.7M), crime (6M), flood (3.5M).
- **Testing:** tsc -b 0 errors, vite build clean, 21/21 metric refactor, 114/123 comprehensive (0 regressions; 4 pre-existing: 1 Scotland, 1 chart toggle, 2 Governance timing).

### Session 28 — Results.tsx Decomposition (S6) Complete
Full decomposition of 721-line Results.tsx into React Context architecture. 8 new files. Zero regressions: 122/123 comprehensive + 21/21 metric refactor. tsc -b clean, vite build clean. Visual diff identical (file sizes within 0.2% of baseline).

### Session 29 — epc_domestic.py Rewrite (S3) Complete
Full rewrite of `etl/sources/epc_domestic.py`. Old approach: 93-col load + Python Jaccard loop + separate `absorb_epc.py` + manual aggregate rebuild. New approach: 4-phase `run()` — (1) 9-col COPY load, (2) SQL TRANSLATE match → direct UPDATE master, (3) lsoa_month ppsf aggregate recompute, (4) verify + DROP. `pipeline.py` entry updated. Single command: `python3 pipeline.py --source epc_domestic`.

### Sessions 36-37 — Data Gap Audit + Fixes (D1-D7) Complete
28 data gaps catalogued across 8 categories. 7 fixed, 2 deferred:
- **D1:** Metro county lookup — CSV-based `metro_county_lookup.csv` for all 36 E08 metro districts across 6 metro counties. Uses truncate-and-reload (not blue-green swap) to preserve matview dependencies.
- **D2:** `core_place_boundaries_union` — ran `place_lsoa_mapping` derivation (9,565 pre-computed unions)
- **D3:** Dead persona weights — removed 3 non-existent metrics from frontend
- **D4:** `core_price_by_bedrooms_lad` — ran derivation (144,906 rows)
- **D5:** Census religion — wired `core_census_religion_ward` into `tab_community.py` as new metric
- **D6:** GMP crime data verified present across all metro districts
- **D7:** EPC backfill confirmed complete (was incorrectly listed as blocked)

### Sessions 37-38 — AWS Deployment (Phase 3) Complete
EC2 t4g.small (eu-west-2), 80 GB gp3 EBS, Elastic IP 16.60.67.248. Full `pg_dump`/`pg_restore` (18 GB). Docker Compose with API + frontend/nginx + Redis + PostgreSQL. Let's Encrypt TLS via Cloudflare DNS (`paintedstock.com`). All data verified — exact row counts match local.

### Session 38 — Google AI Studio Live Review (Phase 4) Complete
Google's 4th-round review of the live site. ~34 items triaged: 29 already fixed, 5 new. Fixes: TabBar resize, mobile hover states, choropleth legend overflow, PDF blob download, sold price marker cap.

### Sessions 39-40 (latest) — Google AI Studio Review Round 5 (Phase 5) Complete
Two batches (17 + 14 items). Google acknowledged batch 1 was reviewing stale code. ~22 already fixed, 8 genuinely new — all fixed. 5 items justified as not fixing. Key changes:
- **G5-1:** MapLibre feature-state hover highlighting (`promoteId`, `setFeatureState`, tooltip) in `MapView.tsx`
- **G5-2:** IntersectionObserver scroll-follow (replaced layout-thrashing rAF) in `useResultsMap.ts`
- **G5-3:** Simpson's Paradox — population-weighted averages across 7 backend files (~45 queries). Weights: `total_population`, `total_households`, `total_workers`, `total_certs`, `total_pop`, `transaction_count`.
- **G5-4:** Schools + NHS `ST_Within` → postcode join for area-mode queries (6 queries in `tab_community.py`)
- **G5-6:** `ST_CollectionExtract` defensive wrapper around `ST_MakeValid()` in `llc.py` + `inspire_parcels.py`
- **G5-7:** Choropleth dynamic bucket detection for <5 unique quantile values
- **G5-8:** Mobile cooperative gestures (two-finger pan) via MapLibre built-in
- **Testing:** tsc -b 0 errors, vite build clean, 21/21 metric. Deployed to EC2.
- **Full triage:** `memory/google_review_5.md`

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
| Zod response schemas | `frontend/src/schemas/area.ts` |
| Results context (data) | `frontend/src/context/ResultsContext.tsx` (exports: useResults, useResultsData, useResultsUI) |
| ETL blue/green swap util | `etl/utils.py` (blue_green_swap) |
| Metric card component | `frontend/src/components/MetricCard.tsx` |
| Persona engine | `frontend/src/utils/personas.ts` |
| Tab config + formatValue | `frontend/src/utils/tabs.ts` |
| Playwright tests | `test_playwright_comprehensive.py` (117/123 — 4 pre-existing, 0 regressions) |
| Metric refactor tests | `test_metric_refactor.py` (21/21) |
| Brutal test suite | `test_brutal.py` (447/447) |
| API E2E tests | `/tmp/deep_e2e_test.py` (890/891) |
| Nginx production config | `frontend/nginx.conf` |
| Nginx SSL config | `frontend/nginx-ssl.conf` |
| Docker Compose (dev) | `docker-compose.yml` |
| Docker Compose (prod) | `docker-compose.prod.yml` |
| Deploy scripts | `deploy/` |
| AWS deployment spec | `memory/deployment.md` |
| Google Review Round 5 triage | `memory/google_review_5.md` |
| Data gap inventory | `memory/data_gaps.md` |
| SQL migrations | `etl/migrations/` |
| Legacy ETL scripts | `etl/legacy/` |
| Data files | `etl/data/` |
| Flood LSOA derivation | `etl/derived/flood_lsoa.py` |
| Spatial LSOA stats | `etl/derived/spatial_lsoa_stats.py` |
| Rate limiter | `backend/app/rate_limit.py` |
| Public review repo | https://github.com/machobowa17/PropertyPulse-review |

### Google Drive Assets

| Item | Location |
|------|----------|
| DB dump v2 | `gdrive:PropertyPulse/ukproperty_20260413_v2.dump` |
| core_epc_domestic backup | `gdrive:PropertyPulse/core_epc_domestic.dump` (1.2 GB) |
| INSPIRE raw | `gdrive:PropertyPulse/raw_downloads/INSPIRE/` |
| LLC raw | `gdrive:PropertyPulse/raw_downloads/LLC/` |
| Flood GeoPackage | `gdrive:PropertyPulse/raw_downloads/` |
| Codebase snapshot (latest) | `gdrive:PropertyPulse/codebase_review_20260417/` (360 files) |
