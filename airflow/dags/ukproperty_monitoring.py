"""
PropertyPulse — Data Quality Monitoring DAG

Schedule: Daily at 06:00 UTC
Tasks:
  1. Check data freshness (alert if stale > 35 days)
  2. Check row counts (alert if significantly dropped)
  3. Check backend API health
  4. Alert on Slack if any check fails
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

POSTGRES_CONN = os.environ.get(
    "DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty"
)
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")

default_args = {
    "owner": "propertypulse",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

FRESHNESS_CHECKS = [
    ("core_crime_lsoa", "month", 35, "SELECT MAX(month) FROM core_crime_lsoa"),
    ("core_property_transactions", "date_of_transfer", 35, "SELECT MAX(date_of_transfer) FROM core_property_transactions"),
    ("core_hpi_lad", "year_month", 120, "SELECT MAX(year_month) FROM core_hpi_lad"),
]

ROW_COUNT_CHECKS = [
    ("core_crime_lsoa", 5_000_000),
    ("core_property_transactions", 20_000_000),
    ("core_schools", 20_000),
    ("core_lsoa_boundaries", 30_000),
    ("core_broadband_postcode", 1_500_000),
    ("core_epc_lsoa", 33_000),
]


def check_data_freshness(**context):
    import psycopg2
    from datetime import date

    conn = psycopg2.connect(POSTGRES_CONN)
    cur = conn.cursor()
    failures = []

    for table, col, max_days, query in FRESHNESS_CHECKS:
        cur.execute(query)
        row = cur.fetchone()
        if not row or row[0] is None:
            failures.append(f"{table}: no data")
            continue
        latest = row[0]
        if hasattr(latest, "date"):
            latest = latest.date()
        elif not isinstance(latest, date):
            latest = date.today()  # fallback
        days_old = (date.today() - latest).days
        if days_old > max_days:
            failures.append(f"{table}.{col}: {days_old} days old (max {max_days})")

    cur.close()
    conn.close()

    if failures:
        msg = "⚠️ Data freshness check failed:\n" + "\n".join(f"  - {f}" for f in failures)
        print(msg)
        if SLACK_WEBHOOK:
            import urllib.request, json
            urllib.request.urlopen(urllib.request.Request(
                SLACK_WEBHOOK,
                data=json.dumps({"text": msg}).encode(),
                headers={"Content-Type": "application/json"},
            ))
        raise ValueError(msg)

    print("✅ All freshness checks passed")


def check_row_counts(**context):
    import psycopg2

    conn = psycopg2.connect(POSTGRES_CONN)
    cur = conn.cursor()
    failures = []

    for table, min_rows in ROW_COUNT_CHECKS:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        if count < min_rows:
            failures.append(f"{table}: {count:,} rows (min {min_rows:,})")

    cur.close()
    conn.close()

    if failures:
        msg = "⚠️ Row count check failed:\n" + "\n".join(f"  - {f}" for f in failures)
        print(msg)
        if SLACK_WEBHOOK:
            import urllib.request, json
            urllib.request.urlopen(urllib.request.Request(
                SLACK_WEBHOOK,
                data=json.dumps({"text": msg}).encode(),
                headers={"Content-Type": "application/json"},
            ))
        raise ValueError(msg)

    print("✅ All row count checks passed")


def check_api_health(**context):
    import urllib.request, json

    test_endpoints = [
        f"{API_BASE}/resolve?q=SW1A+1AA",
        f"{API_BASE}/resolve?q=Manchester",
    ]
    failures = []

    for url in test_endpoints:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("error") or not data.get("resolved_codes"):
                    failures.append(f"{url}: unexpected response")
        except Exception as e:
            failures.append(f"{url}: {e}")

    if failures:
        msg = "⚠️ API health check failed:\n" + "\n".join(f"  - {f}" for f in failures)
        print(msg)
        if SLACK_WEBHOOK:
            import urllib.request, json
            urllib.request.urlopen(urllib.request.Request(
                SLACK_WEBHOOK,
                data=json.dumps({"text": msg}).encode(),
                headers={"Content-Type": "application/json"},
            ))
        raise ValueError(msg)

    print("✅ API health checks passed")


with DAG(
    dag_id="ukproperty_monitoring",
    default_args=default_args,
    description="Daily data quality and API health monitoring",
    schedule_interval="0 6 * * *",  # Daily 06:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["propertypulse", "monitoring", "daily"],
) as dag:

    freshness = PythonOperator(
        task_id="check_data_freshness",
        python_callable=check_data_freshness,
    )

    row_counts = PythonOperator(
        task_id="check_row_counts",
        python_callable=check_row_counts,
    )

    api_health = PythonOperator(
        task_id="check_api_health",
        python_callable=check_api_health,
    )

    # Run checks in parallel
    [freshness, row_counts, api_health]
