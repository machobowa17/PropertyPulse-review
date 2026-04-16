# PropertyPulse — Master Work Queue

Last updated: 2026-04-16 (session 33 — AI Studio Review Fixes COMPLETE)

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

- G12: DecisionMode wiring → **DEFER** (feature design, not a bug)
- Postcode district `dist_len` → Not a bug (WHERE clause works correctly)
- "Fast typer" race → Not a bug (trigram fallback handles)

---

### Phase 3: AWS Deployment (after Phase 2.5)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 13 | AWS: Create account, configure eu-west-2 | Pending | See `memory/deployment.md` |
| 14 | AWS: Launch t4g.small + 80 GB gp3 EBS | Pending | Depends on #13. Tune postgresql.conf per R22 on first boot. |
| 15 | AWS: Provision Docker + docker-compose (AL2023, ARM) | Pending | Depends on #14 |
| 16 | AWS: `pg_dump` → upload → `pg_restore` on EC2 | Pending | Depends on #15 |
| 17 | AWS: Frontend build → S3 + CloudFront | Pending | Depends on #14 |
| 18 | AWS: DNS + TLS (Let's Encrypt) | Pending | Depends on #17 |
| 19 | AWS: GitHub Actions CI/CD | Pending | Depends on #18 |

---

### Post-AWS

| # | Task | Status | Notes |
|---|------|--------|-------|
| R15 | Isochrone school catchments — Outstanding schools within 15-min walk | Pending | Family persona "holy grail". 90% infra exists. |
| G12 | DecisionMode wiring — Buy/Rent/Invest affects scoring | Pending | Feature design, needs product thinking. |

---

### Parked / Won't Do

| # | Task | Rec | Notes |
|---|------|-----|-------|
| R6 | Reduce `execute_values` page_size 10000 → 1000 in ETL | **SKIP** | ETL-only. No user-facing impact. |
| R23 | PgBouncer connection pooling | **DEFER** | Adequate at launch. Revisit when connections bottleneck. |

---

## DB State (session 32)

| Table | Rows | Notes |
|-------|------|-------|
| core_property_transactions | 30.4M | E=29.0M, W=1.45M, ~4.2M with EPC backfill |
| core_postcodes | 1.75M | E+W+S |
| core_crime_lsoa | 5.96M | E+W |
| core_noise | 1.43M | 367/367 DEFRA tiles |
| core_inspire_parcels | 24,255,962 | 318 authorities |
| core_llc_charges | 7,720,311 | 141 authorities |
| core_flood_zones | 3,536,992 | FZ2 82.6%, FZ3 17.4% |

### Google Drive Assets

| Item | Location |
|------|----------|
| DB dump v2 | `gdrive:PropertyPulse/ukproperty_20260413_v2.dump` |
| core_epc_domestic backup | `gdrive:PropertyPulse/core_epc_domestic.dump` (1.2 GB) |
| INSPIRE raw | `gdrive:PropertyPulse/raw_downloads/INSPIRE/` |
| LLC raw | `gdrive:PropertyPulse/raw_downloads/LLC/` |
| Flood GeoPackage | `gdrive:PropertyPulse/raw_downloads/` |
| Codebase snapshot (prev) | `gdrive:PropertyPulse/codebase_review_20260415/` (182 files) |
| Codebase snapshot (latest) | `gdrive:PropertyPulse/codebase_review_20260416/` (344 files, 39.5 MiB) |

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
