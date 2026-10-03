"""
DataGuard Incident Management Unit & API Test Suite (Phase E).
Tests incident creation from quality failures, deduplication, severity policy,
lifecycle state transitions, audit trail events, MTTA/MTTR calculations, filtering, and API endpoints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from dataguard.api.main import app
from dataguard.contracts.registry import ContractRegistryService
from dataguard.quality.models import QualityCheckResult, QualityStatus
from dataguard.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentStatus,
    IncidentSeverity,
    IncidentEventType,
    InvalidStateTransitionError
)
from dataguard.incidents.severity import IncidentSeverityPolicy
from dataguard.incidents.deduplication import compute_failure_signature
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.manager import IncidentManager


@pytest.fixture
def tmp_repo(tmp_path):
    """Provides an isolated SQLite IncidentRepository for unit tests."""
    db_file = tmp_path / "test_incidents.db"
    return IncidentRepository(db_path=db_file)


@pytest.fixture
def test_mgr(tmp_repo):
    """Provides an IncidentManager configured with isolated repository and registry."""
    registry = ContractRegistryService()
    return IncidentManager(repository=tmp_repo, registry_service=registry)


@pytest.fixture
def test_client():
    return TestClient(app)


# 1. Failed quality check creates incident
def test_failed_quality_check_creates_incident(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_test",
        dataset="orders",
        check_name="expect_column_values_to_not_be_null_order_total",
        column="order_total",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="5 null values",
        expected_value="0 null values",
        success=False,
        pipeline="test_pipeline"
    )

    inc = test_mgr.handle_check_failure(failing_check, dataset="orders", pipeline="test_pipeline")
    assert inc is not None
    assert inc.dataset == "orders"
    assert inc.status == IncidentStatus.OPEN
    assert inc.severity == IncidentSeverity.HIGH
    assert inc.owner == "e-commerce-data-team"


# 2. Successful check creates no incident
def test_successful_check_creates_no_incident(test_mgr):
    passing_check = QualityCheckResult(
        run_id="run_test",
        dataset="orders",
        check_name="expect_column_values_to_not_be_null_order_id",
        column="order_id",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.PASS,
        severity="HIGH",
        observed_value="Compliant",
        expected_value="0 null values",
        success=True,
        pipeline="test_pipeline"
    )

    inc = test_mgr.handle_check_failure(passing_check, dataset="orders", pipeline="test_pipeline")
    assert inc is None


# 3. Incident persistence
def test_incident_persistence(test_mgr, tmp_repo):
    failing_check = QualityCheckResult(
        run_id="run_test",
        dataset="payments",
        check_name="expect_column_values_to_be_in_set_status",
        column="status",
        expectation_type="expect_column_values_to_be_in_set",
        status=QualityStatus.FAIL,
        severity="MEDIUM",
        observed_value="3 unexpected values",
        expected_value="in set",
        success=False,
        pipeline="payments_pipeline"
    )

    inc = test_mgr.handle_check_failure(failing_check, dataset="payments", pipeline="payments_pipeline")
    stored = tmp_repo.get_incident(inc.incident_id)
    assert stored is not None
    assert stored.incident_id == inc.incident_id
    assert stored.dataset == "payments"
    assert len(stored.events) == 1
    assert stored.events[0].event_type == IncidentEventType.INCIDENT_CREATED


# 4. Incident deduplication
def test_incident_deduplication(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_test_1",
        dataset="orders",
        check_name="expect_column_values_to_be_unique_order_id",
        column="order_id",
        expectation_type="expect_column_values_to_be_unique",
        status=QualityStatus.FAIL,
        severity="CRITICAL",
        observed_value="Duplicate ID detected",
        expected_value="Unique IDs",
        success=False,
        pipeline="test_pipeline"
    )

    inc1 = test_mgr.handle_check_failure(failing_check, dataset="orders", pipeline="test_pipeline")
    inc2 = test_mgr.handle_check_failure(failing_check, dataset="orders", pipeline="test_pipeline")

    assert inc1.incident_id == inc2.incident_id
    all_orders_incidents = test_mgr.list_incidents(dataset="orders")
    assert len(all_orders_incidents) == 1


# 5. Deduplication after resolution allows new incident
def test_deduplication_after_resolution(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_test_1",
        dataset="orders",
        check_name="expect_column_values_to_be_unique_order_id",
        column="order_id",
        expectation_type="expect_column_values_to_be_unique",
        status=QualityStatus.FAIL,
        severity="CRITICAL",
        observed_value="Duplicate ID",
        expected_value="Unique IDs",
        success=False,
        pipeline="test_pipeline"
    )

    inc1 = test_mgr.handle_check_failure(failing_check, dataset="orders", pipeline="test_pipeline")
    test_mgr.resolve_incident(inc1.incident_id, notes="Remediated")

    # Second failure should now create a new incident because previous is resolved
    inc2 = test_mgr.handle_check_failure(failing_check, dataset="orders", pipeline="test_pipeline")
    assert inc2.incident_id != inc1.incident_id
    assert inc2.status == IncidentStatus.OPEN


# 6. Severity mapping: Critical for PK corruption
def test_severity_mapping_critical_pk():
    sev = IncidentSeverityPolicy.determine_severity(
        expectation_type="expect_column_values_to_be_unique",
        column="order_id",
        is_primary_key=True
    )
    assert sev == IncidentSeverity.CRITICAL


# 7. Severity mapping: Critical for referential integrity
def test_severity_mapping_critical_referential():
    sev = IncidentSeverityPolicy.determine_severity(
        expectation_type="expect_column_values_to_match_foreign_key",
        column="customer_id"
    )
    assert sev == IncidentSeverity.CRITICAL


# 8. Severity mapping: Critical for stale dataset
def test_severity_mapping_critical_freshness_stale():
    sev = IncidentSeverityPolicy.determine_severity(
        expectation_type="expect_dataset_freshness_within_sla",
        column="created_at",
        details={"status": "STALE"}
    )
    assert sev == IncidentSeverity.CRITICAL


# 9. Severity mapping: High for null checks
def test_severity_mapping_high_nulls():
    sev = IncidentSeverityPolicy.determine_severity(
        expectation_type="expect_column_values_to_not_be_null",
        column="order_total"
    )
    assert sev == IncidentSeverity.HIGH


# 10. Severity mapping: Medium for enums and ranges
def test_severity_mapping_medium_enums_and_ranges():
    sev1 = IncidentSeverityPolicy.determine_severity(
        expectation_type="expect_column_values_to_be_in_set",
        column="status"
    )
    sev2 = IncidentSeverityPolicy.determine_severity(
        expectation_type="expect_column_values_to_be_between",
        column="price"
    )
    assert sev1 == IncidentSeverity.MEDIUM
    assert sev2 == IncidentSeverity.MEDIUM


# 11. Owner assignment from contract
def test_owner_assignment(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_1",
        dataset="orders",
        check_name="test_check",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="null",
        expected_value="not null",
        success=False
    )
    inc = test_mgr.handle_check_failure(failing_check, dataset="orders")
    assert inc.owner == "e-commerce-data-team"


# 12. Lifecycle: OPEN -> ACKNOWLEDGED
def test_open_to_acknowledged(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_1",
        dataset="orders",
        check_name="check_a",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="null",
        expected_value="not null",
        success=False
    )
    inc = test_mgr.handle_check_failure(failing_check, dataset="orders")
    assert inc.status == IncidentStatus.OPEN
    assert inc.acknowledged_at is None

    acked = test_mgr.acknowledge_incident(inc.incident_id, actor="bob", notes="Triaging")
    assert acked.status == IncidentStatus.ACKNOWLEDGED
    assert acked.acknowledged_at is not None


# 13. Lifecycle: ACKNOWLEDGED -> RESOLVED
def test_acknowledged_to_resolved(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_1",
        dataset="orders",
        check_name="check_b",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="null",
        expected_value="not null",
        success=False
    )
    inc = test_mgr.handle_check_failure(failing_check, dataset="orders")
    test_mgr.acknowledge_incident(inc.incident_id, actor="bob")
    resolved = test_mgr.resolve_incident(inc.incident_id, actor="bob", notes="Done")
    assert resolved.status == IncidentStatus.RESOLVED
    assert resolved.resolved_at is not None


# 14. Invalid lifecycle transition: RESOLVED -> ACKNOWLEDGED
def test_invalid_transition(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_1",
        dataset="orders",
        check_name="check_c",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="null",
        expected_value="not null",
        success=False
    )
    inc = test_mgr.handle_check_failure(failing_check, dataset="orders")
    test_mgr.resolve_incident(inc.incident_id)

    with pytest.raises(InvalidStateTransitionError):
        test_mgr.acknowledge_incident(inc.incident_id)


# 15. Incident events audit trail
def test_incident_events(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_1",
        dataset="orders",
        check_name="check_d",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="null",
        expected_value="not null",
        success=False
    )
    inc = test_mgr.handle_check_failure(failing_check, dataset="orders")
    test_mgr.acknowledge_incident(inc.incident_id, actor="alice", notes="Ack note")
    test_mgr.resolve_incident(inc.incident_id, actor="alice", notes="Res note")

    events = test_mgr.get_events(inc.incident_id)
    assert len(events) == 3
    assert events[0].event_type == IncidentEventType.INCIDENT_CREATED
    assert events[1].event_type == IncidentEventType.INCIDENT_ACKNOWLEDGED
    assert events[2].event_type == IncidentEventType.INCIDENT_RESOLVED


# 16. Incident summary & MTTA / MTTR
def test_incident_summary_and_mtta_mttr(test_mgr):
    failing_check = QualityCheckResult(
        run_id="run_1",
        dataset="orders",
        check_name="check_e",
        expectation_type="expect_column_values_to_not_be_null",
        status=QualityStatus.FAIL,
        severity="HIGH",
        observed_value="null",
        expected_value="not null",
        success=False
    )
    inc = test_mgr.handle_check_failure(failing_check, dataset="orders")
    test_mgr.acknowledge_incident(inc.incident_id)
    test_mgr.resolve_incident(inc.incident_id)

    summary = test_mgr.get_summary()
    assert summary.total_incidents >= 1
    assert summary.resolved_incidents >= 1
    assert summary.mtta_seconds is not None
    assert summary.mttr_seconds is not None


# 17. Filtering by status
def test_filter_by_status(test_mgr):
    failing_check1 = QualityCheckResult(
        run_id="r1", dataset="orders", check_name="c1",
        expectation_type="exp1", status=QualityStatus.FAIL,
        severity="HIGH", observed_value="x", expected_value="y", success=False
    )
    failing_check2 = QualityCheckResult(
        run_id="r2", dataset="orders", check_name="c2",
        expectation_type="exp2", status=QualityStatus.FAIL,
        severity="HIGH", observed_value="x", expected_value="y", success=False
    )
    inc1 = test_mgr.handle_check_failure(failing_check1, dataset="orders")
    inc2 = test_mgr.handle_check_failure(failing_check2, dataset="orders")
    test_mgr.resolve_incident(inc1.incident_id)

    open_incs = test_mgr.list_incidents(status="OPEN")
    res_incs = test_mgr.list_incidents(status="RESOLVED")

    assert any(i.incident_id == inc2.incident_id for i in open_incs)
    assert any(i.incident_id == inc1.incident_id for i in res_incs)


# 18. Filtering by severity
def test_filter_by_severity(test_mgr):
    failing_crit = QualityCheckResult(
        run_id="r1", dataset="orders", check_name="crit_check",
        expectation_type="expect_column_values_to_match_foreign_key",
        status=QualityStatus.FAIL, severity="CRITICAL", observed_value="x", expected_value="y", success=False
    )
    failing_med = QualityCheckResult(
        run_id="r2", dataset="orders", check_name="med_check",
        expectation_type="expect_column_values_to_be_in_set",
        status=QualityStatus.FAIL, severity="MEDIUM", observed_value="x", expected_value="y", success=False
    )
    inc_crit = test_mgr.handle_check_failure(failing_crit, dataset="orders")
    inc_med = test_mgr.handle_check_failure(failing_med, dataset="orders")

    crits = test_mgr.list_incidents(severity="CRITICAL")
    assert any(i.incident_id == inc_crit.incident_id for i in crits)


# 19. Filtering by dataset
def test_filter_by_dataset(test_mgr):
    failing_orders = QualityCheckResult(
        run_id="r1", dataset="orders", check_name="c_ord",
        expectation_type="exp", status=QualityStatus.FAIL, severity="HIGH", observed_value="x", expected_value="y", success=False
    )
    failing_payments = QualityCheckResult(
        run_id="r2", dataset="payments", check_name="c_pay",
        expectation_type="exp", status=QualityStatus.FAIL, severity="HIGH", observed_value="x", expected_value="y", success=False
    )
    test_mgr.handle_check_failure(failing_orders, dataset="orders")
    test_mgr.handle_check_failure(failing_payments, dataset="payments")

    orders_only = test_mgr.list_incidents(dataset="orders")
    assert all(i.dataset == "orders" for i in orders_only)


# 20. Filtering by owner
def test_filter_by_owner(test_mgr):
    failing_orders = QualityCheckResult(
        run_id="r1", dataset="orders", check_name="c_ord2",
        expectation_type="exp", status=QualityStatus.FAIL, severity="HIGH", observed_value="x", expected_value="y", success=False
    )
    test_mgr.handle_check_failure(failing_orders, dataset="orders")
    owner_incs = test_mgr.list_incidents(owner="e-commerce-data-team")
    assert len(owner_incs) >= 1
    assert all(i.owner == "e-commerce-data-team" for i in owner_incs)


# 21. API: GET /incidents
def test_api_list_incidents(test_client):
    response = test_client.get("/incidents?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# 22. API: GET /incidents/summary
def test_api_incident_summary(test_client):
    response = test_client.get("/incidents/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_incidents" in data
    assert "open_incidents" in data


# 23. API: Ack and Resolve lifecycle via REST
def test_api_ack_and_resolve(test_client):
    # Trigger a quality failure on orders to ensure an incident exists
    import json
    from dataguard.quality.datasets import DatasetCatalog
    bad_df = DatasetCatalog.bad_orders_nulls(num_rows=20)
    bad_orders = json.loads(bad_df.to_json(orient="records", date_format="iso"))
    test_client.post("/quality/validate/orders", json=bad_orders)

    incidents = test_client.get("/incidents?dataset=orders&status=OPEN").json()
    assert len(incidents) >= 1
    target_id = incidents[0]["incident_id"]

    # 1. POST /incidents/{id}/ack
    ack_res = test_client.post(f"/incidents/{target_id}/ack", json={"actor": "tester", "notes": "Ack via API"})
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # 2. POST /incidents/{id}/resolve
    res_res = test_client.post(f"/incidents/{target_id}/resolve", json={"actor": "tester", "notes": "Resolved via API"})
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"

    # 3. GET /incidents/{id}/events
    events_res = test_client.get(f"/incidents/{target_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 3


# 24. API: 404 for unknown incident
def test_api_404_unknown_incident(test_client):
    response = test_client.get("/incidents/inc_totally_unknown_123")
    assert response.status_code == 404
