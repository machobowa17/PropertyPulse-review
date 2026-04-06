"""ETL: DfE GIAS + KS2/KS4 → core_schools. Bible: Tab 4 Schools.
Uses GitHub JSON endpoint as primary source (CSV endpoint often down)."""
import os, csv, json, psycopg2, requests
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
KS2_PATH = os.path.expanduser("~/Desktop/geodepth/etl/data/ks2_school_2024.csv")
KS4_PATH = os.path.expanduser("~/Desktop/geodepth/etl/data/ks4_school_2024.csv")

GIAS_JSON_URL = "https://dfe-digital.github.io/gias-data/schools.json"
GIAS_JSON_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/gias_schools.json")

PHASE_MAP = {
    "Primary": "Primary",
    "Secondary": "Secondary",
    "All-through": "All-through",
    "Middle deemed primary": "Middle deemed primary",
    "Middle deemed secondary": "Middle deemed secondary",
    "16 plus": "16 plus",
}

def download_gias():
    if os.path.exists(GIAS_JSON_PATH):
        print("  GIAS JSON exists, skipping download")
        return
    print("  Downloading GIAS JSON from GitHub...")
    resp = requests.get(GIAS_JSON_URL, timeout=120)
    resp.raise_for_status()
    os.makedirs(os.path.dirname(GIAS_JSON_PATH), exist_ok=True)
    with open(GIAS_JSON_PATH, "wb") as f:
        f.write(resp.content)
    print(f"  Downloaded {len(resp.content)/1024/1024:.1f} MB")

def ingest():
    print("Ingesting schools...")
    download_gias()

    # Read KS2 performance (primary)
    # Columns: school_urn, subject, progress_measure_score
    ks2 = {}
    if os.path.exists(KS2_PATH):
        with open(KS2_PATH, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                urn = r.get("school_urn", "").strip()
                if not urn:
                    continue
                subject = r.get("subject", "").lower()
                score = r.get("progress_measure_score", "")
                try:
                    urn_int = int(urn)
                    score_f = float(score) if score and score != "x" else None
                except (ValueError, TypeError):
                    continue
                if urn_int not in ks2:
                    ks2[urn_int] = {}
                if "reading" in subject and score_f is not None:
                    ks2[urn_int]["reading"] = score_f
                elif "math" in subject and score_f is not None:
                    ks2[urn_int]["maths"] = score_f
        print(f"  KS2 scores: {len(ks2):,}")

    # Read KS4 performance (secondary)
    # Columns: school_urn, avg_p8score, avg_att8
    ks4 = {}
    if os.path.exists(KS4_PATH):
        with open(KS4_PATH, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                urn = r.get("school_urn", "").strip()
                if not urn:
                    continue
                # Only use "Total" breakdown (aggregate row)
                breakdown = r.get("breakdown", "")
                if breakdown != "Total":
                    continue
                try:
                    urn_int = int(urn)
                    p8 = r.get("avg_p8score", "")
                    a8 = r.get("avg_att8", "")
                    p8_f = float(p8) if p8 and p8 not in ("x", "SUPP", "NE", "z", "c") else None
                    a8_f = float(a8) if a8 and a8 not in ("x", "SUPP", "NE", "z", "c") else None
                except (ValueError, TypeError):
                    continue
                if p8_f is not None or a8_f is not None:
                    ks4[urn_int] = {"p8": p8_f, "a8": a8_f}
        print(f"  KS4 scores: {len(ks4):,}")

    # Parse GIAS JSON
    with open(GIAS_JSON_PATH, "r") as f:
        schools = json.load(f)
    print(f"  GIAS schools: {len(schools):,}")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_schools CASCADE")

    rows = []
    for s in schools:
        status = s.get("status", "")
        if status != "Open":
            continue

        urn = s.get("urn")
        if not urn:
            continue

        phase = s.get("phase_of_education", "")
        if phase not in PHASE_MAP:
            continue

        lat = s.get("latitude")
        lon = s.get("longitude")
        try:
            lat_f = float(lat) if lat else None
            lon_f = float(lon) if lon else None
        except (ValueError, TypeError):
            lat_f = lon_f = None

        # LAD code from administritive_district_code
        lad_code = s.get("administritive_district_code", "")

        k2 = ks2.get(int(urn), {})
        k4 = ks4.get(int(urn), {})

        rows.append((
            int(urn),
            s.get("name", ""),
            s.get("type", ""),
            phase,
            s.get("postcode", ""),
            lat_f, lon_f,
            lad_code,
            None,  # ofsted_rating — not in JSON
            None,  # ofsted_date
            k2.get("reading"),
            k2.get("maths"),
            k4.get("p8"),
            k4.get("a8"),
            True,
        ))

    print(f"  Collected {len(rows):,} schools")
    if rows:
        execute_values(cur, """INSERT INTO core_schools
            (urn, school_name, school_type, phase, postcode, latitude, longitude,
             lad_code, ofsted_rating, ofsted_date,
             ks2_reading_pct, ks2_maths_pct, gcse_progress_8, gcse_attainment_8, is_open)
            VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=5000)
        conn.commit()

    cur.execute("""UPDATE core_schools
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL""")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_schools")
    print(f"core_schools: {cur.fetchone()[0]:,} rows")
    cur.execute("SELECT phase, COUNT(*) FROM core_schools GROUP BY phase ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,}")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
