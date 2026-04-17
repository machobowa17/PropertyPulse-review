# PropertyPulse — Master Work Queue

Last updated: 2026-04-17 (session 38)

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

Source: Sessions 37-38. EC2 t4g.small (eu-west-2), 80 GB gp3 EBS, Elastic IP 16.60.67.248. Domain: paintedstock.com (Cloudflare). All data restored and verified (exact row counts match local).

| # | Task | Status | Notes |
|---|------|--------|-------|
| 13 | AWS: Create account, configure eu-west-2 | DONE | Elastic IP 16.60.67.248 |
| 14 | AWS: Launch t4g.small + 80 GB gp3 EBS | DONE | ARM64 Graviton, 2 vCPU, 2 GB RAM |
| 15 | AWS: Provision Docker + docker-compose (AL2023, ARM) | DONE | Docker 27.x, Compose v2.29.2, 2 GB swap |
| 16 | AWS: `pg_dump` → upload → `pg_restore` on EC2 | DONE | 18 GB dump, all 30.4M transactions + indexes + MVs restored. `imresamu/postgis:16-3.4` (ARM64) |
| 17 | AWS: Docker Compose (API + frontend/nginx + Redis + PG) | DONE | `docker-compose.ssl.yml` override. No S3/CloudFront — nginx serves frontend directly |
| 18 | AWS: DNS + TLS (Let's Encrypt) | DONE | `paintedstock.com` via Cloudflare DNS. Let's Encrypt cert (expires 2026-07-16) |
| 19 | AWS: GitHub Actions CI/CD | Pending | Not yet needed — deploying via rsync + rebuild |

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

### Post-AWS

| # | Task | Status | Notes |
|---|------|--------|-------|
| R15 | Isochrone school catchments — Outstanding schools within 15-min walk | Pending | Family persona "holy grail". 90% infra exists. |

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
| Codebase snapshot (latest) | `gdrive:PropertyPulse/codebase_review_20260416/` (344 files, 39.5 MiB) |
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
