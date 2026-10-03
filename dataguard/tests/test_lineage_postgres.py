"""
DataGuard OpenLineage Live PostgreSQL 16 Integration Tests.
Executes real pipeline lineage, column mappings, and incident references against the live PostgreSQL container.
"""

import os
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import text

from dataguard.contracts.registry import get_default_db_url
from dataguard.lineage.repository import LineageRepository
from dataguard.lineage.collector import LineageCollector
from dataguard.lineage.models import LineageStatus
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.manager import IncidentManager
from dataguard.incidents.models import IncidentSeverity
from dataguard.quality.models import QualityCheckResult, QualityStatus


@pytest.fixture(scope="module")
def pg_repo():
    db_url = get_default_db_url()
    try:
        repo = LineageRepository(db_url=db_url)
        with repo.engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return repo
    except Exception as e:
        pytest.skip(f"Live PostgreSQL not reachable: {e}")


@pytest.fixture(scope="module")
def pg_collector(pg_repo: LineageRepository):
    return LineageCollector(repository=pg_repo)


def test_postgres_lineage_connectivity(pg_repo: LineageRepository):
    with pg_repo.engine.connect() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM lineage_datasets;")).scalar()
        assert res is not None
        assert res >= 0


def test_postgres_end_to_end_lineage_pipeline(pg_collector: LineageCollector, pg_repo: LineageRepository):
    test_pipe_id = f"test_pipe_{uuid.uuid4().hex[:8]}"
    in_ds = f"pg_test_in_{uuid.uuid4().hex[:6]}"
    out_ds = f"pg_test_out_{uuid.uuid4().hex[:6]}"

    # Start run
    run = pg_collector.start_run(
        pipeline_id=test_pipe_id,
        inputs=[in_ds],
        job_name=test_pipe_id
    )
    assert run.status == LineageStatus.START

    # Complete run
    completed = pg_collector.complete_run(
        run_id=run.run_id,
        pipeline_id=test_pipe_id,
        outputs=[out_ds],
        column_mappings=[{
            "source_dataset": in_ds,
            "source_column": "raw_val",
            "target_dataset": out_ds,
            "target_column": "clean_val",
            "transformation": "CLEANSE_WHITESPACE"
        }]
    )
    assert completed.status == LineageStatus.COMPLETE

    # Verify persistence in PostgreSQL
    fetched_run = pg_repo.get_run(run.run_id)
    assert fetched_run is not None
    assert fetched_run.status == LineageStatus.COMPLETE
    assert in_ds in fetched_run.inputs
    assert out_ds in fetched_run.outputs


def test_postgres_column_lineage_persistence(pg_repo: LineageRepository, pg_collector: LineageCollector):
    pipe_id = "live_pg_compute"
    run = pg_collector.start_run(pipeline_id=pipe_id, inputs=["postgres.transactions"])
    t_ds = f"target_col_ds_{uuid.uuid4().hex[:6]}"

    pg_repo.record_column_mapping(
        run_id=run.run_id,
        source_dataset="postgres.transactions",
        source_column="amount",
        target_dataset=t_ds,
        target_column="avg_amt_7d",
        transformation="AVG(amount) over 7 days",
        pipeline_id=pipe_id
    )

    cols = pg_repo.get_column_lineage(t_ds)
    assert len(cols) == 1
    assert cols[0].target_column == "avg_amt_7d"
    assert cols[0].transformation == "AVG(amount) over 7 days"


def test_postgres_upstream_downstream_traversal(pg_collector: LineageCollector, pg_repo: LineageRepository):
    d_a = f"ds_hop_a_{uuid.uuid4().hex[:6]}"
    d_b = f"ds_hop_b_{uuid.uuid4().hex[:6]}"
    d_c = f"ds_hop_c_{uuid.uuid4().hex[:6]}"
    p_1 = f"pipe_hop_1_{uuid.uuid4().hex[:6]}"
    p_2 = f"pipe_hop_2_{uuid.uuid4().hex[:6]}"

    # A -> p_1 -> B
    r1 = pg_collector.start_run(pipeline_id=p_1, inputs=[d_a])
    pg_collector.complete_run(run_id=r1.run_id, outputs=[d_b], pipeline_id=p_1)

    # B -> p_2 -> C
    r2 = pg_collector.start_run(pipeline_id=p_2, inputs=[d_b])
    pg_collector.complete_run(run_id=r2.run_id, outputs=[d_c], pipeline_id=p_2)

    # Verify upstream from C reaches A and B
    up = pg_repo.get_upstream(d_c, max_depth=5)
    assert d_b in up.upstream_datasets
    assert d_a in up.upstream_datasets

    # Verify downstream from A reaches B and C
    down = pg_repo.get_downstream(d_a, max_depth=5)
    assert d_b in down.downstream_datasets
    assert d_c in down.downstream_datasets


def test_postgres_incident_lineage_correlation():
    db_url = get_default_db_url()
    inc_repo = IncidentRepository(db_url=db_url)
    inc_mgr = IncidentManager(repository=inc_repo)

    unique_run_id = f"pg_run_fail_{uuid.uuid4().hex[:10]}"
    fail_check = QualityCheckResult(
        run_id=unique_run_id,
        dataset="orders",
        check_name=f"order_amount_bounds_{uuid.uuid4().hex[:6]}",
        column="order_amount",
        expectation_type="expect_column_values_to_be_between",
        status=QualityStatus.FAIL,
        severity=IncidentSeverity.CRITICAL,
        observed_value="-199.99",
        expected_value="[0, 50000]",
        success=False,
        pipeline="live_postgres_order_quality"
    )

    inc = inc_mgr.handle_check_failure(
        check=fail_check,
        dataset="orders",
        pipeline="live_postgres_order_quality"
    )

    assert inc is not None
    assert inc.run_id == unique_run_id
    assert inc.pipeline_id == "live_postgres_order_quality"

    # Query directly from PostgreSQL incidents table
    fetched = inc_repo.get_incident(inc.incident_id)
    assert fetched is not None
    assert fetched.run_id == unique_run_id
    assert fetched.pipeline_id == "live_postgres_order_quality"
