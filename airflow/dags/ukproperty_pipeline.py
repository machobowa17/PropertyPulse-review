"""
PropertyPulse — Monthly Data Pipeline DAG

Schedule: 1st of each month at 02:00 UTC
Runs all monthly sources (land_registry_full, hpi, crime, schools, epc_domestic,
price_by_bedrooms) via pipeline.py, which handles:
  - Dependency ordering
  - Run tracking (core_pipeline_runs)
  - Targeted Redis cache invalidation (never FLUSHDB)
  - Row-count validation
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

ETL_DIR = os.environ.get("ETL_DIR", "/opt/ukproperty/etl")
POSTGRES_CONN = os.environ.get(
    "DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

default_args = {
    "owner": "propertypulse",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=6),
}

with DAG(
    dag_id="ukproperty_monthly_pipeline",
    default_args=default_args,
    description="PropertyPulse monthly data refresh (Land Registry, HPI, crime, schools, EPC)",
    schedule_interval="0 2 1 * *",  # 1st of month, 02:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["propertypulse", "etl", "monthly"],
) as dag:

    run_monthly = BashOperator(
        task_id="run_monthly_pipeline",
        bash_command=f"cd {ETL_DIR} && python3 pipeline.py --schedule monthly",
        env={
            "DATABASE_URL": POSTGRES_CONN,
            "REDIS_URL": REDIS_URL,
        },
    )
