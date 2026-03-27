"""ETL: VOA Private Rental Market Statistics → core_voa_rents_lad. Bible: Tab 1 Rental Market.
XLS sheets: Table2.3=1bed, Table2.4=2bed, Table2.5=3bed, Table2.6=4+bed, Table2.7=all.
Data rows: nan, LA Code, Area Code, Area, Count, Mean, Lower Q, Median, Upper Q."""
import os, pandas as pd, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/voa_rents.xls")

SHEETS = {
    "all": "Table2.7",
    "1bed": "Table2.3",
    "2bed": "Table2.4",
    "3bed": "Table2.5",
    "4bed": "Table2.6",
}

def parse_sheet(xls, sheet_name):
    """Parse a VOA rents sheet, return {area_code: median_rent}."""
    df = xls.parse(sheet_name, header=None, skiprows=6)
    results = {}
    for _, r in df.iterrows():
        # Area code is in column 2 for LADs (E06/E07/E08/E09)
        area_code = str(r.iloc[2]).strip() if pd.notna(r.iloc[2]) else ""
        if not area_code.startswith("E0"):
            continue
        try:
            median = float(r.iloc[7]) if pd.notna(r.iloc[7]) else None
            if median is not None:
                results[area_code] = median
        except (ValueError, IndexError):
            continue
    return results

def ingest():
    print("Ingesting VOA rents...")
    xls = pd.ExcelFile(SRC)

    medians = {}
    for key, sheet in SHEETS.items():
        data = parse_sheet(xls, sheet)
        print(f"  {key}: {len(data):,} LADs")
        for code, val in data.items():
            if code not in medians:
                medians[code] = {}
            medians[code][key] = val

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_voa_rents_lad CASCADE")

    rows = []
    for lad_code, vals in medians.items():
        rows.append((
            lad_code, "2022-23",
            vals.get("all"),
            vals.get("1bed"),
            vals.get("2bed"),
            vals.get("3bed"),
            vals.get("4bed"),
        ))

    print(f"  Total: {len(rows):,} LADs")
    if rows:
        execute_values(cur, """INSERT INTO core_voa_rents_lad
            (lad_code, period, median_rent_all, median_rent_1bed, median_rent_2bed,
             median_rent_3bed, median_rent_4bed) VALUES %s ON CONFLICT DO NOTHING""", rows)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_voa_rents_lad")
    print(f"core_voa_rents_lad: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
