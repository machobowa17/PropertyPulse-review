"""
PropertyPulse — Main Data Pipeline DAG

Schedule: Weekly on Sunday 02:00 UTC
Tasks:
  1. Check source data freshness
  2. Land Registry PPD (monthly)
  3. HPI data (quarterly)
  4. GIAS schools + Ofsted (monthly)
  5. dbt run (transforms + aggregations)
  6. dbt test (data quality checks)
  7. Redis cache invalidation
  8. Slack notification (optional)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.trigger_rule import TriggerRule

ETL_DIR = os.environ.get("ETL_DIR", "/opt/ukproperty/etl")
DBT_DIR = os.environ.get("DBT_DIR", "/opt/ukproperty/dbt/ukproperty")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
POSTGRES_CONN = os.environ.get(
    "DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty"
)

default_args = {
    "owner": "propertypulse",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=15),
    "execution_timeout": timedelta(hours=4),
}

with DAG(
    dag_id="ukproperty_weekly_pipeline",
    default_args=default_args,
    description="PropertyPulse weekly data refresh pipeline",
    schedule_interval="0 2 * * 0",  # Sunday 02:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["propertypulse", "etl", "weekly"],
) as dag:

    # ─── 1. Land Registry Price Paid (monthly PPD, incremental) ─────────────
    ingest_land_registry = BashOperator(
        task_id="ingest_land_registry",
        bash_command=f"cd {ETL_DIR} && python3 ingest_land_registry.py --incremental",
        env={"DATABASE_URL": POSTGRES_CONN},
    )

    # ─── 2. House Price Index (HPI) ─────────────────────────────────────────
    ingest_hpi = BashOperator(
        task_id="ingest_hpi",
        bash_command=f"cd {ETL_DIR} && python3 ingest_hpi.py",
        env={"DATABASE_URL": POSTGRES_CONN},
    )

    # ─── 3. GIAS Schools + Ofsted refresh ───────────────────────────────────
    ingest_schools = BashOperator(
        task_id="ingest_schools",
        bash_command=f"cd {ETL_DIR} && python3 ingest_schools_ofsted.py",
        env={"DATABASE_URL": POSTGRES_CONN},
    )

    # ─── 4. Crime data (monthly, police.uk) ─────────────────────────────────
    ingest_crime = BashOperator(
        task_id="ingest_crime",
        bash_command=f"cd {ETL_DIR} && python3 ingest_crime.py",
        env={"DATABASE_URL": POSTGRES_CONN},
        execution_timeout=timedelta(hours=2),
    )

    # ─── 5. dbt run — transforms & aggregations ──────────────────────────────
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt run --target prod --profiles-dir . --no-partial-parse"
        ),
        env={
            "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "POSTGRES_DB": os.environ.get("POSTGRES_DB", "ukproperty"),
            "POSTGRES_USER": os.environ.get("POSTGRES_USER", "postgres"),
            "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        },
    )

    # ─── 6. dbt test — data quality ──────────────────────────────────────────
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt test --target prod --profiles-dir ."
        ),
        env={
            "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "POSTGRES_DB": os.environ.get("POSTGRES_DB", "ukproperty"),
            "POSTGRES_USER": os.environ.get("POSTGRES_USER", "postgres"),
            "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        },
    )

    # ─── 7. Redis cache flush ─────────────────────────────────────────────────
    def flush_redis_cache():
        """Flush all cached API responses after data refresh."""
        import redis
        r = redis.from_url(REDIS_URL)
        flushed = r.flushdb()
        print(f"Redis cache flushed: {flushed}")

    invalidate_cache = PythonOperator(
        task_id="invalidate_cache",
        python_callable=flush_redis_cache,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # ─── 8. Refresh materialized broadband LAD view ───────────────────────────
    refresh_broadband_mat = BashOperator(
        task_id="refresh_broadband_materialized",
        bash_command=(
            f"psql $DATABASE_URL -c "
            "'REFRESH MATERIALIZED VIEW CONCURRENTLY core_broadband_lad;' "
            "|| true"  # non-fatal if it's a regular table
        ),
        env={"DATABASE_URL": POSTGRES_CONN},
    )

    # ─── Task dependencies ────────────────────────────────────────────────────
    # ETL tasks can run in parallel
    [ingest_land_registry, ingest_hpi, ingest_schools, ingest_crime] >> dbt_run
    dbt_run >> dbt_test >> invalidate_cache
    dbt_run >> refresh_broadband_mat >> invalidate_cache
