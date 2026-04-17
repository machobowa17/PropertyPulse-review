# PropertyPulse — Complete Metrics Reference

**Last verified against code: 2026-04-16 (session 33)**
**Source of truth: `backend/app/services/tab_*.py`**

**Legend:**
- **Local**: Shows for the search key (postcode/place/ward/LAD/county)
- **Parent**: Shows comparison against parent region (county/region)
- Status: Y = implemented, `—` = not applicable/meaningful
- **Bucket**: `core` = visible by default, `detail_only` = shown in expanded panel only, `persona_only` = used in fit scoring/summaries only

---

## Tab 1: Property & Market

Source: `tab_property.py`

| # | Metric ID | Metric Name | Local | Parent | Unit | Bucket | Notes |
|---|-----------|-------------|:-----:|:------:|------|--------|-------|
| 1 | `avg_price` | Average Sale Price (last 12m) | Y | Y | GBP | core | True AVG from raw transactions (13m window) |
| 2 | `median_price` | Median House Price | Y | Y | GBP | core | PERCENTILE_CONT(0.5) on raw transactions |
| 3 | `price_per_sqft` | Price per Sqft | Y | Y | GBP/sqft | core | **Only 2024-2025 data** — needs EPC backfill for history |
| 4 | `transaction_volume` | Transaction Volume (12m) | Y | Y | count/LSOA | core | Per-LSOA normalized. Details: YoY change, prior 12m |
| 5 | `freehold_leasehold` | Freehold vs Leasehold | Y | Y | % freehold | core | Details: avg prices by tenure, price difference |
| 6 | `new_build_proportion` | New Build Proportion | Y | Y | % | core | Details: 10-year trend chart, caveat note |
| 7 | `price_trend_yoy` | Price Trend (YoY) | Y | Y | % | core | HPI data — LAD-level only. Skipped for postcode/place/ward |
| 8 | `median_rent` | Median Monthly Rent | Y | Y | GBP/month | core | VOA PRMS — LAD-level only. Details: by bedroom (1-4) |
| 9 | `gross_yield` | Gross Rental Yield | Y | Y | % | core | LAD/county only with data. Postcode/place/ward: None + note |
| 10 | `affordability` | Rent Affordability | Y | Y | % of income | core | LAD/county only. Rent / median earnings |
| 11 | `median_earnings` | Median Annual Earnings | Y | Y | GBP/year | core | ASHE — LAD-level only |
| 12 | `investment_grade` | Investment Grade | Y | Y | grade (A-F) | core | Composite: yield + HPI growth. Parent grade computed from parent yield + parent YoY |
| 13 | `epc_energy_score` | EPC Energy Score | Y | Y | score | core | From core_epc_lsoa. Details: A-G distribution, heating types |
| 14 | `epc_rating_c_plus` | EPC Rated C or Above | Y | Y | % | detail_only | Derived from EPC distribution |

### Additional Property chart data (not metric cards):

| Data | Endpoint | Local | Parent | Notes |
|------|----------|:-----:|:------:|-------|
| Price history (yearly) | `/price-history` | Y | Y | avg_price, median, avg_ppsf. **avg_ppsf only 2024+** |
| Price by type (yearly) | `/price-by-type` | Y | Y | Detached/Semi/Terraced/Flat breakdown |
| Price by bedrooms | `/price-history` | Y | — | LAD/county only, from core_price_by_bedrooms_lad |
| Transaction list | `/transactions` | Y | — | Paginated, sortable, filterable. 13m window |
| Comparable areas | `/comparable` | Y | — | Top 5 similar LADs by Euclidean distance |

---

## Tab 2: Lifestyle & Connectivity

Source: `tab_lifestyle.py`

| # | Metric ID | Metric Name | Local | Parent | Unit | Bucket | Notes |
|---|-----------|-------------|:-----:|:------:|------|--------|-------|
| 1 | `amenities_15min` | 15-Minute Amenities (1km) / Amenities in Area | Y | Y | count | core | Within 1km (postcode) or area boundary. Parent = avg per LSOA across parent LADs |
| 2 | `nearest_station` | Nearest Station | Y | Y | metres | core | Postcode mode only. Parent from core_lsoa_transport avg |
| 2b | `stations_in_area` | Rail/Metro Stations in Area | Y | — | count | core | Area mode only. Count metric — no parent comparison |
| 3 | `ptal_score` | Public Transport Accessibility (PTAL) | Y | Y | level | core | London only (TfL data). Parent = avg PTAI across parent LADs |
| 4 | `commuter_connectivity` | Commuter Connectivity | Y | Y | score /100 | core | DfT destination-reach data. Details: PT/walk/cycle/drive + dest types |
| 5 | `ev_chargers` | EV Chargers (1km) | Y | Y | count | core | Within 1km (postcode) or area boundary |
| 6 | `broadband` | Broadband Coverage | Y | Y | % gigabit | core | Ofcom data. Details: full fibre, superfast, ultrafast, gigabit |
| 6b | `broadband_superfast` | Superfast Broadband | Y | Y | % | detail_only | Same Ofcom source, focused on superfast availability |
| 7 | `cycling` | Cycling to Work | Y | Y | % commuters | core | Census TS061 |
| 8 | `commute_distance` | Work From Home Rate | Y | Y | % of workers | core | Census TS058. Details: commute distance bands |
| 9 | `mobile_coverage` | Mobile Coverage (4G/5G) | Y | Y | % 4G outdoor | core | Ofcom — LAD-level data |
| 9b | `mobile_4g_indoor` | 4G Indoor Coverage | Y | Y | % | detail_only | Same Ofcom source, indoor 4G reliability |
| 9c | `mobile_5g_outdoor` | 5G Outdoor Coverage | Y | Y | % | detail_only | Same Ofcom source |

### Additional Lifestyle data:

| Data | Endpoint | Local | Parent | Notes |
|------|----------|:-----:|:------:|-------|
| Commute estimate | `/commute` | Y | — | Driving/transit/cycling/walking times to any destination |

---

## Tab 3: Environment & Safety

Source: `tab_environment.py`

| # | Metric ID | Metric Name | Local | Parent | Unit | Bucket | Notes |
|---|-----------|-------------|:-----:|:------:|------|--------|-------|
| 1 | `crime_rate` | Crime Rate (per 1,000 pop/yr) | Y | Y | per 1,000/yr | core | GMP areas excluded from parent |
| 2 | `crime_trend` | Crime Trend (YoY) | Y | Y | % | core | Requires 2 years of data. GMP areas excluded from parent |
| 3 | `flood_risk` | Flood Risk | Y | Y | level | core | Categorical. Parent = aggregated zone % across parent LADs |
| 4 | `air_quality_no2` | Air Quality (NO2) | Y | Y | µg/m³ | core | Defra PCM grid. Details: WHO limit comparison |
| 5 | `air_quality_pm25` | Air Quality (PM2.5) | Y | Y | µg/m³ | core | Defra PCM grid. Details: WHO limit comparison |
| 6 | `noise` | Noise Level | Y | Y | dB | core | DEFRA strategic noise map. 1,427,115 rows in core_noise. Parent = avg road dB |
| 7 | `green_cover` | Park Cover (1km) | Y | Y | % | core | Postcode mode. Parent from core_lsoa_green_space |
| 7b | `green_spaces` | Parks & Gardens in Area | Y | Y | count | core | Area mode. Uses parent_parks_1km as parent |
| 8 | `nearest_park` | Nearest Park | Y | Y | metres | core | Postcode mode. Parent from core_lsoa_green_space |
| 9 | `parks_1km` | Parks Within 1km | Y | Y | count | core | Postcode mode. Parent from core_lsoa_green_space |
| 10 | `sports_recreation` | Sports & Recreation (1km) / in Area | Y | Y | count | core | Parent from core_lsoa_green_space |
| 11 | `epc_rating` | Average EPC Score | Y | Y | score | core | From core_epc_lsoa (same source as Tab 1, different detail shape) |
| 11b | `epc_rating_c_plus` | EPC Rated C or Above | Y | Y | % | detail_only | Derived from EPC distribution |

### Additional Environment data:

| Data | Endpoint | Local | Parent | Notes |
|------|----------|:-----:|:------:|-------|
| AQ history (yearly) | `/aq-history` | Y | Y (national) | NO2, PM2.5, PM10 trend. Parent = national average |

---

## Tab 4: Community & Education

Source: `tab_community.py`

| # | Metric ID | Metric Name | Local | Parent | Unit | Bucket | Notes |
|---|-----------|-------------|:-----:|:------:|------|--------|-------|
| 0 | `demographics_overview` | Demographics Overview | Y | Y | people | core | Summary card with 8 sub-metrics, each with own parent. Parent headline = total pop |
| 1 | `population_density` | Population Density | Y | Y | people/hectare | core | Census |
| 2 | `median_age` | Median Age | Y | Y | years | core | Census. Details: age band %s |
| 3 | `household_composition` | Household Composition | Y | Y | % families | core | Census. Details: families, singles, sharers |
| 4 | `good_health` | Good Health | Y | Y | % | core | Census TS037 |
| 5 | `economically_active` | Economically Active | Y | Y | % | core | Census TS066 |
| 6 | `degree_educated` | Degree Educated | Y | Y | % | core | Census TS067 |
| 7 | `no_car` | No Car Household | Y | Y | % | core | Census TS045 |
| 8 | `born_abroad` | Born Abroad | Y | Y | % | core | Census TS004 |
| 9 | `wfh` | Works From Home | Y | Y | % | core | Census TS058 (also in Lifestyle tab as commute_distance) |
| 10 | `housing_tenure` | Housing Tenure | Y | Y | % owner-occupied | core | Census. Details: owned, social rent, private rent |
| 11 | `housing_type` | Housing Stock | Y | Y | % detached | core | Census. Details: detached, semi, terraced, flat |
| 12 | `household_size` | Household Size | Y | Y | % single-person | core | Census. Details: 1/2/3-4/5+ person |
| 13 | `ethnicity` | Ethnicity | Y | Y | % White | core | Ward-level only (core_census_ethnicity_ward) |
| 14 | `primary_schools` | Primary Schools | Y | — | Outstanding/Good count | core | Within boundary (area) or 1mi (postcode). Count — no parent |
| 14b | `primary_school_quality` | Primary School Quality | Y | Y | % Outstanding/Good | core | Share of schools rated Outstanding/Good. Parent = same % across parent LADs |
| 15 | `secondary_schools` | Secondary Schools | Y | — | Outstanding/Good count | core | Within boundary (area) or 3mi (postcode). Count — no parent |
| 15b | `secondary_school_quality` | Secondary School Quality | Y | Y | % Outstanding/Good | core | Share of schools rated Outstanding/Good. Parent = same % across parent LADs |
| 16 | `deprivation` | IMD Deprivation | Y | Y | score | core | IMD 2025. Details: rank, decile, 7 domain scores |
| 17 | `nhs_facilities` | NHS Facilities (2km) | Y | Y | count | core | GP/dentist/pharmacy/optician/care home. Pre-computed in core_nhs_lsoa |
| 18 | `area_persona` | Area Persona | Y | — | persona | persona_only | Categorical label. Not meaningful as parent comparison |

---

## Tab 5: Local Governance

Source: `tab_governance.py`

| # | Metric ID | Metric Name | Local | Parent | Unit | Bucket | Notes |
|---|-----------|-------------|:-----:|:------:|------|--------|-------|
| 1 | `council_tax` | Council Tax (Band D) | Y | Y | GBP/year | core | Details: all bands (A-I) + parent averages |
| 2 | `local_authority` | Local Authority | Y | — | name | core | Categorical. Not meaningful as parent comparison |
| 3 | `controlling_party` | Controlling Party | Y | — | party | core | Categorical. Not meaningful as parent comparison |
| 4 | `water_company` | Water Company | Y | — | provider | core | Categorical. Not meaningful as parent comparison |
| 5 | `financial_health` | Financial Health (S114) | — | — | status | — | **DISABLED** — hard-coded data didn't meet production standard. Needs provenance-backed ingestion register |

---

## Metrics NOT implemented (referenced in old docs but NOT in code)

| Metric ID | Was in | Status |
|-----------|--------|--------|
| `fifteen_min_score` | Old METRICS.md | Never implemented as separate metric. `amenities_15min` covers this |
| `connectivity_index` | Old METRICS.md | Replaced by `commuter_connectivity` (DfT data) |
| `esg_score` | Old METRICS.md | Never implemented. Was planned composite of EPC + AQ + flood + green |

---

## Summary

| | Count |
|--|-------|
| **Total distinct metric IDs in code** | 60 |
| **With local value** | 59 (all except financial_health) |
| **With parent value** | 48 |
| **No parent (intentional — categorical/count)** | 11 |
| **Disabled** | 1 (financial_health) |

### No parent (intentional):

| Metric | Tab | Reason |
|--------|-----|--------|
| `stations_in_area` | Lifestyle | Area-mode count, no distance concept |
| `local_authority` | Governance | Name, not a number |
| `controlling_party` | Governance | Categorical |
| `water_company` | Governance | Categorical |
| `primary_schools` | Community | Raw count; quality % metric has parent |
| `secondary_schools` | Community | Raw count; quality % metric has parent |
| `area_persona` | Community | Categorical label |

### Data gaps (code ready, data incomplete):

| Metric | Tab | What's needed |
|--------|-----|---------------|
| `price_per_sqft` (historical) | Property | **EPC full re-ingest** — floor_area_sqm only covers 2024-2025 |
