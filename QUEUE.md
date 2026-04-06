# PropertyPulse — Work Queue

Last updated: 2026-04-06 (session 11)

---

## HIGH PRIORITY

### EPC Full Re-Ingest — CRITICAL for price-per-sqft historical data
**Impact:** Price per sqft combined average chart lines only show 2024-2025 data. All years before 2024 show null because `floor_area_sqm` was only matched for recent transactions.

**Root cause:** `core_epc_domestic` does not exist in DB. Only 1.49M of 28.9M transactions have EPC matches (floor_area_sqm, bedrooms_estimated, epc_rating). The matching script exists in `etl/legacy/transactions_epc.py` but was never run against all historical years.

**Steps:**
1. [ ] Register at https://epc.opendatacommunities.org/downloads/domestic
2. [ ] Download domestic-csv.zip (~4-5 GB) → place at `etl/data/domestic-csv.zip`
3. [ ] Run `python3 pipeline.py --source epc_domestic` — loads ~23M certificates into `core_epc_domestic`
4. [ ] Move `etl/legacy/transactions_epc.py` → `etl/derived/transactions_epc.py`, re-register in pipeline.py
5. [ ] Run the EPC matching: processes ~1.5M postcodes, Jaccard address-matches all 28.9M transactions
6. [ ] Run `etl/migrations/absorb_epc.py` — copies matched floor_area/bedrooms/epc to master table
7. [ ] Recompute lsoa_month_avg_ppsm and lsoa_month_avg_ppsft aggregate columns
8. [ ] Verify: price-per-sqft chart should show data back to ~2008

---

## MEDIUM PRIORITY

### Noise Data Ingest
- `core_noise` table exists with correct schema (postcode, road_noise_db, rail_noise_db, air_noise_db, noise_band) but has **zero rows**
- Source: DEFRA strategic noise maps (road, rail, aviation)
- [ ] Download DEFRA noise data
- [ ] Write `etl/sources/noise.py` ingest module
- [ ] Register in pipeline.py
- The backend query in `tab_environment.py` already handles noise correctly (conditionally includes metric when data exists)

### Spatial Parent Comparisons
These metrics return `parent_value: null` because parent-region computation is too expensive at query time:
- nearest_station, nearest_park, parks_1km, green_cover, sports_recreation
- [ ] Create pre-computed per-LSOA aggregate tables (same pattern as core_nhs_lsoa)
- [ ] Add derived ETL modules to pipeline
- [ ] Wire parent values in tab service files

### Step 4: INSPIRE Index Polygons — DEFERRED
- User said: "keep the INSPIRE in queue for now, we'll get back to it"
- 318 LA zips in ~/Downloads/inspire_polygons/ — **286 are 0 bytes (download failure)**
- Only 32 LAs have data (~10% coverage). Need to re-download before proceeding.
- GML format, EPSG:27700. Fields: INSPIREID, polygon geometry, VALIDFROM. No title numbers.
- Architecture: separate `core_inspire_parcels` table for address-level search
- [ ] Re-download the 286 failed zips from Land Registry
- [ ] Write etl/sources/inspire_polygons.py — ingest GML, reproject to WGS84
- [ ] Migration 008: CREATE core_inspire_parcels (inspire_id, geometry, la_code, valid_from)
- [ ] Address-level search endpoint + frontend view

### Census Extra LSOA CSVs — Need Download
- `_ingest_extra()` in census.py is ready; needs LSOA-level CSVs from ONS/Nomis:
  - [ ] census2021-ts037-lsoa.csv (General health → pct_good_health)
  - [ ] census2021-ts045-lsoa.csv (Car/van availability → pct_no_car)
  - [ ] census2021-ts066-lsoa.csv (Economic activity → pct_economically_active)
  - [ ] census2021-ts067-lsoa.csv (Qualifications → pct_degree)
  - [ ] census2021-ts004-lsoa.csv (Country of birth → pct_born_abroad)
- Data already in DB from migration 007 — only needed for future ETL re-runs

---

## LOW PRIORITY

- [ ] Guildford: "Guilford" typo in core_place_names data (data fix only)
- [ ] LLC (Local Land Charges) — 137 zips in ~/Downloads/llc/ — deferred
- [ ] Census TS027 (national identity) — low priority
- [ ] Census TS031 (religion) — low priority

---

## Known Data Gaps (not code bugs)

- Whitby/North Yorkshire: E06000065 missing VOA rent (new unitary authority Apr 2023)
- Scotland/Wales postcodes: no postcode-level data (England-only)
- LS1 Terraced: no Last 12m (no recent terraced sales in Leeds CC)
- Land Registry new-build flag: unreliable for house-to-flat conversions (caveat note displayed)
- Price per sqft history: only 2024-2025 data until EPC full re-ingest is completed (see High Priority)

---

## Completed (sessions 10-11)

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
- ✅ Price per sqft chart: combined average lines for local + parent (2024+ only due to data gap)
- ✅ newbuild_pct: fixed to use raw count (not normalized per-LSOA value)
- ✅ PRICE_TYPES filter consistency across all new-build queries
