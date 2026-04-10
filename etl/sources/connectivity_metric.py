"""
sources/connectivity_metric.py — DfT Transport Connectivity Metric 2025 → core_connectivity_lsoa

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_connectivity_lsoa)

Data file required in etl/data/ (or set env var to override):
    CONNECTIVITY_METRIC_PATH — connectivity_metrics_2025.ods

If the file is missing locally, this source will download the official ODS workbook from
GOV.UK and cache it in etl/data/ for repeatable subsequent runs.
"""

import os
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES


METADATA = {
    "name": "connectivity_metric",
    "description": "DfT Transport Connectivity Metric 2025 ODS → core_connectivity_lsoa (England LSOAs).",
    "schedule": SCHEDULE_ANNUAL,
    "depends_on": [],
    "tables_written": [TABLE_NAMES["connectivity_lsoa"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (30_000, 36_000),
}


DATA_URL = "https://assets.publishing.service.gov.uk/media/68c966fc07d9e92bc5517b80/connectivity_metrics_2025.ods"
DATA_FILENAME = "connectivity_metrics_2025.ods"
SOURCE_RELEASE = "DfT Transport Connectivity Metric 2025"

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
TABLE = f"{{{NS['table']}}}table"
ROW = f"{{{NS['table']}}}table-row"
CELL = f"{{{NS['table']}}}table-cell"
P = f"{{{NS['text']}}}p"
TABLE_NAME = f"{{{NS['table']}}}name"
ROW_REPEAT = f"{{{NS['table']}}}number-rows-repeated"
COL_REPEAT = f"{{{NS['table']}}}number-columns-repeated"

COLUMN_MAP = {
    "LSOA21CD": "lsoa_code",
    "Overall": "overall_score",
    "Overall (walking)": "overall_walking",
    "Overall (cycling)": "overall_cycling",
    "Overall (public transport)": "overall_public_transport",
    "Overall (driving)": "overall_driving",
    "Employment (overall)": "employment_overall",
    "Education (overall)": "education_overall",
    "Healthcare (overall)": "healthcare_overall",
    "Leisure and Community (overall)": "leisure_community_overall",
    "Shopping (overall)": "shopping_overall",
    "Residential (overall)": "residential_overall",
    "Business (public transport)": "business_public_transport",
    "Education (public transport)": "education_public_transport",
    "Healthcare (public transport)": "healthcare_public_transport",
    "Leisure and Community (public transport)": "leisure_community_public_transport",
    "Shopping (public transport)": "shopping_public_transport",
    "Residential (public transport)": "residential_public_transport",
}

INSERT_COLUMNS = [
    "lsoa_code",
    "overall_score",
    "overall_walking",
    "overall_cycling",
    "overall_public_transport",
    "overall_driving",
    "employment_overall",
    "education_overall",
    "healthcare_overall",
    "leisure_community_overall",
    "shopping_overall",
    "residential_overall",
    "business_public_transport",
    "education_public_transport",
    "healthcare_public_transport",
    "leisure_community_public_transport",
    "shopping_public_transport",
    "residential_public_transport",
    "source_release",
]


def _resolve_data_path() -> str:
    path = os.environ.get("CONNECTIVITY_METRIC_PATH")
    if path and os.path.exists(path):
        return path

    os.makedirs(_ETL_DATA_DIR, exist_ok=True)
    candidate = os.path.join(_ETL_DATA_DIR, DATA_FILENAME)
    if os.path.exists(candidate):
        return candidate

    print(f"  Downloading connectivity metric workbook from {DATA_URL}", flush=True)
    urllib.request.urlretrieve(DATA_URL, candidate)
    return candidate


def _cell_text(cell) -> str:
    parts = []
    for node in cell.iter():
        if node.tag == P:
            if node.text:
                parts.append(node.text)
            if node.tail:
                parts.append(node.tail)
    return "".join(parts).strip()


def _row_values(row) -> list[str]:
    values: list[str] = []
    for cell in row.findall(CELL):
        repeat = int(cell.attrib.get(COL_REPEAT, "1"))
        value = _cell_text(cell)
        values.extend([value] * repeat)
    while values and values[-1] == "":
        values.pop()
    return values


def _iter_lsoa_rows(path: str):
    with zipfile.ZipFile(path) as zf:
        with zf.open("content.xml") as fh:
            in_target = False
            header = None
            for event, elem in ET.iterparse(fh, events=("start", "end")):
                if event == "start" and elem.tag == TABLE:
                    table_name = elem.attrib.get(TABLE_NAME, "")
                    in_target = "lsoa" in table_name.lower()
                elif event == "end" and elem.tag == ROW and in_target:
                    values = _row_values(elem)
                    if values:
                        if header is None and values and values[0] == "LSOA21CD":
                            header = values
                        elif header is not None and values[0].startswith("E"):
                            yield dict(zip(header, values))
                    elem.clear()
                elif event == "end" and elem.tag == TABLE and in_target:
                    break
                elif event == "end" and not in_target:
                    elem.clear()


def _as_float(value: str | None):
    if value in (None, ""):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def run(db_url: str) -> int:
    path = _resolve_data_path()
    print(f"  Connectivity metric source: {path}", flush=True)

    rows = []
    for record in _iter_lsoa_rows(path):
        lsoa_code = (record.get("LSOA21CD") or "").strip()
        if not lsoa_code.startswith("E"):
            continue

        payload = {db_col: None for db_col in INSERT_COLUMNS}
        payload["lsoa_code"] = lsoa_code
        payload["source_release"] = SOURCE_RELEASE

        for source_col, db_col in COLUMN_MAP.items():
            if db_col == "lsoa_code":
                continue
            payload[db_col] = _as_float(record.get(source_col))

        rows.append(tuple(payload[col] for col in INSERT_COLUMNS))

    print(f"  Collected {len(rows):,} England LSOA connectivity rows", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['connectivity_lsoa']} CASCADE")
    if rows:
        assignments = ",\n                ".join(
            f"{col} = EXCLUDED.{col}" for col in INSERT_COLUMNS if col != "lsoa_code"
        )
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['connectivity_lsoa']} ({', '.join(INSERT_COLUMNS)})
            VALUES %s
            ON CONFLICT (lsoa_code) DO UPDATE SET
                {assignments}
            """,
            rows,
            page_size=1000,
        )
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['connectivity_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
