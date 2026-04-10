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

#### `backend/app/routers/report.py` — MODIFIED (+519 / -216, massive PDF rewrite)
**What Manus changed:**
1. Geo contract v2 accessors (same pattern as area.py).
2. New constants: `TAB_COLOURS`, `PERSONA_LABELS`, `MODE_LABELS`, `SKIP_METRICS = {"demographics_overview", "area_persona"}` (consistent with heuristic withdrawal).
3. HTML escape via `_safe()` on all user-provided strings going into PDF paragraphs.
4. Metric helpers that read Manus's richer metric contract: `_metric_name` (reads `registry.headline_label`), `_metric_priority` (reads `registry.display_priority`), `_metric_capsule` (reads `capsule.text`), `_metric_source`, `_metric_licence`, `_metric_quality_notes`.
5. New section helpers: `_prioritised_metrics` (sorts by display_priority), `_comparison_badge`, `_section_overview`, `_decision_lens_text` (persona + buy/rent/invest framing), `_executive_recommendations`, `_collect_source_rows` (provenance table).
6. `_build_pdf()` signature now accepts `decision_mode` and `persona` kwargs — the report becomes personalised.
7. Endpoint body heavily refactored.

**Recommendation:** 🔴 SKIP (for now) — requires dependency chain
**Rationale:** The entire rewrite assumes Manus's richer metric contract (capsule, registry.headline_label, etc.) which comes from their `metric_registry.py` + `helpers.metric()` rewrite. Taking report.py without those dependencies means every `_metric_name`/`_metric_capsule` returns fallback values and the report becomes pointlessly rewritten. Also depends on persona engine v2 and buy/rent/invest decision mode.
**Alternative:** If we decide later to adopt Manus's metric contract + persona engine + decision modes as a bundle, revisit this. Until then our existing report.py works correctly and shows real content.
**Status:** `PENDING_REVIEW`

### Backend — services

#### `backend/app/services/comparable_areas.py` — MODIFIED (+211 / -108, refactor)
**What Manus changed:** Refactors single-LAD comparable logic into shared helpers (`FEATURES_SQL`, `_normalise_rows`, `_feature_means`). Adds new function `find_comparable_scopes(db, *, target_lad_codes, target_name, scope_type, limit)` for multi-LAD (county/custom scope) comparison: builds a LAD-level feature matrix, aggregates target LADs into a single "scope vector" (weighted mean), then finds the most similar OTHER scopes in the same comparison space.
**Recommendation:** 🟢 TAKE (bundled with area.py comparable county support)
**Rationale:** Genuine new capability — counties can now be compared to other counties instead of being unsupported. No dependency on metric contract v2 or persona engine. Pure SQL + Python refactor. SAFE.
**Status:** `PENDING_REVIEW`

#### `backend/app/services/geo_resolver.py` — MODIFIED (+12 / -0)
**What Manus changed:** Adds `_resolved_country_metadata()` helper and attaches a `country` dict (from `build_country_metadata` + `infer_country_from_geo_codes` in helpers.py) to EVERY resolve result: postcode, district, county, lad, place, ward. Enables downstream code to see if the result is in a "live" / "partial" / "planned" / "parked" country.
**Recommendation:** 🟢 TAKE
**Rationale:** Trivial, additive, and aligns with UK-wide coverage plans in MEMORY.md. Dependencies: `build_country_metadata` and `infer_country_from_geo_codes` from helpers.py (also recommended as TAKE). If those are imported, this is a 12-line win.
**Status:** `PENDING_REVIEW`

#### `backend/app/services/tab_property.py` — MODIFIED (+1181 / -739, huge diff, mostly formatting)
**What Manus changed:**
1. **Same 14 metric IDs on both sides** (affordability, avg_price, epc_energy_score, epc_rating_c_plus, freehold_leasehold, gross_yield, investment_grade, median_earnings, median_price, median_rent, new_build_proportion, price_per_sqft, price_trend_yoy, transaction_volume). No net metric additions or removals.
2. **Formatting-only churn**: renames `_local_txn_filter`/`_local_txn_params` → `local_txn_filter`/`local_txn_params`, splits SQL across multiple lines, splits function signatures across multiple lines. Accounts for ~900 of the 1181 diff lines.
3. **Substantive adds**:
   - New Census 2021 housing-stock context query against `core_census_lsoa` (pct_owned, pct_private_rent, pct_social_rent, pct_detached, pct_semi, pct_terraced, pct_flat). Attached as `housing_stock` details on the `freehold_leasehold` metric to contrast recent-sales tenure with resident stock tenure.
   - New `stock_note` explanation: "Housing-stock context uses Census 2021 LSOA aggregates for the resolved area rather than the currently empty LAD bedroom-price table."
   - Refined `data_note` copy across ~8 metrics (price_per_sqft, transaction_volume, freehold_leasehold, price_trend_yoy, median_rent, gross_yield, affordability, median_earnings, investment_grade). Shorter, clearer, more honest about scope ("withheld for postcode, place, and ward searches because…").
4. **Adds `local_txn_filter_plain`** variant (no `t.` alias) so the second "price by property_type" query can reuse the same LSOA-code filter from the tighter search mode — currently our version used a hardcoded `lsoa_code = ANY(:codes)` which ignored `is_lad_or_coarser` mode and could return wrong data for LAD+ searches.

**Recommendation:** 🟡 SELECTIVE
**Rationale:**
- TAKE the Census housing-stock context additions + `stock_note` — pure enrichment, reads from our `core_census_lsoa` table, no dependency on metric contract v2.
- TAKE the `local_txn_filter_plain` fix — this is actually a **latent bug fix** on our side where the property-type breakdown query was hardcoded to `lsoa_code = ANY(:codes)` regardless of `is_lad_or_coarser`. Verify our side has the same bug before merging.
- TAKE the refined `data_note` copy — cleaner UX language, no behaviour change.
- SKIP the pure formatting churn (rename underscores, SQL splits, signature splits). It's diff noise that would make future diffs harder to read.
**Status:** `PENDING_REVIEW`

#### `backend/app/services/tab_lifestyle.py` — MODIFIED (+167 / -?, substantive)
**What Manus changed:**
1. **REMOVED** `fifteen_min_score` metric (heuristic composite = `types_present * 10`). Honesty pass.
2. **REMOVED** `connectivity_index` metric (heuristic composite of rail + bus + broadband + amenities for non-London areas). Honesty pass.
3. **ADDED** `commuter_connectivity` metric sourced from `core_connectivity_lsoa` (DfT Connectivity Metric 2025). Replaces the heuristic composite with a source-backed alternative.
4. **ADDED** `full_fibre` metric from Ofcom Connected Nations `fttp` column (full-fibre coverage %).
5. **ADDED** `superfast_broadband` metric from Ofcom Connected Nations `sfbb` column (superfast coverage %).
6. Enriches existing `broadband` metric details with `full_fibre_pct` and `parent_full_fibre_pct`.
7. Adds `source_note` on superfast metric explaining it shares the Ofcom postcode-to-area dataset.

**Recommendation:** 🟢 TAKE (bundled with DfT connectivity decision + Ofcom fftp/sfbb availability check)
**Rationale:**
- Honesty-pass removals (`fifteen_min_score`, `connectivity_index`) are correct — both were pure heuristics with no source citation. TAKE.
- `commuter_connectivity` requires `core_connectivity_lsoa` table, which requires ETL migration 008 + `etl/sources/connectivity_metric.py`. Bundle as one decision.
- `full_fibre` / `superfast_broadband` require `fttp` and `sfbb` columns on `core_broadband_lsoa`. **MUST VERIFY** our ingest already captures these (it should — Ofcom Connected Nations publishes both). If yes, this is a pure enrichment win; if no, bundle with broadband ingest update.
- Net metric count: -2 removed, +3 added → users gain honesty + two extra broadband dimensions.

**Status:** `PENDING_REVIEW` (dependency on DfT connectivity ingest + broadband column availability)

#### `backend/app/services/tab_environment.py` — MODIFIED (+63 / -?)
**What Manus changed:**
1. **REMOVED** `esg_score` composite metric (EPC + air-quality + flood-risk + green-space heuristic average, all equally weighted). Honesty pass — no source methodology.
2. **ADDED** `epc_rating_c_plus` metric in this tab (combines `pct_rating_a_b + pct_rating_c` from `core_epc_lsoa`). Note: `epc_rating_c_plus` already exists in tab_property — this is a *duplicate* surfacing of the same metric ID in the Environment tab for better discoverability.
3. Extends EPC local/parent SELECT to also fetch `pct_rating_c` alongside `pct_rating_a_b`.

**Recommendation:** 🟢 TAKE (mostly) + one question
**Rationale:**
- `esg_score` removal is the correct honesty call. TAKE.
- EPC C-plus in Environment tab: genuinely useful (Environment tab is where energy-efficiency context belongs). BUT we need to decide whether the same `epc_rating_c_plus` metric ID appears twice across tabs (once in Property, once in Environment). Frontend metric rendering typically keys on `id` — having the same id in two tabs may cause duplicate React keys or weird dedup behaviour. Either:
  (a) Keep ID unique and only surface in one tab (our current state — Property tab).
  (b) Use a different ID like `epc_rating_c_plus_environment` in the second tab.
  (c) Allow the frontend to render the same metric object in both tabs deliberately.
- Manus chose option (c) implicitly. Need to confirm frontend handles it cleanly before merging.

**Status:** `PENDING_REVIEW`

#### `backend/app/services/tab_community.py` — MODIFIED (+238 / -?)
**What Manus changed:**
1. **REMOVED** `area_persona` metric (heuristic single-label area personality like "Family suburb" / "Student quarter"). Honesty pass.
2. **ADDED 7 new sub-domain deprivation metrics**: `deprivation_income`, `deprivation_employment`, `deprivation_education`, `deprivation_health`, `deprivation_crime`, `deprivation_barriers`, `deprivation_living_environment`. Each sources from existing `core_imd_lsoa` domain score columns — no new ingest required. Adds parent comparison via AVG across parent LAD LSOAs.
3. Adds data_note copy explaining each deprivation sub-domain.

**Recommendation:** 🟢 TAKE
**Rationale:**
- `area_persona` withdrawal is correct honesty pass. TAKE.
- 7 deprivation sub-domains: pure enrichment with zero ingest cost — our `core_imd_lsoa` already stores all 7 domain scores. The data is sitting there unused. Surfacing it is a free UX win and gives users much richer deprivation context than the single headline IMD score.
- Compatible with our flat registry (just add 7 new entries with `interpretation_direction='lower_is_better'`, `section='community'`, `source_tables=['core_imd_lsoa']`).

**Status:** `PENDING_REVIEW`

#### `backend/app/services/tab_governance.py` — MODIFIED (+363 / -?)
**What Manus changed:**
1. **REMOVED** `financial_health` (S114 notice) metric. Our current file header already has a comment explaining intentional withdrawal pending source-backed replacement — Manus did the same withdrawal in their branch.
2. **Multi-authority refactor**: `fetch_local_governance` now accepts `local_lads` and `parent_lads` lists instead of a single `lad_code`. Aggregates council-tax / controlling-party / water-company / local-authority across multiple LADs (counties, custom scopes). Reports `authority_count` and `multi_authority` flag in details.
3. **ADDED `band_i`** (9th council-tax band) to both local and parent SELECTs — requires `band_i` column on `core_council_tax_lad` (Manus migration 009).
4. Adds `authority_label` with smart formatting: single authority name, "{county} county area", or "{N} local authorities" fallback.
5. Controlling-party: Counter of party across constituent authorities, "Mixed control" label if >1 distinct party, per-authority breakdown in details.
6. Water-company: deduped provider list, "Multiple providers" label if >1, per-authority provider in details.

**Status note:** Our WORKING TREE tab_governance.py already matches the Manus multi-LAD refactor (confirmed via diff), but `main` branch does NOT — meaning a partial Manus merge was done in an earlier session but never committed. Need to decide whether to:
- (a) Commit our current working tree first (which is functionally identical to Manus minus `band_i` and minor formatting) and then only cherry-pick `band_i` from Manus.
- (b) Reset our working tree and take Manus's version wholesale.

**Recommendation:** 🟡 SELECTIVE
**Rationale:**
- The multi-LAD refactor is correct and matches our working tree. TAKE in some form.
- `band_i` council tax support: TAKE (bundled with migration 009 + our council_tax ingest needing to populate band_i — verify).
- Formatting differences (docstring, SQL multi-line style): irrelevant — keep our working-tree version.
- **Action required:** user must decide whether to commit our working tree governance changes now or roll them into the Manus merge.

**Status:** `PENDING_REVIEW` + `ACTION_REQUIRED` (working-tree reconciliation)

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

---

### ETL — foundation (country metadata)

#### `etl/constants.py` — MODIFIED (+289 / -?, huge addition)
**What Manus changed:**
1. Adds `COUNTRY_GEOGRAPHY` dict — single source of truth for country rollout: England (live) / Wales (partial) / Scotland (planned) / Northern Ireland (parked). Each entry has `name`, `status`, `overpass_bbox`, `has_regions`, `has_counties`, `default_parent_name`.
2. Derives prefix tuples: `LIVE_COUNTRY_PREFIXES`, `PARTIAL_COUNTRY_PREFIXES`, `PLANNED_COUNTRY_PREFIXES`, `PARKED_COUNTRY_PREFIXES`, `SUPPORTED_COUNTRY_PREFIXES`.
3. Adds `SUPPORTED_LAD_CODE_PREFIXES_BY_COUNTRY` mapping (E→E06/E07/E08/E09, W→W06, S→S12).
4. Helper functions: `country_prefix_from_code()`, `country_name_from_code()`, `country_status_from_code()`, `default_parent_name_for_country()`, `is_supported_lad_code()`, `supported_country_prefixes()`, `supported_overpass_bboxes()`, `point_in_supported_country_bbox()`.
5. Preserves `ENGLAND_BBOX` (now derived from dict) + adds `SCOTLAND_BBOX`, `GB_BBOX` for Overpass queries.

**Recommendation:** 🟢 TAKE
**Rationale:** This is the foundation for the entire Wales/Scotland/NI rollout which is already flagged in our MEMORY.md as planned. Every other ETL source file that uses country filtering now imports from this module. Pure additive — our existing `ENGLAND_BBOX` usage keeps working via the derived constant. **Must be taken first** before any other ETL source diff.
**Status:** `PENDING_REVIEW`

#### `etl/pipeline.py` — MODIFIED (+22 / -0)
**What Manus changed:** Adds two new entries to `SOURCE_REGISTRY`:
1. `land_registry_wales_ppd` — staged Welsh PPD CSV backfill, depends_on postcodes.
2. `connectivity_metric` — DfT connectivity metric 2025, no deps.

**Recommendation:** 🟢 TAKE (bundled with new source files)
**Rationale:** Trivial registry additions with no behaviour change for existing sources. Only useful if we take the corresponding `sources/*.py` files.
**Status:** `PENDING_REVIEW` (bundled with connectivity_metric + land_registry_wales_ppd decisions)

### ETL — new sources

#### `etl/sources/connectivity_metric.py` — ADDED (217 lines)
**What Manus added:** New source for DfT Transport Connectivity Metric 2025 (official ODS workbook). Downloads from GOV.UK if missing. Parses ODS XML, extracts LSOA-level scores for overall connectivity + walking/cycling/PT/driving breakdowns + employment/education/healthcare/leisure/shopping/residential sub-scores + PT-specific breakdowns. Inserts into `core_connectivity_lsoa`.
**Recommendation:** 🟢 TAKE (bundled with migration 008 + tab_lifestyle commuter_connectivity)
**Rationale:** Source-backed, official DfT data, 30k–36k expected rows (one per LSOA). Replaces our withdrawn heuristic `connectivity_index`. No external API dependency (direct HTTPS download from GOV.UK asset). Clean self-contained implementation.
**Status:** `PENDING_REVIEW` (bundled with migration 008 + backend tab_lifestyle)

#### `etl/sources/land_registry_wales_ppd.py` — ADDED (284 lines)
**What Manus added:** Wales-only PPD CSV backfill that:
- Reads from `etl/data/land_registry_wales/*.csv` (or `LAND_REGISTRY_WALES_GLOB`).
- Filters to rows where the postcode joins to a Welsh LSOA (via `core_postcodes`).
- Upserts into `core_property_transactions` on `transaction_id`, WITHOUT truncating existing national data.
- Uses the official HM Land Registry PPD report-builder CSV schema (`unique_id,price_paid,deed_date,postcode,property_type,new_build,estate_type,saon,paon,street,locality,town,district,county,transaction_category,linked_data_uri`).

**Recommendation:** 🟡 SELECTIVE — user decision
**Rationale:** This is a targeted fix for a storage problem Manus was hitting. Our environment has the full national `pp-complete.csv` ingest working. The Welsh PPD row-export path is useful as a fallback but not strictly needed if we already have Welsh data in our main ingest. **Need to verify**: do our `core_property_transactions` currently contain Welsh rows? If yes, this source is redundant; if no, it's the cleanest backfill path.
**Status:** `PENDING_REVIEW` + `ACTION_REQUIRED` (check existing Welsh transaction coverage)

#### `etl/data/section_114_notices.csv` — ADDED (1 line, header only)
**What Manus added:** Empty CSV with columns `lad_code,council_name,notice_date,source_url,document_url,source_type,verification_status,last_checked_at,notes`. Used by `etl/legacy/ingest_governance.py` to replace the hardcoded S114 list.
**Recommendation:** 🟢 TAKE (bundled with governance legacy update)
**Rationale:** Proper provenance schema for when S114 data becomes available. Zero rows = zero behaviour change, but the schema is correct. TAKE as a scaffold.
**Status:** `PENDING_REVIEW`

### ETL — migrations

#### `etl/migrations/008_connectivity_lsoa.sql` — ADDED
**What Manus added:** Creates `core_connectivity_lsoa` table (lsoa_code PK + 17 NUMERIC columns + source_release). Required by `sources/connectivity_metric.py`.
**Recommendation:** 🟢 TAKE (bundled with connectivity source + tab_lifestyle)
**Rationale:** Simple DDL. Verified the column set matches the DfT Connectivity Metric schema.
**Status:** `PENDING_REVIEW`

#### `etl/migrations/009_council_tax_band_i.sql` — ADDED (2 lines)
**What Manus added:** `ALTER TABLE core_council_tax_lad ADD COLUMN IF NOT EXISTS band_i NUMERIC(8,2);`
**Recommendation:** 🟢 TAKE (bundled with council_tax ingest update + tab_governance)
**Rationale:** Needed to support Welsh 9-band council-tax schedule. IF NOT EXISTS makes it idempotent. TAKE.
**Status:** `PENDING_REVIEW`

### ETL — modified sources (country-aware refactor)

These files all share the same refactor pattern: replace hardcoded `startswith("E")` / bbox literal with helpers from the new `etl/constants.py` (`is_supported_lad_code`, `supported_country_prefixes`, `SUPPORTED_LAD_CODE_PREFIXES_BY_COUNTRY`, `supported_overpass_bboxes`). All depend on `etl/constants.py` being taken first.

#### `etl/sources/ashe.py` — MODIFIED (+2 / -2) 🟢 TAKE
#### `etl/sources/broadband.py` — MODIFIED (+5 / -4) 🟢 TAKE — supports E+W via prefix check
#### `etl/sources/census.py` — MODIFIED (+13 / -10) 🟢 TAKE — adds W census geography filter
#### `etl/sources/epc_lsoa.py` — MODIFIED (+1 / -1) 🟢 TAKE — trivial import
#### `etl/sources/hpi.py` — MODIFIED (+5 / -4) 🟢 TAKE — uses `is_supported_lad_code`
#### `etl/sources/mobile_coverage.py` — MODIFIED (+5 / -3) 🟢 TAKE
#### `etl/sources/naptan.py` — MODIFIED (+5 / -10) 🟢 TAKE — replaces `_LAT_MIN/_LAT_MAX` literals with `point_in_supported_country_bbox`
#### `etl/sources/place_names.py` — MODIFIED (+4 / -3) 🟢 TAKE — uses `COUNTRY_PREFIX_BY_NAME`
#### `etl/sources/price_sqm.py` — MODIFIED (+7 / -3) 🟢 TAKE — E+W LAD prefix union

**Rationale for all 9 files above:** All are mechanical "replace literal filter with shared helper" changes. Each opens the door to Welsh data flowing through the ingest. Net behaviour preserved for England; Welsh rows now accepted where the data exists. Safe, low-risk, high-leverage. TAKE as one batch after `etl/constants.py`.
**Status:** `PENDING_REVIEW` (all 9 bundled)

#### `etl/sources/water.py` — MODIFIED (+15 / -3) 🟢 TAKE
**What Manus changed:** (1) Country-aware imports. (2) **Geometry fix**: wraps the incoming GeoJSON with `ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(...)), 3))` to handle invalid multipolygons from the Defra water-company boundary source. Prevents `invalid geometry` errors at insert time.
**Rationale:** The ST_MakeValid fix is a genuine bug fix independent of country-awareness. TAKE.
**Status:** `PENDING_REVIEW`

#### `etl/sources/lad_county_lookup.py` — MODIFIED (+32 / -11) 🟢 TAKE
**What Manus changed:** Country-aware filter on `LAD25CD[0].isin(_SUPPORTED_PREFIXES)` instead of `startswith('E')`. No other logic change.
**Status:** `PENDING_REVIEW`

#### `etl/sources/place_boundaries.py` — MODIFIED (+22 / -13) 🟡 SELECTIVE
**What Manus changed:** Replaces single `ENGLAND_BBOX` Overpass query with a multi-bbox query iterating `supported_overpass_bboxes()`. Larger Overpass payload.
**Rationale:** Works, but increases Overpass API load. We should verify the Overpass query still fits under rate limits and query timeout when expanded to include Wales + Scotland bboxes.
**Status:** `PENDING_REVIEW` (verify Overpass query budget)

#### `etl/sources/boundaries.py` — MODIFIED (+28 / -12) 🟢 TAKE
**What Manus changed:** `_fetch_all_features` helper now accepts `code_prefixes` tuple and filters the ONS Geography Portal feature collection accordingly. Called with `SUPPORTED_COUNTRY_PREFIXES` for both LAD and ward fetches. Builds `core_county_boundaries` by unioning LAD polygons for supported countries.
**Status:** `PENDING_REVIEW`

#### `etl/sources/governance.py` — MODIFIED (+51 / -24) 🟢 TAKE
**What Manus changed:** Adds `_load_s114_rows()` helper reading from `etl/data/section_114_notices.csv` (provenance-backed) instead of hardcoded list. If the CSV is empty or missing, the table is cleared and tab_governance correctly reports "no data available" (instead of a stale hardcoded list).
**Status:** `PENDING_REVIEW` (bundled with section_114_notices.csv scaffold + tab_governance withdrawal)

### ETL — modified sources (feature-rich, non-trivial)

#### `etl/sources/council_tax.py` — MODIFIED (+212 / -46) 🟢 TAKE
**What Manus changed:**
1. Adds Welsh StatsWales council-tax CSV path (`COUNCIL_TAX_WALES_PATH`, defaults to `etl/data/council/statswales_council_tax.csv`).
2. Adds `_WELSH_BAND_MAP` with 9 bands (A–I) — Wales has band I which England doesn't.
3. Splits ingest into `_read_england_rows()` + `_read_wales_rows()` and merges results.
4. Validates Welsh authority codes via `is_supported_lad_code()` + W prefix check.
5. Final table TRUNCATE + bulk insert combined rows.

**Rationale:** Proper multi-country council tax support. Requires migration 009 (band_i column). If the Welsh CSV isn't present, the loader prints a message and leaves Wales unchanged — graceful degradation. TAKE.
**Status:** `PENDING_REVIEW`

#### `etl/sources/crime.py` — MODIFIED (+171 / -8) 🟢 TAKE
**What Manus changed:**
1. Adds ONS Wales 2011→2021 LSOA lookup download (`_WALES_LOOKUP_URL` from ONS hub).
2. `_largest_remainder_allocation()` for splitting crime counts across multiple target LSOAs when one 2011 LSOA maps to multiple 2021 LSOAs (uses postcode weights from `core_postcodes`).
3. `_load_wales_lsoa_crosswalk()` builds the per-source-code list of weighted targets.
4. `_normalize_bulk_counts()` rewrites incoming police data from Welsh 2011 LSOA codes to the current 2021 LSOA geography using the crosswalk.
5. Rest of the ingest loop unchanged but now normalises each row through the crosswalk.

**Rationale:** Solves a genuine technical problem — the police data still uses 2011 LSOA codes for Wales, while our master boundary tables use 2021 LSOAs. Without crosswalk, Welsh crime rows get orphaned. The largest-remainder allocation is the correct method for integer count redistribution (standard technique). Dependencies: requires the lookup CSV download path to work and to be cached under `etl/data/`. TAKE.
**Status:** `PENDING_REVIEW`

#### `etl/sources/postcodes.py` — MODIFIED (+273 / -154) 🟡 SELECTIVE
**What Manus changed:**
1. Adds `_resolve_onspd_path()` — searches `~/.cache/onspd/`, `etl/data/`, ONSPD_PATH env var for an existing ZIP/CSV.
2. Adds `_load_catchment_names()` and `_load_county_lookup()` helpers.
3. Adds `_normalise_columns()` to handle both old and new ONSPD column names.
4. Restructures the ingest loop around the resolved ONSPD source (ZIP vs extracted CSV).
5. Supports `SUPPORTED_COUNTRY_PREFIXES` for country filtering.

**Rationale:** The core-function is the same (stream ONSPD → insert postcodes), but the restructure is substantial. Our version has been heavily tuned. Need careful line-by-line comparison before merging — risk of regression in the foundational table. **RECOMMEND SELECTIVE**: cherry-pick the country filter + ZIP/CSV path resolution, skip the rest until tested end-to-end on our infra.
**Status:** `PENDING_REVIEW`

#### `etl/sources/epc_domestic.py` — MODIFIED (+265 / -217) 🔴 SKIP
**What Manus changed:** Rewrites the ingest path to support three modes: local ZIP (our current path), archive directory (year-sliced ZIPs), token-authenticated remote download from the official portal. Adds session management, discovery of year-sliced download links, retry/resume logic.
**Recommendation:** 🔴 SKIP
**Rationale:** Our version already ingests the full 29.2M-row bulk ZIP successfully. The year-sliced + token-auth paths are Manus-environment workarounds for a storage problem we don't have. The rewrite touches the core COPY loop and would risk regressing an ingest that took hours to get right. SKIP.
**Status:** `PENDING_REVIEW`

#### `etl/legacy/ingest_governance.py` — MODIFIED (+39 / -?)
**What Manus changed:** Replaces hardcoded S114 notice list with CSV reader from `SECTION_114_PATH`. Empty CSV = empty table = honesty pass.
**Recommendation:** 🟢 TAKE (bundled with section_114_notices.csv scaffold + governance.py provenance change + tab_governance withdrawal)
**Status:** `PENDING_REVIEW`

### ETL — new diagnostic/run scripts (7 files)

Manus added these operational scripts:
- `etl/run_boundaries_from_live_postcodes.py` — rebuild boundaries from live postcode table
- `etl/run_crime_from_police_zip.py` — rerun crime ingest from cached police.uk ZIP
- `etl/run_land_registry_wales_only.py` — run the new Welsh PPD source in isolation
- `etl/run_postcodes_from_onspd.py` — run postcodes ingest from a specific ONSPD path
- `etl/audit_wales_ppd_char_fields.py` — diagnostic: audit max field widths in Welsh PPD CSV to detect TEXT column overflow
- `etl/diagnose_wales_ppd_failure.py` — diagnostic: replay a failing Welsh PPD batch with verbose logging
- `etl/inspect_police_zip_coverage.py` — diagnostic: report LSOA coverage per month inside the police ZIP

**Recommendation:** 🟢 TAKE (operational utilities, no risk)
**Rationale:** These are dev-ops helpers, not ingest code. They don't change any ETL source behaviour. Taking them gives us quick rerun paths for Welsh + boundary + crime debugging. Zero risk.
**Status:** `PENDING_REVIEW`

---

