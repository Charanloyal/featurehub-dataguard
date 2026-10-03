"""
Comprehensive Unit Tests for SchemaDiffEngine.
Covers all change types, nullability transitions, enum evolutions, constraints,
severities (SAFE, WARNING, BREAKING), error scenarios, and fixture evaluations.
"""

import copy
import yaml
from pathlib import Path
import pytest

from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import DiffSeverity, ChangeType
from dataguard.contracts.registry import ContractRegistryService, ContractNotFoundError

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

@pytest.fixture
def base_order_contract():
    return {
        "dataset": "orders",
        "version": "v1.0.0",
        "owner": "checkout-team",
        "description": "Orders placement and payment lifecycle contract",
        "freshness_sla_minutes": 60,
        "status": "ACTIVE",
        "columns": [
            {
                "name": "order_id",
                "type": "string",
                "nullable": False,
                "unique": True,
                "description": "Unique order identifier UUID"
            },
            {
                "name": "customer_id",
                "type": "integer",
                "nullable": False,
                "unique": False,
                "description": "ID of purchasing customer"
            },
            {
                "name": "amount",
                "type": "numeric",
                "nullable": False,
                "unique": False,
                "min": 0.01,
                "max": 10000.0,
                "description": "Total payment amount in USD"
            },
            {
                "name": "status",
                "type": "string",
                "nullable": False,
                "unique": False,
                "allowed_values": ["pending", "paid", "cancelled"],
                "description": "Current status of order"
            },
            {
                "name": "created_at",
                "type": "timestamp",
                "nullable": False,
                "unique": False,
                "description": "Order creation ISO-8601 timestamp"
            },
            {
                "name": "notes",
                "type": "string",
                "nullable": True,
                "unique": False,
                "description": "Optional customer delivery instructions"
            }
        ],
        "constraints": [
            "order_id IS NOT NULL",
            "amount >= 0.01"
        ]
    }


def test_added_nullable_column_is_safe(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["version"] = "v1.1.0"
    target["columns"].append({
        "name": "discount_code",
        "type": "string",
        "nullable": True,
        "unique": False,
        "description": "Optional coupon code applied to order"
    })

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert result.total_changes == 1
    c = result.changes[0]
    assert c.column == "discount_code"
    assert c.change_type == ChangeType.COLUMN_ADDED
    assert c.severity == DiffSeverity.SAFE


def test_added_non_nullable_column_is_warning(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["version"] = "v1.1.0"
    target["columns"].append({
        "name": "currency",
        "type": "string",
        "nullable": False,
        "unique": False,
        "description": "ISO currency code"
    })

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.WARNING
    assert result.is_breaking is False
    assert any(c.column == "currency" and c.severity == DiffSeverity.WARNING for c in result.changes)


def test_description_change_is_safe(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["description"] = "Updated checkout events contract with revised documentation."

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert any(c.change_type == ChangeType.DESCRIPTION_CHANGED and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_sla_relaxation_is_safe(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["freshness_sla_minutes"] = 120  # Relaxed from 60

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert any(c.change_type == ChangeType.SLA_CHANGED and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_sla_tightening_is_warning(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["freshness_sla_minutes"] = 30  # Tightened from 60

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.WARNING
    assert any(c.change_type == ChangeType.SLA_CHANGED and c.severity == DiffSeverity.WARNING for c in result.changes)


def test_removed_column_is_breaking(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["version"] = "v2.0.0"
    target["columns"] = [c for c in target["columns"] if c["name"] != "notes"]

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert any(c.column == "notes" and c.change_type == ChangeType.COLUMN_REMOVED and c.severity == DiffSeverity.BREAKING for c in result.changes)


def test_incompatible_type_is_breaking(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "customer_id":
            c["type"] = "string"

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert any(c.column == "customer_id" and c.change_type == ChangeType.TYPE_CHANGED and c.severity == DiffSeverity.BREAKING for c in result.changes)


def test_nullable_to_non_nullable_is_breaking(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "notes":
            c["nullable"] = False

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert any(c.column == "notes" and c.change_type == ChangeType.NULLABILITY_CHANGED and c.severity == DiffSeverity.BREAKING for c in result.changes)


def test_non_nullable_to_nullable_is_not_breaking(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "customer_id":
            c["nullable"] = True

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert any(c.column == "customer_id" and c.change_type == ChangeType.NULLABILITY_CHANGED and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_unique_constraint_tightened_is_breaking(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "customer_id":
            c["unique"] = True

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.BREAKING
    assert any(c.column == "customer_id" and c.change_type == ChangeType.UNIQUE_CHANGED and c.severity == DiffSeverity.BREAKING for c in result.changes)


def test_unique_constraint_relaxed_is_safe(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "order_id":
            c["unique"] = False

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert any(c.column == "order_id" and c.change_type == ChangeType.UNIQUE_CHANGED and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_enum_value_addition(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "status":
            c["allowed_values"] = ["pending", "paid", "cancelled", "refunded"]

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert any(c.column == "status" and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_enum_value_removal(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "status":
            c["allowed_values"] = ["pending", "cancelled"]  # "paid" removed

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert any(c.column == "status" and c.severity == DiffSeverity.BREAKING for c in result.changes)


def test_numeric_min_tightened_is_warning(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "amount":
            c["min"] = 5.0  # Tightened from 0.01

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.WARNING
    assert any(c.column == "amount" and c.severity == DiffSeverity.WARNING for c in result.changes)


def test_numeric_max_relaxed_is_safe(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    for c in target["columns"]:
        if c["name"] == "amount":
            c["max"] = 50000.0  # Relaxed from 10000.0

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.SAFE
    assert any(c.column == "amount" and c.severity == DiffSeverity.SAFE for c in result.changes)


def test_constraint_change(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["constraints"] = [
        "order_id IS NOT NULL",
        "amount >= 0.01",
        "customer_id > 0"  # Added custom constraint
    ]

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.WARNING
    assert any(c.change_type == ChangeType.CONSTRAINT_ADDED and c.severity == DiffSeverity.WARNING for c in result.changes)


def test_multiple_changes_use_highest_severity(base_order_contract):
    # Combines SAFE (nullable column added) + WARNING (SLA tightened) + BREAKING (column removed)
    target = copy.deepcopy(base_order_contract)
    target["freshness_sla_minutes"] = 15  # WARNING
    target["columns"].append({"name": "tag", "type": "string", "nullable": True})  # SAFE
    target["columns"] = [c for c in target["columns"] if c["name"] != "notes"]  # BREAKING

    result = SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert result.recommendation == "BLOCK MERGE"


def test_same_schema_has_no_changes(base_order_contract):
    result = SchemaDiffEngine.compare_contracts(base_order_contract, base_order_contract)
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert result.total_changes == 0
    assert len(result.changes) == 0


def test_version_not_found(tmp_path):
    # Test version_not_found using in-memory / temporary registry service
    reg = ContractRegistryService(db_path=tmp_path / "reg_test.db")
    with pytest.raises(ContractNotFoundError) as exc_info:
        SchemaDiffEngine.compare_versions(reg, "unknown_dataset", "v1.0.0", "v1.1.0")
    assert "not found" in str(exc_info.value).lower()


def test_dataset_mismatch(base_order_contract):
    target = copy.deepcopy(base_order_contract)
    target["dataset"] = "customers"  # Mismatch

    with pytest.raises(ValueError) as exc:
        SchemaDiffEngine.compare_contracts(base_order_contract, target)
    assert "mismatch" in str(exc.value).lower()


def test_yaml_fixtures_safe_fixture_evaluation():
    with open(FIXTURES_DIR / "schema_v1.yaml", "r") as f:
        v1 = yaml.safe_load(f)
    with open(FIXTURES_DIR / "schema_safe.yaml", "r") as f:
        safe = yaml.safe_load(f)

    result = SchemaDiffEngine.compare_contracts(v1, safe)
    assert result.classification == DiffSeverity.SAFE
    assert result.is_breaking is False
    assert result.recommendation == "APPROVE"


def test_yaml_fixtures_warning_fixture_evaluation():
    with open(FIXTURES_DIR / "schema_v1.yaml", "r") as f:
        v1 = yaml.safe_load(f)
    with open(FIXTURES_DIR / "schema_warning.yaml", "r") as f:
        warning = yaml.safe_load(f)

    result = SchemaDiffEngine.compare_contracts(v1, warning)
    assert result.classification == DiffSeverity.WARNING
    assert result.is_breaking is False
    assert result.recommendation == "APPROVE WITH WARNING"


def test_yaml_fixtures_breaking_fixture_evaluation():
    with open(FIXTURES_DIR / "schema_v1.yaml", "r") as f:
        v1 = yaml.safe_load(f)
    with open(FIXTURES_DIR / "schema_breaking.yaml", "r") as f:
        breaking = yaml.safe_load(f)

    result = SchemaDiffEngine.compare_contracts(v1, breaking)
    assert result.classification == DiffSeverity.BREAKING
    assert result.is_breaking is True
    assert result.recommendation == "BLOCK MERGE"
