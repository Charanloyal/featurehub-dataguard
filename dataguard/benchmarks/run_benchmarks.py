"""
DataGuard Governance & CI Benchmark Runner
Executes micro-benchmarks for Contract Parsing, Schema Drift Engine, Quality Validation, and CI blocking metrics.
Stores output in dataguard/benchmarks/results.json.
"""

import os
import sys
import os
from pathlib import Path
BENCHMARK_DIR = Path(__file__).resolve().parent
BASE_DIR = BENCHMARK_DIR.parent.parent
sys.path.insert(0, str(BASE_DIR))

import json
import time
import yaml
import platform
import psutil
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from dataguard.schema.diff import SchemaDiffEngine
from dataguard.quality.service import DataQualityEngine

BENCHMARK_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = BENCHMARK_DIR.parent / "contracts"
RESULTS_FILE = BENCHMARK_DIR / "results.json"

def run_dataguard_benchmarks() -> dict:
    print("Executing DataGuard Governance Benchmarks...")
    
    # Load all 25 contracts
    contracts = []
    t0_parse = time.perf_counter()
    for p in CONTRACTS_DIR.glob("*.yaml"):
        with open(p, "r") as f:
            contracts.append(yaml.safe_load(f))
    t1_parse = time.perf_counter()
    parse_duration_ms = (t1_parse - t0_parse) * 1000.0

    # 1. Benchmark: Schema Diff Engine (100 synthetic diffs)
    diff_latencies_ms = []
    breaking_detected = 0
    total_diffs = 100

    for i in range(total_diffs):
        base_c = contracts[i % len(contracts)]
        target_c = json.loads(json.dumps(base_c))
        
        # Inject breaking changes into half of the diffs
        if i % 2 == 0:
            if target_c.get("columns"):
                target_c["columns"].pop(0) # Remove first column (BREAKING)

        t0 = time.perf_counter()
        res = SchemaDiffEngine.compare_contracts(base_c, target_c)
        t1 = time.perf_counter()
        diff_latencies_ms.append((t1 - t0) * 1000.0)
        
        if res["is_breaking"]:
            breaking_detected += 1

    diff_p50 = float(np.percentile(diff_latencies_ms, 50))
    diff_p95 = float(np.percentile(diff_latencies_ms, 95))
    diff_p99 = float(np.percentile(diff_latencies_ms, 99))

    # 2. Benchmark: Data Quality Engine
    quality_engine = DataQualityEngine()
    sample_df = pd.DataFrame([
        {"customer_id": f"cust_{i:04d}", "created_at": "2026-01-01T00:00:00Z", "kyc_status": "VERIFIED", "risk_tier": "LOW", "country": "US"}
        for i in range(500)
    ])
    
    cust_contract = [c for c in contracts if c.get("dataset") == "customers"][0]
    
    t0_val = time.perf_counter()
    val_res = quality_engine.validate_dataset("customers", sample_df, cust_contract)
    t1_val = time.perf_counter()
    val_duration_ms = (t1_val - t0_val) * 1000.0

    # Calculate blocked breaking changes ratio
    blocked_ratio = float(breaking_detected / (total_diffs / 2.0)) if total_diffs > 0 else 1.0

    results = {
        "benchmark_name": "DataGuard Governance & CI Engine",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_contracts_validated": len(contracts),
        "contract_parsing_duration_ms": round(parse_duration_ms, 3),
        "schema_diff": {
            "total_diff_simulations": total_diffs,
            "p50_latency_ms": round(diff_p50, 4),
            "p95_latency_ms": round(diff_p95, 4),
            "p99_latency_ms": round(diff_p99, 4),
            "breaking_changes_detected": breaking_detected,
            "breaking_changes_blocked_ratio": round(blocked_ratio, 4)
        },
        "data_quality": {
            "dataset_rows_validated": len(sample_df),
            "validation_duration_ms": round(val_duration_ms, 3),
            "total_checks_executed": val_res["total_checks"],
            "passed_checks": val_res["passed_checks"]
        }
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"DataGuard benchmark results written to {RESULTS_FILE}")
    print(f"  Contract Parsing -> {len(contracts)} contracts parsed in {parse_duration_ms:.2f}ms")
    print(f"  Schema Diff     -> p50: {diff_p50:.4f}ms | p95: {diff_p95:.4f}ms | Blocked: {breaking_detected}/{total_diffs//2}")
    print(f"  Data Quality    -> {val_res['total_checks']} checks on {len(sample_df)} rows in {val_duration_ms:.2f}ms")

    return results

if __name__ == "__main__":
    run_dataguard_benchmarks()
