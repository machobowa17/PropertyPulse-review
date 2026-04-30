# PropertyPulse — Changelog (Completed Work)

All items below are **confirmed completed** and deployed. Moved from QUEUE.md to keep the master queue clean.

Last updated: 2026-04-30 (session 70)

---

## Phase 1: Foundation (COMPLETE ✓)

All 12 tasks done. INSPIRE 24.3M, LLC 7.7M, Flood 3.5M ingested. Metric registry refactor. Results.tsx decomposition. epc_domestic.py rewrite. personas.ts 60 branches.

---

## Phase 2: Review Fixes (COMPLETE ✓)

22 items done (R1–R25, excluding R6 skip / R23 defer / R15 post-AWS). Security, backend perf, frontend perf, infra. tsc -b 0 errors, vite build clean.

---

## Phase 2.5: AI Studio Review Fixes (COMPLETE ✓)

Source: Google AI Studio code review (session 33). 11 confirmed fixes, all done. tsc -b 0, vite build clean, 21/21 metric + 117/121 comprehensive (1 pre-existing Scotland, 3 timing/rate-limit).

| # | Task | Fix |
|---|------|-----|
| G1 | Crime trend 0-is-falsy | `is not None` checks in `tab_environment.py:178-183` |
| G2 | LsoaContextBlurb missing `lad` type | Added `\|\| type === 'lad'` in `ResultsHero.tsx:29` |
| G3 | flood_lsoa ETL missing | Created `etl/derived/flood_lsoa.py` — ST_Intersects derivation |
| G4 | Schools ST_Within perf | Removed spatial join from 4 parent queries, use `s.lad_code` directly |
| G5 | Suggest rate limit lockout | Created `backend/app/rate_limit.py`, `@limiter.exempt` on suggest |
| G6 | "London" → wrong entity | `'greater ' \|\| :q` match in geo_resolver + suggest county query |
| G7 | Map POI flash-blank | `placeholderData: (prev) => prev` on mapPois useQuery |
| G8 | Mobile map auto-open | Removed `setShowMap(true)` from `handleMetricMapFocus` |
| G9 | localStorage cross-tab | `storage` event listener in `ResultsContext.tsx` |
| G10 | MetricCard scroll-into-view | `transitionend` + `scrollIntoView` on mobile expand |
| G11 | Comparable null imputation | `None` instead of `0.0` for missing dims; skip in `_distance()` |

Deferred: "Fast typer" race → Not a bug (trigram fallback handles).

---

## Phase 2.6: AI Studio Critical Fixes (COMPLETE ✓)

Source: Google AI Studio second-round review (session 34). 4 critical flaws identified and fixed.

| # | Task | Fix |
|---|------|-----|
| C1 | DecisionMode is placebo toggle — scoring ignores Buy/Rent/Invest | `DECISION_MODE_MULTIPLIERS` matrix in `personalization.ts`; threaded through `buildSignal`, `collectPersonaSignals`, `buildPersonaFitSummary`, `rankSectionsForPersona`; `PersonaScoreCard` + `ResultsMetricsPanel` updated |
| C2 | Postcode district substring truncation — Python `dist_len` gives CR51 not CR5 | Replaced with Postgres regex `SUBSTRING(postcode_compact FROM '^[A-Z]{1,2}[0-9][A-Z]?')` in `resolve.py` suggest |
| C3 | Suggest endpoint DoS vector — `@limiter.exempt` | Replaced with `@limiter.limit("300/minute")` + `request: Request` param in `resolve.py` |
| C4 | ETL `INCLUDING ALL` bottleneck — indexes during bulk insert | `create_staging_table()` + `recreate_indexes()` in `etl/utils.py`; 5 large-table modules converted (land_registry 30M, inspire 24M, llc 7.7M, crime 6M, flood 3.5M) |

---

## Phase 2.7: AI Studio Hardening Fixes (COMPLETE ✓)

Source: Google AI Studio third-round review (session 35). 13 fixes from 31+10 item review.

| # | Task | Fix |
|---|------|-----|
| H1 | PDF generation blocks ASGI event loop | `await asyncio.to_thread(_build_pdf, ...)` in `report.py` |
| H2 | DB pool exhaustion (120 > max_connections 100) | `pool_size=5, max_overflow=5` in `database.py` (40 max across 4 workers) |
| H3 | MSOA crime rate population mismatch (500% inflation) | `used_msoa_fallback` flag → MSOA-level population query in `tab_environment.py` |
| H4 | HPI parent drops lagging LADs | `DISTINCT ON (lad_code) ORDER BY date DESC` in `tab_property.py` |
| H5 | Council tax parent unweighted average | Population-weighted `SUM(band * weight) / SUM(weight)` in `tab_governance.py` |
| H6 | GZipMiddleware burns CPU (Nginx handles it) | Removed `GZipMiddleware` from `main.py` |
| H7 | Rate limiter per-process in-memory storage | `storage_uri=settings.REDIS_URL` in `rate_limit.py` |
| H8 | `set()` created inside loop | `target_set = set(target_lad_codes)` before loop in `comparable_areas.py` |
| H9 | localStorage.setItem crash (Safari private) | try/catch in `SearchBox.tsx` `writeRecentSearches()` |
| H10 | localStorage.setItem crash (savedAreas) | try/catch in `savedAreas.ts` `writeRaw()` |
| H11 | getLeaves(Infinity) DOM freeze on dense clusters | Capped at 30 in `MapView.tsx` |
| H12 | Collapsed content in keyboard focus order | `visibility: hidden` on `CollapsibleSection.tsx`, `MetricCard.tsx`, `ResultsMapPanel.tsx` |
| H13 | DHE-RSA cipher Logjam vulnerability | Removed DHE ciphers from `nginx-ssl.conf` |

---

## Phase 2.8: Final Hardening + Brutal Test Suite (COMPLETE ✓)

Source: Session 35 continuation. 3 deferred AI Studio items (H14–H16) + 2 brutal test bugs (B1–B2) fixed. Brutal test suite created (447 tests).

| # | Task | Fix |
|---|------|-----|
| H14 | Prefetch tab storm — 4 tabs fire simultaneously on page load | Staggered delays: tab 0 at 0ms, tab 1 at 2s, tab 2 at 4s, tab 3 at 6s in `ResultsContext.tsx` |
| H15 | GeoJSON payload bloat — county boundaries 300+ KB | `ST_SimplifyPreserveTopology` in `area_boundary.py` (LAD 0.0002, place 0.0003, county 0.0005) + `area_map.py` choropleth |
| H16 | Ethnicity erasure on place searches — uses entire LAD | LSOA→ward derivation via `core_postcodes` subquery in `tab_community.py` |
| B1 | Null bytes in `/resolve` cause 500 | Input sanitisation (strip `\x00`) in `resolve.py` |
| B2 | Place boundary 500 when `core_place_boundaries_union` missing | try/except + `db.rollback()` fallback in `area_boundary.py` |

Test suite: `test_brutal.py` — 13-section brutal stress test. Originally 447 assertions (session 35), now ~468 after evolution.

---

## Phase 2.9: Data Gap Fixes (COMPLETE ✓)

Source: Session 36-37 data gap audit. 28 gaps catalogued, 7 fixed, 1 deferred, 1 won't fix.

| # | Task | Fix |
|---|------|-----|
| D1 | Metro county lookup gap (5 of 6 missing) | CSV-based `metro_county_lookup.csv` in `lad_county_lookup.py` — E11 codes for all 36 E08 metro districts. Matviews rebuilt. |
| D2 | `core_place_boundaries_union` missing | Ran `place_lsoa_mapping` derivation — 9,565 pre-computed unions. |
| D3 | Dead persona weights (3 non-existent metrics) | Removed `connectivity_index`, `fifteen_min_score`, `esg_score` from personalization.ts, personas.ts, tabs.ts, resultsConstants.ts, MetricCard.tsx |
| D4 | `core_price_by_bedrooms_lad` empty (0 rows) | Ran `price_by_bedrooms` derivation — 144,906 rows from 5.3M EPC-matched transactions |
| D5 | Census religion data unused (7,638 rows) | Wired `core_census_religion_ward` into `tab_community.py`. New `religion` metric. |
| D6 | GMP crime data verified | All 36 metro districts have crime data |
| D7 | EPC backfill (price_per_sqft history) | Already complete — 5.3M matched rows |

Deferred: D8 (financial_health/S114 — needs provenance-backed data source), D9 (Commute estimator — won't fix, no local data source).

---

## Phase 3: AWS Deployment (COMPLETE ✓)

Source: Sessions 37-38. EC2 t4g.small (eu-west-2), 80 GB gp3 EBS, Elastic IP 16.60.67.248. Domain: simusimi.com (Cloudflare). All data restored and verified.

| # | Task | Notes |
|---|------|-------|
| 13 | AWS: Create account, configure eu-west-2 | Elastic IP 16.60.67.248 |
| 14 | AWS: Launch t4g.small + 80 GB gp3 EBS | ARM64 Graviton, 2 vCPU, 2 GB RAM |
| 15 | AWS: Provision Docker + docker-compose | Docker 27.x, Compose v2.29.2, 2 GB swap |
| 16 | AWS: `pg_dump` → upload → `pg_restore` on EC2 | 18 GB dump, all 30.4M transactions + indexes + MVs restored |
| 17 | AWS: Docker Compose (API + frontend/nginx + Redis + PG) | `docker-compose.ssl.yml` override |
| 18 | AWS: DNS + TLS (Let's Encrypt) | `simusimi.com`, cert expires 2026-07-16 |
| 19 | AWS: GitHub Actions CI/CD | Parked — Git-based deploy via `deploy.sh` |

---

## Phase 4: Google AI Studio Live Review Polish (COMPLETE ✓)

Source: Session 38. Google's 4th-round review. ~34 items triaged: 29 already fixed, 5 new.

| # | Task | Fix |
|---|------|-----|
| L1 | TabBar pill misaligns on window resize | Added `resize` event listener in `TabBar.tsx` |
| L2 | Sticky hover states on mobile Safari | `@media(hover:hover)` guard in `MetricCard.tsx` |
| L3 | Choropleth legend text overflow on mobile | `max-width: min(200px, calc(100% - 16px))` in `MapView.tsx` |
| L4 | PDF download opens blank tab | Replaced `<a target="_blank">` with blob-fetch `<button>` in `ResultsHero.tsx` |
| L5 | Sold price DOM markers cause mobile stutter | Capped individual markers at 150 in `MapView.tsx` |

---

## Phase 5: Google AI Studio Review Round 5 (COMPLETE ✓)

Source: Sessions 39-40. 8 genuinely new items fixed. ~22 already fixed.

| # | Task | Fix |
|---|------|-----|
| G5-1 | MapLibre hover feature-state | `promoteId`, `setFeatureState`, `fill-opacity` expression in `MapView.tsx` |
| G5-2 | IntersectionObserver scroll-follow | Replaced rAF+getBoundingClientRect with `IntersectionObserver` in `useResultsMap.ts` |
| G5-3 | Simpson's Paradox — population-weighted census averages | `SUM(weight * pct) / NULLIF(SUM(weight), 0)` across 7 files |
| G5-4 | Schools + NHS ST_Within in area-mode local queries | Replaced with postcode join in `tab_community.py` |
| G5-5 | Sold-price spatial bias | VERIFIED — already stratified via `ROW_NUMBER() PARTITION BY lsoa_code` |
| G5-6 | LLC + INSPIRE ST_CollectionExtract defensive fix | `ST_CollectionExtract(ST_MakeValid(), 3)` in `llc.py` + `inspire_parcels.py` |
| G5-7 | Choropleth quantile edge case (<5 unique values) | Dynamic bucket count in `MapView.tsx` |
| G5-8 | Mobile map touch-action | `cooperativeGestures` in MapLibre init |

---

## Phase 6: Gemini Round 6 Review Fixes (COMPLETE ✓)

Source: Session 41. 11 genuine items fixed from ~35 claims.

| # | Task | Fix |
|---|------|-----|
| G6-2A | RequestValidationError masked as 500 | `RequestValidationError` handler → 422 in `main.py` |
| G6-2C | Deprecated X-XSS-Protection header | Removed from `main.py`, `nginx.conf`, `nginx-ssl.conf` |
| G6-1B | Ward name fuzzy search slow | `gin_trgm_ops` index on `core_ward_boundaries` |
| G6-5C | SearchBox debounce timer leaks on unmount | Cleanup return in mount useEffect |
| G6-15D | SearchBox re-focus doesn't select text | `e.target.select()` in onFocus |
| G6-7D | Recharts ResponsiveContainer width(-1) warning | `minWidth={1} minHeight={1}` on all 7 charts |
| G6-7C | Duplicate data notes in MetricCard details | `Set`-based dedup in `DataNotes` |
| G6-7A | Zod schema mismatches | Fixed shapes + added `.passthrough()` |
| G6-11.1 | No focus-visible rings | `focus-visible:ring-2` on TabBar, MetricCard, SearchBox |
| G6-11.4 | Decision question text unreadable contrast | `text-ink-faint/60` → `text-ink-muted` |
| G6-13A | Ghost currency £ on non-financial metrics | Verified non-issue |

---

## Post-AWS Completed Items

| # | Task | Notes |
|---|------|-------|
| R15 | Outstanding schools within 15-min walk | Session 64. New `outstanding_schools_walk` metric. |
| M1 | Choropleth: widen scope to full LAD | Session 59. Postcode searches now use full LAD scope. |
| M3 | EC2: Ingest `core_epc_domestic` + re-run EPC backfill | Session 50. 29.2M rows restored, ~80%+ EPC coverage. |
| M4 | EC2: Full data integrity audit | Session 50. All tables verified. |
| M5 | Fix duplicate data notes globally | Frontend Set-based dedup in MetricCard.tsx. |

---

## Phase 7: User Review Polish — Completed Items

### 7A — Cross-tab / Structural

| # | Task | Notes |
|---|------|-------|
| P1 | Create Overview tab | Session 66. 10 headline metrics, OverviewSnapshotGrid, TabScoreRow, PersonaScoreCard. |
| P2 | Mini overview at top of each tab | Session 66. TabHighlightStrip component. |
| P3 | Move useful resources to Overview tab | Session 66. |
| P4 | Move comparable areas to Overview tab | Session 66. Expanded 5D→11D. SQL migration `011_expand_comparable_features.sql`. |
| P5 | Merge "So what?" + "Watch out for" → single "Takeaway" | Session 65. Single coloured pill. |
| P6 | Shortlisted vs Watch buttons → single Save button | Session 65. localStorage v2 with v1 migration. |
| P7 | Decision mode — make impact visible | Session 64. "Prioritised" / "Lower priority" badges. |
| P8 | Download report button broken | Session 57. |
| P10 | DB scan: unused table data → new metrics | Session 47 audit. |
| P51 | Saved areas — clarify persistence model | Session 65. |
| P52 | Full E2E test + deploy after Phase 7 | Session 66. 122/124, 30/30, 468/468. |
| P54 | Add bedroom layer to price history charts | Session 60. By Type/By Beds toggle. |

### 7B — Map

| # | Task | Notes |
|---|------|-------|
| P11 | Map scroll-follow logic — rethink UX | Session 63. Widened trigger zone, auto-follow toggle. |
| P12 | Distinct map icons per layer | POI_ICONS + Ofsted colour-coding. |
| P13 | Map layers showing nothing (parks, sports/rec) | Fixed duplicate query block in area_map.py. |
| P14 | Map concentric circles — add legend | Walk rings legend in MapLayerControl.tsx. |
| P15 | Metric vs map count mismatch | EV charger LIMIT raised to 200. |
| P16 | Bus stops on map + in transport table | StationTable with type toggle pills. |
| P17 | Median earnings choropleth on Governance tab | Moved to Property & Market. |

### 7C — Property tab

| # | Task | Notes |
|---|------|-------|
| P18 | Price history chart tooltip position | `allowEscapeViewBox` y: true. |
| P19 | New build proportion — add "(last 12m)" | Title changed in tab_property.py. |
| P20 | Hide blank metrics for inapplicable search types | `.filter((m) => m.local_value != null)`. |
| P21 | Remove EPC C+ metric (redundant) | Removed from 6 files. |
| P22 | Remove property calculators section | Removed MortgageCalculator + RentalYieldCalculator. |
| P23 | Move housing tenure + housing stock → Property | Moved from tab_community.py → tab_property.py. |
| P24 | Freehold vs leasehold — redesign details | Session 60. Stacked bar + freehold premium callout. |
| P25 | Move EPC chart from Environment → Property | Verified — already in Property. |
| P55 | Expandable transaction rows — previous sales | Session 47. Click row → sub-rows with % change. |
| P56 | Map fly-to on transaction row click | Session 47. Zoom 17, restores viewport on collapse. |
| P57 | Sold price popup format change | Session 47. New format: Address → Type · Tenure · Beds · Area → Last sold. |
| P58 | EPC rating distribution — enhanced | Session 60. Classic UK EPC arrow-style bars. |
| P59 | Property energy & building profile metric | Session 61. 29.2M EPC certs → 35,889 LSOA rows. BuildingProfileChart. |

### 7D — Lifestyle tab

| # | Task | Notes |
|---|------|-------|
| P26 | 15-minute amenities — rethink | Session 65. Renamed "Local Amenities (within 1 km)", walk-time estimates. |
| P27 | Nearest station — drop chart, keep table only | Removed TransportModeChart. |
| P28 | Transport table: bus vs train icons + bus stops | Session 48. StationTable with type toggle pills. |
| P29 | Sports/recreation — tabulate details | Type count badges + scrollable list. |
| P30 | Broadband: remove separate fibre + superfast metrics | Removed from 5 files. |
| P31 | Mobile: remove separate 4G + 5G metrics | Removed from 5 files. |
| P32 | Cycling to work — rethink | Session 64. National percentile, pct_no_car context. |
| P33 | Surface hub destinations in frontend | Session 64. Already working. |
| P60 | Station enrichment — TfL + NR data | Session 48/51. 22 columns on core_transport_stops. |

### 7E — Environment tab

| # | Task | Notes |
|---|------|-------|
| P34 | Flood risk — drop infographic | Replaced FloodRiskGauge with key-value grid. |
| P35 | Remove EPC metrics from Environment tab | Removed entire EPC section from tab_environment.py. |
| P36 | Air quality PMI trend chart → under PMI metric | AirQualityChart inline after metric. |
| P37 | NO2 trend chart | NO2 AirQualityChart inline. WHO limit: 10 µg/m³. |
| P38 | Park cover — data accuracy + methodology | Session 60. Audited — data correct. |

### 7F — Community tab

| # | Task | Notes |
|---|------|-------|
| P39 | Demographics overview — remove metric comparison | Removed parent comparison from DemographicsCards. |
| P40 | Median age — readable age band labels | "0–15 years", "16–64 years", "65+ years". |
| P41 | Work from home — remove (duplicative) | Removed from 7 files. |
| P42 | Commute distance labels — human-readable | "Under 2 km", "2–10 km", etc. |
| P43 | Household size labels — fix formatting | "1 person", "2 people", etc. |
| P44 | Religion metric — label the headline religion | Dynamic dominant religion detection. |
| P45 | Primary school + school quality → combined metric | Merged. Quality summary bar above school list. |
| P46 | Secondary school + school quality → combined metric | Same pattern as P45. |
| P47 | Consolidate all deprivation indices | Session 60. Hid 7 sub-domain cards, added RadarChart. |
| P48 | NHS facilities — tabulate + type filter toggles | NhsFacilitiesDetail component. |

### 7G — Governance tab

| # | Task | Notes |
|---|------|-------|
| P49 | Enrich governance tab content | Session 64. S114 re-enabled, council tax bands, 5-7 metrics. |
| P50 | Utility providers — add electricity/gas | Session 64. NESO DNO GeoJSON ETL. 350 LADs. |

---

## Phase 8: Idle Data — Completed Items

### Quick Wins (zero ETL)

| # | Task | Notes |
|---|------|-------|
| D10 | Surface freehold premium ratio | Session 50. Added to `freehold_leasehold` metric details. |
| D11 | Surface price spread (min/max/p10/p90) | Session 50. New `price_spread` metric on Property tab. |
| D14+D15 | Official ONS HPI trend + YoY change | Session 50. New `official_hpi` metric with time series. |

Skipped: D12 (redundant — `new_build_proportion` already exists), D13 (redundant — `tab_property.py` already computes price/sqft).

### Medium Effort (EPC re-aggregation from Hetzner)

| # | Task | Notes |
|---|------|-------|
| D16 | Construction age band distribution | Session 61 (P59). 7 age bands from Hetzner EPC. |
| D17 | Running costs (heating + hot water + lighting) | Session 61 (P59). |
| D18 | CO2 emissions per property | Session 61 (P59). |
| D19 | Heating fuel type breakdown | Session 61 (P59). |
| D20 | Solar/renewable adoption rate | Session 61 (P59). |
| D21 | Glazing + insulation quality | Session 62. 16 new columns on core_epc_lsoa. |
| D22 | Built form distribution | Session 62. 6 clean categories. |

### Census Data (already implemented)

D23 (age distribution), D24 (household size), D25 (born abroad), D26 (commute distance) — all already implemented in earlier sessions.

### Other Completed Data Items

| # | Task | Notes |
|---|------|-------|
| D27 | Enrich transaction table — all tiers | Tier 1: sessions 60+63. Tiers 2-3: session 64 via Hetzner EPC proxy. |
| D29 | Surface INSPIRE + LLC at area level | Session 63. `land_designations` metric on Environment tab. |
| D31 | EPC coverage footnote on price_per_sqm | Session 63. Hetzner Property API returns coverage counts. |

---

## Sessions 56–69: Completed Work

| # | Task | Notes |
|---|------|-------|
| S56 | Section accordion UX + prototype pages | Session 56. |
| S57 | 19-fix audit — perf, map, UX, accessibility, data | Session 57. |
| S58 | Prototype-style metric rendering restored | Session 58. 14 redesigned renderers. |
| S59-1 | Fix map double-creation fly-away effect | Session 59. boundaryRef pattern. |
| S59-2 | M1: Choropleth scope widened to full LAD | Session 59. |
| S60-1 | P24: Tenure visual stacked bar + freehold premium | Session 60. |
| S60-2 | D27-T1: Transaction table extra columns | Session 60. |
| S60-3 | P47: Deprivation radar chart consolidation | Session 60. |
| S60-4 | P54: Bedroom filter on price history charts | Session 60. |
| S60-5 | P58: EPC rating distribution fix + redesign | Session 60. |
| S60-6 | P38: Park cover data audit | Session 60. Verified correct. |
| S61-1 | P59: Building Profile metric | Session 61. 29.2M EPC certs → 35,889 LSOAs. |
| S62-1 | D21+D22: Glazing, insulation, built form | Session 62. 16 new columns. |
| S63-1 | D29: LLC land designations | Session 63. |
| S63-2 | D31: EPC coverage footnote | Session 63. |
| S63-3 | D27: Transaction table Tier 1 columns | Session 63. |
| S63-4 | P11: Map scroll-follow rethink | Session 63. |
| S64-1 | P49: Enrich Governance tab | Session 64. |
| S64-2 | P32: Cycling metric rethink | Session 64. |
| S64-3 | P33: Hub destinations verified | Session 64. |
| S64-4 | P7: Decision mode visibility | Session 64. |
| S64-5 | R15: Outstanding schools walkable | Session 64. |
| S64-6 | D27 T2-3: Per-transaction EPC details | Session 64. |
| S64-7 | P50: Electricity & gas providers | Session 64. |
| S65-1 | P5: Takeaway merge | Session 65. |
| S65-2 | P6+P51: Save button simplification | Session 65. |
| S65-3 | P26: Amenities rethink | Session 65. |
| S66-1 | P1-P4: Overview tab + structural changes | Session 66. |
| S67-1 | Ceremonial county mapping for parent comparison | Session 67. 86 rows, 49 groups + 6 singletons. |
| S67-2 | Singleton escalation in `get_parent_lad_info()` | Session 67. |
| S67-3 | `_resolve_parent()` delegates to `get_parent_lad_info()` | Session 67. |
| S67-4 | Sub-LAD parent comparison shortcircuit | Session 67. Note: later reverted in S68-1. |
| S67-5 | Enhanced mode attempt + revert | Session 67. REVERTED — plumbing preserved. |
| S67-6 | Map marker idle-event race fix | Session 67. |
| S68-1 | Revert sub-LAD entity_type parent logic | Session 68. Commit `67198c2` reverted in `9331166`. |
| S68-2 | Revert enhanced mode work | Session 68. All 4 commits reverted in `0ab1da7`. |
| S69-1 | Universal parent query migration (`WHERE lad_code = ANY(:parent_lads)`) | Session 69. All 5 MV-backed parent queries converted. |
| S69-2 | Population-weighted AVG migration (31 queries, 10 files) | Session 69. Every multi-LAD `AVG()` → weighted. |
| S69-3 | New MV: `mv_lad_population` (318 rows) | Session 69. `sql/013_lad_population_view.sql`. |
| S69-4 | Add `transactions` column to `mv_parent_yearly_ppsf` | Session 69. |
| S69-5 | HPI COALESCE fix | Session 69. `COALESCE(sales_volume, 1)` for graceful NULL degradation. |
| S69-6 | Compliance audit — 2 additional local multi-LAD fixes | Session 69. |
| S69-7 | Full verification (5 search types × 6 tabs) | Session 69. Playwright 122/124, Metric 30/30, Brutal 468/468. |

---

## Session 69: Population-Weighted AVG Migration Summary

**Problem:** 23+ queries used unweighted `AVG()` for multi-LAD aggregation. City of London (8,600 pop) = Birmingham (1.1M).

**Solution:** `SUM(metric * weight) / NULLIF(SUM(weight), 0)`. 31 queries fixed across 10 files + 1 new MV + 1 MV column.

| Weight | Used for | Source |
|--------|----------|--------|
| `total_pop` | AQ, mobile, council tax, earnings, IMD, NHS, station, PTAL, connectivity, green space | `mv_lad_population` (LAD) or `core_census_lsoa` (LSOA) |
| `total_hh` | Rent, broadband | `mv_lad_population` |
| `transactions` | PPSF | `mv_parent_yearly_ppsf` (new column) |
| `COALESCE(sales_volume, 1)` | HPI YoY | `core_hpi_lad` (graceful NULL degradation) |
| `transaction_count` | Census-derived %s | Already existed (sessions 39-40, G5-3) |

**LSOA-level queries left unweighted (safe):** LSOAs have ~1,500 population by design.

**Commits:** `4d15c1b` (main batch), `60e013d` (HPI fix), `9dbabb4` (2 local fixes + cache bump).

**Cache versions:** `AREA_CACHE_VERSION = "v37"`, `PRICE_CACHE_VERSION = "v36"`.

---

## Session 70: Quick Wins (Apr 30 2026)

| # | Task | Notes |
|---|------|-------|
| P61 | Landing page tagline update | "Know your neighbourhood" → "Move with certainty." + new supporting copy in `Home.tsx`. |
| — | MetricCard hover bug fix | Added `overflow-hidden` to card container — hover tint no longer pokes out of `rounded-2xl` corners. |
| — | "coming soon" text bug fix | Removed `not_modelled_yet` → "coming soon" branch from MetricCard. Now shows em dash like other null comparisons. |
| — | "Data available - no comment" bug fix | `getTakeaway()` returns `null` when `comparison_flag === null`. Callers guard with optional chaining. No takeaway pill rendered. |
| GD-U1 | `useCountUp` hook | `frontend/src/hooks/useCountUp.ts` — ease-out cubic, rAF, `prefers-reduced-motion` respected. Drop-in for C6. |
| — | QUEUE.md / CHANGELOG.md restructure | Split 940-line QUEUE.md into pending-only queue + completed-work changelog. |

**Commit:** `60a80e4`.

| # | Task | Notes |
|---|------|-------|
| GD-U4 | Sparkline component | `frontend/src/components/Sparkline.tsx` — pure SVG polyline, trend-coloured end dot, no deps. |
| GD-V3 | Animated pulse badge | "Free · Open Data · Every Postcode" pill with pulsing green dot above headline in `Home.tsx`. |
| GD-V5 | `active:scale-95` on buttons | Press-down effect on Home quick links, theme tiles, TabBar pills, MetricCard rows. |

**Commit:** `5052293`.

| # | Task | Notes |
|---|------|-------|
| GD-U3 | VerdictPill hover tooltip | Pure CSS tooltips on takeaway pills (desktop + mobile) showing "So what" and "Watch out" context. `group/pill` + `group-hover/pill:opacity-100` pattern. |
| GD-U5 | Source attribution gap-fill | Added 24 missing entries to `METRIC_SOURCES` in MetricCard.tsx — 82/82 metrics now have source badges. |
| GD-U9 | ScoreRing component | `frontend/src/components/ScoreRing.tsx` — 270° SVG arc gauge with gradient fill, glow aura, parent marker dot. |
| D34 | School Intelligence Module — CLOSED | Audit confirmed 95%+ complete: 17 Hetzner DB tables, 16 ETL scripts, 10 API endpoints, 7 SchoolTable tabs all operational. Independent fees parked (no public data source). |
| D35 | LA admissions scraping — PoC complete | Croydon secondary: 23 schools (PAN, apps, allocation breakdown, LDO, SIF, open days). 13/23 have LDO. Parser: pdfplumber + positional text. SEND/ELP committed as D36. |

**Commit:** `2b79b0d`.

---

## Session 67: Competitive Analyses (Reference)

### Findstead.co.uk

**Where Findstead beats us:** AI-powered natural language search, active property listings (100K+ scraped from Rightmove — legally grey), "paste a Rightmove URL" analysis, financial calculators, persona-driven onboarding UX.

**Where we beat Findstead:** Data depth (72+ metrics vs thin), geographic coverage (all E&W vs London commuter belt), comparable areas (11D algorithm), commute modelling (MOTIS), school intelligence (Ofsted/KS2/KS4/KS5), map visualisations.

**Key insight:** Findstead's listings are almost certainly scraped from Rightmove/Zoopla. One C&D and their core feature disappears. Do NOT replicate.

### BurbScore.com

User loved their visual warmth, typography, and UX — said "this is the gap between what I had in my head vs what I was trying to tell you our site needs to be."

| Element | BurbScore | PropertyPulse | Gap |
|---------|-----------|---------------|-----|
| Colour palette | Warm cream/orange/sage | Cool blue/grey | High |
| Typography | Fraunces + Nunito Sans + IBM Plex Mono | Single font family | High |
| Whitespace | Generous padding | Dense layout | Medium |
| Storytelling | Narrative-first, persona-led | Data-dump style | Medium |
| Chart style | Smooth curves, gradient fills, arc gauges | Straight lines, flat bars | Medium |

**Prototype2:** Created at `/prototype2` (`Prototype2.tsx` ~1800 lines). User approved direction.

---

## Session 67: Parent Comparison — Complete Rule Set (Reference)

| Search Type | Entity Type | Parent Name | `parent_lad_codes` |
|-------------|-------------|-------------|---------------------|
| Postcode inside London borough | postcode | "Greater London" | all 33 E09 codes |
| Postcode inside any other LAD | postcode | that LAD's name | `[that_lad_code]` |
| Ward inside London borough | ward | "Greater London" | all 33 E09 codes |
| Ward inside any other LAD | ward | that LAD's name | `[that_lad_code]` |
| Place inside London borough | place | "Greater London" | all 33 E09 codes |
| Place inside any other LAD | place | that LAD's name | `[that_lad_code]` |
| Postcode district | postcode_district | follows same sub-LAD rule | same as above |
| LAD search (non-singleton) | lad | county peer group name | all LADs in that group |
| LAD search (singleton, England) | lad | region name | all LADs in that region |
| LAD search (singleton, Wales: Powys) | lad | "Wales" | all 22 W06 codes |
| County search | county | region name | all LADs in region |

Wales preserved counties: Clwyd (4), Dyfed (3), Gwent (5), Gwynedd (2), Mid Glamorgan (3), Powys (1 singleton), South Glamorgan (2), West Glamorgan (2).
