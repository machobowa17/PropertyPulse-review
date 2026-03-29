"""ETL: Greater Manchester Police crimes via police.uk API → core_crime_lsoa.
GMP is excluded from the national bulk ZIP, so we use the street crimes API.
Queries each GMP LSOA boundary polygon to get crimes, then attributes them
to the LSOA by reverse-geocoding the crime lat/lng via PostGIS."""
import time, requests, psycopg2, json
from collections import defaultdict
from psycopg2.extras import execute_values

DB = "postgresql://postgres@localhost:5432/ukproperty"
API_BASE = "https://data.police.uk/api"
FORCE = "greater-manchester"
# GMP bounding box (roughly)
GMP_LAD_CODES = ('E08000001','E08000002','E08000003','E08000004','E08000005',
                 'E08000006','E08000007','E08000008','E08000009','E08000010')

def get_available_months():
    r = requests.get(f"{API_BASE}/crimes-street-dates", timeout=10)
    return [d["date"] for d in r.json()]

def get_gmp_lsoa_centroids(conn):
    """Get all GMP LSOAs with their centroid and simplified polygon."""
    cur = conn.cursor()
    cur.execute("""
        SELECT b.lsoa_code,
               ST_Y(ST_Centroid(b.geom)) AS lat,
               ST_X(ST_Centroid(b.geom)) AS lon,
               ST_AsGeoJSON(ST_Simplify(b.geom, 0.001)) AS poly_json
        FROM core_lsoa_boundaries b
        JOIN core_postcodes p ON p.lsoa_code = b.lsoa_code
        WHERE p.lad_code = ANY(%s)
        GROUP BY b.lsoa_code, b.geom
        ORDER BY b.lsoa_code
    """, (list(GMP_LAD_CODES),))
    rows = cur.fetchall()
    cur.close()
    return rows

def polygon_to_api_param(poly_json):
    """Convert GeoJSON polygon to police.uk poly= parameter (lat,lng:lat,lng:...)"""
    geom = json.loads(poly_json)
    if geom["type"] == "Polygon":
        coords = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        # Use the largest ring
        coords = max(geom["coordinates"], key=lambda r: len(r[0]))[0]
    else:
        return None
    # API limit: 100 vertices, sample if needed
    if len(coords) > 99:
        step = len(coords) / 99
        coords = [coords[int(i * step)] for i in range(99)] + [coords[0]]
    # Format: lat,lng pairs
    return ":".join(f"{c[1]:.5f},{c[0]:.5f}" for c in coords[:-1])  # exclude closing coord

def fetch_crimes_for_lsoa(poly_param, month, retries=5):
    """Fetch crimes within LSOA polygon for a given month."""
    url = f"{API_BASE}/crimes-street/all-crime"
    for attempt in range(retries):
        try:
            r = requests.get(url, params={"poly": poly_param, "date": month}, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                # Rate limited — honour retry_after header or back off exponentially
                retry_after = int(r.headers.get("Retry-After", 30))
                wait = max(retry_after, 2 ** (attempt + 2))
                print(f"    429 rate limit — waiting {wait}s", flush=True)
                time.sleep(wait)
            elif r.status_code == 503:
                time.sleep(2 ** attempt)
            else:
                return []
        except Exception:
            time.sleep(2 ** attempt)
    return []

def ingest():
    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    # Get all available months
    months = get_available_months()
    print(f"Available months: {months[0]} → {months[-1]} ({len(months)} total)")

    # Get GMP LSOAs
    lsoas = get_gmp_lsoa_centroids(conn)
    print(f"GMP LSOAs to process: {len(lsoas)}")

    # Check which GMP LSOAs already have data in DB
    cur.execute("""
        SELECT DISTINCT c.lsoa_code FROM core_crime_lsoa c
        WHERE c.lsoa_code IN (
            SELECT b.lsoa_code FROM core_lsoa_boundaries b
            JOIN core_postcodes p ON p.lsoa_code = b.lsoa_code
            WHERE p.lad_code = ANY(%s)
        )
    """, (list(GMP_LAD_CODES),))
    already_loaded = set(r[0] for r in cur.fetchall())
    print(f"Already have data for {len(already_loaded)} GMP LSOAs")

    missing_lsoas = [(code, lat, lon, poly) for code, lat, lon, poly in lsoas if code not in already_loaded]
    print(f"Need to fetch {len(missing_lsoas)} GMP LSOAs × {len(months)} months")

    total_inserted = 0
    for i, (lsoa_code, lat, lon, poly_json) in enumerate(missing_lsoas):
        poly_param = polygon_to_api_param(poly_json)
        if not poly_param:
            continue

        month_rows = []
        for month in months:
            crimes = fetch_crimes_for_lsoa(poly_param, month)
            counts = defaultdict(int)
            for crime in crimes:
                crime_type = crime.get("category", "").replace("-", " ").title()
                if crime_type:
                    counts[crime_type] += 1
            for crime_type, cnt in counts.items():
                month_rows.append((lsoa_code, month + "-01", crime_type, cnt))
            time.sleep(0.5)  # Rate limit: 2 req/sec (polygon endpoint is stricter)

        if month_rows:
            execute_values(cur, """INSERT INTO core_crime_lsoa
                (lsoa_code, month, crime_type, crime_count)
                VALUES %s ON CONFLICT DO NOTHING""", month_rows, page_size=1000)
            conn.commit()
            total_inserted += len(month_rows)

        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{len(missing_lsoas)} LSOAs, inserted {total_inserted:,} rows")

    print(f"\nDone. Total rows inserted: {total_inserted:,}")
    cur.execute("SELECT COUNT(DISTINCT lsoa_code) FROM core_crime_lsoa WHERE lsoa_code IN (SELECT b.lsoa_code FROM core_lsoa_boundaries b JOIN core_postcodes p ON p.lsoa_code = b.lsoa_code WHERE p.lad_code = ANY(%s))", (list(GMP_LAD_CODES),))
    print(f"GMP LSOAs with crime data: {cur.fetchone()[0]:,}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    ingest()
