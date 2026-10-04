# DataGuard Benchmarks — Apache Airflow Pipeline Orchestration (Phase G)

## 1. Test Environment

| Component | Specification |
| :--- | :--- |
| **Operating System** | Windows 11 Pro (Build 10.0.26200) |
| **CPU Architecture** | Intel64 (16 logical cores @ 2.30 GHz) |
| **System Memory (RAM)**| 15.69 GB |
| **Python Runtime** | Python 3.13.9 |
| **Database Engine** | PostgreSQL 16.15 (Docker Container on Alpine Linux) |
| **Airflow Engine** | Apache Airflow 2.9.0 (Docker Container on Python 3.12) |

---

## 2. Benchmark Results Summary

Data generated from `dataguard/benchmarks/airflow_results.json` across 10-50 iterations per operation:

### A. DAG Loading & Parse Performance
Measures compilation and task graph synthesis latency across all production and demo DAGs:
- **Mean Parse Time**: `4.67 ms`
- **P50 (Median)**: `3.50 ms`
- **P95**: `9.75 ms`
- **P99**: `10.99 ms`
- **Parse Throughput**: `213.92 DAGs/sec`

### B. End-to-End Clean Pipeline Execution Latency
Measures total elapsed time for complete lifecycle: Contract Fetch -> Schema Diff -> Great Expectations Quality Evaluation -> OpenLineage Emission -> PostgreSQL Persistence.

| Pipeline ID | Dataset | P50 (ms) | P95 (ms) | Mean (ms) | Throughput (Runs/sec) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_quality_pipeline` | `customers` | 274.19 | 375.33 | 296.31 | 3.37 |
| `transaction_quality_pipeline` | `transactions` | 876.90 | 897.84 | 873.75 | 1.14 |
| `feature_quality_pipeline` | `customer_features` | 287.22 | 306.30 | 291.07 | 3.44 |

*Note: `transaction_quality_pipeline` evaluates relational foreign key constraints against both `customers` and `merchants`, resulting in comprehensive multi-table join verification in under 900 ms.*

### C. Failure Scenario Fast-Fail Latency
Measures the latency from defect injection to pipeline termination, OpenLineage `FAIL` event emission, and incident creation:

| Defect Scenario | Target Pipeline | Mean Latency (ms) | P95 Latency (ms) | Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Breaking Schema Drift** | `customer_quality_pipeline` | **109.85 ms** | 145.44 ms | Fails immediately at Schema Diff stage (bypasses Great Expectations) |
| **Stale Dataset SLA Breach**| `freshness_monitoring_pipeline`| **98.23 ms** | 99.32 ms | Fails at Freshness SLA stage |
| **Null Constraint Violation**| `customer_quality_pipeline` | **251.43 ms** | 256.53 ms | Fails at Quality validation stage; opens incident |
| **Duplicate Key Violation** | `customer_quality_pipeline` | **249.68 ms** | 251.96 ms | Fails at Quality validation stage; opens incident |
| **Invalid Enum Value** | `customer_quality_pipeline` | **249.36 ms** | 257.93 ms | Fails at Quality validation stage; opens incident |

### D. Idempotent Rerun Overhead
Measures execution of repeated runs using a pre-existing `run_id`:
- **Mean Duration**: `265.60 ms`
- **P95 Duration**: `279.75 ms`
- **PostgreSQL Collision Handling**: Zero duplicate key errors; clean record update.

### E. PostgreSQL Repository & Analytics Query Throughput

| Repository Operation | Mean Latency (ms) | P95 Latency (ms) | Throughput (Ops/sec) |
| :--- | :--- | :--- | :--- |
| `get_pipeline_summary` | 4.11 ms | 4.60 ms | **243.0 ops/sec** |
| `get_pipeline_health` | 6.52 ms | 7.19 ms | **153.3 ops/sec** |
| `list_runs` | 2.34 ms | 2.68 ms | **427.8 ops/sec** |
| `list_pipelines` | 2.31 ms | 2.67 ms | **432.3 ops/sec** |
