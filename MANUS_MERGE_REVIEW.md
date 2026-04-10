# Manus Merge Review — Single Source of Truth

**Purpose:** Durable, file-by-file comparison between our `main` and `manus/main`. Survives compaction. Any new Claude session working on Manus merge work MUST read this file first.

**Baseline facts (do not re-derive):**
- Our branch: `main` @ `ffe0e6e` (Add comprehensive metrics reference table for Manus handover)
- Manus branch: `manus/main` @ `613e44c` (Create developer handoff for sessions 26-29 hardening work)
- Merge base: shared baseline (main is 0 commits ahead, manus/main is 22 commits ahead)
- Total diff: 149 files changed, 22,605 insertions, 3,966 deletions
- Manus commits: 22 (listed below)

**Review protocol:**
1. Every code file that differs gets its own entry in this file.
2. Each entry: file path → what changed → recommendation (🟢 TAKE / 🟡 SELECTIVE / 🔴 SKIP) → rationale → status (`PENDING_REVIEW` / `APPROVED` / `REJECTED` / `MERGED`).
3. Commits happen after every ~10 file entries so progress survives compaction.
4. No code changes are made until all PENDING_REVIEW entries are either APPROVED or REJECTED by user.
5. Every actual merge commit references its entry in this file.

**Constraints (from prior sessions — do not override):**
- Our DB has `core_epc_domestic` (29.2M rows) + EPC-backfilled 14M transactions with floor_area_sqm — Manus does NOT have this.
- Our `core_census_lsoa` is the consolidated wide table — Manus still uses older split tables in some places.
- Our METRIC_REGISTRY is flat with fields: `section`, `label`, `local_grain`, `supports_parent`, `supports_trend`, `map_binding`, `unit`, `status`, `sort_priority`, `decision_question`, `metric_family`, `interpretation_direction`, `quality_notes`, `source_tables`. Manus's alternative uses different field names (`metric_id`, `section_id`, `headline_label`, etc.) and is INCOMPATIBLE.
- `habitable_rooms` ≠ bedrooms → always label "N bed (est.)" with footnote.
- `PRICE_TYPES = ('D','S','T','F')` — excludes 'O' (commercial).
- No hardcoded values — use `backend/app/constants.py` and `etl/constants.py`.
- No parallel agents / no background agents (user preference).

---

## Manus Commits (22 total)

In reverse chronological order (newest first):

| # | SHA | Title |
|---|-----|-------|
| 1 | `613e44c` | Create developer handoff for sessions 26-29 hardening work |
| 2 | `2027f0c` | Restore flat metric contract and close Wales crime parity gap |
| 3 | `ea26fd2` | Simplify metric contract and refactor results handover |
| 4 | `bf24e10` | Persist durable Wales boundary and crime repair checkpoint |
| 5 | `a515b76` | Persist durable Wales postcode repair baseline and current handover state |
| 6 | `d0db7c5` | Upgrade persona engine with shared personalization layer |
| 7 | `793af3c` | Implement first-pass buy rent invest decision flow |
| 8 | `063828f` | Implement first-pass UX declutter foundation |
| 9 | `f555363` | Finalize hardening baseline and clean investigation artifacts |
| 10 | `af63a85` | chore: back up latest portal hardening and validation artefacts |
| 11 | `42340e5` | docs: add developer hand-back summary |
| 12 | `ae57fd7` | Add DfT-backed commuter connectivity phase two |
| 13 | `a1da2f3` | docs: checkpoint phase-two commute source research |
| 14 | `c2e8b0f` | Roll out phase-one commuter connectivity panel |
| 15 | `2e58743` | Withdraw heuristic composite metrics and document commute design |
| 16 | `053f3b6` | Withdraw heuristic commute estimator |
| 17 | `f903952` | Withdraw hard-coded Section 114 metric path |
| 18 | `4843b3d` | Checkpoint bedroom price exploration |
| 19 | `56231b3` | Surface EPC C-plus metric and refresh area cache |
| 20 | `ab19b45` | Surface school quality metrics and refresh area cache |
| 21 | `a1eb9e5` | Merge remote-tracking branch 'origin/main' |
| 22 | `8918dfb` | Checkpoint current PropertyPulse implementation progress |

---

## Review Progress

- [ ] Backend routers (7 files: area, commute, report, resolve, main, config, + metric_registry.py new)
- [ ] Backend services (7 files: helpers, tab_property, tab_lifestyle, tab_environment, tab_community, tab_governance, comparable_areas, geo_resolver)
- [ ] ETL sources modified (~18 files)
- [ ] ETL sources added (connectivity_metric, land_registry_wales_ppd)
- [ ] ETL migrations added (008, 009)
- [ ] ETL run scripts added (~7 files)
- [ ] ETL pipeline + constants
- [ ] Frontend components modified (~18 files)
- [ ] Frontend components added (~7 Results* components + DecisionModeSelector)
- [ ] Frontend pages (Home, Results, SavedAreas)
- [ ] Frontend utils (personas, tabs, personalization, savedAreas, sectionSummary)
- [ ] Frontend types + api client
- [ ] Backend tests added
- [ ] Produce final categorized plan

Sessions/docs/logs files are NOT reviewed — they're historical artifacts, not merge candidates.

---

## File-by-File Review

### Backend — core infrastructure

#### `backend/app/config.py` — MODIFIED (+14 / -3)
**What Manus changed:** Adds `SettingsConfigDict` (pydantic-settings v2 pattern) with `.env` file loading, `extra="ignore"`, and `allowed_origins_list` property. Changes default `DATABASE_URL` from explicit `postgresql+asyncpg://postgres@localhost:5432/ukproperty` to peer-auth `postgresql+asyncpg:///ukproperty`.
**Recommendation:** 🟡 SELECTIVE
**Rationale:** The `SettingsConfigDict` + `.env` support + `allowed_origins_list` property are clean wins — they make the config file-driven instead of env-var-driven. But the DATABASE_URL change to peer-auth would break our local setup. Take the `SettingsConfigDict` block and the `allowed_origins_list` property; keep our DATABASE_URL defaults.
**Status:** `PENDING_REVIEW`

#### `backend/app/main.py` — MODIFIED (+4 / -8)
**What Manus changed:** Imports `settings` from `app.config`, uses `settings.RATE_LIMIT` and `settings.allowed_origins_list` instead of reading env vars directly. Removes inline `os.getenv` CORS parsing.
**Recommendation:** 🟢 TAKE
**Rationale:** Pure cleanup — centralizes config reads through the Settings object. No behaviour change if we also take the config.py `allowed_origins_list` property. Dependent on config.py SELECTIVE above.
**Status:** `PENDING_REVIEW`

#### `backend/app/constants.py` — MODIFIED (+1 / -0)
**What Manus changed:** Adds one line: `"connectivity_lsoa": "core_connectivity_lsoa",` to `TABLE_NAMES`.
**Recommendation:** 🟢 TAKE (iff we take DfT Connectivity Metric ETL)
**Rationale:** Trivial one-line addition. Only useful if `core_connectivity_lsoa` table exists — which requires taking `etl/sources/connectivity_metric.py` + migration `008_connectivity_lsoa.sql` + `tab_lifestyle.py` commuter_connectivity metric. Bundle them as a single decision.
**Status:** `PENDING_REVIEW` (bundled with DfT connectivity decision)

#### `backend/app/services/helpers.py` — MODIFIED (+228 / -16)
**What Manus changed:**
1. Adds country metadata infrastructure: `COUNTRY_COVERAGE`, `COUNTRY_STATUS`, `COUNTRY_CODE_PREFIXES`, `infer_country_from_geo_codes()`, `build_country_metadata()`. Supports "live" (England) / "partial" (Wales) / "planned" (Scotland) / "parked" (NI) status per country.
2. Expands `metric()` return dict dramatically: adds `comparison_status`, `comparison_scope_label`, `comparison_difference_abs`, `comparison_difference_pct`, `trend_status`, `trend_window_label`, `trend_direction`, `trend_value`, `trend_series`, `trend_parent_series`, `trend_summary`, `capsule_text`, `capsule_tone`, `map_binding_type`, `registry`, `headline`, `comparison` (nested), `trend` (nested), `capsule` (nested), `map_binding` (nested), `quality_flags`. Delegates computation to new `build_metric_contract()` imported from `app.services.metric_registry`.
3. County self-comparison fix via a different approach: uses `core_lad_boundaries` directly (England-wide) when `county_name` kwarg is present. Our existing fix uses `core_lad_county_lookup` — both achieve the same goal.
4. Adds canonical geo contract v2: `canonical_geo` dict with `entity`, `local_scope`, `comparison_scope`, `display_geometry`, `centroid`, `country` sub-dicts. Stores alongside existing session fields. Contract version field = 2.
5. Entity type inference in `make_lsoa_session`: infers county / place / ward / postcode / postcode_district / lad from resolved fields. Adds new params `entity_type`, `entity_name`, `query_text`.
6. Adds `_normalize_scalar()` helper and uses `NATIONAL_PARENT_NAMES` for scope_type decision.

**Recommendation:** 🟡 SELECTIVE
**Rationale:**
- County metadata + `infer_country_from_geo_codes` + `build_country_metadata` are genuinely valuable for UK-wide expansion (we already have this flagged in MEMORY.md as Wales/Scotland/NI planned). **TAKE.**
- Canonical geo contract v2 is a significant architectural change that all tab services and the frontend would need to understand. Big blast radius. **SELECTIVE** — needs deeper review before taking.
- `metric()` expansion via `build_metric_contract` depends on Manus's NEW `backend/app/services/metric_registry.py` file (1460 lines). That file duplicates our existing `backend/app/metric_registry.py` with a different field schema. Taking this creates TWO parallel registries which is bad. **SKIP** unless we migrate our registry to their schema (separate big decision).
- County self-comparison fix: we already have our own version. **SKIP** — no net gain.
- Entity type inference: clean, useful for richer frontend rendering. **TAKE.**

**Status:** `PENDING_REVIEW`

#### `backend/app/services/metric_registry.py` — ADDED (1460 lines, new file)
**What Manus added:** A parallel metric registry at a NEW path (`backend/app/services/metric_registry.py`, distinct from our existing `backend/app/metric_registry.py`). Exports `build_metric_contract(id, name, local_value, parent_value, unit, details)` which computes a structured contract with nested `comparison`, `trend`, `capsule`, `map_binding`, `registry`, `headline`, `quality_flags` sub-dicts. Uses different field names than ours (`metric_id`/`section_id`/`headline_label`/`display_priority`/`comparison_capability`/etc.).
**Recommendation:** 🔴 SKIP
**Rationale:** This is Manus's alternative registry schema. Adopting it creates two sources of truth (theirs at `services/metric_registry.py`, ours at `metric_registry.py`) with incompatible field names. Our flat registry already has `decision_question`, `interpretation_direction`, `quality_notes`, `metric_family`, `source_tables`, `supports_parent`, `supports_trend`, `map_binding`. The features `build_metric_contract` adds (nested capsule copy, structured trend summary, quality_flags) can be added directly to our existing registry and helpers.metric() if we want them — without adopting the whole parallel file.
**Status:** `PENDING_REVIEW`

### Backend — routers

#### `backend/app/routers/area.py` — MODIFIED (+619 / -25, massive)
**What Manus changed:**
1. **`AREA_CACHE_VERSION = "v8"` + `MAP_CACHE_VERSION = "v2"`** — adds explicit cache versioning so schema changes invalidate caches automatically.
2. **Geo contract v2 accessor helpers**: `_geo`, `_geo_entity`, `_geo_local_scope`, `_geo_comparison_scope`, `_geo_display_geometry`, `_session_centroid`, `_session_boundary_source`, `_session_boundary_id`, `_session_local_scope_type`, `_session_entity_name`, `_session_parent_name`, `_session_parent_lads`. These read from the new `geo` dict on sessions with fallback to flat session fields.
3. **Scope-based cache key** (`_area_scope_cache_key`): hashes local_scope + comparison_scope + display_geometry + lsoa_codes_hash → shared cache key so multiple sessions pointing at the same logical scope reuse each other's cached tab results. **Real performance win.**
4. **AQ-history county aggregation**: `WHERE lad_code = ANY(:lads)` + `GROUP BY year` + `AVG(...)` when `boundary_source == "county"`. (Already in our version of this file from prior partial merge.)
5. **Comparable areas county support**: uses new `find_comparable_scopes()` when `len(local_lads) > 1` instead of just returning `unsupported_scope`. Actually computes county-level similarity. Adds `lad_count`, `scope_name`, `scope_type`, `anchor_lad_code` to the target dict.
6. **Map POIs expansion** (HUGE): adds NHS facilities point layer (Community tab), green space / parks / sports recreation (Environment tab), OSM amenities (Lifestyle tab). All three support both area mode (intersect with lsoa_codes) and radius mode (2km NHS, 1500m green/amenities).
7. **Choropleth layers expansion** (HUGE): goes from 3 layers (`avg_price`, `price_per_sqft`, `epc_score`) to **35 layers**. New layers: `population_density`, `median_age`, `household_composition`, `good_health`, `economically_active`, `degree_educated`, `no_car`, `born_abroad`, `wfh`, `housing_tenure`, `housing_type`, `household_size`, `deprivation` (+ 7 domain breakdowns), `broadband`, `full_fibre`, `superfast_broadband`, `mobile_coverage`, `mobile_4g_indoor`, `mobile_5g_outdoor`, `air_quality_no2`, `air_quality_pm25`, `council_tax`, `median_earnings`, `median_rent`. Each has its own SQL, unit, grain metadata, and optional note.
8. **Metadata on choropleth response**: `grain` ("lsoa" / "lad_proxy" / "grid_to_lsoa") and `note` (caveat string) — honesty about when a LSOA-level heatmap is actually a LAD-level value repeated.

**Recommendation:** 🟢 TAKE (mostly) — but with a dependency chain
**Rationale:**
- Scope-based cache key: pure performance win, independent of other changes. TAKE.
- AQ-history county aggregation: already in our codebase; keep ours.
- Comparable areas county support: richer than our "unsupported_scope" fallback. TAKE (requires `find_comparable_scopes` from `comparable_areas.py`).
- Map POIs expansion (NHS, green space, OSM amenities): pure enrichment, no dependencies. TAKE.
- Choropleth 35 layers: **biggest single UX win in the entire Manus diff.** 35 layers vs our 3. Strongly TAKE. All SQL is straightforward and reads from tables we already have. Requires frontend MapLayerControl to expose them.
- Choropleth grain/note metadata: honesty-pass, clean win. TAKE.
- Geo contract v2 accessor helpers: required iff we take helpers.py geo contract v2; otherwise replace with our flat session reads. The helpers fall back to flat fields gracefully, so taking area.py without helpers.py works BUT misses the richer entity/scope data.

**Status:** `PENDING_REVIEW`

#### `backend/app/routers/commute.py` — MODIFIED (+12 / -60, total withdrawal)
**What Manus changed:** Removes the entire haversine-based commute estimator (modes, speeds, wait times, route factor heuristics). Endpoint now returns `503 COMMUTE_ESTIMATOR_WITHDRAWN` with a message that a source-backed replacement is being built. Part of the "honesty pass."
**Recommendation:** 🟡 SELECTIVE — user decision
**Rationale:** This is a product decision, not a code decision. The haversine estimator IS heuristic (fixed speeds × straight-line × road factor + wait time). But it provides a useful rough number users value. Three options:
  (a) Withdraw it like Manus did (honesty pass)
  (b) Keep it with a big "approximate" disclaimer in the UI
  (c) Replace with DfT Connectivity Metric 2025 + live TfL/Transport APIs (bigger scope)
Manus chose (a) AND built (c) partway via `connectivity_metric.py` + `tab_lifestyle.commuter_connectivity`. Bundle this with the DfT connectivity decision.
**Status:** `PENDING_REVIEW` (bundled with DfT connectivity decision)

#### `backend/app/routers/resolve.py` — MODIFIED (+113 / -21)
**What Manus changed:**
1. Adds `_coverage_metadata()` returning `live_countries`, `partial_countries`, `planned_countries`, `parked_countries`, and a long `coverage_message` describing UK-wide rollout status.
2. Adds `TYPE_LABELS` dict mapping `postcode`/`ward`/`borough`/etc. → human-readable labels.
3. Adds `_format_suggestion()` that enriches each raw suggestion row with `display_label`, `display_type`, `display_context` (joined breadcrumb), `selection_value`, and normalized `secondary` field.
4. Enriches SQL for all suggestion queries (postcode, postcode_district, lad, county, place, ward, contains, trigram) to return `comparison` and `secondary` columns for breadcrumb rendering.
5. `resolve` endpoint now includes `coverage` metadata in every response and also includes `geo` dict when session was built.
6. `_build_and_store_session` now returns `(session_key, lsoa_codes, session)` tuple (was 2-tuple), so the resolve endpoint can echo the canonical geo contract back to the client.
7. Passes `entity_type`, `entity_name`, `query_text` to `make_lsoa_session`.

**Recommendation:** 🟢 TAKE (mostly)
**Rationale:**
- `_coverage_metadata()` and coverage-in-response: pure additive, good UX. TAKE.
- `_format_suggestion()` + display fields + comparison/secondary columns: makes suggestion dropdown much richer (breadcrumbs visible in the autocomplete). Pure win. TAKE.
- TYPE_LABELS helper: TAKE.
- Session 3-tuple return + `geo` echo: dependent on helpers.py geo contract v2. If we take helpers.py partially, the geo echo degrades gracefully (returns `None`). Safe to TAKE.
- entity_type/entity_name/query_text params: same dependency on helpers.py. Safe to TAKE.

**Status:** `PENDING_REVIEW`

