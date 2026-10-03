"""
Deterministic Demo Test Pipelines Airflow DAGs (Phase G).
Provides isolated, parameter-driven demo DAGs for verifying:
1. Clean dataset execution (SUCCESS flow)
2. Null failure injection (FAIL + INCIDENT)
3. Duplicate primary key failure injection (FAIL + INCIDENT)
4. Invalid enum failure injection (FAIL + INCIDENT)
5. Referential integrity failure injection (FAIL + INCIDENT)
6. Stale dataset SLA breach (FAIL + INCIDENT)
7. Breaking schema change detection (FAIL + INCIDENT)
"""

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    from pipelines.airflow.shim import DAG, PythonOperator

from dataguard.pipelines.runner import DataGuardPipelineOrchestrator
from pipelines.airflow.utils.task_helpers import on_pipeline_failure_callback

SCENARIOS = [
    ("demo_clean_pipeline", None, "customers", "Clean dataset benchmark run (Expected: SUCCESS)"),
    ("demo_null_failure_pipeline", "null_failure", "customers", "Deterministic null constraint violation (Expected: FAILED + Incident)"),
    ("demo_duplicate_failure_pipeline", "duplicate_failure", "transactions", "Deterministic duplicate primary key violation (Expected: FAILED + Incident)"),
    ("demo_invalid_enum_pipeline", "invalid_enum", "transactions", "Deterministic invalid enum violation (Expected: FAILED + Incident)"),
    ("demo_referential_failure_pipeline", "referential_failure", "orders", "Deterministic foreign key referential violation (Expected: FAILED + Incident)"),
    ("demo_stale_dataset_pipeline", "stale_dataset", "fraud_events", "Deterministic freshness SLA violation (Expected: FAILED + Incident)"),
    ("demo_breaking_schema_pipeline", "breaking_schema", "accounts", "Deterministic breaking schema alteration (Expected: FAILED + Incident)")
]

default_args = {
    "owner": "platform-qa-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "execution_timeout": timedelta(minutes=2),
    "on_failure_callback": on_pipeline_failure_callback
}


def run_demo_scenario(pipeline_id: str, dataset_name: str, scenario: str, **context):
    orchestrator = DataGuardPipelineOrchestrator()
    return orchestrator.execute_pipeline(
        pipeline_id=pipeline_id,
        dataset_name=dataset_name,
        test_scenario=scenario,
        raise_on_failure=True
    )


# Dynamically register each deterministic demo DAG
for dag_id, scenario_key, dataset, desc in SCENARIOS:
    demo_dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=desc,
        schedule_interval=None, # Manual trigger only
        catchup=False,
        tags=["dataguard", "demo", "test_scenario"]
    )

    with demo_dag:
        exec_task = PythonOperator(
            task_id="execute_scenario_task",
            python_callable=run_demo_scenario,
            op_kwargs={
                "pipeline_id": dag_id,
                "dataset_name": dataset,
                "scenario": scenario_key
            }
        )
    globals()[dag_id] = demo_dag
