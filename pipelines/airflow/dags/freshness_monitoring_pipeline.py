"""
Dataset Freshness SLA Monitoring Airflow DAG (Phase G).
Dynamically evaluates datasets against declared contract freshness SLAs.
Calculates real delays, publishes Prometheus metrics, and generates incidents on SLA breaches.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    from pipelines.airflow.shim import DAG, PythonOperator

from pipelines.airflow.utils.task_helpers import (
    task_start_pipeline,
    task_finalize_pipeline,
    on_pipeline_failure_callback
)
from dataguard.pipelines.freshness import FreshnessMonitorService
from dataguard.quality.datasets import DatasetCatalog
from dataguard.lineage.collector import LineageCollector

PIPELINE_ID = "freshness_monitoring_pipeline"
DATASET_NAME = "fraud_events"

default_args = {
    "owner": "data-operations-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(minutes=5),
    "on_failure_callback": on_pipeline_failure_callback
}

dag = DAG(
    dag_id=PIPELINE_ID,
    default_args=default_args,
    description="Multi-dataset real-time freshness audit against SLA thresholds",
    schedule_interval="*/30 * * * *",
    catchup=False,
    tags=["dataguard", "freshness", "sla", "monitoring"]
)


def task_audit_dataset_freshness(dataset_name: str, sla_override_minutes: int = 60, **context) -> dict:
    freshness_service = FreshnessMonitorService()
    df = DatasetCatalog.load_dataset(dataset_name)
    result = freshness_service.evaluate_dataset_freshness(
        dataset_name=dataset_name,
        df=df,
        pipeline_id=PIPELINE_ID,
        sla_override_minutes=sla_override_minutes
    )
    if not result.is_fresh:
        raise ValueError(
            f"Freshness SLA violation for '{dataset_name}': delay {result.delay_minutes:.1f}m > SLA {result.sla_minutes}m (incident: {result.incident_id})"
        )
    return result.to_dict()


def task_emit_freshness_lineage(pipeline_id: str, dataset: str, **context) -> bool:
    ti = context.get("task_instance")
    run_id = ti.xcom_pull(task_ids="start_pipeline", key="run_id") if ti else "freshness_run"

    collector = LineageCollector()
    collector.complete_run(
        run_id=run_id,
        outputs=["freshness_audit_report"],
        pipeline_id=pipeline_id,
        job_name=pipeline_id
    )
    return True


with dag:
    start_pipeline = PythonOperator(
        task_id="start_pipeline",
        python_callable=task_start_pipeline,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    audit_transactions = PythonOperator(
        task_id="audit_transactions_freshness",
        python_callable=task_audit_dataset_freshness,
        op_kwargs={"dataset_name": "transactions", "sla_override_minutes": 1440}
    )

    audit_fraud = PythonOperator(
        task_id="audit_fraud_events_freshness",
        python_callable=task_audit_dataset_freshness,
        op_kwargs={"dataset_name": "fraud_events", "sla_override_minutes": 1440}
    )

    audit_customers = PythonOperator(
        task_id="audit_customers_freshness",
        python_callable=task_audit_dataset_freshness,
        op_kwargs={"dataset_name": "customers", "sla_override_minutes": 1440}
    )

    emit_lineage = PythonOperator(
        task_id="emit_lineage",
        python_callable=task_emit_freshness_lineage,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    finalize_pipeline = PythonOperator(
        task_id="finalize_pipeline",
        python_callable=task_finalize_pipeline,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    start_pipeline >> [audit_transactions, audit_fraud, audit_customers] >> emit_lineage >> finalize_pipeline
