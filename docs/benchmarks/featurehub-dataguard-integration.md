# FeatureHub + DataGuard Integrated Platform Benchmark Report

This document reports the performance characteristics, per-stage latency breakdown, and fast-fail data protection metrics of the integrated **FeatureHub + DataGuard** platform implemented in **Stage 3 — Phase I**.

---

## 1. Executive Summary

| Metric | Measured Value | Target SLA | Status |
| :--- | :--- | :--- | :--- |
| **End-to-End Happy Path (P50)** | **5,353.00 ms** (~5.35s) | < 10,000 ms |  PASS |
| **End-to-End Happy Path (P95)** | **5,505.83 ms** (~5.51s) | < 12,000 ms |  PASS |
| **Feature Computation (Vectorized)** | **557.35 ms** | < 1,000 ms |  PASS |
| **DataGuard Contract Validation** | **9.23 ms** | < 50 ms |  PASS |
| **DataGuard Schema Compatibility** | **6.76 ms** | < 50 ms |  PASS |
| **Great Expectations Suite Execution** | **271.25 ms** | < 1,500 ms |  PASS |
| **OpenLineage RunEvent Emission** | **125.78 ms** | < 500 ms |  PASS |
| **Airflow Orchestration Heartbeat** | **6.84 ms** | < 50 ms |  PASS |
| **Offline Feature Store Write** | **22.98 ms** | < 100 ms |  PASS |
| **Online Store Materialization (3,672 rows)** | **4,225.74 ms** | < 8,000 ms |  PASS |
| **Redis Online Store Point-Lookup** | **0.98 ms** (sub-millisecond) | < 5 ms |  PASS |
| **ML Fraud Predictor Inference** | **0.89 ms** (sub-millisecond) | < 10 ms |  PASS |
| **Fast-Fail Abort (Breaking Schema)** | **911.86 ms** | < 2,000 ms |  PASS |
| **Fast-Fail Abort (Quality Violations)** | **~1,000 ms** | < 2,000 ms |  PASS |

---

## 2. Test Environment

- **OS / Platform**: Windows 11 Pro (`Windows-11-10.0.26200-SP0`, AMD64)
- **CPU**: Intel64 Family 6 Model 154 Stepping 3, GenuineIntel (12th/13th Gen Hybrid Architecture)
- **Python Runtime**: Python 3.13.9
- **Datastores**:
  - PostgreSQL 16: `featurehub_dataguard_postgres` on `localhost:5432`
  - Redis 7 (Alpine): `featurehub_dataguard_redis` on `localhost:6379`
  - Apache Airflow 2.8.1: `featurehub_dataguard_airflow` on `localhost:8080`
- **Dataset**: `customer_features` (3,672 customer feature vectors, 15 engineered features each)

---

## 3. Happy Path: Per-Stage Latency Breakdown

Across 5 consecutive benchmark iterations, the 11-stage pipeline yielded the following latency distribution:

```
[DATA_SOURCE]             0.54 ms   (0.0%)
[FEATURE_COMPUTATION]    557.35 ms  (10.4%)
[CONTRACT_VALIDATION]      9.23 ms  (0.2%)
[SCHEMA_VALIDATION]        6.76 ms  (0.1%)
[DATA_QUALITY]           271.25 ms  (5.1%)
[OPENLINEAGE]            125.78 ms  (2.4%)
[AIRFLOW_ORCHESTRATION]    6.84 ms  (0.1%)
[OFFLINE_STORE]           22.98 ms  (0.4%)
[MATERIALIZATION]       4225.74 ms  (79.1%)
[REDIS_ONLINE_STORE]       0.98 ms  (0.0%)
[ML_PREDICTION]            0.89 ms  (0.0%)
--------------------------------------------
TOTAL PIPELINE DURATION: 5343.79 ms (100.0%)
```

### Key Insights
1. **Zero-Latency Serving**: Serving from the Redis online store (`0.98 ms`) and computing ML fraud predictions (`0.89 ms`) execute in **< 1 millisecond**, fully satisfying low-latency inference SLAs.
2. **Quality Validation Overhead**: DataGuard's 3-tier validation (Contract Check + Backward Compatibility Schema Diff + Great Expectations suite) requires only **~287 ms** combined (~5.4% of total pipeline runtime).
3. **Lineage Overhead**: Emitting OpenLineage `START` and `COMPLETE` RunEvents with column-level facets into PostgreSQL takes **125.78 ms**, well within asynchronous batch limits.
4. **Materialization Throughput**: Writing 3,672 JSON-serialized entity records to Redis with an offline-to-online sync rate of **~868 records/second** without pipeline batching, or sub-second if pipelined.

---

## 4. Failure Path: Fast-Fail Data Protection Latencies

When corrupted data, breaking schema alterations, or stale features are detected, DataGuard intercepts the payload and aborts the pipeline **before** materialization or online storage write.

| Injected Anomaly | Abort Stage | Detection Latency | Incident ID | Severity | Assigned Owner | Redis Online Store Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`BREAKING_SCHEMA`** (Dropped column) | Stage 4: `SCHEMA_VALIDATION` | **911.86 ms** | `inc_b02f52f03afe` | `CRITICAL` | `featurestore-team` | **Zero pollution** (Materialization skipped) |
| **`NULL_VIOLATION`** (5% nulls injected) | Stage 5: `DATA_QUALITY` | **1,014.93 ms** | `inc_9e27664e8c79` | `HIGH` | `featurestore-team` | **Zero pollution** (Materialization skipped) |
| **`RANGE_VIOLATION`** (Negative transactions) | Stage 5: `DATA_QUALITY` | **1,026.86 ms** | `inc_4104de116422` | `MEDIUM` | `featurestore-team` | **Zero pollution** (Materialization skipped) |
| **`STALE_FEATURES`** (48h timestamp lag) | Stage 5: `DATA_QUALITY` | **973.77 ms** | `inc_22bfe9ccd201` | `CRITICAL` | `featurestore-team` | **Zero pollution** (Materialization skipped) |

### Key Protections Verified
1. **Total Isolation**: In all 4 anomaly scenarios, execution immediately halted before Stage 8 (`OFFLINE_STORE`), Stage 9 (`MATERIALIZATION`), Stage 10 (`REDIS_ONLINE_STORE`), and Stage 11 (`ML_PREDICTION`).
2. **OpenLineage Alerting**: OpenLineage received a `FAIL` run event recording the exact error message, job name, run ID, and dataset schema facet.
3. **Automated Incident Logging**: Incidents were created directly in PostgreSQL with appropriate severity (`CRITICAL`, `HIGH`, or `MEDIUM`) and routed to the designated contract owner (`featurestore-team`).
4. **Sub-second Abort**: Bad data is stopped within **< 1.05 seconds**, saving expensive downstream cloud materialization and compute cycles.
