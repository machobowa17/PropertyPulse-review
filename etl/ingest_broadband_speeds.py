"""ETL: Ofcom Connected Nations LAD-level broadband speeds → core_broadband_lad.
Computes weighted average download/upload speeds from:
  - Fixed performance by LAUA (avg speed within each speed band)
  - Fixed coverage by LAUA (number of premises in each speed band)
Also captures Full Fibre availability % (real FTTP data, not a proxy).
"""
import csv, psycopg2
from psycopg2.extras import execute_values

DB = "postgresql://postgres@localhost:5432/ukproperty"
COVERAGE_CSV = "/Users/batty/Desktop/Manus Take 2/etl/data/broadband/fixed_coverage_laua/202407_fixed_laua_coverage_r01.csv"
PERFORMANCE_CSV = "/Users/batty/Desktop/Manus Take 2/etl/data/broadband/fixed_performance_laua/202407_fixed_performance_laua_r01.csv"

def load_performance():
    """Return dict: lad_code → (avg_dl per band, avg_ul per band)"""
    perf = {}
    with open(PERFORMANCE_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad = r["laua"].strip()
            def flt(v):
                try: return float(v) if v.strip() else None
                except: return None
            # Download: <10, 10-30, 30-100, 100-300, 300-900, >=900
            dl = [
                flt(r.get("Average max download speed (Mbit/s) for lines <10Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 10<30Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 30<100Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 100<300Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 300<900Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines >=900Mbit/s")),
            ]
            # Upload: <10, 10-30, 30-100, 100-300, 300-900, >=900
            ul = [
                flt(r.get("Average max upload speed (Mbit/s) for lines <10Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 10<30Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 30<100Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 100<300Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 300<900Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines >=900Mbit/s")),
            ]
            perf[lad] = (dl, ul)
    return perf

def weighted_avg(counts, speeds):
    """Compute weighted average speed given counts per band and avg speed per band."""
    total_w = 0.0
    total_ws = 0.0
    for cnt, spd in zip(counts, speeds):
        if cnt and spd and cnt > 0:
            total_w += cnt
            total_ws += cnt * spd
    return round(total_ws / total_w, 1) if total_w > 0 else None

def ingest():
    perf = load_performance()
    print(f"Loaded performance data for {len(perf):,} LADs")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    # Create table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_broadband_lad (
            lad_code VARCHAR(10) PRIMARY KEY,
            lad_name TEXT,
            avg_download_mbps NUMERIC(8,1),
            avg_upload_mbps NUMERIC(8,1),
            full_fibre_pct NUMERIC(5,1),
            superfast_pct NUMERIC(5,1),
            gigabit_pct NUMERIC(5,1),
            ultrafast_pct NUMERIC(5,1)
        )
    """)
    cur.execute("TRUNCATE TABLE core_broadband_lad")

    rows = []
    with open(COVERAGE_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad = r["laua"].strip()
            if not lad.startswith("E") and not lad.startswith("W"):
                continue  # Skip Scotland/Northern Ireland

            def flt(v):
                try: return float(v.strip()) if v.strip() else None
                except: return None
            def nt(v):
                try: return int(float(v.strip())) if v.strip() else 0
                except: return 0

            # Coverage band counts (approximate band mapping to performance tiers)
            # Coverage bands: 0-2, 2-5, 5-10 → performance band <10
            # 10-30 → performance band 10-30
            # 30-300 → split across performance bands 30-100, 100-300, 300-900
            # >=300 → performance band >=900
            n_lt10 = nt(r.get("Number of premises with 0<2Mbit/s download speed","")) + \
                     nt(r.get("Number of premises with 2<5Mbit/s download speed","")) + \
                     nt(r.get("Number of premises with 5<10Mbit/s download speed",""))
            n_10_30 = nt(r.get("Number of premises with 10<30Mbit/s download speed",""))
            n_30_300 = nt(r.get("Number of premises with 30<300Mbit/s download speed",""))
            n_gte300 = nt(r.get("Number of premises with >=300Mbit/s download speed",""))
            # Split 30-300 evenly across 30-100, 100-300, 300-900 performance bands (approximation)
            n_30_100 = n_30_300 // 3
            n_100_300 = n_30_300 // 3
            n_300_900 = n_30_300 - n_30_100 - n_100_300
            n_gte900 = n_gte300

            counts = [n_lt10, n_10_30, n_30_100, n_100_300, n_300_900, n_gte900]

            dl_avg = None
            ul_avg = None
            if lad in perf:
                dl_bands, ul_bands = perf[lad]
                dl_avg = weighted_avg(counts, dl_bands)
                ul_avg = weighted_avg(counts, ul_bands)

            rows.append((
                lad,
                r.get("laua_name","").strip(),
                dl_avg,
                ul_avg,
                flt(r.get("Full Fibre availability (% premises)", "")),
                flt(r.get("SFBB availability (% premises)", "")),
                flt(r.get("Gigabit availability (% premises)", "")),
                flt(r.get("UFBB availability (% premises)", "")),
            ))

    execute_values(cur, """
        INSERT INTO core_broadband_lad
        (lad_code, lad_name, avg_download_mbps, avg_upload_mbps, full_fibre_pct, superfast_pct, gigabit_pct, ultrafast_pct)
        VALUES %s ON CONFLICT DO NOTHING
    """, rows, page_size=500)
    conn.commit()

    cur.execute("SELECT COUNT(*), COUNT(avg_download_mbps), COUNT(full_fibre_pct) FROM core_broadband_lad")
    cnt, dl_cnt, ff_cnt = cur.fetchone()
    print(f"core_broadband_lad: {cnt:,} rows, {dl_cnt:,} with avg_dl, {ff_cnt:,} with full_fibre_pct")

    # Sample check
    cur.execute("""SELECT lad_name, avg_download_mbps, avg_upload_mbps, full_fibre_pct
                   FROM core_broadband_lad WHERE lad_code IN ('E08000003','E09000019','E06000023')""")
    for row in cur.fetchall():
        print(f"  {row}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    ingest()
