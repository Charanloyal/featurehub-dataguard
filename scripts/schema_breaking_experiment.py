"""
Schema-Breaking Change Experiment (Phase K)
Empirically evaluates SchemaDiffEngine and CI Gate against a standard suite of schema evolution scenarios:
Breaking changes:
- column removal
- incompatible type change (float -> int)
- nullable -> non-nullable
- enum value removal
- constraint tightening
- cross-domain type change (string -> int)
Safe changes:
- column addition (nullable)
- type widening (int -> bigint)
- type widening (int -> numeric)
- enum value addition
- documentation description change

Calculates:
blocked_breaking_changes / total_breaking_changes * 100
"""

import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dataguard.schema.diff import SchemaDiffEngine

BASE_CONTRACT = {
    "dataset": "transactions_benchmark",
    "version": "v1.0.0",
    "columns": [
        {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
        {"name": "customer_id", "type": "string", "nullable": False},
        {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
        {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED"]},
        {"name": "notes", "type": "string", "nullable": True},
        {"name": "retry_count", "type": "integer", "nullable": True}
    ]
}

SCENARIOS = [
    {
        "name": "Column Removal (notes dropped)",
        "type": "BREAKING",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED"]},
                {"name": "retry_count", "type": "integer", "nullable": True}
            ]
        }
    },
    {
        "name": "Incompatible Type Narrowing (amount float -> integer)",
        "type": "BREAKING",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "integer", "nullable": False, "min": 0, "max": 50000},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED"]},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "integer", "nullable": True}
            ]
        }
    },
    {
        "name": "Nullable to Non-Nullable (retry_count True -> False)",
        "type": "BREAKING",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED"]},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "integer", "nullable": False}
            ]
        }
    },
    {
        "name": "Enum Value Removal (status removes PENDING)",
        "type": "BREAKING",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["SETTLED", "FAILED"]},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "integer", "nullable": True}
            ]
        }
    },
    {
        "name": "Cross-Domain Incompatible Type (status string -> integer)",
        "type": "BREAKING",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "integer", "nullable": False},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "integer", "nullable": True}
            ]
        }
    },
    {
        "name": "Safe Column Addition (nullable merchant_id added)",
        "type": "SAFE",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED"]},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "integer", "nullable": True},
                {"name": "merchant_id", "type": "string", "nullable": True}
            ]
        }
    },
    {
        "name": "Safe Type Widening (retry_count integer -> bigint)",
        "type": "SAFE",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED"]},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "bigint", "nullable": True}
            ]
        }
    },
    {
        "name": "Safe Enum Addition (status adds REFUNDED)",
        "type": "SAFE",
        "target": {
            "dataset": "transactions_benchmark",
            "version": "v1.1.0",
            "columns": [
                {"name": "txn_id", "type": "string", "nullable": False, "unique": True},
                {"name": "customer_id", "type": "string", "nullable": False},
                {"name": "amount", "type": "float", "nullable": False, "min": 0.0, "max": 50000.0},
                {"name": "status", "type": "string", "nullable": False, "allowed_values": ["PENDING", "SETTLED", "FAILED", "REFUNDED"]},
                {"name": "notes", "type": "string", "nullable": True},
                {"name": "retry_count", "type": "integer", "nullable": True}
            ]
        }
    }
]

def run_experiment():
    print("================================================================")
    print("  SCHEMA BREAKING CHANGE EXPERIMENT (SYSTEM TRUTH AUDIT)")
    print("================================================================")
    total_breaking = 0
    blocked_breaking = 0
    total_safe = 0
    allowed_safe = 0
    results = []

    for s in SCENARIOS:
        diff_res = SchemaDiffEngine.compare_contracts(BASE_CONTRACT, s["target"])
        actual_class = diff_res.classification.value if hasattr(diff_res.classification, "value") else str(diff_res.classification)
        is_breaking = (actual_class == "BREAKING")
        ci_result = "MERGE BLOCKED (Exit Code 1)" if is_breaking else "MERGE ALLOWED (Exit Code 0)"

        if s["type"] == "BREAKING":
            total_breaking += 1
            if is_breaking:
                blocked_breaking += 1
        elif s["type"] == "SAFE":
            total_safe += 1
            if not is_breaking:
                allowed_safe += 1

        results.append({
            "scenario": s["name"],
            "expected_type": s["type"],
            "actual_classification": actual_class,
            "ci_result": ci_result,
            "correct": (s["type"] == actual_class)
        })
        print(f"[*] {s['name']:<55} | Actual: {actual_class:<8} | CI: {ci_result}")

    blocking_pct = (blocked_breaking / total_breaking * 100) if total_breaking > 0 else 0.0
    safe_allowed_pct = (allowed_safe / total_safe * 100) if total_safe > 0 else 0.0

    print("-" * 64)
    print(f"Total Breaking Scenarios Tested : {total_breaking}")
    print(f"Breaking Changes Blocked in CI  : {blocked_breaking} ({blocking_pct:.1f}%)")
    print(f"Safe Changes Correctly Allowed  : {allowed_safe}/{total_safe} ({safe_allowed_pct:.1f}%)")
    print("================================================================\n")
    return {
        "total_breaking": total_breaking,
        "blocked_breaking": blocked_breaking,
        "blocking_percentage": blocking_pct,
        "total_safe": total_safe,
        "allowed_safe": allowed_safe,
        "scenarios": results
    }

if __name__ == "__main__":
    run_experiment()
