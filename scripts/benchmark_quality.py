"""
DataGuard Quality Engine Performance Benchmark.
Benchmarks Great Expectations automated data quality validation across multiple dataset sizes:
1,000 rows, 10,000 rows, and 100,000 rows.
Measures latency (p50, p95, p99, mean) and throughput (rows/sec).
Persists structured benchmark metrics to dataguard/benchmarks/quality_results.json.
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

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import great_expectations as gx

from dataguard.contracts.registry import ContractRegistryService
from dataguard.quality.result_store import QualityResultStore
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.datasets import DatasetCatalog

BENCHMARK_DIR = ROOT_DIR / "dataguard" / "benchmarks"
RESULTS_FILE = BENCHMARK_DIR / "quality_results.json"


def get_system_hardware_info():
    """Captures CPU, RAM, and OS metadata."""
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    cpu_freq = psutil.cpu_freq()
    freq_str = f" @ {cpu_freq.max:.1f}MHz" if cpu_freq else ""
    cpu_info = f"{platform.processor() or 'x86_64'} ({os.cpu_count()} logical cores{freq_str})"

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": cpu_info,
        "ram_total_gb": ram_gb,
        "python_version": platform.python_version(),
        "great_expectations_version": gx.__version__,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def benchmark_size(runner: DataQualityRunner, dataset_name: str, num_rows: int, iterations: int = 5):
    """Executes benchmark iterations for a given dataset size and computes statistical metrics."""
    print(f"\n========================================================")
    print(f"Benchmarking {dataset_name} ({num_rows:,} rows) - {iterations} iterations")
    print(f"========================================================")

    # Pre-generate dataset to measure validation execution only
    print(f"Generating synthetic dataset of {num_rows:,} rows...")
    df = DatasetCatalog.generate_clean_dataset(dataset_name, num_rows=num_rows)
    print(f"Dataset generated. Memory usage: {df.memory_usage(deep=True).sum() / (1024**2):.2f} MB")

    latencies_ms = []
    checks_count = 0

    # Warmup run
    print("Executing warmup run...")
    warmup_res = runner.run_validation(dataset_name, df=df, validate_referential=False)
    checks_count = warmup_res.total_checks

    for i in range(1, iterations + 1):
        t0 = time.perf_counter()
        res = runner.run_validation(dataset_name, df=df, validate_referential=False)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)
        print(f"  Iteration {i}/{iterations}: {elapsed_ms:.2f} ms (Status: {res.overall_status.value}, Score: {res.quality_score}%)")

    latencies_arr = np.array(latencies_ms)
    p50 = float(np.percentile(latencies_arr, 50))
    p95 = float(np.percentile(latencies_arr, 95))
    p99 = float(np.percentile(latencies_arr, 99))
    mean_lat = float(np.mean(latencies_arr))
    std_lat = float(np.std(latencies_arr))
    min_lat = float(np.min(latencies_arr))
    max_lat = float(np.max(latencies_arr))

    # Throughput (rows/sec based on mean latency)
    rows_per_sec = round(num_rows / (mean_lat / 1000.0), 2) if mean_lat > 0 else 0.0

    return {
        "dataset": dataset_name,
        "row_count": num_rows,
        "iterations": iterations,
        "number_of_checks": checks_count,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "mean_ms": round(mean_lat, 2),
        "std_ms": round(std_lat, 2),
        "min_ms": round(min_lat, 2),
        "max_ms": round(max_lat, 2),
        "rows_per_second": rows_per_sec
    }


def main():
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    hw_info = get_system_hardware_info()
    print("Hardware & Platform Environment:")
    print(json.dumps(hw_info, indent=2))

    registry = ContractRegistryService()
    # Use isolated SQLite store for benchmark to eliminate network I/O variability
    bench_db = BENCHMARK_DIR / "temp_benchmark.db"
    store = QualityResultStore(db_path=bench_db)
    runner = DataQualityRunner(registry_service=registry, result_store=store)

    sizes = [
        (1_000, 5),
        (10_000, 5),
        (100_000, 3)
    ]

    benchmark_runs = []
    for num_rows, iters in sizes:
        bench_result = benchmark_size(runner, dataset_name="orders", num_rows=num_rows, iterations=iters)
        benchmark_runs.append(bench_result)

    final_payload = {
        "system": hw_info,
        "benchmarks": benchmark_runs,
        "summary": {
            "total_benchmark_sizes": len(sizes),
            "max_rows_tested": 100_000,
            "engine": "Great Expectations 1.x"
        }
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)

    print(f"\nBenchmark successfully saved to {RESULTS_FILE}")

    # Clean up temp db
    if bench_db.exists():
        try:
            os.remove(bench_db)
        except Exception:
            pass


if __name__ == "__main__":
    main()
