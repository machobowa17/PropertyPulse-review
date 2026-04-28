"""Comparable-area logic for PropertyPulse.

Supports both single-LAD comparisons and broader multi-LAD scope comparisons by
building normalised feature vectors at LAD level and then aggregating them into
comparison scopes.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from app.constants import PRICE_TYPES


# Pre-computed materialized view — refreshed after each price data load.
# Falls back to a live CTE query if the MV doesn't exist yet.
FEATURES_SQL_MV = text(
    "SELECT lad_code, lad_name, avg_price, median_rent, earnings, pm25, hpi_yoy, "
    "crime_rate, avg_imd_score, median_age, pop_density, nearest_station_m, council_tax "
    "FROM mv_lad_comparable_features"
)

FEATURES_SQL_LIVE = text(
    """
    WITH price_agg AS (
        SELECT lad_code, AVG(price) AS avg_price
        FROM core_property_transactions
        WHERE date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
          AND property_type = ANY(:price_types)
        GROUP BY lad_code
    ),
    rent_latest AS (
        SELECT DISTINCT ON (lad_code) lad_code, median_rent_all
        FROM core_voa_rents_lad
        ORDER BY lad_code, period DESC
    ),
    hpi_latest AS (
        SELECT DISTINCT ON (lad_code) lad_code, yearly_change_pct
        FROM core_hpi_lad
        ORDER BY lad_code, date DESC
    ),
    aq_latest AS (
        SELECT DISTINCT ON (lad_code) lad_code, pm25_ugm3
        FROM core_air_quality_lad
        ORDER BY lad_code, year DESC
    ),
    crime_agg AS (
        SELECT b2.lad_code,
               SUM(c.crime_count)::float / NULLIF(SUM(cs.total_population), 0) * 1000 AS crime_rate
        FROM core_crime_lsoa c
        JOIN core_lsoa_boundaries b2 ON b2.lsoa_code = c.lsoa_code
        JOIN core_census_lsoa cs ON cs.lsoa_code = c.lsoa_code
        WHERE c.month > (SELECT MAX(month) - INTERVAL '12 months' FROM core_crime_lsoa)
        GROUP BY b2.lad_code
    ),
    imd_agg AS (
        SELECT b2.lad_code,
               SUM(cs.total_population * i.imd_score) / NULLIF(SUM(cs.total_population), 0) AS avg_imd_score
        FROM core_imd_lsoa i
        JOIN core_census_lsoa cs ON cs.lsoa_code = i.lsoa_code
        JOIN core_lsoa_boundaries b2 ON b2.lsoa_code = i.lsoa_code
        GROUP BY b2.lad_code
    ),
    demo_agg AS (
        SELECT b2.lad_code,
               SUM(cs.total_population * cs.median_age) / NULLIF(SUM(cs.total_population), 0) AS median_age,
               SUM(cs.total_population)::float / NULLIF(SUM(cs.total_population::float / NULLIF(cs.population_density, 0)), 0) AS pop_density
        FROM core_census_lsoa cs
        JOIN core_lsoa_boundaries b2 ON b2.lsoa_code = cs.lsoa_code
        WHERE cs.population_density > 0
        GROUP BY b2.lad_code
    ),
    transport_agg AS (
        SELECT b2.lad_code, AVG(t.nearest_station_m) AS nearest_station_m
        FROM core_lsoa_transport t
        JOIN core_lsoa_boundaries b2 ON b2.lsoa_code = t.lsoa_code
        GROUP BY b2.lad_code
    ),
    council_tax_agg AS (
        SELECT lad_code, band_d AS council_tax
        FROM core_council_tax_lad
    )
    SELECT
        lb.lad_code,
        lb.lad_name,
        p.avg_price,
        r.median_rent_all AS median_rent,
        e.median_annual_earnings AS earnings,
        aq.pm25_ugm3 AS pm25,
        h.yearly_change_pct AS hpi_yoy,
        cr.crime_rate,
        imd.avg_imd_score,
        demo.median_age,
        demo.pop_density,
        tr.nearest_station_m,
        ct.council_tax
    FROM core_lad_boundaries lb
    JOIN price_agg p ON p.lad_code = lb.lad_code
    LEFT JOIN rent_latest r ON r.lad_code = lb.lad_code
    LEFT JOIN core_earnings_lad e ON e.lad_code = lb.lad_code
    LEFT JOIN aq_latest aq ON aq.lad_code = lb.lad_code
    LEFT JOIN hpi_latest h ON h.lad_code = lb.lad_code
    LEFT JOIN crime_agg cr ON cr.lad_code = lb.lad_code
    LEFT JOIN imd_agg imd ON imd.lad_code = lb.lad_code
    LEFT JOIN demo_agg demo ON demo.lad_code = lb.lad_code
    LEFT JOIN transport_agg tr ON tr.lad_code = lb.lad_code
    LEFT JOIN council_tax_agg ct ON ct.lad_code = lb.lad_code
    """
)


def _normalise_rows(rows: list[dict]) -> list[dict]:
    numeric_fields = ["avg_price", "median_rent", "earnings", "pm25", "hpi_yoy",
                       "crime_rate", "avg_imd_score", "median_age", "pop_density",
                       "nearest_station_m", "council_tax"]
    stats: dict[str, tuple[float, float]] = {}
    for field in numeric_fields:
        values = [float(row[field]) for row in rows if row.get(field) is not None]
        if not values:
            stats[field] = (0.0, 1.0)
            continue
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
        std = variance ** 0.5 or 1.0
        stats[field] = (mean, std)

    normalised: list[dict] = []
    for row in rows:
        item = dict(row)
        for field in numeric_fields:
            value = item.get(field)
            mean, std = stats[field]
            item[f"n_{field}"] = None if value is None else (float(value) - mean) / std
        normalised.append(item)
    return normalised


def _aggregate_scope(rows: Sequence[dict], *, name: str, code: str, scope_type: str) -> dict:
    numeric_fields = ["avg_price", "median_rent", "earnings", "pm25", "hpi_yoy",
                       "crime_rate", "avg_imd_score", "median_age", "pop_density",
                       "nearest_station_m", "council_tax"]
    aggregated: dict[str, float | str | int | list[str]] = {
        "lad_code": code,
        "lad_name": name,
        "scope_name": name,
        "scope_type": scope_type,
        "component_lads": [row["lad_code"] for row in rows],
        "component_count": len(rows),
    }
    for field in numeric_fields:
        values = [float(row[field]) for row in rows if row.get(field) is not None]
        aggregated[field] = sum(values) / len(values) if values else None
        n_values = [float(row[f"n_{field}"]) for row in rows if row.get(field) is not None]
        aggregated[f"n_{field}"] = sum(n_values) / len(n_values) if n_values else None
    return aggregated


def _distance(a: dict, b: dict) -> float:
    dims = ["avg_price", "median_rent", "earnings", "pm25", "hpi_yoy",
            "crime_rate", "avg_imd_score", "median_age", "pop_density",
            "nearest_station_m", "council_tax"]
    terms = []
    for dim in dims:
        va, vb = a[f"n_{dim}"], b[f"n_{dim}"]
        if va is not None and vb is not None:
            terms.append((float(va) - float(vb)) ** 2)
    if not terms:
        return float("inf")
    return sum(terms) ** 0.5


def _similarity(distance: float) -> float:
    import math

    return round(max(0.0, 100 * math.exp(-(distance / 2.0))), 1)


async def _fetch_normalised_lad_rows(db) -> list[dict]:
    try:
        result = await db.execute(FEATURES_SQL_MV)
        rows = [dict(row) for row in result.mappings().all()]
    except Exception:
        # MV doesn't exist yet — fall back to live query
        result = await db.execute(FEATURES_SQL_LIVE, {"price_types": list(PRICE_TYPES)})
        rows = [dict(row) for row in result.mappings().all()]
    return _normalise_rows(rows)


async def find_comparable_scopes(
    db,
    *,
    target_lad_codes: Sequence[str],
    target_name: str,
    scope_type: str,
    limit: int = 5,
):
    """Return comparable scopes for either one-LAD or multi-LAD search areas."""
    normalised_rows = await _fetch_normalised_lad_rows(db)
    by_lad = {row["lad_code"]: row for row in normalised_rows}

    target_rows = [by_lad[lad_code] for lad_code in target_lad_codes if lad_code in by_lad]
    if not target_rows:
        return {
            "target": {
                "lad_name": target_name,
                "scope_name": target_name,
                "scope_type": scope_type,
                "component_count": 0,
            },
            "comparable": [],
            "status": "no_comparison_data",
            "message": "No comparison-ready data is available for this scope yet.",
        }

    target_scope = _aggregate_scope(
        target_rows,
        name=target_name,
        code="|".join(sorted(target_lad_codes)),
        scope_type=scope_type,
    )

    candidates: list[dict] = []
    target_set = set(target_lad_codes)
    for row in normalised_rows:
        if row["lad_code"] in target_set:
            continue
        candidate = _aggregate_scope(
            [row],
            name=row["lad_name"],
            code=row["lad_code"],
            scope_type="lad",
        )
        distance = _distance(candidate, target_scope)
        candidate["distance"] = round(distance, 3)
        candidate["similarity_pct"] = _similarity(distance)
        candidates.append(candidate)

    candidates.sort(key=lambda item: item["distance"])

    return {
        "target": target_scope,
        "comparable": candidates[:limit],
        "status": "ok",
        "comparison_basis": "Aggregated LAD profile across 11 dimensions: price, rent, earnings, air quality, price growth, crime, deprivation, demographics, density, transport access, and council tax.",
    }


async def find_comparable_lads(db, *, lad_code: str, limit: int = 5):
    """Backward-compatible wrapper for single-LAD comparable results."""
    result = await find_comparable_scopes(
        db,
        target_lad_codes=[lad_code],
        target_name=lad_code,
        scope_type="lad",
        limit=limit,
    )
    if result.get("target", {}).get("component_count") == 1:
        target_row = result["target"]
        row = await db.execute(
            text("SELECT lad_name FROM core_lad_boundaries WHERE lad_code = :lad_code"),
            {"lad_code": lad_code},
        )
        match = row.mappings().first()
        if match:
            target_row["lad_name"] = match["lad_name"]
            target_row["scope_name"] = match["lad_name"]
    return result
