"""
Phase I Comprehensive Verification Test Suite:
FeatureHub + DataGuard Integrated Platform Flow.
Tests both the End-to-End Success Path (Ingestion -> Compute -> Contracts -> Diff -> Quality -> Lineage -> Offline -> Redis -> ML)
and the Failure Paths (Bad Data / Breaking Schema / Stale Features -> FAILED -> OpenLineage FAIL + Incident).
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from featurehub.integration.service import FeatureHubDataGuardIntegrator
from featurehub.integration.models import StageStatus, IntegrationStage
from featurehub.api.main import app
from featurehub.online_store.redis_store import RedisOnlineStore
from dataguard.contracts.registry import ContractRegistryService
from dataguard.incidents.repository import IncidentRepository
from dataguard.lineage.repository import LineageRepository

client = TestClient(app)


@pytest.fixture(scope="module")
def integrator():
    return FeatureHubDataGuardIntegrator()


def test_e2e_integration_happy_path(integrator):
    """Full 11-stage flow completes with StageStatus.SUCCESS and valid ML prediction."""
    res = integrator.run_e2e_pipeline(target_customer_id="cust_000001")
    assert res.status == StageStatus.SUCCESS
    assert res.error_message is None
    assert len(res.stages) == 11
    assert all(s.status == StageStatus.SUCCESS for s in res.stages)
    assert res.features_computed_count > 0
    assert res.records_materialized_count > 0
    assert res.quality_score is not None and res.quality_score >= 90.0
    assert res.ml_prediction is not None
    assert "risk_score" in res.ml_prediction
    assert "prediction" in res.ml_prediction


def test_e2e_data_source_stage_success(integrator):
    """Stage 1: verifies source parquet files exist and are readable."""
    res = integrator.run_e2e_pipeline()
    s1 = res.get_stage(IntegrationStage.DATA_SOURCE)
    assert s1 is not None
    assert s1.status == StageStatus.SUCCESS
    assert "transactions_path" in s1.details
    assert "merchants_path" in s1.details


def test_e2e_feature_computation_stage(integrator):
    """Stage 2: computes offline customer and merchant features."""
    res = integrator.run_e2e_pipeline()
    s2 = res.get_stage(IntegrationStage.FEATURE_COMPUTATION)
    assert s2 is not None
    assert s2.status == StageStatus.SUCCESS
    assert s2.details["rows_computed"] >= 100
    assert "cust_txn_count_24h" in s2.details["feature_columns"]


def test_e2e_contract_validation_stage(integrator):
    """Stage 3: verifies data contract specification and structural validity."""
    res = integrator.run_e2e_pipeline()
    s3 = res.get_stage(IntegrationStage.CONTRACT_VALIDATION)
    assert s3 is not None
    assert s3.status == StageStatus.SUCCESS
    assert s3.details["owner"] == "featurestore-team"


def test_e2e_schema_validation_stage(integrator):
    """Stage 4: validates schema backward compatibility against registered contract."""
    res = integrator.run_e2e_pipeline()
    s4 = res.get_stage(IntegrationStage.SCHEMA_VALIDATION)
    assert s4 is not None
    assert s4.status == StageStatus.SUCCESS
    assert res.schema_compatible is True


def test_e2e_quality_validation_great_expectations(integrator):
    """Stage 5: Great Expectations suite passes with high quality score."""
    res = integrator.run_e2e_pipeline()
    s5 = res.get_stage(IntegrationStage.DATA_QUALITY)
    assert s5 is not None
    assert s5.status == StageStatus.SUCCESS
    assert s5.details["quality_score"] >= 90.0


def test_e2e_openlineage_emission_lifecycle(integrator):
    """Stage 6: OpenLineage complete run emitted."""
    res = integrator.run_e2e_pipeline()
    s6 = res.get_stage(IntegrationStage.OPENLINEAGE)
    assert s6 is not None
    assert s6.status == StageStatus.SUCCESS
    assert res.openlineage_run_id is not None

    lineage_repo = LineageRepository()
    run = lineage_repo.get_run(res.openlineage_run_id)
    assert run is not None
    assert run.status.value.upper() == "COMPLETE"


def test_e2e_airflow_pipeline_tracking(integrator):
    """Stage 7: Airflow pipeline run saved in PostgreSQL pipeline_runs."""
    res = integrator.run_e2e_pipeline()
    s7 = res.get_stage(IntegrationStage.AIRFLOW_ORCHESTRATION)
    assert s7 is not None
    assert s7.status == StageStatus.SUCCESS

    runs = integrator.pipeline_repo.list_runs(pipeline_id="integrated_feature_store_pipeline", limit=5)
    matching = [r for r in runs if r.run_id == res.run_id]
    assert len(matching) == 1
    assert matching[0].status.value == "SUCCESS"


def test_e2e_offline_store_parquet_persistence(integrator):
    """Stage 8: offline feature store parquet file updated."""
    res = integrator.run_e2e_pipeline()
    s8 = res.get_stage(IntegrationStage.OFFLINE_STORE)
    assert s8 is not None
    assert s8.status == StageStatus.SUCCESS
    assert s8.details["rows_saved"] > 0


def test_e2e_redis_materialization(integrator):
    """Stage 9: features materialized into Redis online store."""
    res = integrator.run_e2e_pipeline()
    s9 = res.get_stage(IntegrationStage.MATERIALIZATION)
    assert s9 is not None
    assert s9.status == StageStatus.SUCCESS
    assert res.records_materialized_count > 0


def test_e2e_redis_online_feature_retrieval(integrator):
    """Stage 10: retrieves online features from Redis for entity."""
    res = integrator.run_e2e_pipeline(target_customer_id="cust_000001")
    s10 = res.get_stage(IntegrationStage.REDIS_ONLINE_STORE)
    assert s10 is not None
    assert s10.status == StageStatus.SUCCESS
    assert s10.details["retrieved"] is True


def test_e2e_real_time_ml_prediction_inference(integrator):
    """Stage 11: Real-time fraud prediction computed using Redis features."""
    res = integrator.run_e2e_pipeline(target_customer_id="cust_000001")
    s11 = res.get_stage(IntegrationStage.ML_PREDICTION)
    assert s11 is not None
    assert s11.status == StageStatus.SUCCESS
    pred = res.ml_prediction
    assert pred is not None
    assert 0.0 <= pred["risk_score"] <= 1.0
    assert pred["prediction"] in [0, 1]
    assert pred["model_version"] is not None


def test_e2e_failure_path_breaking_schema(integrator):
    """Failure Path: BREAKING_SCHEMA fails at Stage 4, halts pipeline, skips materialization."""
    res = integrator.run_e2e_pipeline(inject_anomaly="BREAKING_SCHEMA")
    assert res.status == StageStatus.FAILED
    assert res.schema_compatible is False
    assert "schema" in res.error_message.lower()

    s4 = res.get_stage(IntegrationStage.SCHEMA_VALIDATION)
    assert s4.status == StageStatus.FAILED

    # Downstream stages must be SKIPPED
    s8 = res.get_stage(IntegrationStage.OFFLINE_STORE)
    s9 = res.get_stage(IntegrationStage.MATERIALIZATION)
    s11 = res.get_stage(IntegrationStage.ML_PREDICTION)
    assert s8.status == StageStatus.SKIPPED
    assert s9.status == StageStatus.SKIPPED
    assert s11.status == StageStatus.SKIPPED
    assert res.ml_prediction is None


def test_e2e_failure_path_null_violation(integrator):
    """Failure Path: NULL_VIOLATION fails at Stage 5 (Data Quality)."""
    res = integrator.run_e2e_pipeline(inject_anomaly="NULL_VIOLATION")
    assert res.status == StageStatus.FAILED
    s5 = res.get_stage(IntegrationStage.DATA_QUALITY)
    assert s5.status == StageStatus.FAILED
    assert res.ml_prediction is None


def test_e2e_failure_path_range_violation(integrator):
    """Failure Path: RANGE_VIOLATION fails at Stage 5 (Data Quality)."""
    res = integrator.run_e2e_pipeline(inject_anomaly="RANGE_VIOLATION")
    assert res.status == StageStatus.FAILED
    s5 = res.get_stage(IntegrationStage.DATA_QUALITY)
    assert s5.status == StageStatus.FAILED
    assert res.ml_prediction is None


def test_e2e_failure_path_stale_features(integrator):
    """Failure Path: STALE_FEATURES triggers freshness SLA breach and halts pipeline."""
    res = integrator.run_e2e_pipeline(inject_anomaly="STALE_FEATURES")
    assert res.status == StageStatus.FAILED
    s5 = res.get_stage(IntegrationStage.DATA_QUALITY)
    assert s5.status == StageStatus.FAILED
    assert res.ml_prediction is None


def test_e2e_failure_openlineage_failed_event(integrator):
    """Failure Path: OpenLineage records event with status FAIL."""
    res = integrator.run_e2e_pipeline(inject_anomaly="BREAKING_SCHEMA")
    lineage_repo = LineageRepository()
    run = lineage_repo.get_run(res.openlineage_run_id)
    assert run is not None
    assert run.status.value.upper() == "FAIL"


def test_e2e_failure_incident_creation_and_owner_routing(integrator):
    """Failure Path: Operational incident created with owner featurestore-team and proper severity."""
    res = integrator.run_e2e_pipeline(inject_anomaly="BREAKING_SCHEMA")
    assert res.incident_id is not None
    assert res.incident_owner == "featurestore-team"
    assert res.incident_severity == "CRITICAL"

    # Verify persistent incident in PostgreSQL
    inc_repo = IncidentRepository()
    inc = inc_repo.get_incident(res.incident_id)
    assert inc is not None
    assert inc.owner == "featurestore-team"
    assert inc.severity.value == "CRITICAL"
    assert inc.status.value == "OPEN"


def test_e2e_failure_online_store_protection(integrator):
    """Corrupted features never overwrite existing valid online features in Redis."""
    # Seed a known good customer in Redis
    store = RedisOnlineStore()
    store.put_online_features(
        entity_name="customer",
        entity_id="cust_protect_test",
        feature_vector={"cust_txn_count_24h": 42},
        feature_timestamp="2026-10-04T00:00:00Z"
    )

    # Run failing pipeline with anomaly
    integrator.run_e2e_pipeline(
        target_customer_id="cust_protect_test",
        inject_anomaly="BREAKING_SCHEMA"
    )

    # Check that Redis features remain untampered
    data = store.get_online_features("customer", "cust_protect_test")
    assert data is not None
    assert data["features"]["cust_txn_count_24h"] == 42


def test_e2e_fastapi_integrated_run_endpoint():
    """Test POST /pipeline/integrated-run via FastAPI TestClient."""
    resp = client.post("/pipeline/integrated-run", json={
        "dataset_name": "customer_features",
        "target_customer_id": "cust_0001",
        "inject_anomaly": None
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert len(data["stages"]) == 11
    assert data["ml_prediction"] is not None


def test_e2e_fastapi_latest_run_endpoint():
    """Test GET /pipeline/integrated-run/latest via FastAPI TestClient."""
    resp = client.get("/pipeline/integrated-run/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["pipeline_id"] == "integrated_feature_store_pipeline"


def test_e2e_allow_breaking_override(integrator):
    """When allow_breaking=True, breaking schema drift does not halt Stage 4."""
    res = integrator.run_e2e_pipeline(
        inject_anomaly="BREAKING_SCHEMA",
        allow_breaking=True
    )
    s4 = res.get_stage(IntegrationStage.SCHEMA_VALIDATION)
    # Schema validation stage passes under override
    assert s4.status == StageStatus.SUCCESS
