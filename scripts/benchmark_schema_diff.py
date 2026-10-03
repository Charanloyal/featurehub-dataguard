#!/usr/bin/env python3
"""
DataGuard Schema Diff Performance Benchmark
Measures execution latency (p50, p95, p99) for 10, 50, 100, and 250 columns contracts.
Saves measured metrics and environment information to dataguard/benchmarks/schema_diff_results.json.
"""

import sys
import os
import time
import json
import platform
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dataguard.schema.diff import SchemaDiffEngine


def generate_contract_pair(column_count: int):
    """
    Generates realistic baseline and target contracts with `column_count` columns.
    Introduces a realistic mix of:
    - 5% added nullable columns
    - 5% removed columns
    - 10% type widenings
    - 10% nullability shifts
    - 10% enum modifications
    """
    base_columns = []
    target_columns = []

    types_pool = ["string", "integer", "numeric", "timestamp", "float"]

    for i in range(column_count):
        col_name = f"col_{i:04d}"
        col_type = types_pool[i % len(types_pool)]
        is_nullable = bool(i % 2 == 0)
        is_unique = bool(i == 0)
        desc = f"Synthetic benchmark field {i}"

        base_col = {
            "name": col_name,
            "type": col_type,
            "nullable": is_nullable,
            "unique": is_unique,
            "description": desc
        }

        # Add constraints/enums to some columns
        if col_type == "numeric":
            base_col["min"] = 0.0
            base_col["max"] = 1000.0
        elif col_type == "string" and i % 5 == 0:
            base_col["allowed_values"] = ["ALPHA", "BETA", "GAMMA"]

        base_columns.append(base_col)

        # Build target version variations
        if i % 20 == 1:
            # Drop column in target (removed column)
            continue
        elif i % 20 == 2:
            # Type widening (integer -> numeric)
            tgt_col = dict(base_col)
            tgt_col["type"] = "numeric"
            target_columns.append(tgt_col)
        elif i % 20 == 3:
            # Nullability shift
            tgt_col = dict(base_col)
            tgt_col["nullable"] = not is_nullable
            target_columns.append(tgt_col)
        elif i % 20 == 4 and "allowed_values" in base_col:
            # Enum addition
            tgt_col = dict(base_col)
            tgt_col["allowed_values"] = ["ALPHA", "BETA", "GAMMA", "DELTA"]
            target_columns.append(tgt_col)
        else:
            target_columns.append(dict(base_col))

    # Add 5% new columns to target
    for j in range(max(1, int(column_count * 0.05))):
        target_columns.append({
            "name": f"new_field_{j:03d}",
            "type": "string",
            "nullable": True,
            "unique": False,
            "description": f"New nullable field {j}"
        })

    base_contract = {
        "dataset": f"benchmark_{column_count}_cols",
        "version": "v1.0.0",
        "owner": "benchmark-suite",
        "description": f"Benchmark baseline contract with {column_count} columns",
        "freshness_sla_minutes": 60,
        "columns": base_columns,
        "constraints": ["col_0000 IS NOT NULL"]
    }

    target_contract = {
        "dataset": f"benchmark_{column_count}_cols",
        "version": "v1.1.0",
        "owner": "benchmark-suite",
        "description": f"Benchmark target contract with {column_count} columns",
        "freshness_sla_minutes": 60,
        "columns": target_columns,
        "constraints": ["col_0000 IS NOT NULL"]
    }

    return base_contract, target_contract


def run_benchmark():
    column_scales = [10, 50, 100, 250]
    iterations_per_scale = 100
    warmup_runs = 10

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "system": platform.system()
        },
        "benchmark_parameters": {
            "iterations_per_scale": iterations_per_scale,
            "warmup_runs": warmup_runs,
            "scales_tested": column_scales
        },
        "measurements": {}
    }

    print("==================================================")
    print("DATAGUARD SCHEMA DIFF ENGINE PERFORMANCE BENCHMARK")
    print("==================================================")
    print(f"Platform: {results['environment']['platform']}")
    print(f"Python:   {results['environment']['python_version']}")
    print(f"Runs:     {iterations_per_scale} per scale ({warmup_runs} warmups)")
    print("--------------------------------------------------")

    for cols in column_scales:
        base, tgt = generate_contract_pair(cols)

        # Warmup
        for _ in range(warmup_runs):
            _ = SchemaDiffEngine.compare_contracts(base, tgt)

        # Timed executions
        latencies_ms = []
        for _ in range(iterations_per_scale):
            t0 = time.perf_counter()
            res = SchemaDiffEngine.compare_contracts(base, tgt)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        p50 = float(np.percentile(latencies_ms, 50))
        p95 = float(np.percentile(latencies_ms, 95))
        p99 = float(np.percentile(latencies_ms, 99))
        mean = float(np.mean(latencies_ms))
        min_ms = float(np.min(latencies_ms))
        max_ms = float(np.max(latencies_ms))

        scale_res = {
            "columns": cols,
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "mean_ms": round(mean, 4),
            "min_ms": round(min_ms, 4),
            "max_ms": round(max_ms, 4),
            "total_changes_detected": res.total_changes,
            "classification": res.classification.value if hasattr(res.classification, "value") else str(res.classification)
        }

        results["measurements"][f"{cols}_columns"] = scale_res

        print(f"Columns: {cols:3d} | p50: {p50:6.3f} ms | p95: {p95:6.3f} ms | p99: {p99:6.3f} ms | Mean: {mean:6.3f} ms | Changes: {res.total_changes}")

    # Ensure output directory exists
    output_dir = project_root / "dataguard" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "schema_diff_results.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("--------------------------------------------------")
    print(f"Results successfully saved to: {output_path}")
    print("==================================================")
    return results


if __name__ == "__main__":
    run_benchmark()
