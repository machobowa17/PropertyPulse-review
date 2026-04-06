# Session Contract

Redis key: `lsoa_sess:{session_key}` — 24 hour TTL
Created by: `helpers.make_lsoa_session()` via `resolve.py:_build_and_store_session()`
Retrieved by: `helpers.get_lsoa_session(session_key)` — returns `None` on expiry

---

## Full Session Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `lsoa_codes` | `list[str]` | yes | — | All LSOA codes in the search area |
| `lat` | `float\|None` | yes | `None` | Centroid latitude |
| `lon` | `float\|None` | yes | `None` | Centroid longitude |
| `search_mode` | `str` | yes | — | `"postcode"` or `"area"` |
| `local_lads` | `list[str]` | yes | `[]` | LAD code(s) for LAD-level metric queries |
| `lad_code` | `str` | yes | `"_"` | Primary LAD code (or `"_"` if not applicable) |
| `ward_code` | `str` | yes | `"_"` | Ward code (or `"_"`) |
| `lsoa_code` | `str` | yes | `"_"` | Single LSOA (postcode searches only; else `"_"`) |
| `parent_lad_codes` | `list[str]` | yes | `[]` | All LADs sharing the same parent comparison region |
| `parent_name` | `str` | yes | `"England"` | Parent region name (county/region or `"England"`) |
| `boundary_source` | `str` | yes | `"lad"` | How to look up the boundary polygon — see table below |
| `boundary_id` | `str` | yes | `""` | Identifier used to look up the boundary polygon |
| `postcode_district` | `str\|None` | no | `None` | Outward code, e.g. `"SW1A"` (postcode/district searches only) |
| `place_name` | `str\|None` | no | `None` | Place name (place searches only) |
| `place_lad_code` | `str\|None` | no | `None` | LAD containing the place (place searches only) |
| `place_type` | `str\|None` | no | `None` | `"City"`, `"Town"`, `"Suburban Area"`, `"Village"`, etc. |

**Required fields** (always present — safe to use `sess["field"]`):
`lsoa_codes`, `lad_code`, `ward_code`, `lsoa_code`, `search_mode`, `local_lads`, `parent_lad_codes`, `parent_name`, `boundary_source`, `boundary_id`

**Optional fields** (may be absent or `None` — always use `sess.get("field", default)`):
`lat`, `lon`, `postcode_district`, `place_name`, `place_lad_code`, `place_type`

---

## boundary_source Values

| `boundary_source` | Search Type | `boundary_id` | Boundary Polygon Source |
|-------------------|-------------|---------------|-------------------------|
| `"ward_lsoa"` | Full postcode | `ward_code` | Ward + LSOA overlay (two features) |
| `"ward"` | Ward name | `ward_code` | `core_ward_boundaries WHERE ward_code = boundary_id` |
| `"lad"` | LAD/borough name or postcode district | `lad_code` | `core_lad_boundaries WHERE lad_code = boundary_id` |
| `"county"` | County name | `county_name` | `core_county_boundaries WHERE county_name = boundary_id` |
| `"place"` | Place name | `place_name` | `ST_Union` of LSOAs from `core_place_lsoa_mapping[_town]` |

`is_lad_or_coarser = boundary_source in ("lad", "county")` — used in tab_property.py to gate LAD-level-only metrics.

---

## How Fields Are Set Per Search Type

| User Search | `boundary_source` | `boundary_id` | `lad_code` | `ward_code` | `lsoa_code` |
|-------------|-------------------|---------------|------------|-------------|-------------|
| Full postcode (e.g. `CR5 1RA`) | `ward_lsoa` | ward_code | from postcode | from postcode | from postcode |
| Postcode district (e.g. `SW1A`) | `lad` | lad_code | dominant LAD | `"_"` | `"_"` |
| LAD/Borough name | `lad` | lad_code | lad_code | `"_"` | `"_"` |
| County name | `county` | county_name | `"_"` | `"_"` | `"_"` |
| Place name (suburb/town/city) | `place` | place_name | place_lad_code | `"_"` | `"_"` |
| Ward name | `ward` | ward_code | containing LAD | ward_code | `"_"` |

For county searches, `local_lads` = all LAD codes within that county.
For place searches, `local_lads` = `[place_lad_code]`.
For all others, `local_lads` = `[lad_code]` if lad_code is valid.

---

## Endpoint → Session Field Usage

### GET /api/v1/area (tab handlers)
Passes to all 5 tab service functions:
- `lad_code`, `ward_code`, `lsoa_codes`
- `lat` → `centroid_lat`, `lon` → `centroid_lon`
- `search_mode`, `local_lads`
- `parent_lad_codes` → `parent_lads`
- `boundary_source`

### GET /api/v1/price-history
- `boundary_source` — decides lad vs lsoa scope on core_property_transactions
- `local_lads` — LAD-level local query (via lsoa_codes from core_lsoa_boundaries)
- `lsoa_codes` — LSOA-level local query
- `parent_lad_codes` — regional comparison
- `parent_name` — regional label

### GET /api/v1/price-by-type
- `boundary_source`, `local_lads`, `lsoa_codes`, `parent_lad_codes`
- Local: raw PERCENTILE_CONT/AVG on core_property_transactions; Parent: mv_parent_yearly/rolling_price_stats

### GET /api/v1/aq-history
- `lad_code` — local LAD AQ trend

### GET /api/v1/comparable
- `lad_code` — find comparable LADs

### GET /api/v1/map-pois
- `lat`, `lon` — spatial distance ordering
- `search_mode` — postcode vs area branch
- `ward_code` — ward boundary JOIN (postcode mode)
- `lsoa_code` (singular) — LSOA boundary JOIN (postcode mode)
- `lsoa_codes` — area mode filter

### GET /api/v1/boundary
- `boundary_source` — selects which boundary table
- `boundary_id` — identifies the boundary
- `ward_code`, `lsoa_code` — for `ward_lsoa` source
- `place_name`, `place_lad_code`, `place_type` — for `place` source

### GET /api/v1/map-choropleth
- `boundary_source` — determines LSOA scope
- `local_lads` — LAD/county scope
- `lsoa_codes` — place/ward scope
- `ward_code` — `ward_lsoa` scope (expands to all ward LSOAs)

### GET /api/v1/commute
- `lat`, `lon` — origin coordinates

### GET /api/v1/report
- `lad_code`, `ward_code`, `lsoa_codes`, `lat`, `lon`, `search_mode`, `local_lads`, `parent_lad_codes`, `boundary_source`

---

## Session Field → Core Table JOIN Key Mapping

| Session Field | Core Table.Column |
|--------------|-------------------|
| `lsoa_codes` | `core_property_transactions.lsoa_code` (master — all price/EPC queries) |
| `lsoa_codes` | `core_census_lsoa.lsoa_code` (consolidated census — demographics, housing, commute, extra) |
| `lsoa_codes` | `core_crime_lsoa.lsoa_code` |
| `lsoa_codes` | `core_imd_lsoa.lsoa_code` |
| `lsoa_codes` | `core_lsoa_boundaries.lsoa_code` |
| `lsoa_codes` | `core_postcodes.lsoa_code` |
| `lsoa_codes` | `core_place_lsoa_mapping.lsoa_code` |
| `lsoa_code` (singular) | `core_lsoa_boundaries.lsoa_code` (map-pois JOIN only) |
| `local_lads` | `core_lsoa_boundaries.lad_code` (→ lsoa_codes → core_property_transactions) |
| `local_lads` | `core_hpi_lad.lad_code` |
| `local_lads` | `core_voa_rents_lad.lad_code` |
| `local_lads` | `core_broadband_lad.lad_code` |
| `local_lads` | `core_lsoa_boundaries.lad_code` (choropleth scope) |
| `local_lads` | `core_price_by_bedrooms_lad.lad_code` |
| `parent_lad_codes` | `core_lsoa_boundaries.lad_code` (→ lsoa_codes → core_property_transactions) |
| `lad_code` | `core_air_quality_lad.lad_code` |
| `lad_code` | `core_lad_boundaries.lad_code` |
| `lad_code` | `core_lad_county_lookup.lad_code` |
| `ward_code` | `core_ward_boundaries.ward_code` |
| `ward_code` | `core_postcodes.ward_code` |
| `place_name` + `place_lad_code` | `core_place_lsoa_mapping.place_name` + `.lad_code` |
| `place_name` + `place_lad_code` | `core_place_lsoa_mapping_town.place_name` + `.lad_code` |
| `boundary_id` (county) | `core_county_boundaries.county_name` |

> **Note (post-Step 3):** `core_property_prices_lsoa`, `core_property_prices_lad`,
> `core_price_sqm_lsoa`, `core_price_sqm_lad`, `core_property_prices_district` have been
> DROPPED. All price queries now use raw AVG/PERCENTILE_CONT on `core_property_transactions`.
> Parent-level medians are pre-computed in `mv_parent_yearly_price_stats` and
> `mv_parent_rolling_price_stats` (refreshed weekly via pipeline).
>
> **Note (post-Step 5, session 9):** 5 individual census LSOA tables (`core_census_demographics_lsoa`,
> `core_census_housing_lsoa`, `core_census_hh_size_lsoa`, `core_census_commute_lsoa`,
> `core_census_extra_lsoa`) have been DROPPED and consolidated into `core_census_lsoa`.
> `core_census_ethnicity_ward` remains separate (ward-level geography).
> `pct_wfh` was dropped from `core_cycling_lsoa` (duplicate of census commute data).

---

## Rules

1. **Session fields are additive only** — never rename or remove existing fields. Adding new fields is safe because all consumers use `sess.get("field", default)` for optional fields.

2. **Session TTL is 24 hours**. All data endpoints return HTTP 410 on expiry. The frontend must handle 410 by prompting the user to search again.

3. **Cache invalidation**: changing any session field's semantics requires clearing the `lsoa_sess:*` namespace in Redis.

4. **Do not add non-deterministic data to the session** — session key is a deterministic SHA256 hash of input codes. Session payload may be refreshed (same key, same content) on repeated `/resolve` requests.

5. **Tab services never access the session directly** — they receive pre-unpacked parameters from `area.py:get_area_data()`. If a tab service needs a new session field, add it to the function signature in `area.py` (unpack from session there) and pass it through.

---

## How to Add a New Search Type

1. **geo_resolver.py**: Add a resolver function `_try_<type>()` returning the standard result dict:
   ```python
   {
     "query": ..., "type": "<type>", "search_mode": "area"|"postcode",
     "resolved_codes": {"lsoa": ..., "ward": ..., "lad": ...},
     "coordinates": {"lat": ..., "lon": ...},
     "boundary_source": "<new_source>",
     "boundary_id": "<identifier>",
     # add any new fields for session here (e.g. "place_name")
   }
   ```
   Register it in `_resolve_place_name()` resolution order.

2. **helpers.py `expand_lsoa_codes()`**: Add a new case to expand the LSOA set for the new boundary type. Add any new kwargs to the function signature.

3. **helpers.py `make_lsoa_session()`**: If the new type requires new session fields, add them to the `cache_set()` payload and pass them through via kwargs.

4. **resolve.py `_build_and_store_session()`**: Extract and forward any new fields from the resolver result to `make_lsoa_session()`.

5. **area.py `get_boundary()`**: Add a new `elif source == "<new_source>":` branch to render the boundary polygon.

6. **area.py `get_map_choropleth()`**: Add a scope case if the new type needs custom LSOA scope logic.

7. **This file**: Document all new session fields, boundary_source values, and endpoint usage.
