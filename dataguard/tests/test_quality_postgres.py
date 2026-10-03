"""
DataGuard Quality Engine Live PostgreSQL Integration Test.
Validates the complete end-to-end data quality pipeline against live PostgreSQL Docker container:
Real dataset -> Contract -> Expectation Builder -> Great Expectations -> Runner -> PostgreSQL Store.
MUST fail if PostgreSQL container is unavailable.
"""

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from dataguard.contracts.registry import ContractRegistryService, get_default_db_url
from dataguard.quality.result_store import QualityResultStore
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.datasets import DatasetCatalog
from dataguard.quality.models import QualityStatus
from dataguard.api.main import app


@pytest.fixture(scope="module")
def postgres_quality_runner():
    """
    Initializes DataQualityRunner with real PostgreSQL connection.
    Fails immediately if PostgreSQL container is not reachable.
    """
    url = get_default_db_url()
    store = QualityResultStore(db_url=url)

    # Fail if PostgreSQL is unavailable
    try:
        with store.engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
            assert val == 1, "Failed to execute query on PostgreSQL"
    except Exception as e:
        pytest.fail(f"Real PostgreSQL database is not reachable at {url}: {e}")

    assert store.engine.name == "postgresql", f"Expected 'postgresql' dialect, got '{store.engine.name}'"

    registry = ContractRegistryService(db_url=url)
    return DataQualityRunner(registry_service=registry, result_store=store), store


def test_1_postgres_quality_connectivity(postgres_quality_runner):
    """Proves PostgreSQL container is running and has quality tables created."""
    runner, store = postgres_quality_runner
    with store.engine.connect() as conn:
        res = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('quality_runs', 'quality_results');
        """)).fetchall()
        tables = [r[0] for r in res]
        assert "quality_runs" in tables, "Table 'quality_runs' missing from PostgreSQL"
        assert "quality_results" in tables, "Table 'quality_results' missing from PostgreSQL"


def test_2_e2e_quality_validation_persists_to_postgres(postgres_quality_runner):
    """
    Executes full Great Expectations validation against real dataset,
    and proves records are persisted into PostgreSQL quality_runs and quality_results.
    """
    runner, store = postgres_quality_runner

    # Load real dataset
    clean_orders = DatasetCatalog.generate_clean_dataset("orders", num_rows=25)

    # Run validation
    result = runner.run_validation(
        dataset_name="orders",
        df=clean_orders,
        pipeline="postgres_integration_test",
        validate_referential=False
    )

    assert result.overall_status == QualityStatus.PASS
    assert result.total_checks > 0
    assert result.quality_score == 100.0

    # Verify directly via SQL in PostgreSQL
    with store.engine.connect() as conn:
        run_row = conn.execute(
            text("SELECT run_id, dataset_name, overall_status, total_checks, passed_checks, quality_score FROM quality_runs WHERE run_id = :rid"),
            {"rid": result.run_id}
        ).fetchone()

        assert run_row is not None, f"Run {result.run_id} was not persisted in PostgreSQL quality_runs"
        assert run_row[0] == result.run_id
        assert run_row[1] == "orders"
        assert run_row[2] == "PASS"
        assert run_row[3] == result.total_checks
        assert run_row[4] == result.passed_checks
        assert float(run_row[5]) == 100.0

        # Verify child checks in quality_results
        checks_count = conn.execute(
            text("SELECT count(*) FROM quality_results WHERE run_id = :rid"),
            {"rid": result.run_id}
        ).scalar()

        assert checks_count == result.total_checks, f"Expected {result.total_checks} check records in PostgreSQL, found {checks_count}"


def test_3_postgres_bad_dataset_failure_recorded(postgres_quality_runner):
    """Proves failures are accurately captured and recorded in PostgreSQL."""
    runner, store = postgres_quality_runner

    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=25)
    bad_result = runner.run_validation(
        dataset_name="orders",
        df=bad_df,
        pipeline="postgres_failure_test",
        validate_referential=False
    )

    assert bad_result.overall_status == QualityStatus.FAIL
    assert bad_result.failed_checks > 0

    with store.engine.connect() as conn:
        run_row = conn.execute(
            text("SELECT overall_status, failed_checks FROM quality_runs WHERE run_id = :rid"),
            {"rid": bad_result.run_id}
        ).fetchone()

        assert run_row is not None
        assert run_row[0] == "FAIL"
        assert run_row[1] > 0


def test_4_postgres_retrieval_and_summary(postgres_quality_runner):
    """Proves latest run and dynamic summary are accurately calculated from PostgreSQL."""
    runner, store = postgres_quality_runner

    latest = store.get_latest_run("orders")
    assert latest is not None
    assert latest.dataset == "orders"

    summary = store.get_summary()
    assert summary.datasets_checked >= 1
    assert summary.total_checks > 0
    assert summary.checks_passed > 0
    assert summary.overall_quality_score > 0.0


def test_5_api_e2e_postgres():
    """Proves FastAPI reads live data persisted in PostgreSQL."""
    client = TestClient(app)

    res_sum = client.get("/quality/summary")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert data_sum["datasets_checked"] >= 1

    res_latest = client.get("/quality/orders/latest")
    assert res_latest.status_code == 200
    data_latest = res_latest.json()
    assert data_latest["dataset"] == "orders"
