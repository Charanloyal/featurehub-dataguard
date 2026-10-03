"""
DataGuard Data Quality Engine Test Suite (Phase D).
Tests contract-to-expectation mapping, Great Expectations validation execution,
freshness SLAs, referential integrity, scoring, persistence, and API endpoints.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from dataguard.api.main import app
from dataguard.contracts.registry import ContractRegistryService, ContractNotFoundError
from dataguard.quality.models import (
    QualityStatus,
    QualitySeverity,
    FreshnessStatus,
    QualityRunResult,
    QualityCheckResult
)
from dataguard.quality.expectations import ContractExpectationBuilder
from dataguard.quality.freshness import FreshnessValidator
from dataguard.quality.referential import ReferentialIntegrityValidator
from dataguard.quality.datasets import DatasetCatalog
from dataguard.quality.result_store import QualityResultStore
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.service import DataQualityEngine


@pytest.fixture
def tmp_store(tmp_path):
    """Provides an isolated SQLite QualityResultStore for fast unit testing."""
    db_file = tmp_path / "test_quality.db"
    return QualityResultStore(db_path=db_file)


@pytest.fixture
def test_runner(tmp_store):
    """Provides a DataQualityRunner configured with the isolated result store."""
    registry = ContractRegistryService()
    return DataQualityRunner(registry_service=registry, result_store=tmp_store)


@pytest.fixture
def test_client():
    """FastAPI TestClient for API endpoint validation."""
    return TestClient(app)


# 1. Not-null validation
def test_not_null_validation(test_runner):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    res_clean = test_runner.run_validation("orders", df=clean_df, validate_referential=False)
    not_null_checks = [c for c in res_clean.checks if c.expectation_type == "expect_column_values_to_not_be_null"]
    assert len(not_null_checks) > 0
    assert all(c.success for c in not_null_checks)

    # Inject nulls
    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=20)
    res_bad = test_runner.run_validation("orders", df=bad_df, validate_referential=False)
    failed_not_null = [c for c in res_bad.checks if c.expectation_type == "expect_column_values_to_not_be_null" and not c.success]
    assert len(failed_not_null) > 0
    assert any(c.column == "order_total" for c in failed_not_null)


# 2. Unique validation
def test_unique_validation(test_runner):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    res_clean = test_runner.run_validation("orders", df=clean_df, validate_referential=False)
    unique_checks = [c for c in res_clean.checks if c.expectation_type == "expect_column_values_to_be_unique"]
    assert len(unique_checks) > 0
    assert all(c.success for c in unique_checks)

    bad_df = DatasetCatalog.bad_orders_duplicates(num_rows=20)
    res_bad = test_runner.run_validation("orders", df=bad_df, validate_referential=False)
    failed_unique = [c for c in res_bad.checks if c.expectation_type == "expect_column_values_to_be_unique" and not c.success]
    assert len(failed_unique) == 1
    assert failed_unique[0].column == "order_id"


# 3. Accepted values validation
def test_accepted_values(test_runner):
    clean_df = DatasetCatalog.generate_clean_dataset("payments", num_rows=20)
    res_clean = test_runner.run_validation("payments", df=clean_df, validate_referential=False)
    enum_checks = [c for c in res_clean.checks if c.expectation_type == "expect_column_values_to_be_in_set"]
    assert len(enum_checks) > 0
    assert all(c.success for c in enum_checks)

    bad_df = DatasetCatalog.bad_payments_invalid_status(num_rows=20)
    res_bad = test_runner.run_validation("payments", df=bad_df, validate_referential=False)
    failed_enum = [c for c in res_bad.checks if c.expectation_type == "expect_column_values_to_be_in_set" and not c.success]
    assert len(failed_enum) > 0
    assert any(c.column == "status" for c in failed_enum)


# 4. Numeric range validation
def test_numeric_range(test_runner):
    clean_df = DatasetCatalog.generate_clean_dataset("transactions", num_rows=20)
    res_clean = test_runner.run_validation("transactions", df=clean_df, validate_referential=False)
    range_checks = [c for c in res_clean.checks if c.expectation_type == "expect_column_values_to_be_between"]
    assert len(range_checks) > 0
    assert all(c.success for c in range_checks)

    bad_df = DatasetCatalog.bad_transactions_negative_amounts(num_rows=20)
    res_bad = test_runner.run_validation("transactions", df=bad_df, validate_referential=False)
    failed_range = [c for c in res_bad.checks if c.expectation_type == "expect_column_values_to_be_between" and not c.success]
    assert len(failed_range) > 0
    assert any(c.column == "amount" for c in failed_range)


# 5. Row count validation
def test_row_count(test_runner):
    # Contract defines min_rows: 10
    tiny_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=3)
    res_tiny = test_runner.run_validation("orders", df=tiny_df, validate_referential=False)
    row_count_check = [c for c in res_tiny.checks if c.expectation_type == "expect_table_row_count_to_be_between"]
    assert len(row_count_check) == 1
    assert not row_count_check[0].success

    normal_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=25)
    res_normal = test_runner.run_validation("orders", df=normal_df, validate_referential=False)
    normal_row_check = [c for c in res_normal.checks if c.expectation_type == "expect_table_row_count_to_be_between"]
    assert len(normal_row_check) == 1
    assert normal_row_check[0].success


# 6. Duplicate detection details
def test_duplicate_detection(test_runner):
    bad_df = DatasetCatalog.bad_orders_duplicates(num_rows=20)
    res = test_runner.run_validation("orders", df=bad_df, validate_referential=False)
    dup_check = next(c for c in res.checks if c.expectation_type == "expect_column_values_to_be_unique")
    assert not dup_check.success
    assert dup_check.status == QualityStatus.FAIL
    assert dup_check.observed_value is not None


# 7. Referential integrity valid
def test_referential_integrity():
    customers_df = pd.DataFrame({"customer_id": ["cust_001", "cust_002", "cust_003"]})
    orders_df = pd.DataFrame({"order_id": ["ord_01", "ord_02"], "customer_id": ["cust_001", "cust_002"]})

    res = ReferentialIntegrityValidator.validate_referential_integrity(
        run_id="test_run",
        child_dataset="orders",
        child_df=orders_df,
        parent_dataset="customers",
        parent_df=customers_df,
        child_fk_col="customer_id",
        parent_pk_col="customer_id"
    )
    assert res.success is True
    assert res.status == QualityStatus.PASS
    assert res.details["orphan_count"] == 0


# 8. Referential integrity orphaned fails
def test_referential_integrity_orphaned_fails():
    customers_df = pd.DataFrame({"customer_id": ["cust_001", "cust_002"]})
    orders_df = pd.DataFrame({"order_id": ["ord_01", "ord_02"], "customer_id": ["cust_001", "cust_GHOST_999"]})

    res = ReferentialIntegrityValidator.validate_referential_integrity(
        run_id="test_run",
        child_dataset="orders",
        child_df=orders_df,
        parent_dataset="customers",
        parent_df=customers_df,
        child_fk_col="customer_id",
        parent_pk_col="customer_id"
    )
    assert res.success is False
    assert res.status == QualityStatus.FAIL
    assert res.details["orphan_count"] == 1
    assert "cust_GHOST_999" in res.details["sample_orphan_keys"]


# 9. Freshness SLA evaluations
def test_freshness():
    now = datetime.now(timezone.utc)
    contract = {"dataset": "orders", "freshness_sla_minutes": 60}

    # Fresh (< 60 min)
    df_fresh = pd.DataFrame({"created_at": [now - timedelta(minutes=15)]})
    res_fresh = FreshnessValidator.evaluate_freshness(df_fresh, contract)
    assert res_fresh["status"] == FreshnessStatus.FRESH

    # Warning (60 to 120 min)
    df_warn = pd.DataFrame({"created_at": [now - timedelta(minutes=90)]})
    res_warn = FreshnessValidator.evaluate_freshness(df_warn, contract)
    assert res_warn["status"] == FreshnessStatus.WARNING

    # Stale (> 120 min)
    df_stale = pd.DataFrame({"created_at": [now - timedelta(minutes=180)]})
    res_stale = FreshnessValidator.evaluate_freshness(df_stale, contract)
    assert res_stale["status"] == FreshnessStatus.STALE


# 10. Clean dataset passes
def test_clean_dataset_passes(test_runner):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=30)
    res = test_runner.run_validation("orders", df=clean_df, validate_referential=False)
    assert res.overall_status == QualityStatus.PASS
    assert res.quality_score == 100.0
    assert res.failed_checks == 0


# 11. Bad dataset fails
def test_bad_dataset_fails(test_runner):
    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=30)
    res = test_runner.run_validation("orders", df=bad_df, validate_referential=False)
    assert res.overall_status == QualityStatus.FAIL
    assert res.failed_checks > 0
    assert res.quality_score < 100.0


# 12. Quality score formula transparency
def test_quality_score(test_runner):
    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=20)
    res = test_runner.run_validation("orders", df=bad_df, validate_referential=False)
    expected_score = round((res.passed_checks / res.total_checks) * 100.0, 2)
    assert res.quality_score == expected_score


# 13. Persistence of validation results
def test_results_persisted(test_runner, tmp_store):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    res = test_runner.run_validation("orders", df=clean_df, validate_referential=False)

    stored_run = tmp_store.get_run(res.run_id)
    assert stored_run is not None
    assert stored_run.run_id == res.run_id
    assert stored_run.dataset == "orders"
    assert stored_run.total_checks == res.total_checks
    assert len(stored_run.checks) == res.total_checks


# 14. Latest run retrieval
def test_latest_run_retrieval(test_runner, tmp_store):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    res1 = test_runner.run_validation("orders", df=clean_df, validate_referential=False)
    res2 = test_runner.run_validation("orders", df=clean_df, validate_referential=False)

    latest = tmp_store.get_latest_run("orders")
    assert latest is not None
    assert latest.run_id == res2.run_id


# 15. History retrieval
def test_history_retrieval(test_runner, tmp_store):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    test_runner.run_validation("orders", df=clean_df, validate_referential=False)
    test_runner.run_validation("orders", df=clean_df, validate_referential=False)
    test_runner.run_validation("orders", df=clean_df, validate_referential=False)

    history = tmp_store.get_history("orders", limit=10)
    assert len(history) == 3


# 16. Granular check results filtering
def test_list_results_filtering(test_runner, tmp_store):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    test_runner.run_validation("orders", df=clean_df, validate_referential=False)

    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=20)
    test_runner.run_validation("orders", df=bad_df, validate_referential=False)

    pass_results = tmp_store.list_results(dataset="orders", status="PASS")
    fail_results = tmp_store.list_results(dataset="orders", status="FAIL")

    assert len(pass_results) > 0
    assert len(fail_results) > 0
    assert all(r["status"] == "PASS" for r in pass_results)
    assert all(r["status"] == "FAIL" for r in fail_results)


# 17. Quality summary calculation
def test_quality_summary_dynamic(test_runner, tmp_store):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    test_runner.run_validation("orders", df=clean_df, validate_referential=False)

    summary = tmp_store.get_summary(total_registered_datasets=25)
    assert summary.datasets_checked >= 1
    assert summary.total_checks > 0
    assert summary.checks_passed > 0
    assert summary.overall_quality_score > 0.0


# 18. Error handling: unknown contract
def test_error_handling_unknown_dataset(test_runner):
    with pytest.raises(ContractNotFoundError):
        test_runner.run_validation("non_existent_dataset_xyz")


# 19. Error handling: missing column in dataset
def test_error_handling_missing_column(test_runner):
    clean_df = DatasetCatalog.generate_clean_dataset("orders", num_rows=20)
    # Drop required column 'currency'
    df_missing_col = clean_df.drop(columns=["currency"])
    res = test_runner.run_validation("orders", df=df_missing_col, validate_referential=False)
    assert res.overall_status == QualityStatus.FAIL
    col_exist_check = [c for c in res.checks if c.column == "currency" and c.expectation_type == "expect_column_to_exist"]
    assert len(col_exist_check) == 1
    assert not col_exist_check[0].success


# 20. Error handling: invalid payload type
def test_error_handling_invalid_dataframe(test_runner):
    with pytest.raises(ValueError):
        test_runner.run_validation("orders", df="not_a_dataframe")


# 21. Check severity categorization
def test_severity_categorization():
    assert ContractExpectationBuilder.get_expectation_severity("expect_column_to_exist") == QualitySeverity.CRITICAL
    assert ContractExpectationBuilder.get_expectation_severity("expect_column_values_to_not_be_null") == QualitySeverity.HIGH
    assert ContractExpectationBuilder.get_expectation_severity("expect_column_values_to_be_unique") == QualitySeverity.HIGH
    assert ContractExpectationBuilder.get_expectation_severity("expect_column_values_to_be_in_set") == QualitySeverity.MEDIUM


# 22. DatasetCatalog realistic dataset loading
def test_dataset_catalog_realistic_entities():
    for ds in ["customers", "accounts", "merchants", "products", "orders", "order_items", "payments", "transactions", "fraud_events"]:
        df = DatasetCatalog.load_dataset(ds)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0


# 23. Stale dataset generation
def test_stale_dataset_fixture():
    df_stale = DatasetCatalog.stale_dataset("orders", hours_old=72)
    assert isinstance(df_stale, pd.DataFrame)
    now = datetime.now(timezone.utc)
    ts = pd.to_datetime(df_stale["created_at"].iloc[0], utc=True)
    assert (now - ts).total_seconds() > 3600 * 48


# 24. FastAPI POST /quality/validate/{dataset}
def test_api_validate_dataset(test_client):
    response = test_client.post("/quality/validate/orders")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset"] == "orders"
    assert "overall_status" in data
    assert "quality_score" in data
    assert "checks" in data


# 25. FastAPI POST /quality/validate with custom payload
def test_api_validate_dataset_with_custom_payload(test_client):
    payload = [
        {"order_id": "ord_9901", "customer_id": "cust_000001", "order_total": 150.0, "currency": "USD", "created_at": datetime.now(timezone.utc).isoformat()},
        {"order_id": "ord_9902", "customer_id": "cust_000001", "order_total": 250.0, "currency": "USD", "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    response = test_client.post("/quality/validate/orders", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 2


# 26. FastAPI GET /quality/results
def test_api_quality_results(test_client):
    response = test_client.get("/quality/results?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# 27. FastAPI GET /quality/summary
def test_api_quality_summary(test_client):
    response = test_client.get("/quality/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_datasets" in data
    assert "overall_quality_score" in data


# 28. FastAPI GET /quality/{dataset}/latest and /history
def test_api_quality_latest_and_history(test_client):
    # Validate first to ensure a record exists
    test_client.post("/quality/validate/orders")

    res_latest = test_client.get("/quality/orders/latest")
    assert res_latest.status_code == 200
    assert res_latest.json()["dataset"] == "orders"

    res_hist = test_client.get("/quality/orders/history")
    assert res_hist.status_code == 200
    assert isinstance(res_hist.json(), list)


# 29. FastAPI 404 for unknown dataset
def test_api_404_unknown_dataset(test_client):
    response = test_client.post("/quality/validate/totally_unknown_dataset_xyz")
    assert response.status_code == 404


# 30. Prometheus metrics export includes quality metrics
def test_prometheus_metrics_export(test_client):
    response = test_client.get("/metrics")
    assert response.status_code == 200
    content = response.text
    assert "quality_validation_total" in content
    assert "quality_checks_total" in content
