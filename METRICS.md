# PropertyPulse — Complete Metrics Reference

**Legend:**
- **Local**: Shows for the search key (postcode/place/ward/LAD/county)
- **Parent**: Shows comparison against parent region (county/region)
- Status: Y = implemented, N = not implemented, `—` = not applicable/meaningful, `DATA` = code ready but data missing

---

## Tab 1: Property & Market

| # | Metric ID | Metric Name | Local | Parent | Unit | Notes |
|---|-----------|-------------|:-----:|:------:|------|-------|
| 1 | `avg_price` | Average Sale Price (last 12m) | Y | Y | GBP | True AVG from raw transactions (13m window) |
| 2 | `median_price` | Median House Price | Y | Y | GBP | PERCENTILE_CONT(0.5) on raw transactions |
| 3 | `price_per_sqft` | Price per Sqft | Y | Y | GBP/sqft | **Only 2024-2025 data** — needs EPC backfill for history |
| 4 | `transaction_volume` | Transaction Volume (12m) | Y | Y | count/LSOA | Per-LSOA normalized. Details: YoY change, prior 12m |
| 5 | `freehold_leasehold` | Freehold vs Leasehold | Y | Y | % freehold | Details: avg prices by tenure, price difference |
| 6 | `new_build_proportion` | New Build Proportion | Y | Y | % | Details: 10-year trend chart, caveat note |
| 7 | `price_trend_yoy` | Price Trend (YoY) | Y | Y | % | HPI data — LAD-level only. Skipped for postcode/place/ward |
| 8 | `median_rent` | Median Monthly Rent | Y | Y | GBP/month | VOA PRMS — LAD-level only. Details: by bedroom (1-4) |
| 9 | `gross_yield` | Gross Rental Yield | Y | Y | % | LAD/county only with data. Postcode/place/ward: None + note |
| 10 | `affordability` | Rent Affordability | Y | Y | % of income | LAD/county only. Rent / median earnings |
| 11 | `median_earnings` | Median Annual Earnings | Y | Y | GBP/year | ASHE — LAD-level only |
| 12 | `investment_grade` | Investment Grade | Y | **N** | grade (A-F) | Composite: yield + HPI growth. LAD/county only |
| 13 | `epc_energy_score` | EPC Energy Score | Y | Y | score | From core_epc_lsoa. Details: A-G distribution, heating types |
| 14 | `epc_rating_c_plus` | EPC Rated C or Above | Y | Y | % | Derived from EPC distribution |

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

| # | Metric ID | Metric Name | Local | Parent | Unit | Notes |
|---|-----------|-------------|:-----:|:------:|------|-------|
| 1 | `fifteen_min_score` | 15-Minute Score | Y | **N** | score /100 | Composite: 10 pts per amenity type present. Could compute parent avg |
| 2 | `amenities_15min` | 15-Minute Amenities (1km) | Y | Y | count | Within 1km (postcode) or area boundary |
| 3 | `nearest_station` | Nearest Station | Y | **N** | metres | Postcode only. **Could compute parent avg from pre-computed table** |
| 3b | `stations_in_area` | Rail/Metro Stations in Area | Y | **N** | count | Area mode only |
| 4 | `ptal_score` | Public Transport (PTAL) | Y | **N** | level | London only (TfL data). Could show parent avg PTAI |
| 5 | `connectivity_index` | Connectivity Index | Y | **N** | score /100 | Non-London only. Composite: rail + bus + broadband + amenity |
| 6 | `ev_chargers` | EV Chargers (1km) | Y | Y | count | Within 1km (postcode) or area boundary |
| 7 | `broadband` | Broadband Coverage | Y | Y | % gigabit | Ofcom data. Details: full fibre, superfast, ultrafast, gigabit |
| 8 | `cycling` | Cycling to Work | Y | Y | % commuters | Census TS061 |
| 9 | `commute_distance` | Work From Home Rate | Y | Y | % of workers | Census TS058. Details: commute distance bands |
| 10 | `mobile_coverage` | Mobile Coverage (4G/5G) | Y | Y | % 4G outdoor | Ofcom — LAD-level data |

### Additional Lifestyle data:

| Data | Endpoint | Local | Parent | Notes |
|------|----------|:-----:|:------:|-------|
| Commute estimate | `/commute` | Y | — | Driving/transit/cycling/walking times to any destination |

---

## Tab 3: Environment & Safety

| # | Metric ID | Metric Name | Local | Parent | Unit | Notes |
|---|-----------|-------------|:-----:|:------:|------|-------|
| 1 | `crime_rate` | Crime Rate (per 1,000 pop/yr) | Y | Y | per 1,000/yr | GMP areas excluded from parent |
| 2 | `crime_trend` | Crime Trend (YoY) | Y | Y | % | Requires 2 years of data. GMP areas excluded from parent |
| 3 | `flood_risk` | Flood Risk | Y | **N** | level | Categorical. Details: zone 2/3 %, risk score gauge. Could compute parent avg zone % |
| 4 | `air_quality_no2` | Air Quality (NO2) | Y | Y | ug/m3 | Defra PCM grid. Details: WHO limit comparison |
| 5 | `air_quality_pm25` | Air Quality (PM2.5) | Y | Y | ug/m3 | Defra PCM grid. Details: WHO limit comparison |
| 6 | `noise` | Noise Level | Y | Y | dB | **DATA MISSING — core_noise has 0 rows** |
| 7 | `green_cover` | Park Cover (1km) | Y | **N** | % | Postcode only. **Could compute parent avg from pre-computed table** |
| 7b | `green_spaces` | Parks & Gardens in Area | Y | **N** | count | Area mode only |
| 8 | `nearest_park` | Nearest Park | Y | **N** | metres | Postcode only. **Could compute parent avg from pre-computed table** |
| 9 | `parks_1km` | Parks Within 1km | Y | **N** | count | Postcode only. **Could compute parent avg from pre-computed table** |
| 10 | `sports_recreation` | Sports & Recreation | Y | **N** | count | **Could compute parent avg from pre-computed table** |
| 11 | `epc_rating` | Average EPC Score | Y | Y | score | Duplicate of Tab 1 epc_energy_score (different detail shape) |
| 12 | `esg_score` | ESG Score | Y | **N** | score /100 | Composite: EPC + AQ + flood + green space. Could compute parent |

### Additional Environment data:

| Data | Endpoint | Local | Parent | Notes |
|------|----------|:-----:|:------:|-------|
| AQ history (yearly) | `/aq-history` | Y | Y (national) | NO2, PM2.5, PM10 trend. Parent = national average |

---

## Tab 4: Community & Education

| # | Metric ID | Metric Name | Local | Parent | Unit | Notes |
|---|-----------|-------------|:-----:|:------:|------|-------|
| 0 | `demographics_overview` | Demographics Overview | Y | **N** | people | Summary card with 8 sub-metrics. Could add parent total pop |
| 1 | `population_density` | Population Density | Y | Y | people/hectare | Census |
| 2 | `median_age` | Median Age | Y | Y | years | Census. Details: age band %s |
| 3 | `household_composition` | Household Composition | Y | Y | % families | Census. Details: families, singles, sharers |
| 4 | `good_health` | Good Health | Y | Y | % | Census TS037 |
| 5 | `economically_active` | Economically Active | Y | Y | % | Census TS066 |
| 6 | `degree_educated` | Degree Educated | Y | Y | % | Census TS067 |
| 7 | `no_car` | No Car Household | Y | Y | % | Census TS045 |
| 8 | `born_abroad` | Born Abroad | Y | Y | % | Census TS004 |
| 9 | `wfh` | Works From Home | Y | Y | % | Census TS058 (also in Lifestyle tab as commute_distance) |
| 10 | `housing_tenure` | Housing Tenure | Y | Y | % owner-occupied | Census. Details: owned, social rent, private rent |
| 11 | `housing_type` | Housing Stock | Y | Y | % detached | Census. Details: detached, semi, terraced, flat |
| 12 | `household_size` | Household Size | Y | Y | % single-person | Census. Details: 1/2/3-4/5+ person |
| 13 | `ethnicity` | Ethnicity | Y | Y | % White | Ward-level only (core_census_ethnicity_ward) |
| 14 | `primary_schools` | Primary Schools | Y | **N** | Outstanding/Good count | Within 1mi (postcode) or area. Could compute parent avg |
| 15 | `secondary_schools` | Secondary Schools | Y | **N** | Outstanding/Good count | Within 3mi (postcode) or area. Could compute parent avg |
| 16 | `deprivation` | IMD Deprivation | Y | Y | score | IMD 2025. Details: rank, decile, 7 domain scores |
| 17 | `nhs_facilities` | NHS Facilities (2km) | Y | Y | count | GP/dentist/pharmacy/optician/care home. Pre-computed in core_nhs_lsoa |
| 18 | `area_persona` | Area Persona | Y | — | persona | Categorical label. Not meaningful as parent comparison |

---

## Tab 5: Local Governance

| # | Metric ID | Metric Name | Local | Parent | Unit | Notes |
|---|-----------|-------------|:-----:|:------:|------|-------|
| 1 | `council_tax` | Council Tax (Band D) | Y | Y | GBP/year | Details: all 8 bands (A-H) + parent averages |
| 2 | `local_authority` | Local Authority | Y | — | name | Categorical. Not meaningful as parent comparison |
| 3 | `controlling_party` | Controlling Party | Y | — | party | Categorical. Not meaningful as parent comparison |
| 4 | `water_company` | Water Company | Y | — | provider | Categorical. Not meaningful as parent comparison |
| 5 | `financial_health` | Financial Health (S114) | Y | — | status | Categorical. Not meaningful as parent comparison |

---

## Summary: Parent Comparison Gaps

### Could add parent but haven't yet (need pre-computed per-LSOA tables):

| Metric | Tab | What's needed |
|--------|-----|---------------|
| `fifteen_min_score` | Lifestyle | Avg composite score across parent LSOAs (could compute from existing amenity data) |
| `nearest_station` | Lifestyle | Pre-computed "nearest station distance" per LSOA, then AVG across parent |
| `ptal_score` | Lifestyle | Avg PTAI across parent LSOAs (London only) |
| `connectivity_index` | Lifestyle | Avg composite score across parent LSOAs |
| `flood_risk` | Environment | Avg zone 2/3 % across parent LSOAs |
| `green_cover` | Environment | Pre-computed park coverage per LSOA, then AVG across parent |
| `nearest_park` | Environment | Pre-computed nearest park per LSOA, then AVG across parent |
| `parks_1km` | Environment | Pre-computed park count per LSOA, then AVG across parent |
| `sports_recreation` | Environment | Pre-computed sports count per LSOA, then AVG across parent |
| `esg_score` | Environment | Compute parent ESG from parent component averages |
| `primary_schools` | Community | Avg Outstanding/Good count across parent LSOAs |
| `secondary_schools` | Community | Avg Outstanding/Good count across parent LSOAs |
| `investment_grade` | Property | Compute parent grade from parent yield + parent HPI |

### Data missing entirely:

| Metric | Tab | What's needed |
|--------|-----|---------------|
| `noise` | Environment | **DEFRA strategic noise map data** — core_noise table has 0 rows |
| `price_per_sqft` (historical) | Property | **EPC full re-ingest** — floor_area_sqm only covers 2024-2025 |

### Intentionally no parent (categorical/composite — comparison not meaningful):

| Metric | Tab | Reason |
|--------|-----|--------|
| `local_authority` | Governance | It's a name, not a number |
| `controlling_party` | Governance | Categorical |
| `water_company` | Governance | Categorical |
| `financial_health` | Governance | Binary status |
| `area_persona` | Community | Categorical label |
| `demographics_overview` | Community | Summary card, sub-metrics have their own parents |

---

## Totals

| | Count |
|--|-------|
| **Total distinct metrics** | 55 |
| **With local value** | 55 (all) |
| **With parent value** | 35 |
| **Missing parent (could add)** | 13 |
| **No parent (intentional)** | 6 |
| **Missing data** | 1 (noise) |
