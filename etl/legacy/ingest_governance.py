"""ETL: Tab 5 governance datasets → council control, S114, water companies.
Sources:
  - Open Council Data UK source CSV → core_council_control_lad
  - Provenance-backed Section 114 registry CSV → core_s114_notices
"""
import os, csv, psycopg2
from collections import defaultdict
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
DATA_DIR = os.path.expanduser("~/Desktop/Manus Take 2/etl/data")
SECTION_114_PATH = os.environ.get("SECTION_114_PATH", os.path.join(DATA_DIR, "section_114_notices.csv"))

def ingest_council_control():
    """Derive controlling party from councillor-level data."""
    print("Ingesting council control...")
    path = os.path.join(DATA_DIR, "council_control_2025.csv")

    # Count seats by council × party
    council_parties = defaultdict(lambda: defaultdict(int))
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            council = r.get("Council", "").strip()
            party = r.get("Party Name", "").strip()
            if council and party:
                council_parties[council][party] += 1

    # Determine control: majority party or NOC
    controls = {}
    for council, parties in council_parties.items():
        total_seats = sum(parties.values())
        majority_needed = total_seats / 2
        sorted_parties = sorted(parties.items(), key=lambda x: -x[1])
        top_party, top_seats = sorted_parties[0]
        if top_seats > majority_needed:
            controls[council] = (top_party, top_seats, total_seats)
        else:
            controls[council] = ("No Overall Control", top_seats, total_seats)

    print(f"  Councils parsed: {len(controls)}")

    # Now map council names to LAD codes via core_lad_boundaries
    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT lad_code, lad_name FROM core_lad_boundaries")
    lad_map = {}
    for row in cur.fetchall():
        lad_map[row[1].lower()] = row[0]
        # Also try without "City of", "Borough of" etc.
        clean = row[1].lower().replace("city of ", "").replace("borough of ", "").replace("royal borough of ", "")
        lad_map[clean] = row[0]

    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_council_control_lad (
            lad_code TEXT PRIMARY KEY,
            council_name TEXT,
            controlling_party TEXT,
            majority_seats INTEGER,
            total_seats INTEGER
        )
    """)
    cur.execute("TRUNCATE TABLE core_council_control_lad")

    seen_lads = {}
    matched = 0
    for council, (party, seats, total) in controls.items():
        lad_code = lad_map.get(council.lower())
        if not lad_code:
            for lad_name, code in lad_map.items():
                if council.lower() in lad_name or lad_name in council.lower():
                    lad_code = code
                    break
        if lad_code and lad_code not in seen_lads:
            seen_lads[lad_code] = (lad_code, council, party, seats, total)
            matched += 1

    rows = list(seen_lads.values())
    execute_values(cur, """
        INSERT INTO core_council_control_lad (lad_code, council_name, controlling_party, majority_seats, total_seats)
        VALUES %s ON CONFLICT DO NOTHING
    """, rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_council_control_lad")
    print(f"  core_council_control_lad: {cur.fetchone()[0]:,} rows (matched {matched} of {len(controls)} councils)")

    cur.execute("SELECT controlling_party, COUNT(*) FROM core_council_control_lad GROUP BY controlling_party ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]}")

    cur.close(); conn.close()


def ingest_s114():
    """Load Section 114 notices from a provenance-backed registry CSV."""
    print("Ingesting S114 notices...")

    s114_data = []
    if os.path.exists(SECTION_114_PATH):
        with open(SECTION_114_PATH, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            required = {"lad_code", "council_name", "notice_date"}
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise ValueError("Section 114 registry missing required columns: " + ", ".join(sorted(missing)))
            for row in reader:
                lad_code = (row.get("lad_code") or "").strip()
                council_name = (row.get("council_name") or "").strip()
                notice_date = (row.get("notice_date") or "").strip()
                if lad_code and council_name and notice_date:
                    s114_data.append((lad_code, council_name, notice_date))
    else:
        print(f"  Section 114 registry not found at {SECTION_114_PATH}; loading 0 rows.")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_s114_notices (
            lad_code TEXT PRIMARY KEY,
            council_name TEXT,
            notice_date DATE
        )
    """)
    cur.execute("TRUNCATE TABLE core_s114_notices")
    if s114_data:
        execute_values(cur, "INSERT INTO core_s114_notices (lad_code, council_name, notice_date) VALUES %s", s114_data)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_s114_notices")
    print(f"  core_s114_notices: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()


if __name__ == "__main__":
    ingest_council_control()
    ingest_s114()
