"""ETL: Ofsted Management Information → UPDATE core_schools. Bible: Tab 4 Schools.
Reads Ofsted latest inspections CSV, updates ofsted_rating and ofsted_date in core_schools by URN."""
import os, csv, psycopg2

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
OFSTED_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/ofsted_latest.csv")

def ingest():
    print("Ingesting Ofsted ratings...")

    ratings = {}
    with open(OFSTED_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            urn = r.get("URN", "").strip()
            if not urn:
                continue
            try:
                urn_int = int(urn)
            except ValueError:
                continue

            rating_raw = r.get("Overall effectiveness", "").strip()
            # Ratings are numeric: 1=Outstanding, 2=Good, 3=Requires improvement, 4=Inadequate
            RATING_MAP = {"1": "Outstanding", "2": "Good", "3": "Requires improvement", "4": "Inadequate"}
            rating = RATING_MAP.get(rating_raw)
            if not rating:
                continue

            # Parse date DD/MM/YYYY → YYYY-MM-DD
            date_str = r.get("Inspection start date", "").strip()
            date_iso = None
            if date_str and date_str != "NULL":
                parts = date_str.split("/")
                if len(parts) == 3:
                    date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"

            ratings[urn_int] = (rating, date_iso)

    print(f"  Ofsted ratings loaded: {len(ratings):,} schools")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    updated = 0
    for urn, (rating, date_iso) in ratings.items():
        cur.execute("""
            UPDATE core_schools SET ofsted_rating = %s, ofsted_date = %s
            WHERE urn = %s
        """, (rating, date_iso, urn))
        if cur.rowcount > 0:
            updated += 1

    conn.commit()
    print(f"  Updated {updated:,} schools with Ofsted ratings")

    cur.execute("SELECT ofsted_rating, COUNT(*) FROM core_schools WHERE ofsted_rating IS NOT NULL GROUP BY ofsted_rating ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,}")

    cur.close(); conn.close()

if __name__ == "__main__": ingest()
