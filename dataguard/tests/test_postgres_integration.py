"""
DataGuard Real PostgreSQL Integration Tests
Tests real PostgreSQL connectivity and contract lifecycle against PostgreSQL Docker container.
Do NOT mock the database. Test must fail if PostgreSQL is unavailable.
"""

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from dataguard.contracts.registry import (
    ContractRegistryService,
    DuplicateVersionError,
    get_default_db_url
)
from dataguard.api.main import app

@pytest.fixture(scope="module")
def postgres_service():
    """
    Initializes ContractRegistryService connected directly to real PostgreSQL.
    Fails if PostgreSQL is not reachable or if engine is not postgresql.
    """
    url = get_default_db_url()
    service = ContractRegistryService(db_url=url)
    
    # 1. Assert PostgreSQL is reachable directly
    try:
        with service.engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            assert res == 1, "Failed to execute query on PostgreSQL"
    except Exception as e:
        pytest.fail(f"Real PostgreSQL database is not reachable at {url}: {e}")

    engine_name = service.get_db_engine_name()
    assert engine_name == "postgresql", f"Expected real postgresql dialect, got '{engine_name}'"

    return service


def test_1_postgres_is_reachable(postgres_service):
    """Proves PostgreSQL is reachable directly."""
    with postgres_service.engine.connect() as conn:
        res = conn.execute(text("SELECT current_database(), version()")).fetchone()
        assert res is not None
        assert "PostgreSQL" in res[1]


def test_2_and_3_contract_and_version_stored(postgres_service):
    """Proves contract is inserted and contract version is stored in PostgreSQL tables."""
    dataset_name = "test_pg_e2e_orders"
    v1_contract = {
        "dataset": dataset_name,
        "version": "v1.0.0",
        "owner": "ecommerce-platform",
        "description": "Integration test orders dataset in PostgreSQL",
        "freshness_sla_minutes": 30,
        "status": "ACTIVE",
        "columns": [
            {
                "name": "order_id",
                "type": "string",
                "nullable": False,
                "unique": True,
                "description": "Unique order ID"
            },
            {
                "name": "amount",
                "type": "numeric",
                "nullable": False,
                "unique": False,
                "description": "Total order amount"
            }
        ],
        "constraints": ["order_id IS NOT NULL", "amount > 0"]
    }

    # Register contract
    reg_result = postgres_service.register_contract(v1_contract, allow_skip=True)
    assert reg_result["status"] in ["REGISTERED", "SKIPPED"]

    # Directly verify in PostgreSQL contract_registry table
    with postgres_service.engine.connect() as conn:
        reg_row = conn.execute(
            text("SELECT dataset_name, latest_version, owner FROM contract_registry WHERE dataset_name = :d"),
            {"d": dataset_name}
        ).fetchone()
        assert reg_row is not None
        assert reg_row[0] == dataset_name
        assert reg_row[1] == "v1.0.0"
        assert reg_row[2] == "ecommerce-platform"

        # Directly verify in PostgreSQL contract_versions table
        ver_row = conn.execute(
            text("SELECT version, owner, schema_json FROM contract_versions WHERE dataset_name = :d AND version = :v"),
            {"d": dataset_name, "v": "v1.0.0"}
        ).fetchone()
        assert ver_row is not None
        assert ver_row[0] == "v1.0.0"
        assert ver_row[1] == "ecommerce-platform"


def test_4_contract_can_be_retrieved(postgres_service):
    """Proves contract can be retrieved from PostgreSQL."""
    dataset_name = "test_pg_e2e_orders"
    retrieved = postgres_service.get_contract(dataset_name, version="v1.0.0")
    assert retrieved is not None
    assert retrieved["dataset"] == dataset_name
    assert retrieved["version"] == "v1.0.0"
    assert len(retrieved["columns"]) == 2
    assert retrieved["registered_id"] is not None


def test_5_duplicate_version_is_rejected(postgres_service):
    """Proves duplicate version for a dataset is rejected in PostgreSQL."""
    dataset_name = "test_pg_e2e_orders"
    duplicate_contract = {
        "dataset": dataset_name,
        "version": "v1.0.0",
        "owner": "ecommerce-platform",
        "description": "Attempt to duplicate v1.0.0",
        "freshness_sla_minutes": 30,
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False, "unique": True, "description": "ID"}
        ],
        "constraints": ["order_id IS NOT NULL"]
    }

    with pytest.raises(DuplicateVersionError):
        postgres_service.register_contract(duplicate_contract, allow_skip=False)


def test_6_api_returns_stored_contract_from_postgres():
    """Proves FastAPI retrieves and returns the stored contract from real PostgreSQL."""
    dataset_name = "test_pg_e2e_orders"
    client = TestClient(app)

    # 1. GET /contracts/{name}
    resp = client.get(f"/contracts/{dataset_name}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["dataset"] == dataset_name
    assert data["version"] == "v1.0.0"
    assert data["owner"] == "ecommerce-platform"
    assert len(data["columns"]) == 2

    # 2. GET /contracts
    list_resp = client.get(f"/contracts?dataset={dataset_name}")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) == 1
    assert list_data[0]["dataset"] == dataset_name

    # 3. Duplicate registration via API returns 409 Conflict
    dup_payload = {
        "dataset": dataset_name,
        "version": "v1.0.0",
        "owner": "ecommerce-platform",
        "description": "Duplicate contract payload test",
        "freshness_sla_minutes": 30,
        "columns": [{"name": "order_id", "type": "string", "nullable": False, "unique": True, "description": "ID"}],
        "constraints": ["order_id IS NOT NULL"]
    }
    dup_resp = client.post("/contracts", json=dup_payload)
    assert dup_resp.status_code == 409
