# ETL Data Sources

Every authoritative data source used by PropertyPulse, listed by schedule.
Each entry shows the source, license, download location, and which `core_*` tables it feeds.

---

## Foundation Sources

These run once at setup and again when ONS publishes new postcode or boundary data.

---

### postcodes
**Description:** ONS Postcode Directory (ONSPD) — the geographic backbone for all LAD/ward/LSOA joins.

| Field | Value |
|-------|-------|
| Source | ONS Open Geography Portal |
| URL | https://geoportal.statistics.gov.uk/search?q=ONSPD |
| License | Open Government Licence v3.0 |
| Update frequency | Quarterly (use the latest release) |
| Data files | `etl/data/ONSPD_*.csv`, `etl/data/catchment_names.json`, `etl/data/lad_to_ctyua_2025.csv` |
| Tables written | `core_postcodes` |
| Expected rows | 1,400,000 – 2,800,000 |

---

### boundaries
**Description:** ONS Open Geography LSOA / ward / LAD boundaries, plus county boundaries derived from LAD polygons.
Fetched live from the ArcGIS FeatureServer — no local files required.

| Field | Value |
|-------|-------|
| Source | ONS Open Geography Portal (ArcGIS FeatureServer) |
| LSOA URL | `https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5/FeatureServer/0/query` |
| Ward URL | `https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/WD_MAY_2025_UK_BGC_V2/FeatureServer/0/query` |
| LAD URL | `https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/LAD_MAY_2025_UK_BGC_V2/FeatureServer/0/query` |
| License | Open Government Licence v3.0 |
| Update frequency | Annually (ONS publishes updated boundaries each May) |
| Data files | None — live API fetch |
| Tables written | `core_lsoa_boundaries`, `core_ward_boundaries`, `core_lad_boundaries`, `core_county_boundaries` |
| Expected rows | 33,000 – 35,000 (core_lsoa_boundaries) |

---

### lad_county_lookup
**Description:** LAD → county / region parent mapping. Powers the "parent area" context on all LAD-and-above searches.

| Field | Value |
|-------|-------|
| Source | ONS Open Geography Portal |
| URL | https://geoportal.statistics.gov.uk/ |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/lad_to_ctyua_2025.csv` |
| Tables written | `core_lad_county_lookup` |
| Expected rows | 280 – 350 |

---

### place_names
**Description:** OS Open Names — all named settlements (city / town / village / suburb) for place-name search.

| Field | Value |
|-------|-------|
| Source | Ordnance Survey Open Data Hub |
| URL | https://osdatahub.os.uk/downloads/open/OpenNames |
| License | Open Government Licence v3.0 |
| Update frequency | Bi-annually |
| Data files | `etl/data/opname_csv_gb.zip`, `etl/data/catchment_names.json` |
| Tables written | `core_place_names` |
| Expected rows | 1 – 500,000 |

---

### place_boundaries
**Description:** OSM place boundary polygons for suburb / town / village / neighbourhood boundaries used in Voronoi search.
Fetched live from Overpass API — no local files required.

| Field | Value |
|-------|-------|
| Source | OpenStreetMap (via Overpass API) |
| URL | https://overpass-api.de/api/interpreter |
| License | ODbL (OpenStreetMap contributors) |
| Update frequency | Quarterly (delete cache to force refresh) |
| Data files | None — live API fetch |
| Tables written | `core_place_boundaries` |
| Expected rows | 10,000 – 50,000 |

---

## Monthly Sources

Run after each monthly Land Registry / HPI / crime / EPC release.

---

### land_registry_full
**Description:** HM Land Registry Price Paid Data (PPD) — every residential and commercial property sale in England and Wales. Full historical ingest (1995–present) including district, county, and PPD category columns.

| Field | Value |
|-------|-------|
| Source | HM Land Registry |
| URL | `http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-complete.csv` |
| License | HM Land Registry Open Government Licence v3.0 (free for commercial use) |
| Update frequency | Monthly |
| Data files | `~/Downloads/pp-complete.csv` (or yearly files downloaded from LR S3) |
| Tables written | `core_property_transactions` |
| Expected rows | 20,000,000 – 40,000,000 |

---

### hpi
**Description:** ONS / Land Registry UK House Price Index — monthly average prices by LAD from January 1995.

| Field | Value |
|-------|-------|
| Source | HM Land Registry |
| URL | `http://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-YYYY-MM.csv` |
| License | Open Government Licence v3.0 |
| Update frequency | Monthly |
| Data files | Downloaded live; cached at `etl/data/uk_hpi.csv` between runs |
| Tables written | `core_hpi_lad` |
| Expected rows | 80,000 – 200,000 |

---

### crime
**Description:** Police.uk national crime data — street-level crime records for the last 36 months.
Phase 1 uses the bulk national ZIP; Phase 2 supplements with the Police.uk API for GMP.

| Field | Value |
|-------|-------|
| Source | Police.uk / data.police.uk |
| Bulk ZIP | https://data.police.uk/data/ |
| API | https://data.police.uk/api (crimes-street/all-crime) |
| License | Open Government Licence v3.0 |
| Update frequency | Monthly |
| Data files | `etl/data/police_latest.zip` (or set `CRIME_ZIP_PATH` env var) |
| Tables written | `core_crime_lsoa` |
| Expected rows | 4,000,000 – 8,000,000 |
| Notes | GMP / Sussex / Gwent / BTP are absent from the national bulk ZIP and are fetched via the API separately |

---

### schools
**Description:** DfE Get Information About Schools (GIAS) register + Ofsted inspection ratings + KS2/KS4 performance tables.

| Field | Value |
|-------|-------|
| Source (GIAS) | Department for Education |
| GIAS URL | https://dfe-digital.github.io/gias-data/schools.json (auto-downloaded) |
| Ofsted URL | https://www.gov.uk/government/statistics/state-funded-schools-inspections-and-outcomes-as-at-31-august |
| KS2/KS4 URL | https://www.gov.uk/government/collections/statistics-key-stage-2-and-key-stage-4 |
| License | Open Government Licence v3.0 |
| Update frequency | Monthly (Ofsted); Annually (KS2/KS4) |
| Data files | `etl/data/ofsted_latest.csv` (required), `etl/data/ks2_school_2024.csv`, `etl/data/ks4_school_2024.csv` (optional) |
| Tables written | `core_schools` |
| Expected rows | 20,000 – 35,000 |

---

### epc_domestic
**Description:** MHCLG Energy Performance Certificate domestic certificates — all 93 columns for the full national dataset.

| Field | Value |
|-------|-------|
| Source | MHCLG / Open Data Communities |
| URL | https://epc.opendatacommunities.org/downloads/domestic |
| License | Open Government Licence v3.0 |
| Update frequency | Monthly |
| Data files | `etl/data/domestic-csv.zip` (or set `EPC_ZIP_PATH` env var) |
| Tables written | `core_epc_domestic` |
| Expected rows | 20,000,000 – 30,000,000 |
| Notes | Full replace on each run. ~23M rows as of March 2026. PK on `certificate_number`; index on `postcode` and `(postcode, lodgement_date DESC)` |

---

## Quarterly Sources

Run after each quarterly EPC-LSOA / EV charger / OSM / mobile update.

---

### epc_lsoa
**Description:** ONS/Nomis Energy Efficiency of Housing (NM_2401_1) — EPC rating distribution by LSOA.

| Field | Value |
|-------|-------|
| Source | ONS / Nomis |
| URL | https://www.nomisweb.co.uk/api/v01/dataset/NM_2401_1.bulk.csv |
| License | Open Government Licence v3.0 |
| Update frequency | Quarterly |
| Data files | `etl/data/epc_lsoa_nomis.csv` (or set `EPC_LSOA_PATH` env var) |
| Tables written | `core_epc_lsoa` |
| Expected rows | 30,000 – 36,000 |

---

### osm_amenities
**Description:** OpenStreetMap POIs (Bible Section 3.1 types: café, pub, park, gym, supermarket, etc.) via Overpass API.

| Field | Value |
|-------|-------|
| Source | OpenStreetMap (via Overpass API) |
| URL | https://overpass-api.de/api/interpreter |
| License | ODbL (OpenStreetMap contributors) |
| Update frequency | Quarterly (delete `etl/data/osm_bible_pois.json` to force refresh) |
| Data files | Cached at `etl/data/osm_bible_pois.json` |
| Tables written | `core_osm_amenities` |
| Expected rows | 100,000 – 400,000 |

---

### ev_chargers
**Description:** Office for Zero Emission Vehicles (OZEV) Open Charge Point Registry — all public EV charge points in the UK.

| Field | Value |
|-------|-------|
| Source | OZEV / Department for Transport |
| URL | https://www.gov.uk/guidance/find-and-use-data-on-public-electric-vehicle-chargepoints |
| License | Open Government Licence v3.0 |
| Update frequency | Quarterly |
| Data files | `etl/data/ev_chargepoints.csv` (or set `EV_CHARGERS_PATH` env var) |
| Tables written | `core_ev_chargers` |
| Expected rows | 10,000 – 60,000 |

---

### governance
**Description:** Council political control (majority party, NOC flag) and S114 (effective bankruptcy) notices.

| Field | Value |
|-------|-------|
| Source (control) | Open Council Data |
| Control URL | https://opencouncildata.co.uk/ |
| Control license | CC-BY-SA |
| Source (S114) | UK Government public record |
| S114 URL | https://www.gov.uk/government/publications/ |
| Update frequency | Quarterly (control); Ad-hoc (S114) |
| Data files | `etl/data/council_control_2025.csv` (or set `COUNCIL_CONTROL_PATH` env var) |
| Tables written | `core_council_control_lad`, `core_s114_notices` |
| Expected rows | 250 – 400 (core_council_control_lad) |
| Notes | S114 notices list is hardcoded in the module; update when new notices are issued |

---

### mobile_coverage
**Description:** Ofcom Connected Nations — 4G/5G mobile outdoor coverage by operator and LAD.

| Field | Value |
|-------|-------|
| Source | Ofcom |
| URL | https://www.ofcom.org.uk/research-and-data/telecoms-research/connected-nations |
| License | Open Government Licence v3.0 |
| Update frequency | Quarterly |
| Data files | `etl/data/202409_mobile_coverage_laua_r01.csv` (or set `MOBILE_COVERAGE_PATH` env var) |
| Tables written | `core_mobile_coverage_lad` |
| Expected rows | 250 – 400 |

---

## Annual Sources

Run once per year after Ofcom, NHS, DfE, Defra, and other annual releases.

---

### ~~price_sqm~~ *(LEGACY — moved to etl/legacy/)*
**Status:** Superseded. PPSM/PPSF now computed directly from `price / floor_area_sqm` on `core_property_transactions`. Target tables (`core_price_sqm_lad`, `core_price_sqm_lsoa`) have been dropped.

| Field | Value |
|-------|-------|
| Source | UCL / London Datastore |
| License | CC-BY 4.0 |

---

### voa_rents
**Description:** Valuation Office Agency Private Rental Market Statistics — median rents by bedroom count and LAD.

| Field | Value |
|-------|-------|
| Source | Valuation Office Agency |
| URL | https://www.gov.uk/government/statistics/private-rental-market-summary-statistics-april-2022-to-march-2023 |
| License | Open Government Licence v3.0 |
| Update frequency | Annually (April–March year) |
| Data files | `etl/data/voa_rents.xls` (Tables 2.3–2.7 by bedroom count) |
| Tables written | `core_voa_rents_lad` |
| Expected rows | ~1,500 |

---

### ashe
**Description:** ONS Annual Survey of Hours and Earnings (ASHE) — median resident earnings by LAD.

| Field | Value |
|-------|-------|
| Source | ONS / Nomis |
| URL | https://www.nomisweb.co.uk/ (ASHE Resident Analysis, dataset NM_30_1) |
| License | Open Government Licence v3.0 |
| Update frequency | Annually (October release) |
| Data files | `etl/data/ashe_median_earnings.csv` |
| Tables written | `core_earnings_lad` |
| Expected rows | ~380 |

---

### broadband
**Description:** Ofcom Connected Nations — fixed broadband speeds and full-fibre / superfast coverage at postcode and LAD level.

| Field | Value |
|-------|-------|
| Source | Ofcom |
| URL | https://www.ofcom.org.uk/research-and-data/telecoms-research/connected-nations |
| License | Open Government Licence v3.0 |
| Update frequency | Annually (December release) |
| Data files | `etl/data/broadband/postcode_files/postcode_files/` (one CSV per postcode area), `etl/data/broadband/fixed_coverage_laua/*.csv`, `etl/data/broadband/fixed_performance_laua/*.csv` |
| Tables written | `core_broadband_postcode`, `core_broadband_lad` |
| Expected rows | 1,500,000 – 2,000,000 (core_broadband_postcode) |

---

### air_quality
**Description:** Defra Pollution Climate Mapping (PCM) 1km grid for NO₂, PM₂.₅, and PM₁₀, aggregated to LAD.

| Field | Value |
|-------|-------|
| Source | Defra |
| URL | https://uk-air.defra.gov.uk/data/pcm-data |
| File patterns | `mapno2{year}.csv`, `mappm25{year}g.csv`, `mappm10{year}g.csv` |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/air_quality/` (downloaded from Defra if not cached; history from 2018) |
| Tables written | `core_air_quality`, `core_air_quality_lad` |
| Expected rows | 200,000 – 600,000 (core_air_quality) |

---

### flood
**Description:** Environment Agency Flood Map for Planning — Flood Zone 2 and 3 polygons for rivers and sea.

| Field | Value |
|-------|-------|
| Source | Environment Agency |
| URL | https://www.data.gov.uk/dataset/bed63fc1-dd26-4685-b143-2941088923b3/flood-map-for-planning-rivers-and-sea-flood-zone-3 |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/Historic_Flood_Map.gpkg` |
| Tables written | `core_flood_zones` |
| Expected rows | 10,000 – 500,000 |

---

### green_space
**Description:** OS Open Greenspace — parks, playing fields, allotments, golf courses, and other public green space across Great Britain.

| Field | Value |
|-------|-------|
| Source | Ordnance Survey Open Data Hub |
| URL | https://osdatahub.os.uk/downloads/open/OpenGreenspace |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/greenspace/Data/opgrsp_gb.gpkg` (or auto-extracted from `etl/data/opgrsp_gpkg_gb.zip`) |
| Tables written | `core_green_space` |
| Expected rows | 50,000 – 350,000 |

---

### nhs
**Description:** NHS Organisation Data Service (ODS) JSON — GP practices, hospitals, and dental practices geocoded via `core_postcodes`.

| Field | Value |
|-------|-------|
| Source | NHS Digital / ODS |
| URL | https://digital.nhs.uk/services/organisation-data-service/export-data-files/csv-downloads/gp-and-gp-practice-related-data |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/nhs/gp.json`, `etl/data/nhs/hospital.json`, `etl/data/nhs/dentist.json` |
| Tables written | `core_nhs_facilities` |
| Expected rows | 5,000 – 100,000 |

---

### naptan
**Description:** DfT National Public Transport Access Nodes (NaPTAN) — bus stops, rail stations, ferry terminals, and other access nodes in England.

| Field | Value |
|-------|-------|
| Source | Department for Transport |
| URL | https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/naptan.csv` |
| Tables written | `core_transport_stops` |
| Expected rows | 200,000 – 600,000 |
| Notes | Filtered to England only (lat 49.9°–56.0°N) |

---

### council_tax
**Description:** VOA Council Tax Band charges (Bands A–H) by LAD for England.

| Field | Value |
|-------|-------|
| Source | Valuation Office Agency |
| URL | https://www.gov.uk/government/statistics/council-tax-statistics-for-town-and-parish-councils-in-england |
| License | Open Government Licence v3.0 |
| Update frequency | Annually |
| Data files | `etl/data/council/ctb1_table8.ods` (Table 8) |
| Tables written | `core_council_tax_lad` |
| Expected rows | 300 – 400 |

---

### water
**Description:** Ofwat water company boundary polygons — which water company serves each LAD (largest-intersection join).

| Field | Value |
|-------|-------|
| Source | Stream / Catchment Based Approach |
| URL | https://data.catchmentbasedapproach.org/datasets/water-company-boundaries |
| License | CC-BY 4.0 |
| Update frequency | Annually |
| Data files | `etl/data/water_company_boundaries.geojson` |
| Tables written | `core_water_company_lad` |
| Expected rows | 300 – 400 |

---

### cycling_ptal
**Description:** Two sources combined: TfL Public Transport Accessibility Levels (London only) and Census 2021 TS061 cycling-to-work data (England).

| Field | Value |
|-------|-------|
| Source (PTAL) | Transport for London |
| PTAL URL | https://data.london.gov.uk/dataset/public-transport-accessibility-levels |
| Source (Census cycling) | ONS |
| Census URL | https://www.ons.gov.uk/datasets/TS061/editions/2021/versions/3 |
| License | OGL v3.0 (both) |
| Update frequency | Annually |
| Data files | `etl/data/ptal_lsoa_2015.csv`, `etl/data/census2021-ts061-lsoa.csv` |
| Tables written | `core_ptal_lsoa`, `core_cycling_lsoa` |
| Expected rows | 30,000 – 42,000 |

---

### place_lsoa_mapping *(derived — annual)*
**Description:** Spatial join: `core_place_names` × `core_lsoa_boundaries` using two-pass containment + Voronoi.
No external data source — derives entirely from previously ingested `core_*` tables.

| Field | Value |
|-------|-------|
| Depends on | place_names, boundaries |
| Tables written | `core_place_lsoa_mapping`, `core_place_lsoa_mapping_town` |
| Expected rows | 45,000 – 65,000 |

---

### nhs_lsoa *(derived — annual)*
**Description:** Aggregates `core_nhs_facilities` within 2 km of each LSOA centroid.
No external data source — derives from `core_nhs_facilities` + `core_lsoa_boundaries`.

| Field | Value |
|-------|-------|
| Depends on | nhs, boundaries |
| Tables written | `core_nhs_lsoa` |
| Expected rows | 30,000 – 38,000 |

---

## One-Time Sources

Run once; data does not change.

---

### census
**Description:** Census 2021 (England & Wales) — nine topic summaries (TS001/003/006/007A/017/022/044/054/058) covering population, households, tenure, age, ethnicity, and commute.

| Field | Value |
|-------|-------|
| Source | ONS |
| URL | https://www.ons.gov.uk/census/2021census/2021censusdata |
| License | Open Government Licence v3.0 |
| Update frequency | Once (Census 2021; next census ~2031) |
| Data files | `etl/data/census/census2021-ts001-lsoa.csv` (population), `census2021-ts006-lsoa.csv` (density), `census2021-ts003-lsoa.csv` (households), `census2021-ts007a-lsoa.csv` (age), `census2021-ts054-lsoa.csv` (tenure), `census2021-ts044-lsoa.csv` (accommodation), `census2021-ts017-lsoa.csv` (household size), `census2021-ts022-ward.csv` (ethnicity by ward), `census2021-ts058-lsoa.csv` (distance to work) |
| Tables written | `core_census_lsoa` (consolidated wide table), `core_census_ethnicity_ward` |
| Expected rows | 32,000 – 36,000 per table |

---

### imd
**Description:** MHCLG Index of Multiple Deprivation (IMD) 2025 — all 7 domains (Income, Employment, Education, Health, Crime, Barriers to Housing, Living Environment) for 2021 LSOAs in England.

| Field | Value |
|-------|-------|
| Source | MHCLG |
| URL | https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019 (update URL when IMD 2025 is published) |
| License | Open Government Licence v3.0 |
| Update frequency | Once (IMD 2025; previous release was 2019) |
| Data files | `etl/data/iod2025_all_domains.csv` |
| Tables written | `core_imd_lsoa` |
| Expected rows | 32,000 – 36,000 |

---

## Derived Tables

These modules derive new `core_*` tables purely from existing `core_*` tables.
They never download files.

---

### ~~transactions_epc~~ *(LEGACY — moved to etl/legacy/)*
**Status:** Superseded. EPC data absorbed into `core_property_transactions` master table (Step 2). Target table `core_transactions_epc` has been dropped.

| Field | Value |
|-------|-------|
| Depends on | *(was: land_registry, epc_domestic)* |

---

### price_by_bedrooms *(derived — monthly)*
**Description:** Aggregates `core_property_transactions` by LAD / year / property type / bedroom count using `bedrooms_estimated`. Suppresses cells with < 3 transactions.

| Field | Value |
|-------|-------|
| Depends on | land_registry_full |
| Tables written | `core_price_by_bedrooms_lad` |
| Property types | D (Detached), S (Semi-detached), T (Terraced), F (Flat) |
| Expected rows | 1,000 – 100,000 |

---

## License Summary

| License | Sources |
|---------|---------|
| Open Government Licence v3.0 | ONS, Land Registry, Defra, Ofcom, NHS, DfT, DfE, EA, VOA, Police.uk, MHCLG |
| ODbL (OpenStreetMap) | `place_boundaries`, `osm_amenities` |
| CC-BY 4.0 | ~~`price_sqm`~~ *(legacy)*, `water` (CaBA) |
| CC-BY-SA | `governance` (Open Council Data) |

All OGL v3.0 and CC-BY sources are free for commercial use with attribution.
ODbL requires share-alike for derived database products.
