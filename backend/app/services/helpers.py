"""Shared helpers for tab services. Bible Part 6 response shape."""


def comparison_flag(local, parent):
    """Return comparison_flag per Bible: lower_than_parent / higher_than_parent / equal_to_parent."""
    if local is None or parent is None:
        return None
    if local < parent:
        return "lower_than_parent"
    elif local > parent:
        return "higher_than_parent"
    return "equal_to_parent"


def metric(id: str, name: str, local_value, parent_value, unit: str, details=None):
    """Build a single metric dict matching Bible Section 6.1 response shape."""
    return {
        "id": id,
        "name": name,
        "local_value": local_value,
        "parent_value": parent_value,
        "unit": unit,
        "comparison_flag": comparison_flag(local_value, parent_value),
        "details": details,
    }


async def get_lsoa_centroid(db, lsoa_code: str):
    """Get lat/lon centroid of an LSOA boundary for spatial queries."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
            FROM core_lsoa_boundaries WHERE lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    row = result.mappings().first()
    if row:
        return float(row["lat"]), float(row["lon"])
    return None, None


async def get_parent_lad_codes(db, lad_code: str):
    """Get all LAD codes sharing the same parent_comparison, for parent-level averaging."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT l2.lad_code
            FROM core_lad_county_lookup l1
            JOIN core_lad_county_lookup l2 ON l2.parent_comparison = l1.parent_comparison
            WHERE l1.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    return [r["lad_code"] for r in result.mappings().all()]
