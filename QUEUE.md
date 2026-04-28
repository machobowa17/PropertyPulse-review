# PropertyPulse — Master Work Queue

Last updated: 2026-04-28 (session 65)

**This is the SINGLE source of truth for all task tracking. No other file tracks task status.**

---

## ONE QUEUE — Execute in Order

### Phase 1: Foundation (COMPLETE ✓)

All 12 tasks done. INSPIRE 24.3M, LLC 7.7M, Flood 3.5M ingested. Metric registry refactor. Results.tsx decomposition. epc_domestic.py rewrite. personas.ts 60 branches.

---

### Phase 2: Review Fixes (COMPLETE ✓)

22 items done (R1–R25, excluding R6 skip / R23 defer / R15 post-AWS). Security, backend perf, frontend perf, infra. tsc -b 0 errors, vite build clean.

---

### Phase 2.5: AI Studio Review Fixes (COMPLETE ✓)

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

#### Deferred / Not a bug

- "Fast typer" race → Not a bug (trigram fallback handles)

---

### Phase 2.6: AI Studio Critical Fixes (COMPLETE ✓)

Source: Google AI Studio second-round review (session 34). 4 critical flaws identified and fixed. tsc -b 0 errors, vite build clean, 21/21 metric + 114/123 comprehensive (0 regressions).

| # | Task | Fix |
|---|------|-----|
| C1 | DecisionMode is placebo toggle — scoring ignores Buy/Rent/Invest | `DECISION_MODE_MULTIPLIERS` matrix in `personalization.ts`; threaded through `buildSignal`, `collectPersonaSignals`, `buildPersonaFitSummary`, `rankSectionsForPersona`; `PersonaScoreCard` + `ResultsMetricsPanel` updated |
| C2 | Postcode district substring truncation — Python `dist_len` gives CR51 not CR5 | Replaced with Postgres regex `SUBSTRING(postcode_compact FROM '^[A-Z]{1,2}[0-9][A-Z]?')` in `resolve.py` suggest |
| C3 | Suggest endpoint DoS vector — `@limiter.exempt` | Replaced with `@limiter.limit("300/minute")` + `request: Request` param in `resolve.py` |
| C4 | ETL `INCLUDING ALL` bottleneck — indexes during bulk insert | `create_staging_table()` + `recreate_indexes()` in `etl/utils.py`; 5 large-table modules converted (land_registry 30M, inspire 24M, llc 7.7M, crime 6M, flood 3.5M) |

---

### Phase 2.7: AI Studio Hardening Fixes (COMPLETE ✓)

Source: Google AI Studio third-round review (session 35). 13 fixes from 31+10 item review (16 already fixed in sessions 31-34, 3 deferred). tsc -b 0 errors, vite build clean, 21/21 metric + 117/123 comprehensive (0 regressions).

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

#### Deferred / Not fixed (session 35) — ALL RESOLVED in Phase 2.8 below

---

### Phase 2.8: Final Hardening + Brutal Test Suite (COMPLETE ✓)

Source: Session 35 continuation. 3 deferred AI Studio items (H14–H16) implemented + 2 bugs found by brutal test suite (B1–B2) fixed. Brutal test suite created (447 tests). tsc -b 0 errors, vite build clean, 21/21 metric + 117/123 comprehensive (0 regressions) + 447/447 brutal.

| # | Task | Fix |
|---|------|-----|
| H14 | Prefetch tab storm — 4 tabs fire simultaneously on page load | Staggered delays: tab 0 at 0ms, tab 1 at 2s, tab 2 at 4s, tab 3 at 6s in `ResultsContext.tsx` |
| H15 | GeoJSON payload bloat — county boundaries 300+ KB | `ST_SimplifyPreserveTopology` in `area_boundary.py` (LAD 0.0002, place 0.0003, county 0.0005) + `area_map.py` choropleth |
| H16 | Ethnicity erasure on place searches — uses entire LAD | LSOA→ward derivation via `core_postcodes` subquery in `tab_community.py` |
| B1 | Null bytes in `/resolve` cause 500 | Input sanitisation (strip `\x00`) in `resolve.py` |
| B2 | Place boundary 500 when `core_place_boundaries_union` missing | try/except + `db.rollback()` fallback in `area_boundary.py` |

#### Test suite
- `test_brutal.py`: 13-section brutal stress test (adversarial inputs, math correctness, boundary integrity, ethnicity accuracy, cross-search consistency, 5×5 tab×search matrix, Playwright UI). Originally 447 assertions (session 35), now ~390 after test evolution. 385/390 as of session 63.

---

### Phase 2.9: Data Gap Fixes (COMPLETE ✓)

Source: Session 36-37 data gap audit. 28 gaps catalogued, 7 fixed, 1 deferred, 1 won't fix. tsc -b 0 errors, vite build clean.

| # | Task | Fix |
|---|------|-----|
| D1 | Metro county lookup gap (5 of 6 missing) | CSV-based `metro_county_lookup.csv` in `lad_county_lookup.py` — E11 codes for all 36 E08 metro districts. Matviews rebuilt. Boundary names fixed. |
| D2 | `core_place_boundaries_union` missing | Ran `place_lsoa_mapping` derivation — 9,565 pre-computed unions. Endpoint no longer needs live ST_Union. |
| D3 | Dead persona weights (3 non-existent metrics) | Removed `connectivity_index`, `fifteen_min_score`, `esg_score` from personalization.ts, personas.ts, tabs.ts, resultsConstants.ts, MetricCard.tsx |
| D4 | `core_price_by_bedrooms_lad` empty (0 rows) | Ran `price_by_bedrooms` derivation — 144,906 rows from 5.3M EPC-matched transactions |
| D5 | Census religion data unused (7,638 rows) | Wired `core_census_religion_ward` into `tab_community.py`. New `religion` metric with ward-level derivation (same pattern as ethnicity). Registry, icons, data sources updated. |
| D6 | GMP crime data verified | All 36 metro districts have crime data (Bolton 101, Manchester 163, Birmingham 659, Sheffield 344 LSOAs) |
| D7 | EPC backfill (price_per_sqft history) | Already complete — 5.3M matched rows, ~20% match rate across all years (sessions 17-18). Was incorrectly listed as blocked. |

#### Deferred / Won't fix

| # | Gap | Status | Notes |
|---|-----|--------|-------|
| D8 | financial_health/S114 | DEFERRED | Needs provenance-backed data source. Registry entry exists, no tab service wired. |
| D9 | Commute estimator (501 Not Implemented) | WON'T FIX | No local data source. Frontend-only via TfL/Google APIs. |

---

### Phase 3: AWS Deployment (COMPLETE ✓)

Source: Sessions 37-38. EC2 t4g.small (eu-west-2), 80 GB gp3 EBS, Elastic IP 16.60.67.248. Domain: simusimi.com (Cloudflare). All data restored and verified (exact row counts match local).

| # | Task | Status | Notes |
|---|------|--------|-------|
| 13 | AWS: Create account, configure eu-west-2 | DONE | Elastic IP 16.60.67.248 |
| 14 | AWS: Launch t4g.small + 80 GB gp3 EBS | DONE | ARM64 Graviton, 2 vCPU, 2 GB RAM |
| 15 | AWS: Provision Docker + docker-compose (AL2023, ARM) | DONE | Docker 27.x, Compose v2.29.2, 2 GB swap |
| 16 | AWS: `pg_dump` → upload → `pg_restore` on EC2 | DONE | 18 GB dump, all 30.4M transactions + indexes + MVs restored. `imresamu/postgis:16-3.4` (ARM64) |
| 17 | AWS: Docker Compose (API + frontend/nginx + Redis + PG) | DONE | `docker-compose.ssl.yml` override. No S3/CloudFront — nginx serves frontend directly |
| 18 | AWS: DNS + TLS (Let's Encrypt) | DONE | `simusimi.com` via Cloudflare DNS. Let's Encrypt cert (expires 2026-07-16) |
| 19 | AWS: GitHub Actions CI/CD | Parked | Git-based deploy via `deploy.sh` (session 56). CI removed (token lacks workflow scope). |

---

### Phase 4: Google AI Studio Live Review Polish (COMPLETE ✓)

Source: Session 38. Google's 4th-round review (codebase + live site). ~34 items triaged: 29 already fixed in sessions 33-36, 5 new items fixed. tsc -b 0 errors, vite build clean. Deployed to EC2.

| # | Task | Fix |
|---|------|-----|
| L1 | TabBar pill misaligns on window resize | Added `resize` event listener in `TabBar.tsx` |
| L2 | Sticky hover states on mobile Safari | `[@media(hover:hover)]:group-hover:` guard in `MetricCard.tsx` |
| L3 | Choropleth legend text overflow on mobile | `max-width: min(200px, calc(100% - 16px)); word-wrap` in `MapView.tsx` legend |
| L4 | PDF download opens blank tab | Replaced `<a target="_blank">` with blob-fetch `<button>` + spinner in `ResultsHero.tsx` |
| L5 | Sold price DOM markers cause mobile stutter | Capped individual markers at 150 (clusters unaffected) in `MapView.tsx` |

#### Already fixed (confirmed in triage)
29 items from Google's review were already resolved in G1-G11 (session 33), C1-C4 (session 34), H1-H16 (session 35), B1-B2 (session 35), D1-D7 (session 36).

---

### Phase 5: Google AI Studio Review Round 5 (COMPLETE ✓)

Source: Sessions 39-40. Two batches from Google (17 + 14 items). Google admitted batch 1 was reviewing stale code. Combined triage: ~22 items already fixed (sessions 32-38), 8 genuinely new — all fixed. Full triage in `memory/google_review_5.md`. tsc -b 0 errors, vite build clean, 21/21 metric tests.

| # | Task | Status | Fix |
|---|------|--------|-----|
| G5-1 | MapLibre hover feature-state — polygon highlight + tooltip | DONE | `promoteId: 'lsoa_code'`, `setFeatureState`, `fill-opacity` feature-state expression, mousemove tooltip + hover popup in `MapView.tsx` |
| G5-2 | IntersectionObserver scroll-follow — replace layout thrashing | DONE | Replaced rAF+getBoundingClientRect with `IntersectionObserver` (`rootMargin: '-35% 0px -35% 0px'`) in `useResultsMap.ts` |
| G5-3 | Simpson's Paradox — population-weighted census averages | DONE | `SUM(weight * pct) / NULLIF(SUM(weight), 0)` across 7 files: `tab_community.py` (demographics, health, housing, household size, ethnicity, religion), `tab_property.py` (stock + EPC), `tab_lifestyle.py` (cycling, commute), `tab_environment.py` (EPC), `area_price.py` (bedroom prices). Weights: `total_population`, `total_households`, `total_workers`, `total_certs`, `total_pop`, `transaction_count`. |
| G5-4 | Schools + NHS ST_Within in area-mode local queries | DONE | Replaced `JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)` with `JOIN core_postcodes p ON p.postcode_compact = REPLACE(s.postcode, ' ', '')` for schools (4 queries) and NHS facilities (2 queries) in `tab_community.py` |
| G5-5 | Sold-price spatial bias | VERIFIED | Already uses `ROW_NUMBER() PARTITION BY lsoa_code` — stratified sample. Not broken. |
| G5-6 | LLC + INSPIRE ST_CollectionExtract defensive fix | DONE | Wrapped `ST_MakeValid()` in `ST_CollectionExtract(..., 3)` in `llc.py` (2 sites) and `inspire_parcels.py` (1 site) |
| G5-7 | Choropleth quantile edge case (<5 unique values) | DONE | Dynamic bucket count from actual data. Maps fewer buckets to evenly-spaced colours from the 5-colour ramp in `MapView.tsx` |
| G5-8 | Mobile map touch-action (two-finger pan) | DONE | `cooperativeGestures: window.matchMedia('(pointer: coarse)').matches` in MapLibre init (`MapView.tsx`) |

#### Already fixed (confirmed in triage — Google reviewing stale code)
Batch 1: #4 a11y (H12), #6 Z-score (G11), #7 ethnicity (H16), #8 crime falsy (G1), #14 DecisionMode (C1), #15 CR5 (C2), #16 cross-tab (G9), #17 rate limit (C3).
Batch 2: ASGI thread (H1), TRUNCATE (C4), mega-context (session 32), GeoJSON off-thread (R2), PDF XML escape (session 35), chart lazy (H12).

#### Not fixing (justified)
- `geom::geography` index bypass — ST_DWithin uses GiST index for bounding box pre-filter. Not a seq scan.
- Pagination OFFSET — scoped to 13 months of single area. Max ~1000 rows.
- Overpass API — ETL-only, data already ingested.
- EPC backfill index bloat — one-time script, already run.
- Query consolidation (5× queries) — different column sets, optimisation not a bug.

---

### Phase 6: Gemini Round 6 Review Fixes (COMPLETE ✓)

Source: Session 41. Gemini AI Studio full audit (15-section report in `Gemini_Review/`). ~35 claims triaged: ~13 wrong conclusions, ~11 already fixed, 11 genuine items fixed. tsc -b 0 errors, vite build clean, 21/21 metric + 112/115 comprehensive (3 pre-existing).

| # | Task | Fix |
|---|------|-----|
| G6-2A | RequestValidationError masked as 500 | Added `RequestValidationError` handler → returns 422 with field-level detail in `main.py` |
| G6-2C | Deprecated X-XSS-Protection header | Removed from `main.py`, `nginx.conf`, `nginx-ssl.conf` |
| G6-1B | Ward name fuzzy search slow (no trigram index) | `CREATE INDEX idx_ward_boundaries_name_trgm ON core_ward_boundaries USING gin (ward_name gin_trgm_ops)` |
| G6-5C | SearchBox debounce timer leaks on unmount | Cleanup return in mount useEffect |
| G6-15D | SearchBox re-focus doesn't select text | `e.target.select()` in onFocus handler |
| G6-7D | Recharts ResponsiveContainer width(-1) warning | `minWidth={1} minHeight={1}` on all 7 chart ResponsiveContainers |
| G6-7C | Duplicate data notes in MetricCard details | `Set`-based dedup in `DataNotes` component |
| G6-7A | Zod schema mismatches (console warnings on every /area call) | Fixed `headline`, `comparison`, `capsule`, `map_binding` shapes to match actual backend contract; added `.passthrough()` |
| G6-11.1 | No focus-visible rings on interactive elements | `focus-visible:ring-2 focus-visible:ring-brand-500` on TabBar, MetricCard (desktop+mobile), SearchBox submit |
| G6-11.4 | Decision question text unreadable contrast | `text-ink-faint/60` → `text-ink-muted` (2 sites in MetricCard) |
| G6-13A | Ghost currency £ on non-financial metrics | Verified non-issue — `formatValue` only applies £ for GBP units |

#### Gemini claims triaged as wrong / already fixed
~24 items dismissed: pool_size claim (would reintroduce H2 crash), clustering (Supercluster already exists), ghost metrics (removed in D3), context thrashing (already memoized in R1), ETL SQL injection (parameterized queries), map lag (lazy loading already done), and others.

---

### Post-AWS

| # | Task | Status | Notes |
|---|------|--------|-------|
| R15 | Outstanding schools within 15-min walk | **DONE** | Session 64. New `outstanding_schools_walk` metric on Community tab. Haversine 1500m radius proxy for ~15 min walk. Skipped for area-mode searches. |
| M1 | Choropleth: widen scope to full LAD (not just ward) | **DONE** | Session 59. Removed ward-scoped branch from `area_map.py` choropleth endpoint — postcode searches now use full LAD scope (~300-500 LSOAs). CR5 1RA: 229 LSOAs (was ~15). SW1A 1AA: 123 LSOAs. Cache version bumped to v6. |
| M2 | Choropleth: national coverage via PMTiles (vector tiles) | Pending | Pre-generate PMTiles per choropleth layer using `tippecanoe` from `core_lsoa_boundaries` + pre-joined metric values. ~35k polygons/layer → ~10-50MB per file. Host on S3/CloudFront (free tier). Frontend: swap `type: 'geojson'` for `type: 'vector'` + PMTiles protocol. Quantiles baked at generation time (no flicker). ~30 layers × ~20MB = ~600MB on S3. Best UX: instant pan/zoom, full national coverage, no API calls. Requires ETL pipeline addition. Do after M1 proves demand. |
| M3 | EC2: Ingest `core_epc_domestic` + re-run EPC backfill | **DONE** | Session 50. (1) Restored `core_epc_domestic` (29,214,082 rows) from `gdrive:PropertyPulse/core_epc_domestic.dump` via rclone + pg_restore. (2) Ran `backfill_epc_matching.py` to populate `bedrooms_estimated`, `floor_area_sqm`, `epc_rating` on `core_property_transactions`. Coverage went from ~17% to ~80%+. Also dropped `tmp_postcode_bng` (252 MB) and `_epc_staging` (empty). |
| M4 | EC2: Full data integrity audit | **DONE** | Session 50. Comprehensive audit: all tables verified. Key findings: `core_epc_domestic` restored (was 0), `core_connectivity_lsoa` empty (planned data never loaded — not blocking), EPC population now ~80%+ after backfill. Disk at ~79% usage. All materialized views populated. All indexes present. |
| M5 | Fix duplicate data notes globally | **DONE** | Frontend MetricCard.tsx now collects all `_note` texts from details into a Set, then filters quality_flags to exclude any matching text. Prevents duplicate display across DataNotes + quality_flags. |

---

### Phase 7: User Review Polish (session 43)

Source: User walkthrough of all 5 tabs on live site. ~50 items covering UX, data accuracy, metric consolidation, tab restructuring, map improvements, and label readability.

#### 7A — Cross-tab / Structural

| # | Task | Status | Notes |
|---|------|--------|-------|
| P1 | Create Overview tab | Pending | New central tab. Houses: comparable areas (cross-tab, not per-tab), useful resources, and other cross-cutting content. Comparable areas comparison should use metrics from ALL tabs, not just one. Create provision first, populate later. |
| P2 | Mini overview at top of each tab | Pending | Consider a summary/overview strip at the top of every tab (like demographics overview but without metric comparison indicators). Design TBD. |
| P3 | Move useful resources to Overview tab | Pending | Currently duplicated across multiple tabs. Move to P1's Overview tab. |
| P4 | Move comparable areas to Overview tab | Pending | Currently per-tab. Rearchitect to use cross-tab metrics for comparison. |
| P5 | Merge "So what?" + "Watch out for" → single "Takeaway" | **DONE** | Session 65. Combined two pills into single coloured takeaway pill: "soWhat — watchOut". Simpler, less visual clutter. MetricCard desktop: one w-44 column. Mobile: one pill. personalization.ts capsule also combined. |
| P6 | Shortlisted vs Watch buttons → single Save button | **DONE** | Session 65. Merged shortlist+watchlist into single "Save"/"Saved" toggle (Bookmark icon). localStorage v2 migration with v1 auto-import. SavedAreas page simplified to single list (48 item cap). ResultsContext: `isSaved` boolean + `toggleSave()`. |
| P7 | Decision mode (Buy/Rent/Invest) — make impact visible | **DONE** | Session 64. "Prioritised" (green) and "Lower priority" (amber) badges on MetricCard. PersonaScoreCard shows mode-aware label. |
| P8 | Download report button broken | **DONE** | Fixed in session 57 (commit `2b6150f`). Report endpoint returns valid PDF (reportlab on EC2). Verified session 59: 200 OK, 18KB PDF for CR5 1RA. |
| P9 | Scotland + NI coverage | Pending | To be discussed — scope, data sources, feasibility. |
| P10 | DB scan: unused table data → new metrics | **DONE** | Audit completed session 47. See "Phase 8: Idle Data — Audit & Proposals" below. |
| P51 | Saved areas — clarify persistence model | **DONE** | Session 65. Addressed alongside P6. localStorage v2 with clear "Saved to this browser" copy. Single collection, 48-item limit, auto-migration from v1. No cross-device sync needed for MVP. |
| P52 | Full E2E test + deploy after Phase 7 | Pending | After all Phase 7 changes: run full Playwright suite, tsc -b, vite build. Deploy latest to EC2. Upload codebase to Google Drive. Save context, queue, memory. |
| P53 | Single address search — show all data for a specific property | Pending | Allow searching by full address (e.g. "14 Acacia Avenue, SW1A 1AA"). Display all non-GDPR-sensitive data we hold: transaction history, EPC ratings/details, floor area, property type, tenure, flood zone, LLC charges, INSPIRE parcel, noise levels, broadband, etc. All public registry data — no personal data. Requires: (1) resolve endpoint to handle address-level search, (2) new address-level results view, (3) DB scan to catalogue all address-level data available. Includes classic UK EPC certificate visual (arrow-style A-G chart with pointer) for the individual property. Data plan: see D28. |
| P54 | Add bedroom layer to price history charts | **DONE** | Session 60. "By Type" / "By Beds" dimension toggle in DistrictPriceHistoryChart. 1-5+ bed lines with colour-coded toggles. Backend now returns `by_bedrooms` for all search types (not just LAD). |

#### 7B — Map

| # | Task | Status | Notes |
|---|------|--------|-------|
| P11 | Map scroll-follow logic — rethink UX | **DONE** | Session 63. Widened trigger zone (top 15-45%), auto-follow toggle, context-only metrics no longer blank map, MapPin active indicator on MetricCard. |
| P12 | Distinct map icons per layer | **DONE** | POI_ICONS in MapView.tsx: 🎓 school, 🚆 station, ⚡ EV charger, 🏪 amenity, 🌳 park, ⚽ sports/rec, 🏥 NHS. Schools also colour-coded by Ofsted rating. |
| P13 | Map layers showing nothing (parks, sports/rec) | **DONE** | Duplicate park/sports query block removed from Environment & Safety branch in area_map.py. Parks/sports correctly only served under Lifestyle tab. |
| P14 | Map concentric circles — add legend/explanation | **DONE** | Walk rings legend added to MapLayerControl.tsx under Lifestyle & Connectivity tab — shows 5/10/15 min walk rings as dashed lines with distance labels. |
| P15 | Metric vs map count mismatch | **DONE** | EV charger LIMIT raised from 20/30 → 200 in area_map.py for both postcode and area modes. |
| P16 | Bus stops on map + in transport table | **DONE** (table) | Bus stops in StationTable with type toggle pills (Rail/Metro-DLR/Tram/Bus/Ferry). Fully deployed. Map distinct icons still pending (P12). |
| P17 | Median earnings choropleth on Governance tab | **DONE** | Moved choropleth_median_earnings to Property & Market. Also moved choropleth_housing_tenure, choropleth_housing_type. Removed dead choropleth layers (full_fibre, superfast_broadband, mobile_4g_indoor, mobile_5g_outdoor, wfh). |

#### 7C — Property tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P18 | Price history chart tooltip position | **DONE** | Changed `allowEscapeViewBox={{ x: false, y: false }}` to `y: true` in DistrictPriceHistoryChart.tsx — tooltip can now escape chart bounds vertically. |
| P19 | New build proportion — add "(last 12m)" to title | **DONE** | Title changed to "New Build Proportion (last 12m)" in tab_property.py. |
| P20 | Hide blank metrics for inapplicable search types | **DONE** | Added `.filter((m) => m.local_value != null)` in ResultsMetricsPanel.tsx. Metrics with null local_value are now hidden. |
| P21 | Remove EPC C+ metric (redundant) | **DONE** | Removed from tab_property.py, tab_environment.py, resultsConstants.ts, personalization.ts, personas.ts, tabs.ts, MetricCard.tsx METRIC_SOURCES. |
| P22 | Remove property calculators section | **DONE** | Removed MortgageCalculator + RentalYieldCalculator imports and CollapsibleSection from ResultsMetricsPanel.tsx. Test updated. |
| P23 | Move housing tenure + housing stock from Community → Property | **DONE** | Moved queries + metric emission from tab_community.py → tab_property.py. Moved choropleth bindings in resultsConstants.ts. Updated METRIC_TAB in personalization.ts. Human-readable detail keys. |
| P24 | Freehold vs leasehold — redesign expanded details | **DONE** | Session 60. Added stacked bar chart (coloured segments for freehold/leasehold/tenure splits) + freehold premium callout (amber box: "2.7× freehold premium"). Applied to all `tenure_table` breakdown types. |
| P25 | Move EPC chart from Environment → Property | **DONE** | EPC chart already lives in Property tab via `epc_energy_score` metric. P35 removed all EPC metrics from Environment tab. Verified — no action needed. |
| P55 | Expandable transaction rows — previous sales | **DONE** | Session 47. Click row → sub-rows show previous sales of same property. Backend `/transactions/history` endpoint matches by `postcode + paon + street`. SAON handling: empty=match all (houses), specific=exact match (flats). +/− indicator, % change vs older sale, main row shows % in brackets. |
| P56 | Map fly-to on transaction row click | **DONE** | Session 47. Expanding a row flies map to property at zoom 17. Collapsing row or metric card restores original viewport. `mapFlyToRef` in ResultsContext, populated by MapView `onMapReady` callback. `lat`/`lon` added to `/transactions` response. |
| P57 | Sold price popup format change | **DONE** | Session 47. Changed from Address → £price (big) → Type · Tenure → Date to: Address → Type · Tenure · Beds · Floor area → "Last sold: Month Year, £price". |
| P58 | EPC rating distribution — enhanced with type + period toggles | **DONE** (Phase 1) | Session 60. Fixed NULL pct_a-g by switching to populated grouped columns (pct_rating_a_b, pct_rating_c, pct_rating_d, pct_rating_e_g). Classic UK EPC arrow-style band labels. Phase 2 (type toggles, period-built) deferred until M3. |
| P59 | Property energy & building profile metric | **DONE** | Session 61. Aggregated 29.2M EPC certificates from Hetzner → 35,889 LSOA-level building profile stats. Populated 6 existing NULL heating columns + added 13 new columns (energy consumption kWh/m²/yr, CO2 t/yr, running costs, mains gas %, solar %, 7 construction age bands). New `building_profile` metric on Property tab with `BuildingProfileChart.tsx`. Heating moved from EpcRatingChart → BuildingProfileChart. Verified: CR5 1RA (95% gas, 1930s housing), SW1A 1AA (62% gas/34% electric, 41% pre-1900), TA24 8SH (47% electric/41% oil, 1% mains gas). |

#### 7D — Lifestyle tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P26 | 15-minute amenities — rethink | **DONE** | Session 65. Renamed "15-Minute Amenities" → "Local Amenities (within 1 km)". AmenityRadarChart: removed crude /100 score, added walk-time estimates (min) per amenity, coloured essential-amenity badges (supermarket/GP/pharmacy/park with green/amber walk-time), cleaner header. |
| P27 | Nearest station — drop chart, keep table only | **DONE** | Removed TransportModeChart from station details in MetricCard.tsx. Added scrollable container with bus/train icon differentiation (Coffee=bus, TrainFront=train). |
| P28 | Transport table: bus vs train icons + bus stops | **DONE (S48)** | Full redesign: StationTable component with type toggle pills (Rail/Metro-DLR/Tram/Bus/Ferry), TransactionTable-matching style (rounded-xl, bg-surface header, alternating rows). Shows: name, lines served, operator, zone, location, distance, step-free/facilities icons. Backend returns all stop types with 8 new NaPTAN columns + enrichment columns (crs, lines, operator, zone, step_free, facilities via TfL API). |
| P60 | Station enrichment — TfL + NR data | **DONE** | S48 code, deployed by S51. EC2 `core_transport_stops` has all 22 columns (crs_code, tiploc_code, lines, operator, zone, step_free, facilities). Migration, NaPTAN re-run, and enrichment all completed. |
| P29 | Sports/recreation — tabulate details, scrollable | **DONE** | Added sports/recreation renderer in MetricCard.tsx with type count badges and scrollable max-h-[220px] list. |
| P30 | Broadband: remove separate fibre + superfast metrics | **DONE** | Removed full_fibre + superfast_broadband metric emissions from tab_lifestyle.py. Cleaned up choropleth layers in area_map.py, MapView.tsx, MapLayerControl.tsx, resultsConstants.ts. |
| P31 | Mobile: remove separate 4G + 5G metrics | **DONE** | Removed mobile_4g_indoor + mobile_5g_outdoor from tab_lifestyle.py, area_map.py, MapView.tsx, MapLayerControl.tsx, resultsConstants.ts. |
| P32 | Cycling to work — rethink | **DONE** | Session 64. Added national percentile, pct_no_car context, cycling_count/total_workers breakdown, context_note. Expanded details now rich instead of blank. |
| P33 | Surface hub destinations in frontend | **DONE** | Session 64. Verified — backend already computes and returns hub destinations attached to stations. Frontend StationTable already renders via DestinationSubTable on row expand. |

#### 7E — Environment tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P34 | Flood risk — drop infographic | **DONE** | Replaced FloodRiskGauge with simple key-value grid (Risk Level, Zone 3, Zone 2, LSOAs Assessed) in MetricCard.tsx. Removed lazy import. |
| P35 | Remove EPC metrics from Environment tab | **DONE** | Removed entire EPC section from tab_environment.py (queries, parent comparison, epc_rating + epc_rating_c_plus metrics). |
| P36 | Air quality PMI trend chart → under PMI metric | **DONE** | AirQualityChart now accepts `pollutant` prop ('pm25'/'no2'). Rendered inline after `air_quality_pm25` metric in ResultsMetricsPanel. Standalone AQ trend CollapsibleSection removed. |
| P37 | NO2 trend chart | **DONE** | NO2 trend chart rendered inline after `air_quality_no2` metric using same AirQualityChart with `pollutant="no2"`. WHO limit: 10 µg/m³. |
| P38 | Park cover — data accuracy + methodology | **Audited** | Session 60. Data is correct: 53.5 ha of 'Public Park Or Garden' within 1km / 314.16 ha circle = 17.0%. 3 parks found, largest 49.8 ha. Methodology sound (1km radius, π×r² denominator). `PARK_TYPES` only includes 'Public Park Or Garden' — could expand to playing fields etc. but that's a policy choice. No bug. |

#### 7F — Community tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P39 | Demographics overview — remove metric comparison | **DONE** | Removed parent comparison display (trend icons + "area X" text) from DemographicsCards.tsx. |
| P40 | Median age — readable age band labels | **DONE** | Changed detail keys to "0–15 years", "16–64 years", "65+ years" with detail_unit="%" in tab_community.py. Frontend generic fallback renders with % suffix. |
| P41 | Work from home — remove (duplicative) | **DONE** | Removed WFH standalone metric + demographics overview card entry from tab_community.py. Cleaned up choropleth in area_map.py, MapView.tsx, personalization.ts, personas.ts, tabs.ts, resultsConstants.ts. |
| P42 | Commute distance labels — human-readable | **DONE** | Changed detail keys to "Under 2 km", "2–10 km", "10–30 km", "30+ km", "Work from home" with detail_unit="%" in tab_lifestyle.py. |
| P43 | Household size labels — fix formatting | **DONE** | Changed detail keys to "1 person", "2 people", "3–4 people", "5+ people" with detail_unit="%" in tab_community.py. |
| P44 | Religion metric — label the headline religion | **DONE** | Dynamic dominant religion detection in tab_community.py. Unit changes to "% {dominant_name}". Human-readable detail keys. |
| P45 | Primary school + school quality → combined metric | **DONE** | Merged in tab_community.py (both area-mode + postcode-mode). local_value = total count, details includes quality_pct, parent_quality_pct, good_count, total_in_area. Frontend MetricCard shows quality summary bar above school list. Removed separate primary_school_quality emission. |
| P46 | Secondary school + school quality → combined metric | **DONE** | Same pattern as P45. Removed secondary_school_quality emission. Cleaned up resultsConstants.ts METRIC_MAP_BINDINGS and tabs.ts METRIC_ICONS. |
| P47 | Consolidate all deprivation indices | **DONE** | Session 60. Hid 7 sub-domain deprivation_* MetricCards (they were redundant — data already in main card). Added Recharts RadarChart to ImdDeprivationBlock showing all 7 domains normalised 0–100. Compact score table below radar. |
| P48 | NHS facilities — tabulate + type filter toggles | **DONE** | Added NhsFacilitiesDetail component in MetricCard.tsx with type filter toggle buttons (pill-shaped, brand-600 active state) and scrollable max-h-[260px] facility list. |

#### 7G — Governance tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P49 | Enrich governance tab content | **DONE** | Session 64. Re-enabled S114 financial health notices from `core_s114_notices` table. Council tax band composition already present. Now 5-7 governance metrics (council tax, local authority, controlling party, water company, S114, electricity DNO, gas GDN). |
| P50 | Utility providers — add electricity/gas alongside water | **DONE** | Session 64. ETL: `etl/sources/electricity_gas.py` using NESO DNO licence area GeoJSON (14 polygons, EPSG:27700). Spatial join with LAD boundaries. GDN derived from DNO region code via static mapping. SQL: `sql/migrate_utilities.sql`. Backend: try/except queries in `tab_governance.py`. Registry entries. 350 LADs populated for both tables. |

---

### Sessions 56–59: UX Redesign + Bug Fixes (not in original queue)

| # | Task | Status | Notes |
|---|------|--------|-------|
| S56 | Section accordion UX + prototype pages | **DONE** | Session 56. Metrics grouped into collapsible sections with icons, summary pills, badges. `sectionGrouping.ts` utility. |
| S57 | 19-fix audit — perf, map, UX, accessibility, data | **DONE** | Session 57. Includes report endpoint fix, badge styling, pill alignment, map width 40%. |
| S58 | Prototype-style metric rendering restored to main portal | **DONE** | Session 58. 14 redesigned detail renderers in RedesignedDetails.tsx, inline row-style MetricCard, section accordion with all sections collapsed by default. |
| S59-1 | Fix map double-creation causing fly-away effect | **DONE** | Session 59. Root cause: `boundary` prop in MapView useEffect deps caused full map destroy+recreate on boundary API response. Fixed with boundaryRef pattern. |
| S59-2 | M1: Choropleth scope widened to full LAD | **DONE** | Session 59. See M1 above. |
| S60-1 | P24: Tenure visual stacked bar + freehold premium | **DONE** | Session 60. Stacked coloured bar for freehold/leasehold splits, amber premium callout. |
| S60-2 | D27-T1: Transaction table extra columns | **DONE** | Session 60. `new_build` green badge, `price_per_sqft` sub-text, `ppd_category` in API. |
| S60-3 | P47: Deprivation radar chart consolidation | **DONE** | Session 60. Hid 7 sub-domain cards, added Recharts RadarChart to main IMD block. |
| S60-4 | P54: Bedroom filter on price history charts | **DONE** | Session 60. By Type/By Beds toggle, 1-5+ bed lines. Backend returns `by_bedrooms` for all search types. |
| S60-5 | P58: EPC rating distribution fix + redesign | **DONE** | Session 60. Switched to grouped columns, classic UK EPC arrow-style bars. |
| S60-6 | P38: Park cover data audit | **Audited** | Session 60. Data and methodology verified correct. No changes needed. |
| S61-1 | P59: Building Profile metric | **DONE** | Session 61. Aggregated 29.2M EPC certs from Hetzner → 35,889 LSOA rows. New building_profile metric with BuildingProfileChart: heating fuel, CO2, energy, costs, construction age, solar. Also completed D16-D20. |
| S62-1 | D21+D22: Glazing, insulation, built form | **DONE** | Session 62. Aggregated windows/walls/roof energy efficiency ratings + glazing type + built form from Hetzner (35,748 LSOAs). 16 new columns on core_epc_lsoa. Two new BuildingProfileChart sections: "Built Form" stacked bar + "Fabric & Insulation" quality bars with glazing breakdown. Cache v29. |
| S63-1 | D29: LLC land designations | **DONE** | Session 63. New `land_designations` metric on Environment tab. ST_Intersects query for Protected_Sites + Area_Management from core_llc_charges. |
| S63-2 | D31: EPC coverage footnote | **DONE** | Session 63. Hetzner Property API returns total_txn/txn_with_area counts. Backend adds data_note to price_per_sqft quality_flags. |
| S63-3 | D27: Transaction table Tier 1 columns | **DONE** | Session 63. Locality sub-text, habitable_rooms, sqft conversion, epc_match_score indicator, area context in expanded rows. |
| S63-4 | P11: Map scroll-follow rethink | **DONE** | Session 63. Auto-follow toggle, widened trigger zone (-15%/0/-55%/0), context-only metrics preserve layers, MapPin indicator on active metric. Cache v30. |
| S64-1 | P49: Enrich Governance tab | **DONE** | Session 64. S114 financial health notices re-enabled. Council tax band composition. |
| S64-2 | P32: Cycling metric rethink | **DONE** | Session 64. National percentile, pct_no_car context, cycling_count/total_workers. |
| S64-3 | P33: Hub destinations verified | **DONE** | Session 64. Already working — backend sends, frontend renders. |
| S64-4 | P7: Decision mode visibility | **DONE** | Session 64. "Prioritised" / "Lower priority" badges on MetricCard. PersonaScoreCard mode-aware label. |
| S64-5 | R15: Outstanding schools walkable | **DONE** | Session 64. 1500m radius proxy. Postcode-only. |
| S64-6 | D27 T2-3: Per-transaction EPC details | **DONE** | Session 64. Hetzner → EC2 proxy → frontend EpcDetailPanel. 25 EPC fields on row expand. |
| S64-7 | P50: Electricity & gas providers | **DONE** | Session 64. NESO DNO GeoJSON ETL + GDN derived. 350 LADs. |
| S65-1 | P5: Takeaway merge | **DONE** | Session 65. Merged "So what?" + "Watch out for" into single coloured pill. |
| S65-2 | P6+P51: Save button simplification | **DONE** | Session 65. Shortlist + Watchlist → single "Save" button. localStorage v2 with v1 migration. |
| S65-3 | P26: Amenities rethink | **DONE** | Session 65. Renamed to "Local Amenities", walk-time estimates, essential-amenity badges. Cache v32. |

---

### Phase 8: Idle Data — Audit & Proposals (session 47, quick wins DONE session 50)

Source: Full DB schema audit — every table, every column checked against backend query usage. Identifies data already sitting in the database that we're not surfacing.

#### Audit Report

**`core_property_transactions` — 12 pre-computed `lsoa_month_*` columns NEVER queried at runtime:**

| Column | What it is |
|--------|-----------|
| `lsoa_month_avg_price` | Average price per LSOA per month |
| `lsoa_month_median_price` | Median price per LSOA per month |
| `lsoa_month_min_price` | Min sale price in that LSOA/month |
| `lsoa_month_max_price` | Max sale price in that LSOA/month |
| `lsoa_month_transaction_count` | Sales volume per LSOA per month |
| `lsoa_month_new_build_count` | New builds per LSOA per month |
| `lsoa_month_freehold_count` | Freehold sales count |
| `lsoa_month_leasehold_count` | Leasehold sales count |
| `lsoa_month_avg_freehold_price` | Avg freehold price |
| `lsoa_month_avg_leasehold_price` | Avg leasehold price |
| `lsoa_month_avg_ppsm` | Avg price/sqm per LSOA per month (only populated by ETL, never queried) |
| `lsoa_month_avg_ppsft` | Avg price/sqft per LSOA per month (same) |

Also idle: `price_per_sqm` (per-transaction, never queried — only sqft is used). ~~`epc_match_score`~~ now exposed in transaction table (session 63, D27).

**`core_price_sqm_lad` (318 rows) + `core_price_sqm_lsoa` (35,670 rows) — entire tables NEVER queried:**
Pre-computed price-per-sqm breakdowns by property type (detached/semi/terraced/flat). Both have `avg_price_per_sqm`, `avg_ppsm_detached`, `avg_ppsm_semi`, `avg_ppsm_terraced`, `avg_ppsm_flat`, `transaction_count`.

**~~`core_hpi_lad` (122,533 rows) — was only used by comparable-areas~~** — **RESOLVED (D14+D15, session 50).** Now powers `official_hpi` metric on Property tab with annual time series, type breakdown, and parent comparison.

**~~`core_epc_lsoa` — heating + CO2 columns were ALL NULL~~** — **RESOLVED (session 61).** All heating + CO2 columns now populated (35,748 LSOAs) via Hetzner EPC aggregation. D16-D20 implemented: construction age, running costs, CO2, heating fuel, solar. D21-D22 (session 62) added glazing, insulation, built form.

**~~Raw EPC CSV — 84 of 93 columns not loaded~~** — **RESOLVED.** Hetzner has ALL 93 columns in `bronze.raw_epc_domestic` (29.2M rows). Sessions 61-62 aggregated most high-value columns (construction age, heating fuel, CO2, running costs, solar, glazing, insulation, built form) to `core_epc_lsoa` (35,748 LSOAs). EC2 `core_epc_domestic` still has only 9 columns (used for transaction matching), but area-level metrics now pull from the fully-populated `core_epc_lsoa`. Remaining per-transaction EPC columns (D27 Tier 2) would need Hetzner Property API enrichment.

#### Proposals — Quick Wins (zero ETL, just query existing data)

| # | Proposal | Effort | Impact | Status | Notes |
|---|----------|--------|--------|--------|-------|
| D10 | Surface freehold premium ratio | Low | Medium | **DONE** | Session 50. Added `freehold_premium` ratio to existing `freehold_leasehold` metric details (freehold avg / leasehold avg). |
| D11 | Surface price spread (min/max/p10/p90) | Low | Medium | **DONE** | Session 50. New `price_spread` metric on Property tab. Shows min-max range + 10th/90th percentiles + spread ratio. Registry entry + persona weights added. |
| D12 | Surface `lsoa_month_*` new build counts | Low | Medium | SKIP | Redundant — existing `new_build_proportion` already computes from raw transactions at runtime. |
| D13 | Surface `core_price_sqm_lad` / `core_price_sqm_lsoa` | Low | Medium | SKIP | Redundant — `tab_property.py` already computes price/sqft from transactions. Separate pre-computed table adds no value. |
| D14+D15 | Official ONS HPI trend + YoY change | Medium | High | **DONE** | Session 50. New `official_hpi` metric on Property tab. Queries `core_hpi_lad` for annual time series (2010+) with type breakdown + parent comparison. YoY change as headline. Registry entry (supports_trend=True) + persona weights. |

#### Proposals — Medium Effort (re-run EPC ETL with additional columns)

| # | Proposal | Effort | Impact | Notes |
|---|----------|--------|--------|-------|
| D16 | Construction age band distribution | Medium | High | **DONE** (P59, session 61). 7 age bands aggregated from Hetzner raw EPC → `core_epc_lsoa`. |
| D17 | Running costs (heating + hot water + lighting) | Medium | High | **DONE** (P59, session 61). avg_heating_cost, avg_hotwater_cost, avg_lighting_cost in `core_epc_lsoa`. |
| D18 | CO2 emissions per property | Medium | Medium | **DONE** (P59, session 61). avg_co2_emissions populated from Hetzner raw EPC aggregation. |
| D19 | Heating fuel type breakdown | Medium | Medium | **DONE** (P59, session 61). heat_gas/electric/oil/district/other/none_pct populated. |
| D20 | Solar/renewable adoption rate | Medium | Medium | **DONE** (P59, session 61). pct_solar (solar water heating OR photovoltaic) in `core_epc_lsoa`. |
| D21 | Glazing + insulation quality | Medium | Low | **DONE** (session 62). Used `windows_energy_eff`, `walls_energy_eff`, `roof_energy_eff` (5-level ratings), `glazed_type` (single/double/triple %), `multi_glaze_proportion`. 16 new columns on `core_epc_lsoa`. BuildingProfileChart "Fabric & Insulation" section with quality bars + glazing breakdown. |
| D22 | Built form distribution (bungalow/maisonette/end-terrace) | Medium | Medium | **DONE** (session 62). Aggregated `built_form` from Hetzner (6 clean categories) → detached/semi/terrace % per LSOA. BuildingProfileChart "Built Form" stacked bar with legend. |

D16–D22 all completed by aggregating from Hetzner's full 93-column EPC table (29.2M rows → 35,748 LSOAs).

#### Proposals — Zero ETL, Census Data Already in `core_census_lsoa`

| # | Proposal | Tab | Status | Notes |
|---|----------|-----|--------|-------|
| D23 | Age distribution metric (median_age with age bands) | Community & Education | **DONE** | Already implemented in earlier sessions. `median_age` metric with age band breakdowns in `tab_community.py`. |
| D24 | Household size distribution metric | Community & Education | **DONE** | Already implemented. `household_composition` metric with 1/2/3-4/5+ person breakdowns in `tab_community.py`. |
| D25 | Born abroad / national identity metric | Community & Education | **DONE** | Already implemented. `born_abroad` metric in `tab_community.py`. |
| D26 | Commute distance distribution metric | Lifestyle & Connectivity | **DONE** | Already implemented. `commute_distance` metric with WFH + distance bands in `tab_lifestyle.py`. |

All D23–D26 were found to be **already implemented** in sessions prior to the audit (session 50 verification).

#### D29 — Surface INSPIRE + LLC at Area Level (current portal) — **DONE** (session 63)

**Implemented:** `land_designations` metric on Environment & Safety tab. Queries `core_llc_charges` for `Protected_Sites` + `Area_Management` charges intersecting local LSOAs via `ST_Intersects`. Shows Yes/No with detail breakdown (protected count, management zones, LSOA coverage %). Parent comparison via EXISTS check for performance. INSPIRE parcels deferred to P53.

~~Both `core_inspire_parcels` (24.3M rows) and `core_llc_charges` (7.7M rows) were ingested in Phase 1 but **zero backend queries exist** for either table.~~

#### D30 — Surface INSPIRE + LLC at Property Level (feeds P53)

For the address-level search feature, these become high-value:

| Dataset | Property-level use | Query |
|---------|-------------------|-------|
| **INSPIRE parcels** | Show exact land parcel boundary on map + title number + plot area in sqm | `ST_Contains(geom, property_point)` or nearest parcel |
| **LLC `LU_Residential`** | Residential land-use charge polygon for that property | `ST_Contains(geom, property_point)` |
| **LLC `Area_Management`** | "This property is within a conservation area" / "TPO applies" | `ST_Contains(geom, property_point)` |

Already covered under D28-3 and D28-4 but noting here that the data is **already ingested and indexed** — no ETL needed, just property-level query endpoints.

#### D27 — Enrich Transaction Table with Additional Columns — **Tier 1 DONE** (session 63)

**Done (Tier 1):** locality sub-text, habitable_rooms "(X rooms)", sqft conversion, epc_match_score low-confidence indicator, area context in expanded rows (avg price, median, sales count). No new table columns — uses sub-text and expanded rows.

Expand the sales history table beyond the current 8 columns. Three tiers based on effort required.

**Currently showing (8 columns):**

| Column | Source |
|--------|--------|
| Date | `date_of_transfer` |
| Address | `CONCAT(saon, paon, street, town)` |
| Price | `price` |
| Type | `property_type` (D/S/T/F) |
| Beds | `bedrooms_estimated` (est. from habitable rooms) |
| Size | `floor_area_sqm` |
| Tenure | `duration` (F/L) |
| EPC | `epc_rating` (A-G) |

**Tier 1 — Zero effort (already in DB, just add to SELECT):**

| Column | Display as | Notes |
|--------|-----------|-------|
| `old_new` | New Build | Y/N flag — "Was this a new build when sold?" |
| `price_per_sqft` | £/sqft | Already computed per-row |
| `price_per_sqm` | £/sqm | Metric variant — pick one or show both |
| `locality` | Locality | Sub-area name (often blank but useful when present) |
| `town` | Town | Currently folded into address, could be separate |
| `ppd_category` | PPD Category | A = standard, B = additional (transfers, repossessions) |
| `habitable_rooms` | Rooms | Raw room count from EPC |
| floor_area → sqft | Size (sqft) | Easy conversion from sqm |
| `epc_match_score` | EPC Confidence | Match confidence 0-1 (niche but transparent) |

**Tier 1b — Zero effort (contextual, from `lsoa_month_*` columns):**

| Column | Display as | Notes |
|--------|-----------|-------|
| `lsoa_month_avg_price` | Area Avg | "You paid X, area average was Y" |
| `lsoa_month_median_price` | Area Median | Same but median |
| `lsoa_month_transaction_count` | Sales/Month | Market activity context for that LSOA/month |

**Tier 2 — Requires EPC ETL re-run (blocked by M3), high value:**

| EPC Column | Display as | Example | Notes |
|-----------|-----------|---------|-------|
| `CONSTRUCTION_AGE_BAND` | Period Built | "1950-1966" | When was it built? Very popular. |
| `BUILT_FORM` | Built Form | "End-Terrace", "Bungalow" | More granular than D/S/T/F |
| `MAINHEAT_DESCRIPTION` | Heating | "Gas boiler, radiators" | What heats the property? |
| `MAIN_FUEL` | Fuel Type | "mains gas", "oil" | Gas vs electric vs oil |
| `ENERGY_CONSUMPTION_CURRENT` | Energy kWh/yr | "15,230" | Annual energy consumption |
| `CO2_EMISSIONS_CURRENT` | CO2 t/yr | "3.2" | Carbon footprint |
| `HEATING_COST_CURRENT` | Heating £/yr | "£824" | Annual heating cost at EPC time |
| `HOT_WATER_COST_CURRENT` | Hot Water £/yr | "£142" | Annual hot water cost |
| `LIGHTING_COST_CURRENT` | Lighting £/yr | "£96" | Annual lighting cost |
| `WINDOWS_DESCRIPTION` | Glazing | "Double glazed" | Window quality |
| `WALLS_DESCRIPTION` | Walls | "Cavity wall, insulated" | Construction/insulation |
| `SOLAR_WATER_HEATING_FLAG` | Solar | Y/N | Has solar water heating? |
| `PHOTO_SUPPLY` | Solar PV | "2.5 kWp" | Has photovoltaic panels? |
| `MAINS_GAS_FLAG` | Mains Gas | Y/N | Connected to gas network? |
| `NUMBER_HEATED_ROOMS` | Heated Rooms | "5" | vs total habitable rooms |
| `FLOOR_LEVEL` | Floor | "1st", "Ground" | For flats — which floor? |
| `TENURE` | EPC Tenure | "owner-occupied" | More granular than F/L |
| `INSPECTION_DATE` | EPC Date | "2022-03-15" | When was the EPC done? |
| `POTENTIAL_ENERGY_RATING` | Potential EPC | "B" | What property *could* achieve |

**Tier 3 — Requires EPC ETL re-run (blocked by M3), moderate value:**

| EPC Column | Display as |
|-----------|-----------|
| `ROOF_DESCRIPTION` | Roof construction/insulation |
| `FLOOR_DESCRIPTION` | Floor insulation |
| `LOW_ENERGY_LIGHTING` | % low-energy lighting |
| `EXTENSION_COUNT` | Number of extensions |
| `WIND_TURBINE_COUNT` | Wind turbines |
| `MULTI_GLAZE_PROPORTION` | % double/triple glazed |

**Implementation:** Tier 1 can be done immediately. Tiers 2-3 blocked by M3 (EPC re-ingestion). Frontend table needs horizontal scroll for wider layout.

**Status:** All tiers **DONE**. Tier 1: sessions 60+63. Tiers 2-3: session 64. Hetzner endpoint `/transactions/epc/by-transaction/{id}` → EC2 proxy `/transactions/{id}/epc` → frontend `EpcDetailPanel` (lazy-loaded on row expand). Shows: construction age, built form, heating, fuel, energy kWh/yr, CO2 t/yr, running costs, glazing, walls, roof, floor, solar, mains gas, heated rooms, floor level, tenure, EPC current+potential ratings.

#### D28 — Per-Property Data Sources for Address-Level Search (feeds P53)

New feature: search by **specific address** and show everything we know about THAT property. Requires ingesting additional free/OGL datasets that provide per-property (not just per-area) information. This is the data sourcing plan for P53.

**Datasets we already have (just need property-level queries):**

| # | Dataset | Licence | Join key | What it adds at property level | Current area-level coverage |
|---|---------|---------|----------|-------------------------------|----------------------------|
| D28-1 | **Land Registry PPD** (existing) | OGL v3 | address match | Full transaction history for that address — every sale, price, date, type, tenure | Yes — `core_property_transactions` |
| D28-2 | **EPC certificates** (existing, expand columns) | OGL v3 | address/UPRN | All 93 columns: energy rating, floor area, construction age, heating system, running costs, glazing, walls, roof, CO2, solar, etc. | Partially — 9 of 93 columns loaded |
| D28-3 | **INSPIRE Index Polygons** (existing) | OGL v3 | spatial (coordinate) | Land parcel boundary + title number for that property | Yes — `core_inspire_parcels` |
| D28-4 | **Local Land Charges** (existing) | OGL v3 | spatial (coordinate) | Planning charges, tree preservation orders, conservation area designations, smoke control zones affecting that property | Yes — `core_llc_charges` |
| D28-5 | **Flood zones** (existing) | OGL v3 | spatial (coordinate) | "This property is in Flood Zone 2" (specific, not % of LSOAs) | Yes — area-level `core_flood_zones` |
| D28-6 | **Crime** (existing) | OGL v3 | spatial (nearby) | Crimes within 200m of this address in last 12 months, by type | Yes — LSOA-level `core_crime_lsoa` |
| D28-7 | **Noise** (existing) | OGL v3 | spatial (coordinate) | Road/rail noise level at this exact location (dB) | Yes — `core_noise` |
| D28-8 | **Broadband** (existing) | OGL v3 | postcode | Max download/upload speed at this postcode | Yes — area-level in `tab_lifestyle` |

**New datasets to ingest (all free, OGL or equivalent):**

| # | Dataset | Licence | Source URL | Records | Join key | What it adds | Effort |
|---|---------|---------|-----------|---------|----------|-------------|--------|
| D28-9 | **Council Tax Band (VOA)** | OGL v3 | `gov.uk/check-council-tax-bands` / VOA bulk download | ~26M | address match | Band A-H + annual cost. Everyone asks this. | Medium |
| D28-10 | **Listed Building status (Historic England)** | OGL v3 | `historicengland.org.uk/listing/the-list/data-downloads` | ~400K | UPRN / coordinate | Grade I, II*, II status + listing description. Affects planning rights. | Low |
| D28-11 | **Ground stability / subsidence (BGS GeoSure)** | OGL v3 | `bgs.ac.uk/datasets/geosure/` | National grid | coordinate | Shrink-swell clay risk, landslip, dissolution, compressible ground. Affects insurance + structure. | Medium |
| D28-12 | **Planning applications** | OGL v3 (council data) | Individual council APIs / PlanIt aggregator | Millions | address/UPRN | Extensions, new builds, change of use, demolitions — submitted, approved, refused. | High |
| D28-13 | **Corporate & Overseas Ownership (CCOD/OCOD)** | OGL v3 | `gov.uk/government/collections/price-paid-data` (Land Registry) | ~6M titles | title number / address | Company name + country for every corporate-owned property. "Is this owned by a company?" | Medium |
| D28-14 | **Radon risk (UKHSA)** | Free (public health) | `ukradon.org` / UKHSA bulk data | National | postcode | Radon affected area probability band (1-5%). Health risk, especially SW England. | Low |
| D28-15 | **OS Open UPRN** | OGL v3 | `osdatahub.os.uk/downloads/open/OpenUPRN` | ~41M | UPRN = canonical ID | Lat/lng for every UPRN. Enables reliable matching across ALL other datasets. Foundation dataset. | Medium |

**How these feed the address-level view (P53):**

The address search would resolve to a specific UPRN (via D28-15), then fan out queries:
1. **Property identity**: address, UPRN, land parcel (D28-3), council tax band (D28-9), listed status (D28-10)
2. **Transaction history**: every sale of this property (D28-1), with % change between sales
3. **EPC deep dive**: full energy certificate — rating, potential, construction age, heating, costs, glazing, walls, roof, solar, CO2 (D28-2)
4. **Legal & planning**: LLC charges (D28-4), planning applications (D28-12), corporate ownership (D28-13)
5. **Environmental risks**: flood zone (D28-5), ground stability (D28-11), radon (D28-14), noise (D28-7)
6. **Local context**: nearby crime (D28-6), broadband speed (D28-8)
7. **Area context**: pull in existing LSOA/LAD metrics as neighbourhood backdrop

**Priority order for ingestion:**
1. **D28-15 OS Open UPRN** — foundation, improves all other joins
2. **D28-9 Council Tax Band** — highest buyer demand, easy to display
3. **D28-10 Listed Building** — low effort, high impact for affected properties
4. **D28-14 Radon** — low effort, important safety data
5. **D28-11 Ground stability** — medium effort, high insurance/structural relevance
6. **D28-13 Corporate ownership** — medium effort, investor/transparency interest
7. **D28-12 Planning applications** — highest effort, highest long-term value

---

#### D31 — Add EPC coverage footnote to price_per_sqm metrics — **DONE** (session 63)

**Implemented:** Hetzner Property API `/aggregate` and `/aggregate-by-lad` now return `total_txn` and `txn_with_area` counts. EC2 backend computes `data_note` (e.g. "Based on 97.3% of sales with EPC floor area (36 of 37)") and adds to `price_per_sqft` metric details. Auto-picked up by `build_metric_contract()` → `quality_flags` → rendered as footnote by MetricCard.

---

#### D32 — P53 EPC Lookup: Show Current EPC + EPC at Time of Sale

When a user searches by address (P53), they want to see **all** EPC data for that property — not just what the transaction-matching engine found. Two distinct use cases:

1. **Current/most recent EPC certificate** — query `bronze.raw_epc_domestic` directly by address (or UPRN when available). This gives ~92% coverage since most properties have had at least one EPC, regardless of when they last sold. A property sold in 2005 (pre-EPC) almost certainly has a current EPC today.

2. **EPC at time of each sale** — use the transaction-matching results from `silver.match_results` to show which EPC certificate was active when each sale occurred. This is what the matching engine already provides.

**Key insight:** The matching engine (80.1% coverage, 12 rules) solves area-level aggregation (price_per_sqm averages across postcodes/LSOAs). But for address-level lookup, we bypass the matching engine entirely and query the EPC table directly — much simpler, much higher coverage.

**Implementation approach:**
- P53 address search resolves to a canonical address (or UPRN)
- Query `bronze.raw_epc_domestic` for all certificates at that address, ordered by `lodgement_date DESC`
- Show most recent certificate prominently (floor area, EPC rating, energy costs, recommendations)
- Show historical certificates as timeline
- Cross-reference with `silver.match_results` to link specific EPCs to specific sales

**Priority:** Part of P53 (address-level search feature). Depends on D28 (per-property data sources).

---

#### D33 — NPD Workaround: Catchment Probability Model Without Pupil Data

LocRating's most unique features (catchment heatmaps, feeder/destination school tracking, local school attendance) depend on the National Pupil Database (NPD) — restricted DfE data requiring a formal data sharing agreement. We can't access NPD (no formal entity yet).

**Workaround — reconstruct ~80% of the insight from public signals:**

Inputs we HAVE:
- **LDO (Last Distance Offered)** — effective catchment radius (from LA websites)
- **Admissions data** — applications, offers, oversubscription ratio (DfE EES, OGL)
- **School capacity + pupil count** — from GIAS
- **Geographic positions** — every school + every postcode/LSOA centroid
- **School phase + type** — eligibility constraints (age, gender, faith)

What we can DERIVE:
1. **Catchment probability model**: For any postcode, compute probability of admission to each nearby school using distance/LDO ratio × oversubscription pressure × capacity utilisation. Pre-compute school→LSOA probability matrix (~500K rows).
2. **Feeder school inference**: Find primary/secondary pairs whose LDO circles overlap. Weight by proximity and capacity ratio.
3. **Neighbourhood school attendance estimate**: For each LSOA, identify overlapping school catchments and allocate proportionally by distance-decay.
4. **Distribution of existing pupils**: Inverse — shade LSOAs within a school's catchment with intensity proportional to proximity.

**Implementation**: `compute_catchment.py` on Hetzner. Pre-compute annually when LDO/admissions data refreshes. Store in `schools.catchment_model` table.

**Priority:** Part of School Intelligence Module Phase 6. Depends on LDO data collection.

---

#### D34 — School Intelligence Module (Full Plan)

Comprehensive school module matching/exceeding LocRating.com. Hosted on Hetzner, EC2 calls via API. Full plan at: `.claude/plans/mutable-nibbling-flurry.md`

**13 database tables, 16 ETL scripts, FastAPI service on port 8082, SchoolTable + SchoolDetailPanel + SchoolComparison frontend components.**

**7 implementation phases (~12-16 sessions total):**
1. Data Foundation (GIAS, Ofsted history, KS2/KS4/KS5)
2. School API + Rich SchoolTable
3. Demographics, Workforce, Finances, Parent View
4. Nurseries + Admissions + Independent Fees
5. Shortlists + Comparison + League Tables
6. Walking Routes + Catchment Model
7. Polish + Academic Velocity + Heatmaps

**Priority:** Major feature. Start after current Hetzner data platform work stabilises.

---

### Parked / Won't Do

| # | Task | Rec | Notes |
|---|------|-----|-------|
| R6 | Reduce `execute_values` page_size 10000 → 1000 in ETL | **SKIP** | ETL-only. No user-facing impact. |
| R23 | PgBouncer connection pooling | **DEFER** | Adequate at launch. Revisit when connections bottleneck. |

---

## DB State (session 37)

| Table | Rows | Notes |
|-------|------|-------|
| core_property_transactions | 30.4M | E=29.0M, W=1.45M, ~5.3M with EPC backfill |
| core_postcodes | 1.75M | E+W+S |
| core_crime_lsoa | 5.96M | E+W (incl. GMP verified) |
| core_noise | 1.43M | 367/367 DEFRA tiles |
| core_inspire_parcels | 24,255,962 | 318 authorities |
| core_llc_charges | 7,720,311 | 141 authorities |
| core_flood_zones | 3,536,992 | FZ2 82.6%, FZ3 17.4% |
| core_flood_lsoa | 33,755 | Per-LSOA flood exposure (derived) |
| core_lad_county_lookup | 318 | All 6 metro counties now populated |
| core_place_boundaries_union | 9,565 | Pre-computed ST_Union per place (new) |
| core_price_by_bedrooms_lad | 144,906 | LAD/year/type/bedroom aggregation (new) |
| core_census_religion_ward | 7,638 | Census 2021 TS031 (now wired to tab) |

### Google Drive Assets

| Item | Location |
|------|----------|
| DB dump v2 | `gdrive:PropertyPulse/ukproperty_20260413_v2.dump` |
| core_epc_domestic backup | `gdrive:PropertyPulse/core_epc_domestic.dump` (1.2 GB) |
| INSPIRE raw | `gdrive:PropertyPulse/raw_downloads/INSPIRE/` |
| LLC raw | `gdrive:PropertyPulse/raw_downloads/LLC/` |
| Flood GeoPackage | `gdrive:PropertyPulse/raw_downloads/` |
| Codebase snapshot (latest) | `gdrive:PropertyPulse/codebase_review_20260417/` (360 files) |
| Public review repo | https://github.com/machobowa17/PropertyPulse-review |

---

## Architecture Decisions (NEVER violate)

1. Session key is the ONLY input to all API endpoints
2. PRICE_TYPES = ('D','S','T','F') — always exclude 'O'
3. `habitable_rooms` ≠ bedrooms — ALWAYS "N bed (est.)" with footnote
4. No hardcoded values — use constants.py
5. Legacy modules stay in etl/legacy/
6. Source modules don't call each other — use depends_on
7. Derived modules never download — only query core_*
8. HAVING COUNT(*) >= 3 — privacy suppression
9. Tab services never access session directly — receive unpacked params
10. Data file policy: move ingested files to `gdrive:PropertyPulse/raw_downloads/` via rclone (never delete)
11. **Metric registry is the source of truth for metric metadata** (adopted session 25)
