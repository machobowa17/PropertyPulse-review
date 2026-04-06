"""
Derive core_county_boundaries by ST_Union of LAD boundaries
grouped by parent_comparison from core_lad_county_lookup.
No external download needed — uses existing tables.
"""
import asyncio
import asyncpg

DB = "postgresql://postgres@localhost:5432/ukproperty"


async def main():
    conn = await asyncpg.connect(DB)

    await conn.execute("DROP TABLE IF EXISTS core_county_boundaries CASCADE;")
    await conn.execute("""
        CREATE TABLE core_county_boundaries (
            county_name TEXT PRIMARY KEY,
            lad_count   INTEGER NOT NULL,
            geom        GEOMETRY(MultiPolygon, 4326) NOT NULL
        );
    """)

    await conn.execute("""
        INSERT INTO core_county_boundaries (county_name, lad_count, geom)
        SELECT cl.parent_comparison,
               COUNT(lb.lad_code)::int,
               ST_Multi(ST_Union(lb.geom))
        FROM core_lad_county_lookup cl
        JOIN core_lad_boundaries lb ON cl.lad_code = lb.lad_code
        WHERE cl.parent_comparison IS NOT NULL
          AND lb.geom IS NOT NULL
        GROUP BY cl.parent_comparison
    """)

    count = await conn.fetchval("SELECT COUNT(*) FROM core_county_boundaries")
    print(f"Inserted {count} county boundaries")

    await conn.execute("""
        CREATE INDEX idx_county_boundaries_geom
        ON core_county_boundaries USING GIST(geom);
    """)
    await conn.execute("""
        CREATE INDEX idx_county_boundaries_name
        ON core_county_boundaries(county_name);
    """)

    # Verify
    rows = await conn.fetch("""
        SELECT county_name, lad_count,
               ROUND(ST_Area(geom::geography) / 1e6) AS area_km2
        FROM core_county_boundaries
        ORDER BY lad_count DESC
        LIMIT 10
    """)
    print("\nTop 10 counties by LAD count:")
    for r in rows:
        print(f"  {r['county_name']:25s}  {r['lad_count']:3d} LADs  {r['area_km2']:>8.0f} km²")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
