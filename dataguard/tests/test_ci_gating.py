"""
Phase H Verification Tests for DataGuard CI/CD Pull Request Gating Engine
Tests 3-stage validation: Contract Structural Validation -> Schema Diff -> Quality Regression -> Merge Verdict.
"""

import copy
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from dataguard.ci.models import (
    GatingVerdict,
    GatingChange,
    ContractGatingResult,
    PRGatingSummary
)
from dataguard.ci.gate import CICDContractGatingEngine
from dataguard.api.main import app

client = TestClient(app)

BASE_CONTRACT = {
    "dataset": "test_orders",
    "version": "v1.0.0",
    "owner": "checkout_team",
    "description": "Order transactions stream",
    "freshness_sla_minutes": 60,
    "status": "ACTIVE",
    "columns": [
        {"name": "order_id", "type": "string", "nullable": False, "unique": True, "description": "Primary order key"},
        {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Foreign customer key"},
        {"name": "amount", "type": "numeric", "nullable": False, "unique": False, "description": "Order amount in USD", "min": 0.0, "max": 100000.0},
        {"name": "status", "type": "string", "nullable": False, "unique": False, "description": "Order status", "allowed_values": ["PENDING", "COMPLETED", "FAILED"]},
        {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Timestamp created"}
    ],
    "constraints": []
}


def test_ci_gate_identical_contracts_safe():
    """Identical contracts produce SAFE verdict, can_merge=True, 0 breaking/warnings."""
    target = copy.deepcopy(BASE_CONTRACT)
    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.SAFE
    assert res.can_merge is True
    assert res.is_breaking is False
    assert res.breaking_count == 0
    assert res.warning_count == 0


def test_ci_gate_new_contract_safe():
    """Registering a new contract (baseline is None) is SAFE."""
    target = copy.deepcopy(BASE_CONTRACT)
    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=None,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.SAFE
    assert res.can_merge is True
    assert res.is_breaking is False
    assert any("NEW_CONTRACT_ADDED" in ch.change_type for ch in res.changes)


def test_ci_gate_add_nullable_column_safe():
    """Adding a new nullable column is a backward-compatible SAFE change."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"].append({
        "name": "notes",
        "type": "string",
        "nullable": True,
        "unique": False,
        "description": "Optional buyer note"
    })
    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.SAFE
    assert res.can_merge is True
    assert res.breaking_count == 0
    assert res.safe_count > 0


def test_ci_gate_widen_type_safe():
    """Widening column type from integer to numeric is SAFE."""
    baseline = copy.deepcopy(BASE_CONTRACT)
    baseline["columns"][2]["type"] = "integer"
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"][2]["type"] = "numeric"

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=baseline,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.SAFE
    assert res.can_merge is True


def test_ci_gate_add_allowed_enum_value_safe():
    """Adding an allowed enum value (e.g. REFUNDED) is SAFE."""
    target = copy.deepcopy(BASE_CONTRACT)
    for col in target["columns"]:
        if col["name"] == "status":
            col["allowed_values"] = ["PENDING", "COMPLETED", "FAILED", "REFUNDED"]

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.SAFE
    assert res.can_merge is True


def test_ci_gate_relax_nullability_safe():
    """Relaxing nullability from False to True is SAFE."""
    target = copy.deepcopy(BASE_CONTRACT)
    for col in target["columns"]:
        if col["name"] == "customer_id":
            col["nullable"] = True

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.SAFE
    assert res.can_merge is True


def test_ci_gate_add_non_nullable_column_warning():
    """Adding a non-nullable column produces a WARNING verdict."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"].append({
        "name": "currency",
        "type": "string",
        "nullable": False,
        "unique": False,
        "description": "ISO currency code"
    })
    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.WARNING
    assert res.can_merge is True
    assert res.warning_count > 0


def test_ci_gate_tighten_freshness_sla_warning():
    """Shortening freshness SLA (e.g. 60 min to 15 min) triggers a WARNING."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["freshness_sla_minutes"] = 15

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.WARNING
    assert res.can_merge is True
    assert res.warning_count > 0


def test_ci_gate_tighten_numeric_range_warning():
    """Tightening numeric min/max bounds triggers WARNING."""
    target = copy.deepcopy(BASE_CONTRACT)
    for col in target["columns"]:
        if col["name"] == "amount":
            col["max"] = 50000.0  # was 100000.0

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.WARNING
    assert res.can_merge is True


def test_ci_gate_drop_column_breaking():
    """Dropping a column is BREAKING and blocks merge."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"] = [c for c in target["columns"] if c["name"] != "amount"]

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False
    assert res.is_breaking is True
    assert res.breaking_count >= 1
    assert any("COLUMN_REMOVED" in ch.change_type for ch in res.changes)


def test_ci_gate_incompatible_type_change_breaking():
    """Incompatible type change (numeric -> string or vice versa) is BREAKING."""
    target = copy.deepcopy(BASE_CONTRACT)
    for col in target["columns"]:
        if col["name"] == "amount":
            col["type"] = "string"

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False
    assert res.is_breaking is True


def test_ci_gate_tighten_nullability_breaking():
    """Changing nullable from True to False is BREAKING."""
    baseline = copy.deepcopy(BASE_CONTRACT)
    baseline["columns"][1]["nullable"] = True  # customer_id was nullable
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"][1]["nullable"] = False  # now required

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=baseline,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False
    assert res.is_breaking is True


def test_ci_gate_remove_allowed_enum_value_breaking():
    """Removing an allowed enum value (e.g. FAILED) is BREAKING."""
    target = copy.deepcopy(BASE_CONTRACT)
    for col in target["columns"]:
        if col["name"] == "status":
            col["allowed_values"] = ["PENDING", "COMPLETED"]  # removed FAILED

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False
    assert res.is_breaking is True


def test_ci_gate_invalid_yaml_contract_syntax():
    """Contract missing required root keys fails Stage 1 validation and blocks merge."""
    bad_contract = {
        "dataset": "invalid_dataset"
        # missing version, owner, description, columns, etc.
    }
    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=bad_contract,
        validate_quality=False
    )
    assert res.contract_valid is False
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False
    assert len(res.contract_errors) > 0


def test_ci_gate_empty_columns_rejection():
    """Contract with empty columns list fails Stage 1 validation."""
    bad_contract = copy.deepcopy(BASE_CONTRACT)
    bad_contract["columns"] = []

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=bad_contract,
        validate_quality=False
    )
    assert res.contract_valid is False
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False


def test_ci_gate_invalid_column_type_rejection():
    """Column with unrecognized type fails Stage 1 validation."""
    bad_contract = copy.deepcopy(BASE_CONTRACT)
    bad_contract["columns"][0]["type"] = "super_unknown_type"

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=bad_contract,
        validate_quality=False
    )
    assert res.contract_valid is False
    assert res.verdict == GatingVerdict.BREAKING
    assert res.can_merge is False


def test_ci_gate_remediation_guidance_for_dropped_column():
    """Verifies actionable remediation advice generated when dropping a column."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"] = [c for c in target["columns"] if c["name"] != "status"]

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    drop_change = next(ch for ch in res.changes if "status" in (ch.column or ""))
    assert "deprecate" in drop_change.remediation.lower() or "major version" in drop_change.remediation.lower()


def test_ci_gate_remediation_guidance_for_type_shift():
    """Verifies actionable remediation advice generated for incompatible type shift."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"][2]["type"] = "string"  # amount -> string

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=BASE_CONTRACT,
        target_contract=target,
        validate_quality=False
    )
    type_change = next(ch for ch in res.changes if ch.column == "amount")
    assert "incompatible type" in type_change.remediation.lower() or "type" in type_change.remediation.lower()


def test_ci_gate_remediation_guidance_for_nullability():
    """Verifies actionable remediation advice generated when nullability is tightened."""
    baseline = copy.deepcopy(BASE_CONTRACT)
    baseline["columns"][1]["nullable"] = True
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"][1]["nullable"] = False

    res = CICDContractGatingEngine.evaluate_contract_change(
        baseline_contract=baseline,
        target_contract=target,
        validate_quality=False
    )
    null_change = next(ch for ch in res.changes if ch.column == "customer_id")
    assert "null" in null_change.remediation.lower() or "backfill" in null_change.remediation.lower()


def test_ci_gate_batch_pr_all_safe():
    """Batch PR evaluation with multiple safe contracts allows merge with exit code 0."""
    c1_base = copy.deepcopy(BASE_CONTRACT)
    c1_target = copy.deepcopy(BASE_CONTRACT)
    c1_target["columns"].append({"name": "c1_extra", "type": "string", "nullable": True, "unique": False, "description": "extra"})

    c2_base = copy.deepcopy(BASE_CONTRACT)
    c2_base["dataset"] = "test_customers"
    c2_target = copy.deepcopy(c2_base)

    summary = CICDContractGatingEngine.evaluate_pr(
        contracts_to_evaluate=[
            (c1_base, c1_target, "contracts/orders.yaml"),
            (c2_base, c2_target, "contracts/customers.yaml")
        ],
        validate_quality=False
    )
    assert summary.verdict == GatingVerdict.SAFE
    assert summary.can_merge is True
    assert summary.exit_code == 0
    assert summary.total_breaking_changes == 0
    assert summary.contracts_with_breaking == 0


def test_ci_gate_batch_pr_with_warning():
    """Batch PR evaluation with one warning contract allows merge with WARNING status."""
    c1_base = copy.deepcopy(BASE_CONTRACT)
    c1_target = copy.deepcopy(BASE_CONTRACT)
    c1_target["columns"].append({"name": "c1_req", "type": "string", "nullable": False, "unique": False, "description": "non-nullable"})

    summary = CICDContractGatingEngine.evaluate_pr(
        contracts_to_evaluate=[
            (c1_base, c1_target, "contracts/orders.yaml")
        ],
        validate_quality=False
    )
    assert summary.verdict == GatingVerdict.WARNING
    assert summary.can_merge is True
    assert summary.exit_code == 0
    assert summary.contracts_with_warnings == 1


def test_ci_gate_batch_pr_with_breaking_blocks_merge():
    """Batch PR evaluation with a breaking contract blocks merge and exits with code 1."""
    c1_base = copy.deepcopy(BASE_CONTRACT)
    c1_target = copy.deepcopy(BASE_CONTRACT)
    # Drop order_id
    c1_target["columns"] = [c for c in c1_target["columns"] if c["name"] != "order_id"]

    summary = CICDContractGatingEngine.evaluate_pr(
        contracts_to_evaluate=[
            (c1_base, c1_target, "contracts/orders.yaml")
        ],
        validate_quality=False
    )
    assert summary.verdict == GatingVerdict.BREAKING
    assert summary.can_merge is False
    assert summary.exit_code == 1
    assert summary.contracts_with_breaking == 1


def test_ci_gate_admin_override_allow_breaking():
    """With allow_breaking=True, PR merge is allowed even if breaking changes exist."""
    c1_base = copy.deepcopy(BASE_CONTRACT)
    c1_target = copy.deepcopy(BASE_CONTRACT)
    c1_target["columns"] = [c for c in c1_target["columns"] if c["name"] != "order_id"]

    summary = CICDContractGatingEngine.evaluate_pr(
        contracts_to_evaluate=[
            (c1_base, c1_target, "contracts/orders.yaml")
        ],
        allow_breaking=True,
        validate_quality=False
    )
    assert summary.can_merge is True
    assert summary.exit_code == 0


def test_ci_gate_markdown_report_formatting():
    """Verifies Markdown summary contains proper GitHub-flavored tables and callouts."""
    c1_base = copy.deepcopy(BASE_CONTRACT)
    c1_target = copy.deepcopy(BASE_CONTRACT)
    c1_target["columns"] = [c for c in c1_target["columns"] if c["name"] != "amount"]

    summary = CICDContractGatingEngine.evaluate_pr(
        contracts_to_evaluate=[
            (c1_base, c1_target, "contracts/orders.yaml")
        ],
        validate_quality=False
    )
    report = summary.markdown_report
    assert "## ❌ DataGuard CI Gate: MERGE BLOCKED" in report
    assert "| Dataset | File | Verdict |" in report
    assert "| `test_orders` | `contracts/orders.yaml` | ❌ BREAKING |" in report
    assert "Detailed Schema Modifications & Remediation" in report
    assert "COLUMN_REMOVED" in report


def test_ci_gate_fastapi_single_gate_endpoint():
    """Test POST /ci/gate endpoint via FastAPI TestClient."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"].append({
        "name": "promo_code",
        "type": "string",
        "nullable": True,
        "unique": False,
        "description": "Optional coupon"
    })
    payload = {
        "baseline_contract": BASE_CONTRACT,
        "target_contract": target,
        "dataset_name": "test_orders",
        "file_path": "contracts/orders.yaml",
        "validate_quality": False
    }
    resp = client.post("/ci/gate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "SAFE"
    assert data["can_merge"] is True
    assert data["breaking_count"] == 0


def test_ci_gate_fastapi_single_gate_breaking_endpoint():
    """Test POST /ci/gate endpoint returns BREAKING for dropped column."""
    target = copy.deepcopy(BASE_CONTRACT)
    target["columns"] = [c for c in target["columns"] if c["name"] != "amount"]
    payload = {
        "baseline_contract": BASE_CONTRACT,
        "target_contract": target,
        "dataset_name": "test_orders",
        "file_path": "contracts/orders.yaml",
        "validate_quality": False
    }
    resp = client.post("/ci/gate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "BREAKING"
    assert data["can_merge"] is False
    assert data["is_breaking"] is True


def test_ci_gate_fastapi_batch_pr_endpoint():
    """Test POST /ci/gate/pr batch endpoint via FastAPI TestClient."""
    target = copy.deepcopy(BASE_CONTRACT)
    payload = {
        "contracts": [
            {
                "baseline_contract": BASE_CONTRACT,
                "target_contract": target,
                "file_path": "contracts/orders.yaml"
            }
        ],
        "allow_breaking": False,
        "validate_quality": False
    }
    resp = client.post("/ci/gate/pr", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "SAFE"
    assert data["can_merge"] is True
    assert data["exit_code"] == 0
    assert "markdown_report" in data


def test_ci_gate_real_contracts_consistency():
    """Validates that real production contracts evaluated against themselves yield SAFE."""
    import yaml
    contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
    yaml_files = list(contracts_dir.glob("*.yaml"))[:5]  # Sample 5 real contracts
    
    for yf in yaml_files:
        with open(yf, "r", encoding="utf-8") as f:
            contract_data = yaml.safe_load(f)
        
        res = CICDContractGatingEngine.evaluate_contract_change(
            baseline_contract=contract_data,
            target_contract=contract_data,
            validate_quality=False
        )
        assert res.contract_valid is True, f"Contract {yf.name} failed structure validation"
        assert res.verdict == GatingVerdict.SAFE, f"Contract {yf.name} produced non-safe diff against itself"
        assert res.can_merge is True
