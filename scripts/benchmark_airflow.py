"""
DataGuard Phase G - Apache Airflow & Pipeline Orchestration Benchmark.
Measures latency, throughput, and overhead of DAG parsing, end-to-end pipeline execution,
deterministic failure detection, OpenLineage emission, and repository querying on live PostgreSQL 16.
Outputs results to dataguard/benchmarks/airflow_results.json.
"""

import sys
import os
import json
import time
import uuid
import platform
import psutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataguard.pipelines.runner import DataGuardPipelineOrchestrator
from dataguard.pipelines.repository import PipelineRepository
from dataguard.pipelines.registry import PipelineRegistryService
from dataguard.pipelines.freshness import FreshnessMonitorService


def get_system_metrics(repo: PipelineRepository) -> Dict[str, Any]:
    pg_version = "PostgreSQL 16"
    try:
        with repo.engine.connect() as conn:
            from sqlalchemy import text
            row = conn.execute(text("SELECT version();")).fetchone()
            if row:
                pg_version = row[0].split("\n")[0]
    except Exception:
        pass

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": f"{platform.processor()} ({psutil.cpu_count(logical=True)} logical cores @ {psutil.cpu_freq().max if psutil.cpu_freq() else 'N/A'}MHz)",
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": platform.python_version(),
        "postgres_version": pg_version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def compute_stats(durations_ms: List[float]) -> Dict[str, Any]:
    arr = np.array(durations_ms)
    return {
        "p50_ms": round(float(np.percentile(arr, 50)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "p99_ms": round(float(np.percentile(arr, 99)), 2),
        "mean_ms": round(float(np.mean(arr)), 2),
        "std_ms": round(float(np.std(arr)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "operations_per_second": round(1000.0 / float(np.mean(arr)), 2) if np.mean(arr) > 0 else 0
    }


def run_benchmark():
    print("=" * 70)
    print("DATAGUARD PHASE G: AIRFLOW PIPELINE ORCHESTRATION BENCHMARK")
    print("=" * 70)

    repo = PipelineRepository()
    orchestrator = DataGuardPipelineOrchestrator()
    freshness = FreshnessMonitorService()

    system_metrics = get_system_metrics(repo)
    print(f"Host System   : {system_metrics['os']}")
    print(f"CPU / Cores   : {system_metrics['cpu']}")
    print(f"Memory        : {system_metrics['ram_total_gb']} GB")
    print(f"PostgreSQL    : {system_metrics['postgres_version']}")
    print("-" * 70)

    results: Dict[str, Any] = {
        "benchmark": "DataGuard Apache Airflow Pipeline Orchestration",
        "phase": "Phase G",
        "system": system_metrics,
        "metrics": {}
    }

    # 1. DAG Loading & Parse Time
    print("\n[1/5] Benchmarking DAG Loading & Parse Time (10 iterations)...")
    dag_files = [
        "customer_quality_pipeline",
        "transaction_quality_pipeline",
        "feature_quality_pipeline",
        "schema_validation_pipeline",
        "freshness_monitoring_pipeline",
        "demo_test_pipelines"
    ]
    dag_durations = []
    for _ in range(10):
        t0 = time.perf_counter()
        import importlib
        for df in dag_files:
            mod = importlib.import_module(f"pipelines.airflow.dags.{df}")
            importlib.reload(mod)
        dag_durations.append((time.perf_counter() - t0) * 1000.0)

    results["metrics"]["dag_parsing"] = compute_stats(dag_durations)
    print(f"  DAG Parse Mean Latency: {results['metrics']['dag_parsing']['mean_ms']} ms "
          f"(P95: {results['metrics']['dag_parsing']['p95_ms']} ms)")

    # 2. E2E Clean Pipeline Execution
    print("\n[2/5] Benchmarking E2E Clean Pipeline Executions (10 runs each)...")
    clean_pipelines = [
        ("customer_quality_pipeline", "customers"),
        ("transaction_quality_pipeline", "transactions"),
        ("feature_quality_pipeline", "customer_features")
    ]
    results["metrics"]["clean_pipelines"] = {}

    for pipe_id, ds in clean_pipelines:
        durations = []
        for i in range(10):
            t0 = time.perf_counter()
            res = orchestrator.execute_pipeline(pipe_id, run_id=f"bench_clean_{pipe_id}_{i}")
            durations.append((time.perf_counter() - t0) * 1000.0)
            assert res.get("status") == "SUCCESS", f"Pipeline failed: {res}"

        stats = compute_stats(durations)
        results["metrics"]["clean_pipelines"][pipe_id] = stats
        print(f"  {pipe_id:30s}: Mean {stats['mean_ms']:6.2f} ms | P95 {stats['p95_ms']:6.2f} ms | Ops/sec {stats['operations_per_second']:5.2f}")

    # 3. Deterministic Failure Scenario Execution (Fast-Fail Latency)
    print("\n[3/5] Benchmarking Failure Scenario Fast-Fail Latencies (5 runs each)...")
    scenarios = [
        ("breaking_schema", "customer_quality_pipeline"),
        ("null_violation", "customer_quality_pipeline"),
        ("duplicate_violation", "customer_quality_pipeline"),
        ("enum_violation", "customer_quality_pipeline"),
        ("stale_dataset", "freshness_monitoring_pipeline")
    ]
    results["metrics"]["failure_scenarios"] = {}

    for scen, pipe_id in scenarios:
        durations = []
        for i in range(5):
            t0 = time.perf_counter()
            res = orchestrator.execute_pipeline(pipe_id, test_scenario=scen, raise_on_failure=False, run_id=f"bench_fail_{scen}_{i}")
            durations.append((time.perf_counter() - t0) * 1000.0)
            assert res.get("status") == "FAILED", f"Scenario did not fail: {res}"

        stats = compute_stats(durations)
        results["metrics"]["failure_scenarios"][scen] = stats
        print(f"  {scen:25s}: Mean {stats['mean_ms']:6.2f} ms | P95 {stats['p95_ms']:6.2f} ms | Fast-fail OK")

    # 4. Idempotent Rerun Overhead
    print("\n[4/5] Benchmarking Idempotent Reruns (10 runs with identical run_id)...")
    rerun_durations = []
    fixed_id = f"bench_idempotent_{uuid.uuid4().hex[:8]}"
    for _ in range(10):
        t0 = time.perf_counter()
        res = orchestrator.execute_pipeline("customer_quality_pipeline", run_id=fixed_id)
        rerun_durations.append((time.perf_counter() - t0) * 1000.0)
        assert res.get("status") == "SUCCESS"

    results["metrics"]["idempotent_rerun"] = compute_stats(rerun_durations)
    print(f"  Idempotent Rerun Mean : {results['metrics']['idempotent_rerun']['mean_ms']} ms "
          f"(P95: {results['metrics']['idempotent_rerun']['p95_ms']} ms)")

    # 5. Metadata Repository & Analytics Query Throughput
    print("\n[5/5] Benchmarking PostgreSQL Pipeline Queries (50 iterations)...")
    query_benchmarks = {
        "get_pipeline_summary": lambda: repo.get_pipeline_summary(),
        "get_pipeline_health": lambda: repo.get_pipeline_health("customer_quality_pipeline"),
        "list_runs": lambda: repo.list_runs("customer_quality_pipeline", limit=20),
        "list_pipelines": lambda: repo.list_pipelines()
    }
    results["metrics"]["repository_queries"] = {}

    for q_name, fn in query_benchmarks.items():
        durations = []
        for _ in range(50):
            t0 = time.perf_counter()
            fn()
            durations.append((time.perf_counter() - t0) * 1000.0)

        stats = compute_stats(durations)
        results["metrics"]["repository_queries"][q_name] = stats
        print(f"  {q_name:25s}: Mean {stats['mean_ms']:5.2f} ms | P95 {stats['p95_ms']:5.2f} ms | Ops/sec {stats['operations_per_second']:6.1f}")

    # Output JSON
    output_path = Path(__file__).resolve().parent.parent / "dataguard" / "benchmarks" / "airflow_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"BENCHMARK COMPLETE - Results saved to {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
