"""
DataGuard OpenLineage Performance Benchmark.
Measures latency and throughput of OpenLineage event ingestion, graph queries,
upstream/downstream graph traversal, and column-level lineage queries on live PostgreSQL 16.
Outputs results to dataguard/benchmarks/lineage_results.json.
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

from dataguard.lineage.repository import LineageRepository
from dataguard.lineage.collector import LineageCollector
from dataguard.lineage.events import RunEvent, Run, Job, InputDataset, OutputDataset
from dataguard.lineage.column_lineage import build_column_lineage_facet


def get_system_metrics(repo: LineageRepository) -> Dict[str, Any]:
    pg_version = "Unknown"
    try:
        with repo.engine.connect() as conn:
            from sqlalchemy import text
            row = conn.execute(text("SELECT version();")).fetchone()
            if row:
                pg_version = row[0]
    except Exception:
        pass

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": f"{platform.processor()} ({psutil.cpu_count(logical=True)} logical cores @ {psutil.cpu_freq().max if psutil.cpu_freq() else 'N/A'}MHz)",
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": platform.python_version(),
        "postgres_version": pg_version.split("\n")[0] if pg_version else "PostgreSQL 16",
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


def run_lineage_benchmark(iterations: int = 25):
    print("=" * 70)
    print("  RUNNING DATAGUARD OPENLINEAGE BENCHMARK (PostgreSQL 16)")
    print(f"  Iterations: {iterations} per operation")
    print("=" * 70)

    repo = LineageRepository()
    collector = LineageCollector(repository=repo)

    # 1. Benchmark: OpenLineage Event Ingestion
    print("\n[1/5] Benchmarking OpenLineage Event Ingestion...")
    ingestion_times: List[float] = []
    for i in range(iterations):
        run_id = f"bench_run_{uuid.uuid4().hex[:12]}"
        col_facet = build_column_lineage_facet("customer_features", "feature_compute")
        event = RunEvent(
            eventType="COMPLETE",
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(runId=run_id, facets={"bench_iter": i}),
            job=Job(namespace="airflow", name=f"benchmark_pipeline_{i % 5}"),
            inputs=[
                InputDataset(namespace="postgres", name="transactions"),
                InputDataset(namespace="postgres", name="customers")
            ],
            outputs=[
                OutputDataset(
                    namespace="featurehub",
                    name="customer_features",
                    facets={"columnLineage": col_facet.model_dump() if hasattr(col_facet, "model_dump") else col_facet.dict()}
                )
            ]
        )
        t0 = time.perf_counter()
        collector.emit_event(event)
        t1 = time.perf_counter()
        ingestion_times.append((t1 - t0) * 1000.0)

    # 2. Benchmark: Dynamic Lineage Graph Query
    print("[2/5] Benchmarking Dynamic Lineage Graph Query (Nodes & Edges)...")
    graph_times: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        g = repo.get_graph()
        t1 = time.perf_counter()
        graph_times.append((t1 - t0) * 1000.0)

    # 3. Benchmark: Upstream Graph Traversal
    print("[3/5] Benchmarking Upstream Graph Traversal (customer_features -> sources)...")
    upstream_times: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        up = repo.get_upstream("customer_features", max_depth=5)
        t1 = time.perf_counter()
        upstream_times.append((t1 - t0) * 1000.0)

    # 4. Benchmark: Downstream Graph Traversal
    print("[4/5] Benchmarking Downstream Graph Traversal (transactions_clean -> sinks)...")
    downstream_times: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        down = repo.get_downstream("transactions_clean", max_depth=5)
        t1 = time.perf_counter()
        downstream_times.append((t1 - t0) * 1000.0)

    # 5. Benchmark: Column-Level Lineage Query
    print("[5/5] Benchmarking Column Lineage Query (transaction_features)...")
    column_times: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        cols = repo.get_column_lineage("transaction_features")
        t1 = time.perf_counter()
        column_times.append((t1 - t0) * 1000.0)

    # Compile Final Benchmark Structure
    counts = repo.get_counts()
    sys_metrics = get_system_metrics(repo)

    results = {
        "system": sys_metrics,
        "graph_state": {
            "total_nodes": len(g.nodes),
            "total_edges": len(g.edges),
            "total_datasets": counts["datasets"],
            "total_jobs": counts["jobs"],
            "total_runs": counts["runs"],
            "total_column_mappings": counts["column_mappings"]
        },
        "benchmarks": {
            "event_ingestion": compute_stats(ingestion_times),
            "lineage_graph_query": compute_stats(graph_times),
            "upstream_traversal": compute_stats(upstream_times),
            "downstream_traversal": compute_stats(downstream_times),
            "column_lineage_query": compute_stats(column_times)
        },
        "summary": {
            "sample_size": iterations,
            "persistence_backend": "PostgreSQL 16",
            "standard": "OpenLineage 1.0.5 compliant JSON"
        }
    }

    # Save to JSON artifact
    out_dir = Path(__file__).resolve().parent.parent / "dataguard" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "lineage_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print("  LINEAGE BENCHMARK RESULTS")
    print("=" * 70)
    print(f"  Event Ingestion (Mean)     : {results['benchmarks']['event_ingestion']['mean_ms']} ms ({results['benchmarks']['event_ingestion']['operations_per_second']} ops/s)")
    print(f"  Graph Query (Mean)         : {results['benchmarks']['lineage_graph_query']['mean_ms']} ms ({results['benchmarks']['lineage_graph_query']['operations_per_second']} ops/s)")
    print(f"  Upstream Traversal (Mean)  : {results['benchmarks']['upstream_traversal']['mean_ms']} ms ({results['benchmarks']['upstream_traversal']['operations_per_second']} ops/s)")
    print(f"  Downstream Traversal (Mean): {results['benchmarks']['downstream_traversal']['mean_ms']} ms ({results['benchmarks']['downstream_traversal']['operations_per_second']} ops/s)")
    print(f"  Column Lineage Query (Mean): {results['benchmarks']['column_lineage_query']['mean_ms']} ms ({results['benchmarks']['column_lineage_query']['operations_per_second']} ops/s)")
    print(f"  Saved to: {out_file}")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_lineage_benchmark()
