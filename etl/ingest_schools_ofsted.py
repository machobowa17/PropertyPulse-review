"""ETL: Refresh core_schools from GIAS JSON + Ofsted latest CSV.

Changes vs original ingest_schools.py:
  1. Includes 'Not applicable' phase schools (nurseries, special schools)
  2. Loads Ofsted ratings from ofsted_latest.csv (numeric → text)
  3. Uses ON CONFLICT DO UPDATE to upsert without truncating
"""
import os, csv, json, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
GIAS_JSON_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/gias_schools.json")
OFSTED_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/ofsted_latest.csv")

PHASE_MAP = {
    "Primary": "Primary",
    "Secondary": "Secondary",
    "All-through": "All-through",
    "Middle deemed primary": "Middle deemed primary",
    "Middle deemed secondary": "Middle deemed secondary",
    "16 plus": "16 plus",
    "Not applicable": "Not applicable",  # nurseries, special schools, AP
    "Nursery": "Nursery",
}

OFSTED_NUM_TO_TEXT = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}


def load_ofsted():
    """Read Ofsted latest CSV → {urn: (rating_text, inspection_date)}."""
    ratings = {}
    with open(OFSTED_PATH, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for r in reader:
            urn_str = r.get("URN", "").strip()
            if not urn_str or not urn_str.isdigit():
                continue
            num = r.get("Overall effectiveness", "").strip()
            text_rating = OFSTED_NUM_TO_TEXT.get(num)
            if not text_rating:
                continue
            date_str = r.get("Inspection start date", "").strip()
            if date_str and date_str != "NULL":
                # Convert DD/MM/YYYY → YYYY-MM-DD
                parts = date_str.split("/")
                inspection_date = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else None
            else:
                inspection_date = None
            ratings[int(urn_str)] = (text_rating, inspection_date)
    print(f"  Ofsted ratings loaded: {len(ratings):,}")
    return ratings


def ingest():
    print("Ingesting schools (GIAS + Ofsted)...")
    ofsted = load_ofsted()

    with open(GIAS_JSON_PATH, "r") as f:
        schools = json.load(f)
    print(f"  GIAS schools: {len(schools):,}")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    rows = []
    for s in schools:
        status = s.get("status", "")
        if status not in ("Open", "Open, but proposed to close"):
            continue

        urn_raw = s.get("urn")
        if not urn_raw:
            continue
        try:
            urn = int(urn_raw)
        except (ValueError, TypeError):
            continue

        phase = s.get("phase_of_education", "")
        if phase not in PHASE_MAP:
            continue

        # Only include English schools
        lad_code = s.get("administritive_district_code", "")
        if not lad_code.startswith("E"):
            continue

        lat = s.get("latitude")
        lon = s.get("longitude")
        try:
            lat_f = float(lat) if lat else None
            lon_f = float(lon) if lon else None
        except (ValueError, TypeError):
            lat_f = lon_f = None

        # Skip schools without coordinates
        if lat_f is None or lon_f is None:
            continue

        ofsted_rating, ofsted_date = ofsted.get(urn, (None, None))

        rows.append((
            urn,
            s.get("name", ""),
            s.get("type", ""),
            PHASE_MAP[phase],
            s.get("postcode", ""),
            lat_f, lon_f,
            lad_code,
            ofsted_rating,
            ofsted_date,
            None,  # ks2_reading_pct — preserved from existing data
            None,  # ks2_maths_pct
            None,  # gcse_progress_8
            None,  # gcse_attainment_8
            True,
        ))

    print(f"  Prepared {len(rows):,} rows for upsert")

    # Upsert: update name/type/phase/geo/lad/ofsted but preserve KS2/KS4 scores
    execute_values(cur, """
        INSERT INTO core_schools
          (urn, school_name, school_type, phase, postcode, latitude, longitude,
           lad_code, ofsted_rating, ofsted_date,
           ks2_reading_pct, ks2_maths_pct, gcse_progress_8, gcse_attainment_8, is_open)
        VALUES %s
        ON CONFLICT (urn) DO UPDATE SET
          school_name    = EXCLUDED.school_name,
          school_type    = EXCLUDED.school_type,
          phase          = EXCLUDED.phase,
          postcode       = EXCLUDED.postcode,
          latitude       = EXCLUDED.latitude,
          longitude      = EXCLUDED.longitude,
          lad_code       = EXCLUDED.lad_code,
          ofsted_rating  = COALESCE(EXCLUDED.ofsted_rating, core_schools.ofsted_rating),
          ofsted_date    = COALESCE(EXCLUDED.ofsted_date, core_schools.ofsted_date),
          is_open        = EXCLUDED.is_open
    """, rows, page_size=5000)
    conn.commit()
    print("  Upsert complete")

    # Mark closed schools (not in open GIAS set)
    open_urns = [r[0] for r in rows]
    cur.execute("UPDATE core_schools SET is_open = false WHERE urn != ALL(%s)", (open_urns,))
    closed_count = cur.rowcount
    conn.commit()
    print(f"  Marked {closed_count:,} schools as closed")

    # Rebuild geometry
    cur.execute("""
        UPDATE core_schools
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND (geom IS NULL OR
              ST_X(geom) != longitude OR ST_Y(geom) != latitude)
    """)
    conn.commit()

    # Final stats
    cur.execute("SELECT COUNT(*) FROM core_schools WHERE is_open=true")
    open_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM core_schools WHERE is_open=true AND ofsted_rating IS NOT NULL")
    with_ofsted = cur.fetchone()[0]
    cur.execute("SELECT phase, COUNT(*) FROM core_schools WHERE is_open=true GROUP BY phase ORDER BY COUNT(*) DESC")
    by_phase = cur.fetchall()

    print(f"\ncore_schools: {open_count:,} open schools ({with_ofsted:,} with Ofsted rating)")
    for phase, cnt in by_phase:
        print(f"  {phase}: {cnt:,}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
