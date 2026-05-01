#!/usr/bin/env python3
"""
D35 — LA Admissions Booklet Scraper (schema-forward, school-by-school)

Downloads PDF booklets from the LA admissions catalogue, extracts per-school
admissions data, and saves structured JSON output with confidence scoring
and full provenance.

Usage:
    python3 scrape_all.py                    # scrape all LAs with PDF URLs
    python3 scrape_all.py --la 306           # scrape single LA by code
    python3 scrape_all.py --tier 1           # scrape Tier 1 LAs only
    python3 scrape_all.py --resume           # skip already-scraped LAs

Output structure:
    output/
      {la_code}_{la_name_slug}/
        secondary.json          # per-school extraction
        primary.json
        metadata.json           # provenance, confidence, field coverage
        raw_text/               # full page text dumps for debugging
      master_combined.json      # all LAs combined
      field_coverage.csv        # which fields exist across which LAs
      scrape_log.jsonl          # append-only log of every scrape attempt
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pdfplumber
import requests

# ─── Config ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
CATALOGUE_PATH = PROJECT_ROOT / "etl" / "data" / "la_admissions_catalogue.csv"
OUTPUT_DIR = SCRIPT_DIR / "output"
PDF_DIR = SCRIPT_DIR / "pdfs"
LOG_PATH = SCRIPT_DIR / "output" / "scrape_log.jsonl"
MASTER_PATH = SCRIPT_DIR / "output" / "master_combined.json"
COVERAGE_PATH = SCRIPT_DIR / "output" / "field_coverage.csv"

# Tier 1 LAs — top 30-40 by school-age population (London boroughs + major cities)
TIER_1_CODES = {
    # Inner London
    "201", "202", "203", "204", "205", "206", "207", "208", "209",
    "210", "211", "212", "213",
    # Outer London
    "301", "302", "303", "304", "305", "306", "307", "308", "309",
    "310", "311", "312", "313", "314", "315", "316", "317", "318",
    "319", "320",
    # Major cities / metros
    "330", "331", "332", "334", "335", "336",  # West Midlands
    "340", "341", "342", "343", "344",          # Merseyside
    "350", "351", "352", "353", "354", "355", "356", "357", "358", "359",  # Greater Manchester
    "370", "371", "372", "373",                  # South Yorkshire
    "380", "381", "382", "383", "384",           # West Yorkshire
    "886", "936", "935",                         # Kent, Essex, Surrey
}

# HTTP session with retries
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PropertyPulse-Admissions-Scraper/1.0 (research; contact@simusimi.com)"
})

# Known extraction fields — the superset schema. New fields discovered during
# scraping get appended here and logged.
KNOWN_SCHOOL_FIELDS = [
    "la_code", "la_name", "phase", "admissions_year",
    "dfe_number", "urn", "school_name", "school_type",
    "pan", "applications_received",
    "first_preference", "second_preference", "third_preference",
    "offers_made", "pct_first_choice",
    "oversubscription_ratio",
    "allocation_breakdown",  # dict of {criterion: count}
    "furthest_distance_miles", "furthest_distance_km",
    "distance_method",  # "straight_line" | "walking" | "unknown"
    "sif_required",
    "open_day_dates",   # list of {date, time, booking_url}
    "sen_places",
    "waiting_list_info",
    "neighbouring_la_schools",  # list of {name, la_name}
    "in_year_process",  # prose summary
    "special_schools",  # list of {name, specialism, age_range, address}
    "elp_provisions",   # list of {school, unit_name, specialism, places}
]

# All allocation criteria we've seen across any LA
KNOWN_CRITERIA = {
    "LAC", "Medical/Social", "Feeder", "Feeder/Siblings",
    "Staff Child", "Ability/Aptitude", "Banding", "Faith",
    "Faith Siblings", "Siblings", "Open Places", "Open Places Siblings",
    "Non-Faith/Distance", "SEN", "Distance", "Catchment",
    "Catchment Siblings", "Pupil Premium", "Service Children",
    "Music Aptitude", "Random Allocation", "Named on EHCP",
}

# Fields discovered during THIS run (not in KNOWN_SCHOOL_FIELDS)
DISCOVERED_FIELDS: set = set()
DISCOVERED_CRITERIA: set = set()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def log_event(event: dict):
    """Append a JSON line to the scrape log."""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def download_pdf(url: str, dest: Path, la_code: str) -> bool:
    """Download a PDF. Returns True if successful."""
    if dest.exists() and dest.stat().st_size > 1000:
        return True  # already downloaded

    try:
        resp = SESSION.get(url, timeout=60, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type and len(resp.content) < 50000:
            log_event({"event": "download_skip_html", "la_code": la_code,
                       "url": url, "content_type": content_type})
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(resp.content)

        if dest.stat().st_size < 5000:
            log_event({"event": "download_too_small", "la_code": la_code,
                       "url": url, "size": dest.stat().st_size})
            dest.unlink()
            return False

        return True

    except Exception as e:
        log_event({"event": "download_error", "la_code": la_code,
                   "url": url, "error": str(e)})
        return False


# ─── Generic PDF Extractor ───────────────────────────────────────────────────

def extract_all_text(pdf_path: Path) -> list[dict]:
    """Extract text from every page. Returns list of {page_num, text, tables}."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages.append({
                "page_num": i + 1,
                "text": text,
                "tables": tables,
                "width": page.width,
                "height": page.height,
            })
    return pages


def find_school_table_pages(pages: list[dict]) -> list[int]:
    """Find pages likely containing school listing tables with PAN/applications."""
    candidates = []
    for p in pages:
        text_lower = p["text"].lower()
        # Look for keywords indicating school listing tables
        score = 0
        if "admission number" in text_lower or "pan" in text_lower or "published admission" in text_lower:
            score += 3
        if "application" in text_lower and ("received" in text_lower or "made" in text_lower):
            score += 2
        if "oversubscri" in text_lower:
            score += 2
        if "allocation" in text_lower:
            score += 2
        if "furthest distance" in text_lower or "last distance" in text_lower:
            score += 3
        if "criterion" in text_lower or "criteria" in text_lower:
            score += 2
        # Tables present
        if p["tables"]:
            score += 1
        if score >= 3:
            candidates.append(p["page_num"])
    return candidates


def find_distance_method(pages: list[dict]) -> str:
    """Detect distance measurement method from policy text."""
    for p in pages:
        text_lower = p["text"].lower()
        if "straight line" in text_lower or "straight-line" in text_lower or "as the crow flies" in text_lower:
            return "straight_line"
        if "walking distance" in text_lower or "shortest walking" in text_lower or "walking route" in text_lower:
            return "walking"
        if "road distance" in text_lower or "shortest route" in text_lower:
            return "walking"  # road distance = walking route typically
    return "unknown"


def find_in_year_process(pages: list[dict]) -> str | None:
    """Extract in-year admissions process summary."""
    for p in pages:
        text_lower = p["text"].lower()
        if "in-year" in text_lower or "in year" in text_lower:
            # Grab the paragraph
            lines = p["text"].split("\n")
            in_year_lines = []
            capturing = False
            for line in lines:
                if "in-year" in line.lower() or "in year" in line.lower():
                    capturing = True
                if capturing:
                    in_year_lines.append(line.strip())
                    if len(in_year_lines) > 5:
                        break
                    if not line.strip():
                        break
            if in_year_lines:
                return " ".join(in_year_lines).strip()[:500]
    return None


def find_special_schools(pages: list[dict]) -> list[dict]:
    """Extract special school directory from SEND sections."""
    specials = []
    for p in pages:
        text_lower = p["text"].lower()
        if "special school" not in text_lower and "special educational" not in text_lower:
            continue
        # Try tables first
        for table in p["tables"]:
            if not table or len(table) < 2:
                continue
            header = [str(c).lower() if c else "" for c in table[0]]
            if any("school" in h or "name" in h for h in header):
                for row in table[1:]:
                    if row and row[0] and len(str(row[0]).strip()) > 3:
                        specials.append({
                            "name": str(row[0]).strip(),
                            "specialism": str(row[1]).strip() if len(row) > 1 and row[1] else None,
                            "age_range": str(row[2]).strip() if len(row) > 2 and row[2] else None,
                        })
    return specials


def find_elp_provisions(pages: list[dict]) -> list[dict]:
    """Extract Enhanced Learning Provisions from SEND sections."""
    elps = []
    for p in pages:
        text_lower = p["text"].lower()
        if "enhanced learning" not in text_lower and "additionally resourced" not in text_lower and "specialist resource" not in text_lower:
            continue
        for table in p["tables"]:
            if not table or len(table) < 2:
                continue
            header = [str(c).lower() if c else "" for c in table[0]]
            if any("school" in h or "provision" in h or "unit" in h for h in header):
                for row in table[1:]:
                    if row and row[0] and len(str(row[0]).strip()) > 3:
                        elps.append({
                            "school": str(row[0]).strip(),
                            "unit_name": str(row[1]).strip() if len(row) > 1 and row[1] else None,
                            "specialism": str(row[2]).strip() if len(row) > 2 and row[2] else None,
                            "places": _parse_int(str(row[3])) if len(row) > 3 and row[3] else None,
                        })
    return elps


def _parse_int(s: str) -> int | None:
    """Parse a string to int, returning None on failure."""
    if not s:
        return None
    s = s.strip().replace(",", "").replace(" ", "")
    if s in ("N/A", "n/a", "-", "—", "–", ""):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _parse_float(s: str) -> float | None:
    """Parse a string to float, returning None on failure."""
    if not s:
        return None
    s = s.strip().replace(",", "").replace(" ", "")
    if s in ("N/A", "n/a", "-", "—", "–", ""):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def extract_schools_from_tables(pages: list[dict], la_code: str, la_name: str,
                                 phase: str) -> list[dict]:
    """
    Generic table extractor: find tables with school names + numeric columns,
    map columns to known fields by header text.
    """
    schools = []
    table_pages = find_school_table_pages(pages)

    for page_num in table_pages:
        page = pages[page_num - 1]  # 0-indexed
        for table in page["tables"]:
            if not table or len(table) < 2:
                continue

            # Parse header row
            header = [str(c).strip() if c else "" for c in table[0]]
            header_lower = [h.lower() for h in header]

            # Must have a school name column
            name_col = None
            for i, h in enumerate(header_lower):
                if "school" in h or "name" in h or "academy" in h:
                    name_col = i
                    break
            if name_col is None:
                # Try first column if it has text values
                if len(table) > 1 and table[1] and table[1][0] and len(str(table[1][0])) > 5:
                    name_col = 0
                else:
                    continue

            # Map other columns
            col_map = {}
            for i, h in enumerate(header_lower):
                if i == name_col:
                    continue
                if "pan" in h or "admission number" in h or "published" in h:
                    col_map["pan"] = i
                elif "application" in h and ("1st" in h or "first" in h):
                    col_map["first_preference"] = i
                elif "application" in h and ("2nd" in h or "second" in h):
                    col_map["second_preference"] = i
                elif "application" in h and ("3rd" in h or "third" in h):
                    col_map["third_preference"] = i
                elif "application" in h or "apps" in h:
                    col_map["applications_received"] = i
                elif "offer" in h:
                    col_map["offers_made"] = i
                elif "distance" in h or "ldo" in h or "furthest" in h:
                    col_map["furthest_distance"] = i
                elif "dfe" in h or "dfes" in h or "laestab" in h:
                    col_map["dfe_number"] = i
                elif "type" in h and "school" not in h:
                    col_map["school_type"] = i
                elif "sif" in h or "supplementary" in h:
                    col_map["sif_required"] = i
                elif "waiting" in h:
                    col_map["waiting_list_info"] = i
                elif "preference" in h and "%" in h:
                    col_map["pct_first_choice"] = i
                else:
                    # Unknown column — log it
                    if h and h not in ("", "notes", "address", "telephone", "phone",
                                       "website", "headteacher", "head", "postcode",
                                       "email", "tel", "age range", "age", "gender",
                                       "uniform", "status"):
                        # Might be a new field worth tracking
                        field_name = re.sub(r'[^a-z0-9_]+', '_', h).strip('_')
                        if field_name and field_name not in KNOWN_SCHOOL_FIELDS:
                            DISCOVERED_FIELDS.add(f"{la_code}:{field_name}:{h}")

            # Extract rows
            for row in table[1:]:
                if not row or not row[name_col]:
                    continue
                school_name = str(row[name_col]).strip()
                if len(school_name) < 3 or school_name.lower() in ("total", "totals", "all", ""):
                    continue

                school = {
                    "la_code": la_code,
                    "la_name": la_name,
                    "phase": phase,
                    "school_name": school_name,
                }

                for field, col_idx in col_map.items():
                    if col_idx < len(row) and row[col_idx]:
                        val = str(row[col_idx]).strip()
                        if field in ("pan", "applications_received", "first_preference",
                                     "second_preference", "third_preference", "offers_made",
                                     "sen_places"):
                            school[field] = _parse_int(val)
                        elif field in ("furthest_distance", "pct_first_choice"):
                            school[field] = _parse_float(val)
                        elif field == "sif_required":
                            school[field] = val.lower() in ("yes", "y", "true", "✓", "✔")
                        else:
                            school[field] = val

                # Derive oversubscription ratio
                pan = school.get("pan")
                apps = school.get("applications_received")
                if pan and apps and pan > 0:
                    school["oversubscription_ratio"] = round(apps / pan, 2)

                # Handle furthest_distance → separate miles/km field
                fd = school.pop("furthest_distance", None)
                if fd is not None:
                    school["furthest_distance_miles"] = fd  # assume miles unless text says km

                schools.append(school)

    return schools


def extract_allocation_from_tables(pages: list[dict], school_names: list[str]) -> dict:
    """
    Try to extract allocation breakdown tables. Returns {school_name: {criterion: count}}.
    This is harder — allocation tables vary wildly per LA.
    """
    allocations = {}

    for p in pages:
        text_lower = p["text"].lower()
        if "allocation" not in text_lower and "criterion" not in text_lower:
            continue

        for table in p["tables"]:
            if not table or len(table) < 2:
                continue
            header = [str(c).strip() if c else "" for c in table[0]]
            header_lower = [h.lower() for h in header]

            # Check if this table has school names as columns or rows
            # Pattern 1: schools as columns, criteria as rows
            school_cols = {}
            for i, h in enumerate(header):
                for sn in school_names:
                    if sn.lower() in h.lower() or h.lower() in sn.lower():
                        school_cols[i] = sn
                        break

            if school_cols:
                # Criteria as rows
                for row in table[1:]:
                    if not row or not row[0]:
                        continue
                    criterion = str(row[0]).strip()
                    for col_idx, school_name in school_cols.items():
                        if col_idx < len(row) and row[col_idx]:
                            val = _parse_int(str(row[col_idx]))
                            if val is not None:
                                if school_name not in allocations:
                                    allocations[school_name] = {}
                                allocations[school_name][criterion] = val
                                # Track new criteria
                                if criterion not in KNOWN_CRITERIA:
                                    DISCOVERED_CRITERIA.add(f"{criterion}")

            # Pattern 2: schools as rows, criteria as columns
            else:
                crit_cols = {}
                for i, h in enumerate(header_lower):
                    if any(k in h for k in ["lac", "sibling", "distance", "faith",
                                            "catchment", "feeder", "medical",
                                            "banding", "ability", "open", "sen",
                                            "pupil premium", "random"]):
                        crit_cols[i] = header[i]

                if crit_cols:
                    for row in table[1:]:
                        if not row or not row[0]:
                            continue
                        school_name = str(row[0]).strip()
                        if len(school_name) < 3:
                            continue
                        alloc = {}
                        for col_idx, criterion in crit_cols.items():
                            if col_idx < len(row) and row[col_idx]:
                                val = _parse_int(str(row[col_idx]))
                                if val is not None:
                                    alloc[criterion] = val
                                    if criterion not in KNOWN_CRITERIA:
                                        DISCOVERED_CRITERIA.add(criterion)
                        if alloc:
                            allocations[school_name] = alloc

    return allocations


def assess_confidence(schools: list[dict], pages: list[dict],
                      la_code: str, pdf_path: Path) -> dict:
    """
    Assess extraction confidence for this LA booklet.
    Returns confidence metadata.
    """
    total_pages = len(pages)
    total_text_chars = sum(len(p["text"]) for p in pages)
    total_tables = sum(len(p["tables"]) for p in pages)
    has_pan = sum(1 for s in schools if s.get("pan"))
    has_apps = sum(1 for s in schools if s.get("applications_received"))
    has_ldo = sum(1 for s in schools if s.get("furthest_distance_miles"))
    has_alloc = sum(1 for s in schools if s.get("allocation_breakdown"))
    n = len(schools)

    # Confidence scoring
    score = 0
    max_score = 100
    reasons = []

    if n == 0:
        return {
            "confidence_score": 0,
            "confidence_level": "FAILED",
            "reasons": ["No schools extracted"],
            "schools_extracted": 0,
            "total_pages": total_pages,
            "total_text_chars": total_text_chars,
            "total_tables": total_tables,
        }

    # Schools found (0-30 points)
    if n >= 5:
        score += 30
        reasons.append(f"{n} schools found")
    elif n >= 1:
        score += 15
        reasons.append(f"Only {n} school(s) found (may be incomplete)")

    # PAN coverage (0-20 points)
    if n > 0 and has_pan / n >= 0.8:
        score += 20
        reasons.append(f"PAN: {has_pan}/{n}")
    elif has_pan > 0:
        score += 10
        reasons.append(f"PAN partial: {has_pan}/{n}")
    else:
        reasons.append("No PAN data extracted")

    # Applications coverage (0-15 points)
    if n > 0 and has_apps / n >= 0.5:
        score += 15
        reasons.append(f"Applications: {has_apps}/{n}")
    elif has_apps > 0:
        score += 7
        reasons.append(f"Applications partial: {has_apps}/{n}")

    # LDO (0-15 points)
    if has_ldo > 0:
        score += 15
        reasons.append(f"LDO: {has_ldo}/{n}")
    else:
        reasons.append("No LDO data found")

    # Allocation breakdown (0-20 points)
    if has_alloc > 0 and n > 0 and has_alloc / n >= 0.5:
        score += 20
        reasons.append(f"Allocation breakdown: {has_alloc}/{n}")
    elif has_alloc > 0:
        score += 10
        reasons.append(f"Allocation partial: {has_alloc}/{n}")
    else:
        reasons.append("No allocation breakdown found")

    # Confidence level
    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    elif score >= 15:
        level = "LOW"
    else:
        level = "VERY_LOW"

    return {
        "confidence_score": score,
        "confidence_level": level,
        "reasons": reasons,
        "schools_extracted": n,
        "has_pan": has_pan,
        "has_applications": has_apps,
        "has_ldo": has_ldo,
        "has_allocation": has_alloc,
        "total_pages": total_pages,
        "total_text_chars": total_text_chars,
        "total_tables": total_tables,
    }


# ─── Open Days Extraction ───────────────────────────────────────────────────

def find_open_days(pages: list[dict], school_names: list[str]) -> dict:
    """Extract open day/evening dates. Returns {school_name: [{date, time, type}]}."""
    open_days = {}
    date_re = re.compile(
        r'(\d{1,2})\s*(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s*(\d{4})?',
        re.IGNORECASE
    )
    time_re = re.compile(r'(\d{1,2}[.:]\d{2}\s*(?:am|pm|noon)?)', re.IGNORECASE)

    for p in pages:
        text_lower = p["text"].lower()
        if "open day" not in text_lower and "open evening" not in text_lower and "open event" not in text_lower:
            continue

        # Try tables first
        for table in p["tables"]:
            if not table or len(table) < 2:
                continue
            header_lower = [str(c).lower() if c else "" for c in table[0]]
            if any("open" in h or "event" in h or "date" in h for h in header_lower):
                name_col = None
                date_col = None
                time_col = None
                for i, h in enumerate(header_lower):
                    if "school" in h or "name" in h:
                        name_col = i
                    elif "date" in h:
                        date_col = i
                    elif "time" in h:
                        time_col = i

                if name_col is not None:
                    for row in table[1:]:
                        if not row or not row[name_col]:
                            continue
                        sn = str(row[name_col]).strip()
                        entry = {"date": None, "time": None, "type": "open_day"}
                        if date_col and date_col < len(row) and row[date_col]:
                            entry["date"] = str(row[date_col]).strip()
                        if time_col and time_col < len(row) and row[time_col]:
                            entry["time"] = str(row[time_col]).strip()
                        if sn not in open_days:
                            open_days[sn] = []
                        open_days[sn].append(entry)

        # Text-based extraction as fallback
        lines = p["text"].split("\n")
        current_school = None
        for line in lines:
            line_stripped = line.strip()
            # Check if this line mentions a school name
            for sn in school_names:
                if sn.lower() in line_stripped.lower():
                    current_school = sn
                    break
            # Check for dates
            if current_school:
                dm = date_re.search(line_stripped)
                tm = time_re.search(line_stripped)
                if dm:
                    entry = {
                        "date": dm.group(0),
                        "time": tm.group(1) if tm else None,
                        "type": "open_evening" if "evening" in line_stripped.lower() else "open_day",
                    }
                    if current_school not in open_days:
                        open_days[current_school] = []
                    open_days[current_school].append(entry)

    return open_days


# ─── Main Scrape Pipeline ───────────────────────────────────────────────────

def scrape_single_booklet(pdf_path: Path, la_code: str, la_name: str,
                           phase: str, source_url: str) -> dict:
    """
    Scrape a single PDF booklet. Returns structured output dict.
    """
    pages = extract_all_text(pdf_path)

    # Extract schools from tables
    schools = extract_schools_from_tables(pages, la_code, la_name, phase)

    # Detect distance method
    dist_method = find_distance_method(pages)
    for s in schools:
        s["distance_method"] = dist_method

    # Extract allocation breakdowns
    school_names = [s["school_name"] for s in schools]
    allocations = extract_allocation_from_tables(pages, school_names)
    for s in schools:
        if s["school_name"] in allocations:
            s["allocation_breakdown"] = allocations[s["school_name"]]

    # Extract open days
    open_days = find_open_days(pages, school_names)
    for s in schools:
        if s["school_name"] in open_days:
            s["open_day_dates"] = open_days[s["school_name"]]

    # Extract SEND info
    special_schools = find_special_schools(pages)
    elp_provisions = find_elp_provisions(pages)

    # In-year process
    in_year = find_in_year_process(pages)

    # Confidence assessment
    confidence = assess_confidence(schools, pages, la_code, pdf_path)

    # Provenance
    provenance = {
        "source_url": source_url,
        "source_file_hash": file_hash(pdf_path),
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "parser_version": "2.0.0",
        "extraction_method": "pdfplumber_generic_table_parser",
        "pdf_pages": len(pages),
    }

    # Save raw text for debugging
    raw_text_dir = OUTPUT_DIR / f"{la_code}_{slugify(la_name)}" / "raw_text"
    raw_text_dir.mkdir(parents=True, exist_ok=True)
    for p in pages:
        with open(raw_text_dir / f"page_{p['page_num']:03d}.txt", "w") as f:
            f.write(p["text"])

    return {
        "la_code": la_code,
        "la_name": la_name,
        "phase": phase,
        "schools": schools,
        "special_schools": special_schools,
        "elp_provisions": elp_provisions,
        "in_year_process": in_year,
        "confidence": confidence,
        "provenance": provenance,
    }


def scrape_la(row: dict, resume: bool = False) -> dict:
    """
    Scrape all booklets for a single LA. Returns combined result.
    """
    la_code = row["la_code"]
    la_name = row["la_name"]
    la_slug = slugify(la_name)
    la_dir = OUTPUT_DIR / f"{la_code}_{la_slug}"

    # Resume check
    metadata_path = la_dir / "metadata.json"
    if resume and metadata_path.exists():
        print(f"  ⏭  {la_code} {la_name} — already scraped, skipping")
        with open(metadata_path) as f:
            return json.load(f)

    results = {"la_code": la_code, "la_name": la_name, "phases": {}}

    for phase, url_key in [("secondary", "secondary_url"), ("primary", "primary_url"),
                            ("junior", "junior_url")]:
        url = row.get(url_key, "").strip()
        if not url:
            continue

        # Check if it's HTML-only (no PDF)
        parsed = urlparse(url)
        is_likely_html = (not parsed.path.endswith(".pdf") and
                         not parsed.path.endswith("/pdf/") and
                         "download" not in parsed.path.lower())

        pdf_filename = f"{la_code}_{la_slug}_{phase}.pdf"
        pdf_path = PDF_DIR / pdf_filename

        # Download
        print(f"  📥 {phase}: downloading...")
        if not download_pdf(url, pdf_path, la_code):
            log_event({"event": "download_failed", "la_code": la_code,
                       "phase": phase, "url": url,
                       "note": "HTML page or download failed"})
            results["phases"][phase] = {
                "status": "download_failed",
                "url": url,
                "is_html_page": is_likely_html,
            }
            continue

        # Verify it's actually a PDF
        try:
            with open(pdf_path, "rb") as f:
                magic = f.read(5)
            if magic != b"%PDF-":
                log_event({"event": "not_pdf", "la_code": la_code,
                           "phase": phase, "magic": magic.decode("ascii", errors="replace")})
                results["phases"][phase] = {
                    "status": "not_pdf",
                    "url": url,
                }
                pdf_path.unlink(missing_ok=True)
                continue
        except Exception:
            pass

        # Extract
        print(f"  🔍 {phase}: extracting...")
        try:
            result = scrape_single_booklet(pdf_path, la_code, la_name, phase, url)
            results["phases"][phase] = result

            # Save per-phase JSON
            la_dir.mkdir(parents=True, exist_ok=True)
            with open(la_dir / f"{phase}.json", "w") as f:
                json.dump(result, f, indent=2, default=str)

            conf = result["confidence"]
            print(f"  ✅ {phase}: {conf['schools_extracted']} schools, "
                  f"confidence={conf['confidence_level']} ({conf['confidence_score']}/100)")

            log_event({
                "event": "extraction_complete",
                "la_code": la_code,
                "phase": phase,
                "schools": conf["schools_extracted"],
                "confidence_score": conf["confidence_score"],
                "confidence_level": conf["confidence_level"],
            })

        except Exception as e:
            tb = traceback.format_exc()
            print(f"  ❌ {phase}: extraction error — {e}")
            log_event({
                "event": "extraction_error",
                "la_code": la_code,
                "phase": phase,
                "error": str(e),
                "traceback": tb,
            })
            results["phases"][phase] = {
                "status": "extraction_error",
                "error": str(e),
                "url": url,
            }

    # Save metadata
    la_dir.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


def load_catalogue() -> list[dict]:
    """Load the LA admissions catalogue CSV."""
    rows = []
    with open(CATALOGUE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def build_field_coverage(all_results: list[dict]):
    """Build a field coverage matrix CSV."""
    # Collect all fields seen per LA
    field_set = set()
    la_fields = {}

    for r in all_results:
        la_key = f"{r['la_code']}_{r['la_name']}"
        la_fields[la_key] = set()
        for phase, phase_data in r.get("phases", {}).items():
            if isinstance(phase_data, dict) and "schools" in phase_data:
                for school in phase_data["schools"]:
                    for field, val in school.items():
                        if val is not None and val != "" and field not in ("la_code", "la_name", "phase"):
                            field_set.add(field)
                            la_fields[la_key].add(field)

    # Write CSV
    fields = sorted(field_set)
    with open(COVERAGE_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["la"] + fields)
        for la_key in sorted(la_fields.keys()):
            row = [la_key] + ["✓" if field in la_fields[la_key] else "" for field in fields]
            writer.writerow(row)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="D35 LA Admissions Booklet Scraper")
    parser.add_argument("--la", help="Scrape single LA by code (e.g., 306)")
    parser.add_argument("--tier", type=int, help="Scrape tier (1 = top LAs)")
    parser.add_argument("--resume", action="store_true", help="Skip already-scraped LAs")
    parser.add_argument("--dry-run", action="store_true", help="List LAs without scraping")
    args = parser.parse_args()

    catalogue = load_catalogue()
    print(f"Loaded {len(catalogue)} LAs from catalogue")

    # Filter
    if args.la:
        catalogue = [r for r in catalogue if r["la_code"] == args.la]
    elif args.tier == 1:
        catalogue = [r for r in catalogue if r["la_code"] in TIER_1_CODES]

    # Filter to LAs that have at least one PDF URL
    has_pdf = []
    html_only = []
    for r in catalogue:
        urls = [r.get("secondary_url", ""), r.get("primary_url", ""), r.get("junior_url", "")]
        pdf_urls = [u for u in urls if u.strip() and
                    (u.strip().endswith(".pdf") or "download" in u.lower()
                     or "asset" in u.lower() or "media" in u.lower()
                     or "document" in u.lower() or "file" in u.lower())]
        if pdf_urls:
            has_pdf.append(r)
        elif any(u.strip() for u in urls):
            html_only.append(r)

    print(f"LAs with PDF URLs: {len(has_pdf)}")
    print(f"LAs with HTML-only: {len(html_only)}")

    if args.dry_run:
        print("\n--- PDF LAs ---")
        for r in has_pdf:
            print(f"  {r['la_code']} {r['la_name']}")
        print("\n--- HTML-only LAs ---")
        for r in html_only:
            print(f"  {r['la_code']} {r['la_name']}")
        return

    # Scrape
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results = []

    print(f"\n{'='*80}")
    print(f"Starting scrape of {len(has_pdf)} LAs with PDF booklets")
    print(f"{'='*80}\n")

    for i, row in enumerate(has_pdf):
        la_code = row["la_code"]
        la_name = row["la_name"]
        print(f"\n[{i+1}/{len(has_pdf)}] {la_code} {la_name}")
        print(f"{'─'*60}")

        try:
            result = scrape_la(row, resume=args.resume)
            all_results.append(result)
        except Exception as e:
            print(f"  ❌ FATAL: {e}")
            log_event({"event": "la_fatal_error", "la_code": la_code, "error": str(e),
                       "traceback": traceback.format_exc()})
            all_results.append({"la_code": la_code, "la_name": la_name, "phases": {},
                                "error": str(e)})

        # Rate limit — be polite to council servers
        time.sleep(2)

    # Save master combined
    with open(MASTER_PATH, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Build field coverage
    build_field_coverage(all_results)

    # Summary
    print(f"\n{'='*80}")
    print("SCRAPE COMPLETE — SUMMARY")
    print(f"{'='*80}\n")

    total_schools = 0
    by_confidence = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "VERY_LOW": 0, "FAILED": 0}

    for r in all_results:
        for phase, phase_data in r.get("phases", {}).items():
            if isinstance(phase_data, dict) and "confidence" in phase_data:
                conf = phase_data["confidence"]
                total_schools += conf.get("schools_extracted", 0)
                level = conf.get("confidence_level", "FAILED")
                by_confidence[level] = by_confidence.get(level, 0) + 1

    print(f"Total LAs scraped: {len(all_results)}")
    print(f"Total schools extracted: {total_schools}")
    print(f"\nConfidence distribution:")
    for level, count in sorted(by_confidence.items()):
        print(f"  {level}: {count}")

    if DISCOVERED_FIELDS:
        print(f"\n🆕 New fields discovered ({len(DISCOVERED_FIELDS)}):")
        for f in sorted(DISCOVERED_FIELDS):
            print(f"  {f}")

    if DISCOVERED_CRITERIA:
        print(f"\n🆕 New allocation criteria discovered ({len(DISCOVERED_CRITERIA)}):")
        for c in sorted(DISCOVERED_CRITERIA):
            print(f"  {c}")

    print(f"\nOutputs:")
    print(f"  Master JSON: {MASTER_PATH}")
    print(f"  Field coverage: {COVERAGE_PATH}")
    print(f"  Scrape log: {LOG_PATH}")
    print(f"  Per-LA output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
