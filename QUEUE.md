# PropertyPulse — Master Work Queue

Last updated: 2026-04-30 (session 71)

**This is the SINGLE source of truth for all pending tasks. Completed work is in CHANGELOG.md.**

---

## Pending — Phase 7 Remaining

| # | Task | Status | Notes |
|---|------|--------|-------|
| P9 | Scotland + NI coverage | Pending | Scope, data sources, feasibility TBD. |
| P53 | Single address search — show all data for a specific property | Pending | Full address search (e.g. "14 Acacia Avenue, SW1A 1AA"). Display transaction history, EPC, floor area, type, tenure, flood, LLC, INSPIRE, noise, broadband. Classic UK EPC arrow chart. Requires: resolve endpoint, address-level results view, DB scan for address-level data. Data plan: D28. |

---

## Pending — Post-AWS

| # | Task | Status | Notes |
|---|------|--------|-------|
| M2 | Choropleth: national coverage via PMTiles (vector tiles) | Pending | Pre-generate PMTiles per layer using `tippecanoe` from `core_lsoa_boundaries` + metric values. ~35k polygons/layer → ~10-50MB per file. Host on S3/CloudFront. Frontend: swap `type: 'geojson'` for `type: 'vector'` + PMTiles protocol. ~30 layers × ~20MB = ~600MB. Do after M1 proves demand. |

---

## Pending — Phase 8 Data Items

| # | Task | Status | Notes |
|---|------|--------|-------|
| D28 | Per-property datasets for address-level search (P53) | Pending | See spec below. |
| D30 | Surface INSPIRE + LLC at property level (feeds P53) | Pending | `ST_Contains(geom, property_point)` for parcel boundary, LLC charges. Data already ingested and indexed. |
| D32 | P53 EPC Lookup: current EPC + EPC at time of sale | Pending | Bypass matching engine, query `bronze.raw_epc_domestic` directly by address. ~92% coverage. |
| D33 | NPD Workaround: catchment probability model | Pending | Reconstruct ~80% of school catchment insight from LDO + admissions + capacity + geography. `compute_catchment.py` on Hetzner. Depends on D35 (LA scraping for LDO data). |
| D35 | LA admissions booklet scraping | In Progress | Scrape 150 LA admission booklets. PoC complete (Croydon, session 71). See D35 spec below. |
| D36 | SEND / ELP directory | Pending | Special schools + Enhanced Learning Provisions. Specialism, age range, address, contact. Extracted per-LA from admissions booklets (D35). "No one caters to SEND families — we will." |

### D35 Spec — LA Admissions Booklet Scraping

**PoC (session 71):** Croydon secondary — 23 schools, 13 with LDO, full allocation breakdowns. Parser: `pdfplumber` + positional text parsing. Output: `/tmp/croydon_admissions_extracted.json`.

**Core extraction per LA:**

| Field | Priority | Source |
|-------|----------|--------|
| PAN (Published Admission Number) | Must have | School list table |
| Applications received | Must have | School list table |
| Oversubscription ratio (derived) | Must have | apps / PAN |
| Allocation breakdown per criterion | Must have | Allocation overview table |
| LDO (Furthest Distance Offered) | Must have | Allocation overview table |
| Distance measurement method | Must have | Policy text (straight-line vs walking) |
| SIF required (Yes/No) | Must have | School list table |
| Open days/evenings | Must have | Dates, times, booking info per school |
| SEND / ELP provisions | Must have | Special schools section (feeds D36) |

**Risks:** Format varies wildly per LA. ~30% clean tables, ~40% semi-structured prose, ~15% image PDFs (OCR needed), ~15% HTML. Confidence scoring needed. Per-LA parsers likely required for non-standard formats.

**Presentation plan:** Admissions Intelligence section per school — horizontal allocation bar chart, LDO comparison ("your distance vs cutoff"), sibling caveat, LDO circle on map with measurement method label, source + year caveat.

**Scale plan:** Tier 1 = top 30-40 LAs (~60% of England's school-age population). Tier 2 = remaining ~110 LAs.

---

### D28 Spec — Per-Property Data Sources

**Datasets we already have (just need property-level queries):**

| # | Dataset | Join key | What it adds |
|---|---------|----------|-------------|
| D28-1 | Land Registry PPD | address match | Full transaction history |
| D28-2 | EPC certificates (expand to all 93 columns) | address/UPRN | Full energy certificate |
| D28-3 | INSPIRE Index Polygons | spatial | Land parcel boundary + title number |
| D28-4 | Local Land Charges | spatial | Planning charges, TPOs, conservation area |
| D28-5 | Flood zones | spatial | "This property is in Flood Zone 2" |
| D28-6 | Crime | spatial (nearby) | Crimes within 200m, last 12 months |
| D28-7 | Noise | spatial | Road/rail dB at exact location |
| D28-8 | Broadband | postcode | Max download/upload speed |

**New datasets to ingest (all free, OGL):**

| # | Dataset | Source | What it adds | Priority | Effort |
|---|---------|--------|-------------|----------|--------|
| D28-9 | Council Tax Band (VOA) | gov.uk | Band A-H + annual cost | 2nd | Medium |
| D28-10 | Listed Building status | Historic England | Grade I/II*/II + listing description | 3rd | Low |
| D28-11 | Ground stability / subsidence (BGS GeoSure) | bgs.ac.uk | Shrink-swell clay risk, landslip | 5th | Medium |
| D28-12 | Planning applications | Council APIs / PlanIt | Extensions, change of use, approvals | 7th | High |
| D28-13 | Corporate & Overseas Ownership (CCOD/OCOD) | Land Registry | Company name + country for corporate-owned | 6th | Medium |
| D28-14 | Radon risk (UKHSA) | ukradon.org | Radon probability band (1-5%) | 4th | Low |
| D28-15 | OS Open UPRN | osdatahub.os.uk | Lat/lng for every UPRN (foundation dataset) | 1st | Medium |

---

## Pending — Phase 9: Financial Tools & Discovery Features

Source: Competitive analysis of Findstead.co.uk (session 67). All from our own data + public government formulae.

| # | Task | Status | Notes |
|---|------|--------|-------|
| F1 | Stamp duty calculator | Pending | HMRC formulae, pure arithmetic. Standard rates, first-time buyer relief, additional property surcharge (3%), Welsh LTT. |
| F2 | Mortgage affordability estimate | Pending | BoE average rates + area price data. Monthly repayment, affordability ratio, LTV. |
| F3 | Rent vs Buy comparison | Pending | Side-by-side rent vs mortgage repayment. Break-even analysis. No external data. |
| F4 | "Areas you haven't considered" — comparable areas reframed | Pending | 11D comparable areas + price filtering. "Similar scores at lower prices." |
| F5 | Persona-driven onboarding flow | Pending | Pick persona → budget range → commute destination → pre-filtered results. |

---

## Pending — BurbScore Design Refresh

Source: Session 67 competitive analysis. User approved direction. Prototype2 exists at `/prototype2`.

**Status:** Awaiting re-implementation. First attempt (session 67) reverted — 14 of 22 renderers only got invisible `isAnimationActive` one-liners. Plumbing preserved (context, toggle, prop threading).

**22 renderers to implement** — each mapped to exact file, BurbScore visual spec, affected metrics, and estimated LOC. Consolidated reference in `.claude/plans/mutable-nibbling-flurry.md`.

**10 cross-cutting patterns:**

| # | Pattern | Effect |
|---|---------|--------|
| C1 | Smooth curves (`type="monotone"`) | Catmull-Rom vs angular lines |
| C2 | Fixed hover readouts | Values in fixed top-left box, not floating tooltip |
| C3 | Parent comparison bars/markers | Vertical tick with label on all bars |
| C4 | Series dimming | Non-hovered chart lines → 30% opacity |
| C5 | Dual comparison rows | Local bar + parent bar stacked |
| C6 | Animated number counters | Headlines count from 0→value on mount |
| C7 | Warm color shifts | Earth tones, section-colored accents |
| C8 | Skeleton shimmers | Section-colored loading placeholders |
| C9 | Staggered entrance | fadeInUp with 50ms delay per card |
| C10 | `prefers-reduced-motion` | All animations suppressed |

---

## Pending — Phase 10: GeoDepth/SimplySettled Retrospective — Stealable Ideas

Source: Audit of `~/Desktop/geodepth/` codebase (session 68). That project had 76 datasets, 130+ DB tables, and features/patterns we never ported. **Compare notes against `~/Desktop/geodepth/` at implementation time.**

### 10A — Whole Features

| # | Feature | Notes |
|---|---------|-------|
| GD1 | **Find My Area — Multi-Dimensional Area Discovery** (`/find-my-area`) | Step-by-step wizard: workplace → budget → max distance → priority toggles → dealbreakers. PostGIS spatial filters + priority weights → ranked results on map. We have ALL underlying data. Richer version of F4+F5. GeoDepth: `web/app/find-my-area/page.tsx`. **"The killer differentiator."** |
| GD2 | **Rankings — Top 10 Area Lists** (`/rankings`) | Category-based rankings per LAD: Greenest, Best Connected, Safest, Best for Families, Best Value. Low effort, high SEO value. GeoDepth: `web/app/rankings/page.tsx`. |
| GD3 | **Compare — Side-by-Side Area Comparison** (`/compare`) | Head-to-head comparison of two postcodes/areas. URL: `/compare?a=SW1A+1AA&b=CR0+1LG`. Dual-column scorecard. GeoDepth: `CompareView.tsx`. |
| GD4 | **Portfolio Scorer — Bulk Postcode Upload** (`/portfolio`) | Upload CSV of postcodes → scored results + CSV export. For estate agents, investors, relocation consultants. GeoDepth: `UploadZone` + `PortfolioSummary`. |

### 10B — Data Sources We're Missing

**Low effort:**

| # | Dataset | Source | What it adds | Priority |
|---|---------|--------|-------------|----------|
| GD-D1 | Light pollution (CPRE Night Blight) | CPRE + VIIRS satellite | Artificial sky brightness score. Unique. | Medium |
| GD-D2 | Fly-tipping incidents | Defra | LAD-level incidents per 1,000 pop | High |
| GD-D3 | Fuel poverty (LSOA) | DESNZ | Fuel-poor households proportion | High |
| GD-D4 | DWP benefit claimant count | DWP Stat-Xplore | LSOA-level claimant rate | High |
| GD-D5 | ONS Wellbeing scores | ONS Annual Population Survey | Life satisfaction, happiness, anxiety, worthwhile | High |
| GD-D6 | Population projections (2030/2040) | ONS subnational projections | "Expected to grow 12% by 2040" | Medium |
| GD-D7 | Heritage at Risk register | Historic England | At-risk heritage assets | Low |
| GD-D8 | Conservation areas | Historic England | Conservation area boundaries + at-risk | Medium |
| GD-D9 | CRoW Act open access land | Natural England | Open access land polygons | Low |
| GD-D10 | Water company performance (Ofwat) | Ofwat Performance Report | Leakage, pollution incidents, complaints, avg bill | Medium |
| GD-D11 | NSIP projects + enterprise zones + freeports | Planning Inspectorate / HM Treasury | Development pipeline signal | Low |
| GD-D12 | MP lookup | Parliament API | MP name, party, email | Low |

**Medium effort:**

| # | Dataset | Source | What it adds | Priority |
|---|---------|--------|-------------|----------|
| GD-D13 | Coastal erosion (NCERM 2024) | Environment Agency | Erosion predictions under 4 scenarios. High impact for coastal. | Medium |
| GD-D14 | DESNZ actual energy consumption (LSOA, 2010-2024) | DESNZ | ACTUAL running costs — not EPC estimates. 15-year time series. | High |
| GD-D15 | DfT traffic counts (AADF) | DfT | Road congestion signal. Nearest count point + daily flow. | Medium |
| GD-D16 | Food hygiene ratings (FSA) | FSA FHRS API | "94% of food businesses rated 4-5." | Medium |
| GD-D17 | Brownfield land register | DLUHC | Development pipeline. Sites, hectares, dwelling capacity. | Medium |
| GD-D18 | Corporate/overseas ownership (CCOD/OCOD) | HM Land Registry | Area-level corporate title counts + top owners. (See also D28-13.) | Medium |
| GD-D19 | Charity register | Charity Commission | Community/social infrastructure. Count + top charities by income. | Low |
| GD-D20 | Nurseries & care homes | Ofsted / CQC | Family/retiree amenity. Nearest + count within radius. | Medium |

**Cross-reference with our queue:**

| GeoDepth dataset | Our item | Status |
|-----------------|----------|--------|
| Radon risk | D28-14 | Planned (part of P53) |
| Corporate ownership | D28-13 | Planned (part of P53) — GD-D18 does area-level |
| Listed buildings | D28-10 | Planned (part of P53) |
| OS Open UPRN | D28-15 | Planned (foundation for P53) |
| Conservation areas | GD-D8 | New |
| Brownfield | GD-D17 | New |

### 10C — UI/UX Patterns Worth Stealing

| # | Pattern | Description | Effort |
|---|---------|-------------|--------|
| GD-U2 | Question-based metric framing | "What's the crime rate?" instead of `crime_rate`. Add `question` field to registry. | Low |
| GD-U6 | "If you love this area..." framing | Comparable areas with similarity %, trajectory grade, natural-language WHY. | Low |
| GD-U7 | IntelligenceCard structure | 6-layer card: question heading, headline, summary, reassurance tip, expandable detail, source footer. | Medium |
| GD-U8 | GeoToggle — per-card geographic level switcher | Pill bar to switch metrics between postcode/ward/borough/county. | High |

### 10D — Narrative/Content Architecture

| # | Pattern | Description |
|---|---------|-------------|
| GD-N1 | "Looking Ahead" subsection | Forward-looking: brownfield pipeline, heritage constraints, business vitality, population trajectory, NSIP, enterprise zones. |
| GD-N2 | Takeaway engine "Sacred Rules" | 9 codified rules. 18-word cap. NO metrics/numbers in takeaway text. Outlier-driven. Sentiment colour from deviation. |
| GD-N3 | ESG composite scoring | E/S/G sub-scores + "Stranded asset" flag. Investor framing. |
| GD-N4 | Verdict Composer — intent × lifestyle matrix | 6 intents × 13 lifestyles × 22 concerns. Geometric mean weighting. Richer than our 4 personas × 3 modes. |
| GD-N5 | Cost of Living subsection | Unified view: council tax, energy, water, commute cost, childcare, stamp duty. |
| GD-N6 | Community organisations | Charities, food banks, community centres, nurseries, care homes. |
| GD-N7 | Walking & outdoor access | PRoW km, NCN routes, national trails, CRoW land, bike hire/parking. |
| GD-N8 | Water quality (WFD) | EA Catchment Data Explorer. Water body classification + ecological status. |
| GD-N9 | Contaminated land / pollution incidents | EA pollution incidents registry. Nearest + count within 2km. |

### 10E — Design Patterns

| # | Pattern | Description |
|---|---------|-------------|
| GD-V1 | Warm gradient mesh backgrounds | Multi-colour radial gradient orbs at 3-7% opacity with blur-3xl. |
| GD-V2 | Glass card style (`gd-glass`) | Backdrop blur + border + shadow. Score-dependent glow. |
| GD-V4 | Card entrance animations | Staggered fade-in with `card-enter` CSS class. |
| GD-V6 | Three-font system | Heading (serif) + mono (data) + sans (body). |
| GD-V7 | Dot-grid background | Radial gradient dots at 40×40px, 25% opacity. |

---

## Parked / Won't Do

| # | Task | Rec | Notes |
|---|------|-----|-------|
| R6 | Reduce `execute_values` page_size 10000 → 1000 in ETL | SKIP | ETL-only. No user-facing impact. |
| R23 | PgBouncer connection pooling | DEFER | Revisit when connections bottleneck. |
| D8 | financial_health/S114 data source | DEFERRED | Needs provenance-backed data source. |
| D9 | Commute estimator (501 Not Implemented) | WON'T FIX | No local data source. Frontend-only via TfL/Google APIs. |
| D34 | School Intelligence Module | COMPLETE | Closed session 71. 17 tables, 16 ETL scripts, 10 API endpoints, 7 SchoolTable tabs — all operational. Independent fees parked (no public data source). |

---

## Reference — DB State (session 37)

| Table | Rows | Notes |
|-------|------|-------|
| core_property_transactions | 30.4M | E=29.0M, W=1.45M, ~5.3M with EPC backfill |
| core_postcodes | 1.75M | E+W+S |
| core_crime_lsoa | 5.96M | E+W (incl. GMP verified) |
| core_noise | 1.43M | 367/367 DEFRA tiles |
| core_inspire_parcels | 24,255,962 | 318 authorities |
| core_llc_charges | 7,720,311 | 141 authorities |
| core_flood_zones | 3,536,992 | FZ2 82.6%, FZ3 17.4% |
| core_flood_lsoa | 33,755 | Per-LSOA flood exposure (derived) |
| core_lad_county_lookup | 318 | 49 county groups + 6 singletons |
| core_place_boundaries_union | 9,565 | Pre-computed ST_Union per place |
| core_price_by_bedrooms_lad | 144,906 | LAD/year/type/bedroom aggregation |
| core_census_religion_ward | 7,638 | Census 2021 TS031 |

---

## Reference — Google Drive Assets

| Item | Location |
|------|----------|
| DB dump v2 | `gdrive:PropertyPulse/ukproperty_20260413_v2.dump` |
| core_epc_domestic backup | `gdrive:PropertyPulse/core_epc_domestic.dump` (1.2 GB) |
| INSPIRE raw | `gdrive:PropertyPulse/raw_downloads/INSPIRE/` |
| LLC raw | `gdrive:PropertyPulse/raw_downloads/LLC/` |
| Flood GeoPackage | `gdrive:PropertyPulse/raw_downloads/` |
| Codebase snapshot (latest) | `gdrive:PropertyPulse/codebase_review_20260417/` (360 files) |
| Public review repo | https://github.com/machobowa17/PropertyPulse-review |

---

## Reference — Architecture Decisions (NEVER violate)

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
