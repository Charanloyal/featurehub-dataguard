"""
Transaction Quality Validation Airflow DAG (Phase G).
Orchestrates real-time payments contract checks, currency validations,
amount boundaries, OpenLineage tracking, and incident escalation.
"""

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    from pipelines.airflow.shim import DAG, PythonOperator

from pipelines.airflow.utils.task_helpers import (
    task_start_pipeline,
    task_load_contract,
    task_validate_contract,
    task_validate_schema,
    task_run_quality_checks,
    task_persist_quality_results,
    task_emit_lineage,
    task_create_incident_if_required,
    task_finalize_pipeline,
    on_pipeline_failure_callback
)

PIPELINE_ID = "transaction_quality_pipeline"
DATASET_NAME = "transactions"

default_args = {
    "owner": "payments-data-team",
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
    description="Transactions dataset quality validation: currency codes, amounts, settlement status",
    schedule_interval="*/15 * * * *",
    catchup=False,
    tags=["dataguard", "transactions", "payments", "financial"]
)

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

    validate_contract = PythonOperator(
        task_id="validate_contract",
        python_callable=task_validate_contract,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    validate_schema = PythonOperator(
        task_id="validate_schema",
        python_callable=task_validate_schema,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    run_quality_checks = PythonOperator(
        task_id="run_quality_checks",
        python_callable=task_run_quality_checks,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    persist_quality_results = PythonOperator(
        task_id="persist_quality_results",
        python_callable=task_persist_quality_results,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    emit_lineage = PythonOperator(
        task_id="emit_lineage",
        python_callable=task_emit_lineage,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    create_incident_if_required = PythonOperator(
        task_id="create_incident_if_required",
        python_callable=task_create_incident_if_required,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    finalize_pipeline = PythonOperator(
        task_id="finalize_pipeline",
        python_callable=task_finalize_pipeline,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    start_pipeline >> load_contract >> validate_contract >> validate_schema >> run_quality_checks >> persist_quality_results >> emit_lineage >> create_incident_if_required >> finalize_pipeline
