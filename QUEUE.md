# PropertyPulse — Work Queue

Last updated: 2026-04-12 (session 16)

---

## IN PROGRESS

### Q3: Wales Data Re-Ingest
Sequence: postcodes → boundaries → census → imd → land_registry_full → backfill_epc_matching → crime → council_tax
- Code ready (Bundles A-F landed country-aware ETL)
- postcodes.py now filters E+W+S via SUPPORTED_COUNTRY_PREFIXES
- land_registry_full.py has no country filter — gated by core_postcodes
- land_registry_full TRUNCATEs core_property_transactions — EPC backfill must re-run after
- DO NOT drop core_epc_domestic until backfill completes (6.5 GB, needed by backfill_epc_matching.py)
- Disk: 11 GB free (sufficient)

---

## PARKED

### Q1: Noise Data Ingest
- `etl/sources/noise.py` written: tile-based WCS download → PostGIS raster → postcode sampling
- 273 tiles × 2 layers (road Lden + rail Lden), ~4hrs runtime
- Registered in pipeline.py
- Backend query in `tab_environment.py` already wired (conditionally includes metric)
- Air noise (airport) deferred — very limited coverage, different source

### Q2: INSPIRE Index Polygons — DEFERRED
- 318 LA zips were in ~/Downloads/inspire_polygons/ — **deleted during disk cleanup** (286 were 0 bytes)
- Need to re-download ALL zips from Land Registry before proceeding
- GML format, EPSG:27700. Fields: INSPIREID, polygon geometry, VALIDFROM. No title numbers.
- Architecture: separate `core_inspire_parcels` table for address-level search

---

## AFTER Q3 COMPLETES

- [ ] Q4: LLC (Local Land Charges) — 137 zips in ~/Downloads/llc/
- [ ] Q5: Census TS027 (national identity)
- [ ] Q6: Census TS031 (religion)

---

## REVISIT (pending user discussion)

- [ ] SKIP items: metric_registry.py, epc_domestic.py rewrite, personas.ts replacement
- [ ] Known data gaps: E06000065 (Whitby/North Yorks) missing VOA rent, LS1 Terraced no Last 12m, Land Registry new-build flag unreliable for conversions

---

## Completed

### Session 16 (Manus merge)
- ✅ Manus merge: 10 bundles (A-J) all committed to main
- ✅ All 6 Action Required verifications resolved
- ✅ All 3 SELECTIVE items resolved (S1 helpers.py cherry-pick, S2 postcodes.py full rewrite, S3 land_registry_wales_ppd skipped)
- ✅ Disk cleanup: tmp tables + caches + old extensions + dead downloads → 6.2 GB → 11 GB free

### Sessions 10-15
- ✅ EPC Full Re-Ingest: core_epc_domestic 29.2M rows, 14M floor-area matches backfilled
- ✅ BUG-1: census.py missing _ingest_extra() — added function + removed TRUNCATE
- ✅ BUG-2: cycling_ptal.py writes to dropped pct_wfh column — removed all references
- ✅ Playwright 123/123, Map E2E all pass, Map edge cases all pass
- ✅ Exhaustive audit: 99+ files, all stale references resolved
- ✅ Transaction volume /LSOA suffix + per-LSOA normalization fix
- ✅ Paginated transaction table (backend endpoint + frontend component)
- ✅ New build proportion: parent comparison, trend chart, caveat note
- ✅ Freehold/leasehold: parent comparison
- ✅ Amenities 15min: parent comparison (was computed but not passed)
- ✅ Crime trend: parent YoY comparison
- ✅ Noise: parent average (code ready, no data in table)
- ✅ NHS facilities: parent average for area mode
- ✅ Price per sqft chart: combined average lines for local + parent
- ✅ newbuild_pct: fixed to use raw count (not normalized per-LSOA value)
- ✅ PRICE_TYPES filter consistency across all new-build queries
- ✅ Spatial parent comparisons: core_lsoa_green_space + core_lsoa_transport
- ✅ Census Extra CSVs: all 5 TS files downloaded, DB populated
- ✅ Guildford typo: verified correct in DB
