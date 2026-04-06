"""Comparable Areas — find LADs most similar to a given LAD.
Uses normalised feature vectors: avg_price, median_rent, earnings, pm25, hpi_yoy."""
from sqlalchemy import text
from app.constants import PRICE_TYPES


async def find_comparable_lads(db, *, lad_code: str, limit: int = 5):
    """Return up to `limit` LADs most similar to the given LAD."""
    # Build feature vectors for all LADs in a single query
    result = await db.execute(
        text("""
            WITH features AS (
                SELECT
                    lb.lad_code,
                    lb.lad_name,
                    -- Latest avg price from raw transactions
                    (SELECT AVG(price)
                     FROM core_property_transactions
                     WHERE lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = lb.lad_code)
                       AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                       AND property_type = ANY(:price_types)
                    ) AS avg_price,
                    -- Median rent
                    (SELECT r.median_rent_all
                     FROM core_voa_rents_lad r
                     WHERE r.lad_code = lb.lad_code
                     ORDER BY r.period DESC LIMIT 1
                    ) AS median_rent,
                    -- Earnings
                    (SELECT e.median_annual_earnings
                     FROM core_earnings_lad e
                     WHERE e.lad_code = lb.lad_code
                    ) AS earnings,
                    -- PM2.5 (latest year)
                    (SELECT aq.pm25_ugm3
                     FROM core_air_quality_lad aq
                     WHERE aq.lad_code = lb.lad_code
                     ORDER BY aq.year DESC LIMIT 1
                    ) AS pm25,
                    -- HPI yearly change
                    (SELECT h.yearly_change_pct
                     FROM core_hpi_lad h
                     WHERE h.lad_code = lb.lad_code
                     ORDER BY h.date DESC LIMIT 1
                    ) AS hpi_yoy
                FROM core_lad_boundaries lb
            ),
            stats AS (
                SELECT
                    AVG(avg_price) AS mean_price, STDDEV(avg_price) AS std_price,
                    AVG(median_rent) AS mean_rent, STDDEV(median_rent) AS std_rent,
                    AVG(earnings) AS mean_earn, STDDEV(earnings) AS std_earn,
                    AVG(pm25) AS mean_pm25, STDDEV(pm25) AS std_pm25,
                    AVG(hpi_yoy) AS mean_hpi, STDDEV(hpi_yoy) AS std_hpi
                FROM features
                WHERE avg_price IS NOT NULL
            ),
            normalised AS (
                SELECT
                    f.lad_code, f.lad_name,
                    f.avg_price, f.median_rent, f.earnings, f.pm25, f.hpi_yoy,
                    COALESCE((f.avg_price - s.mean_price) / NULLIF(s.std_price, 0), 0) AS n_price,
                    COALESCE((f.median_rent - s.mean_rent) / NULLIF(s.std_rent, 0), 0) AS n_rent,
                    COALESCE((f.earnings - s.mean_earn) / NULLIF(s.std_earn, 0), 0) AS n_earn,
                    COALESCE((f.pm25 - s.mean_pm25) / NULLIF(s.std_pm25, 0), 0) AS n_pm25,
                    COALESCE((f.hpi_yoy - s.mean_hpi) / NULLIF(s.std_hpi, 0), 0) AS n_hpi
                FROM features f, stats s
                WHERE f.avg_price IS NOT NULL
            ),
            target AS (
                SELECT * FROM normalised WHERE lad_code = :lad
            )
            SELECT
                n.lad_code, n.lad_name,
                ROUND(n.avg_price::numeric, 0) AS avg_price,
                ROUND(n.median_rent::numeric, 0) AS median_rent,
                ROUND(n.earnings::numeric, 0) AS earnings,
                ROUND(n.pm25::numeric, 1) AS pm25,
                ROUND(n.hpi_yoy::numeric, 1) AS hpi_yoy,
                ROUND(
                    SQRT(
                        POWER(n.n_price - t.n_price, 2) +
                        POWER(n.n_rent - t.n_rent, 2) +
                        POWER(n.n_earn - t.n_earn, 2) +
                        POWER(n.n_pm25 - t.n_pm25, 2) +
                        POWER(n.n_hpi - t.n_hpi, 2)
                    )::numeric, 3
                ) AS distance,
                ROUND(
                    GREATEST(0, 100 * EXP(
                        -SQRT(
                            POWER(n.n_price - t.n_price, 2) +
                            POWER(n.n_rent - t.n_rent, 2) +
                            POWER(n.n_earn - t.n_earn, 2) +
                            POWER(n.n_pm25 - t.n_pm25, 2) +
                            POWER(n.n_hpi - t.n_hpi, 2)
                        ) / 2.0
                    ))::numeric, 1
                ) AS similarity_pct
            FROM normalised n, target t
            WHERE n.lad_code != :lad
            ORDER BY distance ASC
            LIMIT :lim
        """),
        {"lad": lad_code, "lim": limit, "price_types": list(PRICE_TYPES)},
    )
    rows = result.mappings().all()

    # Also fetch the target LAD's own values for context
    target = await db.execute(
        text("""
            SELECT lb.lad_name,
                   (SELECT ROUND(AVG(price)::numeric, 0)
                    FROM core_property_transactions
                    WHERE lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = :lad)
                      AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                      AND property_type = ANY(:price_types)
                   ) AS avg_price,
                   (SELECT ROUND(r.median_rent_all::numeric, 0)
                    FROM core_voa_rents_lad r WHERE r.lad_code = :lad
                    ORDER BY r.period DESC LIMIT 1
                   ) AS median_rent,
                   (SELECT ROUND(e.median_annual_earnings::numeric, 0)
                    FROM core_earnings_lad e WHERE e.lad_code = :lad
                   ) AS earnings
            FROM core_lad_boundaries lb WHERE lb.lad_code = :lad
        """),
        {"lad": lad_code, "price_types": list(PRICE_TYPES)},
    )
    target_row = target.mappings().first()

    return {
        "target": dict(target_row) if target_row else {},
        "comparable": [dict(r) for r in rows],
    }
