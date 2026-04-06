-- Individual Land Registry Price Paid transactions for map pin display
CREATE TABLE IF NOT EXISTS core_property_transactions (
  transaction_id TEXT PRIMARY KEY,
  price INTEGER NOT NULL,
  date_of_transfer DATE NOT NULL,
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
  lsoa_code TEXT
);

CREATE INDEX IF NOT EXISTS idx_transactions_geom ON core_property_transactions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON core_property_transactions (date_of_transfer DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_postcode ON core_property_transactions (postcode);
