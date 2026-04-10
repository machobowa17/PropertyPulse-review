"""Comparable-area logic for PropertyPulse.

Supports both single-LAD comparisons and broader multi-LAD scope comparisons by
building normalised feature vectors at LAD level and then aggregating them into
comparison scopes.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from app.constants import PRICE_TYPES


FEATURES_SQL = text(
    """
    WITH features AS (
        SELECT
            lb.lad_code,
            lb.lad_name,
            (
                SELECT AVG(price)
                FROM core_property_transactions
                WHERE lsoa_code IN (
                    SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = lb.lad_code
                )
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                  AND property_type = ANY(:price_types)
            ) AS avg_price,
            (
                SELECT r.median_rent_all
                FROM core_voa_rents_lad r
                WHERE r.lad_code = lb.lad_code
                ORDER BY r.period DESC
                LIMIT 1
            ) AS median_rent,
            (
                SELECT e.median_annual_earnings
                FROM core_earnings_lad e
                WHERE e.lad_code = lb.lad_code
            ) AS earnings,
            (
                SELECT aq.pm25_ugm3
                FROM core_air_quality_lad aq
                WHERE aq.lad_code = lb.lad_code
                ORDER BY aq.year DESC
                LIMIT 1
            ) AS pm25,
            (
                SELECT h.yearly_change_pct
                FROM core_hpi_lad h
                WHERE h.lad_code = lb.lad_code
                ORDER BY h.date DESC
                LIMIT 1
            ) AS hpi_yoy
        FROM core_lad_boundaries lb
    )
    SELECT *
    FROM features
    WHERE avg_price IS NOT NULL
    """
)


def _normalise_rows(rows: list[dict]) -> list[dict]:
    numeric_fields = ["avg_price", "median_rent", "earnings", "pm25", "hpi_yoy"]
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
            item[f"n_{field}"] = 0.0 if value is None else (float(value) - mean) / std
        normalised.append(item)
    return normalised


def _aggregate_scope(rows: Sequence[dict], *, name: str, code: str, scope_type: str) -> dict:
    numeric_fields = ["avg_price", "median_rent", "earnings", "pm25", "hpi_yoy"]
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
        aggregated[f"n_{field}"] = sum(n_values) / len(n_values) if n_values else 0.0
    return aggregated


def _distance(a: dict, b: dict) -> float:
    dims = ["avg_price", "median_rent", "earnings", "pm25", "hpi_yoy"]
    return sum((float(a[f"n_{dim}"]) - float(b[f"n_{dim}"])) ** 2 for dim in dims) ** 0.5


def _similarity(distance: float) -> float:
    import math

    return round(max(0.0, 100 * math.exp(-(distance / 2.0))), 1)


async def _fetch_normalised_lad_rows(db) -> list[dict]:
    result = await db.execute(FEATURES_SQL, {"price_types": list(PRICE_TYPES)})
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
    for row in normalised_rows:
        if row["lad_code"] in set(target_lad_codes):
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
        "comparison_basis": "Aggregated LAD profile across price, rent, earnings, air quality, and price growth.",
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
