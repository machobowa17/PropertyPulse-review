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

(entries added below as each file is reviewed)

