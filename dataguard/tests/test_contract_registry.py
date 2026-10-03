"""
DataGuard Phase B Contract Registry Unit and Integration Tests
Covers contract registration, versioning, discovery, validation, filtering, duplicate handling, and full end-to-end integration flow.
"""

import pytest
import yaml
from pathlib import Path
from fastapi.testclient import TestClient

from dataguard.contracts.registry import (
    ContractRegistryService, 
    DuplicateVersionError, 
    ContractNotFoundError
)
from dataguard.contracts.validator import ContractValidationError
from dataguard.api.main import app

@pytest.fixture
def temp_db_service(tmp_path):
    db_file = tmp_path / "test_registry.db"
    return ContractRegistryService(db_path=db_file)

@pytest.fixture
def sample_valid_contract():
    return {
        "dataset": "test_orders_stream",
        "version": "v1",
        "owner": "data-engineering",
        "description": "Stream of incoming order records",
        "freshness_sla_minutes": 15,
        "status": "ACTIVE",
        "columns": [
            {
                "name": "order_id",
                "type": "string",
                "nullable": False,
                "unique": True,
                "description": "Primary key UUID"
            },
            {
                "name": "amount",
                "type": "numeric",
                "nullable": False,
                "unique": False,
                "min": 0.0,
                "max": 10000.0,
                "description": "Total order amount in USD"
            }
        ],
        "constraints": ["order_id IS NOT NULL", "amount >= 0"]
    }

def test_register_contract(temp_db_service, sample_valid_contract):
    result = temp_db_service.register_contract(sample_valid_contract)
    assert result["status"] == "REGISTERED"
    assert result["dataset"] == "test_orders_stream"
    assert result["version"] == "v1"
    assert result["owner"] == "data-engineering"

def test_get_contract(temp_db_service, sample_valid_contract):
    temp_db_service.register_contract(sample_valid_contract)
    retrieved = temp_db_service.get_contract("test_orders_stream")
    assert retrieved is not None
    assert retrieved["dataset"] == "test_orders_stream"
    assert retrieved["version"] == "v1"
    assert len(retrieved["columns"]) == 2

def test_list_contracts(temp_db_service, sample_valid_contract):
    temp_db_service.register_contract(sample_valid_contract)
    contracts = temp_db_service.list_contracts()
    assert len(contracts) >= 1
    assert any(c["dataset"] == "test_orders_stream" for c in contracts)

def test_get_contract_versions(temp_db_service, sample_valid_contract):
    temp_db_service.register_contract(sample_valid_contract)
    
    # Register v2
    v2_contract = sample_valid_contract.copy()
    v2_contract["version"] = "v2"
    v2_contract["columns"] = sample_valid_contract["columns"] + [
        {
            "name": "currency",
            "type": "string",
            "nullable": False,
            "unique": False,
            "description": "ISO currency code"
        }
    ]
    temp_db_service.register_contract(v2_contract)

    versions = temp_db_service.get_contract_versions("test_orders_stream")
    assert len(versions) == 2
    version_strs = [v["version"] for v in versions]
    assert "v1" in version_strs
    assert "v2" in version_strs

def test_duplicate_version(temp_db_service, sample_valid_contract):
    temp_db_service.register_contract(sample_valid_contract)
    with pytest.raises(DuplicateVersionError):
        temp_db_service.register_contract(sample_valid_contract, allow_skip=False)

def test_invalid_contract(temp_db_service):
    invalid_contract = {
        "dataset": "invalid_dataset",
        "version": "v1",
        # Missing owner and columns
    }
    with pytest.raises(ContractValidationError):
        temp_db_service.register_contract(invalid_contract)

def test_missing_contract(temp_db_service):
    retrieved = temp_db_service.get_contract("non_existent_dataset")
    assert retrieved is None

def test_contract_validation(temp_db_service, sample_valid_contract):
    is_valid, errors = temp_db_service.validate_contract_structure(sample_valid_contract)
    assert is_valid is True
    assert len(errors) == 0

    bad_contract = sample_valid_contract.copy()
    bad_contract["columns"] = [
        {"name": "bad_col", "type": "unsupported_datatype", "nullable": True, "unique": False, "description": "test"}
    ]
    is_valid, errors = temp_db_service.validate_contract_structure(bad_contract)
    assert is_valid is False
    assert len(errors) > 0

def test_status_filter(temp_db_service, sample_valid_contract):
    c1 = sample_valid_contract.copy()
    c1["dataset"] = "active_dataset"
    c1["status"] = "ACTIVE"

    c2 = sample_valid_contract.copy()
    c2["dataset"] = "deprecated_dataset"
    c2["status"] = "DEPRECATED"

    temp_db_service.register_contract(c1)
    temp_db_service.register_contract(c2)

    active_list = temp_db_service.list_contracts(status="ACTIVE")
    assert any(c["dataset"] == "active_dataset" for c in active_list)
    assert not any(c["dataset"] == "deprecated_dataset" for c in active_list)

    deprecated_list = temp_db_service.list_contracts(status="DEPRECATED")
    assert any(c["dataset"] == "deprecated_dataset" for c in deprecated_list)
    assert not any(c["dataset"] == "active_dataset" for c in deprecated_list)

def test_owner_filter(temp_db_service, sample_valid_contract):
    c1 = sample_valid_contract.copy()
    c1["dataset"] = "team_a_dataset"
    c1["owner"] = "team-a"

    c2 = sample_valid_contract.copy()
    c2["dataset"] = "team_b_dataset"
    c2["owner"] = "team-b"

    temp_db_service.register_contract(c1)
    temp_db_service.register_contract(c2)

    team_a_list = temp_db_service.list_contracts(owner="team-a")
    assert len(team_a_list) == 1
    assert team_a_list[0]["dataset"] == "team_a_dataset"

# SECTION 9: INTEGRATION TEST
def test_full_integration_pipeline_yaml_to_fastapi(tmp_path):
    """
    Integration Test Flow:
    YAML contract -> Contract parser -> Validator -> Real Database Registry -> FastAPI TestClient -> GET contract.
    Verify returned contract matches registered source YAML.
    """
    yaml_content = """
dataset: e2e_user_events
version: v1
owner: event-platform
description: Real-time user clickstream events
freshness_sla_minutes: 5
status: ACTIVE
columns:
  - name: event_id
    type: string
    nullable: false
    unique: true
    description: Unique event ID
  - name: user_id
    type: string
    nullable: false
    unique: false
    description: User ID
  - name: timestamp
    type: timestamp
    nullable: false
    unique: false
    description: Event timestamp
constraints:
  - event_id IS NOT NULL
  - timestamp <= CURRENT_TIMESTAMP
"""
    # 1. Parse YAML
    parsed_contract = yaml.safe_load(yaml_content)

    # 2. Test Client & Service targeting real test DB
    test_db = tmp_path / "integration_registry.db"
    svc = ContractRegistryService(db_path=test_db)
    
    # 3. Validate & Register via service
    is_valid, errors = svc.validate_contract_structure(parsed_contract)
    assert is_valid is True, f"Validation failed: {errors}"

    reg_result = svc.register_contract(parsed_contract, yaml_content=yaml_content)
    assert reg_result["status"] == "REGISTERED"

    # 4. Patch main app registry_service for test client
    from dataguard.api import main
    original_service = main.registry_service
    main.registry_service = svc
    
    try:
        client = TestClient(app)
        
        # GET /contracts/e2e_user_events
        response = client.get("/contracts/e2e_user_events")
        assert response.status_code == 200
        fetched_data = response.json()

        assert fetched_data["dataset"] == "e2e_user_events"
        assert fetched_data["version"] == "v1"
        assert fetched_data["owner"] == "event-platform"
        assert len(fetched_data["columns"]) == 3
        assert fetched_data["yaml_content"].strip() == yaml_content.strip()

        # GET /contracts with owner filter
        filtered_resp = client.get("/contracts?owner=event-platform")
        assert filtered_resp.status_code == 200
        assert len(filtered_resp.json()) == 1

        # Test duplicate registration API return 409
        dup_resp = client.post("/contracts", json=parsed_contract)
        assert dup_resp.status_code == 409

        # Test invalid contract API return 422
        invalid_resp = client.post("/contracts", json={"dataset": "bad"})
        assert invalid_resp.status_code == 422

    finally:
        main.registry_service = original_service
