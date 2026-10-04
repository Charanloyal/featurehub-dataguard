#!/usr/bin/env python3
"""
FeatureHub + DataGuard Integrated Platform Performance Benchmark.
Measures latency breakdown across all 11 stages of the integrated flow:
Data Source -> Feature Compute -> Contracts -> Schema Diff -> Quality ->
Lineage -> Airflow -> Offline Store -> Materialization -> Redis -> ML Inference.

Also benchmarks the fast-fail protection path:
Breaking Schema / Bad Data / Stale Features -> Immediate Abort & Protection.
Saves comprehensive results to featurehub/benchmarks/integration_results.json.
"""

import sys
import time
import json
import platform
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from featurehub.integration.service import FeatureHubDataGuardIntegrator
from featurehub.integration.models import StageStatus


def benchmark_integration_platform():
    integrator = FeatureHubDataGuardIntegrator()

    print("=" * 80)
    print("FEATUREHUB + DATAGUARD INTEGRATED PLATFORM BENCHMARK")
    print(f"Platform: {platform.system()} {platform.machine()} | Python {platform.python_version()}")
    print("=" * 80)

    # 1. Benchmark Happy Path (Full 11 Stages)
    print("\n[+] Benchmarking Full End-to-End Success Path (11 Stages)...")
    happy_iterations = 5
    happy_durations_ms: List[float] = []
    stage_durations_ms: Dict[str, List[float]] = {}
    last_res = None

    for i in range(happy_iterations):
        t0 = time.perf_counter()
        res = integrator.run_e2e_pipeline(target_customer_id="cust_000001")
        t1 = time.perf_counter()
        dur = (t1 - t0) * 1000.0
        happy_durations_ms.append(dur)
        last_res = res

        for s in res.stages:
            s_name = s.stage.value
            if s_name not in stage_durations_ms:
                stage_durations_ms[s_name] = []
            stage_durations_ms[s_name].append(s.duration_ms)

        print(f"  Iteration {i + 1}/{happy_iterations}: {dur:.2f}ms | Status: {res.status.value}")

    happy_durations_ms.sort()
    happy_p50 = happy_durations_ms[len(happy_durations_ms) // 2]
    happy_p95 = happy_durations_ms[int(0.95 * len(happy_durations_ms))]
    happy_mean = sum(happy_durations_ms) / len(happy_durations_ms)

    stage_breakdown = {}
    for s_name, times in stage_durations_ms.items():
        avg_time = sum(times) / len(times)
        stage_breakdown[s_name] = {
            "mean_ms": round(avg_time, 2),
            "percentage_of_total": round((avg_time / happy_mean) * 100.0, 1) if happy_mean > 0 else 0.0
        }

    # 2. Benchmark Fast-Fail Failure Paths
    print("\n[+] Benchmarking Fast-Fail Data Integrity Protection Paths...")
    fail_scenarios = ["BREAKING_SCHEMA", "NULL_VIOLATION", "RANGE_VIOLATION", "STALE_FEATURES"]
    failure_benchmarks = {}

    for sc in fail_scenarios:
        t0 = time.perf_counter()
        fail_res = integrator.run_e2e_pipeline(inject_anomaly=sc)
        t1 = time.perf_counter()
        dur = (t1 - t0) * 1000.0
        failure_benchmarks[sc] = {
            "status": fail_res.status.value,
            "duration_ms": round(dur, 2),
            "incident_id": fail_res.incident_id,
            "incident_severity": fail_res.incident_severity,
            "incident_owner": fail_res.incident_owner,
            "failing_reason": fail_res.error_message
        }
        print(f"  Anomaly [{sc:<16}]: {dur:6.2f}ms | Incident: {fail_res.incident_id} ({fail_res.incident_severity}) | Owner: {fail_res.incident_owner}")

    # Compile benchmark payload
    bench_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "system": platform.system()
        },
        "success_path": {
            "iterations": happy_iterations,
            "total_mean_ms": round(happy_mean, 2),
            "total_p50_ms": round(happy_p50, 2),
            "total_p95_ms": round(happy_p95, 2),
            "records_computed": last_res.features_computed_count if last_res else 0,
            "records_materialized": last_res.records_materialized_count if last_res else 0,
            "quality_score": last_res.quality_score if last_res else 0.0,
            "ml_prediction_risk_score": last_res.ml_prediction.get("risk_score") if last_res and last_res.ml_prediction else None,
            "stages_breakdown": stage_breakdown
        },
        "failure_paths": failure_benchmarks
    }

    out_dir = Path(__file__).resolve().parent.parent / "featurehub" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "integration_results.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bench_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Benchmark results successfully saved to: {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_integration_platform()
