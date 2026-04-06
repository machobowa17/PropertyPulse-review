"""ETL: ONS UK House Price Index → core_hpi_lad. Bible: Tab 1 Property Market.
Downloads UK HPI data from ONS/Land Registry open data."""
import os, csv, requests, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
HPI_URL = "http://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-2025-01.csv"
HPI_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/uk_hpi.csv")

def download_hpi():
    if os.path.exists(HPI_PATH):
        print("  HPI file exists, skipping download")
        return
    print("  Downloading UK HPI data...")
    resp = requests.get(HPI_URL, timeout=120)
    resp.raise_for_status()
    os.makedirs(os.path.dirname(HPI_PATH), exist_ok=True)
    with open(HPI_PATH, "wb") as f:
        f.write(resp.content)
    print(f"  Downloaded {len(resp.content)/1024/1024:.1f} MB")

def ingest():
    print("Ingesting UK HPI...")
    download_hpi()

    # Build LAD name→code lookup from core_lad_boundaries
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT lad_code, lad_name FROM core_lad_boundaries")
    lad_lookup = {}
    for code, name in cur.fetchall():
        if name:
            lad_lookup[name.lower()] = code
    print(f"  LAD lookup: {len(lad_lookup)} entries")

    cur.execute("TRUNCATE TABLE core_hpi_lad CASCADE")

    rows = []
    with open(HPI_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            region = r.get("RegionName", "").strip()
            area_code = r.get("AreaCode", "").strip()

            # Only LAD-level England codes
            if not area_code.startswith("E0"):
                continue

            date_str = r.get("Date", "")
            if not date_str:
                continue

            try:
                avg_price = float(r.get("AveragePrice", "")) if r.get("AveragePrice") else None
                index_val = float(r.get("Index", "")) if r.get("Index") else None
                sales_vol = int(float(r.get("SalesVolume", "") or 0)) if r.get("SalesVolume") else None
                det = float(r.get("DetachedPrice", "")) if r.get("DetachedPrice") else None
                semi = float(r.get("SemiDetachedPrice", "")) if r.get("SemiDetachedPrice") else None
                terr = float(r.get("TerracedPrice", "")) if r.get("TerracedPrice") else None
                flat = float(r.get("FlatPrice", "")) if r.get("FlatPrice") else None
                yoy = float(r.get("12m%Change", "")) if r.get("12m%Change") else None
            except (ValueError, TypeError):
                continue

            rows.append((
                area_code, date_str, avg_price, index_val, sales_vol,
                det, semi, terr, flat, yoy
            ))

    print(f"  Collected {len(rows):,} HPI records")
    if rows:
        execute_values(cur, """INSERT INTO core_hpi_lad
            (lad_code, date, average_price, index_value, sales_volume,
             detached_price, semi_detached_price, terraced_price, flat_price, yearly_change_pct)
            VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=10000)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_hpi_lad")
    print(f"core_hpi_lad: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
