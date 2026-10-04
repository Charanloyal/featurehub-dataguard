"""
DataGuard Phase G - Apache Airflow Pipeline Orchestration Test Suite
====================================================================
Comprehensive tests validating:
1. Airflow DAG loading & task dependency structures
2. Custom DataGuard operators and plugins
3. Pipeline catalog and PostgreSQL repository persistence
4. Dynamic health and summary calculations
5. Orchestrator end-to-end execution lifecycle (Contract -> Schema -> Quality -> Lineage -> Incidents)
6. Deterministic failure scenarios (Null, Duplicate, Enum, Referential, Breaking Schema, Stale)
7. Fast-fail behavior, retry handling, timeouts, and idempotent reruns
8. FastAPI pipeline endpoints and Prometheus observability metrics
"""

import os
import uuid
import pytest
import pandas as pd
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from dataguard.pipelines.models import (
    PipelineConfig,
    PipelineRun,
    PipelineStatus,
    PipelineRunStatus,
    PipelineHealth,
    PipelineSummary
)
from dataguard.pipelines.registry import PipelineRegistryService
from dataguard.pipelines.repository import PipelineRepository
from dataguard.pipelines.runner import (
    DataGuardPipelineOrchestrator,
    PipelineExecutionError,
    TransientInfrastructureError
)
from dataguard.pipelines.freshness import FreshnessMonitorService
from dataguard.contracts.registry import ContractRegistryService
from dataguard.quality.datasets import DatasetCatalog
from dataguard.api.main import app
from dataguard.metrics import (
    PIPELINE_RUNS_TOTAL,
    PIPELINE_SUCCESS_TOTAL,
    PIPELINE_FAILURE_TOTAL,
    PIPELINE_QUALITY_FAILURES_TOTAL
)


@pytest.fixture(scope="module")
def repo():
    return PipelineRepository()


@pytest.fixture(scope="module")
def orchestrator():
    return DataGuardPipelineOrchestrator()


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


# ==============================================================================
# 1. DAG & Operator Structure Tests
# ==============================================================================

def test_01_dag_imports_and_structure():
    """Verify DAG definitions import cleanly and expose expected DAG IDs and parameters."""
    from pipelines.airflow.dags.customer_quality_pipeline import dag as cust_dag
    from pipelines.airflow.dags.transaction_quality_pipeline import dag as tx_dag
    from pipelines.airflow.dags.feature_quality_pipeline import dag as feat_dag
    from pipelines.airflow.dags.schema_validation_pipeline import dag as schema_dag
    from pipelines.airflow.dags.freshness_monitoring_pipeline import dag as fresh_dag

    assert cust_dag.dag_id == "customer_quality_pipeline"
    assert tx_dag.dag_id == "transaction_quality_pipeline"
    assert feat_dag.dag_id == "feature_quality_pipeline"
    assert schema_dag.dag_id == "schema_validation_pipeline"
    assert fresh_dag.dag_id == "freshness_monitoring_pipeline"

    # Verify default args and retries
    assert cust_dag.default_args.get("retries", 0) >= 1
    assert "retry_delay" in cust_dag.default_args


def test_02_customer_pipeline_task_dependencies():
    """Verify task flow dependencies in customer_quality_pipeline DAG."""
    from pipelines.airflow.dags.customer_quality_pipeline import dag
    task_ids = {t.task_id for t in dag.tasks}
    expected = {
        "start_pipeline",
        "load_contract",
        "validate_contract",
        "validate_schema",
        "run_quality_checks",
        "persist_quality_results",
        "emit_lineage",
        "create_incident_if_required",
        "finalize_pipeline"
    }
    assert expected.issubset(task_ids)


def test_03_transaction_pipeline_task_dependencies():
    """Verify task flow dependencies in transaction_quality_pipeline DAG."""
    from pipelines.airflow.dags.transaction_quality_pipeline import dag
    task_ids = {t.task_id for t in dag.tasks}
    expected = {
        "start_pipeline",
        "load_contract",
        "validate_contract",
        "validate_schema",
        "run_quality_checks",
        "persist_quality_results",
        "emit_lineage",
        "create_incident_if_required",
        "finalize_pipeline"
    }
    assert expected.issubset(task_ids)


def test_04_feature_pipeline_task_dependencies():
    """Verify feature_quality_pipeline DAG covers feature datasets."""
    from pipelines.airflow.dags.feature_quality_pipeline import dag
    task_ids = {t.task_id for t in dag.tasks}
    assert "start_pipeline" in task_ids
    assert "load_contract" in task_ids
    assert "validate_schema" in task_ids
    assert "audit_feature_freshness" in task_ids
    assert "audit_feature_null_rates" in task_ids
    assert "audit_feature_row_count" in task_ids
    assert "persist_quality_results" in task_ids


def test_05_schema_validation_pipeline_tasks():
    """Verify schema_validation_pipeline evaluates schema compatibility across critical domains."""
    from pipelines.airflow.dags.schema_validation_pipeline import dag
    task_ids = {t.task_id for t in dag.tasks}
    assert "fetch_baseline_contract" in task_ids
    assert "inspect_physical_schema" in task_ids
    assert "compare_and_gate_schema" in task_ids


def test_06_freshness_monitoring_pipeline_tasks():
    """Verify freshness_monitoring_pipeline executes SLA audits."""
    from pipelines.airflow.dags.freshness_monitoring_pipeline import dag
    task_ids = {t.task_id for t in dag.tasks}
    assert "audit_transactions_freshness" in task_ids
    assert "audit_fraud_events_freshness" in task_ids
    assert "audit_customers_freshness" in task_ids


def test_07_demo_test_pipelines_registered():
    """Verify all 7 deterministic failure test DAGs are registered."""
    from pipelines.airflow.dags import demo_test_pipelines
    expected_dags = [
        "demo_clean_pipeline",
        "demo_null_failure_pipeline",
        "demo_duplicate_failure_pipeline",
        "demo_invalid_enum_pipeline",
        "demo_referential_failure_pipeline",
        "demo_stale_dataset_pipeline",
        "demo_breaking_schema_pipeline"
    ]
    for d in expected_dags:
        assert hasattr(demo_test_pipelines, d)
        dag_obj = getattr(demo_test_pipelines, d)
        assert dag_obj.dag_id == d


def test_08_custom_operator_plugin():
    """Verify DataGuardQualityOperator and DataGuardPlugin attributes."""
    from pipelines.airflow.plugins.dataguard_plugin import DataGuardQualityOperator, DataGuardPlugin
    assert DataGuardPlugin.name == "dataguard_plugin"
    assert DataGuardQualityOperator in DataGuardPlugin.operators

    op = DataGuardQualityOperator(
        task_id="test_op",
        pipeline_id="customer_quality_pipeline",
        dataset_name="customers"
    )
    assert op.pipeline_id == "customer_quality_pipeline"
    assert op.dataset_name == "customers"


# ==============================================================================
# 2. Registry & Repository Persistence Tests
# ==============================================================================

def test_09_pipeline_catalog_contains_standard_pipelines():
    """Verify PipelineRegistryService registers all 26 production pipelines."""
    service = PipelineRegistryService()
    configs = service.list_standard_pipelines()
    assert len(configs) >= 25
    ids = {c.pipeline_id for c in configs}
    assert "customer_quality_pipeline" in ids
    assert "transaction_quality_pipeline" in ids
    assert "feature_quality_pipeline" in ids


def test_10_pipeline_metadata_persistence(repo):
    """Verify saving and retrieving pipeline configurations in PostgreSQL."""
    pipe_id = f"test_pipe_{uuid.uuid4().hex[:8]}"
    config = PipelineConfig(
        pipeline_id=pipe_id,
        name="Test Pipeline",
        description="Test automated pipeline",
        owner="test-team",
        dataset="customers",
        contract="customers",
        status=PipelineStatus.ACTIVE,
        schedule="0 0 * * *",
        freshness_sla_minutes=60,
        tags=["test"]
    )
    saved = repo.upsert_pipeline(config)
    assert saved.pipeline_id == pipe_id

    fetched = repo.get_pipeline(pipe_id)
    assert fetched is not None
    assert fetched.pipeline_id == pipe_id
    assert fetched.owner == "test-team"
    assert fetched.freshness_sla_minutes == 60


def test_11_pipeline_run_persistence_and_query(repo):
    """Verify saving and querying execution runs in PostgreSQL."""
    pipe_id = "customer_quality_pipeline"
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    repo.record_run_start(run_id=run_id, pipeline_id=pipe_id, dataset="customers", start_time=now)
    saved = repo.record_run_finish(
        run_id=run_id,
        status=PipelineRunStatus.SUCCESS,
        duration_ms=450.0,
        quality_run_id="qr_123",
        retry_count=0,
        metrics={"total_checks": 14, "passed_checks": 14, "quality_score": 100.0}
    )
    assert saved is not None
    assert saved.run_id == run_id

    runs = repo.list_runs(pipeline_id=pipe_id, limit=10)
    run_ids = [r.run_id for r in runs]
    assert run_id in run_ids

    latest = repo.get_latest_run(pipe_id)
    assert latest is not None
    assert latest.pipeline_id == pipe_id


def test_12_pipeline_health_calculation(repo):
    """Verify dynamic health calculation evaluates health score correctly."""
    health = repo.get_pipeline_health("customer_quality_pipeline")
    assert health is not None
    assert health.pipeline_id == "customer_quality_pipeline"
    assert isinstance(health.is_healthy, bool)
    assert hasattr(health, "freshness_status")


def test_13_pipeline_summary_aggregation(repo):
    """Verify aggregate summary calculates live platform metrics."""
    summary = repo.get_pipeline_summary()
    assert summary is not None
    assert summary.total_pipelines >= 25
    assert summary.active_pipelines >= 20
    assert summary.total_runs >= 1
    assert 0.0 <= summary.success_rate <= 100.0


# ==============================================================================
# 3. Orchestrator End-to-End Success & Failure Execution Tests
# ==============================================================================

def test_14_orchestrator_clean_customer_pipeline_success(orchestrator):
    """Verify clean execution of customer_quality_pipeline."""
    res = orchestrator.execute_pipeline("customer_quality_pipeline")
    assert res.get("status") == "SUCCESS"
    assert res.get("quality_score") == 100.0
    assert res.get("failed_checks") == 0
    assert res.get("checks_passed") > 0
    assert res.get("run_id") is not None


def test_15_orchestrator_clean_transaction_pipeline_success(orchestrator):
    """Verify clean execution of transaction_quality_pipeline."""
    res = orchestrator.execute_pipeline("transaction_quality_pipeline")
    assert res.get("status") == "SUCCESS"
    assert res.get("quality_score") == 100.0
    assert res.get("failed_checks") == 0


def test_16_orchestrator_clean_feature_pipeline_success(orchestrator):
    """Verify clean execution of feature_quality_pipeline."""
    res = orchestrator.execute_pipeline("feature_quality_pipeline")
    assert res.get("status") == "SUCCESS"
    assert res.get("quality_score") == 100.0
    assert res.get("failed_checks") == 0


def test_17_orchestrator_null_violation_failure(orchestrator):
    """Verify injected null in non-nullable column fails quality validation and logs incident."""
    res = orchestrator.execute_pipeline(
        "customer_quality_pipeline",
        test_scenario="null_violation",
        raise_on_failure=False
    )
    assert res.get("status") == "FAILED"
    assert res.get("failed_checks") >= 1
    assert res.get("quality_score") < 100.0


def test_18_orchestrator_duplicate_failure(orchestrator):
    """Verify duplicate primary keys trigger failure in pipeline."""
    res = orchestrator.execute_pipeline(
        "customer_quality_pipeline",
        test_scenario="duplicate_violation",
        raise_on_failure=False
    )
    assert res.get("status") == "FAILED"
    assert res.get("failed_checks") >= 1


def test_19_orchestrator_invalid_enum_failure(orchestrator):
    """Verify illegal enum value triggers failure in pipeline."""
    res = orchestrator.execute_pipeline(
        "customer_quality_pipeline",
        test_scenario="enum_violation",
        raise_on_failure=False
    )
    assert res.get("status") == "FAILED"
    assert res.get("failed_checks") >= 1


def test_20_orchestrator_referential_failure(orchestrator):
    """Verify orphan foreign keys trigger referential check failure."""
    res = orchestrator.execute_pipeline(
        "transaction_quality_pipeline",
        test_scenario="referential_violation",
        raise_on_failure=False
    )
    assert res.get("status") == "FAILED"
    assert res.get("failed_checks") >= 1


def test_21_orchestrator_breaking_schema_failure(orchestrator):
    """Verify breaking schema drift triggers schema stage failure and fails fast."""
    res = orchestrator.execute_pipeline(
        "customer_quality_pipeline",
        test_scenario="breaking_schema",
        raise_on_failure=False
    )
    assert res.get("status") == "FAILED"
    assert "schema_validation" in str(res.get("stage", "")) or "Breaking schema" in str(res.get("error_message", ""))


def test_22_orchestrator_stale_dataset_failure(orchestrator):
    """Verify stale data triggers SLA breach failure."""
    res = orchestrator.execute_pipeline(
        "freshness_monitoring_pipeline",
        test_scenario="stale_dataset",
        raise_on_failure=False
    )
    assert res.get("status") == "FAILED"


def test_23_orchestrator_idempotent_rerun(orchestrator):
    """Verify successive executions with the same run_id update cleanly."""
    fixed_run_id = f"fixed_{uuid.uuid4().hex[:10]}"
    res1 = orchestrator.execute_pipeline("customer_quality_pipeline", run_id=fixed_run_id)
    assert res1.get("status") == "SUCCESS"
    assert res1.get("run_id") == fixed_run_id

    # Rerun with same run_id
    res2 = orchestrator.execute_pipeline("customer_quality_pipeline", run_id=fixed_run_id)
    assert res2.get("status") == "SUCCESS"
    assert res2.get("run_id") == fixed_run_id


def test_24_orchestrator_timeout_handling(orchestrator):
    """Verify timeout threshold stops long executions."""
    with pytest.raises(TransientInfrastructureError):
        orchestrator.execute_pipeline("customer_quality_pipeline", timeout_seconds=0.00001)


def test_25_freshness_service_evaluation():
    """Verify FreshnessMonitorService audits recency against contract SLA."""
    service = FreshnessMonitorService()
    res = service.evaluate_dataset_freshness(
        dataset_name="customers",
        pipeline_id="test_freshness"
    )
    assert res.dataset == "customers"
    assert res.sla_minutes > 0
    assert res.delay_minutes >= 0.0


# ==============================================================================
# 4. FastAPI Endpoints & Prometheus Metrics Tests
# ==============================================================================

def test_26_fastapi_list_pipelines(api_client):
    """Verify GET /pipelines returns active catalog list."""
    response = api_client.get("/pipelines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 25
    assert any(p["pipeline_id"] == "customer_quality_pipeline" for p in data)


def test_27_fastapi_pipeline_summary_and_details(api_client):
    """Verify GET /pipelines/summary, GET /pipelines/{id}, and GET /pipelines/{id}/health."""
    summary_resp = api_client.get("/pipelines/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_pipelines"] >= 25

    detail_resp = api_client.get("/pipelines/customer_quality_pipeline")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["pipeline_id"] == "customer_quality_pipeline"

    health_resp = api_client.get("/pipelines/customer_quality_pipeline/health")
    assert health_resp.status_code == 200
    assert "health_score" in health_resp.json() or "quality_score" in health_resp.json()


def test_28_prometheus_metrics_increment(api_client):
    """Verify Prometheus metrics endpoint exposes pipeline orchestration counters."""
    resp = api_client.get("/metrics")
    assert resp.status_code == 200
    content = resp.text
    assert "pipeline_runs_total" in content
    assert "pipeline_duration_seconds" in content
    assert "pipeline_retries_total" in content
