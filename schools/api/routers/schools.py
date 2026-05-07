"""School API endpoints.

Serves school data to EC2 — nearby schools, detail profiles, comparisons.
EC2 passes search parameters, gets back processed results ready for display.
"""

import logging
import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

from api.db import get_conn, put_conn

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Nearby Schools ──────────────────────────────────────────────────
@router.get("/nearby")
def nearby_schools(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_m: int = Query(3000, ge=100, le=20000, description="Search radius in metres"),
    phase: Optional[str] = Query(None, description="Comma-separated phases: Primary,Secondary,All-through,16 plus,Nursery"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return schools near a lat/lon point with distance, Ofsted rating, and key metrics."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            phase_filter = ""
            params = {"lat": lat, "lon": lon, "radius": radius_m, "limit": limit}

            if phase:
                phases = [p.strip() for p in phase.split(",")]
                phase_filter = "AND i.phase = ANY(%(phases)s)"
                params["phases"] = phases

            cur.execute(
                f"""
                SELECT
                    i.urn, i.name, i.type_code, i.phase, i.gender,
                    i.religious_char, i.age_low, i.age_high,
                    i.capacity, i.pupil_count, i.postcode,
                    i.latitude, i.longitude, i.la_name, i.lad_code,
                    i.website, i.phone, i.admissions_policy,
                    i.boarding, i.nursery_provision, i.sixth_form,
                    ROUND(ST_Distance(
                        i.geom::geography,
                        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
                    ))::int AS distance_m,
                    -- Latest Ofsted rating
                    insp.overall_rating AS ofsted_rating,
                    insp.inspection_date AS ofsted_date,
                    insp.quality_of_education,
                    insp.behaviour_attitudes,
                    insp.personal_development,
                    insp.leadership_management,
                    -- Latest KS2 results (primary)
                    ks2.pct_rwm_expected AS ks2_rwm_expected,
                    ks2.reading_progress AS ks2_reading_progress,
                    ks2.maths_progress AS ks2_maths_progress,
                    ks2.writing_progress AS ks2_writing_progress,
                    ks2.reading_scaled_score AS ks2_reading_score,
                    ks2.maths_scaled_score AS ks2_maths_score,
                    -- Latest KS4 results (secondary)
                    ks4.attainment_8,
                    ks4.progress_8,
                    ks4.pct_grade_5_em AS ks4_basics_5,
                    -- Latest KS5 results (sixth form)
                    ks5.avg_point_score_a AS ks5_a_level_score,
                    -- Demographics
                    dem.pct_fsm,
                    dem.pct_eal,
                    dem.total_pupils AS dem_total_pupils,
                    -- Workforce
                    wf.pupil_teacher_ratio,
                    -- Absence
                    abs.overall_absence_pct,
                    abs.persistent_absence_pct,
                    -- Admissions
                    adm.applications_received AS adm_applications,
                    adm.offers_made AS adm_offers,
                    adm.is_oversubscribed,
                    -- LA Admissions Detail (scraped from booklets)
                    la_adm.la_ldo,
                    la_adm.la_ldo_unit,
                    la_adm.la_sif,
                    la_adm.la_allocation,
                    -- Finances
                    fin.per_pupil_expenditure,
                    fin.pct_budget_staff,
                    -- Academic Velocity (previous year for trend)
                    ks2_prev.pct_rwm_expected AS ks2_prev_rwm,
                    ks4_prev.progress_8 AS ks4_prev_p8,
                    ks4_prev.attainment_8 AS ks4_prev_a8,
                    ks4_latest.attainment_8 AS ks4_latest_a8
                FROM schools.institutions i
                LEFT JOIN LATERAL (
                    SELECT overall_rating, inspection_date,
                           quality_of_education, behaviour_attitudes,
                           personal_development, leadership_management
                    FROM schools.inspections
                    WHERE urn = i.urn AND inspection_body = 'Ofsted'
                    ORDER BY inspection_date DESC
                    LIMIT 1
                ) insp ON true
                LEFT JOIN LATERAL (
                    SELECT pct_rwm_expected, reading_progress, maths_progress,
                           writing_progress, reading_scaled_score, maths_scaled_score
                    FROM schools.ks2_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks2 ON true
                LEFT JOIN LATERAL (
                    SELECT attainment_8, progress_8, pct_grade_5_em
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY (CASE WHEN progress_8 IS NOT NULL THEN 0 ELSE 1 END), academic_year DESC
                    LIMIT 1
                ) ks4 ON true
                LEFT JOIN LATERAL (
                    SELECT avg_point_score_a
                    FROM schools.ks5_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks5 ON true
                LEFT JOIN LATERAL (
                    SELECT pct_fsm, pct_eal, total_pupils
                    FROM schools.pupil_demographics
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) dem ON true
                LEFT JOIN LATERAL (
                    SELECT pupil_teacher_ratio
                    FROM schools.workforce
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) wf ON true
                LEFT JOIN LATERAL (
                    SELECT overall_absence_pct, persistent_absence_pct
                    FROM schools.absence
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) abs ON true
                LEFT JOIN LATERAL (
                    SELECT applications_received, offers_made, is_oversubscribed
                    FROM schools.admissions
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) adm ON true
                LEFT JOIN LATERAL (
                    SELECT last_distance_offered AS la_ldo,
                           ldo_unit AS la_ldo_unit,
                           sif_required AS la_sif,
                           allocation_breakdown AS la_allocation
                    FROM schools.admissions_la_detail
                    WHERE urn = i.urn
                    ORDER BY academic_year DESC LIMIT 1
                ) la_adm ON true
                LEFT JOIN LATERAL (
                    SELECT per_pupil_expenditure, pct_budget_staff
                    FROM schools.finances
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) fin ON true
                LEFT JOIN LATERAL (
                    SELECT pct_rwm_expected
                    FROM schools.ks2_results
                    WHERE urn = i.urn ORDER BY academic_year DESC OFFSET 1 LIMIT 1
                ) ks2_prev ON true
                LEFT JOIN LATERAL (
                    SELECT progress_8, attainment_8
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY academic_year DESC OFFSET 1 LIMIT 1
                ) ks4_prev ON true
                LEFT JOIN LATERAL (
                    SELECT attainment_8
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY academic_year DESC LIMIT 1
                ) ks4_latest ON true
                WHERE i.is_open = true
                  AND i.geom IS NOT NULL
                  AND ST_DWithin(
                      i.geom::geography,
                      ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                      %(radius)s
                  )
                  {phase_filter}
                ORDER BY distance_m
                LIMIT %(limit)s
                """,
                params,
            )
            rows = []
            for r in cur.fetchall():
                row = _serialize(r)
                row["velocity"] = _compute_velocity(row)
                row["quality_flags"] = _quality_flags(row)
                rows.append(row)
            return {"schools": rows, "count": len(rows)}
    except Exception as e:
        logger.exception("Nearby schools query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── Schools by LSOA codes ──────────────────────────────────────────
@router.post("/by-lsoa")
def schools_by_lsoa(req: dict):
    """Return schools matching a set of LSOA codes or LAD codes (for area-mode searches).

    Supports two modes:
    - lsoa_codes: matches schools by postcode → LSOA lookup
    - lad_codes: matches schools directly by LAD code (preferred for area search)
    """
    lsoa_codes = req.get("lsoa_codes", [])
    lad_codes = req.get("lad_codes", [])
    phase = req.get("phase")
    lat = req.get("lat")
    lon = req.get("lon")
    limit = req.get("limit", 50)

    if not lsoa_codes and not lad_codes:
        raise HTTPException(400, "lsoa_codes or lad_codes must not be empty")

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            phase_filter = ""
            params = {"limit": limit}

            if phase:
                phases = [p.strip() for p in phase.split(",")]
                phase_filter = "AND i.phase = ANY(%(phases)s)"
                params["phases"] = phases

            distance_col = "NULL::int AS distance_m"
            distance_order = "i.name"
            if lat is not None and lon is not None:
                params["lat"] = lat
                params["lon"] = lon
                distance_col = """ROUND(ST_Distance(
                    i.geom::geography,
                    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
                ))::int AS distance_m"""
                distance_order = "distance_m"

            # Prefer LAD code matching (direct), fall back to LSOA→postcode join
            if lad_codes:
                params["lad_codes"] = lad_codes
                area_join = ""
                area_filter = "AND i.lad_code = ANY(%(lad_codes)s)"
            else:
                params["lsoa_codes"] = lsoa_codes
                area_join = "JOIN public.postcode_lsoa pl ON pl.postcode = i.postcode"
                area_filter = "AND pl.lsoa_code = ANY(%(lsoa_codes)s)"

            cur.execute(
                f"""
                SELECT
                    i.urn, i.name, i.type_code, i.phase, i.gender,
                    i.religious_char, i.age_low, i.age_high,
                    i.capacity, i.pupil_count, i.postcode,
                    i.latitude, i.longitude, i.la_name, i.lad_code,
                    i.website, i.phone, i.admissions_policy,
                    {distance_col},
                    insp.overall_rating AS ofsted_rating,
                    insp.inspection_date AS ofsted_date,
                    insp.quality_of_education,
                    insp.behaviour_attitudes,
                    insp.personal_development,
                    insp.leadership_management,
                    -- Latest exam results
                    ks2.pct_rwm_expected AS ks2_rwm_expected,
                    ks2.reading_progress AS ks2_reading_progress,
                    ks2.maths_progress AS ks2_maths_progress,
                    ks4.attainment_8,
                    ks4.progress_8,
                    ks4.pct_grade_5_em AS ks4_basics_5,
                    ks5.avg_point_score_a AS ks5_a_level_score,
                    -- Demographics
                    dem.pct_fsm,
                    dem.pct_eal,
                    dem.total_pupils AS dem_total_pupils,
                    -- Workforce
                    wf.pupil_teacher_ratio,
                    -- Absence
                    abs.overall_absence_pct,
                    abs.persistent_absence_pct,
                    -- Admissions
                    adm.applications_received AS adm_applications,
                    adm.offers_made AS adm_offers,
                    adm.is_oversubscribed,
                    -- LA Admissions Detail (scraped from booklets)
                    la_adm.la_ldo,
                    la_adm.la_ldo_unit,
                    la_adm.la_sif,
                    la_adm.la_allocation,
                    -- Finances
                    fin.per_pupil_expenditure,
                    fin.pct_budget_staff,
                    -- Academic Velocity (previous year for trend)
                    ks2_prev.pct_rwm_expected AS ks2_prev_rwm,
                    ks4_prev.progress_8 AS ks4_prev_p8,
                    ks4_prev.attainment_8 AS ks4_prev_a8,
                    ks4_latest.attainment_8 AS ks4_latest_a8
                FROM schools.institutions i
                {area_join}
                LEFT JOIN LATERAL (
                    SELECT overall_rating, inspection_date,
                           quality_of_education, behaviour_attitudes,
                           personal_development, leadership_management
                    FROM schools.inspections
                    WHERE urn = i.urn AND inspection_body = 'Ofsted'
                    ORDER BY inspection_date DESC
                    LIMIT 1
                ) insp ON true
                LEFT JOIN LATERAL (
                    SELECT pct_rwm_expected, reading_progress, maths_progress
                    FROM schools.ks2_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks2 ON true
                LEFT JOIN LATERAL (
                    SELECT attainment_8, progress_8, pct_grade_5_em
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY (CASE WHEN progress_8 IS NOT NULL THEN 0 ELSE 1 END), academic_year DESC
                    LIMIT 1
                ) ks4 ON true
                LEFT JOIN LATERAL (
                    SELECT avg_point_score_a
                    FROM schools.ks5_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks5 ON true
                LEFT JOIN LATERAL (
                    SELECT pct_fsm, pct_eal, total_pupils
                    FROM schools.pupil_demographics
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) dem ON true
                LEFT JOIN LATERAL (
                    SELECT pupil_teacher_ratio
                    FROM schools.workforce
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) wf ON true
                LEFT JOIN LATERAL (
                    SELECT overall_absence_pct, persistent_absence_pct
                    FROM schools.absence
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) abs ON true
                LEFT JOIN LATERAL (
                    SELECT applications_received, offers_made, is_oversubscribed
                    FROM schools.admissions
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) adm ON true
                LEFT JOIN LATERAL (
                    SELECT last_distance_offered AS la_ldo,
                           ldo_unit AS la_ldo_unit,
                           sif_required AS la_sif,
                           allocation_breakdown AS la_allocation
                    FROM schools.admissions_la_detail
                    WHERE urn = i.urn
                    ORDER BY academic_year DESC LIMIT 1
                ) la_adm ON true
                LEFT JOIN LATERAL (
                    SELECT per_pupil_expenditure, pct_budget_staff
                    FROM schools.finances
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) fin ON true
                LEFT JOIN LATERAL (
                    SELECT pct_rwm_expected
                    FROM schools.ks2_results
                    WHERE urn = i.urn ORDER BY academic_year DESC OFFSET 1 LIMIT 1
                ) ks2_prev ON true
                LEFT JOIN LATERAL (
                    SELECT progress_8, attainment_8
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY academic_year DESC OFFSET 1 LIMIT 1
                ) ks4_prev ON true
                LEFT JOIN LATERAL (
                    SELECT attainment_8
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY academic_year DESC LIMIT 1
                ) ks4_latest ON true
                WHERE i.is_open = true
                  {area_filter}
                  {phase_filter}
                ORDER BY {distance_order}
                LIMIT %(limit)s
                """,
                params,
            )
            rows = []
            for r in cur.fetchall():
                row = _serialize(r)
                row["velocity"] = _compute_velocity(row)
                row["quality_flags"] = _quality_flags(row)
                rows.append(row)
            return {"schools": rows, "count": len(rows)}
    except Exception as e:
        logger.exception("Schools by LSOA query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── Quality Summary ─────────────────────────────────────────────────
@router.get("/quality-summary")
def quality_summary(
    lat: float = Query(None),
    lon: float = Query(None),
    radius_m: int = Query(3000, ge=100, le=20000),
    phase: Optional[str] = Query(None),
    lad_code: Optional[str] = Query(None, description="LAD code for area-mode search"),
):
    """Return Ofsted rating distribution for schools near a point.

    This is the data needed for the school metric cards:
    - Count by phase (primary/secondary)
    - Ofsted rating distribution
    - Average rating
    """
    if not lat and not lon and not lad_code:
        raise HTTPException(400, "Provide lat+lon or lad_code")

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            phase_filter = ""
            params = {}

            if phase:
                phases = [p.strip() for p in phase.split(",")]
                phase_filter = "AND i.phase = ANY(%(phases)s)"
                params["phases"] = phases

            # Area filter: lad_code OR radius search
            if lad_code:
                params["lad_code"] = lad_code
                area_filter = "AND i.lad_code = %(lad_code)s"
            else:
                params["lat"] = lat
                params["lon"] = lon
                params["radius"] = radius_m
                area_filter = """AND i.geom IS NOT NULL
                      AND ST_DWithin(
                          i.geom::geography,
                          ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                          %(radius)s
                      )"""

            cur.execute(
                f"""
                WITH nearby AS (
                    SELECT i.urn, i.phase, insp.overall_rating
                    FROM schools.institutions i
                    LEFT JOIN LATERAL (
                        SELECT overall_rating
                        FROM schools.inspections
                        WHERE urn = i.urn AND inspection_body = 'Ofsted'
                        ORDER BY inspection_date DESC
                        LIMIT 1
                    ) insp ON true
                    WHERE i.is_open = true
                      {area_filter}
                      {phase_filter}
                )
                SELECT
                    COUNT(*) AS total_schools,
                    COUNT(*) FILTER (WHERE phase = 'Primary') AS primary_count,
                    COUNT(*) FILTER (WHERE phase = 'Secondary') AS secondary_count,
                    COUNT(*) FILTER (WHERE phase = 'All-through') AS allthrough_count,
                    COUNT(*) FILTER (WHERE phase = '16 plus') AS post16_count,
                    COUNT(*) FILTER (WHERE overall_rating = 1) AS outstanding,
                    COUNT(*) FILTER (WHERE overall_rating = 2) AS good,
                    COUNT(*) FILTER (WHERE overall_rating = 3) AS requires_improvement,
                    COUNT(*) FILTER (WHERE overall_rating = 4) AS inadequate,
                    COUNT(*) FILTER (WHERE overall_rating IS NULL) AS not_inspected,
                    ROUND(AVG(overall_rating) FILTER (WHERE overall_rating IS NOT NULL), 2) AS avg_rating
                FROM nearby
                """,
                params,
            )
            row = cur.fetchone()
            return _serialize(row) if row else {}
    except Exception as e:
        logger.exception("Quality summary query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── Catchment Check ─────────────────────────────────────────────────
@router.get("/catchment-check")
def catchment_check(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    phase: Optional[str] = Query(None, description="Phase filter"),
    limit: int = Query(20, ge=1, le=50),
):
    """Which schools likely serve this location? Returns schools ranked by admission probability."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find the nearest school's LSOA to this point
            cur.execute("""
                SELECT pl.lsoa_code
                FROM schools.institutions i
                JOIN postcode_lsoa pl ON REPLACE(UPPER(pl.postcode), ' ', '') = REPLACE(UPPER(i.postcode), ' ', '')
                WHERE i.geom IS NOT NULL
                ORDER BY ST_Distance(
                    i.geom::geography,
                    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
                )
                LIMIT 1
            """, {"lat": lat, "lon": lon})
            row = cur.fetchone()
            if not row:
                return {"schools": [], "count": 0, "lsoa_code": None}

            lsoa_code = row["lsoa_code"]

            phase_filter = ""
            params = {"lsoa": lsoa_code, "limit": limit}
            if phase:
                phases = [p.strip() for p in phase.split(",")]
                phase_filter = "AND i.phase = ANY(%(phases)s)"
                params["phases"] = phases

            cur.execute(
                f"""
                SELECT
                    c.urn, i.name, i.phase, i.type_code,
                    c.distance_m, c.admission_probability,
                    c.is_within_ldo,
                    insp.overall_rating AS ofsted_rating,
                    i.capacity, i.pupil_count
                FROM schools.catchment_model c
                JOIN schools.institutions i ON i.urn = c.urn
                LEFT JOIN LATERAL (
                    SELECT overall_rating
                    FROM schools.inspections
                    WHERE urn = i.urn AND inspection_body = 'Ofsted'
                    ORDER BY inspection_date DESC LIMIT 1
                ) insp ON true
                WHERE c.lsoa_code = %(lsoa)s
                  AND i.is_open = true
                  {phase_filter}
                ORDER BY c.admission_probability DESC
                LIMIT %(limit)s
                """,
                params,
            )
            rows = [_serialize(r) for r in cur.fetchall()]
            return {"schools": rows, "count": len(rows), "lsoa_code": lsoa_code}
    except Exception as e:
        logger.exception("Catchment check failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── League Table ────────────────────────────────────────────────────
@router.get("/league-table")
def league_table(
    lad_code: Optional[str] = Query(None, description="LAD code for local league"),
    phase: str = Query("Secondary", description="Phase: Primary or Secondary"),
    sort_by: str = Query("progress_8", description="Sort metric: progress_8, attainment_8, ks2_rwm, ofsted"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return a league table of schools sorted by a performance metric."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            params = {"phase": phase, "limit": limit}
            area_filter = ""
            if lad_code:
                area_filter = "AND i.lad_code = %(lad_code)s"
                params["lad_code"] = lad_code

            sort_map = {
                "progress_8": "ks4.progress_8 DESC NULLS LAST",
                "attainment_8": "ks4.attainment_8 DESC NULLS LAST",
                "ks2_rwm": "ks2.pct_rwm_expected DESC NULLS LAST",
                "ofsted": "insp.overall_rating ASC NULLS LAST",
            }
            order_clause = sort_map.get(sort_by, "ks4.progress_8 DESC NULLS LAST")

            cur.execute(
                f"""
                SELECT
                    i.urn, i.name, i.phase, i.type_code,
                    i.la_name, i.lad_code,
                    i.capacity, i.pupil_count,
                    insp.overall_rating AS ofsted_rating,
                    ks2.pct_rwm_expected AS ks2_rwm_expected,
                    ks2.reading_progress AS ks2_reading_progress,
                    ks2.maths_progress AS ks2_maths_progress,
                    ks4.attainment_8,
                    ks4.progress_8,
                    ks4.pct_grade_5_em AS ks4_basics_5,
                    ks5.avg_point_score_a AS ks5_a_level_score,
                    dem.pct_fsm,
                    abs.overall_absence_pct,
                    fin.per_pupil_expenditure
                FROM schools.institutions i
                LEFT JOIN LATERAL (
                    SELECT overall_rating
                    FROM schools.inspections
                    WHERE urn = i.urn AND inspection_body = 'Ofsted'
                    ORDER BY inspection_date DESC LIMIT 1
                ) insp ON true
                LEFT JOIN LATERAL (
                    SELECT pct_rwm_expected, reading_progress, maths_progress
                    FROM schools.ks2_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks2 ON true
                LEFT JOIN LATERAL (
                    SELECT attainment_8, progress_8, pct_grade_5_em
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY (CASE WHEN progress_8 IS NOT NULL THEN 0 ELSE 1 END), academic_year DESC
                    LIMIT 1
                ) ks4 ON true
                LEFT JOIN LATERAL (
                    SELECT avg_point_score_a
                    FROM schools.ks5_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks5 ON true
                LEFT JOIN LATERAL (
                    SELECT pct_fsm
                    FROM schools.pupil_demographics
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) dem ON true
                LEFT JOIN LATERAL (
                    SELECT overall_absence_pct
                    FROM schools.absence
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) abs ON true
                LEFT JOIN LATERAL (
                    SELECT per_pupil_expenditure
                    FROM schools.finances
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) fin ON true
                WHERE i.is_open = true
                  AND i.phase = %(phase)s
                  {area_filter}
                ORDER BY {order_clause}
                LIMIT %(limit)s
                """,
                params,
            )
            rows = [_serialize(r) for r in cur.fetchall()]
            return {"schools": rows, "count": len(rows), "sort_by": sort_by, "phase": phase}
    except Exception as e:
        logger.exception("League table query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── School Detail ───────────────────────────────────────────────────
@router.get("/{urn}")
def school_detail(urn: int):
    """Return full school profile — institution info + inspection history + performance data."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Institution
            cur.execute(
                """
                SELECT * FROM schools.institutions WHERE urn = %(urn)s
                """,
                {"urn": urn},
            )
            school = cur.fetchone()
            if not school:
                raise HTTPException(404, f"School URN {urn} not found")

            # Full inspection history
            cur.execute(
                """
                SELECT * FROM schools.inspections
                WHERE urn = %(urn)s
                ORDER BY inspection_date DESC
                """,
                {"urn": urn},
            )
            inspections = [_serialize(r) for r in cur.fetchall()]

            # KS2 multi-year results
            cur.execute(
                """
                SELECT * FROM schools.ks2_results
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            ks2_results = [_serialize(r) for r in cur.fetchall()]

            # KS4 multi-year results
            cur.execute(
                """
                SELECT * FROM schools.ks4_results
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            ks4_results = [_serialize(r) for r in cur.fetchall()]

            # KS5 multi-year results
            cur.execute(
                """
                SELECT * FROM schools.ks5_results
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            ks5_results = [_serialize(r) for r in cur.fetchall()]

            # Destinations
            cur.execute(
                """
                SELECT * FROM schools.destinations
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            destinations = [_serialize(r) for r in cur.fetchall()]

            # Subject-level results (latest year only, limit 30)
            cur.execute(
                """
                SELECT * FROM schools.subjects
                WHERE urn = %(urn)s
                ORDER BY academic_year DESC, entries DESC NULLS LAST
                LIMIT 30
                """,
                {"urn": urn},
            )
            subjects = [_serialize(r) for r in cur.fetchall()]

            # Workforce data
            cur.execute(
                """
                SELECT * FROM schools.workforce
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            workforce = [_serialize(r) for r in cur.fetchall()]

            # Pupil demographics
            cur.execute(
                """
                SELECT * FROM schools.pupil_demographics
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            demographics = [_serialize(r) for r in cur.fetchall()]

            # Parent View
            cur.execute(
                """
                SELECT * FROM schools.parent_view
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            parent_view = [_serialize(r) for r in cur.fetchall()]

            # Absence rates
            cur.execute(
                """
                SELECT * FROM schools.absence
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            absence = [_serialize(r) for r in cur.fetchall()]

            # Admissions (DfE official)
            cur.execute(
                """
                SELECT * FROM schools.admissions
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            admissions = [_serialize(r) for r in cur.fetchall()]

            # Admissions LA detail (scraped from booklets)
            cur.execute(
                """
                SELECT academic_year, year_group,
                       last_distance_offered, ldo_unit, ldo_detail,
                       distance_method, allocation_breakdown,
                       oversubscription_criteria, sif_required,
                       open_days, appeals_heard, appeals_upheld,
                       waiting_list_size, source_la_code,
                       source_confidence, data_quality_flags
                FROM schools.admissions_la_detail
                WHERE urn = %(urn)s
                ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            admissions_la_detail = [_serialize(r) for r in cur.fetchall()]

            # Finances
            cur.execute(
                """
                SELECT * FROM schools.finances
                WHERE urn = %(urn)s ORDER BY academic_year DESC
                """,
                {"urn": urn},
            )
            finances = [_serialize(r) for r in cur.fetchall()]

            # SEN provisions
            cur.execute(
                """
                SELECT * FROM schools.sen_provisions
                WHERE urn = %(urn)s
                """,
                {"urn": urn},
            )
            sen_provisions = [_serialize(r) for r in cur.fetchall()]

            result = _serialize(school)
            result["inspections"] = inspections
            result["ks2_results"] = ks2_results
            result["ks4_results"] = ks4_results
            result["ks5_results"] = ks5_results
            result["destinations"] = destinations
            result["subjects"] = subjects
            result["workforce"] = workforce
            result["demographics"] = demographics
            result["parent_view"] = parent_view
            result["absence"] = absence
            result["admissions"] = admissions
            result["admissions_la_detail"] = admissions_la_detail
            result["finances"] = finances
            result["sen_provisions"] = sen_provisions

            # Compute velocity from multi-year results arrays
            result["velocity"] = _compute_velocity_from_results(
                result.get("phase"), ks2_results, ks4_results
            )
            result["quality_flags"] = _quality_flags(result)

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("School detail query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── Compare Schools ─────────────────────────────────────────────────
@router.post("/compare")
def compare_schools(req: dict):
    """Compare up to 5 schools side-by-side."""
    urns = req.get("urns", [])
    if not urns or len(urns) > 5:
        raise HTTPException(400, "Provide 1-5 URNs")

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    i.urn, i.name, i.type_code, i.phase, i.gender,
                    i.religious_char, i.age_low, i.age_high,
                    i.capacity, i.pupil_count, i.postcode,
                    i.latitude, i.longitude, i.la_name, i.lad_code,
                    i.website, i.phone, i.admissions_policy,
                    i.boarding, i.nursery_provision, i.sixth_form,
                    insp.overall_rating AS ofsted_rating,
                    insp.inspection_date AS ofsted_date,
                    insp.quality_of_education,
                    insp.behaviour_attitudes,
                    insp.personal_development,
                    insp.leadership_management,
                    insp.early_years,
                    insp.sixth_form AS sixth_form_rating,
                    ks2.pct_rwm_expected AS ks2_rwm_expected,
                    ks2.reading_progress AS ks2_reading_progress,
                    ks2.maths_progress AS ks2_maths_progress,
                    ks2.reading_scaled_score AS ks2_reading_score,
                    ks2.maths_scaled_score AS ks2_maths_score,
                    ks4.attainment_8,
                    ks4.progress_8,
                    ks4.pct_grade_5_em AS ks4_basics_5,
                    ks5.avg_point_score_a AS ks5_a_level_score,
                    dem.pct_fsm,
                    dem.pct_eal,
                    dem.total_pupils AS dem_total_pupils,
                    wf.pupil_teacher_ratio
                FROM schools.institutions i
                LEFT JOIN LATERAL (
                    SELECT overall_rating, inspection_date,
                           quality_of_education, behaviour_attitudes,
                           personal_development, leadership_management,
                           early_years, sixth_form
                    FROM schools.inspections
                    WHERE urn = i.urn AND inspection_body = 'Ofsted'
                    ORDER BY inspection_date DESC
                    LIMIT 1
                ) insp ON true
                LEFT JOIN LATERAL (
                    SELECT pct_rwm_expected, reading_progress, maths_progress,
                           reading_scaled_score, maths_scaled_score
                    FROM schools.ks2_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks2 ON true
                LEFT JOIN LATERAL (
                    SELECT attainment_8, progress_8, pct_grade_5_em
                    FROM schools.ks4_results
                    WHERE urn = i.urn
                    ORDER BY (CASE WHEN progress_8 IS NOT NULL THEN 0 ELSE 1 END), academic_year DESC
                    LIMIT 1
                ) ks4 ON true
                LEFT JOIN LATERAL (
                    SELECT avg_point_score_a
                    FROM schools.ks5_results
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) ks5 ON true
                LEFT JOIN LATERAL (
                    SELECT pct_fsm, pct_eal, total_pupils
                    FROM schools.pupil_demographics
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) dem ON true
                LEFT JOIN LATERAL (
                    SELECT pupil_teacher_ratio
                    FROM schools.workforce
                    WHERE urn = i.urn ORDER BY academic_year DESC LIMIT 1
                ) wf ON true
                WHERE i.urn = ANY(%(urns)s)
                """,
                {"urns": urns},
            )
            rows = [_serialize(r) for r in cur.fetchall()]
            return {"schools": rows}
    except Exception as e:
        logger.exception("Compare schools query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── Walk Time (calls MOTIS internally) ──────────────────────────────
@router.get("/{urn}/walk-time")
def walk_time(
    urn: int,
    from_lat: float = Query(...),
    from_lon: float = Query(...),
):
    """Calculate walking time from a point to a school using MOTIS."""
    import json
    import urllib.request as req
    import ssl

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT latitude, longitude FROM schools.institutions WHERE urn = %(urn)s",
                {"urn": urn},
            )
            school = cur.fetchone()
            if not school or not school["latitude"]:
                raise HTTPException(404, "School not found or no coordinates")

        # Call MOTIS (running on same Hetzner box, port 8080)
        # Use Docker gateway IP since school_api is in a different network than MOTIS
        import os
        motis_host = os.environ.get("MOTIS_HOST", "172.19.0.1")
        motis_url = (
            f"http://{motis_host}:8080/api/v1/plan"
            f"?fromPlace={from_lat},{from_lon}"
            f"&toPlace={school['latitude']},{school['longitude']}"
            f"&time=2026-04-24T08:00:00Z"
            f"&numItineraries=1"
            f"&mode=WALK"
        )

        ctx = ssl._create_unverified_context()
        motis_req = req.Request(motis_url, headers={
            "Accept": "application/json",
            "User-Agent": "PropertyPulse-School/1.0",
        })
        try:
            resp = req.urlopen(motis_req, timeout=15, context=ctx)
            data = json.loads(resp.read())
        except Exception as e:
            logger.warning("MOTIS walk request failed: %s", e)
            # Fall back to crow-flies estimate
            dist_m = _haversine(from_lat, from_lon, school["latitude"], school["longitude"])
            walk_min = round(dist_m / 80)  # ~80m/min walking speed
            return {
                "urn": urn,
                "walk_minutes": walk_min,
                "distance_m": round(dist_m),
                "source": "estimated",
            }

        itineraries = data.get("direct", []) or data.get("itineraries", [])
        if itineraries:
            best = itineraries[0]
            walk_sec = best.get("duration", 0)
            walk_min = walk_sec // 60 if walk_sec > 60 else max(1, round(walk_sec / 60))
            distance_m = sum(leg.get("distance", 0) for leg in best.get("legs", []))
            return {
                "urn": urn,
                "walk_minutes": walk_min,
                "distance_m": round(distance_m),
                "source": "motis",
                "legs": best.get("legs", []),
            }
        else:
            # No walking route found
            dist_m = _haversine(from_lat, from_lon, school["latitude"], school["longitude"])
            return {
                "urn": urn,
                "walk_minutes": round(dist_m / 80),
                "distance_m": round(dist_m),
                "source": "estimated",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Walk time query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


def _haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in metres between two points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _serialize(row):
    """Convert psycopg2 RealDictRow to JSON-safe dict."""
    if row is None:
        return None
    import datetime
    import decimal
    import uuid
    result = {}
    for k, v in row.items():
        if isinstance(v, decimal.Decimal):
            result[k] = float(v)
        elif isinstance(v, (datetime.date, datetime.datetime)):
            result[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            result[k] = str(v)
        elif isinstance(v, memoryview):
            result[k] = None  # skip binary geometry
        elif k == "geom":
            continue  # skip geometry column
        else:
            result[k] = v
    # Compute Academic Velocity badge from current vs previous year
    result["velocity"] = _compute_velocity(result)
    return result


def _quality_flags(row: dict) -> list[str]:
    """Return list of quality flag strings for a school."""
    flags = []
    type_code = (row.get("type_code") or "").lower()
    if "independent" in type_code:
        # Independent schools may use iGCSEs which aren't counted in A8/P8
        if row.get("attainment_8") is not None or row.get("progress_8") is not None:
            flags.append("igcse_caveat")
    return flags


def _compute_velocity(row: dict) -> str | None:
    """Compute Academic Velocity: 'rising', 'stable', or 'declining'.

    For primary: compare KS2 RWM % (current vs previous year).
    For secondary: compare Progress 8 (current vs previous year).
    Thresholds: >=+3pp (KS2) or >=+0.2 (P8) = rising; <=-3pp or <=-0.2 = declining; else stable.
    """
    phase = row.get("phase")
    if phase == "Primary":
        curr = row.get("ks2_rwm_expected")
        prev = row.get("ks2_prev_rwm")
        if curr is not None and prev is not None:
            diff = curr - prev
            if diff >= 3:
                return "rising"
            elif diff <= -3:
                return "declining"
            return "stable"
    elif phase in ("Secondary", "All-through"):
        # Prefer Progress 8 comparison, but only if values differ (different years)
        curr_p8 = row.get("progress_8")
        prev_p8 = row.get("ks4_prev_p8")
        if curr_p8 is not None and prev_p8 is not None and curr_p8 != prev_p8:
            diff = curr_p8 - prev_p8
            if diff >= 0.2:
                return "rising"
            elif diff <= -0.2:
                return "declining"
            return "stable"
        # Fall back to Attainment 8 (±3 points threshold)
        # ks4_latest_a8 = most recent year, ks4_prev_a8 = second most recent
        curr_a8 = row.get("ks4_latest_a8") or row.get("attainment_8")
        prev_a8 = row.get("ks4_prev_a8")
        if curr_a8 is not None and prev_a8 is not None:
            diff = curr_a8 - prev_a8
            if diff >= 3:
                return "rising"
            elif diff <= -3:
                return "declining"
            return "stable"
    return None


def _compute_velocity_from_results(phase, ks2_results, ks4_results):
    """Compute velocity from multi-year results arrays (for detail endpoint)."""
    if phase == "Primary" and len(ks2_results) >= 2:
        curr = ks2_results[0].get("pct_rwm_expected")
        prev = ks2_results[1].get("pct_rwm_expected")
        if curr is not None and prev is not None:
            diff = curr - prev
            if diff >= 3:
                return "rising"
            elif diff <= -3:
                return "declining"
            return "stable"
    elif phase in ("Secondary", "All-through") and len(ks4_results) >= 2:
        # Prefer Progress 8
        curr_p8 = ks4_results[0].get("progress_8")
        prev_p8 = ks4_results[1].get("progress_8")
        if curr_p8 is not None and prev_p8 is not None:
            diff = curr_p8 - prev_p8
            if diff >= 0.2:
                return "rising"
            elif diff <= -0.2:
                return "declining"
            return "stable"
        # Fall back to Attainment 8
        curr_a8 = ks4_results[0].get("attainment_8")
        prev_a8 = ks4_results[1].get("attainment_8")
        if curr_a8 is not None and prev_a8 is not None:
            diff = curr_a8 - prev_a8
            if diff >= 3:
                return "rising"
            elif diff <= -3:
                return "declining"
            return "stable"
    return None


# ── School Catchment ────────────────────────────────────────────────
@router.get("/{urn}/catchment")
def school_catchment(urn: int):
    """Return catchment probability map for a school (LSOAs with admission probability)."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT lsoa_code, distance_m, admission_probability, is_within_ldo
                FROM schools.catchment_model
                WHERE urn = %(urn)s
                ORDER BY admission_probability DESC
            """, {"urn": urn})
            rows = [_serialize(r) for r in cur.fetchall()]
            return {"urn": urn, "catchment": rows, "count": len(rows)}
    except Exception as e:
        logger.exception("School catchment failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


# ── Feeder Schools ──────────────────────────────────────────────────
@router.get("/{urn}/feeders")
def feeder_schools(urn: int):
    """Infer feeder/destination schools based on catchment overlap."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get this school's phase
            cur.execute("SELECT phase FROM schools.institutions WHERE urn = %(urn)s", {"urn": urn})
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, f"School {urn} not found")

            phase = row["phase"]

            # For secondary schools: find primary schools whose catchment overlaps
            # For primary schools: find secondary schools whose catchment overlaps
            if phase == "Secondary" or phase == "All-through":
                target_phase = "Primary"
            elif phase == "Primary":
                target_phase = "Secondary"
            else:
                return {"urn": urn, "feeders": [], "destinations": []}

            # Find schools that share catchment LSOAs with this school
            cur.execute("""
                SELECT
                    i.urn, i.name, i.phase, i.type_code,
                    COUNT(DISTINCT c2.lsoa_code) AS shared_lsoas,
                    AVG(c1.admission_probability * c2.admission_probability) AS overlap_score,
                    insp.overall_rating AS ofsted_rating
                FROM schools.catchment_model c1
                JOIN schools.catchment_model c2 ON c2.lsoa_code = c1.lsoa_code AND c2.urn != c1.urn
                JOIN schools.institutions i ON i.urn = c2.urn AND i.phase = %(target_phase)s AND i.is_open = true
                LEFT JOIN LATERAL (
                    SELECT overall_rating
                    FROM schools.inspections
                    WHERE urn = i.urn AND inspection_body = 'Ofsted'
                    ORDER BY inspection_date DESC LIMIT 1
                ) insp ON true
                WHERE c1.urn = %(urn)s
                  AND c1.admission_probability > 0.05
                  AND c2.admission_probability > 0.05
                GROUP BY i.urn, i.name, i.phase, i.type_code, insp.overall_rating
                HAVING COUNT(DISTINCT c2.lsoa_code) >= 2
                ORDER BY overlap_score DESC
                LIMIT 10
            """, {"urn": urn, "target_phase": target_phase})
            rows = [_serialize(r) for r in cur.fetchall()]

            result = {"urn": urn}
            if phase in ("Secondary", "All-through"):
                result["feeder_primaries"] = rows
            else:
                result["destination_secondaries"] = rows
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Feeder schools query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)
