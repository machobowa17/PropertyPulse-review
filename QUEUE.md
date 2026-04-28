# PropertyPulse — Master Work Queue

Last updated: 2026-04-28 (session 60)

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
- `test_brutal.py`: 13-section, 447-test brutal stress test (adversarial inputs, math correctness, boundary integrity, ethnicity accuracy, cross-search consistency, 5×5 tab×search matrix, Playwright UI)

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
| R15 | Isochrone school catchments — Outstanding schools within 15-min walk | Pending | Family persona "holy grail". 90% infra exists. |
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
| P5 | Merge "So what?" + "Watch out for" → single "Takeaway" | Pending | Across all tabs. Simpler, easier to tune per persona. **To be discussed.** |
| P6 | Shortlisted vs Watch buttons — rethink UX | Pending | Unclear what each does, where saved, what the difference is. Sort out or simplify. |
| P7 | Decision mode (Buy/Rent/Invest) — make impact visible | Pending | User can't see what changes when toggling. Need evidence of effect. **To be discussed.** |
| P8 | Download report button broken | **DONE** | Fixed in session 57 (commit `2b6150f`). Report endpoint returns valid PDF (reportlab on EC2). Verified session 59: 200 OK, 18KB PDF for CR5 1RA. |
| P9 | Scotland + NI coverage | Pending | To be discussed — scope, data sources, feasibility. |
| P10 | DB scan: unused table data → new metrics | **DONE** | Audit completed session 47. See "Phase 8: Idle Data — Audit & Proposals" below. |
| P51 | Saved areas — clarify persistence model | Pending | Where does it save? How does it remember the user? Currently localStorage only — no cross-device sync, no account system. Clarify UX and consider if this is sufficient. |
| P52 | Full E2E test + deploy after Phase 7 | Pending | After all Phase 7 changes: run full Playwright suite, tsc -b, vite build. Deploy latest to EC2. Upload codebase to Google Drive. Save context, queue, memory. |
| P53 | Single address search — show all data for a specific property | Pending | Allow searching by full address (e.g. "14 Acacia Avenue, SW1A 1AA"). Display all non-GDPR-sensitive data we hold: transaction history, EPC ratings/details, floor area, property type, tenure, flood zone, LLC charges, INSPIRE parcel, noise levels, broadband, etc. All public registry data — no personal data. Requires: (1) resolve endpoint to handle address-level search, (2) new address-level results view, (3) DB scan to catalogue all address-level data available. Includes classic UK EPC certificate visual (arrow-style A-G chart with pointer) for the individual property. Data plan: see D28. |
| P54 | Add bedroom layer to price history charts | Pending | M3 done but bedroom coverage is ~50% post-2020 (not 80%+ as hoped). Still viable with quality_flag. Add bedroom breakdown (1-bed, 2-bed, 3-bed, 4-bed, 5+) as filter toggle on price history charts. No longer blocked. |

#### 7B — Map

| # | Task | Status | Notes |
|---|------|--------|-------|
| P11 | Map scroll-follow logic — rethink UX | Pending | Buggy and confusing. Layers change as user scrolls/hovers but behaviour is unpredictable. Needs fundamental rethink. Audit across ALL 5 tabs. |
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
| P58 | EPC rating distribution — enhanced with type + period toggles | Pending | Redesign `epc_energy_score` metric expanded view: show property count per band (not just %), classic UK EPC arrow-style visual (A green → G red), toggle by property type (D/S/T/F), toggle by period built (requires `CONSTRUCTION_AGE_BAND` from M3). **Phase 1 (now):** type toggle using existing `core_epc_lsoa` + `core_property_transactions` EPC match data. **Phase 2 (after M3):** add period-built toggle. |
| P59 | Property energy & building profile metric | Pending | New metric on Property tab showing area-level EPC-derived building characteristics in a table with type toggles (same pattern as freehold/leasehold, housing stock tables): heating type breakdown (gas/electric/oil/district), fuel type, energy consumption (kWh/yr), CO2 emissions (t/yr), running costs (heating £/yr, hot water £/yr, lighting £/yr), glazing quality, wall construction/insulation, solar adoption, mains gas connectivity. **Fully blocked by M3** — requires EPC re-ingestion with additional columns (D17-D21). All columns exist in raw EPC CSV but are not currently loaded. |

#### 7D — Lifestyle tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P26 | 15-minute amenities — rethink | Pending | Current implementation needs rethink. **To be discussed.** |
| P27 | Nearest station — drop chart, keep table only | **DONE** | Removed TransportModeChart from station details in MetricCard.tsx. Added scrollable container with bus/train icon differentiation (Coffee=bus, TrainFront=train). |
| P28 | Transport table: bus vs train icons + bus stops | **DONE (S48)** | Full redesign: StationTable component with type toggle pills (Rail/Metro-DLR/Tram/Bus/Ferry), TransactionTable-matching style (rounded-xl, bg-surface header, alternating rows). Shows: name, lines served, operator, zone, location, distance, step-free/facilities icons. Backend returns all stop types with 8 new NaPTAN columns + enrichment columns (crs, lines, operator, zone, step_free, facilities via TfL API). |
| P60 | Station enrichment — TfL + NR data | **DONE** | S48 code, deployed by S51. EC2 `core_transport_stops` has all 22 columns (crs_code, tiploc_code, lines, operator, zone, step_free, facilities). Migration, NaPTAN re-run, and enrichment all completed. |
| P29 | Sports/recreation — tabulate details, scrollable | **DONE** | Added sports/recreation renderer in MetricCard.tsx with type count badges and scrollable max-h-[220px] list. |
| P30 | Broadband: remove separate fibre + superfast metrics | **DONE** | Removed full_fibre + superfast_broadband metric emissions from tab_lifestyle.py. Cleaned up choropleth layers in area_map.py, MapView.tsx, MapLayerControl.tsx, resultsConstants.ts. |
| P31 | Mobile: remove separate 4G + 5G metrics | **DONE** | Removed mobile_4g_indoor + mobile_5g_outdoor from tab_lifestyle.py, area_map.py, MapView.tsx, MapLayerControl.tsx, resultsConstants.ts. |
| P32 | Cycling to work — rethink | Pending | Current presentation needs rethink. **To be discussed.** |
| P33 | Community connectivity — compute travel to named hubs | Pending | Needs actual computed travel times to named major hubs (airports, city centres) relative to the search location. Not a generic metric. |

#### 7E — Environment tab

| # | Task | Status | Notes |
|---|------|--------|-------|
| P34 | Flood risk — drop infographic | **DONE** | Replaced FloodRiskGauge with simple key-value grid (Risk Level, Zone 3, Zone 2, LSOAs Assessed) in MetricCard.tsx. Removed lazy import. |
| P35 | Remove EPC metrics from Environment tab | **DONE** | Removed entire EPC section from tab_environment.py (queries, parent comparison, epc_rating + epc_rating_c_plus metrics). |
| P36 | Air quality PMI trend chart → under PMI metric | **DONE** | AirQualityChart now accepts `pollutant` prop ('pm25'/'no2'). Rendered inline after `air_quality_pm25` metric in ResultsMetricsPanel. Standalone AQ trend CollapsibleSection removed. |
| P37 | NO2 trend chart | **DONE** | NO2 trend chart rendered inline after `air_quality_no2` metric using same AirQualityChart with `pollutant="no2"`. WHO limit: 10 µg/m³. |
| P38 | Park cover — data accuracy + methodology | Pending | CR5 1RA shows 17% vs London 21.3% — suspect wrong for a green area. (1) Verify data accuracy. (2) Rethink methodology: 1km radius may not be right, consider LSOA-scoped instead. |

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
| P49 | Enrich governance tab content | Pending | Currently thin. Add more: council performance, factual info, non-comparative text summaries. Research what's available. |
| P50 | Utility providers — add electricity/gas alongside water | Pending | Water company is shown but no other utilities. Research available data sources for electricity/gas distribution companies by postcode. |

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

Also idle: `price_per_sqm` (per-transaction, never queried — only sqft is used), `epc_match_score` (EPC→transaction match confidence, never exposed).

**`core_price_sqm_lad` (318 rows) + `core_price_sqm_lsoa` (35,670 rows) — entire tables NEVER queried:**
Pre-computed price-per-sqm breakdowns by property type (detached/semi/terraced/flat). Both have `avg_price_per_sqm`, `avg_ppsm_detached`, `avg_ppsm_semi`, `avg_ppsm_terraced`, `avg_ppsm_flat`, `transaction_count`.

**`core_hpi_lad` (122,533 rows) — only used by comparable-areas algorithm, NEVER displayed:**
Official ONS House Price Index. Monthly time series with: `average_price`, `index_value`, `sales_volume`, `detached_price`, `semi_detached_price`, `terraced_price`, `flat_price`, `yearly_change_pct`. Could power an official HPI trend chart or validate our transaction-derived prices.

**`core_epc_lsoa` — heating + CO2 columns exist in schema but are ALL NULL (0 of 35,672 rows populated):**
`avg_co2_emissions`, `heat_gas_pct`, `heat_electric_pct`, `heat_oil_pct`, `heat_district_pct`, `heat_other_pct`, `heat_none_pct` — schema is ready but the ETL aggregation step never populated these. The heating columns ARE queried by `tab_property.py` but return NULLs. Fixing requires re-running EPC ETL with additional raw columns (`MAIN_FUEL`, `CO2_EMISSIONS_CURRENT`).

**Raw EPC CSV — 84 of 93 columns not loaded:**
ETL loads only 9 columns (`LMK_KEY`, `ADDRESS1-3`, `POSTCODE`, `LODGEMENT_DATE`, `TOTAL_FLOOR_AREA`, `NUMBER_HABITABLE_ROOMS`, `CURRENT_ENERGY_RATING`). Notable idle raw columns that would need fresh ETL ingestion:

| Raw CSV column | Potential metric |
|---------------|-----------------|
| `CONSTRUCTION_AGE_BAND` | "Period built" distribution (Victorian / Inter-war / Post-2000 etc.) |
| `WALLS_DESCRIPTION`, `ROOF_DESCRIPTION` | Construction quality insights |
| `HEATING_COST_CURRENT`, `HOT_WATER_COST_CURRENT`, `LIGHTING_COST_CURRENT` | Running costs estimate |
| `CO2_EMISSIONS_CURRENT` | Carbon footprint per property |
| `MAIN_FUEL` | Gas/electric/oil heating breakdown (would populate the empty `core_epc_lsoa` heating columns) |
| `SOLAR_WATER_HEATING_FLAG`, `PHOTO_SUPPLY` | Renewable energy adoption rate |
| `BUILT_FORM` | Granular type (bungalow, maisonette, end-terrace, etc.) |
| `ENVIRONMENT_IMPACT_CURRENT/POTENTIAL` | Environmental impact score |
| `ENERGY_CONSUMPTION_CURRENT` | kWh/year energy use |
| `MAINHEAT_DESCRIPTION` | Specific heating system (e.g. "Gas boiler, radiators") |
| `WINDOWS_DESCRIPTION` | Double/triple glazing prevalence |
| `FLOOR_DESCRIPTION` | Floor insulation quality |
| `TENURE` | Ownership type at individual property level (owner-occupied / rented / social) |

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
| D16 | Construction age band distribution | Medium | High | Requires adding `CONSTRUCTION_AGE_BAND` to EPC ETL `_COLUMN_MAP` + new LSOA aggregation. Answers "what era were properties here built?" |
| D17 | Running costs (heating + hot water + lighting) | Medium | High | Requires adding 3 cost columns to EPC ETL. Powerful for buyers: "how much does it cost to run a home here?" |
| D18 | CO2 emissions per property | Medium | Medium | Requires `CO2_EMISSIONS_CURRENT`. Environmental metric. Would populate the empty `avg_co2_emissions` in `core_epc_lsoa`. |
| D19 | Heating fuel type breakdown | Medium | Medium | Requires `MAIN_FUEL`. Would populate the empty `heat_gas_pct` etc. in `core_epc_lsoa`. Tab_property.py already queries these — just needs data. |
| D20 | Solar/renewable adoption rate | Medium | Medium | Requires `SOLAR_WATER_HEATING_FLAG` + `PHOTO_SUPPLY`. Trending metric for eco-conscious buyers. |
| D21 | Glazing + insulation quality | Medium | Low | Requires `WINDOWS_DESCRIPTION` + `FLOOR_DESCRIPTION`. Niche but relevant to energy bills. |
| D22 | Built form distribution (bungalow/maisonette/end-terrace) | Medium | Medium | Requires `BUILT_FORM`. More granular than D/S/T/F. Shows "is this a bungalow area?" |

All D16–D22 require re-running EPC ETL with additional columns. M3 (EPC table restore) is now DONE — these need new column extraction from raw CSV, not just the table restore.

#### Proposals — Zero ETL, Census Data Already in `core_census_lsoa`

| # | Proposal | Tab | Status | Notes |
|---|----------|-----|--------|-------|
| D23 | Age distribution metric (median_age with age bands) | Community & Education | **DONE** | Already implemented in earlier sessions. `median_age` metric with age band breakdowns in `tab_community.py`. |
| D24 | Household size distribution metric | Community & Education | **DONE** | Already implemented. `household_composition` metric with 1/2/3-4/5+ person breakdowns in `tab_community.py`. |
| D25 | Born abroad / national identity metric | Community & Education | **DONE** | Already implemented. `born_abroad` metric in `tab_community.py`. |
| D26 | Commute distance distribution metric | Lifestyle & Connectivity | **DONE** | Already implemented. `commute_distance` metric with WFH + distance bands in `tab_lifestyle.py`. |

All D23–D26 were found to be **already implemented** in sessions prior to the audit (session 50 verification).

#### D29 — Surface INSPIRE + LLC at Area Level (current portal)

Both `core_inspire_parcels` (24.3M rows) and `core_llc_charges` (7.7M rows) were ingested in Phase 1 but **zero backend queries exist** for either table. They sit completely idle today.

**LLC — `Area_Management` charges (6,037 rows across 116 authorities):**

| Metric | Tab | Query approach | Notes |
|--------|-----|---------------|-------|
| **Conservation area coverage** | Environment & Safety or Local Governance | `ST_Intersects` of LSOA/LAD boundary with `Area_Management` charge polygons | "This area includes a conservation area" / "X% of the area is within a conservation zone" |
| **Active land charges count** | Local Governance | Count `LU_Residential` charges per LSOA/LAD | Total registered charges — shows legal activity density |

**INSPIRE — marginal at area level:**

| Metric | Tab | Query approach | Notes |
|--------|-----|---------------|-------|
| **Avg land parcel size** | Property & Market | `AVG(ST_Area(geom::geography))` per LSOA | "Average plot size: 280 sqm" — niche, mildly interesting |

**Verdict:** LLC `Area_Management` (conservation areas) is the clear win for the current portal. INSPIRE parcels and LLC `LU_Residential` are per-property datasets that belong in P53.

#### D30 — Surface INSPIRE + LLC at Property Level (feeds P53)

For the address-level search feature, these become high-value:

| Dataset | Property-level use | Query |
|---------|-------------------|-------|
| **INSPIRE parcels** | Show exact land parcel boundary on map + title number + plot area in sqm | `ST_Contains(geom, property_point)` or nearest parcel |
| **LLC `LU_Residential`** | Residential land-use charge polygon for that property | `ST_Contains(geom, property_point)` |
| **LLC `Area_Management`** | "This property is within a conservation area" / "TPO applies" | `ST_Contains(geom, property_point)` |

Already covered under D28-3 and D28-4 but noting here that the data is **already ingested and indexed** — no ETL needed, just property-level query endpoints.

#### D27 — Enrich Transaction Table with Additional Columns

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

**Status:** Tier 1 partial — **DONE** (session 60). Added `new_build` (green "New" badge), `price_per_sqft` (£/sqft sub-text under price), `ppd_category` to API response. Remaining Tier 1 columns (locality, rooms, sqft conversion, epc_match_score, lsoa_month_*) deferred.

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

#### D31 — Add EPC coverage footnote to price_per_sqm metrics

Metrics computed from EPC-matched data (price_per_sqm, price_per_sqft, floor area averages, LSOA avg ppsm/ppsft) currently report aggregates without disclosing what proportion of transactions contributed. E.g. if an LSOA has 100 transactions but only 60 have floor area, the "average price per sqm" is based on 60 — user has no idea.

**Fix:** Add a quality_flag or footnote like "Based on N of M transactions with floor area data" to any metric derived from EPC-matched columns. Use the existing `quality_flags` system in `build_metric_contract()`.

**Priority:** Medium. Coverage jumped from 42% → 81% with Hetzner matching (session 53), so the issue is less severe now, but still worth transparency. Generic quality_notes already exists in metric registry ("Depends on availability of matched floor-area records from EPC data."). Specific N/M counts require Hetzner property API to return `with_area_count` / `total_count` — not a quick backend-only fix.

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
