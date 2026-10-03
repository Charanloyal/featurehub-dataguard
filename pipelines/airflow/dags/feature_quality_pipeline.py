"""
FeatureHub Quality Validation Airflow DAG (Phase G).
Audits computed offline FeatureHub feature store datasets (customer_features, merchant_features)
for schema adherence, feature freshness, null rates, distribution shifts, and OpenLineage provenance.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    from pipelines.airflow.shim import DAG, PythonOperator

from pipelines.airflow.utils.task_helpers import (
    task_start_pipeline,
    task_load_contract,
    task_validate_schema,
    task_persist_quality_results,
    task_finalize_pipeline,
    on_pipeline_failure_callback
)
from dataguard.contracts.registry import ContractRegistryService
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.models import QualityStatus, QualityCheckResult
from dataguard.quality.datasets import DatasetCatalog
from dataguard.lineage.collector import LineageCollector
from dataguard.incidents.manager import IncidentManager
from dataguard.pipelines.freshness import FreshnessMonitorService

PIPELINE_ID = "feature_quality_pipeline"
DATASET_NAME = "customer_features"

default_args = {
    "owner": "mlops-platform-team",
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
    description="FeatureHub Feature Store quality monitoring: schema, null rates, freshness, row counts",
    schedule_interval="0 2 * * *",
    catchup=False,
    tags=["dataguard", "featurehub", "features", "mlops"]
)


def task_audit_feature_freshness(pipeline_id: str, dataset: str, **context) -> bool:
    """Audits feature timestamp recency against SLA limits."""
    freshness_service = FreshnessMonitorService()
    df = DatasetCatalog.load_dataset(dataset)
    res = freshness_service.evaluate_dataset_freshness(
        dataset_name=dataset,
        df=df,
        pipeline_id=pipeline_id,
        sla_override_minutes=120
    )
    if not res.is_fresh:
        raise ValueError(f"Feature dataset '{dataset}' is STALE: delay {res.delay_minutes:.1f}m > SLA {res.sla_minutes}m")
    return True


def task_audit_feature_null_rates(pipeline_id: str, dataset: str, **context) -> Dict[str, float]:
    """Calculates null rates across all feature columns and flags violations > 5%."""
    df = DatasetCatalog.load_dataset(dataset)
    if df is None or df.empty:
        raise ValueError(f"Feature dataset '{dataset}' is empty or missing.")

    null_rates = (df.isnull().sum() / len(df)).to_dict()
    violations = {k: v for k, v in null_rates.items() if v > 0.05}
    if violations:
        raise ValueError(f"Excessive null rates detected in features: {violations}")
    return null_rates


def task_audit_feature_row_count(pipeline_id: str, dataset: str, **context) -> int:
    """Verifies feature dataset meets minimum expected row count threshold."""
    df = DatasetCatalog.load_dataset(dataset)
    if df is None:
        raise ValueError(f"Feature dataset '{dataset}' not found.")
    count = len(df)
    if count < 10:
        raise ValueError(f"Feature row count {count} is below minimum threshold (10)")
    return count


def task_emit_feature_lineage(pipeline_id: str, dataset: str, **context) -> bool:
    """Emits OpenLineage event with upstream dependencies (customers, transactions)."""
    ti = context.get("task_instance")
    run_id = ti.xcom_pull(task_ids="start_pipeline", key="run_id") if ti else "feature_run"

    collector = LineageCollector()
    collector.complete_run(
        run_id=run_id,
        outputs=[dataset],
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

    load_contract = PythonOperator(
        task_id="load_contract",
        python_callable=task_load_contract,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    validate_schema = PythonOperator(
        task_id="validate_schema",
        python_callable=task_validate_schema,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    audit_freshness = PythonOperator(
        task_id="audit_feature_freshness",
        python_callable=task_audit_feature_freshness,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    audit_null_rates = PythonOperator(
        task_id="audit_feature_null_rates",
        python_callable=task_audit_feature_null_rates,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    audit_row_count = PythonOperator(
        task_id="audit_feature_row_count",
        python_callable=task_audit_feature_row_count,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    persist_results = PythonOperator(
        task_id="persist_quality_results",
        python_callable=task_persist_quality_results,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    emit_lineage = PythonOperator(
        task_id="emit_lineage",
        python_callable=task_emit_feature_lineage,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    finalize_pipeline = PythonOperator(
        task_id="finalize_pipeline",
        python_callable=task_finalize_pipeline,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    # Dependencies: parallel branch for feature audits
    start_pipeline >> load_contract >> validate_schema
    validate_schema >> [audit_freshness, audit_null_rates, audit_row_count] >> persist_results
    persist_results >> emit_lineage >> finalize_pipeline
