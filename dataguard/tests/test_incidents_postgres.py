"""
DataGuard Incident Management PostgreSQL Integration Tests.
Tests real end-to-end integration against the live PostgreSQL Docker container:
Failing Dataset -> Great Expectations -> Incident Creation -> PostgreSQL Persistence -> API Lifecycle.
MUST fail if PostgreSQL container is unreachable.
"""

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from dataguard.contracts.registry import ContractRegistryService, get_default_db_url
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.datasets import DatasetCatalog
from dataguard.quality.models import QualityStatus
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.manager import IncidentManager
from dataguard.incidents.models import IncidentStatus, IncidentSeverity
from dataguard.api.main import app


@pytest.fixture(scope="module")
def postgres_incident_stack():
    """
    Connects IncidentRepository, IncidentManager, and DataQualityRunner directly to real PostgreSQL.
    Fails immediately if PostgreSQL is not reachable.
    """
    url = get_default_db_url()
    repo = IncidentRepository(db_url=url)

    # Fail if PostgreSQL is down
    try:
        with repo.engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
            assert val == 1
    except Exception as e:
        pytest.fail(f"Real PostgreSQL database is not reachable at {url}: {e}")

    assert repo.engine.name == "postgresql", f"Expected 'postgresql' dialect, got '{repo.engine.name}'"

    registry = ContractRegistryService(db_url=url)
    mgr = IncidentManager(repository=repo, registry_service=registry)
    runner = DataQualityRunner(registry_service=registry, incident_manager=mgr)

    return mgr, runner, repo


def test_1_postgres_incidents_table_exists(postgres_incident_stack):
    """Proves incidents and incident_events tables exist in live PostgreSQL."""
    mgr, runner, repo = postgres_incident_stack
    with repo.engine.connect() as conn:
        res = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('incidents', 'incident_events');
        """)).fetchall()
        tables = [r[0] for r in res]
        assert "incidents" in tables, "Table 'incidents' missing from PostgreSQL"
        assert "incident_events" in tables, "Table 'incident_events' missing from PostgreSQL"


def test_2_e2e_quality_failure_to_postgres_incident(postgres_incident_stack):
    """
    Proves real quality failure generates an incident in PostgreSQL,
    which is then acknowledged and resolved with full audit logging.
    """
    mgr, runner, repo = postgres_incident_stack

    # 1. Generate bad dataset
    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=25)

    # 2. Run Great Expectations validation
    val_res = runner.run_validation("orders", df=bad_df, validate_referential=False, create_incidents=True)
    assert val_res.overall_status == QualityStatus.FAIL

    # 3. Verify incident created in PostgreSQL via direct SQL query
    with repo.engine.connect() as conn:
        inc_row = conn.execute(text("""
            SELECT incident_id, dataset, status, severity, owner, failure_signature
            FROM incidents 
            WHERE dataset = 'orders' 
            AND status = 'OPEN'
            ORDER BY created_at DESC 
            LIMIT 1
        """)).fetchone()

        assert inc_row is not None, "No OPEN incident found in PostgreSQL for orders"
        incident_id = inc_row[0]
        assert inc_row[1] == "orders"
        assert inc_row[2] == "OPEN"
        assert inc_row[4] == "e-commerce-data-team"

    # 4. Acknowledge in PostgreSQL
    acked = mgr.acknowledge_incident(incident_id, actor="lead_sre", notes="Triaging database null spike")
    assert acked.status == IncidentStatus.ACKNOWLEDGED
    assert acked.acknowledged_at is not None

    # 5. Resolve in PostgreSQL
    resolved = mgr.resolve_incident(incident_id, actor="lead_sre", notes="Upstream schema issue resolved")
    assert resolved.status == IncidentStatus.RESOLVED
    assert resolved.resolved_at is not None

    # 6. Verify audit trail in PostgreSQL
    events = mgr.get_events(incident_id)
    assert len(events) >= 3
    assert events[0].event_type.value == "INCIDENT_CREATED"
    assert events[1].event_type.value == "INCIDENT_ACKNOWLEDGED"
    assert events[2].event_type.value == "INCIDENT_RESOLVED"


def test_3_postgres_deduplication(postgres_incident_stack):
    """Proves duplicate active quality failures do NOT spawn duplicate incidents in PostgreSQL."""
    mgr, runner, repo = postgres_incident_stack

    bad_df = DatasetCatalog.bad_payments_invalid_status(num_rows=20)

    # First execution creates incident
    _ = runner.run_validation("payments", df=bad_df, validate_referential=False, create_incidents=True)

    with repo.engine.connect() as conn:
        count_1 = conn.execute(text("SELECT count(*) FROM incidents WHERE dataset = 'payments' AND status = 'OPEN'")).scalar()

    # Second execution of identical failure
    _ = runner.run_validation("payments", df=bad_df, validate_referential=False, create_incidents=True)

    with repo.engine.connect() as conn:
        count_2 = conn.execute(text("SELECT count(*) FROM incidents WHERE dataset = 'payments' AND status = 'OPEN'")).scalar()

    assert count_1 == count_2, f"Expected duplicate incident suppression in PostgreSQL, but count changed from {count_1} to {count_2}"


def test_4_postgres_summary_and_mtta_mttr(postgres_incident_stack):
    """Proves dynamic incident summary and MTTA/MTTR calculations over real PostgreSQL data."""
    mgr, runner, repo = postgres_incident_stack

    summary = mgr.get_summary()
    assert summary.total_incidents >= 1
    assert summary.resolved_incidents >= 1
    # Check that MTTA/MTTR are real floats calculated from timestamps
    assert summary.mtta_seconds is not None
    assert summary.mttr_seconds is not None


def test_5_api_postgres_live_endpoints():
    """Proves FastAPI reads live incidents and summaries persisted in PostgreSQL."""
    client = TestClient(app)

    res_list = client.get("/incidents?limit=5")
    assert res_list.status_code == 200
    assert isinstance(res_list.json(), list)

    res_sum = client.get("/incidents/summary")
    assert res_sum.status_code == 200
    data = res_sum.json()
    assert data["total_incidents"] >= 1
