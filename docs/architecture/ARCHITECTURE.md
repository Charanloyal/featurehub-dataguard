# System Architecture Specification

## Overview

FeatureHub & DataGuard forms a production-grade data engineering and ML governance platform designed for low-latency feature serving and zero-downtime schema evolution.

```
+-------------------------------------------------------------------------------+
|                            STORAGE & INGESTION                                |
|  +--------------------+    +--------------------+    +---------------------+  |
|  | PostgreSQL DB      |    | Seed Event Data    |    | Local Parquet       |  |
|  +---------+----------+    +---------+----------+    +----------+----------+  |
+------------|-------------------------|--------------------------|-------------+
             |                         |                          |
             v                         v                          v
+-------------------------------------------------------------------------------+
|                        FEATUREHUB FEATURE STORE PLATFORM                      |
|  +-----------------------+    +-----------------------+                         |
|  | Feature Compute       |--->| Offline Parquet Store |                         |
|  | (Windowed Aggregates) |    +-----------+-----------+                         |
|  +-----------------------+                |                                     |
|              |                            v                                     |
|              v                +-----------------------+                         |
|  +-----------------------+    | Point-in-Time Engine  |                         |
|  | Feature Registry      |    | (Zero Target Leakage) |                         |
|  +-----------+-----------+    +-----------+-----------+                         |
|              |                            |                                     |
|              v                            v                                     |
|  +-----------------------+    +-----------------------+                         |
|  | Online Materializer   |    | Model Training        |                         |
|  +-----------+-----------+    | (Random Forest Fraud) |                         |
|              |                +-----------+-----------+                         |
|              v                            |                                     |
|  +-----------------------+                |                                     |
|  | Redis Online Store    |                |                                     |
|  +-----------+-----------+                |                                     |
|              |                            |                                     |
|              +--------------+-------------+                                     |
|                             |                                                   |
|                             v                                                   |
|                +--------------------------+                                     |
|                | FastAPI Prediction API   |                                     |
|                +--------------------------+                                     |
+-------------------------------------------------------------------------------+
             ^                                                    ^
             |                                                    |
+------------|----------------------------------------------------|-------------+
|                      DATAGUARD RELIABILITY PLATFORM             |             |
|  +-----------------------+    +-----------------------+    +----+------------+|
|  | 25 Data Contracts     |--->| Schema Diff Engine    |--->| CI Gatekeeper   ||
|  +-----------------------+    +-----------------------+    +-----------------+|
|              |                                                                |
|              v                                                                |
|  +-----------------------+    +-----------------------+                       |
|  | Data Quality Engine   |--->| Quality Incidents     |                       |
|  +-----------------------+    +-----------------------+                       |
+-------------------------------------------------------------------------------+
```

## Subsystem Details

### 1. FeatureHub Subsystem
- **Feature Catalog**: 122 registered features categorized across 6 domain groups (`customer_velocity`, `account_balance_stats`, `merchant_risk_profile`, `transaction_window_stats`, `temporal_behavioral`, `velocity_and_risk_scores`).
- **Point-In-Time (PIT) Engine**: Implements strictly backward `merge_asof` matching observation event timestamp $T$ against historical feature timestamps $t_f \le T$. Prevents training-serving skew.
- **Online Materializer**: Idempotent background process copying offline Parquet vectors to Redis key-value pairs (`featurehub:<entity>:<id>`).

### 2. DataGuard Subsystem
- **YAML Contracts**: Declarative schema definitions specifying data types, nullability, uniqueness, and allowed values across 25 core datasets.
- **Schema Drift Engine**: Automates comparison of incoming PR schemas against target baselines, classifying drifts as `SAFE`, `WARNING`, or `BREAKING`.
- **Quality & Incidents**: Statistical quality checks capturing anomalies and creating structured incident tickets (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`).
