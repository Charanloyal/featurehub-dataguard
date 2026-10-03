"""
Phase A Verification Tests for DataGuard Data Contract Engine
Verifies structural validity, required fields, column schemas, and constraints across 25 YAML contracts.
"""

import pytest
import yaml
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"

def get_all_contracts():
    files = list(CONTRACTS_DIR.glob("*.yaml"))
    assert len(files) >= 25, f"Expected at least 25 contracts, found {len(files)}"
    contracts = []
    for p in files:
        with open(p, "r") as f:
            data = yaml.safe_load(f)
            contracts.append((p.name, data))
    return contracts

def test_contract_file_count():
    """Verify at least 25 dataset contracts exist."""
    files = list(CONTRACTS_DIR.glob("*.yaml"))
    assert len(files) >= 25

def test_contract_root_fields():
    """Verify every contract contains required root fields."""
    contracts = get_all_contracts()
    required_root_keys = ["dataset", "version", "owner", "description", "freshness_sla_minutes", "columns", "constraints"]
    
    for filename, contract in contracts:
        for key in required_root_keys:
            assert key in contract, f"Contract '{filename}' missing required root key '{key}'"
        assert len(contract["columns"]) > 0, f"Contract '{filename}' has empty columns list"

def test_contract_column_definitions():
    """Verify column definitions contain mandatory fields and valid types."""
    contracts = get_all_contracts()
    mandatory_col_keys = ["name", "type", "nullable", "unique", "description"]
    valid_types = ["string", "numeric", "integer", "timestamp", "float"]

    for filename, contract in contracts:
        for col in contract["columns"]:
            for key in mandatory_col_keys:
                assert key in col, f"Column '{col.get('name')}' in '{filename}' missing key '{key}'"
            assert col["type"] in valid_types, f"Column '{col.get('name')}' in '{filename}' has invalid type '{col['type']}'"

def test_contract_constraints_and_enums():
    """Verify optional constraints and allowed enum values formatting."""
    contracts = get_all_contracts()
    for filename, contract in contracts:
        for col in contract["columns"]:
            if "allowed_values" in col:
                assert isinstance(col["allowed_values"], list), f"allowed_values in '{filename}.{col['name']}' must be a list"
                assert len(col["allowed_values"]) > 0, f"allowed_values in '{filename}.{col['name']}' is empty"
            if "min" in col and "max" in col:
                assert col["min"] <= col["max"], f"min > max in '{filename}.{col['name']}'"
