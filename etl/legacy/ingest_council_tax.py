"""ETL: VOA Council Tax → core_council_tax_lad. Bible: Tab 5 Council & Tax.
Data format: E Code, ONS Code, Authority, Region, Class, Area, Band A-H, Notes."""
import os, psycopg2
import pandas as pd
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/council/ctb1_table8.ods")

def ingest():
    print("Ingesting council tax...")
    # Read with no header (header is row 2 = index 2)
    df = pd.read_excel(SRC, engine="odf", header=None, skiprows=2)
    # Columns: E Code(0), ONS Code(1), Authority(2), Region(3), Class(4), Area(5),
    #          Band A(6), Band B(7), Band C(8), Band D(9), Band E(10), Band F(11), Band G(12), Band H(13)
    print(f"  Read {len(df)} rows")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_council_tax_lad CASCADE")

    rows = []
    for _, r in df.iterrows():
        lad_code = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        if not lad_code.startswith("E"):
            continue
        # Skip region/country level codes
        if lad_code.startswith("E12") or lad_code.startswith("E92"):
            continue
        try:
            bands = []
            for i in range(6, 14):
                val = float(r.iloc[i]) if pd.notna(r.iloc[i]) else None
                bands.append(val)
            if any(b is not None for b in bands):
                rows.append((lad_code, *bands))
        except (ValueError, IndexError):
            continue

    print(f"  Collected {len(rows):,} LADs")
    if rows:
        execute_values(cur, """INSERT INTO core_council_tax_lad
            (lad_code, band_a, band_b, band_c, band_d, band_e, band_f, band_g, band_h)
            VALUES %s ON CONFLICT DO NOTHING""", rows)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_council_tax_lad")
    print(f"core_council_tax_lad: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
