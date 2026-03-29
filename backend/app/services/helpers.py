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


async def expand_lsoa_codes(db, lad_code: str, ward_code: str, lsoa_code: str):
    """Bible Rule 4 — Data Querying Hierarchy.

    Expand search key to all applicable LSOAs and compute area centroid.
    - Postcode search (lsoa_code is a real code): returns [lsoa_code] + LSOA centroid
    - Ward/town search (lsoa_code='_', ward_code is real): returns all LSOAs in ward + ward centroid
    - Borough/LAD search (lsoa_code='_', ward_code='_'): returns all LSOAs in LAD + LAD centroid

    Returns (lsoa_codes: list[str], centroid_lat: float, centroid_lon: float)
    """
    from sqlalchemy import text

    # Case 1: Single LSOA (postcode search)
    if lsoa_code and lsoa_code != '_':
        lat, lon = await get_lsoa_centroid(db, lsoa_code)
        return [lsoa_code], lat, lon

    # Case 2: Ward-level search — all LSOAs in ward
    if ward_code and ward_code != '_':
        result = await db.execute(
            text("""
                SELECT DISTINCT lsoa_code
                FROM core_postcodes
                WHERE ward_code = :ward
                  AND lsoa_code IS NOT NULL
            """),
            {"ward": ward_code},
        )
        codes = [r["lsoa_code"] for r in result.mappings().all()]

        # Centroid from ward boundary if available, else from postcodes
        centroid = await db.execute(
            text("""
                SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
                FROM core_ward_boundaries WHERE ward_code = :ward
            """),
            {"ward": ward_code},
        )
        crow = centroid.mappings().first()
        if crow and crow["lat"]:
            return codes, float(crow["lat"]), float(crow["lon"])

        # Fallback: avg of postcode lat/lon
        centroid2 = await db.execute(
            text("""
                SELECT AVG(latitude) as lat, AVG(longitude) as lon
                FROM core_postcodes WHERE ward_code = :ward
            """),
            {"ward": ward_code},
        )
        crow2 = centroid2.mappings().first()
        if crow2 and crow2["lat"]:
            return codes, float(crow2["lat"]), float(crow2["lon"])
        return codes, None, None

    # Case 3: LAD/borough-level search — all LSOAs in LAD
    result = await db.execute(
        text("""
            SELECT DISTINCT lsoa_code
            FROM core_postcodes
            WHERE lad_code = :lad
              AND lsoa_code IS NOT NULL
        """),
        {"lad": lad_code},
    )
    codes = [r["lsoa_code"] for r in result.mappings().all()]

    # Centroid from LAD boundary
    centroid = await db.execute(
        text("""
            SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
            FROM core_lad_boundaries WHERE lad_code = :lad
        """),
        {"lad": lad_code},
    )
    crow = centroid.mappings().first()
    if crow and crow["lat"]:
        return codes, float(crow["lat"]), float(crow["lon"])

    # Fallback
    centroid2 = await db.execute(
        text("""
            SELECT AVG(latitude) as lat, AVG(longitude) as lon
            FROM core_postcodes WHERE lad_code = :lad
        """),
        {"lad": lad_code},
    )
    crow2 = centroid2.mappings().first()
    if crow2 and crow2["lat"]:
        return codes, float(crow2["lat"]), float(crow2["lon"])
    return codes, None, None


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
