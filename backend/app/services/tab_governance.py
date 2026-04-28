"""
Local Governance data service.

Aggregates cleanly across county and other multi-LAD scopes instead of assuming a
single governing authority for every session.
"""
from collections import Counter

from sqlalchemy import text

from app.services.helpers import metric


async def fetch_local_governance(
    db,
    *,
    lad_code,
    ward_code,
    lsoa_codes,
    centroid_lat,
    centroid_lon,
    search_mode="postcode",
    local_lads=None,
    parent_lads=None,
    parent_name="England",
    boundary_source="lad",
):
    metrics = []
    if parent_lads is None:
        parent_lads = []
    if local_lads is None:
        local_lads = [lad_code] if lad_code and lad_code != "_" else []

    local_lads = [code for code in local_lads if code and code != "_"]
    parent_lads = [code for code in parent_lads if code and code != "_"]
    multi_authority = len(local_lads) > 1

    if not local_lads:
        return metrics

    # --- Council Tax ---
    # Use a straight average across the authorities inside the resolved local scope.
    ct_local = await db.execute(
        text(
            """
            SELECT AVG(band_a) AS band_a,
                   AVG(band_b) AS band_b,
                   AVG(band_c) AS band_c,
                   AVG(band_d) AS band_d,
                   AVG(band_e) AS band_e,
                   AVG(band_f) AS band_f,
                   AVG(band_g) AS band_g,
                   AVG(band_h) AS band_h,
                   AVG(band_i) AS band_i,
                   COUNT(*) AS authority_count
            FROM core_council_tax_lad
            WHERE lad_code = ANY(:lads)
            """
        ),
        {"lads": local_lads},
    )
    ct_row = ct_local.mappings().first()

    ct_parent_row = None
    if parent_lads:
        ct_parent = await db.execute(
            text(
                """
                WITH weighted AS (
                    SELECT ct.band_a, ct.band_b, ct.band_c, ct.band_d,
                           ct.band_e, ct.band_f, ct.band_g, ct.band_h, ct.band_i,
                           COALESCE(pop.total_pop, 1) AS weight
                    FROM core_council_tax_lad ct
                    LEFT JOIN (
                        SELECT l.lad_code, SUM(c.total_population) AS total_pop
                        FROM core_lsoa_boundaries l
                        JOIN core_census_lsoa c ON c.lsoa_code = l.lsoa_code
                        WHERE l.lad_code = ANY(:lads)
                        GROUP BY l.lad_code
                    ) pop ON pop.lad_code = ct.lad_code
                    WHERE ct.lad_code = ANY(:lads)
                )
                SELECT SUM(band_a * weight) / NULLIF(SUM(weight), 0) AS avg_a,
                       SUM(band_b * weight) / NULLIF(SUM(weight), 0) AS avg_b,
                       SUM(band_c * weight) / NULLIF(SUM(weight), 0) AS avg_c,
                       SUM(band_d * weight) / NULLIF(SUM(weight), 0) AS avg_d,
                       SUM(band_e * weight) / NULLIF(SUM(weight), 0) AS avg_e,
                       SUM(band_f * weight) / NULLIF(SUM(weight), 0) AS avg_f,
                       SUM(band_g * weight) / NULLIF(SUM(weight), 0) AS avg_g,
                       SUM(band_h * weight) / NULLIF(SUM(weight), 0) AS avg_h,
                       SUM(band_i * weight) / NULLIF(SUM(weight), 0) AS avg_i,
                       SUM(band_d * weight) / NULLIF(SUM(weight), 0) AS avg_band_d
                FROM weighted
                """
            ),
            {"lads": parent_lads},
        )
        ct_parent_row = ct_parent.mappings().first()

    if ct_row and ct_row["band_d"] is not None:
        local_band_d = _r(ct_row["band_d"])
        parent_band_d = _r(ct_parent_row["avg_band_d"]) if ct_parent_row and ct_parent_row["avg_band_d"] is not None else None
        details = {
            "band_a": _r(ct_row["band_a"]),
            "band_b": _r(ct_row["band_b"]),
            "band_c": _r(ct_row["band_c"]),
            "band_d": local_band_d,
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
            "authority_count": int(ct_row["authority_count"] or 0),
            "aggregation_basis": "average_across_constituent_authorities" if multi_authority else "single_authority",
            "comparison_scope": parent_name,
            "comparison_scope_label": parent_name,
            "parent_name": parent_name,
        }
        local_band_i = _r(ct_row["band_i"])
        parent_band_i = _r(ct_parent_row["avg_i"]) if ct_parent_row else None
        if local_band_i is not None or parent_band_i is not None:
            details["band_i"] = local_band_i
            details["parent_i"] = parent_band_i

        metrics.append(
            metric(
                "council_tax",
                "Council Tax (Band D)",
                local_band_d,
                parent_band_d,
                "GBP/year",
                details=details,
            )
        )

    # --- Local Authority / governance context ---
    lad_info = await db.execute(
        text(
            """
            SELECT lad_code,
                   lad_name,
                   region_name,
                   county_name,
                   is_london_borough,
                   is_metropolitan
            FROM core_lad_county_lookup
            WHERE lad_code = ANY(:lads)
            ORDER BY lad_name
            """
        ),
        {"lads": local_lads},
    )
    lad_rows = [dict(r) for r in lad_info.mappings().all()]

    if lad_rows:
        authority_names = [row["lad_name"] for row in lad_rows if row.get("lad_name")]
        county_names = sorted({row["county_name"] for row in lad_rows if row.get("county_name")})
        region_names = sorted({row["region_name"] for row in lad_rows if row.get("region_name")})

        if len(authority_names) == 1:
            authority_label = authority_names[0]
        elif boundary_source == "county" and len(county_names) == 1:
            authority_label = f"{county_names[0]} county area"
        else:
            authority_label = f"{len(authority_names)} local authorities"

        metrics.append(
            metric(
                "local_authority",
                "Local Authority",
                authority_label,
                None,
                "name",
                details={
                    "authority_count": len(authority_names),
                    "authorities": authority_names,
                    "regions": region_names,
                    "counties": county_names,
                    "is_london_borough": len(authority_names) == 1 and bool(lad_rows[0].get("is_london_borough")),
                    "is_metropolitan": len(authority_names) == 1 and bool(lad_rows[0].get("is_metropolitan")),
                    "scope_mode": "multi_authority" if multi_authority else "single_authority",
                },
            )
        )

    # --- Controlling Party ---
    control_result = await db.execute(
        text(
            """
            SELECT c.lad_code,
                   l.lad_name,
                   c.controlling_party,
                   c.majority_seats,
                   c.total_seats
            FROM core_council_control_lad c
            LEFT JOIN core_lad_county_lookup l ON l.lad_code = c.lad_code
            WHERE c.lad_code = ANY(:lads)
            ORDER BY l.lad_name
            """
        ),
        {"lads": local_lads},
    )
    control_rows = [dict(r) for r in control_result.mappings().all()]
    if control_rows:
        party_counts = Counter((row.get("controlling_party") or "Unknown") for row in control_rows)
        if len(party_counts) == 1:
            control_label = next(iter(party_counts.keys()))
        else:
            control_label = "Mixed control"

        metrics.append(
            metric(
                "controlling_party",
                "Controlling Party",
                control_label,
                None,
                "party",
                details={
                    "dominant_party": party_counts.most_common(1)[0][0],
                    "authority_count": len(control_rows),
                    "party_breakdown": [
                        {"party": party, "authority_count": count}
                        for party, count in party_counts.most_common()
                    ],
                    "authority_controls": [
                        {
                            "lad_code": row.get("lad_code"),
                            "lad_name": row.get("lad_name"),
                            "controlling_party": row.get("controlling_party"),
                            "majority_seats": int(row["majority_seats"]) if row.get("majority_seats") is not None else None,
                            "total_seats": int(row["total_seats"]) if row.get("total_seats") is not None else None,
                        }
                        for row in control_rows
                    ],
                },
            )
        )

    # --- Water Company ---
    water_result = await db.execute(
        text(
            """
            SELECT w.lad_code,
                   l.lad_name,
                   w.water_company,
                   w.water_company_type
            FROM core_water_company_lad w
            LEFT JOIN core_lad_county_lookup l ON l.lad_code = w.lad_code
            WHERE w.lad_code = ANY(:lads)
            ORDER BY l.lad_name, w.water_company
            """
        ),
        {"lads": local_lads},
    )
    water_rows = [dict(r) for r in water_result.mappings().all()]
    if water_rows:
        providers = sorted({row["water_company"] for row in water_rows if row.get("water_company")})
        water_label = providers[0] if len(providers) == 1 else "Multiple providers"
        metrics.append(
            metric(
                "water_company",
                "Water Company",
                water_label,
                None,
                "provider",
                details={
                    "provider_count": len(providers),
                    "providers": providers,
                    "authority_providers": [
                        {
                            "lad_code": row.get("lad_code"),
                            "lad_name": row.get("lad_name"),
                            "water_company": row.get("water_company"),
                            "company_type": row.get("water_company_type"),
                        }
                        for row in water_rows
                    ],
                },
            )
        )

    # --- Electricity Distribution (DNO) ---
    try:
        elec_result = await db.execute(
            text(
                """
                SELECT e.lad_code,
                       l.lad_name,
                       e.dno_name,
                       e.dno_region,
                       e.dno_code
                FROM core_electricity_dno_lad e
                LEFT JOIN core_lad_county_lookup l ON l.lad_code = e.lad_code
                WHERE e.lad_code = ANY(:lads)
                ORDER BY l.lad_name
                """
            ),
            {"lads": local_lads},
        )
        elec_rows = [dict(r) for r in elec_result.mappings().all()]
        if elec_rows:
            operators = sorted({row["dno_name"] for row in elec_rows if row.get("dno_name")})
            regions = sorted({row["dno_region"] for row in elec_rows if row.get("dno_region")})
            elec_label = operators[0] if len(operators) == 1 else "Multiple operators"
            metrics.append(
                metric(
                    "electricity_dno",
                    "Electricity Provider",
                    elec_label,
                    None,
                    "provider",
                    details={
                        "operator_count": len(operators),
                        "operators": operators,
                        "regions": regions,
                        "authority_operators": [
                            {
                                "lad_code": row.get("lad_code"),
                                "lad_name": row.get("lad_name"),
                                "dno_name": row.get("dno_name"),
                                "dno_region": row.get("dno_region"),
                            }
                            for row in elec_rows
                        ],
                    },
                )
            )
    except Exception:
        pass  # Table may not exist yet

    # --- Gas Distribution (GDN) ---
    try:
        gas_result = await db.execute(
            text(
                """
                SELECT g.lad_code,
                       l.lad_name,
                       g.gdn_name,
                       g.gdn_region
                FROM core_gas_gdn_lad g
                LEFT JOIN core_lad_county_lookup l ON l.lad_code = g.lad_code
                WHERE g.lad_code = ANY(:lads)
                ORDER BY l.lad_name
                """
            ),
            {"lads": local_lads},
        )
        gas_rows = [dict(r) for r in gas_result.mappings().all()]
        if gas_rows:
            operators = sorted({row["gdn_name"] for row in gas_rows if row.get("gdn_name")})
            regions = sorted({row["gdn_region"] for row in gas_rows if row.get("gdn_region")})
            gas_label = operators[0] if len(operators) == 1 else "Multiple operators"
            metrics.append(
                metric(
                    "gas_gdn",
                    "Gas Provider",
                    gas_label,
                    None,
                    "provider",
                    details={
                        "operator_count": len(operators),
                        "operators": operators,
                        "regions": regions,
                        "authority_operators": [
                            {
                                "lad_code": row.get("lad_code"),
                                "lad_name": row.get("lad_name"),
                                "gdn_name": row.get("gdn_name"),
                                "gdn_region": row.get("gdn_region"),
                            }
                            for row in gas_rows
                        ],
                    },
                )
            )
    except Exception:
        pass  # Table may not exist yet

    # --- Financial Health (Section 114 Notices) ---
    # Data source: core_s114_notices — ingested from official GOV.UK publications.
    s114_result = await db.execute(
        text(
            "SELECT council_name, notice_date FROM core_s114_notices WHERE lad_code = ANY(:lads) ORDER BY notice_date DESC"
        ),
        {"lads": local_lads},
    )
    s114_rows = [dict(r) for r in s114_result.mappings().all()]
    if s114_rows:
        latest = s114_rows[0]
        metrics.append(
            metric(
                "financial_health",
                "Financial Health Warning",
                f"S114 issued ({latest['notice_date'].year})",
                None,
                "status",
                details={
                    "notices": [
                        {
                            "council_name": row["council_name"],
                            "notice_date": row["notice_date"].isoformat(),
                        }
                        for row in s114_rows
                    ],
                    "notice_count": len(s114_rows),
                    "data_note": "Section 114 notices are issued when a council cannot balance its budget. Based on published notices as of April 2025.",
                },
            )
        )
    else:
        metrics.append(
            metric(
                "financial_health",
                "Financial Health",
                "No S114 notice",
                None,
                "status",
            )
        )

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
