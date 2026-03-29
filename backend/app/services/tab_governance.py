"""Tab 5: Local Governance — Bible Part 4, Tab 5.
Queries: core_council_tax_lad."""
from sqlalchemy import text
from app.services.helpers import metric, get_parent_lad_codes


async def fetch_local_governance(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon):
    metrics = []

    # --- Council Tax ---
    # Bible: Band D default, expandable shows all bands
    ct_local = await db.execute(
        text("""
            SELECT band_a, band_b, band_c, band_d, band_e, band_f, band_g, band_h
            FROM core_council_tax_lad WHERE lad_code = :lad
        """),
        {"lad": lad_code},
    )
    ct_row = ct_local.mappings().first()

    # Parent average (all LADs sharing same parent_comparison)
    parent_lads = await get_parent_lad_codes(db, lad_code)
    ct_parent = await db.execute(
        text("""
            SELECT AVG(band_a) as avg_a, AVG(band_b) as avg_b, AVG(band_c) as avg_c,
                   AVG(band_d) as avg_d, AVG(band_e) as avg_e, AVG(band_f) as avg_f,
                   AVG(band_g) as avg_g, AVG(band_h) as avg_h,
                   AVG(band_d) as avg_band_d
            FROM core_council_tax_lad
            WHERE lad_code = ANY(:lads)
        """),
        {"lads": parent_lads},
    )
    ct_parent_row = ct_parent.mappings().first()

    if ct_row:
        local_band_d = round(float(ct_row["band_d"]), 2) if ct_row["band_d"] else None
        parent_band_d = round(float(ct_parent_row["avg_band_d"]), 2) if ct_parent_row and ct_parent_row["avg_band_d"] else None

        metrics.append(metric(
            "council_tax", "Council Tax (Band D)",
            local_band_d, parent_band_d, "GBP/year",
            details={
                "band_a": _r(ct_row["band_a"]),
                "band_b": _r(ct_row["band_b"]),
                "band_c": _r(ct_row["band_c"]),
                "band_d": _r(ct_row["band_d"]),
                "band_e": _r(ct_row["band_e"]),
                "band_f": _r(ct_row["band_f"]),
                "band_g": _r(ct_row["band_g"]),
                "band_h": _r(ct_row["band_h"]),
                "parent_a": _r(ct_parent_row["avg_a"]) if ct_parent_row else None,
                "parent_b": _r(ct_parent_row["avg_b"]) if ct_parent_row else None,
                "parent_c": _r(ct_parent_row["avg_c"]) if ct_parent_row else None,
                "parent_d": _r(ct_parent_row["avg_d"]) if ct_parent_row else None,
                "parent_e": _r(ct_parent_row["avg_e"]) if ct_parent_row else None,
                "parent_f": _r(ct_parent_row["avg_f"]) if ct_parent_row else None,
                "parent_g": _r(ct_parent_row["avg_g"]) if ct_parent_row else None,
                "parent_h": _r(ct_parent_row["avg_h"]) if ct_parent_row else None,
            },
        ))

    # --- LAD Info ---
    lad_info = await db.execute(
        text("""
            SELECT lad_name, region_name, county_name, is_london_borough, is_metropolitan
            FROM core_lad_county_lookup WHERE lad_code = :lad
        """),
        {"lad": lad_code},
    )
    lad_row = lad_info.mappings().first()

    if lad_row:
        metrics.append(metric(
            "local_authority", "Local Authority",
            lad_row["lad_name"], None, "name",
            details={
                "region": lad_row["region_name"],
                "county": lad_row["county_name"],
                "is_london_borough": lad_row["is_london_borough"],
                "is_metropolitan": lad_row["is_metropolitan"],
            },
        ))

    # --- Controlling Party ---
    control_result = await db.execute(
        text("SELECT controlling_party, majority_seats, total_seats FROM core_council_control_lad WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    control_row = control_result.mappings().first()
    if control_row:
        metrics.append(metric(
            "controlling_party", "Controlling Party",
            control_row["controlling_party"], None, "party",
            details={
                "majority_seats": int(control_row["majority_seats"]) if control_row["majority_seats"] else None,
                "total_seats": int(control_row["total_seats"]) if control_row["total_seats"] else None,
            },
        ))

    # --- Water Company ---
    water_result = await db.execute(
        text("SELECT water_company, water_company_type FROM core_water_company_lad WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    water_row = water_result.mappings().first()
    if water_row:
        metrics.append(metric(
            "water_company", "Water Company",
            water_row["water_company"], None, "provider",
            details={"company_type": water_row["water_company_type"]},
        ))

    # --- Financial Health (S114 Risk) ---
    s114_result = await db.execute(
        text("SELECT council_name, notice_date FROM core_s114_notices WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    s114_row = s114_result.mappings().first()
    s114_status = "S114 Notice Issued" if s114_row else "No S114 Notice"
    metrics.append(metric(
        "financial_health", "Financial Health",
        s114_status, None, "status",
        details={
            "s114_issued": s114_row is not None,
            "notice_date": str(s114_row["notice_date"]) if s114_row else None,
        },
    ))

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
