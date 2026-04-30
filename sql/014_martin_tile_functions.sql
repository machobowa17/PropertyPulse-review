-- 014_martin_tile_functions.sql
-- Vector tile functions for Martin tile server (P53 — Property Search)
-- Martin auto-serves PostGIS tables as MVT tiles, but we need a custom
-- function for address points to control zoom-level filtering and field selection.

-- Address points: returns PAON/SAON/street/postcode as labelled points
-- Only serves tiles at zoom >= 16 to avoid overwhelming tile sizes.
-- Martin calls this as: SELECT address_points(z, x, y, '{}')
CREATE OR REPLACE FUNCTION address_points(
    z integer,
    x integer,
    y integer,
    query_params json DEFAULT '{}'::json
)
RETURNS bytea AS $$
DECLARE
    bounds geometry;
    mvt bytea;
BEGIN
    -- No data at low zoom levels
    IF z < 16 THEN
        RETURN NULL;
    END IF;

    bounds := ST_TileEnvelope(z, x, y);

    SELECT ST_AsMVT(q, 'address_points', 4096, 'geom') INTO mvt
    FROM (
        SELECT
            ST_AsMVTGeom(t.geom, bounds, 4096, 64, true) AS geom,
            t.paon,
            t.saon,
            t.street,
            t.postcode
        FROM core_property_transactions t
        WHERE t.geom && bounds
          AND ST_Intersects(t.geom, bounds)
        LIMIT 2000
    ) q;

    RETURN mvt;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE;
