"""
DataGuard Incident Management Performance Benchmark (Phase E).
Benchmarks incident creation, deduplication processing, querying, acknowledgement, and resolution latencies against live PostgreSQL.
Persists structured metrics to dataguard/benchmarks/incident_results.json.
"""

import os
import sys
import time
import json
import platform
import psutil
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dataguard.contracts.registry import ContractRegistryService, get_default_db_url
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.manager import IncidentManager
from dataguard.quality.models import QualityCheckResult, QualityStatus

BENCHMARK_DIR = ROOT_DIR / "dataguard" / "benchmarks"
RESULTS_FILE = BENCHMARK_DIR / "incident_results.json"


def get_system_hardware_info(engine):
    """Captures CPU, RAM, OS, and PostgreSQL version."""
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    cpu_freq = psutil.cpu_freq()
    freq_str = f" @ {cpu_freq.max:.1f}MHz" if cpu_freq else ""
    cpu_info = f"{platform.processor() or 'x86_64'} ({os.cpu_count()} logical cores{freq_str})"

    # Query real PostgreSQL version
    pg_version = "PostgreSQL 16"
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version()")).scalar()
            if row:
                pg_version = row.split(",")[0]
    except Exception:
        pass

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": cpu_info,
        "ram_total_gb": ram_gb,
        "python_version": platform.python_version(),
        "postgres_version": pg_version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def compute_stats(latencies_ms):
    arr = np.array(latencies_ms)
    return {
        "p50_ms": round(float(np.percentile(arr, 50)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "p99_ms": round(float(np.percentile(arr, 99)), 2),
        "mean_ms": round(float(np.mean(arr)), 2),
        "std_ms": round(float(np.std(arr)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "operations_per_second": round(1000.0 / float(np.mean(arr)), 2) if float(np.mean(arr)) > 0 else 0.0
    }


def main():
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    url = get_default_db_url()
    repo = IncidentRepository(db_url=url)
    registry = ContractRegistryService(db_url=url)
    mgr = IncidentManager(repository=repo, registry_service=registry)

    hw_info = get_system_hardware_info(repo.engine)
    print("Environment:")
    print(json.dumps(hw_info, indent=2))

    iterations = 25

    # 1. Benchmark Incident Creation
    print(f"\nBenchmarking incident creation ({iterations} iterations)...")
    creation_latencies = []
    created_ids = []

    for i in range(iterations):
        mock_check = QualityCheckResult(
            run_id=f"bench_run_{i}",
            dataset="orders",
            check_name=f"bench_unique_check_{i}",
            column="order_id",
            expectation_type="expect_column_values_to_be_unique",
            status=QualityStatus.FAIL,
            severity="CRITICAL",
            observed_value="Duplicate ID detected",
            expected_value="Distinct IDs",
            success=False,
            pipeline="benchmark_pipeline"
        )
        t0 = time.perf_counter()
        inc = mgr.handle_check_failure(mock_check, dataset="orders", pipeline="benchmark_pipeline")
        elapsed = (time.perf_counter() - t0) * 1000.0
        creation_latencies.append(elapsed)
        created_ids.append(inc.incident_id)

    creation_stats = compute_stats(creation_latencies)

    # 2. Benchmark Duplicate Failure Processing (Deduplication)
    print(f"Benchmarking duplicate failure deduplication ({iterations} iterations)...")
    dedup_latencies = []
    # Re-use the last failing check
    for _ in range(iterations):
        t0 = time.perf_counter()
        inc_dup = mgr.handle_check_failure(mock_check, dataset="orders", pipeline="benchmark_pipeline")
        elapsed = (time.perf_counter() - t0) * 1000.0
        dedup_latencies.append(elapsed)

    dedup_stats = compute_stats(dedup_latencies)

    # 3. Benchmark Incident Querying
    print(f"Benchmarking incident queries ({iterations} iterations)...")
    query_latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = mgr.list_incidents(dataset="orders", status="OPEN", limit=50)
        elapsed = (time.perf_counter() - t0) * 1000.0
        query_latencies.append(elapsed)

    query_stats = compute_stats(query_latencies)

    # 4. Benchmark Incident Acknowledgement
    print(f"Benchmarking incident acknowledgement ({iterations} iterations)...")
    ack_latencies = []
    for inc_id in created_ids:
        t0 = time.perf_counter()
        _ = mgr.acknowledge_incident(inc_id, actor="benchmark_runner", notes="Bench ack")
        elapsed = (time.perf_counter() - t0) * 1000.0
        ack_latencies.append(elapsed)

    ack_stats = compute_stats(ack_latencies)

    # 5. Benchmark Incident Resolution
    print(f"Benchmarking incident resolution ({iterations} iterations)...")
    res_latencies = []
    for inc_id in created_ids:
        t0 = time.perf_counter()
        _ = mgr.resolve_incident(inc_id, actor="benchmark_runner", notes="Bench resolve")
        elapsed = (time.perf_counter() - t0) * 1000.0
        res_latencies.append(elapsed)

    res_stats = compute_stats(res_latencies)

    # Count total incidents and events in database
    with repo.engine.connect() as conn:
        total_inc = conn.execute(text("SELECT count(*) FROM incidents")).scalar()
        total_ev = conn.execute(text("SELECT count(*) FROM incident_events")).scalar()

    benchmark_payload = {
        "system": hw_info,
        "database": {
            "total_incidents": total_inc,
            "total_events": total_ev
        },
        "benchmarks": {
            "incident_creation": creation_stats,
            "duplicate_processing_deduplication": dedup_stats,
            "incident_query": query_stats,
            "incident_acknowledgement": ack_stats,
            "incident_resolution": res_stats
        },
        "summary": {
            "sample_size": iterations,
            "persistence_backend": "PostgreSQL 16",
            "deduplication_engine": "Deterministic SHA-256 Signature"
        }
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_payload, f, indent=2)

    print(f"\nBenchmark completed and saved to {RESULTS_FILE}")
    print(json.dumps(benchmark_payload["benchmarks"], indent=2))


if __name__ == "__main__":
    main()
