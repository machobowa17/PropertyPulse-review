# PropertyPulse — Pipeline Queue

## Data Ingestion
- [ ] **EPC raw certificate ingestion**: Download DLUHC domestic EPC open data, ingest into `raw_epc_domestic` table in ukproperty, then aggregate by property type (house/flat/bungalow) per LSOA into `core_epc_lsoa`. This enables EPC score breakdown by house type in the Property & Market tab details panel.
- [ ] **Census TS017 — Household size**: `~/Downloads/census2021-ts017.zip` → LSOA-level. Columns: 1-person %, 2-person %, 3+ person %. Useful as detail breakdown on Household Composition metric (Community tab).
- [ ] **Census TS022 — Ethnicity (detailed)**: `~/Downloads/census2021-ts022-extra.zip` → ward-level only. Columns: Asian/Asian British, Black/Black British, Mixed, White, Other. Useful as detail on Demographics (Community tab).
- [ ] **Census TS027 — National identity**: `~/Downloads/census2021-ts027.zip` → LSOA-level. Columns: British only, English only, Welsh only, Scottish only, Other. Parked — low priority for property search context.
- [ ] **Census TS031 — Religion (detailed)**: `~/Downloads/census2021-ts031-extra.zip` → ward-level only. Columns: Christian, Muslim, Hindu, Jewish, Sikh, Buddhist, No religion. Parked — low priority.
- [ ] **Census TS058 — Distance to work**: `~/Downloads/census2021-ts058.zip` → LSOA-level. Columns: <2km, 2-5km, 5-10km, 10-20km, 20-30km, 30km+, WFH. Could add a "typical commute distance" metric to Lifestyle tab.
