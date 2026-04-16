-- core_property_transactions — HM Land Registry PPD + EPC backfill + LSOA aggregates
CREATE TABLE IF NOT EXISTS core_property_transactions (
  transaction_id TEXT PRIMARY KEY,
  price INTEGER,
  date_of_transfer DATE,
  postcode TEXT,
  property_type CHAR(1),
  old_new CHAR(1),
  duration CHAR(1),
  paon TEXT,
  saon TEXT,
  street TEXT,
  locality TEXT,
  town TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  geom GEOMETRY(Point, 4326),
  lsoa_code TEXT,
  lad_code TEXT,
  -- PPD extra columns (district/county/category)
  district TEXT,
  county TEXT,
  ppd_category CHAR(1),
  -- EPC backfill columns (populated by backfill_epc_matching + backfill_epc_floor_area)
  epc_certificate_number TEXT,
  epc_match_score DOUBLE PRECISION,
  floor_area_sqm DOUBLE PRECISION,
  habitable_rooms INTEGER,
  bedrooms_estimated INTEGER,
  epc_rating CHAR(1),
  price_per_sqm DOUBLE PRECISION,
  price_per_sqft DOUBLE PRECISION,
  -- Pre-computed LSOA/month/type aggregates (populated by 006_populate_aggregates)
  lsoa_month_avg_price DOUBLE PRECISION,
  lsoa_month_median_price DOUBLE PRECISION,
  lsoa_month_min_price INTEGER,
  lsoa_month_max_price INTEGER,
  lsoa_month_transaction_count INTEGER,
  lsoa_month_new_build_count INTEGER,
  lsoa_month_freehold_count INTEGER,
  lsoa_month_leasehold_count INTEGER,
  lsoa_month_avg_freehold_price DOUBLE PRECISION,
  lsoa_month_avg_leasehold_price DOUBLE PRECISION,
  lsoa_month_avg_ppsm DOUBLE PRECISION,
  lsoa_month_avg_ppsft DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_transactions_geom ON core_property_transactions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_transactions_geom_geog ON core_property_transactions USING GIST ((geom::geography));
CREATE INDEX IF NOT EXISTS idx_transactions_date ON core_property_transactions (date_of_transfer);
CREATE INDEX IF NOT EXISTS idx_transactions_postcode ON core_property_transactions (postcode);
CREATE INDEX IF NOT EXISTS idx_transactions_lad ON core_property_transactions (lad_code);
CREATE INDEX IF NOT EXISTS idx_transactions_lsoa_date_type ON core_property_transactions (lsoa_code, date_of_transfer, property_type);
CREATE INDEX IF NOT EXISTS idx_transactions_floor_area ON core_property_transactions (floor_area_sqm) WHERE floor_area_sqm IS NOT NULL AND floor_area_sqm > 0;
