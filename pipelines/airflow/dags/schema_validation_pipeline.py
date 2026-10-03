"""
Schema Compatibility & Drift Validation Airflow DAG (Phase G).
Compares live physical schemas against registered data contracts using SchemaDiffEngine.
Enforces non-breaking contract evolution policies and escalates breaking modifications.
"""

from datetime import datetime, timedelta

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
from dataguard.contracts.registry import ContractRegistryService
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import DiffSeverity
from dataguard.quality.datasets import DatasetCatalog
from dataguard.quality.models import QualityCheckResult, QualityStatus
from dataguard.lineage.collector import LineageCollector
from dataguard.incidents.manager import IncidentManager

PIPELINE_ID = "schema_validation_pipeline"
DATASET_NAME = "accounts"

default_args = {
    "owner": "data-platform-team",
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
    description="Schema drift and breaking change detection across platform data contracts",
    schedule_interval="0 6 * * *",
    catchup=False,
    tags=["dataguard", "schema", "compatibility", "governance"]
)


def task_fetch_baseline_contract(pipeline_id: str, dataset: str, **context) -> dict:
    registry = ContractRegistryService()
    contract = registry.get_contract(dataset) or registry.get_contract(f"{dataset}.yaml")
    if not contract:
        raise ValueError(f"Baseline contract not found for {dataset}")
    return contract


def task_inspect_physical_schema(pipeline_id: str, dataset: str, **context) -> dict:
    df = DatasetCatalog.load_dataset(dataset)
    if df is None:
        raise FileNotFoundError(f"Physical dataset '{dataset}' not found.")

    columns = []
    for col_name, dtype in df.dtypes.items():
        type_str = "string"
        if "int" in str(dtype):
            type_str = "integer"
        elif "float" in str(dtype):
            type_str = "float"
        elif "bool" in str(dtype):
            type_str = "boolean"
        elif "datetime" in str(dtype):
            type_str = "timestamp"

        columns.append({
            "name": str(col_name),
            "type": type_str,
            "nullable": bool(df[col_name].isnull().any())
        })

    return {"dataset": dataset, "schema": {"columns": columns}}


def task_compare_and_gate_schema(pipeline_id: str, dataset: str, **context) -> dict:
    ti = context.get("task_instance")
    baseline = ti.xcom_pull(task_ids="fetch_baseline_contract") if ti else None
    if not baseline:
        baseline = task_fetch_baseline_contract(pipeline_id, dataset, **context)

    target = ti.xcom_pull(task_ids="inspect_physical_schema") if ti else None
    if not target:
        target = task_inspect_physical_schema(pipeline_id, dataset, **context)

    diff_result = SchemaDiffEngine.compare_contracts(
        baseline_contract=baseline,
        target_contract=target
    )

    if diff_result.breaking_count > 0 or diff_result.severity == DiffSeverity.BREAKING:
        first_break = next((c for c in diff_result.changes if c.severity == DiffSeverity.BREAKING), None)
        desc = first_break.description if first_break else "Breaking change detected"

        # Create incident
        manager = IncidentManager()
        manager.handle_check_failure(
            check=QualityCheckResult(
                check_name=f"breaking_schema_{dataset}",
                expectation_type="expect_schema_compatibility",
                status=QualityStatus.FAIL,
                success=False,
                observed_value=desc,
                expected_value="Backward compatible schema"
            ),
            dataset=dataset,
            pipeline=pipeline_id,
            contract=baseline
        )

        raise ValueError(f"Schema compatibility check failed: {desc} ({diff_result.breaking_count} breaking changes)")

    return {
        "status": "PASS",
        "severity": diff_result.severity.value,
        "breaking_count": diff_result.breaking_count,
        "warning_count": diff_result.warning_count,
        "safe_count": diff_result.safe_count
    }


def task_emit_schema_lineage(pipeline_id: str, dataset: str, **context) -> bool:
    ti = context.get("task_instance")
    run_id = ti.xcom_pull(task_ids="start_pipeline", key="run_id") if ti else "schema_run"

    collector = LineageCollector()
    collector.complete_run(
        run_id=run_id,
        outputs=[f"{dataset}_schema_verified"],
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

    fetch_baseline = PythonOperator(
        task_id="fetch_baseline_contract",
        python_callable=task_fetch_baseline_contract,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    inspect_schema = PythonOperator(
        task_id="inspect_physical_schema",
        python_callable=task_inspect_physical_schema,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    compare_gate = PythonOperator(
        task_id="compare_and_gate_schema",
        python_callable=task_compare_and_gate_schema,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    emit_lineage = PythonOperator(
        task_id="emit_lineage",
        python_callable=task_emit_schema_lineage,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    finalize_pipeline = PythonOperator(
        task_id="finalize_pipeline",
        python_callable=task_finalize_pipeline,
        op_kwargs={"pipeline_id": PIPELINE_ID, "dataset": DATASET_NAME}
    )

    start_pipeline >> [fetch_baseline, inspect_schema] >> compare_gate >> emit_lineage >> finalize_pipeline
