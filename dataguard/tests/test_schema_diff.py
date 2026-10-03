"""
Unit and Integration Tests for DataGuard Schema Diff Engine
Verifies classification of SAFE, WARNING, and BREAKING contract modifications,
range constraints, enum drifts, table schema inspections, and FastAPI endpoints.
"""

import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from dataguard.schema.diff import SchemaDiffEngine, DiffSeverity
from dataguard.contracts.registry import ContractRegistryService
from dataguard.api.main import app

@pytest.fixture
def base_contract():

    return {
        "dataset": "transactions",
        "version": "v1.0.0",
        "owner": "payment-platform",
        "description": "Production transactions event stream",
        "freshness_sla_minutes": 15,
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": True, "description": "Primary key UUID"},
            {"name": "amount", "type": "numeric", "nullable": False, "unique": False, "min": 0.0, "max": 10000.0, "description": "Amount"},
            {"name": "status", "type": "string", "nullable": True, "unique": False, "allowed_values": ["APPROVED", "FAILED"], "description": "Status"}
        ],
        "constraints": ["transaction_id IS NOT NULL", "amount >= 0"]
    }


def test_adding_nullable_column_is_safe(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": base_contract["columns"] + [
            {"name": "promo_code", "type": "string", "nullable": True}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "SAFE"
    assert result["is_breaking"] is False
    assert result["total_changes"] == 1
    assert result["changes"][0]["change_type"] == "COLUMN_ADDED"

def test_adding_non_nullable_column_is_warning(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": base_contract["columns"] + [
            {"name": "mandatory_region", "type": "string", "nullable": False}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "WARNING"
    assert result["is_breaking"] is False
    assert any(c["change_type"] == "COLUMN_ADDED" and c["severity"] == "WARNING" for c in result["changes"])

def test_removing_column_is_breaking(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [c for c in base_contract["columns"] if c["name"] != "amount"]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "BREAKING"
    assert result["is_breaking"] is True
    assert any(c["change_type"] == "COLUMN_REMOVED" for c in result["changes"])

def test_type_change_is_breaking(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "string", "nullable": False},  # Changed numeric to string
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED", "FAILED"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "BREAKING"
    assert result["is_breaking"] is True
    assert any(c["change_type"] == "TYPE_CHANGED" for c in result["changes"])

def test_nullable_to_non_nullable_is_breaking(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "numeric", "nullable": False},
            {"name": "status", "type": "string", "nullable": False, "allowed_values": ["APPROVED", "FAILED"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "BREAKING"
    assert result["is_breaking"] is True
    assert any(c["change_type"] == "NULLABILITY_CHANGED" and c["severity"] == "BREAKING" for c in result["changes"])

def test_non_nullable_to_nullable_is_safe(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": True}, # Relaxed to nullable
            {"name": "amount", "type": "numeric", "nullable": False},
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED", "FAILED"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "SAFE"
    assert result["is_breaking"] is False
    assert any(c["change_type"] == "NULLABILITY_CHANGED" and c["severity"] == "SAFE" for c in result["changes"])

def test_removing_enum_value_is_breaking(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "numeric", "nullable": False},
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED"]} # Removed "FAILED"
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "BREAKING"
    assert result["is_breaking"] is True
    assert any(c["change_type"] == "ENUM_VALUES_REMOVED" for c in result["changes"])

def test_adding_enum_value_is_safe(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "numeric", "nullable": False},
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED", "FAILED", "PENDING"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "SAFE"
    assert result["is_breaking"] is False
    assert any(c["change_type"] == "ENUM_VALUES_ADDED" for c in result["changes"])

def test_tightening_range_constraint_is_warning(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "numeric", "nullable": False, "min": 10.0, "max": 5000.0}, # Tightened 0->10, 10000->5000
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED", "FAILED"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "WARNING"
    assert result["is_breaking"] is False
    assert any(c["change_type"] == "CONSTRAINT_TIGHTENED" for c in result["changes"])

def test_relaxing_range_constraint_is_safe(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "numeric", "nullable": False, "min": -5.0, "max": 20000.0}, # Relaxed
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED", "FAILED"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "SAFE"
    assert result["is_breaking"] is False
    assert any(c["change_type"] == "CONSTRAINT_RELAXED" for c in result["changes"])

def test_possible_column_rename_detected(base_contract):
    target = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "txn_uuid", "type": "string", "nullable": False}, # Replaced transaction_id
            {"name": "amount", "type": "numeric", "nullable": False},
            {"name": "status", "type": "string", "nullable": True, "allowed_values": ["APPROVED", "FAILED"]}
        ]
    }
    result = SchemaDiffEngine.compare_contracts(base_contract, target)
    assert result["classification"] == "BREAKING"
    assert any(c["change_type"] == "COLUMN_RENAMED" for c in result["changes"])

def test_diff_contract_against_database_table(tmp_path, base_contract):
    test_db = tmp_path / "test_physical.db"
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE physical_transactions (
        transaction_id TEXT PRIMARY KEY,
        amount NUMERIC NOT NULL,
        status TEXT,
        live_created_at TIMESTAMP
    );
    """)
    conn.commit()

    # Compare base_contract with physical table
    diff = SchemaDiffEngine.compare_contract_to_table(
        contract=base_contract,
        table_name="physical_transactions",
        conn=conn
    )
    conn.close()

    assert "live_created_at" in [c["column_name"] for c in diff["changes"]]
    assert diff["is_breaking"] is False
    assert diff["classification"] == "SAFE"

def test_api_schema_diff_endpoints(tmp_path, base_contract):
    client = TestClient(app)

    # 1. POST /schema/diff
    diff_payload = {
        "baseline_contract": base_contract,
        "target_contract": {
            "dataset": "transactions",
            "version": "v1.1.0",
            "columns": base_contract["columns"] + [{"name": "extra", "type": "string", "nullable": True}]
        }
    }
    resp = client.post("/schema/diff", json=diff_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["classification"] == "SAFE"
    assert data["total_changes"] == 1

    # 2. Setup isolated registry for API diff test
    test_db = tmp_path / "api_diff_test.db"
    svc = ContractRegistryService(db_path=test_db)
    svc.register_contract(base_contract)

    v2_contract = base_contract.copy()
    v2_contract["version"] = "v2.0.0"
    v2_contract["columns"] = [c for c in base_contract["columns"] if c["name"] != "status"]
    svc.register_contract(v2_contract)

    from dataguard.api import main
    orig_svc = main.registry_service
    main.registry_service = svc
    try:
        # GET /contracts/transactions/diff?v1=v1.0.0&v2=v2.0.0
        v_diff = client.get("/contracts/transactions/diff?v1=v1.0.0&v2=v2.0.0")
        assert v_diff.status_code == 200
        v_data = v_diff.json()
        assert v_data["classification"] == "BREAKING"
        assert v_data["is_breaking"] is True

        # Non-existent version test
        err_diff = client.get("/contracts/transactions/diff?v1=v1.0.0&v2=nonexistent")
        assert err_diff.status_code == 404
    finally:
        main.registry_service = orig_svc
