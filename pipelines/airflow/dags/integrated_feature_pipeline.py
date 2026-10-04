"""
FeatureHub + DataGuard Integrated End-to-End Pipeline Airflow DAG (Phase I).
Orchestrates genuine end-to-end data platform flow:
Data Source -> Feature Computation -> DataGuard Contract Validation ->
DataGuard Schema Validation -> Great Expectations -> OpenLineage ->
Airflow -> FeatureHub Offline Store -> Materialization -> Redis ->
FeatureHub API -> ML Prediction.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    from pipelines.airflow.shim import DAG, PythonOperator

from pipelines.airflow.utils.task_helpers import on_pipeline_failure_callback
from featurehub.integration.service import FeatureHubDataGuardIntegrator

PIPELINE_ID = "integrated_feature_pipeline"
DATASET_NAME = "customer_features"

default_args = {
    "owner": "platform-engineering-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(minutes=10),
    "on_failure_callback": on_pipeline_failure_callback
}

dag = DAG(
    dag_id=PIPELINE_ID,
    default_args=default_args,
    description="End-to-End FeatureHub + DataGuard Flow: Raw Ingestion to Real-Time ML Inference",
    schedule_interval="0 */2 * * *", # Every 2 hours
    catchup=False,
    tags=["featurehub", "dataguard", "integration", "mlops", "production"]
)


def task_run_integrated_platform_pipeline(**context) -> Dict[str, Any]:
    """
    Executes the unified 11-stage integration flow through FeatureHubDataGuardIntegrator.
    """
    integrator = FeatureHubDataGuardIntegrator()
    result = integrator.run_e2e_pipeline(
        dataset_name=DATASET_NAME,
        target_customer_id="cust_0001"
    )
    if result.status != "SUCCESS":
        raise RuntimeError(f"Integrated pipeline failed: {result.error_message}")
    return result.model_dump()


with dag:
    execute_e2e_pipeline = PythonOperator(
        task_id="execute_integrated_flow",
        python_callable=task_run_integrated_platform_pipeline,
        dag=dag
    )
