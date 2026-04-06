"""ETL: OpenStreetMap POIs → core_osm_amenities. Bible: Section 3.1 OSM tags.
Fetches fresh data from Overpass API with Bible-exact tags:
  supermarket: shop=supermarket, cafe: amenity=cafe, restaurant: amenity=restaurant,
  pub: amenity=pub, gym: leisure=fitness_centre, park: leisure=park,
  pharmacy: amenity=pharmacy, dentist: amenity=dentist, hospital: amenity=hospital,
  GP: amenity=doctors
"""
import os, json, requests, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
CACHE_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/osm_bible_pois.json")

# Bible Section 3.1: exact tag mapping
BIBLE_TAGS = [
    ("supermarket", "shop", "supermarket"),
    ("cafe", "amenity", "cafe"),
    ("restaurant", "amenity", "restaurant"),
    ("pub", "amenity", "pub"),
    ("gym", "leisure", "fitness_centre"),
    ("park", "leisure", "park"),
    ("pharmacy", "amenity", "pharmacy"),
    ("dentist", "amenity", "dentist"),
    ("hospital", "amenity", "hospital"),
    ("doctors", "amenity", "doctors"),
]

# England bounding box
BBOX = "49.9,-6.5,55.9,2.0"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def fetch_osm_pois():
    """Fetch all Bible-defined POI types from Overpass API."""
    if os.path.exists(CACHE_PATH):
        print("  Loading cached OSM data...")
        with open(CACHE_PATH) as f:
            return json.load(f)

    import time
    print("  Fetching from Overpass API (this may take a few minutes)...")
    all_elements = []

    for i, (amenity_type, key, value) in enumerate(BIBLE_TAGS):
        query = f"""
        [out:json][timeout:300];
        (
          node["{key}"="{value}"]({BBOX});
          way["{key}"="{value}"]({BBOX});
        );
        out center;
        """
        print(f"  Fetching {amenity_type}...")
        for attempt in range(3):
            try:
                resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=360)
                resp.raise_for_status()
                data = resp.json()
                elements = data.get("elements", [])
                for el in elements:
                    el["_amenity_type"] = amenity_type
                all_elements.extend(elements)
                print(f"    {len(elements):,} elements")
                break
            except Exception as e:
                print(f"    Attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep(15)
        # Rate limit: wait between requests
        if i < len(BIBLE_TAGS) - 1:
            time.sleep(5)

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(all_elements, f)

    return all_elements

def ingest():
    print("Ingesting OSM amenities (Bible-exact tags)...")
    elements = fetch_osm_pois()

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_osm_amenities CASCADE")

    rows = []
    for el in elements:
        amenity_type = el.get("_amenity_type")
        if not amenity_type:
            continue

        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None and "center" in el:
            lat = el["center"].get("lat")
            lon = el["center"].get("lon")
        if lat is None or lon is None:
            continue

        osm_id = el.get("id")
        name = el.get("tags", {}).get("name", "")
        rows.append((osm_id, name, amenity_type, float(lat), float(lon)))

    print(f"  Collected {len(rows):,} amenities")
    if rows:
        execute_values(cur, """INSERT INTO core_osm_amenities
            (osm_id, name, amenity_type, latitude, longitude)
            VALUES %s""", rows, page_size=10000)
        conn.commit()

    cur.execute("""UPDATE core_osm_amenities
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL""")
    conn.commit()

    cur.execute("SELECT amenity_type, COUNT(*) FROM core_osm_amenities GROUP BY amenity_type ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,}")
    cur.execute("SELECT COUNT(*) FROM core_osm_amenities")
    print(f"core_osm_amenities total: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
