#!/usr/bin/env python3
"""
DataGuard CI/CD Compatibility & Quality Gate Performance Benchmark.
Measures latency and throughput across contract scales: 10, 50, 100, 250 columns.
Saves comprehensive results to dataguard/benchmarks/ci_gate_results.json.
"""

import os
import sys
import time
import json
import random
import platform
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataguard.ci.gate import CICDContractGatingEngine
from dataguard.ci.models import GatingVerdict


def generate_contract(col_count: int, seed: int = 42) -> Dict[str, Any]:
    random.seed(seed)
    types = ["string", "numeric", "integer", "timestamp", "float"]
    columns = []
    for i in range(col_count):
        col_type = types[i % len(types)]
        col = {
            "name": f"col_{i:04d}",
            "type": col_type,
            "nullable": (i % 3 != 0),
            "unique": (i == 0),
            "description": f"Benchmark column {i}"
        }
        if col_type == "numeric":
            col["min"] = 0.0
            col["max"] = 1000.0
        elif col_type == "string" and i % 5 == 0:
            col["allowed_values"] = ["ALPHA", "BETA", "GAMMA"]
        columns.append(col)

    return {
        "dataset": f"benchmark_dataset_{col_count}",
        "version": "v1.0.0",
        "owner": "data_platform",
        "description": f"Synthetic contract with {col_count} columns",
        "freshness_sla_minutes": 60,
        "status": "ACTIVE",
        "columns": columns,
        "constraints": []
    }


def generate_evolved_contract(base: Dict[str, Any]) -> Dict[str, Any]:
    """Generates an evolved target contract with safe, warning, and breaking changes."""
    import copy
    target = copy.deepcopy(base)
    cols = target["columns"]
    col_count = len(cols)

    # 1 breaking change: drop a column
    if col_count > 1:
        cols.pop(1)

    # 1 breaking change: incompatible type change
    if col_count > 2:
        cols[1]["type"] = "string" if cols[1]["type"] != "string" else "integer"

    # 1 warning change: add non-nullable column
    cols.append({
        "name": f"col_new_req_{col_count}",
        "type": "string",
        "nullable": False,
        "unique": False,
        "description": "Added non-nullable column"
    })

    # 1 safe change: add nullable column
    cols.append({
        "name": f"col_new_opt_{col_count}",
        "type": "string",
        "nullable": True,
        "unique": False,
        "description": "Added nullable column"
    })

    return target


def benchmark_ci_gate():
    scales = [10, 50, 100, 250]
    iterations = 100
    warmup = 10

    measurements = {}

    print("=" * 70)
    print("DATAGUARD CI/CD GATING ENGINE BENCHMARK")
    print(f"Platform: {platform.system()} {platform.machine()} | Python {platform.python_version()}")
    print("=" * 70)

    for scale in scales:
        base = generate_contract(scale, seed=scale)
        target = generate_evolved_contract(base)

        # Warmup runs
        for _ in range(warmup):
            CICDContractGatingEngine.evaluate_contract_change(
                baseline_contract=base,
                target_contract=target,
                validate_quality=False
            )

        # Timed runs
        durations_ms: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            res = CICDContractGatingEngine.evaluate_contract_change(
                baseline_contract=base,
                target_contract=target,
                validate_quality=False
            )
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000.0)

        durations_ms.sort()
        p50 = durations_ms[int(0.50 * iterations)]
        p95 = durations_ms[int(0.95 * iterations)]
        p99 = durations_ms[int(0.99 * iterations)]
        mean = sum(durations_ms) / len(durations_ms)
        min_v = min(durations_ms)
        max_v = max(durations_ms)
        throughput = 1000.0 / mean if mean > 0 else 0.0

        measurements[f"{scale}_columns"] = {
            "columns": scale,
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "mean_ms": round(mean, 4),
            "min_ms": round(min_v, 4),
            "max_ms": round(max_v, 4),
            "throughput_evals_per_sec": round(throughput, 1),
            "verdict": res.verdict.value,
            "breaking_count": res.breaking_count,
            "warning_count": res.warning_count,
            "safe_count": res.safe_count
        }

        print(f"[{scale:3d} Columns] Mean: {mean:6.3f}ms | p50: {p50:6.3f}ms | p95: {p95:6.3f}ms | p99: {p99:6.3f}ms | Throughput: {throughput:6.1f} evals/sec")

    # Measure full PR batch evaluation (25 real contracts)
    contracts_dir = Path(__file__).resolve().parent.parent / "dataguard" / "contracts"
    yaml_files = list(contracts_dir.glob("*.yaml"))
    
    import yaml
    pr_items = []
    for yf in yaml_files:
        with open(yf, "r", encoding="utf-8") as f:
            c = yaml.safe_load(f)
            pr_items.append((c, c, str(yf.name)))

    batch_durations_ms = []
    for _ in range(50):
        t0 = time.perf_counter()
        summary = CICDContractGatingEngine.evaluate_pr(
            contracts_to_evaluate=pr_items,
            validate_quality=False
        )
        t1 = time.perf_counter()
        batch_durations_ms.append((t1 - t0) * 1000.0)

    batch_durations_ms.sort()
    batch_p50 = batch_durations_ms[int(0.50 * len(batch_durations_ms))]
    batch_p95 = batch_durations_ms[int(0.95 * len(batch_durations_ms))]
    batch_mean = sum(batch_durations_ms) / len(batch_durations_ms)

    measurements["batch_pr_25_contracts"] = {
        "contracts_evaluated": len(pr_items),
        "mean_ms": round(batch_mean, 4),
        "p50_ms": round(batch_p50, 4),
        "p95_ms": round(batch_p95, 4),
        "verdict": summary.verdict.value,
        "throughput_prs_per_sec": round(1000.0 / batch_mean, 1)
    }

    print("-" * 70)
    print(f"[Full PR (25 Contracts)] Mean: {batch_mean:6.3f}ms | p50: {batch_p50:6.3f}ms | p95: {batch_p95:6.3f}ms")
    print("=" * 70)

    out_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "system": platform.system()
        },
        "benchmark_parameters": {
            "iterations_per_scale": iterations,
            "warmup_runs": warmup,
            "scales_tested": scales
        },
        "measurements": measurements
    }

    out_path = Path(__file__).resolve().parent.parent / "dataguard" / "benchmarks" / "ci_gate_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"\nSaved benchmark results to {out_path}")


if __name__ == "__main__":
    benchmark_ci_gate()
