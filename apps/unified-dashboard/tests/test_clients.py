"""
Tests for Unified Dashboard Client Layer
Validates FeatureHubClient, DataGuardClient, and PlatformClient against real backends and graceful fallbacks.
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.unified_dashboard.services.featurehub_client import FeatureHubClient
from apps.unified_dashboard.services.dataguard_client import DataGuardClient
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.config import DEFAULT_ENTITY_ID


@pytest.fixture
def fh_client():
    return FeatureHubClient()


@pytest.fixture
def dg_client():
    return DataGuardClient()


@pytest.fixture
def platform_client():
    return PlatformClient()


class TestFeatureHubClient:
    def test_health(self, fh_client):
        res = fh_client.health()
        assert res["status"] in ["HEALTHY", "DEGRADED"]
        assert "latency_ms" in res
        assert "mode" in res

    def test_list_features(self, fh_client):
        features = fh_client.list_features()
        assert len(features) >= 120, f"Expected at least 120 features, got {len(features)}"
        sample = features[0]
        assert "feature_name" in sample
        assert "entity_type" in sample
        assert "feature_group" in sample

    def test_list_groups(self, fh_client):
        groups = fh_client.list_groups()
        assert len(groups) >= 5, f"Expected at least 5 feature groups, got {len(groups)}"

    def test_get_feature(self, fh_client):
        feat = fh_client.get_feature("cust_txn_count_1h")
        assert feat is not None
        assert feat["entity_type"] == "customer"
        assert feat["data_type"] in ["INT64", "integer", "int"]

    def test_test_online_latency(self, fh_client):
        res = fh_client.test_online_latency(entity_id=DEFAULT_ENTITY_ID, samples=3)
        assert res["samples"] == 3
        assert res["p50_ms"] >= 0.0
        assert "mean_ms" in res

    def test_predict_fraud_risk(self, fh_client):
        res = fh_client.predict(
            customer_id=DEFAULT_ENTITY_ID,
            transaction_amount=150.0,
            merchant_id="merch_000042",
            channel="WEB"
        )
        assert "risk_score" in res
        assert 0.0 <= res["risk_score"] <= 1.0
        assert res["prediction"] in [0, 1]
        assert "model_version" in res
        assert "features_used" in res


class TestDataGuardClient:
    def test_health(self, dg_client):
        res = dg_client.health()
        assert res["status"] in ["HEALTHY", "DEGRADED"]
        assert "latency_ms" in res

    def test_list_contracts(self, dg_client):
        contracts = dg_client.list_contracts()
        assert len(contracts) >= 25, f"Expected at least 25 production contracts, got {len(contracts)}"

    def test_get_contract(self, dg_client):
        c = dg_client.get_contract("customer_features")
        assert c is not None
        assert c["dataset"] == "customer_features"
        assert len(c.get("columns", [])) >= 5

    def test_diff_schemas_safe_and_breaking(self, dg_client):
        import copy
        base = dg_client.get_contract("customer_features")
        target_safe = copy.deepcopy(base)
        target_safe["columns"].append({"name": "new_score", "type": "float", "nullable": True})
        res_safe = dg_client.diff_schemas(base, target_safe)
        assert res_safe["compatibility"] == "SAFE"

        target_breaking = copy.deepcopy(base)
        target_breaking["columns"].pop(-1)
        res_breaking = dg_client.diff_schemas(base, target_breaking)
        assert res_breaking["compatibility"] == "BREAKING"
        res_breaking = dg_client.diff_schemas(base, target_breaking)
        assert res_breaking["compatibility"] == "BREAKING"

    def test_list_incidents(self, dg_client):
        incidents = dg_client.list_incidents(limit=10)
        assert isinstance(incidents, list)

    def test_get_quality_summary(self, dg_client):
        summary = dg_client.get_quality_summary()
        assert "total_runs" in summary
        assert "avg_pass_rate" in summary
        assert summary["total_runs"] >= 0

    def test_column_lineage(self, dg_client):
        col_lin = dg_client.get_column_lineage("customer_features")
        assert len(col_lin) >= 1
        sample = col_lin[0]
        assert "target_column" in sample
        assert "source_columns" in sample
        assert "transformation" in sample


class TestPlatformClient:
    def test_get_platform_overview(self, platform_client):
        ov = platform_client.get_platform_overview()
        assert ov["feature_count"] >= 120
        assert ov["feature_groups_count"] >= 5
        assert ov["contracts_count"] >= 25
        assert ov["quality_total_runs"] >= 0
        assert "open_incidents" in ov
        assert "latest_pipeline_status" in ov

    def test_get_system_health(self, platform_client):
        checks = platform_client.get_system_health()
        assert len(checks) == 6
        subsystems = [c["service"] for c in checks]
        assert "PostgreSQL 16" in subsystems
        assert "Redis 7.2" in subsystems
        assert "Apache Airflow 2.9" in subsystems
        assert "FeatureHub API" in subsystems
        assert "DataGuard API" in subsystems
        assert "Prometheus" in subsystems

    def test_load_benchmarks(self, platform_client):
        benchmarks = platform_client.load_benchmarks()
        assert "integrated" in benchmarks
        int_bench = benchmarks["integrated"]
        assert "success_path" in int_bench
        assert "stages_breakdown" in int_bench["success_path"]
        assert "failure_paths" in int_bench

    def test_run_demo_scenario_pit(self, platform_client):
        res = platform_client.run_demo_scenario("DEMO 6: Point-in-Time Leakage Prevention")
        assert res["status"] == "LEAKAGE PREVENTED"
        assert res["duration_ms"] > 0
        assert "pit_feature_count" in res
