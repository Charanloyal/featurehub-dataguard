"""
DataGuard Real PostgreSQL Schema Diff Integration Tests.
Executes against the real PostgreSQL container (localhost:5432).
No mocks used. Tests:
PostgreSQL -> Registered Contract v1 -> Registered Contract v2 -> Schema Diff Engine -> Compatibility Result
"""

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from dataguard.contracts.registry import ContractRegistryService, get_default_db_url
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import DiffSeverity
from dataguard.api.main import app

DATASET_NAME = "pg_diff_orders"

@pytest.fixture(scope="module")
def postgres_service():
    url = get_default_db_url()
    service = ContractRegistryService(db_url=url)
    try:
        with service.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.fail(f"Real PostgreSQL database is not reachable at {url}: {e}")

    engine_name = service.get_db_engine_name()
    assert engine_name == "postgresql", f"Expected real postgresql dialect, got '{engine_name}'"

    # Pre-populate registered versions for integration test
    v1_contract = {
        "dataset": DATASET_NAME,
        "version": "v1.0.0",
        "owner": "checkout-squad",
        "description": "Baseline PostgreSQL diff contract",
        "freshness_sla_minutes": 60,
        "status": "ACTIVE",
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False, "unique": True, "description": "Order UUID"},
            {"name": "customer_id", "type": "integer", "nullable": False, "unique": False, "description": "Customer ID"},
            {"name": "amount", "type": "numeric", "nullable": False, "unique": False, "min": 0.01, "max": 10000.0, "description": "Amount"},
            {"name": "status", "type": "string", "nullable": False, "unique": False, "allowed_values": ["pending", "paid", "cancelled"], "description": "Status"},
            {"name": "notes", "type": "string", "nullable": True, "unique": False, "description": "Notes"}
        ],
        "constraints": ["order_id IS NOT NULL", "amount >= 0.01"]
    }

    # v1.1.0: SAFE (adds nullable column loyalty_tier, relaxes SLA to 120m)
    v1_1_contract = {
        "dataset": DATASET_NAME,
        "version": "v1.1.0",
        "owner": "checkout-squad",
        "description": "PostgreSQL diff contract with loyalty tier",
        "freshness_sla_minutes": 120,
        "status": "ACTIVE",
        "columns": v1_contract["columns"] + [
            {"name": "loyalty_tier", "type": "string", "nullable": True, "unique": False, "description": "Customer tier"}
        ],
        "constraints": ["order_id IS NOT NULL", "amount >= 0.01"]
    }

    # v1.2.0: WARNING (adds non-nullable column currency, tightens SLA to 30m)
    v1_2_contract = {
        "dataset": DATASET_NAME,
        "version": "v1.2.0",
        "owner": "checkout-squad",
        "description": "PostgreSQL diff contract with mandatory currency",
        "freshness_sla_minutes": 30,
        "status": "ACTIVE",
        "columns": v1_contract["columns"] + [
            {"name": "currency", "type": "string", "nullable": False, "unique": False, "description": "Currency code"}
        ],
        "constraints": ["order_id IS NOT NULL", "amount >= 0.01"]
    }

    # v2.0.0: BREAKING (removes notes, changes customer_id to string)
    v2_contract = {
        "dataset": DATASET_NAME,
        "version": "v2.0.0",
        "owner": "checkout-squad",
        "description": "Breaking PostgreSQL diff contract v2",
        "freshness_sla_minutes": 60,
        "status": "ACTIVE",
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False, "unique": True, "description": "Order UUID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Customer ID string"},
            {"name": "amount", "type": "numeric", "nullable": False, "unique": False, "min": 0.01, "max": 10000.0, "description": "Amount"},
            {"name": "status", "type": "string", "nullable": False, "unique": False, "allowed_values": ["pending", "paid", "cancelled"], "description": "Status"}
        ],
        "constraints": ["order_id IS NOT NULL", "amount >= 0.01"]
    }

    service.register_contract(v1_contract, allow_skip=True)
    service.register_contract(v1_1_contract, allow_skip=True)
    service.register_contract(v1_2_contract, allow_skip=True)
    service.register_contract(v2_contract, allow_skip=True)

    return service


def test_postgres_schema_diff_safe_evolution(postgres_service):
    """Proves engine compares two versions stored in real PostgreSQL and detects SAFE evolution."""
    result = SchemaDiffEngine.compare_versions(
        registry_service=postgres_service,
        dataset=DATASET_NAME,
        from_version="v1.0.0",
        to_version="v1.1.0"
    )
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert result.recommendation == "APPROVE"
    assert any(c.column == "loyalty_tier" and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_postgres_schema_diff_warning_evolution(postgres_service):
    """Proves engine compares two versions stored in real PostgreSQL and detects WARNING evolution."""
    result = SchemaDiffEngine.compare_versions(
        registry_service=postgres_service,
        dataset=DATASET_NAME,
        from_version="v1.0.0",
        to_version="v1.2.0"
    )
    assert result.classification == DiffSeverity.WARNING
    assert result.is_breaking is False
    assert result.recommendation == "APPROVE WITH WARNING"
    assert any(c.column == "currency" and c.severity == DiffSeverity.WARNING for c in result.changes)


def test_postgres_schema_diff_breaking_evolution(postgres_service):
    """Proves engine compares two versions stored in real PostgreSQL and detects BREAKING evolution."""
    result = SchemaDiffEngine.compare_versions(
        registry_service=postgres_service,
        dataset=DATASET_NAME,
        from_version="v1.0.0",
        to_version="v2.0.0"
    )
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert result.recommendation == "BLOCK MERGE"
    assert any(c.column == "notes" and c.severity == DiffSeverity.BREAKING for c in result.changes)
    assert any(c.column == "customer_id" and c.severity == DiffSeverity.BREAKING for c in result.changes)


def test_fastapi_schema_diff_against_real_postgres(postgres_service):
    """Tests POST /schema/diff against live FastAPI service pulling from real PostgreSQL."""
    client = TestClient(app)

    # 1. Safe change
    resp_safe = client.post("/schema/diff", json={
        "dataset": DATASET_NAME,
        "from_version": "v1.0.0",
        "to_version": "v1.1.0"
    })
    assert resp_safe.status_code == 200
    data_safe = resp_safe.json()
    assert data_safe["classification"] == "SAFE"
    assert data_safe["recommendation"] == "APPROVE"

    # 2. Warning change
    resp_warn = client.post("/schema/diff", json={
        "dataset": DATASET_NAME,
        "from_version": "v1.0.0",
        "to_version": "v1.2.0"
    })
    assert resp_warn.status_code == 200
    data_warn = resp_warn.json()
    assert data_warn["classification"] == "WARNING"
    assert data_warn["recommendation"] == "APPROVE WITH WARNING"

    # 3. Breaking change
    resp_break = client.post("/schema/diff", json={
        "dataset": DATASET_NAME,
        "from_version": "v1.0.0",
        "to_version": "v2.0.0"
    })
    assert resp_break.status_code == 200
    data_break = resp_break.json()
    assert data_break["classification"] == "BREAKING"
    assert data_break["recommendation"] == "BLOCK MERGE"
    assert data_break["is_breaking"] is True

    # 4. Error: Unknown dataset
    resp_404_ds = client.post("/schema/diff", json={
        "dataset": "non_existent_dataset_xyz",
        "from_version": "v1.0.0",
        "to_version": "v2.0.0"
    })
    assert resp_404_ds.status_code == 404

    # 5. Error: Unknown version
    resp_404_ver = client.post("/schema/diff", json={
        "dataset": DATASET_NAME,
        "from_version": "v1.0.0",
        "to_version": "v999.0.0"
    })
    assert resp_404_ver.status_code == 404

    # 6. Error: Same version
    resp_400_same = client.post("/schema/diff", json={
        "dataset": DATASET_NAME,
        "from_version": "v1.0.0",
        "to_version": "v1.0.0"
    })
    assert resp_400_same.status_code == 400
